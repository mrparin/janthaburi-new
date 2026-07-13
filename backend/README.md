# Durian Dashboard — Backend (FastAPI)

## Stack
- **FastAPI** + **Uvicorn** — async REST API + WebSocket
- **paho-mqtt** — MQTT subscriber
- **SQLite** — short-term sensor history
- **httpx** — TMD & OpenWeather HTTP client

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

## Environment Variables

Copy `.env.example` from root or edit `.env`:

| Variable | Description |
|---|---|
| `MQTT_HOST` | MQTT broker hostname |
| `MQTT_TOPIC` | MQTT topic to subscribe |
| `DB_PATH` | SQLite file path (relative to `backend/`) |
| `CORS_ORIGINS` | Comma-separated allowed origins (e.g. `http://localhost:3000`) |
| `TMD_PROVINCE` | Default province for weather forecast |
| `APP_PORT` | Port to run on (default: 8080) |

## Run (Development)

```bash
# From backend/ directory
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Or from project root:
```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8080 --reload --app-dir backend
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/latest` | Latest sensor reading |
| GET | `/api/history` | Historical data (field + hours) |
| GET | `/api/scatter` | Scatter plot pairs |
| GET | `/api/weather` | TMD weather forecast |
| GET | `/api/weather/raw` | Raw TMD response |
| GET | `/api/farm-summary` | Farm risk summary |
| GET | `/api/locations/provinces` | Province list |
| GET | `/api/locations/amphoes` | Amphoe list |
| GET | `/api/locations/tambons` | Tambon list |
| GET | `/api/line/alert-status` | LINE alert status |
| POST | `/api/line/alert-toggle` | Toggle LINE alert |
| POST | `/api/line/test-alert` | Send test LINE alert |
| WS  | `/ws` | Real-time sensor stream |
