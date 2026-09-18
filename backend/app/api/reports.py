import io
from datetime import datetime, timezone
from typing import Optional, List, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.session import ClassSession
from app.models.academic import Group
from app.models.attendance import AttendanceRecord
from app.schemas.reports import (
    AttendanceReport,
    StudentRiskSummary,
    DayOfWeekStat,
    SessionPoint,
)

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])

RECENT_N = 3  # how many of the most recent sessions count as "recent" for trend detection
TREND_THRESHOLD = 5.0  # percentage-point delta to call a trend "up"/"down" instead of "flat"


def _weekday_name(dt: datetime) -> str:
    return dt.strftime("%A")


def _risk_level(overall_pct: float, trend_direction: str) -> str:
    if overall_pct >= 85:
        level = "low"
    elif overall_pct >= 60:
        level = "moderate"
    else:
        level = "high"

    # A declining trend bumps the risk up one notch — this is still purely
    # attendance-based, not a real academic-performance prediction.
    if trend_direction == "down":
        if level == "low":
            level = "moderate"
        elif level == "moderate":
            level = "high"
    return level


def _build_report(db: Session, group_name: Optional[str]) -> AttendanceReport:
    query = db.query(ClassSession).filter_by(status="ended")

    group = None
    if group_name:
        group = db.query(Group).filter_by(name=group_name).first()
        if not group:
            raise HTTPException(status_code=404, detail=f"Group '{group_name}' not found.")
        query = query.filter_by(group_id=group.id)

    sessions = query.order_by(ClassSession.started_at.asc()).all()

    if not sessions:
        return AttendanceReport(
            group_name=group_name,
            total_sessions=0,
            total_students=0,
            overall_average_percentage=0.0,
            day_of_week=[],
            trend=[],
            students=[],
        )

    # session_id -> list of records, and per-student ordered history
    student_history: Dict[int, List[float]] = {}
    student_present_count: Dict[int, int] = {}
    student_info: Dict[int, Dict[str, str]] = {}

    trend_points: List[SessionPoint] = []
    weekday_buckets: Dict[str, List[float]] = {}
    all_session_averages: List[float] = []

    for sess in sessions:
        records = db.query(AttendanceRecord).filter_by(session_id=sess.id).all()
        if not records:
            continue

        session_pct_values = [r.percentage for r in records]
        session_avg = round(sum(session_pct_values) / len(session_pct_values), 1)
        all_session_averages.append(session_avg)

        weekday = _weekday_name(sess.started_at)
        weekday_buckets.setdefault(weekday, []).append(session_avg)

        trend_points.append(SessionPoint(
            session_id=sess.id,
            started_at=sess.started_at.isoformat(),
            weekday=weekday,
            average_percentage=session_avg,
        ))

        for r in records:
            student_history.setdefault(r.student_id, []).append(r.percentage)
            if r.status == "PRESENT":
                student_present_count[r.student_id] = student_present_count.get(r.student_id, 0) + 1
            if r.student_id not in student_info and r.student:
                student_info[r.student_id] = {
                    "name": r.student.name,
                    "number": r.student.student_number,
                }

    day_of_week_stats = [
        DayOfWeekStat(
            weekday=day,
            average_percentage=round(sum(vals) / len(vals), 1),
            sessions_count=len(vals),
        )
        for day, vals in weekday_buckets.items()
    ]
    # Sort Monday -> Sunday rather than alphabetically
    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_of_week_stats.sort(key=lambda d: weekday_order.index(d.weekday))

    students: List[StudentRiskSummary] = []
    for student_id, history in student_history.items():
        info = student_info.get(student_id, {"name": "Unknown", "number": "N/A"})
        overall_pct = round(sum(history) / len(history), 1)
        recent_slice = history[-RECENT_N:]
        recent_pct = round(sum(recent_slice) / len(recent_slice), 1)
        delta = round(recent_pct - overall_pct, 1)

        if delta > TREND_THRESHOLD:
            direction = "up"
        elif delta < -TREND_THRESHOLD:
            direction = "down"
        else:
            direction = "flat"

        students.append(StudentRiskSummary(
            student_id=student_id,
            student_name=info["name"],
            student_number=info["number"],
            total_sessions=len(history),
            sessions_present=student_present_count.get(student_id, 0),
            overall_percentage=overall_pct,
            recent_percentage=recent_pct,
            trend_direction=direction,
            trend_delta=delta,
            risk_level=_risk_level(overall_pct, direction),
            history=history,
        ))

    # Highest risk / lowest attendance first, so the teacher sees who needs attention
    risk_order = {"high": 0, "moderate": 1, "low": 2}
    students.sort(key=lambda s: (risk_order[s.risk_level], s.overall_percentage))

    overall_avg = round(sum(all_session_averages) / len(all_session_averages), 1) if all_session_averages else 0.0

    return AttendanceReport(
        group_name=group_name,
        total_sessions=len(sessions),
        total_students=len(students),
        overall_average_percentage=overall_avg,
        day_of_week=day_of_week_stats,
        trend=trend_points,
        students=students,
    )


@router.get("/summary", response_model=AttendanceReport)
def get_attendance_report(group_name: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Returns an attendance analytics report: per-student risk summary (heuristic,
    based only on attendance history), day-of-week patterns, and the overall
    trend across ended sessions. Optionally filtered by group_name.
    """
    return _build_report(db, group_name)


@router.get("/export")
def export_attendance_report(group_name: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Exports the same report as an .xlsx file with two sheets:
    'Students' (per-student risk summary) and 'Day of Week' (attendance patterns).
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="openpyxl is not installed. Add 'openpyxl' to backend/requirements.txt and reinstall."
        )

    report = _build_report(db, group_name)

    wb = Workbook()
    ws_students = wb.active
    ws_students.title = "Students"
    header_font = Font(bold=True)

    headers = [
        "Student", "Student #", "Sessions Attended", "Total Sessions",
        "Overall %", "Recent %", "Trend", "Risk Level"
    ]
    ws_students.append(headers)
    for cell in ws_students[1]:
        cell.font = header_font

    for s in report.students:
        ws_students.append([
            s.student_name, s.student_number, s.sessions_present, s.total_sessions,
            s.overall_percentage, s.recent_percentage, s.trend_direction, s.risk_level
        ])

    ws_days = wb.create_sheet("Day of Week")
    ws_days.append(["Weekday", "Average Attendance %", "Sessions Count"])
    for cell in ws_days[1]:
        cell.font = header_font
    for d in report.day_of_week:
        ws_days.append([d.weekday, d.average_percentage, d.sessions_count])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"attendance_report_{group_name or 'all_groups'}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
