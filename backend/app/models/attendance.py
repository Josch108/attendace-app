from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, ForeignKey, UniqueConstraint, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

def _to_naive_utc(dt: datetime) -> datetime:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_session_student"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("class_sessions.id"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    
    # Status: ABSENT, PRESENT, TEMPORARILY_MISSING, LEFT
    status: Mapped[str] = mapped_column(String(30), default="ABSENT", nullable=False, index=True)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    percentage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    source: Mapped[str] = mapped_column(String(30), default="vision", nullable=False)  # vision, manual

    # Relationships
    session = relationship("ClassSession", back_populates="attendance_records")
    student = relationship("Student", back_populates="attendance_records")
    intervals = relationship("AttendanceInterval", back_populates="record", cascade="all, delete-orphan")
    corrections = relationship("ManualCorrection", back_populates="record", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AttendanceRecord(session={self.session_id}, student={self.student_id}, status='{self.status}')>"


class AttendanceInterval(Base):
    __tablename__ = "attendance_intervals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    attendance_record_id: Mapped[int] = mapped_column(ForeignKey("attendance_records.id"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    close_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)  # timeout, session_ended, manual

    # Relationships
    record = relationship("AttendanceRecord", back_populates="intervals")

    @property
    def duration_seconds(self) -> int:
        if not self.started_at:
            return 0
        end = self.ended_at or datetime.now(timezone.utc)
        start_naive = _to_naive_utc(self.started_at)
        end_naive = _to_naive_utc(end)
        return max(0, int((end_naive - start_naive).total_seconds()))


class AttendanceEvent(Base):
    __tablename__ = "attendance_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)  # UUID for idempotency
    session_id: Mapped[int] = mapped_column(ForeignKey("class_sessions.id"), nullable=False, index=True)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id"), nullable=True, index=True)
    track_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    camera_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    session = relationship("ClassSession", back_populates="events")


class ManualCorrection(Base):
    __tablename__ = "manual_corrections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("attendance_records.id"), nullable=False, index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    before_status: Mapped[str] = mapped_column(String(30), nullable=False)
    after_status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    record = relationship("AttendanceRecord", back_populates="corrections")
