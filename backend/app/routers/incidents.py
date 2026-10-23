"""Module 3 — IMS: incidents, status workflow, assignment, panic button."""
import os
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..config import MAX_UPLOAD_BYTES, UPLOAD_DIR
from ..database import get_db
from ..models import Duty, GpsPing, Incident, IncidentEvent, User, Vehicle
from ..security import CREW_ROLES, GLOBAL_ROLES, OPS_ROLES, can_access_depot, get_current_user, require_roles
from ..serializers import incident_out
from ..timeutil import today_ist, utcnow

router = APIRouter(prefix="/incidents", tags=["IMS"])

STATUSES = ("open", "acknowledged", "in_progress", "resolved", "closed")
# Allowed moves. resolved -> in_progress lets a manager re-open work that was not really fixed.
TRANSITIONS = {
    "open": {"acknowledged"},
    "acknowledged": {"in_progress"},
    "in_progress": {"resolved"},
    "resolved": {"closed", "in_progress"},
    "closed": set(),
}


class IncidentIn(BaseModel):
    type: Literal["breakdown", "accident", "complaint", "other"]
    severity: Literal["P1", "P2", "P3"]
    description: str = Field(min_length=5, max_length=2000)
    vehicle_id: int | None = None


class TransitionIn(BaseModel):
    to_status: Literal["acknowledged", "in_progress", "resolved", "closed"]
    note: str = Field(min_length=3, max_length=1000)


class AssignIn(BaseModel):
    assignee_id: int
    note: str | None = None


class NoteIn(BaseModel):
    note: str = Field(min_length=1, max_length=1000)


class PanicIn(BaseModel):
    lat: float | None = None
    lng: float | None = None


def _get(db: Session, incident_id: int) -> Incident:
    i = db.scalar(select(Incident).where(Incident.id == incident_id).options(
        joinedload(Incident.raiser), joinedload(Incident.assignee), joinedload(Incident.vehicle),
        joinedload(Incident.depot)))
    if not i:
        raise HTTPException(404, "Incident not found")
    return i


def _check_visible(i: Incident, user: User):
    if user.role in CREW_ROLES:
        ok = i.raised_by == user.id
    else:
        ok = can_access_depot(user, i.depot_id)
    if not ok:
        raise HTTPException(403, "You cannot see this incident")


def _check_manage(i: Incident, user: User):
    if user.role not in OPS_ROLES or not can_access_depot(user, i.depot_id):
        raise HTTPException(403, "Only managers of this depot, control room and admins can do this")


def _event(db: Session, i: Incident, actor: User, to_status: str, note: str | None, from_status: str | None = None):
    db.add(IncidentEvent(incident_id=i.id, actor_id=actor.id, from_status=from_status, to_status=to_status, note=note))


@router.post("", status_code=201)
def raise_incident(body: IncidentIn, db: Session = Depends(get_db),
                   user: User = Depends(require_roles(*CREW_ROLES, *OPS_ROLES))):
    depot_id = user.depot_id
    if body.vehicle_id:
        v = db.get(Vehicle, body.vehicle_id)
        if not v:
            raise HTTPException(422, "Unknown vehicle")
        if not can_access_depot(user, v.depot_id):
            raise HTTPException(403, "That vehicle belongs to another depot")
        depot_id = v.depot_id
    if depot_id is None:
        raise HTTPException(422, "Pick a vehicle so the incident can be routed to a depot")
    i = Incident(type=body.type, severity=body.severity, description=body.description, vehicle_id=body.vehicle_id,
                 depot_id=depot_id, raised_by=user.id, status="open")
    db.add(i)
    db.flush()
    _event(db, i, user, "open", "Incident raised")
    db.commit()
    return incident_out(_get(db, i.id), with_events=True)


