"""Module 2 — Scheduling: routes, roster, duties, publish, acknowledge."""
from datetime import date, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Depot, Duty, Route, RouteStop, Stop, User, Vehicle
from ..security import (
    CREW_ROLES, OPS_ROLES, VIEW_ROLES, can_access_depot, get_current_user, require_roles, resolve_depot,
)
from ..serializers import duty_out, route_out
from ..timeutil import today_ist, utcnow

router = APIRouter(tags=["Scheduling"])


# ------------------------------------------------------------------ routes
class RouteStopIn(BaseModel):
    stop_id: int
    planned_offset_min: int = Field(ge=0, le=600)


class RouteIn(BaseModel):
    code: str = Field(min_length=2, max_length=16)
    name: str = Field(min_length=3, max_length=120)
    depot_id: int
    stops: list[RouteStopIn] = Field(min_length=2)


def _apply_stops(db: Session, route: Route, stops: list[RouteStopIn]):
    ids = [s.stop_id for s in stops]
    known = set(db.scalars(select(Stop.id).where(Stop.id.in_(ids))))
    if known != set(ids):
        raise HTTPException(422, "One or more stops do not exist")
    offsets = [s.planned_offset_min for s in stops]
    if offsets != sorted(offsets):
        raise HTTPException(422, "Planned times must not go backwards along the route")
    route.stops.clear()
    db.flush()
    for i, s in enumerate(stops, start=1):
        route.stops.append(RouteStop(stop_id=s.stop_id, sequence=i, planned_offset_min=s.planned_offset_min))


@router.get("/routes")
def list_routes(depot_id: int | None = None, db: Session = Depends(get_db),
                user: User = Depends(require_roles(*VIEW_ROLES))):
    depot_id = resolve_depot(user, depot_id)
    q = select(Route).options(joinedload(Route.stops).joinedload(RouteStop.stop)).order_by(Route.code)
    if depot_id:
        q = q.where(Route.depot_id == depot_id)
    return [route_out(r) for r in db.scalars(q).unique()]


@router.get("/routes/{route_id}")
def get_route(route_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*VIEW_ROLES))):
    r = db.get(Route, route_id)
    if not r:
        raise HTTPException(404, "Route not found")
    if not can_access_depot(user, r.depot_id):
        raise HTTPException(403, "That route belongs to another depot")
    return route_out(r)


