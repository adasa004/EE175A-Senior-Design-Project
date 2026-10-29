"""Local, loopback-only demonstration API for the parking rover dashboard.
Uses Python's standard library and SQLite; no hardware is controlled.
"""
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get('ROVER_DB_PATH', ROOT / 'data' / 'rover.db'))
HOST = '127.0.0.1'  # Deliberately local-only; no authentication is implemented.
PORT = int(os.environ.get('ROVER_PORT', '8000'))


def connect():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    return db


def initialize():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript((ROOT / 'backend' / 'schema.sql').read_text(encoding='utf-8'))
        if not db.execute('SELECT 1 FROM settings WHERE key = ?', ('seeded',)).fetchone():
            db.executemany('INSERT INTO permits (plate, permit_type, status) VALUES (?, ?, ?)', [
                ('6LMT914', 'Student', 'valid'), ('4ABC123', 'Staff', 'valid')])
            rows = [
                ('7KDX284', 72, 'Inconclusive', 'uncertain', 'Lot A · Aisle 03', '10:24 AM', 'Awaiting review'),
                ('8NVR521', 96, 'No permit found', 'missing', 'Lot A · Aisle 02', '10:18 AM', 'Awaiting review'),
                ('6LMT914', 98, 'Valid permit', 'valid', 'Lot A · Aisle 01', '10:12 AM', 'No review needed'),
            ]
            db.executemany('INSERT INTO detections (plate, confidence, permit, reason, location, display_time, status) VALUES (?, ?, ?, ?, ?, ?, ?)', rows)
            db.execute("INSERT INTO settings (key, value) VALUES ('seeded', '1')")
            db.execute("INSERT INTO settings (key, value) VALUES ('scan_count', '12')")
            db.execute("INSERT INTO settings (key, value) VALUES ('paused', 'false')")
            db.execute("INSERT INTO settings (key, value) VALUES ('telemetry', ?)", (json.dumps({'battery_percent': 78, 'speed_mps': 0.7, 'location': 'Lot A · Aisle 03', 'obstacle_status': 'clear', 'source': 'simulated', 'timestamp': None}),))


def state(db):
    records = []
    for row in db.execute('SELECT * FROM detections ORDER BY id DESC'):
        records.append({'id': row['id'], 'plate': row['plate'], 'confidence': row['confidence'],
                        'permit': row['permit'], 'reason': row['reason'], 'location': row['location'],
                        'time': row['display_time'], 'status': row['status'], 'note': row['note']})
    settings = dict(db.execute('SELECT key, value FROM settings').fetchall())
    return {'records': records, 'scans': int(settings['scan_count']), 'paused': settings['paused'] == 'true',
            'telemetry': json.loads(settings['telemetry']), 'storage': 'sqlite'}


def add_detection(db, data):
    plate = str(data.get('plate', '')).strip().upper()
    if not re.fullmatch(r'[A-Z0-9]{1,10}', plate):
        raise ValueError('Plate must contain 1–10 letters or digits.')
    confidence = data.get('confidence')
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 100:
        raise ValueError('Confidence must be a number from 0 to 100.')
    location = str(data.get('location', 'Unknown'))[:100]
    match = db.execute('SELECT status FROM permits WHERE plate = ?', (plate,)).fetchone()
    reason = 'uncertain' if confidence < 85 else ('valid' if match and match['status'] == 'valid' else 'missing')
    result = {'uncertain': 'Inconclusive', 'valid': 'Valid permit', 'missing': 'No permit found'}[reason]
    status = 'No review needed' if reason == 'valid' else 'Awaiting review'
    display_time = datetime.now().astimezone().strftime('%I:%M %p').lstrip('0')
    db.execute('INSERT INTO detections (plate, confidence, permit, reason, location, display_time, status) VALUES (?, ?, ?, ?, ?, ?, ?)',
               (plate, confidence, result, reason, location, display_time, status))
    db.execute("UPDATE settings SET value = CAST(value AS INTEGER) + 1 WHERE key = 'scan_count'")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print('%s - %s' % (self.address_string(), fmt % args))

    def response(self, code, body, content_type='application/json; charset=utf-8'):
        encoded = body if isinstance(body, bytes) else json.dumps(body).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(encoded)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/api/state':
            with connect() as db:
                self.response(200, state(db))
        elif path in ('/', '/index.html'):
            self.response(200, (ROOT / 'dist' / 'index.html').read_bytes(), 'text/html; charset=utf-8')
        else:
            self.response(404, {'error': 'Not found'})

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length < 0 or length > 16384:
                raise ValueError('Request too large.')
            data = json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(data, dict):
                raise ValueError('Expected a JSON object.')
            path = urlparse(self.path).path
            with connect() as db:
                if path == '/api/demo/pause':
                    current = db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()[0]
                    db.execute("UPDATE settings SET value=? WHERE key='paused'", ('false' if current == 'true' else 'true',))
                elif path == '/api/demo/detection':
                    if db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()[0] == 'true':
                        raise ValueError('Resume the simulated patrol first.')
                    count = int(db.execute("SELECT value FROM settings WHERE key='scan_count'").fetchone()[0])
                    samples = [('9BXY146', 89), ('5RPK230', 67), ('6LMT914', 99)]
                    plate, confidence = samples[(count - 12) % len(samples)]
                    add_detection(db, {'plate': plate, 'confidence': confidence, 'location': 'Lot A · Aisle 03'})
                elif path == '/api/detections':
                    add_detection(db, data)
                elif path == '/api/review':
                    decision = data.get('decision')
                    if decision not in ('Reviewed', 'Escalated') or not isinstance(data.get('id'), int):
                        raise ValueError('Invalid review decision or detection ID.')
                    note = str(data.get('note', '')).strip()[:500]
                    cursor = db.execute("UPDATE detections SET status=?, note=? WHERE id=? AND status='Awaiting review'", (decision, note, data['id']))
                    if cursor.rowcount != 1:
                        raise ValueError('Detection not found or already resolved.')
                elif path == '/api/telemetry':
                    battery, speed = data.get('battery_percent'), data.get('speed_mps')
                    if isinstance(battery, bool) or not isinstance(battery, (int, float)) or not 0 <= battery <= 100:
                        raise ValueError('battery_percent must be from 0 to 100.')
                    if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not 0 <= speed <= 20:
                        raise ValueError('speed_mps must be from 0 to 20.')
                    telemetry = {'battery_percent': battery, 'speed_mps': speed, 'location': str(data.get('location', 'Unknown'))[:100],
                                 'obstacle_status': str(data.get('obstacle_status', 'unknown'))[:30], 'source': 'test input',
                                 'timestamp': datetime.now(timezone.utc).isoformat()}
                    db.execute("UPDATE settings SET value=? WHERE key='telemetry'", (json.dumps(telemetry),))
                else:
                    return self.response(404, {'error': 'Not found'})
                self.response(200, state(db))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.response(400, {'error': str(exc)})

if __name__ == '__main__':
    initialize()
    print(f'Parking Rover dashboard: http://{HOST}:{PORT} (local demo only)', flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
