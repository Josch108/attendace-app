#!/usr/bin/env python3
"""
Script to enroll a single student with their photo(s) and facial biometric embedding.
Usage:
  python scripts/enroll_student.py --name "John Doe" --number "20230001" --group "Group A" --photo /path/photo.jpg
Or run interactively:
  python scripts/enroll_student.py
"""
import sys
import shutil
import argparse
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal
from app.models.student import Student
from app.models.academic import Course, Group, Enrollment
from app.models.biometric import FaceEmbedding
from app.services.face_service import face_service
from app.config import settings

def enroll_student(name: str, student_number: str, photo_paths: list[str], group_name: str = "Group A", course_code: str = "COURSE-101"):
    db = SessionLocal()
    try:
        # 1. Find or create course and group
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

        # 2. Find or create student
        student = db.query(Student).filter_by(student_number=student_number).first()
        if not student:
            student = Student(name=name, student_number=student_number)
            db.add(student)
            db.flush()
            print(f"[OK] Student created: {student.name} (Student ID: {student.student_number}, DB ID: {student.id})")
        else:
            print(f"[INFO] Existing student found: {student.name} (DB ID: {student.id})")
            if student.name != name:
                student.name = name

        # 3. Associate with group if not already enrolled
        enrollment = db.query(Enrollment).filter_by(student_id=student.id, group_id=group.id).first()
        if not enrollment:
            enrollment = Enrollment(student_id=student.id, group_id=group.id)
            db.add(enrollment)
            print(f"[OK] Student enrolled into group '{group.name}'")

        # 4. Process photos and persist embeddings
        dest_dir = settings.STORAGE_PATH / student.student_number
        dest_dir.mkdir(parents=True, exist_ok=True)

        embeddings_added = 0
        for p_str in photo_paths:
            src_path = Path(p_str)
            if not src_path.exists():
                print(f"[ERROR] Photo not found: {src_path}")
                continue

            # Copy image to student managed storage
            dest_file = dest_dir / src_path.name
            shutil.copy2(src_path, dest_file)

            try:
                # Extract embedding
                emb_vector, score, bbox = face_service.extract_embedding_from_file(dest_file)
                
                # Create biometric record
                face_emb = FaceEmbedding.create_from_numpy(
                    student_id=student.id,
                    vector=emb_vector,
                    model_version=settings.MODEL_VERSION,
                    photo_path=str(dest_file.relative_to(BACKEND_DIR.parent)),
                    quality_score=score
                )
                db.add(face_emb)
                embeddings_added += 1
                print(f"[OK] Embedding generated for '{src_path.name}' (Confidence: {score:.2f})")
            except Exception as e:
                print(f"[WARN] Could not process face in '{src_path.name}': {e}")

        db.commit()
        print(f"\n[SUCCESS] Enrollment completed for {student.name}. Total embeddings added: {embeddings_added}")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Failed to enroll student: {e}")
        raise e
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description="Enroll student and facial photo samples.")
    parser.add_argument("--name", type=str, help="Full student name")
    parser.add_argument("--number", type=str, help="Student ID / roll number")
    parser.add_argument("--photo", type=str, nargs="+", help="Path to one or more photos")
    parser.add_argument("--group", type=str, default="Group A", help="Group name (defaults to 'Group A')")
    parser.add_argument("--course", type=str, default="COURSE-101", help="Course code")

    args = parser.parse_args()

    name = args.name
    number = args.number
    photos = args.photo or []
    group = args.group
    course = args.course

    # Interactive prompt if arguments are omitted
    if not name or not number or not photos:
        print("=== Student Face Enrollment ===")
        if not name:
            name = input("Full student name: ").strip()
        if not number:
            number = input("Student ID / roll number: ").strip()
        if not photos:
            raw_photos = input("Photo file path(s), comma-separated if multiple: ").strip()
            photos = [p.strip() for p in raw_photos.split(",") if p.strip()]

    enroll_student(name=name, student_number=number, photo_paths=photos, group_name=group, course_code=course)

if __name__ == "__main__":
    main()
