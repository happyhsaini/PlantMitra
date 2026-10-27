from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import ai, auth, dashboard, identify, observations, references, users


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="PlantMitra API",
    description="Medicinal plant identification & plant-care companion (Phase 1: auth + profile).",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(dashboard.router)
app.include_router(identify.router)
app.include_router(ai.router)
app.include_router(observations.router)
app.include_router(references.router)


@app.get("/health")
def health():
    return {
        "ok": True,
        "app": "PlantMitra",
        "phase": 1,
        "disclaimer": "Identification support tool only. Not a medical diagnosis.",
    }
