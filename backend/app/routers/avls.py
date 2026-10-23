"""Module 1 — AVLS: live map + trip history."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..geo import haversine_m, point_in_polygon
from ..models import Depot, Duty, GpsPing, User, Vehicle
from ..security import VIEW_ROLES, can_access_depot, require_roles, resolve_depot
from ..timeutil import ist_day_bounds_utc, iso, today_ist, utcnow

router = APIRouter(prefix="/avls", tags=["AVLS"])

SLOW_KMH = 15  # below this while moving we call the bus "late" (demo heuristic, see README)


def _status(has_duty: bool, ping: GpsPing) -> str:
    if not has_duty or not ping.ignition_on or ping.speed_kmh < 2:
        return "idle"
    return "late" if ping.speed_kmh < SLOW_KMH else "on_time"


@router.get("/live")
def live(depot_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(require_roles(*VIEW_ROLES))):
    depot_id = resolve_depot(user, depot_id)
    latest = (select(GpsPing.vehicle_id, func.max(GpsPing.ts).label("mts")).group_by(GpsPing.vehicle_id).subquery())
    q = (select(GpsPing, Vehicle)
         .join(latest, and_(GpsPing.vehicle_id == latest.c.vehicle_id, GpsPing.ts == latest.c.mts))
         .join(Vehicle, Vehicle.id == GpsPing.vehicle_id))
    if depot_id:
        q = q.where(Vehicle.depot_id == depot_id)

    duties = {
        d.vehicle_id: d for d in db.scalars(
            select(Duty).where(Duty.date == today_ist(), Duty.status != "draft")
            .options(joinedload(Duty.driver), joinedload(Duty.route)))
    }
    depots = {d.id: d for d in db.scalars(select(Depot))}

    vehicles, alerts, seen = [], [], set()
    for ping, v in db.execute(q):
        if v.id in seen:
            continue
        seen.add(v.id)
        duty = duties.get(v.id)
        depot = depots[v.depot_id]
        breach = duty is None and not point_in_polygon(ping.lat, ping.lng, depot.polygon_geojson)
        item = {
            "vehicle_id": v.id, "reg_no": v.reg_no, "depot_id": v.depot_id, "depot_code": depot.code,
            "lat": ping.lat, "lng": ping.lng, "speed_kmh": round(ping.speed_kmh, 1),
            "ignition_on": ping.ignition_on, "ts": iso(ping.ts),
            "status": _status(duty is not None, ping), "geofence_breach": breach,
            "driver": {"id": duty.driver.id, "name": duty.driver.full_name, "phone": duty.driver.phone} if duty else None,
            "route": {"id": duty.route.id, "code": duty.route.code, "name": duty.route.name} if duty else None,
        }
        vehicles.append(item)
        if breach:
            alerts.append({"type": "geofence_breach", "vehicle_id": v.id, "reg_no": v.reg_no,
                           "message": f"{v.reg_no} is outside the {depot.code} depot with no duty assigned today"})
    vehicles.sort(key=lambda x: x["reg_no"])
    return {"as_of": iso(utcnow()), "vehicles": vehicles, "alerts": alerts}


def _vehicle_or_403(db: Session, vehicle_id: int, user: User) -> Vehicle:
    v = db.get(Vehicle, vehicle_id)
    if not v:
        raise HTTPException(404, "Vehicle not found")
    if not can_access_depot(user, v.depot_id):
        raise HTTPException(403, "That vehicle belongs to another depot")
    return v


def _ping_out(p: GpsPing) -> dict:
    return {"ts": iso(p.ts), "lat": p.lat, "lng": p.lng, "speed_kmh": round(p.speed_kmh, 1), "ignition_on": p.ignition_on}


@router.get("/vehicles/{vehicle_id}/trail")
def trail(vehicle_id: int, minutes: int = 30, db: Session = Depends(get_db),
          user: User = Depends(require_roles(*VIEW_ROLES))):
    v = _vehicle_or_403(db, vehicle_id, user)
    since = utcnow() - timedelta(minutes=min(max(minutes, 1), 240))
    pings = db.scalars(select(GpsPing).where(GpsPing.vehicle_id == v.id, GpsPing.ts >= since).order_by(GpsPing.ts))
    return {"vehicle_id": v.id, "reg_no": v.reg_no, "pings": [_ping_out(p) for p in pings]}


@router.get("/vehicles/{vehicle_id}/history")
def history(vehicle_id: int, day: date, db: Session = Depends(get_db),
            user: User = Depends(require_roles(*VIEW_ROLES))):
    v = _vehicle_or_403(db, vehicle_id, user)
    start, end = ist_day_bounds_utc(day)
    pings = list(db.scalars(select(GpsPing).where(GpsPing.vehicle_id == v.id, GpsPing.ts >= start, GpsPing.ts < end)
                            .order_by(GpsPing.ts)))
    dist = sum(haversine_m(a.lat, a.lng, b.lat, b.lng) for a, b in zip(pings, pings[1:]))
    return {
        "vehicle_id": v.id, "reg_no": v.reg_no, "date": day.isoformat(),
        "summary": {
            "pings": len(pings), "distance_km": round(dist / 1000, 2),
            "max_speed_kmh": round(max((p.speed_kmh for p in pings), default=0), 1),
            "first_ts": iso(pings[0].ts) if pings else None, "last_ts": iso(pings[-1].ts) if pings else None,
        },
        "pings": [_ping_out(p) for p in pings],
    }
