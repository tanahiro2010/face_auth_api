import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from src import crud
from src.config import settings
from src.database import get_db
from src.face_service import FaceService, NoFaceDetectedError, get_face_service
from src.schemas import IdentifyResponse, PersonResponse

router = APIRouter(prefix="/faces", tags=["faces"])


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
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    face_service: FaceService = Depends(get_face_service),
) -> PersonResponse:
    embedding = await _extract_embedding(image, face_service)
    parsed_info = _parse_info(info)
    person = crud.create_person(db, name=name, info=parsed_info, embedding=embedding)
    return PersonResponse.model_validate(person)


@router.post("/identify", response_model=IdentifyResponse)
async def identify_face(
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    face_service: FaceService = Depends(get_face_service),
) -> IdentifyResponse:
    embedding = await _extract_embedding(image, face_service)
    match = crud.find_closest_match(db, embedding)
    if match is None or match[1] < settings.face_match_threshold:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="一致する登録者が見つかりませんでした")
    person, similarity = match
    return IdentifyResponse(person=PersonResponse.model_validate(person), similarity=similarity)


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
