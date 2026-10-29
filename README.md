# Parking Rover Operator Dashboard

A senior design prototype for monitoring a parking rover and reviewing detected license plates. The dashboard works with simulated data. No camera, hardware, real permits, notifications, or ticketing system is connected.

## Two ways to run it

1. **Local project:** Python serves the dashboard and an API. Data and review decisions are stored in a local SQLite database. This project runs without ChatGPT or an internet connection once Python is installed.
2. **Private hosted prototype:** The existing hosted site serves the same frontend as a static demo. Its simulated records and decisions stay in that browser's local storage. It does **not** run the included Python backend or share data across devices. Moving the backend online separately is future work.

## What you need

- Python 3.9 or newer from https://www.python.org/downloads/ (on Windows, select **Add Python to PATH** during installation).
- Visual Studio Code, if you want to edit the project. The VS Code Python extension is optional.
- A modern web browser.

There are **no third-party Python packages to install**. Python's standard library includes the HTTP server and SQLite support. `requirements.txt` is intentionally empty.

## Run in VS Code on Windows

1. Download the ZIP and extract it. Open the extracted `parking-rover-dashboard` folder in VS Code with **File → Open Folder**.
2. Select **Terminal → New Terminal**.
3. Run:

   ```powershell
   py backend/server.py
   ```

   If `py` is not recognized, try `python backend/server.py`. On macOS/Linux, run `python3 backend/server.py`.
4. Open **http://127.0.0.1:8000** in your browser. Leave the terminal running. Use **Ctrl+C** in the terminal to stop the server.
5. Look for **Local backend · SQLite database** at the bottom of the dashboard. Try *Simulate detection*, inspect a row, and save a review. Reload: the decision will remain in the database.

The first run creates `data/rover.db` and seeds fictional permits and scans. To reset demo data, stop the server and delete that file; the next run recreates it. This permanently removes local demo decisions. The file is deliberately excluded from Git.

## Project files

```text
parking-rover-dashboard/
  dist/index.html           Frontend: HTML, CSS, and JavaScript
  backend/server.py         Local HTTP API and SQLite logic
  backend/schema.sql        Database tables
  tools/send_test_data.py   Example simulated sender
  tests/test_api.py         Local API integration tests
  requirements.txt          Dependency list (standard library only)
  .gitignore                Excludes generated database and caches
  README.md                 This guide
```

The frontend is a single file to make the current prototype easy to edit. The Python backend and its data format are independent of ChatGPT. The local server serves `dist/index.html`; opening that file directly will instead use the browser-only demo.

## Try a simulated external data source

With the server running, open a second VS Code terminal:

```powershell
py tools/send_test_data.py
```

This sends a fictional battery reading and plate detection to the local API. The dashboard refreshes every five seconds. It does not communicate with a rover. The sample sends to port 8000; edit `BASE` in the script if you change ports.

## Local API for integration experiments

The following endpoints are served at `http://127.0.0.1:8000`. All POST requests use JSON. The server binds only to the local computer and has **no authentication**; it is for local testing, not deployment on a network.

| Endpoint | Purpose | Example body |
|---|---|---|
| `GET /api/state` | Return dashboard records, telemetry, and simulated patrol state. | — |
| `POST /api/telemetry` | Submit a test sensor update. | `{"battery_percent":65,"speed_mps":0.4,"location":"Lot B","obstacle_status":"clear"}` |
| `POST /api/detections` | Submit a plate and perform a demo permit lookup. | `{"plate":"9TEST42","confidence":91,"location":"Lot B"}` |
| `POST /api/review` | Review an awaiting detection. | `{"id":1,"decision":"Escalated","note":"Check in person"}` |
| `POST /api/demo/detection` | Add one of the preset simulated detections. | `{}` |
| `POST /api/demo/pause` | Toggle the simulated patrol state. | `{}` |

Confidence is a percentage between 0 and 100. In this demo, values below 85 are flagged uncertain; otherwise the backend checks the local permit table. That threshold is a placeholder, not a validated accuracy threshold. Uncertain reads and unmatched plates are queued for human review; a mismatch is not proof of a violation. Neither review action sends a message or creates a ticket.

For test data, you can change the seed entries in `initialize()` in `backend/server.py` **before** first run, or reset the generated database after changing them. The SQLite tables are defined in `backend/schema.sql`. Coordinate the schema and fields with the teammate building the permit database; this is an example schema, not a requirement for theirs.

## How to modify and connect real components later

- **Dashboard:** edit `dist/index.html`, save, then refresh the browser.
- **Backend and permit matching:** edit `backend/server.py`; stop and restart it after changes. `backend/schema.sql` defines the demo tables, but changes to existing databases need migrations or a reset.
- **Sensors:** a rover-side program could format data like `tools/send_test_data.py`; the dashboard already displays test battery, speed, position and obstacle status. Plan an authenticated, encrypted network API before connecting a remote rover. The five-second refresh is a starting point, not a real-time control loop.
- **Plate recognition:** have the vision program send its plate, confidence and location to a secured backend. Store any evidence images separately, with access and retention rules appropriate to your project. Current data is fictional.
- **Camera:** the current camera picture is an illustration. Integrating image snapshots or an authenticated video stream requires additional code and a suitable transport; an API URL alone does not create a video feed.
- **Controls:** the pause/resume button changes only simulated state. There is no motor-command endpoint. Design and validate device authentication, acknowledgments, connection-loss behavior, and an independent physical emergency stop before considering real control.
- **Hosting independently:** host the frontend and a Python-compatible backend outside ChatGPT. The local server is intentionally not production-ready: add authenticated access, HTTPS, secure device credentials, privacy controls, request limits, backups, and a production application server before exposing it. The hosted static demo has a different storage model than the local SQLite project. This ZIP contains no ChatGPT SDK or service dependency.

## Configuration

`ROVER_PORT` changes the local port (default `8000`). `ROVER_DB_PATH` changes the database file location. For example, in PowerShell:

```powershell
$env:ROVER_PORT = '8080'
py backend/server.py
```

The bind address is intentionally fixed to `127.0.0.1` in `backend/server.py`. Do not expose this demo server publicly as-is.

## Tests

From the project folder, run:

```powershell
py -m unittest discover -s tests -v
```

The test starts a local server with a temporary SQLite database, exercises demo detection, permit lookup, review, telemetry, and invalid input, and cleans up afterward. On macOS/Linux use `python3`.
