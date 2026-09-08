from datetime import datetime
from typing import Optional, List, Any, Dict, Union
from pydantic import BaseModel, Field

class VisionEventIngest(BaseModel):
    event_id: str = Field(..., description="UUID for idempotent message processing")
    event_type: str = Field(..., description="STUDENT_RECOGNIZED, STUDENT_PRESENT, STUDENT_LEFT, STUDENT_RETURNED, UNKNOWN_PERSON_DETECTED")
    class_session_id: int = Field(..., description="Target active class session ID")
    student_id: Optional[int] = Field(None, description="Enrolled student ID if identified")
    track_id: Optional[Union[str, int]] = Field(None, description="ByteTrack temporal tracking identifier")
    camera_id: Optional[str] = Field("classroom-1", description="Camera device identifier")
    confidence: Optional[float] = Field(None, description="Detection or recognition confidence")
    observed_at: Optional[datetime] = Field(None, description="Event observation timestamp in UTC")
    occurred_at: Optional[datetime] = Field(None, description="Alias for observation timestamp")
    bbox: Optional[List[int]] = Field(None, description="Bounding box [x1, y1, x2, y2]")
    model_version: Optional[str] = Field("insightface/buffalo_l", description="Model version")
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context or metadata")

class VisionEventResponse(BaseModel):
    status: str
    message: str
    event_id: str
    processed: bool
