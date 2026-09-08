import base64
import shutil
import cv2
import numpy as np
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.student import Student
from app.models.academic import Course, Group, Enrollment
from app.models.biometric import FaceEmbedding
from app.services.face_service import face_service
from app.schemas.student import StudentResponse, EnrollmentResult, Base64EnrollmentRequest
from app.config import settings

router = APIRouter(prefix="/students", tags=["Students"])

def _get_or_create_group(db: Session, group_name: str, course_code: str = "COURSE-101") -> Group:
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

    return group

def _check_face_duplicate(db: Session, embedding: np.ndarray, exclude_student_id: int = None, threshold: float = 0.72):
    """
    Checks if an extracted face embedding matches another already-enrolled student.
    Prevents the same person from registering multiple times under different student numbers.
    """
    query = (
        db.query(FaceEmbedding)
        .join(Student, FaceEmbedding.student_id == Student.id)
        .filter(FaceEmbedding.revoked_at == None, Student.is_active == True)
    )
    if exclude_student_id is not None:
        query = query.filter(FaceEmbedding.student_id != exclude_student_id)

    existing_embs = query.all()
    if not existing_embs:
        return

    q_norm = np.linalg.norm(embedding)
    if q_norm == 0:
        return
    q_vec = embedding / q_norm

    for r in existing_embs:
        known = r.to_numpy()
        k_norm = np.linalg.norm(known)
        if k_norm > 0:
            sim = float(np.dot(known / k_norm, q_vec))
            if sim >= threshold:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"This face is already registered to '{r.student.name}' (ID: {r.student.student_number}) with similarity {sim:.2f}. Duplicate face registration is not allowed."
                )

def _save_embeddings_and_files(
    db: Session,
    student: Student,
    images_data: List[bytes]
) -> tuple[int, List[float]]:
    """
    Processes image bytes in memory, validates for duplicate faces, extracts embeddings,
    writes successful files to disk, and saves FaceEmbedding records.
    """
    dest_dir = settings.STORAGE_PATH / student.student_number
    dest_dir.mkdir(parents=True, exist_ok=True)

    extracted_samples = []

    # First pass: Extract embeddings and check for duplicates
    for idx, img_bytes in enumerate(images_data, start=1):
        try:
            emb, score, bbox, bgr_img = face_service.extract_embedding_from_bytes(
                img_bytes,
                source_name=f"capture_{idx}"
            )
            # Check if this face is already registered under someone else
            _check_face_duplicate(db, emb, exclude_student_id=student.id)
            extracted_samples.append((emb, score, bgr_img))
        except HTTPException as he:
            raise he
        except Exception as e:
            print(f"[EnrollmentAPI] Warning: Skipping frame #{idx}: {e}")

    if not extracted_samples:
        return 0, []

    embeddings_saved = 0
    quality_scores = []

    # Second pass: Save to disk and database
    for idx, (emb, score, bgr_img) in enumerate(extracted_samples, start=1):
        filename = f"capture_{idx}_{int(score * 100)}.jpg"
        file_path = dest_dir / filename
        cv2.imwrite(str(file_path), bgr_img)

        rel_path = str(file_path.relative_to(Path(settings.STORAGE_PATH).parent.parent))
        face_emb = FaceEmbedding.create_from_numpy(
            student_id=student.id,
            vector=emb,
            model_version=settings.MODEL_VERSION,
            photo_path=rel_path,
            quality_score=score
        )
        db.add(face_emb)
        embeddings_saved += 1
        quality_scores.append(round(score, 3))

    return embeddings_saved, quality_scores


@router.get("", response_model=List[StudentResponse])
def list_students(db: Session = Depends(get_db)):
    """Lists all enrolled students and their associated face embeddings count."""
    students = db.query(Student).order_by(Student.created_at.desc()).all()
    results = []
    for s in students:
        groups = [e.group.name for e in s.enrollments if e.group]
        active_embs = len([emb for emb in s.embeddings if emb.revoked_at is None])
        results.append(
            StudentResponse(
                id=s.id,
                name=s.name,
                student_number=s.student_number,
                is_active=s.is_active,
                embeddings_count=active_embs,
                groups=groups,
                created_at=s.created_at
            )
        )
    return results


