"""Seed script — fills an empty database with demo NCR data (all fake, all 'demo only').

    python -m app.seed                # SEED_MODE=auto: seed if DB is empty or has no duties for today
    python -m app.seed --reset        # wipe everything and reseed
    python -m app.seed --create-tables  # also create tables (only for SQLite quick-start; Docker uses Alembic)

Coordinates are approximate. Passwords are all `password` — demo only.
"""
import os
import random
import sys
from datetime import datetime, time, timedelta

from faker import Faker
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from . import models as m
from .database import Base, SessionLocal, engine
from .geo import haversine_m, square_polygon
from .security import hash_password
from .simulation import planned_offsets, route_loop, vehicle_speed_kmh
from .timeutil import ist_to_utc_naive, today_ist, utcnow

DEMO_PASSWORD = "password"

DEPOTS = [  # code, name, lat, lng, reg prefix
    ("NSD", "Noida Sec-37", 28.5706, 77.3481, "UP16"),
    ("AVD", "Anand Vihar", 28.6469, 77.3164, "DL01"),
    ("GZB", "Ghaziabad", 28.6692, 77.4538, "UP14"),
    ("SKK", "Sarai Kale Khan", 28.5896, 77.2590, "DL01"),
]
VEHICLES_PER_DEPOT = {"NSD": 13, "AVD": 13, "GZB": 12, "SKK": 12}  # 50 total

STOPS = {  # approximate
    "Noida Sec-37 Depot": (28.5706, 77.3481), "Noida City Centre": (28.5744, 77.3560),
    "Sec-18 Atta Market": (28.5707, 77.3260), "Sec-16 Metro": (28.5788, 77.3171),
    "Sec-15 Metro": (28.5856, 77.3118), "Sec-62 Electronic City": (28.6270, 77.3650),
    "Sec-76": (28.5640, 77.3880), "Sec-137 Metro": (28.5110, 77.4040), "Sec-142": (28.4980, 77.4090),
    "Knowledge Park II": (28.4747, 77.4990), "Pari Chowk": (28.4660, 77.5120),
    "Sec-51 Metro": (28.5846, 77.3578), "Botanical Garden Metro": (28.5640, 77.3340),
    "Anand Vihar ISBT": (28.6469, 77.3164), "Kaushambi": (28.6451, 77.3254),
    "Vaishali Metro": (28.6504, 77.3402), "Vasundhara Sec-1": (28.6590, 77.3550),
    "Indirapuram Shakti Khand": (28.6420, 77.3680), "Sahibabad RRTS": (28.6700, 77.3650),
    "Karkardooma": (28.6513, 77.3055), "Preet Vihar": (28.6416, 77.2950),
    "Mayur Vihar Ext": (28.6063, 77.2937), "Akshardham": (28.6127, 77.2773),
    "Yamuna Bank": (28.6232, 77.2672), "Dilshad Garden": (28.6757, 77.3216),
    "Shahdara": (28.6732, 77.2896), "New Ashok Nagar": (28.5896, 77.3010),
    "Ghaziabad Depot": (28.6692, 77.4538), "Sihani Gate": (28.6770, 77.4590),
    "Ghaziabad Railway Stn": (28.6619, 77.4331), "Raj Nagar Extension": (28.6760, 77.4300),
    "Vijay Nagar": (28.6870, 77.4430), "Guldhar RRTS": (28.6920, 77.4670), "Duhai": (28.7127, 77.4830),
    "Muradnagar": (28.7780, 77.5060), "Modinagar": (28.8340, 77.5720), "Meerut South": (28.9440, 77.7360),
    "Loni": (28.7500, 77.2900),
    "Sarai Kale Khan Depot": (28.5896, 77.2590), "Nizamuddin Stn": (28.5880, 77.2540),
    "Lajpat Nagar": (28.5700, 77.2430), "Nehru Place": (28.5490, 77.2530), "Kalkaji": (28.5430, 77.2580),
    "Okhla": (28.5530, 77.2750), "Lodhi Road": (28.5918, 77.2273), "INA": (28.5750, 77.2100),
    "Jangpura": (28.5830, 77.2420), "Ashram": (28.5710, 77.2589), "Jasola": (28.5390, 77.2840),
    "Sarita Vihar": (28.5280, 77.2900), "Badarpur": (28.4940, 77.3030),
}

