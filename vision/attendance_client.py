import time
import queue
import threading
from typing import Optional, Dict, Any
import requests

class AttendanceClient:
    """
    Non-blocking HTTP client for the Vision Service to report real-time tracking events
    to the FastAPI backend without slowing down video loop FPS.
    """
    def __init__(self, backend_url: str = "http://localhost:8000", session_id: Optional[int] = None):
        self.backend_url = backend_url.rstrip("/")
        self.session_id = session_id
        self._event_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()

    def check_health(self) -> bool:
        """Verifies backend connectivity."""
        try:
            r = requests.get(f"{self.backend_url}/health", timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    def fetch_active_session(self, group_name: str = "Group A") -> Optional[int]:
        """
        Polls backend for currently active class session for a given group.
        Updates self.session_id dynamically.
        """
        try:
            url = f"{self.backend_url}/api/class-sessions/active"
            r = requests.get(url, params={"group_name": group_name}, timeout=2.0)
            if r.status_code == 200:
                data = r.json()
                if data and "id" in data and data.get("status") == "active":
                    if self.session_id != data["id"]:
                        print(f"\n[AttendanceClient] Linked to active Class Session #{data['id']} ({group_name})")
                    self.session_id = data["id"]
                    return self.session_id
            self.session_id = None
            return None
        except Exception:
            return None

    def get_session_info(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Fetches metadata for a given class session."""
        try:
            r = requests.get(f"{self.backend_url}/api/class-sessions/{session_id}", timeout=3.0)
            if r.status_code == 200:
                return r.json()
            return None
        except Exception as e:
            print(f"[AttendanceClient] Error fetching session #{session_id}: {e}")
            return None

    def start_session(self, group_name: str = "Group A", course_code: str = "COURSE-101") -> Optional[int]:
        """Requests backend to initiate a new class session for the group."""
        try:
            payload = {"group_name": group_name, "course_code": course_code}
            r = requests.post(f"{self.backend_url}/api/class-sessions", json=payload, timeout=5.0)
            if r.status_code in (200, 201):
                data = r.json()
                self.session_id = data["id"]
                print(f"[AttendanceClient] Started class session #{self.session_id} for '{group_name}'")
                return self.session_id
            elif r.status_code == 409:
                return self.fetch_active_session(group_name=group_name)
            else:
                print(f"[AttendanceClient] Failed to start session: {r.text}")
                return None
        except Exception as e:
            print(f"[AttendanceClient] Connection error starting session: {e}")
            return None

    def send_event(self, event: Dict[str, Any]):
        """
        Enqueues an event for asynchronous non-blocking transmission to the backend.
        """
        if not self.session_id and "class_session_id" not in event:
            return

        payload = {**event}
        if "class_session_id" not in payload:
            payload["class_session_id"] = self.session_id

        self._event_queue.put(payload)

    def _worker(self):
        """Background worker thread that posts events to the FastAPI backend."""
        endpoint = f"{self.backend_url}/api/internal/vision/events"
        while not self._stop_event.is_set():
            try:
                event_data = self._event_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                r = requests.post(endpoint, json=event_data, timeout=3.0)
                if r.status_code != 200:
                    print(f"[AttendanceClient] Warning: Backend returned HTTP {r.status_code}: {r.text}")
            except Exception as e:
                print(f"[AttendanceClient] Warning: Could not deliver event {event_data.get('event_type')}: {e}")
            finally:
                self._event_queue.task_done()

    def close(self):
        """Waits for pending events in queue and terminates background worker."""
        self._event_queue.join()
        self._stop_event.set()
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
