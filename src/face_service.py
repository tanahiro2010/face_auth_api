import io

import cv2
import numpy as np
from fastapi import HTTPException, status
from insightface.app import FaceAnalysis
from PIL import Image, ImageOps

from src.config import settings

# Orientations checked, beyond the EXIF-corrected one, to cover photos that are
# sideways/upside-down without (or despite) EXIF metadata. A person's natural head
# tilt is already handled by insightface's landmark-based alignment, so this is only
# about whole-image rotation. None = as loaded (after EXIF correction).
_ROTATIONS = (None, cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE)
_PAD_SCALES = (1.35, 1.75, 2.25)


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
        image = self._load_image(image_bytes)
        if image is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="画像を読み込めませんでした"
            )

        candidates = self._detect_candidates(image)

        if not candidates:
            for padded in self._padded(image):
                candidates.extend(self._detect_candidates(padded))

        if not candidates:
            # Nothing at all was found even after retrying tiles at every orientation;
            # this is the expensive path, only hit when the photo has no usable face.
            candidates = [
                self._best_candidate(self._detect_in_tiles(o)) for o in self._oriented(image)
            ]
            candidates = [c for c in candidates if c is not None]

        if not candidates:
            raise NoFaceDetectedError("画像から顔を検出できませんでした")

        best = max(candidates, key=lambda f: f.det_score)
        return best.normed_embedding.tolist()

    def _detect_candidates(self, image: np.ndarray) -> list:
        # A detector can sometimes find a low-quality, poorly-aligned face in a
        # sideways/upside-down photo instead of cleanly failing, so we can't just stop
        # at the first orientation that finds anything. Collect the best (largest)
        # face from each of the 4 orientations, then trust the detector's own
        # confidence (det_score) to pick which orientation was actually correct.
        return [
            candidate
            for candidate in (self._best_candidate(self._app.get(o)) for o in self._oriented(image))
            if candidate is not None
        ]

    @staticmethod
    def _oriented(image: np.ndarray):
        for rotate_code in _ROTATIONS:
            yield image if rotate_code is None else cv2.rotate(image, rotate_code)

    @staticmethod
    def _padded(image: np.ndarray):
        height, width = image.shape[:2]
        for scale in _PAD_SCALES:
            target_height = max(height + 2, int(height * scale))
            target_width = max(width + 2, int(width * scale))
            top = (target_height - height) // 2
            bottom = target_height - height - top
            left = (target_width - width) // 2
            right = target_width - width - left
            yield cv2.copyMakeBorder(
                image,
                top,
                bottom,
                left,
                right,
                cv2.BORDER_REPLICATE,
            )

    @staticmethod
    def _best_candidate(faces: list):
        if not faces:
            return None
        # Multiple faces may appear in one photo; use the largest as the subject.
        return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))

    @staticmethod
    def _load_image(image_bytes: bytes) -> np.ndarray | None:
        try:
            pil_image = Image.open(io.BytesIO(image_bytes))
            # Phone/camera photos are often stored upright with an EXIF orientation
            # tag rather than pre-rotated pixels; apply it before detecting faces.
            pil_image = ImageOps.exif_transpose(pil_image)
            rgb = np.array(pil_image.convert("RGB"))
        except Exception:
            return None
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    def _detect_in_tiles(self, image: np.ndarray) -> list:
        # The detector resizes the whole image down to a fixed input size, so a small
        # face in a large photo can shrink below its detection floor. Splitting the
        # image into overlapping tiles re-crops around the face, giving the detector a
        # much less "zoomed out" view to work with.
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
