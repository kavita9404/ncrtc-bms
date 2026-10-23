"""Data model — the eleven tables from the PRD (§6), plus `incident` photo/location columns."""
from sqlalchemy import (
    JSON, Boolean, Column, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, Time,
    UniqueConstraint, desc,
)
from sqlalchemy.orm import relationship

from .database import Base
from .timeutil import utcnow


class Depot(Base):
    __tablename__ = "depot"
    id = Column(Integer, primary_key=True)
    code = Column(String(16), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    location_lat = Column(Float, nullable=False)
    location_lng = Column(Float, nullable=False)
    # GeoJSON Polygon: {"type": "Polygon", "coordinates": [[[lng, lat], ...]]}
    polygon_geojson = Column(JSON)


class Vehicle(Base):
    __tablename__ = "vehicle"
    id = Column(Integer, primary_key=True)
    reg_no = Column(String(20), unique=True, nullable=False)
    depot_id = Column(Integer, ForeignKey("depot.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="active")  # active | maintenance
    depot = relationship("Depot")


class User(Base):
    __tablename__ = "users"  # "user" is reserved in PostgreSQL
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(100), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False)  # driver|conductor|depot_manager|control_operator|admin|executive
    depot_id = Column(Integer, ForeignKey("depot.id"), index=True)
    phone = Column(String(20))
    depot = relationship("Depot")


class Stop(Base):
    __tablename__ = "stop"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)


class Route(Base):
    __tablename__ = "route"
    id = Column(Integer, primary_key=True)
    code = Column(String(16), unique=True, nullable=False)
    name = Column(String(120), nullable=False)
    depot_id = Column(Integer, ForeignKey("depot.id"), nullable=False, index=True)
    stops = relationship("RouteStop", order_by="RouteStop.sequence", cascade="all, delete-orphan")


class RouteStop(Base):
    __tablename__ = "route_stop"
    id = Column(Integer, primary_key=True)
    route_id = Column(Integer, ForeignKey("route.id", ondelete="CASCADE"), nullable=False)
    stop_id = Column(Integer, ForeignKey("stop.id"), nullable=False)
    sequence = Column(Integer, nullable=False)
    planned_offset_min = Column(Integer, nullable=False, default=0)  # minutes after trip start
    stop = relationship("Stop")
    __table_args__ = (UniqueConstraint("route_id", "sequence", name="uq_route_seq"),)


class Duty(Base):
    __tablename__ = "duty"
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    depot_id = Column(Integer, ForeignKey("depot.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicle.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    conductor_id = Column(Integer, ForeignKey("users.id"))
    route_id = Column(Integer, ForeignKey("route.id"), nullable=False)
    start_time = Column(Time, nullable=False)  # IST wall-clock
    end_time = Column(Time, nullable=False)
    status = Column(String(16), nullable=False, default="draft")  # draft | published | acknowledged
    ack_at = Column(DateTime)

    vehicle = relationship("Vehicle")
    driver = relationship("User", foreign_keys=[driver_id])
    conductor = relationship("User", foreign_keys=[conductor_id])
    route = relationship("Route")

    __table_args__ = (
        UniqueConstraint("date", "driver_id", name="uq_duty_driver_day"),
        UniqueConstraint("date", "vehicle_id", name="uq_duty_vehicle_day"),
        Index("ix_duty_date_depot", "date", "depot_id"),
    )


class GpsPing(Base):
    __tablename__ = "gps_ping"
    id = Column(Integer, primary_key=True)
    vehicle_id = Column(Integer, ForeignKey("vehicle.id"), nullable=False)
    ts = Column(DateTime, nullable=False)  # naive UTC
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    speed_kmh = Column(Float, nullable=False, default=0)
    ignition_on = Column(Boolean, nullable=False, default=True)
    __table_args__ = (Index("ix_gps_vehicle_ts", "vehicle_id", desc("ts")),)


class Incident(Base):
    __tablename__ = "incident"
    id = Column(Integer, primary_key=True)
    type = Column(String(20), nullable=False)  # breakdown|accident|complaint|other|panic
    severity = Column(String(2), nullable=False)  # P1|P2|P3
    status = Column(String(16), nullable=False, default="open")
    raised_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_to = Column(Integer, ForeignKey("users.id"))
    vehicle_id = Column(Integer, ForeignKey("vehicle.id"))
    depot_id = Column(Integer, ForeignKey("depot.id"))
    description = Column(Text, nullable=False)
    photo_path = Column(String(200))
    lat = Column(Float)
    lng = Column(Float)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    resolved_at = Column(DateTime)

    raiser = relationship("User", foreign_keys=[raised_by])
    assignee = relationship("User", foreign_keys=[assigned_to])
    vehicle = relationship("Vehicle")
    depot = relationship("Depot")
    events = relationship("IncidentEvent", order_by="IncidentEvent.ts", cascade="all, delete-orphan")
    __table_args__ = (Index("ix_incident_status_depot", "status", "depot_id"),)


class IncidentEvent(Base):
    __tablename__ = "incident_event"
    id = Column(Integer, primary_key=True)
    incident_id = Column(Integer, ForeignKey("incident.id", ondelete="CASCADE"), nullable=False)
    ts = Column(DateTime, nullable=False, default=utcnow)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    from_status = Column(String(16))
    to_status = Column(String(16), nullable=False)
    note = Column(Text)
    actor = relationship("User")


class Notice(Base):
    __tablename__ = "notice"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    # {"type": "all"} | {"type": "depot", "depot_id": 1} | {"type": "role", "role": "driver"}
    audience_json = Column(JSON, nullable=False)
    publish_at = Column(DateTime, nullable=False, default=utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    requires_ack = Column(Boolean, nullable=False, default=False)
    author = relationship("User")


class NoticeRead(Base):
    __tablename__ = "notice_read"
    notice_id = Column(Integer, ForeignKey("notice.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    read_at = Column(DateTime, nullable=False, default=utcnow)
    ack_at = Column(DateTime)
