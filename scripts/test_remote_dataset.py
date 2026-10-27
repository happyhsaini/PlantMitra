"""Small safety test: fetch and decode only three licensed images per class."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.dataset.remote_plantnet_v2 import RemotePlantNetV2  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-class", type=int, default=3)
    parser.add_argument("--no-display", action="store_true", help="skip opening the preview image")
    args = parser.parse_args()
    config = json.loads((ROOT / "ml/dataset/classes.json").read_text(encoding="utf-8"))["plantnet_v2"]
    classes = config["verified_classes"]
    names = [item["scientific_name"] for item in classes]

    loader = RemotePlantNetV2(
        archive_url=config["dataset_url"],
        allowed_licenses=tuple(config["image_license_allowlist"]),
    )
    preview: Image.Image | None = None
    total = 0
    try:
        species_by_id, records = loader.load_metadata(names)
        by_name = {name: [] for name in names}
        for record in records:
            by_name.setdefault(record.scientific_name, []).append(record)
        for item in classes:
            mapped = species_by_id.get(item["species_id"])
            if not mapped or mapped["species"] != item["scientific_name"]:
                raise RuntimeError(f"Unverified species mapping in current metadata: {item}")
            selected = by_name.get(item["scientific_name"], [])[:args.per_class]
            if len(selected) != args.per_class:
                raise RuntimeError(f"Only {len(selected)} eligible licensed images for {item['scientific_name']}")
            for record in selected:
                image_bytes = loader.fetch_bytes(record)
                with Image.open(io.BytesIO(image_bytes)) as source:
                    source.load()
                    image = source.convert("RGB")
                if image.width <= 0 or image.height <= 0:
                    raise RuntimeError("PIL returned an invalid image size")
                digest = hashlib.sha256(image_bytes).hexdigest()
                print(
                    f"image_hash={digest} species_id={record.species_id} "
                    f"scientific_name={record.scientific_name!r} organ={record.organ!r} "
                    f"author={record.author!r} license={record.license!r} "
                    f"image_size={image.width}x{image.height}"
                )
                if preview is None:
                    preview = image.copy()
                total += 1

        if not args.no_display and preview is not None:
            try:
                preview.show(title="Pl@ntNet-300K-v2 streamed image preview")
                print("Displayed one fetched image using PIL.")
            except Exception as exc:
                print(f"Image display unavailable in this environment: {exc}")
        print(f"Verified {total} images across {len(classes)} official v2 species classes.")
        print(f"HTTP range requests: {loader.range_requests}; bytes received: {loader.bytes_received:,}")
        print("NO COMPLETE DATASET DOWNLOADED")
    finally:
        loader.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
