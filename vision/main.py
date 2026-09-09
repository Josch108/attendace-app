#!/usr/bin/env python3
"""
Main Computer Vision Pipeline for Smart Attendance:
OpenCV (Capture) -> YOLOv8 (Person Detection) -> ByteTrack (Temporal Tracking) -> InsightFace (Recognition) -> AttendanceManager -> AttendanceClient (FastAPI Backend)

Features:
- Standby mode until instructor starts class on dashboard
- Dynamic hot-reloading of new student face enrollments without restarting
- Dynamic camera source switching from Dashboard (Built-in vs. External USB Camera)
- Real-time periodic presence sync so dashboard is always up to date
- Clean shutdown on Ctrl+C without tracebacks
"""
import sys
import argparse
from pathlib import Path
from typing import Union
import cv2
import numpy as np

# Add project directories to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from vision.camera import CameraStream
from vision.detector_tracker import PersonTracker
from vision.face_recognizer import FaceRecognizer
from vision.attendance_manager import AttendanceManager
from vision.attendance_client import AttendanceClient

# BGR colors for visual overlay
COLOR_GREEN = (0, 200, 0)      # Present
COLOR_YELLOW = (0, 215, 255)   # Temporarily Missing
COLOR_RED = (0, 0, 220)        # Left / Absent
COLOR_GRAY = (128, 128, 128)   # Unknown / Unidentified
COLOR_BLUE = (255, 120, 0)     # Active track bounding box

