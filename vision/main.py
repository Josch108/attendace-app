#!/usr/bin/env python3
"""
Main Computer Vision Pipeline for Smart Attendance:
OpenCV (Capture) -> YOLOv8 (Person Detection) -> ByteTrack (Temporal Tracking) -> InsightFace (Recognition) -> AttendanceManager
"""
import sys
import argparse
from pathlib import Path
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

# BGR colors for visual overlay
COLOR_GREEN = (0, 200, 0)      # Present
COLOR_YELLOW = (0, 215, 255)   # Temporarily Missing
COLOR_RED = (0, 0, 220)        # Left / Absent
COLOR_GRAY = (128, 128, 128)   # Unknown / Unidentified
COLOR_BLUE = (255, 120, 0)     # Active track bounding box

def draw_overlay(frame: np.ndarray, tracked_people, attendance_manager: AttendanceManager, fps: float):
    """
    Renders bounding boxes, student badges, track IDs, and top status bar.
    """
    h, w = frame.shape[:2]

    # 1. Semi-transparent top bar for real-time stats
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 50), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    present_count = sum(1 for s in attendance_manager.students_state.values() if s.status == "PRESENT")
    header_text = f"FPS: {fps:.1f} | People in Frame: {len(tracked_people)} | Students Present: {present_count}"
    cv2.putText(frame, header_text, (15, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # 2. Draw person information and tracking badge
    for person in tracked_people:
        x1, y1, x2, y2 = person.bbox
        tid = person.track_id

        # Check if track is associated with an enrolled student
        student_id = attendance_manager.track_to_student.get(tid)
        if student_id and student_id in attendance_manager.students_state:
            state = attendance_manager.students_state[student_id]
            name = state.name
            status = state.status
            color = COLOR_GREEN if status == "PRESENT" else COLOR_YELLOW
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

def on_attendance_event(evt: dict):
    """Callback for terminal logging of domain events."""
    etype = evt["event_type"]
    payload = evt.get("payload", {})
    name = payload.get("name", "Unknown")
    print(f"[{evt['occurred_at'][11:19]}] >>> EVENT: {etype} | Student: {name} (Track ID: {evt.get('track_id')})")

def main():
    parser = argparse.ArgumentParser(description="Computer Vision Attendance Pipeline.")
    parser.add_argument("--source", default=0, help="Webcam index (e.g. 0) or video file path (e.g. sample.mp4)")
    parser.add_argument("--conf", type=float, default=0.40, help="YOLO person detection confidence threshold")
    parser.add_argument("--threshold", type=float, default=0.50, help="Cosine facial similarity match threshold")
    parser.add_argument("--timeout", type=float, default=45.0, help="Absence timeout in seconds")
    parser.add_argument("--recheck", type=int, default=5, help="Frame interval to re-evaluate face on active tracks")
    parser.add_argument("--no-gui", action="store_true", help="Run in headless console mode")
    parser.add_argument("--output", type=str, default=None, help="File path to save output annotated video")

    args = parser.parse_args()

    print("=== Starting Computer Vision Pipeline ===")
    camera = CameraStream(source=args.source).start()
    tracker = PersonTracker(conf_thresh=args.conf)
    recognizer = FaceRecognizer(match_threshold=args.threshold)
    attendance = AttendanceManager(absence_timeout=args.timeout, on_event=on_attendance_event)

    video_writer = None
    if args.output:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        video_writer = cv2.VideoWriter(args.output, fourcc, 20.0, (camera.width, camera.height))
        print(f"[Main] Recording annotated video to: {args.output}")

    frame_count = 0
    print("\n[INFO] Press 'q' in the video window to quit.\n")

    try:
        while True:
            ret, frame = camera.read()
            if not ret:
                print("[Main] Video stream ended or camera disconnected.")
                break

            frame_count += 1

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
                    # Track is already associated: record continuity without re-evaluating face every frame
                    attendance.register_observation(
                        track_id=tid,
                        student_id=None,
                        student_name=None,
                        confidence=1.0,
                        bbox=person.bbox
                    )

            # 3. Evaluate absence timeouts
            attendance.check_timeouts(active_track_ids)

            # 4. Render visual overlay
            draw_overlay(frame, tracked_people, attendance, camera.fps)

            if video_writer:
                video_writer.write(frame)

            # 5. Show GUI window if not in headless mode
            if not args.no_gui:
                cv2.imshow("Smart Attendance System - Tracking & Recognition", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

    finally:
        camera.release()
        if video_writer:
            video_writer.release()
        cv2.destroyAllWindows()

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
