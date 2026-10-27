"""Local DIMPSAR Parquet reader and deterministic metadata-index builder."""

from __future__ import annotations

import hashlib
import io
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import torch
from PIL import Image, UnidentifiedImageError
from torch.utils.data import Dataset

DATASET_ID = "Project-AgML/DIMPSAR_medicinal_plant_classification"
DATASET_URL = f"https://huggingface.co/datasets/{DATASET_ID}"
DATASET_REVISION = "eb460a4f3770a1be748a8ad2d4bc22301755c14a"
DATASET_FILE = "data/train-00000-of-00001.parquet"
LICENSE = "CC BY 4.0"
ATTRIBUTION = (
    "Pushpa, B. R., & Rani, S. (2023). DIMPSAR: Dataset for Indian medicinal plant "
    "species analysis and recognition. Data in Brief, 49, 109388. Dataset mirror: "
    "Project-AgML/DIMPSAR_medicinal_plant_classification, CC BY 4.0."
)
TARGET_CLASSES = (
    "Aloevera",
    "Amla",
    "Ashwagandha",
    "Brahmi",
    "Mint",
    "Neem",
    "Tulasi",
)
CLASS_INFO: dict[str, dict[str, str | None]] = {
    "Aloevera": {"common_name": "Aloe Vera", "scientific_name": "Aloe barbadensis miller"},
    "Amla": {"common_name": "Amla", "scientific_name": "Phyllanthus emblica"},
    "Ashwagandha": {"common_name": "Ashwagandha", "scientific_name": "Withania somnifera"},
    "Brahmi": {"common_name": "Brahmi", "scientific_name": "Bacopa monnieri"},
    "Mint": {"common_name": "Mint", "scientific_name": "Mentha"},
    "Neem": {"common_name": "Neem", "scientific_name": "Azadirachta indica"},
    "Tulasi": {"common_name": "Tulsi", "scientific_name": "Ocimum tenuiflorum"},
}
DEFAULT_INDEX = Path(__file__).resolve().with_name("dimpsar_local_index.json")
DEFAULT_SEED = 42


def _resolve_parquet_path(parquet_path: str | Path | None = None) -> Path:
    if parquet_path is not None:
        path = Path(parquet_path).expanduser().resolve()
    else:
        path = (
            Path.home()
            / ".cache"
            / "huggingface"
            / "hub"
            / f"datasets--{DATASET_ID.replace('/', '--')}"
            / "snapshots"
            / DATASET_REVISION
            / DATASET_FILE
        )
    if not path.is_file():
        raise FileNotFoundError(f"DIMPSAR Parquet shard not found: {path}")
    return path


def _split_counts(size: int) -> dict[str, int]:
    raw = {"train": size * 0.70, "validation": size * 0.15, "test": size * 0.15}
    counts = {key: math.floor(value) for key, value in raw.items()}
    for key in sorted(raw, key=lambda item: raw[item] - counts[item], reverse=True)[: size - sum(counts.values())]:
        counts[key] += 1
    return counts