@router.post("/enroll", response_model=EnrollmentResult, status_code=status.HTTP_201_CREATED)
async def enroll_student_multipart(
    name: str = Form(..., description="Full student name"),
    student_number: str = Form(..., description="Student ID / roll number"),
    group_name: str = Form("Group A", description="Academic group name"),
    photos: List[UploadFile] = File(..., description="List of 3 to 5 face photos captured from webcam"),
    db: Session = Depends(get_db)
):
    """
    Enrolls a student using multipart/form-data upload.
    Rejects duplicate student IDs.
    """
    if not photos or len(photos) < 1:
        raise HTTPException(status_code=400, detail="At least 1 photo is required for enrollment.")

    # 1. Reject duplicate student number
    existing = db.query(Student).filter_by(student_number=student_number).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Student with ID '{student_number}' is already registered as '{existing.name}'. Duplicate registration is not allowed."
        )

    group = _get_or_create_group(db, group_name)

    student = Student(name=name, student_number=student_number)
    db.add(student)
    db.flush()

    enrollment = Enrollment(student_id=student.id, group_id=group.id)
    db.add(enrollment)

    # Read uploaded bytes
    images_data = [await p.read() for p in photos]
    saved_count, scores = _save_embeddings_and_files(db, student, images_data)

    if saved_count == 0:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail="No faces could be detected with sufficient quality in the provided photos. Please retake the photos."
        )

    db.commit()

    return EnrollmentResult(
        status="success",
        message=f"Student {student.name} successfully enrolled with {saved_count} face samples.",
        student_id=student.id,
        name=student.name,
        student_number=student.student_number,
        group_name=group.name,
        embeddings_saved=saved_count,
        quality_scores=scores
    )


@router.post("/enroll-base64", response_model=EnrollmentResult, status_code=status.HTTP_201_CREATED)
def enroll_student_base64(
    request: Base64EnrollmentRequest,
    db: Session = Depends(get_db)
):
    """
    Enrolls a student using JSON payload with base64 data URLs from webcam canvas.
    Rejects duplicate student IDs and duplicate faces.
    """
    # 1. Reject duplicate student number
    existing = db.query(Student).filter_by(student_number=request.student_number).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Student with ID '{request.student_number}' is already registered as '{existing.name}'. Duplicate registration is not allowed."
        )

    group = _get_or_create_group(db, request.group_name)

    student = Student(name=request.name, student_number=request.student_number)
    db.add(student)
    db.flush()

    enrollment = Enrollment(student_id=student.id, group_id=group.id)
    db.add(enrollment)

    # Decode base64 images
    images_data = []
    for raw in request.images:
        if "," in raw:
            raw = raw.split(",", 1)[1]
        try:
            img_bytes = base64.b64decode(raw)
            images_data.append(img_bytes)
        except Exception:
            continue

    if not images_data:
        raise HTTPException(status_code=400, detail="No valid base64 image data provided.")

    saved_count, scores = _save_embeddings_and_files(db, student, images_data)

    if saved_count == 0:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail="No faces could be detected in the captured webcam frames. Ensure proper lighting and face the camera directly."
        )

    db.commit()

    return EnrollmentResult(
        status="success",
        message=f"Student {student.name} successfully enrolled with {saved_count} face samples.",
        student_id=student.id,
        name=student.name,
        student_number=student.student_number,
        group_name=group.name,
        embeddings_saved=saved_count,
        quality_scores=scores
    )


@router.delete("/{student_id}", status_code=status.HTTP_200_OK)
def delete_student(student_id: int, db: Session = Depends(get_db)):
    """Deletes a student, their enrollment, embeddings, and saved photos on disk."""
    student = db.query(Student).filter_by(id=student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    student_number = student.student_number
    student_name = student.name

    # Remove photos from disk
    dest_dir = settings.STORAGE_PATH / student_number
    if dest_dir.exists():
        shutil.rmtree(dest_dir, ignore_errors=True)

    db.delete(student)
    db.commit()

    return {
        "status": "success",
        "message": f"Student '{student_name}' (ID: {student_number}) deleted successfully."
    }
