"""Inspect and stream a small number of Pl@ntNet-300K examples from Hugging Face."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

DATASET_ID = "mikehemberger/plantnet300K"
SPECIES_MAPPING_REPO = "cpoisson/plantnet300k-resnet18"
SPECIES_MAPPING_FILE = "plantnet300K_species_id_2_name.json"
DATASET_DIR = Path(__file__).resolve().parent
CLASSES_PATH = DATASET_DIR / "classes.json"


def open_stream(split: str = "train"):
    try:
        from datasets import load_dataset
    except ImportError as error:
        raise RuntimeError("Install ML dependencies with: pip install -r ml/requirements.txt") from error

    split_names = [split, "validation" if split == "val" else "val"] if split in {"val", "validation"} else [split]
    last_error: Exception | None = None
    for split_name in split_names:
        try:
            dataset = load_dataset(DATASET_ID, split=split_name, streaming=True)
            break
        except Exception as error:
            last_error = error
    else:
        raise RuntimeError(f"Could not open Hugging Face split {split!r} (tried {split_names}).") from last_error
    if not hasattr(dataset, "take") or not hasattr(dataset, "features"):
        raise RuntimeError("Hugging Face did not return a streaming dataset.")
    return dataset


def column_names(dataset: Any) -> tuple[str, str]:
    columns = list(dataset.column_names)
    image_column = next((name for name in ("image", "img", "photo") if name in columns), None)
    label_column = next((name for name in ("label", "class", "species") if name in columns), None)
    if not image_column or not label_column:
        raise RuntimeError(f"Unexpected dataset columns {columns!r}; expected an image column and a class-label column.")
    return image_column, label_column


def feature_label_names(dataset: Any, label_column: str) -> list[str] | None:
    feature = dataset.features[label_column]
    names = getattr(feature, "names", None)
    if names:
        return [str(name) for name in names]
    return None


def get_label(dataset: Any, row: dict[str, Any], label_column: str, species_names: dict[str, str] | None = None) -> tuple[int | str, str]:
    raw_label = row[label_column]
    feature = dataset.features[label_column]
    if hasattr(feature, "int2str"):
        label_id = int(raw_label)
        dataset_label = str(feature.int2str(label_id))
        return label_id, (species_names or {}).get(dataset_label, dataset_label)
    if isinstance(raw_label, str):
        return raw_label, (species_names or {}).get(raw_label, raw_label)
    label_id = int(raw_label)
    dataset_label = str(label_id)
    return label_id, (species_names or {}).get(dataset_label, dataset_label)


def _binomial(scientific_name: str) -> str:
    clean = re.sub(r"\([^)]*\)", " ", scientific_name).replace("×", " ")
    tokens = re.findall(r"[A-Za-z][A-Za-z-]*", clean)
    if len(tokens) < 2:
        return ""
    return f"{tokens[0].casefold()} {tokens[1].casefold()}"


def match_target_classes(labels: Iterable[str], candidates: list[dict[str, str]]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_label in labels:
        actual_label = str(raw_label).strip()
        identity = _binomial(actual_label)
        tokens = actual_label.split()
        for candidate in candidates:
            target = candidate["scientific_name"]
            match_type = candidate["match"]
            found = identity == _binomial(target) if match_type == "species" else bool(tokens and tokens[0].casefold() == target.casefold())
            if found and actual_label not in seen:
                matches.append({
                    "dataset_label": actual_label,
                    "scientific_name": actual_label,
                    "common_name": candidate["common_name"],
                    "match_type": match_type,
                })
                seen.add(actual_label)
                break
    return matches


def load_species_name_map() -> dict[str, str]:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as error:
        raise RuntimeError("Install ML dependencies with: pip install -r ml/requirements.txt") from error

    path = hf_hub_download(repo_id=SPECIES_MAPPING_REPO, filename=SPECIES_MAPPING_FILE, repo_type="model")
    return {str(key): str(value) for key, value in json.loads(Path(path).read_text(encoding="utf-8")).items()}


def write_class_mapping(dataset: Any, label_column: str) -> list[dict[str, Any]]:
    if not CLASSES_PATH.exists():
        raise RuntimeError(f"Missing class candidate file: {CLASSES_PATH}")
    mapping = json.loads(CLASSES_PATH.read_text(encoding="utf-8"))
    label_ids = feature_label_names(dataset, label_column)
    if label_ids is None:
        raise RuntimeError("The dataset label feature does not expose its class names. Refusing to guess scientific labels.")
    species_names = load_species_name_map()
    names = [species_names.get(str(label_id), "") for label_id in label_ids]
    missing = [label_id for label_id, scientific in zip(label_ids, names) if not scientific]
    if missing:
        raise RuntimeError(f"Official species metadata is missing {len(missing)} dataset label ID(s); refusing to guess names.")
    matches = match_target_classes(names, mapping["target_candidates"])
    feature = dataset.features[label_column]
    for item in matches:
        item["class_index"] = names.index(item["scientific_name"])
        item["dataset_label_id"] = str(label_ids[item["class_index"]])
    mapping["label_column"] = label_column
    mapping["label_count"] = len(label_ids)
    mapping["label_id_to_scientific_name"] = {str(label_id): name for label_id, name in zip(label_ids, names)}
    mapping["selected_classes"] = matches
    mapping["stream_checked"] = True
    CLASSES_PATH.write_text(json.dumps(mapping, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return matches


def decode_image(value: Any):
    from io import BytesIO
    from PIL import Image

    if isinstance(value, Image.Image):
        return value.convert("RGB")
    if isinstance(value, dict):
        if value.get("bytes"):
            return Image.open(BytesIO(value["bytes"])).convert("RGB")
        if value.get("path"):
            return Image.open(value["path"]).convert("RGB")
    raise RuntimeError(f"Unsupported streamed image value: {type(value).__name__}")


def run_smoke_test(sample_count: int = 5, display_image: bool = True) -> list[dict[str, Any]]:
    dataset = open_stream("train")
    image_column, label_column = column_names(dataset)
    print(f"Dataset: {DATASET_ID}")
    print(f"Columns: {dataset.column_names}")
    label_ids = feature_label_names(dataset, label_column) or []
    print(f"Feature schema: {image_column}=image; {label_column}=class label ({len(label_ids)} class IDs)")
    print("Mode: streaming=True; full dataset archive download: NO")

    mapping = write_class_mapping(dataset, label_column)
    species_names = json.loads(CLASSES_PATH.read_text(encoding="utf-8"))["label_id_to_scientific_name"]
    print(f"Exact medicinal target classes found: {len(mapping)}")
    for item in mapping:
        print(f"  {item['scientific_name']} ({item['common_name']}) · class {item['class_index']}")

    examples: list[dict[str, Any]] = []
    preview = None
    for row in dataset.take(sample_count):
        label_id, label_name = get_label(dataset, row, label_column, species_names)
        image = decode_image(row[image_column])
        print(f"Sample {len(examples) + 1}: {label_name} · {image.width}×{image.height}")
        examples.append({"label_id": label_id, "label_name": label_name})
        if preview is None:
            preview = image.copy()

    if len(examples) != sample_count:
        raise RuntimeError(f"Requested {sample_count} streamed samples but received {len(examples)}.")
    if display_image and preview is not None:
        try:
            from IPython.display import display

            display(preview)
        except ImportError:
            preview.show(title=f"Pl@ntNet-300K sample: {examples[0]['label_name']}")
    print(f"Smoke test passed: streamed {len(examples)} examples; no ZIP or complete image dataset was downloaded.")
    return examples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=5, help="Number of examples to stream (default: 5).")
    parser.add_argument("--no-display", action="store_true", help="Skip opening the first sample image.")
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("--samples must be at least 1")
    run_smoke_test(args.samples, display_image=not args.no_display)


if __name__ == "__main__":
    main()
