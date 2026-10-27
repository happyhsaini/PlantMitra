import json
import os
import subprocess
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.ml_runtime import python_executable

router = APIRouter(prefix="/api/ai", tags=["plant AI"])
PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODEL_METADATA = PROJECT_ROOT / "ml" / "models" / "plantmitra_model_metadata.json"
MAX_IMAGE_BYTES = 15 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


def read_model_metadata() -> dict:
    try:
        return json.loads(MODEL_METADATA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="The plant identification model is unavailable.") from exc


def infer_image_bytes(raw: bytes) -> tuple[dict, dict]:
    metadata = read_model_metadata()
    python = python_executable()
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    environment["OMP_NUM_THREADS"] = "1"
    environment["MKL_NUM_THREADS"] = "1"
    try:
        completed = subprocess.run(
            [python, "-m", "ml.inference.predict", "--image-stdin"],
            input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=PROJECT_ROOT,
            env=environment, timeout=90, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(status_code=503, detail="Plant identification is temporarily unavailable.") from exc
    if completed.returncode:
        if b"ValueError" in completed.stderr or b"UnidentifiedImageError" in completed.stderr:
            raise HTTPException(status_code=422, detail="The uploaded file is not a valid supported image.")
        raise HTTPException(status_code=503, detail="Plant identification is temporarily unavailable.")
    try:
        return json.loads(completed.stdout), metadata
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=503, detail="Plant identification returned an invalid response.") from exc


@router.get("/classes")
def model_classes():
    metadata = read_model_metadata()
    return {
        "model_version": metadata["model_version"],
        "classes": [item["common_name"] for item in metadata["classes"]],
    }


@router.post("/identify")
async def identify_with_model(image: UploadFile = File(...)):
    if image.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Use a JPEG, PNG, or WEBP image.")
    raw = await image.read(MAX_IMAGE_BYTES + 1)
    await image.close()
    if not raw:
        raise HTTPException(status_code=400, detail="The selected image is empty.")
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be smaller than 15 MB.")

    prediction, metadata = infer_image_bytes(raw)

    result = {
        "success": True,
        "supported": prediction["supported"],
        "predicted_class": prediction["common_name"] if prediction["supported"] else None,
        "dataset_label": prediction["predicted_class"],
        "scientific_name": next(
            (item["scientific_name"] for item in metadata["classes"] if item["dataset_label"] == prediction["predicted_class"]),
            None,
        ),
        "confidence": prediction["model_confidence"],
        "confidence_note": prediction["confidence_note"],
        "model_version": metadata["model_version"],
        "top_predictions": [
            {"class": item["common_name"], "confidence": item["model_confidence"]}
            for item in prediction["top_3_predictions"]
        ],
        "message": prediction["message"],
    }
    if prediction["supported"]:
        try:
            plant_info = json.loads((PROJECT_ROOT / "backend" / "data" / "plant_information.json").read_text(encoding="utf-8"))["plants"][prediction["predicted_class"]]
            result["plant_information"] = plant_info
        except (OSError, json.JSONDecodeError, KeyError):
            result["plant_information"] = None
    return result
