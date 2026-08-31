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
        det_size = settings.face_det_size
        self._app.prepare(ctx_id=-1, det_size=(det_size, det_size))

    def extract_embedding(self, image_bytes: bytes) -> list[float]:
        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="画像を読み込めませんでした"
            )

        faces = self._app.get(image)
        if not faces:
            # The detector resizes the whole image down to a fixed input size, so a
            # small face in a large photo can shrink below its detection floor.
            # Splitting the image into overlapping tiles re-crops around the face,
            # giving the detector a much less "zoomed out" view to work with.
            faces = self._detect_in_tiles(image)
        if not faces:
            raise NoFaceDetectedError("画像から顔を検出できませんでした")

        # Multiple faces may appear in one photo; use the largest as the subject.
        largest = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        return largest.normed_embedding.tolist()

    def _detect_in_tiles(self, image: np.ndarray) -> list:
        grid = settings.face_tile_grid
        if grid < 2:
            return []

        height, width = image.shape[:2]
        row_bounds = self._tile_bounds(height, grid, settings.face_tile_overlap)
        col_bounds = self._tile_bounds(width, grid, settings.face_tile_overlap)

        found = []
        for y0, y1 in row_bounds:
            for x0, x1 in col_bounds:
                tile = image[y0:y1, x0:x1]
                if tile.size == 0:
                    continue
                found.extend(self._app.get(tile))
        return found

    @staticmethod
    def _tile_bounds(size: int, grid: int, overlap: float) -> list[tuple[int, int]]:
        step = size / grid
        tile_size = step * (1 + overlap)
        bounds = []
        for i in range(grid):
            start = max(0, int(i * step - (tile_size - step) / 2))
            end = min(size, int(start + tile_size))
            bounds.append((start, end))
        return bounds


_face_service: FaceService | None = None


def init_face_service() -> None:
    global _face_service
    _face_service = FaceService()


def get_face_service() -> FaceService:
    if _face_service is None:
        raise RuntimeError("FaceService is not initialized")
    return _face_service
