#!/usr/bin/env python3
"""
Utility script to inspect and list registered students,
their IDs, enrolled groups, and biometric face embeddings in the database.
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal
from app.models.student import Student
from app.models.academic import Group, Enrollment
from app.models.biometric import FaceEmbedding

def list_all_students():
    db = SessionLocal()
    try:
        students = db.query(Student).all()
        if not students:
            print("No students currently registered in the database.")
            return

        print(f"\n{'ID':<5} | {'STUDENT ID':<15} | {'NAME':<25} | {'GROUPS':<20} | {'FACE EMBEDDINGS':<15}")
        print("-" * 88)
        for s in students:
            groups = [e.group.name for e in s.enrollments if e.group]
            groups_str = ", ".join(groups) if groups else "No group"
            embs_count = len([emb for emb in s.embeddings if emb.revoked_at is None])
            print(f"{s.id:<5} | {s.student_number:<15} | {s.name:<25} | {groups_str:<20} | {embs_count:<15}")
        print("-" * 88)
        print(f"Total registered students: {len(students)}\n")
    finally:
        db.close()

if __name__ == "__main__":
    list_all_students()
