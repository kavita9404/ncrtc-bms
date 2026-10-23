# NCRTC Bus Management System

Control-room software for NCRTC's feeder bus network around the Delhi-NCR rapid-rail corridor. It does four things: shows where the buses are (AVLS), plans who drives what (Scheduling), tracks problems until they're fixed (IMS), and pushes notices to drivers (CMS).

The look and feel follows RedBus: red header, a big search card on the home page, ticket-style cards for duties, and a bottom tab bar on the driver's phone view.

> **All data is seeded demo data.** There are no real GPS devices. A small "tick" script moves the buses so the live map feels alive. See [What's real and what's simulated](#whats-real-and-whats-simulated).

## Quickstart

```bash
docker compose up --build
```

Then open:

| What | URL |
|---|---|
| App | http://localhost:3000 |
| API docs (Swagger) | http://localhost:3000/docs or http://localhost:8000/docs |

The first start runs the migrations and loads the seed data automatically. Give it about 20 seconds.

### Demo logins (password for all: `password`, demo only)

| Role | Username | Lands on |
|---|---|---|
| Admin | `admin1` | Search / fleet overview, can create routes, notices, vehicles, users |
| Depot manager | `manager_nsd` (also `manager_avd`, `manager_gzb`, `manager_skk`) | Weekly roster, own depot only |
| Control-room operator | `control1` | Live map, all depots |
| Driver | `driver1` (phone view at `/driver`) | Today's duty, panic button, notices |
| Executive (read-only) | `exec1` | Yesterday's report; "Download PDF" opens the browser's print dialog (Save as PDF) |

There are also conductors (`conductor1`...) and about 55 drivers (`driver1`...).

## Demo walkthrough (matches the PRD's demo flow)

1. `docker compose up --build`, wait for the seed.
2. Log in as **admin1** → **Routes** → create a route with 6+ stops.
3. Log in as **manager_nsd** → **Roster** → assign a driver in an empty cell → **Publish**.
4. Log in as **driver1**, resize the window to phone width → **Acknowledge** the duty → open **Notices** → tap **Panic** twice.
5. Log in as **control1** → **Live map**: markers move every 5 s, click one for the side panel. The new P1 shows in **Incidents**, assign it, move it through Acknowledged → In progress → Resolved → Closed (each step needs a note).
6. **Trip history**: pick a vehicle and yesterday's date to see the path and the replay slider. Twelve vehicles have a full trail from yesterday (open any on-duty vehicle from the live map, or use "Show this vehicle's path" on an incident).
7. Open `/docs` for the API.

## What's in each module

| Module | Must-haves | Stretch items included |
|---|---|---|
| **AVLS** | Live map, marker tooltip, 5 s refresh, depot filter, side panel with last 30 min trail, history page | Replay slider, status colours (on-time / slow / idle), geofence breach banner |
| **Scheduling** | Route CRUD, weekly roster grid, assign form, Publish, driver duty + Acknowledge | No double-booking of a driver or a vehicle on the same day, copy last week's roster |
| **IMS** | Raise incident, panic button, filtered list, detail page with timeline and notes, Open → Acknowledged → In progress → Resolved → Closed with a required note, assign | SLA timers (P1 1h, P2 4h, P3 24h) with breaches in red, "show this vehicle's path" from an incident |
| **CMS** | Create notice with audience (all / depot / role), unread notices for drivers, read receipts for admin | "Acknowledgement required" notices |
| **Auth** | bcrypt, JWT, 5 roles checked on every route, depot scoping for managers and drivers | |

Not done: WebSocket live updates (polling every 5 s instead), leave requests, PDF attachments, Hindi notice bodies.

## Stack, and why this much

| Layer | Choice | Why |
|---|---|---|
| Backend | Python, FastAPI | Typed, auto-generated `/docs`, the PRD's recommendation |
| Database | PostgreSQL 16 | One database for everything |
| ORM / migrations | SQLAlchemy 2 + Alembic | No hand-written SQL strings, versioned schema |
| Frontend | React + Vite, React Router, Leaflet | The PRD's recommendation; the driver app is a PWA route in the same app |
| Auth | bcrypt + JWT | Standard, no extra service |
| Containers | Docker Compose | One command to run everything |
| CI | GitHub Actions | Tests, migrations on real Postgres, frontend build, image build |

**Deliberately left out** (from the longer list in the brief): Java Spring Boot, MySQL, Angular and Next.js (one backend and one frontend framework is enough, and a second of either adds work without adding value here), Redis (nothing to cache or queue at 50 vehicles and a 5 s poll), AWS at runtime (see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#deploying-to-aws) for how it would be deployed). PostGIS is also skipped: the geofence check is a point-in-polygon function in Python, which is plenty for 4 depots.

## Running without Docker

You need Python 3.12+, Node 22+ and a PostgreSQL (or leave `DATABASE_URL` unset to use SQLite for local dev).

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg2://bms:bms@localhost:5432/bms   # optional
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload            # http://localhost:8000/docs
python -m app.tick                        # in another terminal: moves the buses

# frontend
cd frontend
npm ci
npm run dev                               # http://localhost:5173 (proxies /api to :8000)
```

Copy `.env.example` to `.env` to change secrets and settings.

## Tests and CI

```bash
cd backend && pytest -q       # 22 tests: auth, scoping, scheduling rules, incident workflow, AVLS, notices
```

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and PR: the backend tests, `alembic upgrade head` plus the seed against a real PostgreSQL service, `alembic check` (fails if the models and migrations drift apart), the frontend build, and the Docker image build.

## What's real and what's simulated

- **Seeded:** 4 depots with polygons (Noida Sec-37, Anand Vihar, Ghaziabad, Sarai Kale Khan), 50 vehicles, 80 users, 12 routes with 6+ stops, a week of duties (yesterday, today, tomorrow published), 12 vehicles with a full GPS trail from yesterday, incidents in every state, 3 notices. Stop coordinates are approximate.
- **Simulated:** live positions. `app/tick.py` writes a new GPS ping per active vehicle every 5 s, moving it along its route (sped up so movement is visible). In production this would be a device ingest service feeding a queue feeding a processor. See the architecture note.
- **Heuristics:** "on time / slow / idle" is derived from speed and duty window, not from a real schedule-adherence calculation.
- **Restarting on a new day** wipes and reseeds the demo data so the roster always spans yesterday to tomorrow. Don't point this at data you care about.

## Project layout

```
backend/app/        models, routers (one per module), seed, tick script, geo helpers
backend/alembic/    migrations
backend/tests/      pytest suite
frontend/src/       pages (one per screen), shared components, API client
docs/               architecture note
```
