from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.face_service import init_face_service
from src.routers import faces

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_face_service()
    yield


app = FastAPI(title="Face Auth API", lifespan=lifespan)
app.include_router(faces.router)
app.mount("/ui", StaticFiles(directory=STATIC_DIR, html=True), name="ui")


@app.get("/")
async def root():
    return RedirectResponse(url="/ui/")
