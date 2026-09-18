from typing import List, Optional
from pydantic import BaseModel


class SessionPoint(BaseModel):
    """A single ended session's aggregate attendance, used to plot trend lines."""
    session_id: int
    started_at: str
    weekday: str
    average_percentage: float


class StudentRiskSummary(BaseModel):
    """
    Attendance-based risk summary for one student.

    NOTE: There is no grade/performance data in this system yet, so `risk_level`
    is a heuristic proxy computed purely from attendance history (overall rate +
    recent trend), not an actual prediction of academic performance.
    """
    student_id: int
    student_name: str
    student_number: str
    total_sessions: int
    sessions_present: int
    overall_percentage: float
    recent_percentage: float  # average of the last N sessions
    trend_direction: str      # "up", "down", "flat"
    trend_delta: float        # recent_percentage - overall_percentage
    risk_level: str           # "low", "moderate", "high"
    history: List[float] = []  # ordered list of per-session percentages (oldest -> newest)


class DayOfWeekStat(BaseModel):
    weekday: str              # "Monday", "Tuesday", ...
    average_percentage: float
    sessions_count: int


class AttendanceReport(BaseModel):
    group_name: Optional[str] = None
    total_sessions: int
    total_students: int
    overall_average_percentage: float
    day_of_week: List[DayOfWeekStat]
    trend: List[SessionPoint]
    students: List[StudentRiskSummary]
