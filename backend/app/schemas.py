from datetime import datetime, date, time
from pydantic import BaseModel, ConfigDict, Field

class LoginRequest(BaseModel): username: str; password: str
class TokenResponse(BaseModel): access_token: str; token_type: str = "bearer"; role: str; full_name: str
class DepotOut(BaseModel): model_config = ConfigDict(from_attributes=True); id: int; code: str; name: str; latitude: float; longitude: float
class VehicleCreate(BaseModel): registration: str = Field(min_length=5,max_length=20); depot_id: int; status: str = "Idle"
class VehicleOut(BaseModel): model_config = ConfigDict(from_attributes=True); id: int; registration: str; depot_id: int; status: str
class GPSOut(BaseModel): model_config = ConfigDict(from_attributes=True); id: int; vehicle_id: int; timestamp: datetime; latitude: float; longitude: float; speed_kmh: float; ignition_on: bool
class IncidentCreate(BaseModel): incident_type: str; severity: str = "P3"; description: str = Field(min_length=5,max_length=3000); vehicle_id: int | None = None; depot_id: int
class IncidentStatusUpdate(BaseModel): status: str; note: str = Field(min_length=3,max_length=1000)
class IncidentOut(BaseModel): model_config = ConfigDict(from_attributes=True); id: int; code: str; incident_type: str; severity: str; status: str; description: str; vehicle_id: int | None; depot_id: int; created_at: datetime
class NoticeCreate(BaseModel): title: str = Field(min_length=3,max_length=180); body: str = Field(min_length=1,max_length=10000); audience: dict = {}; publish: bool = True
class NoticeOut(BaseModel): model_config = ConfigDict(from_attributes=True); id: int; title: str; body: str; audience: dict; published_at: datetime | None
class DutyCreate(BaseModel): service_date: date; vehicle_id: int; driver_id: int; route_id: int; start_time: time; end_time: time
class DutyOut(BaseModel): model_config = ConfigDict(from_attributes=True); id: int; service_date: date; vehicle_id: int; driver_id: int; route_id: int; start_time: time; end_time: time; status: str; acknowledged_at: datetime | None
