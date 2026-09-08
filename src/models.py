from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class Location(BaseModel):
    DataCenter: str
    Room: str
    Row: str
    Rack: str
    Chassis: Optional[str] = None
    Slot: Optional[str] = None

class RedfishAlert(BaseModel):
    EventId: str
    Timestamp: str
    Severity: str
    MessageId: str
    Message: str
    MessageArgs: List[str] = Field(default_factory=list)
    OriginOfCondition: str
    Location: Location
    Subsystem: str
    Resolution: Optional[str] = None

class AlertStats(BaseModel):
    total: int
    critical: int
    warning: int
    ok: int
    racks_affected: int
    subsystems_affected: int
    subsystems: List[str]
    racks: List[str]
