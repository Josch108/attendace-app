from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class EnrolledStudent(BaseModel):
    id: int
    student_number: str
    name: str

    class Config:
        from_attributes = True


class EnrollStudentRequest(BaseModel):
    student_id: int


class MateriaCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Subject / group name, e.g. 'Data Structures - Group A'")
    required_hours: int = Field(0, ge=0, description="Total instructional hours students must complete")


class MateriaResponse(BaseModel):
    id: int
    name: str
    required_hours: int
    student_count: int = 0
    sessions_count: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
