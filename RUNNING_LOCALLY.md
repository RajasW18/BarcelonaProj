# 🚀 Running Barça Bot Locally

This guide walks you through spinning up the full stack — database, backend API, and frontend — on your local machine.

---

## Prerequisites

Make sure you have these installed before starting:

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.12+ | `python --version` |
| Node.js | 18+ | `node --version` |
| Docker Desktop | Latest | `docker --version` |

Also ensure your `.env` file is populated with valid API keys:

```
OPENAI_API_KEY=sk-...
FOOTBALL_DATA_API_KEY=...
DATABASE_URL=postgresql://barca:barca@localhost:5432/barca
```

---

## Step 1 — Start the Database (Docker)

Open a terminal in the project root and run:

```bash
docker compose up -d
```

Wait ~10 seconds, then verify the database is healthy:

```bash
docker compose ps
# STATUS column should show: healthy
```

> **Tip:** If the container fails, run `docker compose logs` to inspect errors.

---

## Step 2 — Activate the Python Virtual Environment

```bash
# Windows (PowerShell)
.venv\Scripts\activate

# Mac / Linux
source .venv/bin/activate
```

You should see `(.venv)` appear in your terminal prompt.

> **First time only?** Create the venv and install dependencies first:
> ```bash
> python -m venv .venv
> .venv\Scripts\activate        # or source .venv/bin/activate
> pip install -r api/requirements.txt
> ```

---

## Step 3 — Start the Backend (FastAPI)

From the project root, with the venv active:

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Verify it's running by visiting:  
👉 **http://localhost:8000/health** → should return `{"status":"ok","agent":"BarcaBot"}`

You can also explore the auto-generated API docs at:  
👉 **http://localhost:8000/docs**

---

## Step 4 — Start the Frontend (Vite / React)

Open a **second terminal** (keep the backend running), then:

```bash
cd frontend
npm install      # only needed the first time, or after pulling new changes
npm run dev
```

The app will be available at:  
👉 **http://localhost:5173**

---

## All Services at a Glance

| Service | URL | Command |
|---------|-----|---------|
| PostgreSQL (Docker) | `localhost:5432` | `docker compose up -d` |
| FastAPI backend | http://localhost:8000 | `uvicorn api.main:app --reload` |
| React frontend | http://localhost:5173 | `npm run dev` (in `frontend/`) |

---

## Stopping Everything

```bash
# Stop the frontend: Ctrl+C in its terminal

# Stop the backend: Ctrl+C in its terminal

# Stop and remove the Docker containers
docker compose down
```

To also wipe the database volume (full reset):

```bash
docker compose down -v
```

---

## Common Issues

| Problem | Fix |
|---------|-----|
| `docker compose ps` shows unhealthy | Wait a few more seconds or run `docker compose restart` |
| `ModuleNotFoundError` in backend | Make sure the venv is activated and `pip install -r api/requirements.txt` has been run |
| Frontend shows blank page / CORS error | Confirm the backend is running on port 8000 before starting the frontend |
| Port 8000 already in use | Kill the existing process or run the backend on a different port: `--port 8001` |
| Voice input not working | Use Chrome or Edge — Firefox does not support the Web Speech API |

---

*Visca el Barça! 🔵🔴*
