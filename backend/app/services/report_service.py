import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from app.config import settings
from app.models.session import ClassSession
from app.models.attendance import AttendanceRecord

def _format_local_datetime(dt: datetime) -> str:
    """Converts a datetime (UTC or naive UTC) to the system's local time string."""
    if not dt:
        return "--"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local_dt = dt.astimezone()
    return local_dt.strftime("%Y-%m-%d %I:%M:%S %p")

def _format_duration(seconds: int) -> str:
    """Formats integer seconds into human-readable minutes and seconds."""
    mins = seconds // 60
    secs = seconds % 60
    if mins >= 60:
        hrs = mins // 60
        rem_mins = mins % 60
        return f"{hrs}h {rem_mins}m {secs}s"
    return f"{mins}m {secs}s"

class ReportService:
    """
    Generates structured, auditable attendance CSV reports upon session conclusion.
    Outputs are stored in the project's 'outputs/' directory.
    """
    def __init__(self, outputs_dir: Path = None):
        self.outputs_dir = outputs_dir or (settings.ROOT_DIR / "outputs")
        self.outputs_dir.mkdir(parents=True, exist_ok=True)

    def generate_session_csv(
        self,
        session: ClassSession,
        records: List[AttendanceRecord],
        summary_stats: Dict[str, Any]
    ) -> Path:
        """
        Builds a complete CSV report containing session summary metrics
        followed by per-student attendance details.
        """
        now = datetime.now()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        clean_group = (session.group.name if session.group else "Group").replace(" ", "_")
        filename = f"attendance_session_{session.id}_{clean_group}_{timestamp_str}.csv"
        file_path = self.outputs_dir / filename

        group_name = session.group.name if session.group else "N/A"
        course_name = session.group.course.name if (session.group and session.group.course) else "Default Course"
        course_code = session.group.course.code if (session.group and session.group.course) else "COURSE-101"

        started_str = _format_local_datetime(session.started_at)
        ended_str = _format_local_datetime(session.ended_at)
        duration_formatted = _format_duration(summary_stats.get("duration_seconds", 0))

        with open(file_path, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)

            # Section 1: Session Overview & Aggregate Metrics
            writer.writerow(["=== CLASS SESSION ATTENDANCE SUMMARY ==="])
            writer.writerow(["Session ID", session.id])
            writer.writerow(["Academic Group", group_name])
            writer.writerow(["Course", f"{course_name} ({course_code})"])
            writer.writerow(["Session Status", session.status])
            writer.writerow(["Class Started At", started_str])
            writer.writerow(["Class Ended At", ended_str])
            writer.writerow(["Total Class Duration", f"{duration_formatted} ({summary_stats.get('duration_seconds', 0)} seconds)"])
            writer.writerow(["Total Enrolled Students", summary_stats.get("total_enrolled", len(records))])
            writer.writerow(["Students Present", summary_stats.get("present_count", 0)])
            writer.writerow(["Students Absent / Left", summary_stats.get("absent_count", 0)])
            writer.writerow(["Average Cohort Attendance", f"{summary_stats.get('average_percentage', 0.0)}%"])
            writer.writerow(["Report Generated At", now.strftime("%Y-%m-%d %I:%M:%S %p")])
            writer.writerow([])  # Blank separator line

            # Section 2: Individual Student Attendance Table
            headers = [
                "Student ID (Matricula)",
                "Full Name",
                "Status",
                "First Seen",
                "Last Seen",
                "Time Present",
                "Total Seconds",
                "Class Attendance %",
                "Verification Source"
            ]
            writer.writerow(headers)

            for rec in records:
                student_num = rec.student.student_number if rec.student else "N/A"
                student_name = rec.student.name if rec.student else "Unknown"
                first_seen = _format_local_datetime(rec.first_seen_at)
                last_seen = _format_local_datetime(rec.last_seen_at)
                time_pres = _format_duration(rec.total_seconds)
                pct_str = f"{rec.percentage:.1f}%"

                writer.writerow([
                    student_num,
                    student_name,
                    rec.status,
                    first_seen,
                    last_seen,
                    time_pres,
                    rec.total_seconds,
                    pct_str,
                    rec.source or "vision"
                ])

        print(f"[ReportService] Attendance CSV generated successfully at: {file_path}")
        return file_path

report_service = ReportService()