ROUTES = [  # code, depot, name, stops
    ("NSD-101", "NSD", "Sec-37 Depot to Sec-62 via Metro belt",
     ["Noida Sec-37 Depot", "Noida City Centre", "Sec-18 Atta Market", "Sec-16 Metro", "Sec-15 Metro", "Sec-62 Electronic City"]),
    ("NSD-102", "NSD", "Sec-37 Depot to Pari Chowk",
     ["Noida Sec-37 Depot", "Sec-76", "Sec-137 Metro", "Sec-142", "Knowledge Park II", "Pari Chowk"]),
    ("NSD-103", "NSD", "Sec-37 Depot to Sec-62 via Botanical Garden",
     ["Noida Sec-37 Depot", "Sec-51 Metro", "Noida City Centre", "Botanical Garden Metro", "Sec-16 Metro", "Sec-15 Metro", "Sec-62 Electronic City"]),
    ("AVD-201", "AVD", "Anand Vihar to Sahibabad RRTS",
     ["Anand Vihar ISBT", "Kaushambi", "Vaishali Metro", "Vasundhara Sec-1", "Indirapuram Shakti Khand", "Sahibabad RRTS"]),
    ("AVD-202", "AVD", "Anand Vihar to Yamuna Bank",
     ["Anand Vihar ISBT", "Karkardooma", "Preet Vihar", "Mayur Vihar Ext", "Akshardham", "Yamuna Bank"]),
    ("AVD-203", "AVD", "Anand Vihar to Mayur Vihar via Shahdara",
     ["Anand Vihar ISBT", "Dilshad Garden", "Shahdara", "Karkardooma", "New Ashok Nagar", "Mayur Vihar Ext"]),
    ("GZB-301", "GZB", "Ghaziabad Depot to Sahibabad RRTS",
     ["Ghaziabad Depot", "Sihani Gate", "Ghaziabad Railway Stn", "Raj Nagar Extension", "Vijay Nagar", "Sahibabad RRTS"]),
    ("GZB-302", "GZB", "Ghaziabad Depot to Meerut South",
     ["Ghaziabad Depot", "Guldhar RRTS", "Duhai", "Muradnagar", "Modinagar", "Meerut South"]),
    ("GZB-303", "GZB", "Ghaziabad Depot to Loni via Duhai",
     ["Ghaziabad Depot", "Ghaziabad Railway Stn", "Raj Nagar Extension", "Duhai", "Guldhar RRTS", "Loni"]),
    ("SKK-401", "SKK", "Sarai Kale Khan to Okhla via Nehru Place",
     ["Sarai Kale Khan Depot", "Nizamuddin Stn", "Lajpat Nagar", "Nehru Place", "Kalkaji", "Okhla"]),
    ("SKK-402", "SKK", "Sarai Kale Khan to Lajpat Nagar via INA",
     ["Sarai Kale Khan Depot", "Lodhi Road", "INA", "Jangpura", "Ashram", "Lajpat Nagar"]),
    ("SKK-403", "SKK", "Sarai Kale Khan to Badarpur",
     ["Sarai Kale Khan Depot", "Ashram", "Okhla", "Jasola", "Sarita Vihar", "Badarpur"]),
]

SHIFTS = [(time(5, 30), time(13, 30)), (time(10, 0), time(18, 0)), (time(14, 0), time(22, 0))]
DRIVERS_PER_DEPOT = 14
CONDUCTORS = {"NSD": 4, "AVD": 3, "GZB": 3, "SKK": 3}
ON_DUTY_PER_DEPOT = 10


def _wipe(db: Session):
    for model in (m.NoticeRead, m.Notice, m.IncidentEvent, m.Incident, m.GpsPing, m.Duty, m.RouteStop,
                  m.Route, m.Stop, m.User, m.Vehicle, m.Depot):
        db.execute(delete(model))
    db.commit()


def needs_seed(db: Session) -> bool:
    if not db.scalar(select(func.count()).select_from(m.User)):
        return True
    return not db.scalar(select(func.count()).select_from(m.Duty).where(m.Duty.date == today_ist()))


