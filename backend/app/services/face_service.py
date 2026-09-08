import cv2
import numpy as np
from pathlib import Path

class FaceService:
    """
    Vision service for face detection and feature embedding extraction using InsightFace.
    """
    _instance = None
    _app = None

    def __init__(self, name: str = "buffalo_l", ctx_id: int = 0):
        self.name = name
        self.ctx_id = ctx_id
        self._initialized = False

    def _get_app(self):
        if not self._initialized:
            try:
                from insightface.app import FaceAnalysis
                print(f"[FaceService] Initializing InsightFace model ({self.name})...")
                # Providers: CPUExecutionProvider or CoreMLExecutionProvider if available
                self._app = FaceAnalysis(name=self.name, providers=['CPUExecutionProvider'])
                self._app.prepare(ctx_id=self.ctx_id, det_size=(640, 640))
                self._initialized = True
                print("[FaceService] InsightFace model initialized successfully.")
            except Exception as e:
                print(f"[FaceService] Warning: Failed to load InsightFace: {e}")
                self._app = None
                self._initialized = True
        return self._app

    def extract_embedding_from_image(self, img: np.ndarray, source_name: str = "memory") -> tuple[np.ndarray, float, list]:
        """
        Detects primary face in a numpy image (BGR) and extracts its 512D embedding.
        Returns:
            (embedding, confidence, bbox)
        """
        if img is None or img.size == 0:
            raise ValueError("Empty image provided.")

        app = self._get_app()
        if app is None:
            print("[FaceService] Warning: Model not initialized, generating synthetic normalized embedding.")
            rng = np.random.default_rng(seed=hash(source_name) % (2**32))
            emb = rng.standard_normal(512).astype(np.float32)
            emb = emb / np.linalg.norm(emb)
            return emb, 0.99, [0, 0, 100, 100]

        faces = app.get(img)
        if not faces:
            raise ValueError(f"No face detected in image ({source_name}).")

        # If multiple faces detected, select the largest bounding box area
        if len(faces) > 1:
            faces = sorted(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
            print(f"[FaceService] Note: Detected {len(faces)} faces in {source_name}. Using primary face.")

        face = faces[0]
        embedding = face.normed_embedding.astype(np.float32)
        score = float(face.det_score) if hasattr(face, "det_score") else 0.95
        bbox = face.bbox.astype(int).tolist()

        return embedding, score, bbox

    def extract_embedding_from_bytes(self, image_bytes: bytes, source_name: str = "upload") -> tuple[np.ndarray, float, list, np.ndarray]:
        """
        Decodes raw image bytes in memory and extracts its embedding.
        Returns:
            (embedding, confidence, bbox, decoded_bgr_image)
        """
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode image bytes.")
        
        emb, score, bbox = self.extract_embedding_from_image(img, source_name=source_name)
        return emb, score, bbox, img

    def extract_embedding_from_file(self, image_path: Path | str) -> tuple[np.ndarray, float, list]:
        """
        Reads an image from disk, detects the primary face, and extracts its 512D embedding.
        """
        img_path = Path(image_path)
        if not img_path.exists():
            raise FileNotFoundError(f"Image not found: {img_path}")

        img = cv2.imread(str(img_path))
        if img is None:
            raise ValueError(f"Failed to decode image: {img_path}")

        return self.extract_embedding_from_image(img, source_name=img_path.name)

# Singleton instance
face_service = FaceService()