@router.post("/routes", status_code=201)
def create_route(body: RouteIn, db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    if not db.get(Depot, body.depot_id):
        raise HTTPException(422, "Unknown depot")
    if db.scalar(select(Route.id).where(Route.code == body.code.upper())):
        raise HTTPException(409, "Route code already exists")
    r = Route(code=body.code.upper(), name=body.name, depot_id=body.depot_id)
    db.add(r)
    db.flush()
    _apply_stops(db, r, body.stops)
    db.commit()
    return route_out(r)


@router.put("/routes/{route_id}")
def update_route(route_id: int, body: RouteIn, db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    r = db.get(Route, route_id)
    if not r:
        raise HTTPException(404, "Route not found")
    clash = db.scalar(select(Route.id).where(Route.code == body.code.upper(), Route.id != route_id))
    if clash:
        raise HTTPException(409, "Route code already exists")
    r.code, r.name, r.depot_id = body.code.upper(), body.name, body.depot_id
    _apply_stops(db, r, body.stops)
    db.commit()
    return route_out(r)


@router.delete("/routes/{route_id}", status_code=204)
def delete_route(route_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    r = db.get(Route, route_id)
    if not r:
        raise HTTPException(404, "Route not found")
    if db.scalar(select(Duty.id).where(Duty.route_id == route_id).limit(1)):
        raise HTTPException(409, "Route is used by existing duties and cannot be deleted")
    db.delete(r)
    db.commit()


# ------------------------------------------------------------------ duties
class DutyIn(BaseModel):
    date: date
    driver_id: int
    vehicle_id: int
    route_id: int
    conductor_id: int | None = None
    start_time: time = time(6, 0)
    end_time: time = time(14, 0)


def _validate_duty(db: Session, body: DutyIn, user: User, ignore_id: int | None = None) -> int:
    """Checks depot consistency + double-booking. Returns depot_id."""
    vehicle, route, driver = db.get(Vehicle, body.vehicle_id), db.get(Route, body.route_id), db.get(User, body.driver_id)
    if not (vehicle and route and driver):
        raise HTTPException(422, "Unknown vehicle, route or driver")
    if driver.role != "driver":
        raise HTTPException(422, "The selected person is not a driver")
    if vehicle.status != "active":
        raise HTTPException(422, f"{vehicle.reg_no} is not active ({vehicle.status})")
    if not can_access_depot(user, vehicle.depot_id):
        raise HTTPException(403, "You can only schedule your own depot")
    if not (driver.depot_id == vehicle.depot_id == route.depot_id):
        raise HTTPException(422, "Driver, vehicle and route must belong to the same depot")
    if body.conductor_id:
        c = db.get(User, body.conductor_id)
        if not c or c.role != "conductor" or c.depot_id != vehicle.depot_id:
            raise HTTPException(422, "Conductor must be a conductor from the same depot")
    if body.end_time <= body.start_time:
        raise HTTPException(422, "End time must be after start time")
    for col, val, label in ((Duty.driver_id, body.driver_id, "Driver"), (Duty.vehicle_id, body.vehicle_id, "Vehicle")):
        q = select(Duty.id).where(Duty.date == body.date, col == val)
        if ignore_id:
            q = q.where(Duty.id != ignore_id)
        if db.scalar(q):
            raise HTTPException(409, f"{label} is already assigned to another duty on {body.date.isoformat()}")
    return vehicle.depot_id


def _load_duty(db: Session, duty_id: int) -> Duty:
    d = db.scalar(select(Duty).where(Duty.id == duty_id).options(
        joinedload(Duty.vehicle), joinedload(Duty.driver), joinedload(Duty.conductor),
        joinedload(Duty.route).joinedload(Route.stops).joinedload(RouteStop.stop)))
    if not d:
        raise HTTPException(404, "Duty not found")
    return d


@router.post("/duties", status_code=201)
def create_duty(body: DutyIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*OPS_ROLES))):
    depot_id = _validate_duty(db, body, user)
    d = Duty(**body.model_dump(), depot_id=depot_id, status="draft")
    db.add(d)
    try:
        db.commit()
    except IntegrityError:  # race with another manager
        db.rollback()
        raise HTTPException(409, "Driver or vehicle was just assigned elsewhere for that day")
    return duty_out(_load_duty(db, d.id))


@router.put("/duties/{duty_id}")
def update_duty(duty_id: int, body: DutyIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*OPS_ROLES))):
    d = _load_duty(db, duty_id)
    if not can_access_depot(user, d.depot_id):
        raise HTTPException(403, "That duty belongs to another depot")
    if d.ack_at:
        raise HTTPException(409, "The driver has already acknowledged this duty")
    depot_id = _validate_duty(db, body, user, ignore_id=duty_id)
    for k, v in body.model_dump().items():
        setattr(d, k, v)
    d.depot_id = depot_id
    d.status = "draft"  # edits need re-publishing
    db.commit()
    return duty_out(_load_duty(db, duty_id))


@router.delete("/duties/{duty_id}", status_code=204)
def delete_duty(duty_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*OPS_ROLES))):
    d = db.get(Duty, duty_id)
    if not d:
        raise HTTPException(404, "Duty not found")
    if not can_access_depot(user, d.depot_id):
        raise HTTPException(403, "That duty belongs to another depot")
    if d.ack_at:
        raise HTTPException(409, "The driver has already acknowledged this duty")
    db.delete(d)
    db.commit()


class PublishIn(BaseModel):
    depot_id: int
    date_from: date
    date_to: date


@router.post("/duties/publish")
def publish(body: PublishIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*OPS_ROLES))):
    if not can_access_depot(user, body.depot_id):
        raise HTTPException(403, "You can only publish your own depot")
    if body.date_to < body.date_from:
        raise HTTPException(422, "date_to is before date_from")
    drafts = list(db.scalars(select(Duty).where(Duty.depot_id == body.depot_id, Duty.status == "draft",
                                                 Duty.date >= body.date_from, Duty.date <= body.date_to)))
    for d in drafts:
        d.status = "published"
    db.commit()
    return {"published": len(drafts)}


