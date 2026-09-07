import sys
from pathlib import Path
from typing import Optional, Tuple
import numpy as np

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal
from app.models.student import Student
from app.models.biometric import FaceEmbedding
from app.services.face_service import face_service
from app.config import settings

class FaceRecognizer:
    """
    Handles comparison of detected face embeddings against registered student embeddings from the database.
    """
    def __init__(self, match_threshold: float = None):
        self.threshold = match_threshold or settings.FACE_MATCH_THRESHOLD
        self.known_embeddings = np.empty((0, 512), dtype=np.float32)
        self.known_students = []
        self.load_database_embeddings()

    def load_database_embeddings(self):
        """
        Loads all active biometric embeddings from the database into memory.
        """
        db = SessionLocal()
        try:
            records = (
                db.query(FaceEmbedding)
                .join(Student, FaceEmbedding.student_id == Student.id)
                .filter(FaceEmbedding.revoked_at == None, Student.is_active == True)
                .all()
            )

            vectors = []
            students_meta = []
            for r in records:
                vec = r.to_numpy()
                # Ensure L2 normalization for exact cosine similarity
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                vectors.append(vec)
                students_meta.append({
                    "student_id": r.student.id,
                    "name": r.student.name,
                    "student_number": r.student.student_number
                })

            if vectors:
                self.known_embeddings = np.vstack(vectors).astype(np.float32)
                self.known_students = students_meta
                print(f"[FaceRecognizer] Loaded {len(self.known_students)} embeddings from database.")
            else:
                self.known_embeddings = np.empty((0, 512), dtype=np.float32)
                self.known_students = []
                print("[FaceRecognizer] No embeddings registered in database yet.")
        finally:
            db.close()

    def recognize_crop(self, crop: np.ndarray) -> Tuple[Optional[int], Optional[str], float]:
        """
        Detects face in the cropped image and calculates cosine similarity against enrolled students.
        Returns:
            (student_id, name, confidence)
            If unmatched/unknown: (None, "Unknown", best_score)
            If no face detected: (None, None, 0.0)
        """
        if crop is None or crop.size == 0:
            return None, None, 0.0

        app = face_service._get_app()
        if app is None:
            return None, None, 0.0

        faces = app.get(crop)
        if not faces:
            return None, None, 0.0

        # Pick the largest face if multiple faces are present in the crop
        face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        q_emb = face.normed_embedding.astype(np.float32)
        q_norm = np.linalg.norm(q_emb)
        if q_norm > 0:
            q_emb = q_emb / q_norm

        if len(self.known_embeddings) == 0:
            return None, "Unknown", float(face.det_score if hasattr(face, "det_score") else 0.5)

        # Cosine similarity: dot product between L2-normalized vectors
        similarities = np.dot(self.known_embeddings, q_emb)
        best_idx = int(np.argmax(similarities))
        best_score = float(similarities[best_idx])

        if best_score >= self.threshold:
            match = self.known_students[best_idx]
            return match["student_id"], match["name"], best_score
        else:
            return None, "Unknown", best_score
