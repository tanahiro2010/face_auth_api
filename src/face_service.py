import cv2
import numpy as np
from fastapi import HTTPException, status
from insightface.app import FaceAnalysis

from src.config import settings


class NoFaceDetectedError(Exception):
    pass


class FaceService:
    """Wraps insightface so the model is loaded once and reused across requests."""

    def __init__(self) -> None:
        self._app = FaceAnalysis(
            name=settings.insightface_model_name,
            providers=["CPUExecutionProvider"],
        )
        self._app.prepare(ctx_id=-1, det_size=(640, 640))

    def extract_embedding(self, image_bytes: bytes) -> list[float]:
        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="画像を読み込めませんでした"
            )

        faces = self._app.get(image)
        if not faces:
            raise NoFaceDetectedError("画像から顔を検出できませんでした")

        # Multiple faces may appear in one photo; use the largest as the subject.
        largest = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        return largest.normed_embedding.tolist()


_face_service: FaceService | None = None


def init_face_service() -> None:
    global _face_service
    _face_service = FaceService()


def get_face_service() -> FaceService:
    if _face_service is None:
        raise RuntimeError("FaceService is not initialized")
    return _face_service
