from datetime import datetime, timezone
from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.session import ClassSession
from app.models.academic import Course, Group, Enrollment
from app.models.student import Student
from app.models.attendance import AttendanceRecord, AttendanceInterval, ManualCorrection
from app.schemas.session import (
    ClassSessionCreate,
    ClassSessionResponse,
    SessionAttendanceSummary,
    AttendanceRecordResponse,
    AttendanceIntervalResponse,
    ManualCorrectionRequest
)
from app.services.report_service import report_service
from app.websockets.connection_manager import ws_manager

router = APIRouter(prefix="/class-sessions", tags=["Class Sessions"])

def _to_naive_utc(dt: datetime) -> datetime:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def _get_or_create_group(db: Session, group_name: str, course_code: str = "COURSE-101") -> Group:
    course = db.query(Course).filter_by(code=course_code).first()
    if not course:
        course = Course(code=course_code, name="Default Course")
        db.add(course)
        db.flush()

    group = db.query(Group).filter_by(name=group_name, course_id=course.id).first()
    if not group:
        group = Group(name=group_name, period="2026-2", course_id=course.id)
        db.add(group)
        db.flush()

    return group


@router.post("", response_model=ClassSessionResponse, status_code=status.HTTP_201_CREATED)
def start_class_session(req: ClassSessionCreate, db: Session = Depends(get_db)):
    """
    Starts a new class session for an academic group.
    Ensures only one active session exists per group and initializes ABSENT records for all enrolled students.
    """
    group = _get_or_create_group(db, req.group_name, req.course_code)

    # Check if an active session already exists for this group
    active_existing = db.query(ClassSession).filter_by(group_id=group.id, status="active").first()
    if active_existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An active class session (#{active_existing.id}) is already running for group '{group.name}'. Please end it first."
        )

    now = datetime.now(timezone.utc)
    new_session = ClassSession(
        group_id=group.id,
        started_at=now,
        status="active"
    )
    db.add(new_session)
    db.flush()

    # Pre-populate attendance records for all enrolled students
    enrollments = db.query(Enrollment).filter_by(group_id=group.id).all()
    for enr in enrollments:
        rec = AttendanceRecord(
            session_id=new_session.id,
            student_id=enr.student_id,
            status="ABSENT",
            source="vision"
        )
        db.add(rec)

    db.commit()
    db.refresh(new_session)

    return ClassSessionResponse(
        id=new_session.id,
        group_id=group.id,
        group_name=group.name,
        course_name=group.course.name if group.course else "Default Course",
        started_at=_ensure_utc(new_session.started_at),
        ended_at=_ensure_utc(new_session.ended_at),
        status=new_session.status,
        total_enrolled=len(enrollments),
        present_count=0
    )


