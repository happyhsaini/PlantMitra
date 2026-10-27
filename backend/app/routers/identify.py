import json
import secrets
from urllib.parse import quote
import urllib.error
import urllib.request

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings

router = APIRouter(tags=["identification"])


@router.post("/identify")
async def identify_plant(image: UploadFile = File(...)):
    if not settings.plantnet_api_key:
        raise HTTPException(
            status_code=503,
            detail="Plant identification is not configured yet. Add PLANTNET_API_KEY to backend/.env.",
        )

    content_type = image.content_type or ""
    if content_type not in {"image/jpeg", "image/png"}:
        raise HTTPException(status_code=415, detail="Use a JPG or PNG image for identification.")

    image_bytes = await image.read(15 * 1024 * 1024 + 1)
    if len(image_bytes) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image must be smaller than 15 MB.")
    if not image_bytes:
        raise HTTPException(status_code=400, detail="The selected image is empty.")

    boundary = secrets.token_hex(16)
    filename = (image.filename or "plant-photo.jpg").replace('"', "").replace("\r", "").replace("\n", "")
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="images"; filename="{filename}"\r\n'.encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            image_bytes,
            f"\r\n--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="organs"\r\n\r\n',
            b"auto\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    request = urllib.request.Request(
        "https://my-api.plantnet.org/v2/identify/all?lang=en&nb-results=5&api-key="
        + quote(settings.plantnet_api_key, safe=""),
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        if error.code == 401:
            raise HTTPException(status_code=502, detail="PlantNet rejected the API key. Check backend/.env.") from error
        if error.code == 429:
            raise HTTPException(status_code=429, detail="PlantNet identification quota is currently exhausted.") from error
        raise HTTPException(status_code=502, detail=f"PlantNet could not identify this photo ({error.code}).") from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=502, detail="PlantNet could not be reached. Please try again.") from error
