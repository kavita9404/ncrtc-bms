"""Dashboard summary and the executive daily report."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..geo import haversine_m
from ..models import Depot, Duty, GpsPing, Incident, User, Vehicle
from ..security import GLOBAL_ROLES, VIEW_ROLES, require_roles
from ..serializers import sla_out
from ..timeutil import ist_day_bounds_utc, iso, today_ist, utcnow

router = APIRouter(prefix="/reports", tags=["reports"])


def _scope(user: User):
    return None if user.role in GLOBAL_ROLES else user.depot_id


@router.get("/summary")
def summary(db: Session = Depends(get_db), user: User = Depends(require_roles(*VIEW_ROLES))):
    depot = _scope(user)
    dq = select(func.count()).select_from(Duty).where(Duty.date == today_ist(), Duty.status != "draft")
    iq = select(Incident).where(Incident.status.in_(("open", "acknowledged", "in_progress")))
    vq = select(func.count()).select_from(Vehicle)
    if depot:
        dq, iq, vq = dq.where(Duty.depot_id == depot), iq.where(Incident.depot_id == depot), vq.where(Vehicle.depot_id == depot)
    open_inc = list(db.scalars(iq))
    return {
        "vehicles_total": db.scalar(vq), "duties_today": db.scalar(dq),
        "open_incidents": len(open_inc),
        "open_p1": sum(1 for i in open_inc if i.severity == "P1"),
        "sla_breached": sum(1 for i in open_inc if sla_out(i)["sla_breached"]),
    }


@router.get("/daily")
def daily(day: date | None = None, db: Session = Depends(get_db),
          user: User = Depends(require_roles("admin", "control_operator", "executive"))):
    """Report for one IST day (default: yesterday)."""
    day = day or today_ist() - timedelta(days=1)
    start, end = ist_day_bounds_utc(day)
    depots = list(db.scalars(select(Depot).order_by(Depot.code)))
    rows = []
    for d in depots:
        duties = list(db.scalars(select(Duty).where(Duty.date == day, Duty.depot_id == d.id, Duty.status != "draft")))
        inc = list(db.scalars(select(Incident).where(Incident.depot_id == d.id, Incident.created_at >= start,
                                                      Incident.created_at < end)))
        vids = [x.vehicle_id for x in duties]
        km = 0.0
        if vids:
            pings = db.scalars(select(GpsPing).where(GpsPing.vehicle_id.in_(vids), GpsPing.ts >= start, GpsPing.ts < end)
                               .order_by(GpsPing.vehicle_id, GpsPing.ts))
            prev = None
            for p in pings:
                if prev and prev.vehicle_id == p.vehicle_id:
                    km += haversine_m(prev.lat, prev.lng, p.lat, p.lng) / 1000
                prev = p
        rows.append({
            "depot_code": d.code, "depot_name": d.name, "duties": len(duties),
            "acknowledged": sum(1 for x in duties if x.ack_at),
            "incidents_raised": len(inc), "p1": sum(1 for i in inc if i.severity == "P1"),
            "incidents_resolved": sum(1 for i in inc if i.status in ("resolved", "closed")),
            "sla_breaches": sum(1 for i in inc if sla_out(i)["sla_breached"]),
            "distance_km": round(km, 1),
        })
    total = {k: sum(r[k] for r in rows) for k in rows[0] if k not in ("depot_code", "depot_name")} if rows else {}
    return {"date": day.isoformat(), "generated_at": iso(utcnow()), "depots": rows, "total": total}