def build_local_index(
    parquet_path: str | Path | None = None,
    index_path: str | Path = DEFAULT_INDEX,
    seed: int = DEFAULT_SEED,
    batch_size: int = 64,
    min_dimension: int = 32,
) -> dict[str, Any]:
    """Validate images in-memory and save target-class metadata only."""
    import pyarrow.parquet as pq

    parquet_path = _resolve_parquet_path(parquet_path)
    index_path = Path(index_path)
    parquet = pq.ParquetFile(parquet_path)
    if parquet.schema.names != ["bytes", "path", "label"]:
        raise ValueError(f"Unexpected Parquet leaf columns: {parquet.schema.names}")
    metadata = parquet.metadata.metadata or {}
    hf_metadata = json.loads(metadata[b"huggingface"])["info"]["features"]["label"]["names"]
    labels = list(hf_metadata)
    missing_classes = [name for name in TARGET_CLASSES if name not in labels]
    if missing_classes:
        raise ValueError(f"Target classes missing from Parquet label feature: {missing_classes}")
    class_ids = {name: labels.index(name) for name in TARGET_CLASSES}

    label_counts: Counter[str] = Counter()
    failed_by_label: Counter[str] = Counter()
    total_corrupt = 0
    total_missing = 0
    candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    target_hash_seen: set[str] = set()
    duplicate_rows_excluded: Counter[str] = Counter()
    row_offset = 0

    for batch in parquet.iter_batches(batch_size=batch_size, columns=["image", "label"]):
        image_values = batch.column(0).to_pylist()
        label_values = batch.column(1).to_pylist()
        for local_idx, (image_value, class_id) in enumerate(zip(image_values, label_values)):
            row_idx = row_offset + local_idx
            label = labels[class_id]
            label_counts[label] += 1
            if not isinstance(image_value, dict) or not image_value.get("bytes"):
                total_missing += 1
                failed_by_label[label] += 1
                continue
            raw = image_value["bytes"]
            digest = hashlib.sha256(raw).hexdigest()
            try:
                with Image.open(io.BytesIO(raw)) as im:
                    width, height = im.size
                    if width < min_dimension or height < min_dimension:
                        raise ValueError(f"Image too small: {width}x{height}")
                    im.verify()
                with Image.open(io.BytesIO(raw)) as im:
                    im.load()
                    im.convert("RGB")
            except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
                total_corrupt += 1
                failed_by_label[label] += 1
                continue
            if label in class_ids:
                if digest in target_hash_seen:
                    duplicate_rows_excluded[label] += 1
                else:
                    target_hash_seen.add(digest)
                    candidates[label].append(
                        {
                            "row_index": row_idx,
                            "image_path": image_value.get("path"),
                            "image_sha256": digest,
                            "width": width,
                            "height": height,
                        }
                    )
        row_offset += len(image_values)

    if row_offset != parquet.metadata.num_rows:
        raise ValueError(f"Scanned {row_offset} rows, expected {parquet.metadata.num_rows}")
    if len(labels) != 40:
        raise ValueError(f"Expected 40 class labels, found {len(labels)}")

    # Exact duplicate image bytes were removed above; split each class after a
    # deterministic shuffle so duplicate images cannot cross split boundaries.
    records: list[dict[str, Any]] = []
    per_class_counts: dict[str, dict[str, int]] = {}
    for class_name in TARGET_CLASSES:
        items = candidates[class_name]
        rng = random.Random(seed + class_ids[class_name])
        rng.shuffle(items)
        desired = _split_counts(len(items))
        split_by_index = (
            ["train"] * desired["train"]
            + ["validation"] * desired["validation"]
            + ["test"] * desired["test"]
        )
        allocated = Counter(split_by_index)
        for item, split in zip(items, split_by_index):
            records.append(
                {
                    "image_reference": f"{DATASET_FILE}#row={item['row_index']}",
                    "row_index": item["row_index"],
                    "image_path": item["image_path"],
                    "image_sha256": item["image_sha256"],
                    "dataset_label": class_name,
                    "class_id": class_ids[class_name],
                    "class_index": TARGET_CLASSES.index(class_name),
                    "common_name": CLASS_INFO[class_name]["common_name"],
                    "scientific_name": CLASS_INFO[class_name]["scientific_name"],
                    "license": LICENSE,
                    "width": item["width"],
                    "height": item["height"],
                    "split": split,
                }
            )
        per_class_counts[class_name] = {
            "total": len(items),
            "dataset_rows": label_counts[class_name],
            "duplicate_rows_excluded": duplicate_rows_excluded[class_name],
            "train": allocated["train"],
            "validation": allocated["validation"],
            "test": allocated["test"],
            "corrupt": failed_by_label[class_name],
        }

    split_hashes: dict[str, set[str]] = defaultdict(set)
    for record in records:
        split_hashes[record["split"]].add(record["image_sha256"])
    overlap = (split_hashes["train"] & split_hashes["validation"]) | (
        split_hashes["train"] & split_hashes["test"]
    ) | (split_hashes["validation"] & split_hashes["test"])
    if overlap:
        raise ValueError(f"Image hashes leaked across splits: {len(overlap)} duplicate hash(es)")

    result = {
        "dataset": DATASET_ID,
        "dataset_url": DATASET_URL,
        "revision": DATASET_REVISION,
        "source_file": DATASET_FILE,
        "parquet_path": str(parquet_path),
        "source_file_bytes": parquet_path.stat().st_size,
        "rows": parquet.metadata.num_rows,
        "row_groups": parquet.metadata.num_row_groups,
        "class_count": len(labels),
        "label_names": labels,
        "label_counts": dict(label_counts),
        "license": LICENSE,
        "attribution": ATTRIBUTION,
        "seed": seed,
        "split_ratios": {"train": 0.70, "validation": 0.15, "test": 0.15},
        "target_classes": per_class_counts,
        "usable_target_images": len(records),
        "corrupt_images": total_corrupt,
        "missing_images": total_missing,
        "duplicate_rows_excluded": sum(duplicate_rows_excluded.values()),
        "duplicate_image_hashes": sum(duplicate_rows_excluded.values()),
        "image_bytes_cached": False,
        "images_extracted_to_files": False,
        "index_generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "records": records,
    }
    index_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = index_path.with_suffix(index_path.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(index_path)
    return result


class DimpsarLocalDataset(Dataset):
    """PyTorch Dataset reading image bytes lazily from the cached Parquet shard."""

    def __init__(
        self,
        index_path: str | Path = DEFAULT_INDEX,
        split: str = "train",
        transform: Callable[[Image.Image], Any] | None = None,
    ) -> None:
        if split not in {"train", "validation", "test"}:
            raise ValueError(f"Unknown split: {split}")
        self.index_path = Path(index_path)
        self.index = json.loads(self.index_path.read_text(encoding="utf-8"))
        self.parquet_path = _resolve_parquet_path(self.index["parquet_path"])
        self.records = [record for record in self.index["records"] if record["split"] == split]
        self.transform = transform
        self._image_bytes: dict[int, bytes] = {}
        self._load_selected_image_bytes()

    def __len__(self) -> int:
        return len(self.records)

    def _load_selected_image_bytes(self) -> None:
        import pyarrow.parquet as pq

        selected = {record["row_index"]: record for record in self.records}
        parquet = pq.ParquetFile(self.parquet_path)
        row_start = 0
        for group_id in range(parquet.metadata.num_row_groups):
            group_size = parquet.metadata.row_group(group_id).num_rows
            group_end = row_start + group_size
            wanted = {row for row in selected if row_start <= row < group_end}
            if wanted:
                rows = parquet.read_row_group(group_id, columns=["image", "label"]).to_pylist()
                for row_index in wanted:
                    row = rows[row_index - row_start]
                    record = selected[row_index]
                    if row["label"] != record["class_id"]:
                        raise ValueError(f"Index label mismatch at row {row_index}")
                    self._image_bytes[row_index] = row["image"]["bytes"]
            row_start = group_end
        if len(self._image_bytes) != len(self.records):
            raise ValueError("Some indexed rows could not be read from the cached Parquet shard.")

    def __getitem__(self, index: int) -> tuple[Any, int]:
        record = self.records[index]
        image_bytes = self._image_bytes[record["row_index"]]
        with Image.open(io.BytesIO(image_bytes)) as source:
            source.load()
            image = source.convert("RGB")
        if self.transform is not None:
            image = self.transform(image)
        return image, record["class_index"]


if __name__ == "__main__":
    summary = build_local_index()
    print(f"rows={summary['rows']} classes={summary['class_count']} usable={summary['usable_target_images']}")
    print("class | total | train | validation | test")
    for name, counts in summary["target_classes"].items():
        print(f"{name} | {counts['total']} | {counts['train']} | {counts['validation']} | {counts['test']}")
