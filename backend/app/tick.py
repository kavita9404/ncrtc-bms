"""Tick script — animates the live map by inserting one new GPS ping per active bus every few seconds.

    python -m app.tick            # run forever
    python -m app.tick --once     # one round (used by tests)

"Active" = a published duty today. Each bus drives its route out and back. Reported speeds stay realistic;
positions advance TICK_SPEED_MULTIPLIER x faster so movement is visible on the demo map.
In production this role is played by a TCP ingest service -> queue -> processor (see docs/ARCHITECTURE.md).
"""
import random
import sys
import time
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from .config import TICK_SECONDS, TICK_SPEED_MULTIPLIER
from .database import SessionLocal
from .models import Duty, GpsPing, Route, RouteStop
from .simulation import SPACING_M, nearest_index, route_loop, vehicle_speed_kmh
from .timeutil import today_ist, utcnow

RETENTION_HOURS = 72


class Bus:
    def __init__(self, vehicle_id: int, loop: list[tuple[float, float]], idx: float, rng: random.Random):
        self.vehicle_id, self.loop, self.idx = vehicle_id, loop, idx
        self.base_speed = vehicle_speed_kmh(vehicle_id, rng)


def load_buses(db: Session, rng: random.Random, previous: dict[int, Bus]) -> dict[int, Bus]:
    duties = db.scalars(select(Duty).where(Duty.date == today_ist(), Duty.status != "draft")
                        .options(joinedload(Duty.route).joinedload(Route.stops).joinedload(RouteStop.stop)))
    buses: dict[int, Bus] = {}
    for d in duties.unique():
        if d.vehicle_id in previous:
            buses[d.vehicle_id] = previous[d.vehicle_id]
            continue
        loop = route_loop([(rs.stop.lat, rs.stop.lng) for rs in d.route.stops])
        last = db.scalar(select(GpsPing).where(GpsPing.vehicle_id == d.vehicle_id).order_by(GpsPing.ts.desc()).limit(1))
        start = nearest_index(loop, last.lat, last.lng) if last else rng.randrange(len(loop))
        buses[d.vehicle_id] = Bus(d.vehicle_id, loop, float(start), rng)
    return buses


def tick_once(db: Session, buses: dict[int, Bus], rng: random.Random) -> int:
    now = utcnow()
    for b in buses.values():
        speed = max(3.0, b.base_speed * rng.uniform(0.85, 1.15))
        b.idx = (b.idx + speed / 3.6 * TICK_SECONDS * TICK_SPEED_MULTIPLIER / SPACING_M) % len(b.loop)
        lat, lng = b.loop[int(b.idx)]
        db.add(GpsPing(vehicle_id=b.vehicle_id, ts=now, lat=lat, lng=lng, speed_kmh=speed, ignition_on=True))
    db.commit()
    return len(buses)


def main(argv: list[str]):
    rng = random.Random()
    buses: dict[int, Bus] = {}
    rounds = 0
    while True:
        with SessionLocal() as db:
            if rounds % 12 == 0:  # re-read duties every ~minute (publishing changes who is active)
                buses = load_buses(db, rng, buses)
            n = tick_once(db, buses, rng)
            if rounds % 600 == 0:
                db.execute(delete(GpsPing).where(GpsPing.ts < utcnow() - timedelta(hours=RETENTION_HOURS)))
                db.commit()
        rounds += 1
        if "--once" in argv:
            print(f"[tick] inserted {n} pings")
            return
        time.sleep(TICK_SECONDS)


if __name__ == "__main__":
    main(sys.argv[1:])
