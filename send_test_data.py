"""Send simulated data to the local backend. This does not connect to hardware."""
import json
import urllib.request

BASE = 'http://127.0.0.1:8000'

def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req) as response:
        print(path, response.status)

if __name__ == '__main__':
    post('/api/telemetry', {'battery_percent': 65, 'speed_mps': 0.4,
                            'location': 'Lot B · Aisle 02', 'obstacle_status': 'clear'})
    post('/api/detections', {'plate': '9TEST42', 'confidence': 91,
                             'location': 'Lot B · Aisle 02'})
    print('Test data sent. Refresh the dashboard or wait up to five seconds.')
