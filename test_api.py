import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        cls.base = f'http://127.0.0.1:{port}'
        env = dict(os.environ, ROVER_PORT=str(port), ROVER_DB_PATH=str(Path(cls.tmp.name) / 'test.db'))
        cls.proc = subprocess.Popen([sys.executable, str(ROOT / 'backend/server.py')], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                cls.request('/api/state')
                break
            except OSError:
                time.sleep(.05)
        else:
            raise RuntimeError('Server did not start')

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)
        cls.tmp.cleanup()

    @classmethod
    def request(cls, path, body=None):
        req = urllib.request.Request(cls.base + path, data=None if body is None else json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.load(response)

    def test_full_workflow(self):
        initial = self.request('/api/state')
        self.assertEqual(initial['storage'], 'sqlite')
        created = self.request('/api/detections', {'plate': '6LMT914', 'confidence': 99, 'location': 'Test lot'})
        self.assertEqual(created['records'][0]['permit'], 'Valid permit')
        uncertain = self.request('/api/detections', {'plate': '6LMT914', 'confidence': 70, 'location': 'Test lot'})
        row = uncertain['records'][0]
        self.assertEqual(row['permit'], 'Inconclusive')
        reviewed = self.request('/api/review', {'id': row['id'], 'decision': 'Escalated', 'note': 'Verify'})
        self.assertEqual(reviewed['records'][0]['status'], 'Escalated')
        self.assertEqual(self.request('/api/state')['records'][0]['note'], 'Verify')
        telem = self.request('/api/telemetry', {'battery_percent': 44, 'speed_mps': .3, 'location': 'Test lot', 'obstacle_status': 'clear'})
        self.assertEqual(telem['telemetry']['battery_percent'], 44)
        with self.assertRaises(urllib.error.HTTPError) as failure:
            self.request('/api/detections', {'plate': '???', 'confidence': 100})
        self.assertEqual(failure.exception.code, 400)
        paused = self.request('/api/demo/pause', {})
        self.assertTrue(paused['paused'])
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/api/demo/detection', {})
        self.assertFalse(self.request('/api/demo/pause', {})['paused'])
        self.assertEqual(self.request('/api/demo/detection', {})['scans'], initial['scans'] + 3)

if __name__ == '__main__':
    unittest.main()