@router.post("/panic", status_code=201)
def panic(body: PanicIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*CREW_ROLES))):
    col = Duty.driver_id if user.role == "driver" else Duty.conductor_id
    duty = db.scalar(select(Duty).where(col == user.id, Duty.date == today_ist(), Duty.status != "draft"))
    lat, lng = body.lat, body.lng
    if duty and lat is None:  # fall back to the bus's last known position
        p = db.scalar(select(GpsPing).where(GpsPing.vehicle_id == duty.vehicle_id).order_by(GpsPing.ts.desc()).limit(1))
        if p:
            lat, lng = p.lat, p.lng
    i = Incident(type="panic", severity="P1", status="open", raised_by=user.id, depot_id=user.depot_id,
                 vehicle_id=duty.vehicle_id if duty else None, lat=lat, lng=lng,
                 description=f"PANIC button pressed by {user.full_name}" + ("" if duty else " (no duty found for today)"))
    db.add(i)
    db.flush()
    _event(db, i, user, "open", "Panic button pressed")
    db.commit()
    return incident_out(_get(db, i.id), with_events=True)


@router.get("")
def list_incidents(status: str | None = None, severity: str | None = None, depot_id: int | None = None,
                   mine: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = (select(Incident).order_by(Incident.created_at.desc())
         .options(joinedload(Incident.raiser), joinedload(Incident.assignee), joinedload(Incident.vehicle),
                  joinedload(Incident.depot)))
    if user.role in CREW_ROLES:
        q = q.where(Incident.raised_by == user.id)
    else:
        if user.role not in GLOBAL_ROLES:
            q = q.where(Incident.depot_id == user.depot_id)
        elif depot_id:
            q = q.where(Incident.depot_id == depot_id)
        if mine:
            q = q.where((Incident.raised_by == user.id) | (Incident.assigned_to == user.id))
    if status:
        q = q.where(Incident.status == status)
    if severity:
        q = q.where(Incident.severity == severity)
    return [incident_out(i) for i in db.scalars(q).unique()]


@router.get("/{incident_id}")
def incident_detail(incident_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    i = _get(db, incident_id)
    _check_visible(i, user)
    return incident_out(i, with_events=True)


@router.post("/{incident_id}/transition")
def transition(incident_id: int, body: TransitionIn, db: Session = Depends(get_db),
               user: User = Depends(require_roles(*OPS_ROLES))):
    i = _get(db, incident_id)
    _check_manage(i, user)
    if body.to_status not in TRANSITIONS[i.status]:
        allowed = ", ".join(sorted(TRANSITIONS[i.status])) or "none"
        raise HTTPException(409, f"Cannot move from {i.status} to {body.to_status}. Allowed next: {allowed}")
    prev = i.status
    i.status = body.to_status
    if body.to_status == "resolved":
        i.resolved_at = utcnow()
    elif body.to_status == "in_progress":
        i.resolved_at = None
    _event(db, i, user, body.to_status, body.note, from_status=prev)
    db.commit()
    return incident_out(_get(db, i.id), with_events=True)


@router.post("/{incident_id}/assign")
def assign(incident_id: int, body: AssignIn, db: Session = Depends(get_db),
           user: User = Depends(require_roles(*OPS_ROLES))):
    i = _get(db, incident_id)
    _check_manage(i, user)
    target = db.get(User, body.assignee_id)
    if not target or target.role not in OPS_ROLES or not can_access_depot(target, i.depot_id):
        raise HTTPException(422, "Assignee must be a manager of this depot, a control operator or an admin")
    i.assigned_to = target.id
    _event(db, i, user, i.status, body.note or f"Assigned to {target.full_name}", from_status=i.status)
    db.commit()
    return incident_out(_get(db, i.id), with_events=True)


@router.post("/{incident_id}/notes")
def add_note(incident_id: int, body: NoteIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    i = _get(db, incident_id)
    _check_visible(i, user)
    if user.role == "executive":
        raise HTTPException(403, "Read-only role")
    _event(db, i, user, i.status, body.note, from_status=i.status)
    db.commit()
    return incident_out(_get(db, i.id), with_events=True)


@router.post("/{incident_id}/photo")
async def upload_photo(incident_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    i = _get(db, incident_id)
    _check_visible(i, user)
    ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(file.content_type or "")
    if not ext:
        raise HTTPException(415, "Only JPEG, PNG or WebP images are accepted")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Image is larger than 5 MB")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"  # unguessable name; client filename is never used
    with open(os.path.join(UPLOAD_DIR, name), "wb") as f:
        f.write(data)
    i.photo_path = name
    db.commit()
    return incident_out(_get(db, i.id), with_events=True)
