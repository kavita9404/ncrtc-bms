#!/bin/sh
set -e
# wait for the database, run migrations, seed demo data, start the API
python - <<'PY'
import os, time
from sqlalchemy import create_engine, text
engine = create_engine(os.environ["DATABASE_URL"])
for i in range(30):
    try:
        engine.connect().execute(text("select 1")); break
    except Exception:
        print("waiting for database..."); time.sleep(2)
else:
    raise SystemExit("database not reachable")
PY
alembic upgrade head
python -m app.seed
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
