import urllib.error
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/reference-observations", tags=["reference observations"])


@router.get("")
def reference_observations(scientific_name: str = Query(min_length=2, max_length=160)):
    query = urllib.parse.urlencode({"scientificName": scientific_name, "mediaType": "StillImage", "limit": 20, "offset": 0})
    api_url = f"https://api.gbif.org/v1/occurrence/search?{query}"
    request = urllib.request.Request(api_url, headers={"User-Agent": "PlantMitra/1.0 (plant observation reference lookup)"})
    try:
        with urllib.request.urlopen(request, timeout=18) as response:
            import json
            result = json.loads(response.read(2_000_000))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        raise HTTPException(status_code=502, detail="Reference observations are temporarily unavailable.") from exc
    records = []
    for row in result.get("results", []):
        media = next((item for item in row.get("media", []) if item.get("identifier")), None)
        if media is None:
            continue
        gbif_id = row.get("key")
        records.append({
            "id": gbif_id,
            "image": media["identifier"],
            "date": row.get("eventDate") or row.get("year"),
            "location": ", ".join(filter(None, [row.get("locality"), row.get("stateProvince"), row.get("country")])),
            "source": "GBIF",
            "source_url": f"https://www.gbif.org/occurrence/{gbif_id}" if gbif_id else api_url,
            "license": media.get("license") or row.get("license") or "Not specified by record",
            "attribution": "; ".join(filter(None, [row.get("recordedBy"), media.get("creator"), row.get("datasetName")])),
            "scientific_name": row.get("scientificName") or scientific_name,
        })
    return {"source": "GBIF", "source_url": api_url, "observations": records}