def draw_overlay(frame: np.ndarray, tracked_people, attendance_manager: AttendanceManager, fps: float, session_id: int = None, camera_source: Union[int, str] = 0):
    """
    Renders bounding boxes, student badges, track IDs, active camera indicator, and top status bar.
    """
    h, w = frame.shape[:2]

    # 1. Semi-transparent top bar for real-time stats
    overlay = frame.copy()
    top_bar_color = (20, 20, 20) if session_id else (10, 30, 60)
    cv2.rectangle(overlay, (0, 0), (w, 52), top_bar_color, -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    present_count = sum(1 for s in attendance_manager.students_state.values() if s.status == "PRESENT")
    cam_label = f"Cam {camera_source}" if str(camera_source).isdigit() else f"Cam: {camera_source}"
    if session_id:
        status_text = f"SESSION #{session_id} [ACTIVE] | {cam_label} | FPS: {fps:.1f} | In Frame: {len(tracked_people)} | Present: {present_count}"
        color_text = (255, 255, 255)
    else:
        status_text = f"STANDBY: Waiting for instructor | {cam_label} | FPS: {fps:.1f}"
        color_text = (0, 220, 255)

    cv2.putText(frame, status_text, (15, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.58, color_text, 2)

    # 2. Draw person information and tracking badge
    for person in tracked_people:
        x1, y1, x2, y2 = person.bbox
        tid = person.track_id

        # Check if track is associated with an enrolled student
        student_id = attendance_manager.track_to_student.get(tid)
        if student_id and student_id in attendance_manager.students_state:
            state = attendance_manager.students_state[student_id]
            name = state.name
            status = state.status if session_id else "IDENTIFIED"
            color = COLOR_GREEN if status in ("PRESENT", "IDENTIFIED") else COLOR_YELLOW
            label = f"#{tid} {name} [{status}]"
        else:
            color = COLOR_BLUE
            label = f"Track #{tid} (Identifying...)"

        # Bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # Badge above bounding box
        label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        lbl_w, lbl_h = label_size
        cv2.rectangle(frame, (x1, max(0, y1 - lbl_h - 10)), (x1 + lbl_w + 10, y1), color, -1)
        cv2.putText(frame, label, (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

def main():
    parser = argparse.ArgumentParser(description="Computer Vision Attendance Pipeline.")
    parser.add_argument("--source", default=0, help="Webcam index (e.g. 0 or 1) or video stream URL")
    parser.add_argument("--conf", type=float, default=0.40, help="YOLO person detection confidence threshold")
    parser.add_argument("--threshold", type=float, default=0.50, help="Cosine facial similarity match threshold")
    parser.add_argument("--timeout", type=float, default=15.0, help="Absence timeout in seconds")
    parser.add_argument("--recheck", type=int, default=5, help="Frame interval to re-evaluate face on active tracks")
    parser.add_argument("--no-gui", action="store_true", help="Run in headless console mode")
    parser.add_argument("--output", type=str, default=None, help="File path to save output annotated video")

    # Backend integration parameters
    parser.add_argument("--session-id", type=int, default=None, help="Link to explicit Class Session ID")
    parser.add_argument("--backend-url", type=str, default="http://localhost:8000", help="FastAPI backend URL")
    parser.add_argument("--auto-session", action="store_true", help="Force auto-create session on start")
    parser.add_argument("--group", type=str, default="Group A", help="Academic group name to monitor")

    args = parser.parse_args()

    print("=== Starting Computer Vision Pipeline ===")

    # Initialize backend communication client
    client = AttendanceClient(backend_url=args.backend_url, session_id=args.session_id)
    if args.auto_session and not client.session_id:
        print("[Main] Requesting backend to auto-start session...")
        client.start_session(group_name=args.group)

    # Resolve initial camera source: prefer backend active camera if set
    initial_source = args.source
    if str(args.source) in ("0", ""):
        active_backend_cam = client.fetch_active_camera()
        if active_backend_cam is not None:
            initial_source = active_backend_cam
            print(f"[Main] Initializing with active camera from backend: {initial_source}")

    camera = CameraStream(source=initial_source).start()

    def on_attendance_event(evt: dict):
        """Callback for terminal logging and backend event dispatch."""
        etype = evt["event_type"]
        payload = evt.get("payload", {})
        name = payload.get("name", "Unknown")
        is_hb = payload.get("total_seconds") is not None
        # Tag camera ID on event
        evt["camera_id"] = str(camera.source)
        # Only log major events or every few heartbeats to keep console readable
        if not is_hb:
            print(f"[{evt['occurred_at'][11:19]}] >>> EVENT: {etype} | Student: {name} (Track: {evt.get('track_id')}, Cam: {camera.source})")
        if client.session_id:
            client.send_event(evt)

    tracker = PersonTracker(conf_thresh=args.conf)
    recognizer = FaceRecognizer(match_threshold=args.threshold)
    attendance = AttendanceManager(
        absence_timeout=args.timeout,
        on_event=on_attendance_event,
        student_name_lookup=recognizer.get_student_name
    )

    # Initial check on startup if a session is already active in the backend
    if args.session_id is None and not args.auto_session:
        active_id = client.fetch_active_session(group_name=args.group)
        if active_id:
            print(f"[Main] Synced with active Class Session #{active_id} on startup!")

    video_writer = None
    if args.output:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        video_writer = cv2.VideoWriter(args.output, fourcc, 20.0, (camera.width, camera.height))
        print(f"[Main] Recording annotated video to: {args.output}")

    frame_count = 0
    prev_session_state = client.session_id
    print("\n[INFO] Press 'q' in the video window or Ctrl+C in terminal to quit.\n")

    try:
        while True:
            ret, frame = camera.read()
            if not ret:
                print(f"[Main] Video stream ended or camera {camera.source} disconnected. Retrying in 1s...")
                import time
                time.sleep(1.0)
                continue

            frame_count += 1

            # Check for newly enrolled face embeddings dynamically every ~1 second (30 frames)
            if frame_count % 30 == 0:
                recognizer.reload_if_updated()

                # Dynamic Camera Switching from Dashboard
                active_backend_cam = client.fetch_active_camera()
                if active_backend_cam is not None and str(active_backend_cam) != str(camera.source):
                    print(f"\n[Main] >>> Dashboard selected camera '{active_backend_cam}' (current: '{camera.source}'). Switching...")
                    switched = camera.switch_source(active_backend_cam)
                    if switched:
                        # Re-initialize tracker to adapt to the new viewpoint cleanly
                        tracker = PersonTracker(conf_thresh=args.conf)
                        print(f"[Main] Now tracking on camera '{active_backend_cam}'.")

            # Sync with backend active session if session-id was not hardcoded
            if args.session_id is None and not args.auto_session:
                if frame_count % 30 == 0:  # Check active session every ~1 second
                    active_id = client.fetch_active_session(group_name=args.group)
                    if active_id != prev_session_state:
                        if active_id:
                            print(f"\n[Main] >>> Active Class Session #{active_id} linked! Attendance tracking is ON.")
                            attendance.reset_session()
                        else:
                            print(f"\n[Main] >>> Class session ended. Vision returned to STANDBY mode.")
                            attendance.reset_session()
                        prev_session_state = active_id

            # 1. Person detection and temporal tracking with YOLO + ByteTrack
            tracked_people = tracker.update(frame)
            active_track_ids = [p.track_id for p in tracked_people]

            # 2. Selective facial recognition
            for person in tracked_people:
                tid = person.track_id
                
                # Run recognition only if track has unconfirmed identity or periodically
                should_check_face = (
                    tid not in attendance.track_to_student or 
                    (frame_count % args.recheck == 0)
                )

                if should_check_face:
                    # Crop upper-body/head region for speed and accuracy
                    head_crop = tracker.crop_head_region(frame, person.bbox)
                    student_id, student_name, confidence = recognizer.recognize_crop(head_crop)

                    if student_id is not None:
                        attendance.register_observation(
                            track_id=tid,
                            student_id=student_id,
                            student_name=student_name,
                            confidence=confidence,
                            bbox=person.bbox
                        )
                else:
                    # Track is already associated: record continuity
                    assigned_id = attendance.track_to_student.get(tid)
                    assigned_name = recognizer.get_student_name(assigned_id) if assigned_id else None
                    attendance.register_observation(
                        track_id=tid,
                        student_id=assigned_id,
                        student_name=assigned_name,
                        confidence=1.0,
                        bbox=person.bbox
                    )

            # 3. Evaluate absence timeouts (only when a session is active)
            if client.session_id:
                attendance.check_timeouts(active_track_ids)

            # 4. Render visual overlay
            draw_overlay(frame, tracked_people, attendance, camera.fps, session_id=client.session_id, camera_source=camera.source)

            if video_writer:
                video_writer.write(frame)

            # 5. Show GUI window if not in headless mode
            if not args.no_gui:
                cv2.imshow("Smart Attendance System - Tracking & Recognition", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

    except KeyboardInterrupt:
        print("\n[Main] Stopped by user (Ctrl+C).")
    finally:
        camera.release()
        if video_writer:
            video_writer.release()
        cv2.destroyAllWindows()
        client.close()

        print("\n=== Session Attendance Summary ===")
        summary = attendance.get_summary()
        if not summary:
            print("No student presences were recorded during the session.")
        else:
            print(f"{'ID':<5} | {'NAME':<25} | {'STATUS':<15} | {'TOTAL SECONDS':<15}")
            print("-" * 65)
            for s in summary:
                print(f"{s['student_id']:<5} | {s['name']:<25} | {s['status']:<15} | {s['total_seconds']:<15}")
            print("-" * 65)

if __name__ == "__main__":
    main()