def run(db: Session, seed: int = 7) -> dict:
    rng = random.Random(seed)
    fake = Faker("en_IN")
    Faker.seed(seed)
    now = utcnow()
    today = today_ist()
    pw = hash_password(DEMO_PASSWORD)  # one hash reused: every demo account shares the password

    # ---- depots
    depots = {}
    for code, name, lat, lng, _ in DEPOTS:
        depots[code] = m.Depot(code=code, name=name, location_lat=lat, location_lng=lng,
                               polygon_geojson=square_polygon(lat, lng, 250))
        db.add(depots[code])
    db.flush()

    # ---- vehicles
    vehicles: dict[str, list[m.Vehicle]] = {c: [] for c in depots}
    used = set()
    for code, _, _, _, prefix in DEPOTS:
        for _ in range(VEHICLES_PER_DEPOT[code]):
            while True:
                reg = f"{prefix} {rng.choice('ABCDEFGHJKLMNPRSTUVWXYZ')}{rng.choice('ABCDEFGHJKLMNPRSTUVWXYZ')} {rng.randint(1000, 9999)}"
                if reg not in used:
                    used.add(reg)
                    break
            v = m.Vehicle(reg_no=reg, depot_id=depots[code].id, status="active")
            vehicles[code].append(v)
            db.add(v)
    vehicles["SKK"][-1].status = "maintenance"  # one bus in the workshop
    db.flush()

    # ---- users (80)
    def mk(username, role, depot=None, name=None):
        u = m.User(username=username, password_hash=pw, full_name=name or fake.name(), role=role,
                   depot_id=depots[depot].id if depot else None, phone=f"+91 {rng.randint(70000, 99999)}{rng.randint(10000, 99999)}")
        db.add(u)
        return u

    admins = [mk(f"admin{i}", "admin") for i in (1, 2, 3)]
    controls = [mk(f"control{i}", "control_operator") for i in (1, 2, 3)]
    mk("exec1", "executive")
    managers = {c: mk(f"manager_{c.lower()}", "depot_manager", c) for c in depots}
    drivers: dict[str, list[m.User]] = {c: [] for c in depots}
    conductors: dict[str, list[m.User]] = {c: [] for c in depots}
    n = 0
    for c in depots:
        for _ in range(DRIVERS_PER_DEPOT):
            n += 1
            drivers[c].append(mk(f"driver{n}", "driver", c))
    n = 0
    for c, k in CONDUCTORS.items():
        for _ in range(k):
            n += 1
            conductors[c].append(mk(f"conductor{n}", "conductor", c))
    db.flush()

    # ---- stops and routes
    stop_rows = {}
    for name, (lat, lng) in STOPS.items():
        stop_rows[name] = m.Stop(name=name, lat=lat, lng=lng)
        db.add(stop_rows[name])
    db.flush()
    routes: dict[str, list[m.Route]] = {c: [] for c in depots}
    route_coords: dict[int, list[tuple[float, float]]] = {}
    for code, depot, name, stop_names in ROUTES:
        coords = [STOPS[s] for s in stop_names]
        r = m.Route(code=code, name=name, depot_id=depots[depot].id)
        db.add(r)
        db.flush()
        for seq, (sn, off) in enumerate(zip(stop_names, planned_offsets(coords)), start=1):
            r.stops.append(m.RouteStop(stop_id=stop_rows[sn].id, sequence=seq, planned_offset_min=off))
        routes[depot].append(r)
        route_coords[r.id] = coords
    db.flush()

    # ---- duties: a 7-day window (today-3 .. today+3)
    duties_by_day: dict[int, list[m.Duty]] = {}
    for offset in range(-3, 4):
        day = today + timedelta(days=offset)
        duties_by_day[offset] = []
        for ci, c in enumerate(depots):
            active = [v for v in vehicles[c] if v.status == "active"]
            for k in range(ON_DUTY_PER_DEPOT):
                v = active[(k + offset) % len(active)]
                drv = drivers[c][(k + offset) % DRIVERS_PER_DEPOT]
                con = conductors[c][k % len(conductors[c])] if k < len(conductors[c]) * 2 and k % 2 == 0 else None
                # unique conductor per day
                if con and any(d.conductor_id == con.id for d in duties_by_day[offset]):
                    con = None
                start, end = SHIFTS[k % 3]
                if offset < 0:
                    status = "acknowledged"
                elif offset == 0:
                    status = "published"
                elif offset == 1 and c == "SKK":
                    status = "published"
                else:
                    status = "draft"
                duty = m.Duty(date=day, depot_id=depots[c].id, vehicle_id=v.id, driver_id=drv.id,
                              conductor_id=con.id if con else None, route_id=routes[c][k % 3].id,
                              start_time=start, end_time=end, status=status)
                if status == "acknowledged":
                    duty.ack_at = ist_to_utc_naive(day, time(5, 0)) + timedelta(minutes=rng.randint(0, 40))
                duties_by_day[offset].append(duty)
                db.add(duty)
    db.flush()
    # today: ~60% acknowledged, but keep driver1 unacknowledged so the demo can show Acknowledge
    for d in duties_by_day[0]:
        if d.driver_id != drivers["NSD"][0].id and rng.random() < 0.6:
            d.status, d.ack_at = "acknowledged", now - timedelta(minutes=rng.randint(30, 300))
    # yesterday: a couple of duties never acknowledged
    for d in rng.sample(duties_by_day[-1], 3):
        d.status, d.ack_at = "published", None

    # ---- GPS history: yesterday, one full trip for 3 buses per depot (12 total)
    route_by_id = {r.id: r for rs in routes.values() for r in rs}
    history_vehicles = []
    for c in depots:
        for d in [x for x in duties_by_day[-1] if x.depot_id == depots[c].id][:3]:
            history_vehicles.append(d.vehicle_id)
            r = route_by_id[d.route_id]
            coords = route_coords[r.id]
            offs = [rs.planned_offset_min * 60 for rs in r.stops]
            t0 = ist_to_utc_naive(d.date, d.start_time)
            for t in range(0, offs[-1] + 1, 30):
                i = max(j for j in range(len(offs)) if offs[j] <= t)
                if i == len(offs) - 1:
                    lat, lng, seg_t, seg_d = coords[-1][0], coords[-1][1], 1, 0
                else:
                    f = (t - offs[i]) / (offs[i + 1] - offs[i])
                    (a1, b1), (a2, b2) = coords[i], coords[i + 1]
                    lat, lng = a1 + (a2 - a1) * f, b1 + (b2 - b1) * f
                    seg_t, seg_d = offs[i + 1] - offs[i], haversine_m(a1, b1, a2, b2)
                speed = min(48, max(6, seg_d / seg_t * 3.6 * rng.uniform(0.8, 1.25)))
                db.add(m.GpsPing(vehicle_id=d.vehicle_id, ts=t0 + timedelta(seconds=t), lat=lat, lng=lng,
                                 speed_kmh=speed, ignition_on=True))

    # ---- GPS now: 30 minutes of trail for buses on duty today, parked pings for the rest
    on_duty_today = {d.vehicle_id: d for d in duties_by_day[0]}
    for v_id, d in on_duty_today.items():
        loop = route_loop(route_coords[d.route_id])
        idx = rng.randint(0, len(loop) - 1)
        base = vehicle_speed_kmh(v_id, rng)
        step = max(1, round(base / 3.6 * 30 * 8 / 50))  # same compression the tick script uses
        for k in range(60, -1, -1):
            lat, lng = loop[(idx - k * step) % len(loop)]
            speed = max(3.0, base * rng.uniform(0.9, 1.1)) if k else base
            db.add(m.GpsPing(vehicle_id=v_id, ts=now - timedelta(seconds=30 * k), lat=lat, lng=lng,
                             speed_kmh=speed, ignition_on=True))
    breach_done = False
    for c, dp in depots.items():
        for v in vehicles[c]:
            if v.id in on_duty_today:
                continue
            lat, lng = dp.location_lat, dp.location_lng
            if c == "AVD" and not breach_done and v.status == "active":
                lat += 0.009  # ~1 km north of the depot: geofence-breach demo
                breach_done = True
            else:
                lat += rng.uniform(-0.0012, 0.0012)
                lng += rng.uniform(-0.0012, 0.0012)
            db.add(m.GpsPing(vehicle_id=v.id, ts=now - timedelta(seconds=rng.randint(5, 60)), lat=lat, lng=lng,
                             speed_kmh=0, ignition_on=False))

    # ---- incidents
    def incident(depot, typ, sev, desc, raiser, vehicle, ago_min, path):
        """path = list of (to_status, note, actor) applied in order."""
        created = now - timedelta(minutes=ago_min)
        i = m.Incident(type=typ, severity=sev, description=desc, raised_by=raiser.id, depot_id=depots[depot].id,
                       vehicle_id=vehicle.id if vehicle else None, status="open", created_at=created)
        db.add(i)
        db.flush()
        db.add(m.IncidentEvent(incident_id=i.id, ts=created, actor_id=raiser.id, to_status="open", note="Incident raised"))
        prev, ts = "open", created
        for to, note, actor in path:
            ts += timedelta(minutes=max(5, ago_min // (len(path) + 2)))
            db.add(m.IncidentEvent(incident_id=i.id, ts=ts, actor_id=actor.id, from_status=prev, to_status=to, note=note))
            i.status = prev = to
            if to == "resolved":
                i.resolved_at = ts
            if actor.role in ("depot_manager", "control_operator", "admin") and not i.assigned_to:
                i.assigned_to = actor.id
        return i

    nsd, avd, gzb, skk = (drivers[c][0] for c in ("NSD", "AVD", "GZB", "SKK"))
    mg = managers
    incident("NSD", "breakdown", "P2", "AC not working and engine overheating near Sec-18.", nsd, vehicles["NSD"][1], 35, [])
    incident("NSD", "breakdown", "P1", "Bus stopped on the road, brake warning light on. Passengers waiting.", drivers["NSD"][3],
             vehicles["NSD"][2], 95, [("acknowledged", "Seen. Sending the mobile workshop team.", mg["NSD"])])
    incident("AVD", "accident", "P1", "Minor collision with an auto at Kaushambi. No injuries reported.", avd, vehicles["AVD"][0], 150,
             [("acknowledged", "Control room informed.", controls[0]), ("in_progress", "Replacement bus dispatched.", mg["AVD"])])
    incident("GZB", "complaint", "P3", "Passenger complaint: bus skipped the Raj Nagar Extension stop.", gzb, vehicles["GZB"][1], 600,
             [("acknowledged", "Checking duty log.", mg["GZB"]), ("in_progress", "Driver contacted.", mg["GZB"]),
              ("resolved", "Driver warned and counselled.", mg["GZB"])])
    incident("SKK", "other", "P3", "Seat cushion torn in the rear row.", skk, vehicles["SKK"][2], 300,
             [("acknowledged", "Added to workshop list.", mg["SKK"])])
    incident("AVD", "complaint", "P2", "Rude behaviour reported against conductor on AVD-202.", drivers["AVD"][2], vehicles["AVD"][3], 1500,
             [("acknowledged", "Noted.", mg["AVD"]), ("in_progress", "Statement taken.", mg["AVD"]),
              ("resolved", "Conductor briefed.", mg["AVD"]), ("closed", "Closed after follow-up.", admins[0])])

    # ---- notices
    all_drivers = [u for c in depots for u in drivers[c]]
    n1 = m.Notice(title="Monsoon safety: slow down on waterlogged stretches",
                  body="Reduce speed near waterlogged roads, keep headlights on, and report blocked routes through the app.\n\n"
                       "मानसून सुरक्षा: जलभराव वाली सड़कों पर गति कम रखें और बाधित मार्गों की सूचना ऐप से दें।",
                  audience_json={"type": "role", "role": "driver"}, publish_at=now - timedelta(days=2),
                  created_by=admins[0].id, requires_ack=True)
    n2 = m.Notice(title="Noida Sec-37 depot: parking bay change",
                  body="Buses on routes NSD-101 and NSD-103 now park in bays C and D. Bay A is closed for resurfacing this week.",
                  audience_json={"type": "depot", "depot_id": depots["NSD"].id}, publish_at=now - timedelta(days=1),
                  created_by=admins[0].id)
    n3 = m.Notice(title="New RRTS feeder timings from Monday",
                  body="Morning shift now starts at 05:30 on all routes. Check your roster for the updated timings.",
                  audience_json={"type": "all"}, publish_at=now - timedelta(hours=2), created_by=admins[1].id)
    db.add_all([n1, n2, n3])
    db.flush()
    for u in rng.sample(all_drivers, 30):
        r = m.NoticeRead(notice_id=n1.id, user_id=u.id, read_at=now - timedelta(hours=rng.randint(3, 40)))
        if rng.random() < 0.7:
            r.ack_at = r.read_at + timedelta(minutes=2)
        db.add(r)
    for u in drivers["NSD"][1:8]:
        db.add(m.NoticeRead(notice_id=n2.id, user_id=u.id, read_at=now - timedelta(hours=rng.randint(1, 20))))

    db.commit()
    return {
        "depots": len(depots), "vehicles": sum(len(v) for v in vehicles.values()),
        "users": db.scalar(select(func.count()).select_from(m.User)),
        "routes": len(ROUTES), "history_vehicles": len(history_vehicles),
    }


def main(argv: list[str]):
    mode = os.getenv("SEED_MODE", "auto")  # auto | reset | never
    if "--reset" in argv:
        mode = "reset"
    if "--create-tables" in argv:
        Base.metadata.create_all(engine)
    if mode == "never":
        print("[seed] SEED_MODE=never, skipping")
        return
    with SessionLocal() as db:
        if mode == "reset":
            _wipe(db)
        elif not needs_seed(db):
            print("[seed] database already has data for today, skipping")
            return
        else:
            _wipe(db)  # stale or empty demo data: start clean
        stats = run(db)
        print(f"[seed] done: {stats}. Demo logins use password '{DEMO_PASSWORD}' (admin1, manager_nsd, control1, driver1, exec1).")


if __name__ == "__main__":
    main(sys.argv[1:])
