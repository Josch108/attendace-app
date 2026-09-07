from app.db.base import Base
from app.models.user import User
from app.models.student import Student
from app.models.academic import Course, Group, Enrollment
from app.models.session import ClassSession
from app.models.attendance import (
    Camera,
    AttendanceRecord,
    AttendanceInterval,
    AttendanceEvent,
    ManualCorrection
)
from app.models.biometric import FaceEmbedding

__all__ = [
    "Base",
    "User",
    "Student",
    "Course",
    "Group",
    "Enrollment",
    "ClassSession",
    "Camera",
    "AttendanceRecord",
    "AttendanceInterval",
    "AttendanceEvent",
    "ManualCorrection",
    "FaceEmbedding"
]
