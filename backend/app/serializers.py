"""Plain-dict serializers shared by routers."""
from datetime import timedelta

from .models import Duty, Incident, Route, User
from .timeutil import hhmm, iso, utcnow

SLA_HOURS = {"P1": 1, "P2": 4, "P3": 24}


def user_out(u: User | None) -> dict | None:
    if not u:
        return None
    return {"id": u.id, "username": u.username, "full_name": u.full_name, "role": u.role,
            "depot_id": u.depot_id, "phone": u.phone}


def route_out(r: Route, with_stops: bool = True) -> dict:
    d = {"id": r.id, "code": r.code, "name": r.name, "depot_id": r.depot_id}
    if with_stops:
        d["stops"] = [{"stop_id": rs.stop_id, "name": rs.stop.name, "lat": rs.stop.lat, "lng": rs.stop.lng,
                       "sequence": rs.sequence, "planned_offset_min": rs.planned_offset_min} for rs in r.stops]
        d["duration_min"] = r.stops[-1].planned_offset_min if r.stops else 0
    return d


def duty_out(d: Duty, with_stops: bool = False) -> dict:
    out = {
        "id": d.id, "date": d.date.isoformat(), "depot_id": d.depot_id,
        "vehicle_id": d.vehicle_id, "vehicle_reg": d.vehicle.reg_no,
        "driver_id": d.driver_id, "driver_name": d.driver.full_name,
        "conductor_id": d.conductor_id, "conductor_name": d.conductor.full_name if d.conductor else None,
        "route_id": d.route_id, "route_code": d.route.code, "route_name": d.route.name,
        "start_time": hhmm(d.start_time), "end_time": hhmm(d.end_time),
        "status": d.status, "ack_at": iso(d.ack_at),
    }
    if with_stops:
        start_min = d.start_time.hour * 60 + d.start_time.minute
        out["stops"] = [
            {"name": rs.stop.name, "lat": rs.stop.lat, "lng": rs.stop.lng,
             "time": f"{((start_min + rs.planned_offset_min) // 60) % 24:02d}:{(start_min + rs.planned_offset_min) % 60:02d}"}
            for rs in d.route.stops
        ]
    return out


def sla_out(i: Incident) -> dict:
    due = i.created_at + timedelta(hours=SLA_HOURS[i.severity])
    end = i.resolved_at or utcnow()
    done = i.status in ("resolved", "closed")
    return {
        "sla_due_at": iso(due),
        "sla_remaining_min": None if done else int((due - utcnow()).total_seconds() // 60),
        "sla_breached": end > due,
    }


def incident_out(i: Incident, with_events: bool = False) -> dict:
    out = {
        "id": i.id, "type": i.type, "severity": i.severity, "status": i.status,
        "description": i.description, "photo_url": f"/uploads/{i.photo_path}" if i.photo_path else None,
        "raised_by": i.raised_by, "raised_by_name": i.raiser.full_name,
        "assigned_to": i.assigned_to, "assigned_to_name": i.assignee.full_name if i.assignee else None,
        "vehicle_id": i.vehicle_id, "vehicle_reg": i.vehicle.reg_no if i.vehicle else None,
        "depot_id": i.depot_id, "depot_code": i.depot.code if i.depot else None,
        "lat": i.lat, "lng": i.lng,
        "created_at": iso(i.created_at), "resolved_at": iso(i.resolved_at),
        **sla_out(i),
    }
    if with_events:
        out["events"] = [{"id": e.id, "ts": iso(e.ts), "actor_id": e.actor_id, "actor_name": e.actor.full_name,
                          "from_status": e.from_status, "to_status": e.to_status, "note": e.note}
                         for e in i.events]
    return out
