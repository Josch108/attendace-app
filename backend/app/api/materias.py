from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.academic import Course, Group, Enrollment
from app.models.session import ClassSession
from app.models.student import Student
from app.schemas.academic import MateriaCreate, MateriaResponse, EnrolledStudent, EnrollStudentRequest

router = APIRouter(prefix="/materias", tags=["Materias"])

DEFAULT_COURSE_CODE = "COURSE-101"


def _get_or_create_default_course(db: Session) -> Course:
    """Same default container used by the existing students/sessions endpoints,
    so materias created here work with the live dashboard unchanged."""
    course = db.query(Course).filter_by(code=DEFAULT_COURSE_CODE).first()
    if not course:
        course = Course(code=DEFAULT_COURSE_CODE, name="Default Course")
        db.add(course)
        db.flush()
    return course


@router.get("", response_model=list[MateriaResponse])
def list_materias(db: Session = Depends(get_db)):
    """Lists all materias (groups) with their student count and required hours."""
    groups = db.query(Group).order_by(Group.created_at.desc()).all()
    results = []
    for g in groups:
        student_count = db.query(Enrollment).filter_by(group_id=g.id).count()
        sessions_count = db.query(ClassSession).filter_by(group_id=g.id).count()
        results.append(MateriaResponse(
            id=g.id,
            name=g.name,
            required_hours=g.required_hours,
            student_count=student_count,
            sessions_count=sessions_count,
            created_at=g.created_at,
        ))
    return results


@router.post("", response_model=MateriaResponse, status_code=status.HTTP_201_CREATED)
def create_materia(req: MateriaCreate, db: Session = Depends(get_db)):
    """Creates a new materia (a Group under the default course), with required hours."""
    course = _get_or_create_default_course(db)

    existing = db.query(Group).filter_by(name=req.name, course_id=course.id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A materia named '{req.name}' already exists."
        )

    group = Group(
        name=req.name,
        period="2026-2",
        course_id=course.id,
        required_hours=req.required_hours,
    )
    db.add(group)
    db.commit()
    db.refresh(group)

    return MateriaResponse(
        id=group.id,
        name=group.name,
        required_hours=group.required_hours,
        student_count=0,
        sessions_count=0,
        created_at=group.created_at,
    )


@router.get("/{materia_id}/students", response_model=list[EnrolledStudent])
def list_materia_students(materia_id: int, db: Session = Depends(get_db)):
    """Lists students currently enrolled in this materia."""
    group = db.query(Group).filter_by(id=materia_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Materia not found.")

    students = (
        db.query(Student)
        .join(Enrollment, Enrollment.student_id == Student.id)
        .filter(Enrollment.group_id == materia_id)
        .all()
    )
    return students


@router.post("/{materia_id}/students", status_code=status.HTTP_201_CREATED)
def enroll_student_in_materia(materia_id: int, req: EnrollStudentRequest, db: Session = Depends(get_db)):
    """Enrolls an already-registered student into this materia (required so the
    live dashboard has attendance rows to show when a session starts)."""
    group = db.query(Group).filter_by(id=materia_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Materia not found.")

    student = db.query(Student).filter_by(id=req.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    existing = db.query(Enrollment).filter_by(student_id=req.student_id, group_id=materia_id).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"{student.name} is already enrolled in this materia.")

    enrollment = Enrollment(student_id=req.student_id, group_id=materia_id)
    db.add(enrollment)
    db.commit()
    return {"status": "success", "message": f"{student.name} enrolled successfully."}


@router.delete("/{materia_id}/students/{student_id}", status_code=status.HTTP_200_OK)
def unenroll_student_from_materia(materia_id: int, student_id: int, db: Session = Depends(get_db)):
    """Removes a student from this materia."""
    enrollment = db.query(Enrollment).filter_by(student_id=student_id, group_id=materia_id).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="This student is not enrolled in this materia.")

    db.delete(enrollment)
    db.commit()
    return {"status": "success", "message": "Student removed from materia."}


@router.delete("/{materia_id}", status_code=status.HTTP_200_OK)
def delete_materia(materia_id: int, db: Session = Depends(get_db)):
    """Deletes a materia (group) along with its enrollments and sessions."""
    group = db.query(Group).filter_by(id=materia_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Materia not found.")

    name = group.name
    db.delete(group)
    db.commit()
    return {"status": "success", "message": f"Materia '{name}' deleted successfully."}
