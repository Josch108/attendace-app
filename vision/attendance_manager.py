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
    last_heartbeat: float = 0.0

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
        absence_timeout: float = 15.0,
        confirmation_count: int = 3,
        on_event: Optional[Callable[[dict], None]] = None,
        student_name_lookup: Optional[Callable[[int], Optional[str]]] = None
    ):
        self.absence_timeout = absence_timeout
        self.confirmation_count = confirmation_count
        self.on_event = on_event or (lambda evt: None)
        self.student_name_lookup = student_name_lookup

        # Persistent mapping of student_id -> full name
        self.student_names: Dict[int, str] = {}
        # Mapping: track_id -> student_id
        self.track_to_student: Dict[int, int] = {}
        # Consecutive confirmation votes: Dict[track_id, Dict[student_id, count]]
        self.track_identities_votes = defaultdict(lambda: defaultdict(int))
        # Attendance state: student_id -> StudentAttendanceState
        self.students_state: Dict[int, StudentAttendanceState] = {}
        # Event history
        self.events: List[dict] = []

    def reset_session(self):
        """Resets attendance state when a new class session starts without losing name mappings."""
        self.students_state.clear()
        self.events.clear()
        print("[AttendanceManager] Attendance state synchronized for class session.")

    def _get_name(self, student_id: int) -> str:
        if student_id in self.student_names:
            return self.student_names[student_id]
        if self.student_name_lookup:
            looked_up = self.student_name_lookup(student_id)
            if looked_up:
                self.student_names[student_id] = looked_up
                return looked_up
        return f"Student #{student_id}"

    def _emit(self, event_type: str, student_id: Optional[int], track_id: Optional[int], payload: dict = None):
        now_iso = datetime.now(timezone.utc).isoformat()
        name = self._get_name(student_id) if student_id else "Unknown"
        evt_payload = {**(payload or {})}
        if student_id and "name" not in evt_payload:
            evt_payload["name"] = name

        evt = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "student_id": student_id,
            "track_id": str(track_id) if track_id is not None else None,
            "occurred_at": now_iso,
            "observed_at": now_iso,
            "payload": evt_payload
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

        if student_id and student_name:
            self.student_names[student_id] = student_name

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
                resolved_name = self._get_name(student_id)
                print(f"[AttendanceManager] Association confirmed: track #{track_id} -> {resolved_name} (ID: {student_id})")
                self._emit("STUDENT_RECOGNIZED", student_id, track_id, {
                    "name": resolved_name,
                    "confidence": confidence,
                    "bbox": bbox
                })

                if student_id not in self.students_state:
                    self.students_state[student_id] = StudentAttendanceState(
                        student_id=student_id,
                        name=resolved_name
                    )

                self._update_student_seen(student_id, track_id, now)

    def _update_student_seen(self, student_id: int, track_id: int, timestamp: float):
        if student_id not in self.students_state:
            real_name = self._get_name(student_id)
            self.students_state[student_id] = StudentAttendanceState(
                student_id=student_id,
                name=real_name
            )

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
            state.last_heartbeat = timestamp
            event_type = "STUDENT_PRESENT" if prev_status == "ABSENT" else "STUDENT_RETURNED"
            self._emit(event_type, student_id, track_id, {
                "name": state.name,
                "first_seen": state.first_seen
            })
        elif prev_status == "TEMPORARILY_MISSING":
            # Returned from brief absence: interval remains continuous
            state.status = "PRESENT"
            state.last_heartbeat = timestamp
            self._emit("STUDENT_RETURNED", student_id, track_id, {
                "name": state.name,
                "first_seen": state.first_seen
            })
        else:
            # Already PRESENT: Emit periodic presence heartbeat every 4 seconds
            if timestamp - state.last_heartbeat >= 4.0:
                state.last_heartbeat = timestamp
                self._emit("STUDENT_PRESENT", student_id, track_id, {
                    "name": state.name,
                    "first_seen": state.first_seen,
                    "total_seconds": state.total_presence_seconds
                })

    def check_timeouts(self, active_track_ids: List[int]):
        """
        Periodically checks if any previously observed student is no longer visible.
        Applies absence policy:
          - >= 2.5s missing: TEMPORARILY_MISSING (notifies backend and dashboard immediately)
          - >= absence_timeout: LEFT (closes interval and locks departure)
        """
        now = time.time()
        active_students = {self.track_to_student[tid] for tid in active_track_ids if tid in self.track_to_student}

        for student_id, state in self.students_state.items():
            if student_id not in active_students:
                if state.last_seen is not None:
                    elapsed = now - state.last_seen
                    if state.status == "PRESENT":
                        if elapsed >= 2.5:
                            state.status = "TEMPORARILY_MISSING"
                            self._emit("STUDENT_TEMPORARILY_MISSING", student_id, state.current_track_id, {
                                "name": state.name,
                                "elapsed_seconds": int(elapsed)
                            })
                    elif state.status == "TEMPORARILY_MISSING":
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
