import uuid

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.config import settings
from src.models import FaceSample, Person


def _normalize_embedding(embedding: list[float]) -> list[float]:
    vector = np.array(embedding, dtype=np.float32)
    norm = np.linalg.norm(vector)
    if norm == 0:
        return embedding
    return (vector / norm).tolist()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    av = np.array(a, dtype=np.float32)
    bv = np.array(b, dtype=np.float32)
    denom = np.linalg.norm(av) * np.linalg.norm(bv)
    if denom == 0:
        return 0.0
    return float(np.dot(av, bv) / denom)


def _refresh_representative_embedding(person: Person) -> None:
    if not person.samples:
        return
    vectors = [
        np.array(sample.embedding, dtype=np.float32) for sample in person.samples
    ]
    person.embedding = _normalize_embedding(np.mean(vectors, axis=0).tolist())


def create_person(db: Session, name: str, info: dict, embedding: list[float]) -> Person:
    person = Person(name=name, info=info, embedding=embedding)
    person.samples.append(FaceSample(embedding=embedding, source=info.get("source")))
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


def get_person_by_name(db: Session, name: str) -> Person | None:
    return db.scalar(
        select(Person)
        .options(selectinload(Person.samples))
        .where(Person.name == name)
        .order_by(Person.created_at)
        .limit(1)
    )


def list_people(db: Session) -> list[Person]:
    return list(
        db.scalars(
            select(Person).options(selectinload(Person.samples)).order_by(Person.created_at)
        )
    )


def get_person(db: Session, person_id: uuid.UUID) -> Person | None:
    return db.scalar(
        select(Person).options(selectinload(Person.samples)).where(Person.id == person_id)
    )


def delete_person(db: Session, person_id: uuid.UUID) -> bool:
    person = db.get(Person, person_id)
    if person is None:
        return False
    db.delete(person)
    db.commit()
    return True


def add_face_sample(
    db: Session,
    person: Person,
    embedding: list[float],
    source: str | None = None,
    duplicate_threshold: float | None = None,
) -> tuple[bool, float | None]:
    """Adds a new pose/sample unless it is already too close to an existing sample."""
    duplicate_threshold = duplicate_threshold or settings.face_sample_duplicate_threshold
    db.refresh(person, attribute_names=["samples"])
    closest_similarity = max(
        (_cosine_similarity(sample.embedding, embedding) for sample in person.samples),
        default=None,
    )
    if closest_similarity is not None and closest_similarity >= duplicate_threshold:
        return False, closest_similarity
    if len(person.samples) >= settings.face_max_samples_per_person:
        return False, closest_similarity

    person.samples.append(FaceSample(embedding=embedding, source=source))
    _refresh_representative_embedding(person)
    db.commit()
    db.refresh(person)
    return True, closest_similarity


def upsert_person_sample(
    db: Session, name: str, info: dict, embedding: list[float]
) -> tuple[Person, bool, float | None]:
    person = get_person_by_name(db, name)
    if person is None:
        return create_person(db, name=name, info=info, embedding=embedding), True, None

    sample_added, closest_similarity = add_face_sample(
        db, person, embedding, source=info.get("source")
    )
    if info:
        person.info = {**person.info, **info}
        db.commit()
        db.refresh(person)
    return person, sample_added, closest_similarity


def find_closest_match(
    db: Session, embedding: list[float]
) -> tuple[Person, float, FaceSample] | None:
    """Returns the closest person sample by cosine similarity."""
    distance = FaceSample.embedding.cosine_distance(embedding)
    result = db.execute(
        select(FaceSample, distance.label("distance"))
        .options(selectinload(FaceSample.person).selectinload(Person.samples))
        .order_by(distance)
        .limit(1)
    ).first()
    if result is None:
        return None
    sample, cosine_distance = result
    similarity = 1 - cosine_distance
    return sample.person, similarity, sample
