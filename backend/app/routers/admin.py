"""Master data: depots, vehicles, users, stops."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..geo import square_polygon
from ..models import Depot, Stop, User, Vehicle
from ..security import (
    GLOBAL_ROLES, ROLES, VIEW_ROLES, get_current_user, hash_password, require_roles, resolve_depot,
)
from ..serializers import user_out

router = APIRouter(tags=["master data"])


class DepotIn(BaseModel):
    code: str = Field(min_length=2, max_length=16)
    name: str
    location_lat: float
    location_lng: float


class VehicleIn(BaseModel):
    reg_no: str = Field(min_length=4, max_length=20)
    depot_id: int
    status: str = "active"


class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6)
    full_name: str
    role: str
    depot_id: int | None = None
    phone: str | None = None


class StopIn(BaseModel):
    name: str
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


def _commit(db: Session, what: str):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"{what} already exists")


# ---- depots
@router.get("/depots")
def list_depots(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = select(Depot).order_by(Depot.code)
    if user.role not in GLOBAL_ROLES:
        q = q.where(Depot.id == user.depot_id)
    return [{"id": d.id, "code": d.code, "name": d.name, "lat": d.location_lat, "lng": d.location_lng,
             "polygon": d.polygon_geojson} for d in db.scalars(q)]


@router.post("/depots", status_code=201)
def create_depot(body: DepotIn, db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    d = Depot(code=body.code.upper(), name=body.name, location_lat=body.location_lat,
              location_lng=body.location_lng, polygon_geojson=square_polygon(body.location_lat, body.location_lng))
    db.add(d)
    _commit(db, "Depot code")
    return {"id": d.id}


# ---- vehicles
@router.get("/vehicles")
def list_vehicles(depot_id: int | None = None, db: Session = Depends(get_db),
                  user: User = Depends(require_roles(*VIEW_ROLES))):
    q = select(Vehicle).order_by(Vehicle.reg_no)
    depot_id = resolve_depot(user, depot_id)
    if depot_id:
        q = q.where(Vehicle.depot_id == depot_id)
    return [{"id": v.id, "reg_no": v.reg_no, "depot_id": v.depot_id, "status": v.status} for v in db.scalars(q)]


@router.post("/vehicles", status_code=201)
def create_vehicle(body: VehicleIn, db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    if not db.get(Depot, body.depot_id):
        raise HTTPException(422, "Unknown depot")
    v = Vehicle(reg_no=body.reg_no.upper(), depot_id=body.depot_id, status=body.status)
    db.add(v)
    _commit(db, "Vehicle registration")
    return {"id": v.id}


# ---- users
@router.get("/users")
def list_users(role: str | None = None, depot_id: int | None = None, db: Session = Depends(get_db),
               user: User = Depends(require_roles("admin", "control_operator", "depot_manager"))):
    q = select(User).order_by(User.full_name)
    depot_id = resolve_depot(user, depot_id)
    if depot_id:
        q = q.where(User.depot_id == depot_id)
    if role:
        q = q.where(User.role == role)
    return [user_out(u) for u in db.scalars(q)]


@router.post("/users", status_code=201)
def create_user(body: UserIn, db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    if body.role not in ROLES:
        raise HTTPException(422, f"role must be one of {ROLES}")
    if body.role in ("driver", "conductor", "depot_manager") and not body.depot_id:
        raise HTTPException(422, "depot_id is required for this role")
    u = User(username=body.username, password_hash=hash_password(body.password), full_name=body.full_name,
             role=body.role, depot_id=body.depot_id, phone=body.phone)
    db.add(u)
    _commit(db, "Username")
    return user_out(u)


# ---- stops
@router.get("/stops")
def list_stops(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [{"id": s.id, "name": s.name, "lat": s.lat, "lng": s.lng} for s in db.scalars(select(Stop).order_by(Stop.name))]


@router.post("/stops", status_code=201)
def create_stop(body: StopIn, db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    s = Stop(name=body.name, lat=body.lat, lng=body.lng)
    db.add(s)
    db.commit()
    return {"id": s.id, "name": s.name, "lat": s.lat, "lng": s.lng}
