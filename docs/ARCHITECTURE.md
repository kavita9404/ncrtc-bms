# Architecture note

## The system in one picture

```
 Browser (React)                    Driver phone (same React app, /driver, PWA)
      │                                        │
      └──────────── HTTPS / JSON ──────────────┘
                          │
                  nginx (serves the built React app, proxies /api and /docs)
                          │
                ┌─────────▼──────────┐
                │ FastAPI (one app)  │   auth · AVLS · Scheduling · IMS · CMS · reports
                │ SQLAlchemy 2       │
                └─────────┬──────────┘
                          │
                ┌─────────▼──────────┐          ┌────────────────────────┐
                │ PostgreSQL 16      │◄─────────│ tick.py (GPS simulator) │
                │ 11 tables, Alembic │  1 ping  │ every 5 s per vehicle   │
                └────────────────────┘          └────────────────────────┘
```

One backend, one database, one frontend. The only extra process is the simulator.

## Data model

Eleven tables, as in the PRD: `depot`, `vehicle`, `users`, `stop`, `route`, `route_stop`, `duty`, `gps_ping`, `incident`, `incident_event`, `notice`, `notice_read`. (`user` is a reserved word in PostgreSQL, so the table is `users`.)

Small additions the features needed:
- `duty.depot_id` so the roster query can use the `(date, depot_id)` index; `duty.conductor_id`; unique constraints on `(date, driver_id)` and `(date, vehicle_id)` so double-booking is impossible even if two managers click at once.
- `notice.requires_ack` and `notice_read.ack_at` for acknowledgement-required notices.
- `incident.photo_path` for the optional photo upload.

Indexes: `gps_ping (vehicle_id, ts DESC)` for "last N pings", `duty (date, depot_id)`, `incident (status, depot_id)`.

## How each module is built

**Auth.** `POST /api/auth/login` checks a bcrypt hash and returns a JWT carrying the user id and role. Every route depends on `require_roles(...)`. Depot scoping lives in one place (`security.resolve_depot` and `can_access_depot`): managers and drivers are forced to their own depot, control operators, admins and the executive see everything.

**AVLS.** `GET /api/avls/live` returns the latest ping per vehicle, joined with today's duty (driver, route) and a computed status. The frontend polls it every 5 s and updates Leaflet markers in place rather than rebuilding them, which is what keeps 50+ markers smooth. `/trail?minutes=30` feeds the side panel; `/history?day=` returns a whole day for the history page and replay slider. The geofence check is a point-in-polygon function over the depot polygon: a vehicle with no duty today that is outside its depot raises a banner.

**Scheduling.** Routes are CRUD with ordered stops and planned offsets. The roster endpoint returns one week as a grid (drivers × days). Assigning checks the driver and vehicle aren't already used that day and returns 409 if so. Duties start as `draft`, **Publish** flips them to `published` in one transaction, drivers only ever see published duties, and **Acknowledge** stamps `ack_at`.

**IMS.** An incident moves through `open → acknowledged → in_progress → resolved → closed`. The transition endpoint rejects skips (409) and requires a note (422); every change writes an `incident_event`, which is the timeline on the detail page. The SLA due time is computed from severity (P1 1 h, P2 4 h, P3 24 h) rather than stored, so changing the SLA table changes every incident. The panic endpoint creates a P1 from the driver's current duty vehicle and optional coordinates.

**CMS.** `notice.audience_json` is `{"type":"all"}`, `{"type":"depot","depot_id":1}` or `{"type":"role","role":"driver"}`. A user's notice list is the notices whose audience matches them. Opening one writes a `notice_read` row, and the admin receipts view is a left join of audience members against those rows.

## The simulator, and what production would look like

`app/tick.py` is the only fake part. Each tick it takes every vehicle with a duty today, finds where the bus last was on its route (an out-and-back loop built from the stop coordinates), moves it forward by its speed (every 4th bus is deliberately slow, which is what shows amber on the map; time is compressed by `TICK_SPEED_MULTIPLIER`), and inserts one `gps_ping`. The seed script uses the same route-loop helper to generate yesterday's history.

In production this would be:

```
GPS devices ──TCP/MQTT──► ingest service ──► queue (SQS/Kafka) ──► processor ──► PostgreSQL (+PostGIS / time-series)
                              │                                        │
                       device protocol,                         dedup, idempotency,
                       auth, rate limits                        geofence + alert rules ──► WebSocket push to the map
```

The API and the frontend would not change much. The ingest service, queue and processor are what this project deliberately doesn't build.

## What I'd improve next

- WebSocket push instead of polling, once there are hundreds of vehicles on screen.
- Real schedule adherence (planned stop times vs actual passing times) instead of the speed-based status heuristic.
- PostGIS for geofencing and "nearest depot" queries; partition `gps_ping` by day.
- Refresh tokens and per-user rate limiting on login.
- Leave requests, PDF/Hindi notices, and a real push channel for the driver PWA.
- Store uploads in S3 rather than a Docker volume.

## Deploying to AWS

Not part of the demo and **not tested here**; this is the shape I'd use.

1. **Images.** The CI already builds both images. Add a job that logs in to ECR and pushes `backend` and `frontend` on merges to `main`, using GitHub's OIDC role (no long-lived AWS keys in secrets).
2. **Database.** RDS PostgreSQL 16, private subnets, security group open only to the API.
3. **Compute.** ECS Fargate: one service for `api`, one for `tick` only in demo environments (it should never run beside real devices), and the frontend either as a third service behind the same ALB or as static files on S3 + CloudFront with `/api` routed to the ALB.
4. **Config.** `SECRET_KEY` and `DATABASE_URL` from Secrets Manager. Run `alembic upgrade head` as a one-off task before each deploy, and drop the seed from the entrypoint outside the demo.
5. **HTTPS.** ACM certificate on the ALB; set `CORS_ORIGINS` to the real origin.
