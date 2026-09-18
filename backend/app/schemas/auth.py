from typing import Optional
from pydantic import BaseModel, Field, field_validator


def _validate_email(value: str) -> str:
    if "@" not in value or "." not in value.split("@")[-1]:
        raise ValueError("Enter a valid email address.")
    return value.strip().lower()


class TeacherRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120, description="Teacher's full name")
    institution: Optional[str] = Field(None, max_length=150, description="School / institution name")
    email: str = Field(..., max_length=150)
    password: str = Field(..., min_length=4, max_length=200)

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        return _validate_email(v)


class TeacherLoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        return _validate_email(v)


class TeacherResponse(BaseModel):
    id: int
    name: str
    email: str
    institution: Optional[str] = None
    role: str

    class Config:
        from_attributes = True
