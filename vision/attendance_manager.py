import time
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Callable
from collections import defaultdict

@dataclass
class PresenceInterval:
    started_at: float
    ended_at: Optional[float] = None
    close_reason: Optional[str] = None

    @property
    def duration(self) -> float:
        end = self.ended_at or time.time()
        return max(0.0, end - self.started_at)


@dataclass
class StudentAttendanceState:
    student_id: int
    name: str
    status: str = "ABSENT"  # ABSENT, PRESENT, TEMPORARILY_MISSING, LEFT
    first_seen: Optional[float] = None
    last_seen: Optional[float] = None
    current_track_id: Optional[int] = None
    intervals: List[PresenceInterval] = field(default_factory=list)

    @property
    def total_presence_seconds(self) -> int:
        return int(sum(i.duration for i in self.intervals))


class AttendanceManager:
    """
    Manages presence intervals, state machine transitions, and absence timeouts
    from raw tracker observations.
    """
    def __init__(
        self,
        absence_timeout: float = 45.0,
        confirmation_count: int = 3,
        on_event: Optional[Callable[[dict], None]] = None
    ):
        self.absence_timeout = absence_timeout
        self.confirmation_count = confirmation_count
        self.on_event = on_event or (lambda evt: None)

        # Mapping: track_id -> student_id
        self.track_to_student: Dict[int, int] = {}
        # Consecutive confirmation votes: Dict[track_id, Dict[student_id, count]]
        self.track_identities_votes = defaultdict(lambda: defaultdict(int))
        # Attendance state: student_id -> StudentAttendanceState
        self.students_state: Dict[int, StudentAttendanceState] = {}
        # Event history
        self.events: List[dict] = []

    def _emit(self, event_type: str, student_id: Optional[int], track_id: Optional[int], payload: dict = None):
        evt = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "student_id": student_id,
            "track_id": track_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload or {}
        }
        self.events.append(evt)
        self.on_event(evt)

    def register_observation(
        self,
        track_id: int,
        student_id: Optional[int],
        student_name: Optional[str],
        confidence: float,
        bbox: list
    ):
        now = time.time()

        # If track is already associated with a student, update their presence
        if track_id in self.track_to_student:
            assigned_student_id = self.track_to_student[track_id]
            self._update_student_seen(assigned_student_id, track_id, now)
            return

        # If unassigned but recognized with sufficient confidence
        if student_id is not None:
            self.track_identities_votes[track_id][student_id] += 1
            votes = self.track_identities_votes[track_id][student_id]

            # Require N consecutive confirmations to solidify association
            if votes >= self.confirmation_count:
                self.track_to_student[track_id] = student_id
                print(f"[AttendanceManager] Association confirmed: track #{track_id} -> {student_name} (ID: {student_id})")
                self._emit("STUDENT_RECOGNIZED", student_id, track_id, {
                    "name": student_name,
                    "confidence": confidence,
                    "bbox": bbox
                })

                if student_id not in self.students_state:
                    self.students_state[student_id] = StudentAttendanceState(
                        student_id=student_id,
                        name=student_name
                    )

                self._update_student_seen(student_id, track_id, now)
        else:
            # Unidentified or face not clearly visible yet
            pass

    def _update_student_seen(self, student_id: int, track_id: int, timestamp: float):
        state = self.students_state[student_id]
        state.current_track_id = track_id

        if state.first_seen is None:
            state.first_seen = timestamp

        prev_status = state.status
        state.last_seen = timestamp

        if prev_status in ("ABSENT", "LEFT"):
            # Start new presence interval
            state.intervals.append(PresenceInterval(started_at=timestamp))
            state.status = "PRESENT"
            event_type = "STUDENT_PRESENT" if prev_status == "ABSENT" else "STUDENT_RETURNED"
            self._emit(event_type, student_id, track_id, {
                "name": state.name,
                "first_seen": state.first_seen
            })
        elif prev_status == "TEMPORARILY_MISSING":
            # Returned before absence timeout: interval remains continuous
            state.status = "PRESENT"

    def check_timeouts(self, active_track_ids: List[int]):
        """
        Periodically checks if any previously observed student is no longer visible.
        Applies absence policy:
          - < absence_timeout: TEMPORARILY_MISSING (interval remains open)
          - >= absence_timeout: LEFT (interval is closed)
        """
        now = time.time()
        active_students = {self.track_to_student[tid] for tid in active_track_ids if tid in self.track_to_student}

        for student_id, state in self.students_state.items():
            if student_id not in active_students:
                if state.status == "PRESENT" and state.last_seen is not None:
                    elapsed = now - state.last_seen
                    if elapsed < self.absence_timeout:
                        state.status = "TEMPORARILY_MISSING"
                    else:
                        self._close_student_interval(state, now, reason="timeout")
                elif state.status == "TEMPORARILY_MISSING" and state.last_seen is not None:
                    elapsed = now - state.last_seen
                    if elapsed >= self.absence_timeout:
                        self._close_student_interval(state, now, reason="timeout")

    def _close_student_interval(self, state: StudentAttendanceState, timestamp: float, reason: str):
        state.status = "LEFT"
        # Close the last active interval
        if state.intervals and state.intervals[-1].ended_at is None:
            state.intervals[-1].ended_at = state.last_seen or timestamp
            state.intervals[-1].close_reason = reason

        self._emit("STUDENT_LEFT", state.student_id, state.current_track_id, {
            "name": state.name,
            "total_presence_seconds": state.total_presence_seconds,
            "reason": reason
        })

    def get_summary(self) -> List[dict]:
        """
        Returns current attendance summary table.
        """
        summary = []
        for s in self.students_state.values():
            summary.append({
                "student_id": s.student_id,
                "name": s.name,
                "status": s.status,
                "first_seen": s.first_seen,
                "last_seen": s.last_seen,
                "total_seconds": s.total_presence_seconds
            })
        return summary
