"""Module 4 — CMS: notices with audience targeting and read receipts."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Depot, Notice, NoticeRead, User
from ..security import GLOBAL_ROLES, ROLES, get_current_user, require_roles
from ..timeutil import iso, utcnow

router = APIRouter(prefix="/notices", tags=["CMS"])


class AudienceIn(BaseModel):
    type: Literal["all", "depot", "role"]
    depot_id: int | None = None
    role: str | None = None


class NoticeIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=1, max_length=10000)
    audience: AudienceIn
    publish_at: str | None = None  # ISO datetime (UTC); default now
    requires_ack: bool = False


def _audience_users(db: Session, aud: dict) -> list[User]:
    q = select(User).order_by(User.full_name)
    if aud["type"] == "depot":
        q = q.where(User.depot_id == aud["depot_id"])
    elif aud["type"] == "role":
        q = q.where(User.role == aud["role"])
    return list(db.scalars(q))


def _targets(n: Notice, user: User) -> bool:
    a = n.audience_json
    return (a["type"] == "all"
            or (a["type"] == "depot" and a.get("depot_id") == user.depot_id)
            or (a["type"] == "role" and a.get("role") == user.role))


def _out(n: Notice, read: NoticeRead | None = None) -> dict:
    return {"id": n.id, "title": n.title, "body": n.body, "audience": n.audience_json,
            "publish_at": iso(n.publish_at), "created_by": n.created_by, "author_name": n.author.full_name,
            "requires_ack": n.requires_ack, "read_at": iso(read.read_at) if read else None,
            "ack_at": iso(read.ack_at) if read else None}


@router.post("", status_code=201)
def create_notice(body: NoticeIn, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    aud = body.audience.model_dump(exclude_none=True)
    if aud["type"] == "depot" and not db.get(Depot, aud.get("depot_id") or 0):
        raise HTTPException(422, "Pick a valid depot for the audience")
    if aud["type"] == "role" and aud.get("role") not in ROLES:
        raise HTTPException(422, "Pick a valid role for the audience")
    from datetime import datetime
    when = utcnow()
    if body.publish_at:
        try:
            when = datetime.fromisoformat(body.publish_at.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            raise HTTPException(422, "publish_at must be an ISO datetime")
    n = Notice(title=body.title, body=body.body, audience_json=aud, publish_at=when, created_by=user.id,
               requires_ack=body.requires_ack)
    db.add(n)
    db.commit()
    return _out(n)


@router.get("")
def list_notices(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Admins see everything (incl. scheduled). Everyone else sees published notices aimed at them."""
    notices = list(db.scalars(select(Notice).order_by(Notice.publish_at.desc())))
    reads = {r.notice_id: r for r in db.scalars(select(NoticeRead).where(NoticeRead.user_id == user.id))}
    if user.role != "admin":
        notices = [n for n in notices if n.publish_at <= utcnow() and _targets(n, user)]
    return [_out(n, reads.get(n.id)) for n in notices]


def _visible_or_404(db: Session, notice_id: int, user: User) -> Notice:
    n = db.get(Notice, notice_id)
    if not n or (user.role != "admin" and (n.publish_at > utcnow() or not _targets(n, user))):
        raise HTTPException(404, "Notice not found")
    return n


@router.post("/{notice_id}/read")
def mark_read(notice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = _visible_or_404(db, notice_id, user)
    r = db.get(NoticeRead, (n.id, user.id))
    if not r:
        r = NoticeRead(notice_id=n.id, user_id=user.id, read_at=utcnow())
        db.add(r)
        db.commit()
    return _out(n, r)


@router.post("/{notice_id}/ack")
def acknowledge(notice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = _visible_or_404(db, notice_id, user)
    r = db.get(NoticeRead, (n.id, user.id))
    if not r:
        r = NoticeRead(notice_id=n.id, user_id=user.id, read_at=utcnow())
        db.add(r)
    if not r.ack_at:
        r.ack_at = utcnow()
    db.commit()
    return _out(n, r)


@router.get("/{notice_id}/receipts")
def receipts(notice_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles("admin"))):
    n = db.get(Notice, notice_id)
    if not n:
        raise HTTPException(404, "Notice not found")
    reads = {r.user_id: r for r in db.scalars(select(NoticeRead).where(NoticeRead.notice_id == n.id))}
    people = _audience_users(db, n.audience_json)
    rows = [{"user_id": u.id, "full_name": u.full_name, "role": u.role, "depot_id": u.depot_id,
             "read_at": iso(reads[u.id].read_at) if u.id in reads else None,
             "ack_at": iso(reads[u.id].ack_at) if u.id in reads else None} for u in people]
    return {"notice_id": n.id, "title": n.title, "requires_ack": n.requires_ack,
            "total": len(rows), "read": sum(1 for r in rows if r["read_at"]),
            "acknowledged": sum(1 for r in rows if r["ack_at"]), "recipients": rows}
