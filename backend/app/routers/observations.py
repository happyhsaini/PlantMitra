import json
import os
from pathlib import Path
import subprocess

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PlantObservation, User
from app.security import get_current_user
from app.ml_runtime import python_executable

router = APIRouter(prefix="/api/observations", tags=["observations"])
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PLANT_INFO = json.loads((PROJECT_ROOT / "backend" / "data" / "plant_information.json").read_text(encoding="utf-8"))["plants"]
MAX_IMAGE_BYTES = 15 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
ALLOWED_PARTS = {"All", "Leaf", "Flower", "Fruit", "Seed", "Bark", "Root", "Stem", "Habit", "Branch", "Bud", "Aerial", "Aerial picture", "Other"}


def serialize(item: PlantObservation) -> dict:
    info = PLANT_INFO.get(item.dataset_label) if item.dataset_label else None
    return {
        "id": item.id,
        "name": item.common_name,
        "scientific": item.scientific_name,
        "location": item.location,
        "coordinates": None if item.latitude is None else {"latitude": item.latitude, "longitude": item.longitude, "accuracy": item.accuracy},
        "date": item.created_at.isoformat() if item.created_at else "",
        "image": "",
        "image_url": f"/api/observations/{item.id}/image",
        "family": info["family"] if info else "Unknown",
        "confidence": round(item.confidence * 100),
        "status": item.status,
        "createdAt": int(item.created_at.timestamp() * 1000) if item.created_at else 0,
        "plantPart": item.plant_part,
        "note": item.note,
        "plantInformation": info,
        "serverBacked": True,
    }


@router.get("")
def list_observations(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(PlantObservation).where(PlantObservation.user_id == current.id).order_by(PlantObservation.created_at.desc(), PlantObservation.id.desc())).all()
    return {"observations": [serialize(row) for row in rows]}


@router.get("/{observation_id}/image")
def observation_image(observation_id: int, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(PlantObservation).where(PlantObservation.id == observation_id, PlantObservation.user_id == current.id))
    if row is None:
        raise HTTPException(status_code=404, detail="Observation not found.")
    return Response(content=row.image, media_type=row.image_type, headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"})


@router.post("")
async def save_observation(
    image: UploadFile = File(...),
    dataset_label: str = Form(default=""),
    plant_part: str = Form(default="Other"),
    note: str = Form(default=""),
    location: str = Form(default=""),
    latitude: float | None = Form(default=None),
    longitude: float | None = Form(default=None),
    accuracy: float | None = Form(default=None),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if image.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Use a JPEG, PNG, or WEBP image.")
    content = await image.read(MAX_IMAGE_BYTES + 1)
    await image.close()
    if not content:
        raise HTTPException(status_code=400, detail="The selected image is empty.")
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be smaller than 15 MB.")
    python = python_executable()
    try:
        checked = subprocess.run(
            [python, "-m", "ml.inference.predict", "--validate-stdin"], input=content,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=PROJECT_ROOT,
            env={**os.environ, "PYTHONUTF8": "1"}, timeout=20, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(status_code=503, detail="Image validation is temporarily unavailable.") from exc
    if checked.returncode:
        raise HTTPException(status_code=422, detail="The uploaded file is not a valid supported image.")
    try:
        decoded_format = json.loads(checked.stdout)["format"]
        detected_type = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[decoded_format]
    except (json.JSONDecodeError, KeyError, TypeError):
        raise HTTPException(status_code=422, detail="The uploaded file is not a valid supported image.")
    if plant_part not in ALLOWED_PARTS or len(note) > 2000 or len(location) > 240:
        raise HTTPException(status_code=422, detail="Observation details are invalid.")
    if (latitude is None) != (longitude is None):
        raise HTTPException(status_code=422, detail="Both GPS coordinates are required.")
    if latitude is not None and not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise HTTPException(status_code=422, detail="GPS coordinates are invalid.")
    if accuracy is not None and accuracy < 0:
        raise HTTPException(status_code=422, detail="GPS accuracy is invalid.")

    if dataset_label:
        if dataset_label not in PLANT_INFO:
            raise HTTPException(status_code=422, detail="This plant class is not supported by the model.")
        from app.routers.ai import infer_image_bytes
        prediction, metadata = infer_image_bytes(content)
        class_entry = next((row for row in metadata["classes"] if row["dataset_label"] == dataset_label), None)
        if class_entry is None:
            raise HTTPException(status_code=422, detail="This plant class is not supported by the model.")
        if not prediction["supported"] or prediction["predicted_class"] != dataset_label:
            raise HTTPException(status_code=422, detail="This photo does not match the selected identification. Identify it again before saving.")
        common_name, scientific_name, status = class_entry["common_name"], class_entry["scientific_name"], "Identified"
        confidence = float(prediction["model_confidence"])
    else:
        common_name, scientific_name, status, confidence = "Unidentified plant", "Identification not run", "Needs identification", 0.0
    row = PlantObservation(
        user_id=current.id, image=content, image_type=detected_type, dataset_label=dataset_label or None,
        common_name=common_name, scientific_name=scientific_name, confidence=confidence, status=status,
        location=location.strip() or "Location not added", latitude=latitude, longitude=longitude, accuracy=accuracy,
        plant_part=plant_part, note=note.strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.delete("/{observation_id}")
def delete_observation(observation_id: int, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(PlantObservation).where(PlantObservation.id == observation_id, PlantObservation.user_id == current.id))
    if row is None:
        raise HTTPException(status_code=404, detail="Observation not found.")
    db.delete(row)
    db.commit()
    return {"success": True}
