from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class StudentBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=150, description="Full student name")
    student_number: str = Field(..., min_length=2, max_length=50, description="Student ID / roll number")

class StudentCreate(StudentBase):
    group_name: Optional[str] = Field("Group A", description="Academic group to enroll into")

class StudentResponse(StudentBase):
    id: int
    is_active: bool
    embeddings_count: int = 0
    groups: List[str] = []
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class EnrollmentResult(BaseModel):
    status: str
    message: str
    student_id: int
    name: str
    student_number: str
    group_name: str
    embeddings_saved: int
    quality_scores: List[float]

class Base64EnrollmentRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    student_number: str = Field(..., min_length=2, max_length=50)
    group_name: Optional[str] = Field("Group A")
    images: List[str] = Field(..., min_length=1, description="List of base64 data URLs or base64 strings")
