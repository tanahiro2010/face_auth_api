import json
import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from src import crud
from src.config import settings
from src.database import get_db
from src.face_service import FaceService, NoFaceDetectedError, get_face_service
from src.schemas import FaceSampleResponse, IdentifyResponse, PersonResponse

router = APIRouter(prefix="/faces", tags=["faces"])
logger = logging.getLogger("uvicorn.error")


def _parse_info(info: str | None) -> dict:
    if not info:
        return {}
    try:
        parsed = json.loads(info)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="info はJSON文字列で指定してください"
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="info はJSONオブジェクトで指定してください"
        )
    return parsed


async def _extract_embedding(image: UploadFile, face_service: FaceService) -> list[float]:
    image_bytes = await image.read()
    try:
        return face_service.extract_embedding(image_bytes)
    except NoFaceDetectedError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/register", response_model=PersonResponse, status_code=status.HTTP_201_CREATED)
async def register_face(
    name: str = Form(...),
    info: str | None = Form(None),
    crop_variant: str | None = Form(None),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    face_service: FaceService = Depends(get_face_service),
) -> PersonResponse:
    embedding = await _extract_embedding(image, face_service)
    parsed_info = _parse_info(info)
    person, sample_added, closest_similarity = crud.upsert_person_sample(
        db, name=name, info=parsed_info, embedding=embedding
    )
    logger.info(
        "face register name=%s variant=%s sample_added=%s closest_similarity=%s samples=%d",
        person.name,
        crop_variant,
        sample_added,
        f"{closest_similarity:.3f}" if closest_similarity is not None else None,
        len(person.samples),
    )
    return PersonResponse.model_validate(person)


@router.post("/identify", response_model=IdentifyResponse)
async def identify_face(
    image: UploadFile = File(...),
    auto_enroll: bool = Form(True),
    source: str | None = Form(None),
    crop_variant: str | None = Form(None),
    db: Session = Depends(get_db),
    face_service: FaceService = Depends(get_face_service),
) -> IdentifyResponse:
    embedding = await _extract_embedding(image, face_service)
    match = crud.find_closest_match(db, embedding)
    if match is None:
        logger.info("face identify no_samples variant=%s", crop_variant)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="一致する登録者が見つかりませんでした")
    if match[1] < settings.face_match_threshold:
        logger.info(
            "face identify rejected variant=%s similarity=%.3f threshold=%.3f",
            crop_variant,
            match[1],
            settings.face_match_threshold,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "一致する登録者が見つかりませんでした "
                f"(closest similarity {match[1]:.3f} < threshold {settings.face_match_threshold:.3f})"
            ),
        )
    person, similarity, _ = match
    sample_added = False
    closest_sample_similarity = None
    if auto_enroll and similarity >= settings.face_auto_enroll_min_similarity:
        sample_added, closest_sample_similarity = crud.add_face_sample(
            db, person, embedding, source=source
        )
    logger.info(
        "face identify accepted name=%s variant=%s similarity=%.3f sample_added=%s samples=%d",
        person.name,
        crop_variant,
        similarity,
        sample_added,
        len(person.samples),
    )
    return IdentifyResponse(
        person=PersonResponse.model_validate(person),
        similarity=similarity,
        sample_added=sample_added,
        closest_sample_similarity=closest_sample_similarity,
    )


@router.post("/{person_id}/samples", response_model=FaceSampleResponse)
async def add_face_sample(
    person_id: uuid.UUID,
    image: UploadFile = File(...),
    source: str | None = Form(None),
    crop_variant: str | None = Form(None),
    db: Session = Depends(get_db),
    face_service: FaceService = Depends(get_face_service),
) -> FaceSampleResponse:
    person = crud.get_person(db, person_id)
    if person is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="登録者が見つかりませんでした")

    embedding = await _extract_embedding(image, face_service)
    sample_added, closest_sample_similarity = crud.add_face_sample(
        db, person, embedding, source=source
    )
    logger.info(
        "face sample name=%s variant=%s sample_added=%s closest_similarity=%s samples=%d",
        person.name,
        crop_variant,
        sample_added,
        (
            f"{closest_sample_similarity:.3f}"
            if closest_sample_similarity is not None
            else None
        ),
        len(person.samples),
    )
    return FaceSampleResponse(
        person=PersonResponse.model_validate(person),
        sample_added=sample_added,
        closest_sample_similarity=closest_sample_similarity,
    )


@router.get("", response_model=list[PersonResponse])
def list_faces(db: Session = Depends(get_db)) -> list[PersonResponse]:
    return [PersonResponse.model_validate(p) for p in crud.list_people(db)]


@router.get("/{person_id}", response_model=PersonResponse)
def get_face(person_id: uuid.UUID, db: Session = Depends(get_db)) -> PersonResponse:
    person = crud.get_person(db, person_id)
    if person is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="登録者が見つかりませんでした")
    return PersonResponse.model_validate(person)


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_face(person_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    if not crud.delete_person(db, person_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="登録者が見つかりませんでした")