@router.get("/active", response_model=Optional[ClassSessionResponse])
def get_active_session(group_name: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Queries the database for the currently active class session (optionally filtered by group).
    Returns None if no session is active.
    """
    query = db.query(ClassSession).filter_by(status="active")
    if group_name:
        group = db.query(Group).filter_by(name=group_name).first()
        if group:
            query = query.filter_by(group_id=group.id)
    session = query.order_by(ClassSession.started_at.desc()).first()
    if not session:
        return None

    enrolled_count = db.query(Enrollment).filter_by(group_id=session.group_id).count()
    present_count = db.query(AttendanceRecord).filter_by(session_id=session.id, status="PRESENT").count()

    return ClassSessionResponse(
        id=session.id,
        group_id=session.group_id,
        group_name=session.group.name if session.group else (group_name or "Group A"),
        course_name=session.group.course.name if session.group and session.group.course else "Default Course",
        started_at=_ensure_utc(session.started_at),
        ended_at=_ensure_utc(session.ended_at),
        status=session.status,
        total_enrolled=enrolled_count,
        present_count=present_count
    )


@router.get("/{session_id}", response_model=ClassSessionResponse)
def get_class_session(session_id: int, db: Session = Depends(get_db)):
    """Fetches session metadata and active status."""
    session = db.query(ClassSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Class session not found.")

    enrolled_count = db.query(Enrollment).filter_by(group_id=session.group_id).count()
    present_count = db.query(AttendanceRecord).filter_by(session_id=session.id, status="PRESENT").count()

    return ClassSessionResponse(
        id=session.id,
        group_id=session.group_id,
        group_name=session.group.name if session.group else "Group A",
        course_name=session.group.course.name if session.group and session.group.course else "Default Course",
        started_at=_ensure_utc(session.started_at),
        ended_at=_ensure_utc(session.ended_at),
        status=session.status,
        total_enrolled=enrolled_count,
        present_count=present_count
    )


@router.post("/{session_id}/end", response_model=SessionAttendanceSummary)
def end_class_session(session_id: int, db: Session = Depends(get_db)):
    """
    Concludes a class session, closes any open presence intervals,
    locks in final attendance percentages, and generates an auditable CSV summary in outputs/.
    """
    session = db.query(ClassSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Class session not found.")

    if session.status == "ended":
        return get_session_attendance(session_id, db)

    now = datetime.now(timezone.utc)
    session.ended_at = now
    session.status = "ended"

    # Close any open intervals across all records for this session
    records = db.query(AttendanceRecord).filter_by(session_id=session.id).all()
    total_duration = max(1, int((_to_naive_utc(now) - _to_naive_utc(session.started_at)).total_seconds()))

    for rec in records:
        open_interval = db.query(AttendanceInterval).filter(
            AttendanceInterval.attendance_record_id == rec.id,
            AttendanceInterval.ended_at == None
        ).first()

        if open_interval:
            open_interval.ended_at = now
            open_interval.close_reason = "session_ended"

        db.flush()
        all_intervals = db.query(AttendanceInterval).filter_by(attendance_record_id=rec.id).all()
        rec.total_seconds = sum(i.duration_seconds for i in all_intervals)
        rec.percentage = round(min(100.0, (rec.total_seconds / total_duration) * 100), 1)

    db.commit()

    # Generate CSV Report in outputs/
    summary_data = get_session_attendance(session_id, db)
    csv_file_path = report_service.generate_session_csv(
        session=session,
        records=records,
        summary_stats={
            "duration_seconds": total_duration,
            "total_enrolled": summary_data.total_enrolled,
            "present_count": summary_data.present_count,
            "absent_count": summary_data.absent_count,
            "average_percentage": summary_data.average_percentage
        }
    )

    summary_data.csv_filename = csv_file_path.name
    summary_data.csv_file_path = str(csv_file_path)
    summary_data.csv_download_url = f"/api/class-sessions/{session.id}/export-csv"

    # Broadcast session ended event via WebSocket
    ws_manager.broadcast_sync(session.id, {
        "type": "session_ended",
        "occurred_at": now.isoformat(),
        "data": {
            "session_id": session.id,
            "status": "ended",
            "duration_seconds": total_duration,
            "csv_filename": csv_file_path.name,
            "csv_download_url": summary_data.csv_download_url
        }
    })

    return summary_data


@router.get("/{session_id}/export-csv")
def export_session_csv(session_id: int, db: Session = Depends(get_db)):
    """
    Exports and downloads the CSV report for a given class session.
    """
    session = db.query(ClassSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Class session not found.")

    outputs_dir = settings.ROOT_DIR / "outputs"
    matched_files = sorted(outputs_dir.glob(f"attendance_session_{session.id}_*.csv"), reverse=True)

    if matched_files:
        target_path = matched_files[0]
    else:
        # Generate on demand if not existing
        records = db.query(AttendanceRecord).filter_by(session_id=session.id).all()
        summary_data = get_session_attendance(session_id, db)
        target_path = report_service.generate_session_csv(
            session=session,
            records=records,
            summary_stats={
                "duration_seconds": summary_data.duration_seconds,
                "total_enrolled": summary_data.total_enrolled,
                "present_count": summary_data.present_count,
                "absent_count": summary_data.absent_count,
                "average_percentage": summary_data.average_percentage
            }
        )

    return FileResponse(
        path=str(target_path),
        filename=target_path.name,
        media_type="text/csv"
    )


@router.get("/{session_id}/attendance", response_model=SessionAttendanceSummary)
def get_session_attendance(session_id: int, db: Session = Depends(get_db)):
    """
    Returns full attendance metrics, intervals, and records for a class session.
    """
    session = db.query(ClassSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Class session not found.")

    now = datetime.now(timezone.utc)
    end_reference = session.ended_at or now
    duration_secs = max(1, int((_to_naive_utc(end_reference) - _to_naive_utc(session.started_at)).total_seconds()))

    records = db.query(AttendanceRecord).filter_by(session_id=session.id).all()

    record_responses = []
    present_count = 0
    percentages = []

    for r in records:
        if r.status == "PRESENT":
            present_count += 1

        intervals = db.query(AttendanceInterval).filter_by(attendance_record_id=r.id).all()
        interval_schemas = []
        computed_seconds = 0

        for i in intervals:
            duration = i.duration_seconds
            computed_seconds += duration
            interval_schemas.append(
                AttendanceIntervalResponse(
                    id=i.id,
                    started_at=_ensure_utc(i.started_at),
                    ended_at=_ensure_utc(i.ended_at),
                    duration_seconds=duration,
                    close_reason=i.close_reason
                )
            )

        pct = round(min(100.0, (computed_seconds / duration_secs) * 100), 1)
        percentages.append(pct)

        record_responses.append(
            AttendanceRecordResponse(
                id=r.id,
                student_id=r.student_id,
                student_name=r.student.name if r.student else "Unknown",
                student_number=r.student.student_number if r.student else "N/A",
                status=r.status,
                first_seen_at=_ensure_utc(r.first_seen_at),
                last_seen_at=_ensure_utc(r.last_seen_at),
                total_seconds=computed_seconds,
                percentage=pct,
                source=r.source,
                intervals=interval_schemas
            )
        )

    avg_pct = round(sum(percentages) / len(percentages), 1) if percentages else 0.0

    # Look for existing generated CSV in outputs/
    outputs_dir = settings.ROOT_DIR / "outputs"
    matched_files = sorted(outputs_dir.glob(f"attendance_session_{session.id}_*.csv"), reverse=True)
    csv_fn = matched_files[0].name if matched_files else None
    csv_fp = str(matched_files[0]) if matched_files else None
    csv_dl = f"/api/class-sessions/{session.id}/export-csv" if matched_files else None

    return SessionAttendanceSummary(
        session_id=session.id,
        status=session.status,
        started_at=_ensure_utc(session.started_at),
        ended_at=_ensure_utc(session.ended_at),
        duration_seconds=duration_secs,
        total_enrolled=len(records),
        present_count=present_count,
        absent_count=len(records) - present_count,
        average_percentage=avg_pct,
        records=record_responses,
        csv_filename=csv_fn,
        csv_file_path=csv_fp,
        csv_download_url=csv_dl
    )


@router.patch("/{session_id}/attendance/{record_id}", response_model=AttendanceRecordResponse)
def manual_attendance_correction(
    session_id: int,
    record_id: int,
    req: ManualCorrectionRequest,
    db: Session = Depends(get_db)
):
    """
    Allows teacher manual override of an attendance status with auditable justification.
    Broadcasts the change via WebSocket to all connected teacher screens.
    """
    record = db.query(AttendanceRecord).filter_by(id=record_id, session_id=session_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found.")

    prev_status = record.status

    # Record auditable correction
    correction = ManualCorrection(
        record_id=record.id,
        before_status=prev_status,
        after_status=req.new_status,
        reason=req.reason,
        created_at=datetime.now(timezone.utc)
    )
    db.add(correction)

    record.status = req.new_status
    record.source = "manual"
    db.commit()
    db.refresh(record)

    now_utc_iso = datetime.now(timezone.utc).isoformat()

    # Broadcast correction via WebSocket
    ws_manager.broadcast_sync(session_id, {
        "type": "attendance_update",
        "occurred_at": now_utc_iso,
        "data": {
            "record_id": record.id,
            "student_id": record.student_id,
            "name": record.student.name if record.student else "Unknown",
            "student_number": record.student.student_number if record.student else "N/A",
            "status": record.status,
            "first_seen_at": _ensure_utc(record.first_seen_at).isoformat() if record.first_seen_at else None,
            "last_seen_at": _ensure_utc(record.last_seen_at).isoformat() if record.last_seen_at else None,
            "total_seconds": record.total_seconds,
            "percentage": record.percentage,
            "source": "manual"
        }
    })

    intervals = db.query(AttendanceInterval).filter_by(attendance_record_id=record.id).all()
    return AttendanceRecordResponse(
        id=record.id,
        student_id=record.student_id,
        student_name=record.student.name if record.student else "Unknown",
        student_number=record.student.student_number if record.student else "N/A",
        status=record.status,
        first_seen_at=_ensure_utc(record.first_seen_at),
        last_seen_at=_ensure_utc(record.last_seen_at),
        total_seconds=record.total_seconds,
        percentage=record.percentage,
        source=record.source,
        intervals=[
            AttendanceIntervalResponse(
                id=i.id,
                started_at=_ensure_utc(i.started_at),
                ended_at=_ensure_utc(i.ended_at),
                duration_seconds=i.duration_seconds,
                close_reason=i.close_reason
            ) for i in intervals
        ]
    )
