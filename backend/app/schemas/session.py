from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class ClassSessionCreate(BaseModel):
    group_name: Optional[str] = Field("Group A", description="Academic group name")
    group_id: Optional[int] = Field(None, description="Existing group ID (optional)")
    course_code: Optional[str] = Field("COURSE-101", description="Course code")

class ClassSessionResponse(BaseModel):
    id: int
    group_id: int
    group_name: str
    course_name: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: str
    total_enrolled: int
    present_count: int

    class Config:
        from_attributes = True

class AttendanceIntervalResponse(BaseModel):
    id: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: int = 0
    close_reason: Optional[str] = None

    class Config:
        from_attributes = True

class AttendanceRecordResponse(BaseModel):
    id: int
    student_id: int
    student_name: str
    student_number: str
    status: str
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    total_seconds: int = 0
    percentage: float = 0.0
    source: str = "vision"
    intervals: List[AttendanceIntervalResponse] = []

    class Config:
        from_attributes = True

class SessionAttendanceSummary(BaseModel):
    session_id: int
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: int = 0
    total_enrolled: int = 0
    present_count: int = 0
    absent_count: int = 0
    average_percentage: float = 0.0
    records: List[AttendanceRecordResponse] = []
    csv_filename: Optional[str] = None
    csv_file_path: Optional[str] = None
    csv_download_url: Optional[str] = None

class ManualCorrectionRequest(BaseModel):
    new_status: str = Field(..., pattern="^(PRESENT|ABSENT|LEFT|TEMPORARILY_MISSING)$", description="New status")
    reason: str = Field(..., min_length=3, max_length=500, description="Reason for the manual adjustment")
