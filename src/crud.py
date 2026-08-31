import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import Person


def create_person(db: Session, name: str, info: dict, embedding: list[float]) -> Person:
    person = Person(name=name, info=info, embedding=embedding)
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


def list_people(db: Session) -> list[Person]:
    return list(db.scalars(select(Person).order_by(Person.created_at)))


def get_person(db: Session, person_id: uuid.UUID) -> Person | None:
    return db.get(Person, person_id)


def delete_person(db: Session, person_id: uuid.UUID) -> bool:
    person = db.get(Person, person_id)
    if person is None:
        return False
    db.delete(person)
    db.commit()
    return True


def find_closest_match(db: Session, embedding: list[float]) -> tuple[Person, float] | None:
    """Returns the closest person by cosine similarity, along with the similarity score."""
    distance = Person.embedding.cosine_distance(embedding)
    result = db.execute(
        select(Person, distance.label("distance")).order_by(distance).limit(1)
    ).first()
    if result is None:
        return None
    person, cosine_distance = result
    similarity = 1 - cosine_distance
    return person, similarity
