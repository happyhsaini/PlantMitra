"""Load the metadata-locked PlantMitra model and predict one plant image."""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import sys
from typing import Any

import torch
from PIL import Image

from ml.dataset.dimpsar_local_dataset import DEFAULT_INDEX, DimpsarLocalDataset, TARGET_CLASSES
from ml.models.architecture import create_mobilenet_v3_small, inference_transform

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = PROJECT_ROOT / "ml/models/plantmitra_mobilenetv3_small.pth"
METADATA_PATH = PROJECT_ROOT / "ml/models/plantmitra_model_metadata.json"


def load_model(
    model_path: str | Path = MODEL_PATH,
    metadata_path: str | Path = METADATA_PATH,
    device: torch.device | None = None,
) -> tuple[torch.nn.Module, dict[str, Any], torch.device]:
    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    classes = metadata.get("classes", [])
    if metadata.get("num_classes") != len(TARGET_CLASSES) or [
        item["dataset_label"] for item in classes
    ] != list(TARGET_CLASSES):
        raise ValueError("Model metadata class mapping is missing or out of order.")
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # The saved checkpoint already contains the complete trained state. Avoid
    # loading the separate ImageNet training cache during production inference.
    model = create_mobilenet_v3_small(len(classes), device, load_pretrained=False)
    checkpoint = torch.load(model_path, map_location=device, weights_only=True)
    if checkpoint.get("architecture") != metadata["model_name"] or checkpoint.get("classes") != classes:
        raise ValueError("Model checkpoint architecture or class mapping differs from metadata.")
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    model.eval()
    return model, metadata, device


def predict_image(
    model: torch.nn.Module,
    metadata: dict[str, Any],
    device: torch.device,
    image: Image.Image | str | Path,
    confidence_threshold: float | None = None,
) -> dict[str, Any]:
    if isinstance(image, (str, Path)):
        with Image.open(image) as opened:
            opened.load()
            image = opened.convert("RGB")
    elif image.mode != "RGB":
        image = image.convert("RGB")
    threshold = (
        float(metadata.get("uncertainty_threshold", 0.55))
        if confidence_threshold is None
        else float(confidence_threshold)
    )
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("confidence_threshold must be between 0 and 1")
    tensor = inference_transform()(image).unsqueeze(0).to(device)
    with torch.inference_mode():
        scores = torch.softmax(model(tensor), dim=1)[0]
    values, indices = scores.topk(min(3, scores.numel()))
    classes = metadata["classes"]
    top_three = [
        {
            "dataset_label": classes[int(index)]["dataset_label"],
            "common_name": classes[int(index)]["common_name"],
            "model_confidence": float(value),
        }
        for value, index in zip(values.cpu(), indices.cpu())
    ]
    best = top_three[0]
    supported = best["model_confidence"] >= threshold
    return {
        "supported": supported,
        "predicted_class": best["dataset_label"] if supported else None,
        "common_name": best["common_name"] if supported else None,
        "model_confidence": best["model_confidence"],
        "confidence_note": "Model confidence is not a probability of correctness.",
        "top_3_predictions": top_three,
        "message": None if supported else "Plant identification is uncertain.",
    }


def smoke_test() -> None:
    model, metadata, device = load_model()
    validation = DimpsarLocalDataset(DEFAULT_INDEX, split="validation")
    test = DimpsarLocalDataset(DEFAULT_INDEX, split="test")
    samples: list[tuple[str, Image.Image, int]] = []
    seen = set()
    for record in validation.records:
        label = record["dataset_label"]
        if label not in seen:
            samples.append((f"validation/{label}", validation[validation.records.index(record)][0], record["class_index"]))
            seen.add(label)
        if len(seen) == len(TARGET_CLASSES):
            break
    samples.append(("test/sample", test[0][0], test.records[0]["class_index"]))
    if len(samples) != len(TARGET_CLASSES) + 1:
        raise RuntimeError("Could not select one validation image per class plus a test image.")

    for source, image, expected_index in samples:
        result = predict_image(model, metadata, device, image)
        predicted_names = {item["dataset_label"] for item in result["top_3_predictions"]}
        if not result["top_3_predictions"] or not predicted_names.issubset(set(TARGET_CLASSES)):
            raise RuntimeError(f"Inference output did not match the saved class mapping: {source}")
        if expected_index >= len(metadata["classes"]):
            raise RuntimeError(f"Stored dataset index exceeds saved class mapping: {source}")
        print(
            f"{source} | expected={metadata['classes'][expected_index]['dataset_label']} "
            f"| predicted={result['predicted_class'] or 'uncertain'} "
            f"| confidence={result['model_confidence']:.4f} | mapping=OK"
        )
    print(f"Inference reload and {len(samples)} mapping checks passed.")


def decode_stdin_image(max_bytes: int = 15 * 1024 * 1024) -> tuple[Image.Image, str, int, int]:
    raw = sys.stdin.buffer.read(max_bytes + 1)
    if not raw or len(raw) > max_bytes:
        raise ValueError("Image is empty or exceeds the 15 MB limit.")
    try:
        with Image.open(io.BytesIO(raw)) as opened:
            if opened.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("Use a JPEG, PNG, or WEBP image.")
            if opened.width < 32 or opened.height < 32 or opened.width * opened.height > 40_000_000:
                raise ValueError("Image dimensions are invalid or too large.")
            image_format, width, height = opened.format, opened.width, opened.height
            opened.load()
            image = opened.convert("RGB")
    except (Image.DecompressionBombError, OSError) as error:
        raise ValueError("The uploaded file is not a valid supported image.") from error
    return image, image_format, width, height


def validate_stdin() -> None:
    image, image_format, width, height = decode_stdin_image()
    print(json.dumps({"format": image_format, "width": width, "height": height}))


def predict_stdin(max_bytes: int = 15 * 1024 * 1024) -> None:
    """Decode one bounded upload from stdin without creating an image file."""
    image, _, _, _ = decode_stdin_image(max_bytes)
    model, metadata, device = load_model()
    print(json.dumps(predict_image(model, metadata, device, image), ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--image-stdin", action="store_true")
    parser.add_argument("--validate-stdin", action="store_true")
    parser.add_argument("--confidence-threshold", type=float)
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    if args.smoke_test:
        smoke_test()
        return
    if args.image_stdin:
        predict_stdin()
        return
    if args.validate_stdin:
        validate_stdin()
        return
    if args.image is None:
        parser.error("Pass --image PATH or use --smoke-test")
    model, metadata, device = load_model()
    print(
        json.dumps(
            predict_image(model, metadata, device, args.image, args.confidence_threshold),
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
