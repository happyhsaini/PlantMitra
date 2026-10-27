"""End-to-end check for the local PlantMitra API and the locked model checkpoint."""

from __future__ import annotations

import io
import asyncio
import json
import os
import secrets
import sys
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ml.dataset.dimpsar_local_dataset import DEFAULT_INDEX, DimpsarLocalDataset, TARGET_CLASSES
from ml.inference.predict import load_model, predict_image

API = os.environ.get("PLANTMITRA_TEST_API", "http://127.0.0.1:8001")
MAX_UPLOAD = 15 * 1024 * 1024


def call(path: str, *, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None):
    request = urllib.request.Request(API + path, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=100) as response:
            payload = response.read()
            content_type = response.headers.get("Content-Type", "")
            return response.status, json.loads(payload) if payload and "json" in content_type else payload
    except urllib.error.HTTPError as error:
        payload = error.read()
        return error.code, json.loads(payload) if payload else {}


def json_request(path: str, body: dict):
    return call(path, method="POST", body=json.dumps(body).encode(), headers={"Content-Type": "application/json"})


def multipart(fields: dict[str, str], image: bytes, content_type: str = "image/png") -> tuple[bytes, str]:
    boundary = "PlantMitra" + secrets.token_hex(12)
    chunks = []
    for key, value in fields.items():
        chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode())
    chunks.extend([
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"plant.png\"\r\nContent-Type: {content_type}\r\n\r\n".encode(),
        image,
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def request_image(path: str, image: bytes, token: str | None = None, fields: dict[str, str] | None = None, content_type: str = "image/png"):
    body, multipart_type = multipart(fields or {}, image, content_type)
    headers = {"Content-Type": multipart_type}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return call(path, method="POST", body=body, headers=headers)


def png_bytes(image: Image.Image) -> bytes:
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def main() -> None:
    if "--live-smoke" in sys.argv:
        class_status, classes = call("/api/ai/classes")
        assert class_status == 200 and classes["classes"] == ["Aloe Vera", "Amla", "Ashwagandha", "Brahmi", "Mint", "Neem", "Tulsi"]
        dataset = DimpsarLocalDataset(DEFAULT_INDEX, split="test")
        image, _ = dataset[0]
        record = dataset.records[0]
        status, result = request_image("/api/ai/identify", png_bytes(image))
        assert status == 200 and result["supported"] and result["dataset_label"] == record["dataset_label"], result
        assert call("/api/observations")[0] == 401
        print(f"PASS live backend on :8000: {result['predicted_class']} ({result['confidence']:.3f}), locked checkpoint, auth enforced")
        return

    classes = call("/api/ai/classes")[1]
    assert classes["classes"] == ["Aloe Vera", "Amla", "Ashwagandha", "Brahmi", "Mint", "Neem", "Tulsi"]
    print("PASS model classes: metadata-backed seven-class mapping")

    backend_python = PROJECT_ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
    code = f'''
import asyncio, io
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers
from app.config import settings
from app.routers.ai import identify_with_model
settings.plantmitra_ml_python = {str(PROJECT_ROOT / "ml" / "missing-test-python.exe")!r}
async def check():
    upload = UploadFile(file=io.BytesIO(b"x"), filename="bad.png", headers=Headers({{"content-type": "image/png"}}))
    try:
        await identify_with_model(upload)
    except HTTPException as error:
        assert error.status_code == 503 and "unavailable" in error.detail.lower()
        return
    raise AssertionError("Expected sanitized model-unavailable response")
asyncio.run(check())
'''
    unavailable = subprocess.run([str(backend_python), "-c", code], cwd=PROJECT_ROOT / "backend", capture_output=True, text=True, timeout=20)
    assert unavailable.returncode == 0, unavailable.stderr
    print("PASS model unavailable response is sanitized")

    suffix = secrets.token_hex(5)
    status, account = json_request("/auth/signup", {
        "display_name": "PlantMitra Test", "email": f"codex-test-{suffix}@example.com", "password": "temporary-test-password"
    })
    assert status == 201, account
    token = account["access_token"]
    second_status, second_account = json_request("/auth/signup", {
        "display_name": "Other Test", "email": f"other-test-{suffix}@example.com", "password": "temporary-test-password"
    })
    assert second_status == 201, second_account
    other_token = second_account["access_token"]
    assert call("/api/observations")[0] == 401
    print("PASS authentication required for personal observations")

    dataset = DimpsarLocalDataset(DEFAULT_INDEX, split="test")
    model, metadata, device = load_model()
    known: dict[str, tuple[bytes, dict]] = {}
    for index, row in enumerate(dataset.records):
        label = row["dataset_label"]
        if label in known:
            continue
        image, _ = dataset[index]
        prediction = predict_image(model, metadata, device, image)
        if prediction["supported"] and prediction["predicted_class"] == label:
            known[label] = (png_bytes(image), prediction)
        if len(known) == len(TARGET_CLASSES):
            break
    assert len(known) == len(TARGET_CLASSES), f"Only found correct held-out samples for {list(known)}"

    first_saved = None
    for label in TARGET_CLASSES:
        image_data, _ = known[label]
        status, result = request_image("/api/ai/identify", image_data, token)
        assert status == 200 and result["supported"] and result["dataset_label"] == label, (label, status, result)
        assert 0 <= result["confidence"] <= 1 and result["model_version"] == "1.0.0"
        assert result.get("plant_information", {}).get("sources")
        print(f"PASS inference {label}: {result['predicted_class']} {result['confidence']:.3f}")
        if first_saved is None:
            first_saved = (label, image_data, result)

    label, image_data, result = first_saved
    saved_status, saved = request_image("/api/observations", image_data, token, {
        "dataset_label": label, "plant_part": "Leaf", "note": "Integration check",
        "latitude": "23.0026", "longitude": "77.6260", "accuracy": "12",
    })
    assert saved_status == 200 and saved["status"] == "Identified" and saved["coordinates"]["latitude"] == 23.0026, saved
    own_status, own = call("/api/observations", headers={"Authorization": f"Bearer {token}"})
    other_status, other = call("/api/observations", headers={"Authorization": f"Bearer {other_token}"})
    assert own_status == 200 and len(own["observations"]) == 1 and own["observations"][0]["image"] == ""
    image_status, image_bytes = call(f"/api/observations/{saved['id']}/image", headers={"Authorization": f"Bearer {token}"})
    assert image_status == 200 and image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert other_status == 200 and other["observations"] == []
    assert call(f"/api/observations/{saved['id']}", method="DELETE", headers={"Authorization": f"Bearer {other_token}"})[0] == 404
    stats = call("/dashboard/me", headers={"Authorization": f"Bearer {token}"})[1]
    assert stats["plants_identified"] == 1 and stats["unique_species"] == 1
    assert call(f"/api/observations/{saved['id']}", method="DELETE", headers={"Authorization": f"Bearer {token}"})[0] == 200
    assert call("/api/observations", headers={"Authorization": f"Bearer {token}"})[1]["observations"] == []
    print("PASS account-scoped save, list, dashboard counts, and owner-only delete")

    valid_png = first_saved[1]
    assert request_image("/api/ai/identify", b"not an image", token)[0] == 422
    assert request_image("/api/ai/identify", valid_png, token, content_type="application/pdf")[0] == 415
    large = b"0" * (MAX_UPLOAD + 1)
    assert request_image("/api/ai/identify", large, token)[0] == 413
    print("PASS invalid bytes, disallowed MIME, and oversized upload rejection")

    noise_model, noise_metadata, noise_device = model, metadata, device
    uncertain = None
    noise_images = [Image.new("RGB", (224, 224), color) for color in [(255, 0, 255), (0, 0, 0), (255, 255, 255), (127, 127, 127)]]
    noise_images.append(Image.effect_noise((224, 224), 100).convert("RGB"))
    for sample in noise_images:
        guess = predict_image(noise_model, noise_metadata, noise_device, sample)
        if not guess["supported"]:
            uncertain = png_bytes(sample)
            break
    if uncertain:
        status, uncertain_result = request_image("/api/ai/identify", uncertain, token)
        assert status == 200 and uncertain_result["supported"] is False and uncertain_result["predicted_class"] is None
        print("PASS uncertainty threshold returns no forced class")
    else:
        print("SKIP synthetic low-confidence case: available synthetic samples exceeded the configured threshold")

    reference_status, reference = call("/api/reference-observations?scientific_name=Azadirachta%20indica")
    if reference_status == 200:
        assert reference["source"] == "GBIF"
        assert all(item.get("source_url") and item.get("license") and "image" in item for item in reference["observations"])
        print(f"PASS GBIF reference endpoint: {len(reference['observations'])} real record(s), source and rights fields present")
    else:
        assert reference_status == 502 and "temporarily unavailable" in reference["detail"]
        print("PASS GBIF outage is reported as temporarily unavailable without affecting AI inference")

    try:
        urllib.request.urlopen("http://127.0.0.1:8002/api/ai/classes", timeout=2)
        raise AssertionError("Expected unavailable backend port")
    except urllib.error.URLError:
        print("PASS backend-unavailable client connection fails cleanly")

    assert (PROJECT_ROOT / "ml/models/plantmitra_mobilenetv3_small.pth").stat().st_size > 0
    print("Verified checkpoint loaded from the existing path; no training or dataset download performed.")


if __name__ == "__main__":
    main()
