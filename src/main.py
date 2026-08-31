from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.face_service import init_face_service
from src.routers import faces


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_face_service()
    yield


app = FastAPI(title="Face Auth API", lifespan=lifespan)
app.include_router(faces.router)


@app.get("/")
async def root():
    return {"message": "Hello World"}