@router.get("/roster")
def roster(depot_id: int, week_start: date, db: Session = Depends(get_db),
           user: User = Depends(require_roles(*OPS_ROLES, "executive"))):
    resolve_depot(user, depot_id)
    days = [week_start + timedelta(days=i) for i in range(7)]
    duties = db.scalars(select(Duty).where(Duty.depot_id == depot_id, Duty.date >= days[0], Duty.date <= days[-1])
                        .options(joinedload(Duty.vehicle), joinedload(Duty.driver), joinedload(Duty.conductor),
                                 joinedload(Duty.route)))
    users = db.scalars(select(User).where(User.depot_id == depot_id).order_by(User.full_name))
    return {
        "depot_id": depot_id, "days": [d.isoformat() for d in days],
        "drivers": [{"id": u.id, "full_name": u.full_name, "username": u.username} for u in users if u.role == "driver"],
        "conductors": [{"id": u.id, "full_name": u.full_name} for u in users if u.role == "conductor"],
        "vehicles": [{"id": v.id, "reg_no": v.reg_no, "status": v.status}
                     for v in db.scalars(select(Vehicle).where(Vehicle.depot_id == depot_id).order_by(Vehicle.reg_no))],
        "routes": [{"id": r.id, "code": r.code, "name": r.name}
                   for r in db.scalars(select(Route).where(Route.depot_id == depot_id).order_by(Route.code))],
        "duties": [duty_out(d) for d in duties.unique()],
    }


class CopyIn(BaseModel):
    depot_id: int
    week_start: date  # the week to fill, copied from the week before


@router.post("/roster/copy-last-week")
def copy_last_week(body: CopyIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*OPS_ROLES))):
    if not can_access_depot(user, body.depot_id):
        raise HTTPException(403, "You can only schedule your own depot")
    prev = body.week_start - timedelta(days=7)
    src = list(db.scalars(select(Duty).where(Duty.depot_id == body.depot_id, Duty.date >= prev,
                                              Duty.date < body.week_start)))
    created = skipped = 0
    for s in src:
        target = s.date + timedelta(days=7)
        busy = db.scalar(select(Duty.id).where(Duty.date == target,
                                               (Duty.driver_id == s.driver_id) | (Duty.vehicle_id == s.vehicle_id)))
        if busy:
            skipped += 1
            continue
        db.add(Duty(date=target, depot_id=s.depot_id, vehicle_id=s.vehicle_id, driver_id=s.driver_id,
                    conductor_id=s.conductor_id, route_id=s.route_id, start_time=s.start_time,
                    end_time=s.end_time, status="draft"))
        created += 1
    db.commit()
    return {"created": created, "skipped": skipped}


# --------------------------------------------------- search (trip-search style)
@router.get("/duties/search")
def search_duties(day: date | None = None, depot_id: int | None = None, route_id: int | None = None,
                  status: str | None = None, db: Session = Depends(get_db),
                  user: User = Depends(require_roles(*VIEW_ROLES))):
    depot_id = resolve_depot(user, depot_id)
    q = (select(Duty).where(Duty.date == (day or today_ist())).order_by(Duty.start_time, Duty.id)
         .options(joinedload(Duty.vehicle), joinedload(Duty.driver), joinedload(Duty.conductor),
                  joinedload(Duty.route).joinedload(Route.stops).joinedload(RouteStop.stop)))
    if depot_id:
        q = q.where(Duty.depot_id == depot_id)
    if route_id:
        q = q.where(Duty.route_id == route_id)
    if status:
        q = q.where(Duty.status == status)
    return [duty_out(d, with_stops=True) for d in db.scalars(q).unique()]


# ----------------------------------------------------------- driver-side
@router.get("/me/duties")
def my_duties(db: Session = Depends(get_db), user: User = Depends(require_roles(*CREW_ROLES))):
    """Published duties from today to +2 days, today first."""
    today = today_ist()
    col = Duty.driver_id if user.role == "driver" else Duty.conductor_id
    q = (select(Duty).where(col == user.id, Duty.status != "draft", Duty.date >= today, Duty.date <= today + timedelta(days=2))
         .order_by(Duty.date).options(joinedload(Duty.vehicle), joinedload(Duty.driver), joinedload(Duty.conductor),
                                      joinedload(Duty.route).joinedload(Route.stops).joinedload(RouteStop.stop)))
    return [duty_out(d, with_stops=True) for d in db.scalars(q).unique()]


@router.post("/duties/{duty_id}/ack")
def acknowledge(duty_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*CREW_ROLES))):
    d = _load_duty(db, duty_id)
    if user.id not in (d.driver_id, d.conductor_id):
        raise HTTPException(403, "This is not your duty")
    if d.status == "draft":
        raise HTTPException(409, "This duty has not been published yet")
    if not d.ack_at:
        d.ack_at, d.status = utcnow(), "acknowledged"
        db.commit()
    return duty_out(d, with_stops=True)
