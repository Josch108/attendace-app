from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.session import ClassSession
from app.models.student import Student
from app.models.attendance import AttendanceRecord, AttendanceInterval, AttendanceEvent
from app.schemas.attendance import VisionEventIngest, VisionEventResponse
from app.websockets.connection_manager import ws_manager

router = APIRouter(prefix="/internal/vision", tags=["Vision Ingestion"])

def _to_naive_utc(dt: datetime) -> datetime:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

def _ensure_utc(dt: datetime) -> datetime:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

@router.post("/events", response_model=VisionEventResponse, status_code=status.HTTP_200_OK)
def ingest_vision_event(event: VisionEventIngest, db: Session = Depends(get_db)):
    """
    Idempotent internal ingestion endpoint for vision tracking events.
    Applies interval management, presence transitions, and WebSocket broadcasts.
    """
    # 1. Idempotency check: discard already received event_id
    existing_event = db.query(AttendanceEvent).filter_by(event_id=event.event_id).first()
    if existing_event:
        return VisionEventResponse(
            status="ok",
            message="Event already processed (idempotent duplicate).",
            event_id=event.event_id,
            processed=False
        )

    # 2. Verify target class session
    session = db.query(ClassSession).filter_by(id=event.class_session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Class session #{event.class_session_id} not found.")

    if session.status != "active":
        raise HTTPException(
            status_code=400,
            detail=f"Class session #{event.class_session_id} is '{session.status}', not accepting vision events."
        )

    occurred_at = event.observed_at or event.occurred_at or datetime.now(timezone.utc)
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)

    # 3. Persist audit event record
    audit_event = AttendanceEvent(
        event_id=event.event_id,
        session_id=session.id,
        student_id=event.student_id,
        track_id=str(event.track_id) if event.track_id is not None else None,
        camera_id=event.camera_id,
        event_type=event.event_type,
        occurred_at=occurred_at,
        payload={
            **(event.payload or {}),
            "confidence": event.confidence,
            "bbox": event.bbox,
            "model_version": event.model_version
        }
    )
    db.add(audit_event)

    student = None
    record = None

    # 4. If an identified student is linked, update their attendance record and intervals
    if event.student_id:
        student = db.query(Student).filter_by(id=event.student_id).first()
        if student:
            record = db.query(AttendanceRecord).filter_by(
                session_id=session.id,
                student_id=student.id
            ).first()

            if not record:
                record = AttendanceRecord(
                    session_id=session.id,
                    student_id=student.id,
                    status="ABSENT",
                    source="vision"
                )
                db.add(record)
                db.flush()

            # Handle event transitions
            if event.event_type in ("STUDENT_PRESENT", "STUDENT_RECOGNIZED", "STUDENT_RETURNED"):
                if not record.first_seen_at:
                    record.first_seen_at = occurred_at
                record.last_seen_at = occurred_at
                record.status = "PRESENT"

                # Check if there is an open interval
                open_interval = db.query(AttendanceInterval).filter(
                    AttendanceInterval.attendance_record_id == record.id,
                    AttendanceInterval.ended_at == None
                ).first()

                if not open_interval:
                    new_interval = AttendanceInterval(
                        attendance_record_id=record.id,
                        started_at=occurred_at
                    )
                    db.add(new_interval)

            elif event.event_type == "STUDENT_TEMPORARILY_MISSING":
                record.status = "TEMPORARILY_MISSING"

            elif event.event_type == "STUDENT_LEFT":
                record.status = "LEFT"
                open_interval = db.query(AttendanceInterval).filter(
                    AttendanceInterval.attendance_record_id == record.id,
                    AttendanceInterval.ended_at == None
                ).first()

                if open_interval:
                    open_interval.ended_at = occurred_at
                    open_interval.close_reason = (event.payload or {}).get("reason", "timeout")

            # Recalculate presence seconds and percentage
            db.flush()
            intervals = db.query(AttendanceInterval).filter_by(attendance_record_id=record.id).all()
            total_secs = 0
            for i in intervals:
                end_time = i.ended_at or occurred_at
                duration = int((_to_naive_utc(end_time) - _to_naive_utc(i.started_at)).total_seconds())
                total_secs += max(0, duration)
            record.total_seconds = total_secs

            session_elapsed = max(1, int((_to_naive_utc(occurred_at) - _to_naive_utc(session.started_at)).total_seconds()))
            record.percentage = round(min(100.0, (record.total_seconds / session_elapsed) * 100), 1)

    db.commit()

    # 5. Broadcast real-time updates via WebSocket
    student_display_name = student.name if student else (event.payload or {}).get("name", "Unknown")
    now_utc_iso = datetime.now(timezone.utc).isoformat()

    ws_manager.broadcast_sync(session.id, {
        "type": "event_log",
        "occurred_at": now_utc_iso,
        "data": {
            "event_type": event.event_type,
            "student_id": event.student_id,
            "student_name": student_display_name,
            "student_number": student.student_number if student else "N/A",
            "track_id": event.track_id,
            "confidence": event.confidence
        }
    })

    if record and student:
        ws_manager.broadcast_sync(session.id, {
            "type": "attendance_update",
            "occurred_at": now_utc_iso,
            "data": {
                "record_id": record.id,
                "student_id": student.id,
                "name": student.name,
                "student_number": student.student_number,
                "status": record.status,
                "first_seen_at": _ensure_utc(record.first_seen_at).isoformat() if record.first_seen_at else None,
                "last_seen_at": _ensure_utc(record.last_seen_at).isoformat() if record.last_seen_at else None,
                "total_seconds": record.total_seconds,
                "percentage": record.percentage
            }
        })

    return VisionEventResponse(
        status="ok",
        message=f"Event {event.event_type} successfully ingested and applied.",
        event_id=event.event_id,
        processed=True
    )
