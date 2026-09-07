from datetime import datetime, timezone
import numpy as np
from sqlalchemy import String, Float, ForeignKey, DateTime, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    
    # Biometric feature vector (stored in 512D float32 binary format for cross-database portability)
    embedding_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    
    # Model metadata for auditing and versioning
    model_version: Mapped[str] = mapped_column(String(100), default="insightface/buffalo_l", nullable=False)
    photo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    student = relationship("Student", back_populates="embeddings")

    def to_numpy(self) -> np.ndarray:
        """Converts raw binary bytes into a 512-dimensional float32 numpy array."""
        return np.frombuffer(self.embedding_data, dtype=np.float32)

    @classmethod
    def create_from_numpy(
        cls,
        student_id: int,
        vector: np.ndarray,
        model_version: str = "insightface/buffalo_l",
        photo_path: str | None = None,
        quality_score: float | None = None
    ):
        """Creates an instance by serializing the numpy float32 vector into raw bytes."""
        data_bytes = vector.astype(np.float32).tobytes()
        return cls(
            student_id=student_id,
            embedding_data=data_bytes,
            model_version=model_version,
            photo_path=photo_path,
            quality_score=quality_score
        )

    def __repr__(self) -> str:
        return f"<FaceEmbedding(id={self.id}, student_id={self.student_id}, model='{self.model_version}')>"
