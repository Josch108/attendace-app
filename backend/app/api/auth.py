from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import TeacherRegisterRequest, TeacherLoginRequest, TeacherResponse
from app.core.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TeacherResponse, status_code=status.HTTP_201_CREATED)
def register_teacher(req: TeacherRegisterRequest, db: Session = Depends(get_db)):
    """Creates a new teacher account. This is a simple, single-institution login,
    not a production-grade auth system."""
    existing = db.query(User).filter_by(email=req.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists. Please log in instead."
        )

    user = User(
        name=req.name,
        email=req.email,
        institution=req.institution,
        role="teacher",
        password_hash=hash_password(req.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TeacherResponse)
def login_teacher(req: TeacherLoginRequest, db: Session = Depends(get_db)):
    """Verifies teacher credentials and returns the teacher's profile."""
    user = db.query(User).filter_by(email=req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )
    return user
