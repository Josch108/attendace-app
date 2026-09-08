#!/usr/bin/env python3
"""
Desktop Webcam Kiosk for Student Face Enrollment:
Interactively captures 3 to 5 photos with on-screen countdown and saves them to the database.

Usage:
  python scripts/webcam_enroll.py
  python scripts/webcam_enroll.py --name "Jane Doe" --number "20230005" --burst 4
"""
import sys
import time
import argparse
from pathlib import Path
import cv2
import numpy as np

# Add project root and backend to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal
from app.models.student import Student
from app.models.academic import Course, Group, Enrollment
from app.models.biometric import FaceEmbedding
from app.services.face_service import face_service
from app.config import settings

def run_webcam_enrollment(name: str, student_number: str, group_name: str = "Group A", burst_count: int = 4, camera_index: int = 0):
    print(f"\n=== Starting Webcam Enrollment for: {name} (ID: {student_number}) ===")

    # Check if student already exists before opening camera
    db = SessionLocal()
    try:
        existing = db.query(Student).filter_by(student_number=student_number).first()
        if existing:
            print(f"[ERROR] Student with ID '{student_number}' is already registered as '{existing.name}'. Duplicate enrollment is not allowed.\n")
            return False
    finally:
        db.close()

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"[ERROR] Could not open webcam at index {camera_index}.")
        return False

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    window_name = "Student Enrollment Kiosk - Press SPACE to start capture, Q to cancel"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    state = "READY"  # READY, COUNTDOWN, BURST, FINISHED
    countdown_start = 0
    countdown_duration = 3.0
    captured_frames = []
    last_burst_time = 0
    burst_interval = 0.5  # 500ms between photos
    flash_until = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            h, w = frame.shape[:2]
            display = frame.copy()
            now = time.time()

            # Draw alignment oval guide
            center = (w // 2, h // 2)
            axes = (int(w * 0.18), int(h * 0.35))
            cv2.ellipse(display, center, axes, 0, 0, 360, (255, 180, 0), 2)

            if state == "READY":
                cv2.putText(display, f"Student: {name} ({student_number})", (25, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
                cv2.putText(display, "Position your face inside the oval and press [SPACE] to start", (25, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)

            elif state == "COUNTDOWN":
                remaining = int(countdown_duration - (now - countdown_start)) + 1
                if remaining > 0:
                    cv2.putText(display, str(remaining), (w // 2 - 30, h // 2 + 30), cv2.FONT_HERSHEY_SIMPLEX, 4.0, (0, 255, 255), 6)
                else:
                    state = "BURST"
                    captured_frames = []
                    last_burst_time = 0

            elif state == "BURST":
                if now - last_burst_time >= burst_interval and len(captured_frames) < burst_count:
                    captured_frames.append(frame.copy())
                    last_burst_time = now
                    flash_until = now + 0.15  # 150ms screen flash

                # Shutter flash effect
                if now < flash_until:
                    display = np.full_like(display, 255)

                cv2.putText(display, f"Capturing: {len(captured_frames)} / {burst_count}", (25, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

                if len(captured_frames) >= burst_count:
                    state = "FINISHED"

            elif state == "FINISHED":
                cv2.putText(display, "Processing photos, please wait...", (w // 2 - 200, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
                cv2.imshow(window_name, display)
                cv2.waitKey(1)
                break

            cv2.imshow(window_name, display)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("[INFO] Capture cancelled by user.")
                return False
            elif key == ord(' ') and state == "READY":
                state = "COUNTDOWN"
                countdown_start = time.time()

    finally:
        cap.release()
        cv2.destroyAllWindows()

    if not captured_frames:
        return False

    # Save to database and filesystem
    print(f"\n[INFO] Saving {len(captured_frames)} photos and extracting facial embeddings...")
    db = SessionLocal()
    try:
        course = db.query(Course).filter_by(code="COURSE-101").first()
        if not course:
            course = Course(code="COURSE-101", name="Default Course")
            db.add(course)
            db.flush()

        group = db.query(Group).filter_by(name=group_name, course_id=course.id).first()
        if not group:
            group = Group(name=group_name, period="2026-2", course_id=course.id)
            db.add(group)
            db.flush()

        student = Student(name=name, student_number=student_number)
        db.add(student)
        db.flush()

        enrollment = Enrollment(student_id=student.id, group_id=group.id)
        db.add(enrollment)

        dest_dir = settings.STORAGE_PATH / student.student_number
        dest_dir.mkdir(parents=True, exist_ok=True)

        saved = 0
        for i, img in enumerate(captured_frames, start=1):
            try:
                emb, score, bbox = face_service.extract_embedding_from_image(img, source_name=f"kiosk_{i}")
                filename = f"kiosk_sample_{i}.jpg"
                filepath = dest_dir / filename
                cv2.imwrite(str(filepath), img)

                rel_path = str(filepath.relative_to(PROJECT_ROOT))
                face_emb = FaceEmbedding.create_from_numpy(
                    student_id=student.id,
                    vector=emb,
                    model_version=settings.MODEL_VERSION,
                    photo_path=rel_path,
                    quality_score=score
                )
                db.add(face_emb)
                saved += 1
                print(f"  - Sample #{i} saved (Confidence: {score:.2f})")
            except Exception as e:
                print(f"  - Sample #{i} skipped: {e}")

        if saved == 0:
            db.rollback()
            print("[ERROR] No faces detected in captured photos.")
            return False

        db.commit()
        print(f"\n[SUCCESS] Successfully registered {student.name} with {saved} face embeddings!\n")
        return True

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Webcam Face Enrollment Kiosk.")
    parser.add_argument("--name", type=str, help="Full student name")
    parser.add_argument("--number", type=str, help="Student ID / roll number")
    parser.add_argument("--group", type=str, default="Group A", help="Academic group name")
    parser.add_argument("--burst", type=int, default=4, help="Number of photos to capture (3-5)")
    parser.add_argument("--camera", type=int, default=0, help="Webcam device index")

    args = parser.parse_args()

    name = args.name
    number = args.number

    if not name:
        name = input("Enter student's full name: ").strip()
    if not number:
        number = input("Enter student's ID / matrícula: ").strip()

    run_webcam_enrollment(
        name=name,
        student_number=number,
        group_name=args.group,
        burst_count=args.burst,
        camera_index=args.camera
    )

if __name__ == "__main__":
    main()
