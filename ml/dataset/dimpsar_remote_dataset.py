"""Selective, in-memory access to DIMPSAR rows through the HF Dataset Viewer API."""

from __future__ import annotations

import csv
import io
import json
import random
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.parse import urlencode

import requests
import torch
from PIL import Image, UnidentifiedImageError
from torch.utils.data import Dataset

DATASET_ID = "Project-AgML/DIMPSAR_medicinal_plant_classification"
DATASET_URL = f"https://huggingface.co/datasets/{DATASET_ID}"
API_ROOT = "https://datasets-server.huggingface.co"
FILTER_URL = f"{API_ROOT}/filter"
ROWS_URL = f"{API_ROOT}/rows"
INFO_URL = f"{API_ROOT}/info"
SPLIT = "train"
CONFIG = "default"
LICENSE = "CC BY 4.0"
ATTRIBUTION = (
    "DIMPSAR: Dataset for Indian medicinal plant species analysis and recognition, "
    "B. R. Pushpa and N. Shobha Rani, Data in Brief 49 (2023), 109388. "
    "Dataset card: https://huggingface.co/datasets/Project-AgML/"
    "DIMPSAR_medicinal_plant_classification (CC BY 4.0)."
)
DATASET_DIR = Path(__file__).resolve().parent
CLASS_CSV = DATASET_DIR / "dimpsar_classes.csv"
DEFAULT_INDEX = DATASET_DIR / "remote_index.json"
PAGE_SIZE = 10
DEFAULT_SEED = 42


class RemoteDatasetError(RuntimeError):
    """Raised when the viewer response cannot be safely interpreted."""


@dataclass(frozen=True)
class ClassInfo:
    dataset_label: str
    common_name: str
    scientific_name: str
    label_id: int


@dataclass(frozen=True)
class RemoteRecord:
    row_idx: int
    label_id: int
    dataset_label: str
    image_reference: str
    license: str = LICENSE
    image_url: str | None = None


class DimpsarRemoteClient:
    """Fetch only class-filtered row metadata and individual image responses."""

    def __init__(
        self,
        timeout: tuple[float, float] = (10.0, 30.0),
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        page_size: int = PAGE_SIZE,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not 1 <= page_size <= PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {PAGE_SIZE}")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        self.timeout = timeout
        self.max_retries = min(max_retries, 3)
        self.backoff_seconds = backoff_seconds
        self.page_size = page_size
        self._sleep = sleep
        self.response_bytes = 0
        self.retry_count = 0
        self.request_count = 0
        self.http_failures = 0

    def _request(self, url: str, params: dict[str, Any] | None = None) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self.request_count += 1
            response: requests.Response | None = None
            try:
                response = requests.get(url, params=params, timeout=self.timeout)
                body = response.content
                self.response_bytes += len(body)
                if response.status_code in {408, 425, 429} or response.status_code >= 500:
                    self.http_failures += 1
                    response.raise_for_status()
                response.raise_for_status()
                return response
            except (requests.RequestException, OSError) as error:
                last_error = error
                should_retry = (
                    response is None
                    or response.status_code in {408, 425, 429}
                    or response.status_code >= 500
                )
                if not should_retry or attempt >= self.max_retries:
                    break
                self.retry_count += 1
                delay = min(self.backoff_seconds * (2**attempt), 12.0)
                self._sleep(delay)
        raise RemoteDatasetError(
            f"Request failed after {self.max_retries + 1} attempt(s): {url}: {last_error}"
        ) from last_error

    def _query_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        response = self._request(url, params=params)
        try:
            payload = response.json()
        except ValueError as error:
            raise RemoteDatasetError(f"Viewer returned invalid JSON from {response.url}") from error
        if not isinstance(payload, dict):
            raise RemoteDatasetError(f"Expected a JSON object from {response.url}")
        return payload

    def discover_classes(self, class_csv: Path = CLASS_CSV) -> tuple[list[ClassInfo], list[str]]:
        if not class_csv.is_file():
            raise FileNotFoundError(f"Verified DIMPSAR class list not found: {class_csv}")
        with class_csv.open(encoding="utf-8-sig", newline="") as stream:
            requested = list(csv.DictReader(stream))
        if not requested:
            raise RemoteDatasetError("The verified DIMPSAR class CSV is empty.")

        # /info contains schema metadata only, so discovery does not read any dataset rows.
        payload = self._query_json(
            INFO_URL,
            {
                "dataset": DATASET_ID,
                "config": CONFIG,
                "split": SPLIT,
            },
        )
        dataset_info = payload.get("dataset_info", {})
        config_info = dataset_info.get(CONFIG, dataset_info)
        features = config_info.get("features", {})
        label_feature = features.get("label", {}) if isinstance(features, dict) else {}
        names = label_feature.get("names")
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            raise RemoteDatasetError("Dataset Viewer did not provide the label ClassLabel name list.")
        name_to_id: dict[str, int] = {}
        for label_id, name in enumerate(names):
            if name in name_to_id:
                raise RemoteDatasetError(f"Duplicate label name in actual dataset metadata: {name}")
            name_to_id[name] = label_id

        selected: list[ClassInfo] = []
        for row in requested:
            label = row.get("dataset_label", "").strip()
            if label not in name_to_id:
                raise RemoteDatasetError(f"Verified class {label!r} is absent from actual dataset labels.")
            selected.append(ClassInfo(
                dataset_label=label,
                common_name=row.get("common_name", "").strip(),
                scientific_name=row.get("scientific_name", "").strip(),
                label_id=name_to_id[label],
            ))
        return selected, names

    def fetch_class_rows(self, class_info: ClassInfo) -> tuple[list[RemoteRecord], int]:
        payload = self._query_json(
            FILTER_URL,
            {
                "dataset": DATASET_ID,
                "config": CONFIG,
                "split": SPLIT,
                "where": f'"label"={class_info.label_id}',
                "offset": 0,
                "length": self.page_size,
            },
        )
        rows = payload.get("rows")
        total = payload.get("num_rows_total")
        if not isinstance(rows, list) or not isinstance(total, int) or total < 0:
            raise RemoteDatasetError(f"Malformed filtered page for {class_info.dataset_label}.")

        records_by_row: dict[int, RemoteRecord] = {}
        for item in rows:
            row = item.get("row", {})
            label_id = row.get("label")
            image = row.get("image")
            row_idx = item.get("row_idx")
            if label_id != class_info.label_id:
                raise RemoteDatasetError(
                    f"Filter leakage: requested {class_info.dataset_label} ({class_info.label_id}) "
                    f"but received label {label_id!r}."
                )
            if not isinstance(row_idx, int) or not isinstance(image, dict) or not image.get("src"):
                raise RemoteDatasetError(f"Malformed image row for {class_info.dataset_label}.")
            record = RemoteRecord(
                row_idx=row_idx,
                label_id=class_info.label_id,
                dataset_label=class_info.dataset_label,
                image_reference=f"{ROWS_URL}?{urlencode({'dataset': DATASET_ID, 'config': CONFIG, 'split': SPLIT, 'offset': row_idx, 'length': 1})}",
                image_url=str(image["src"]),
            )
            records_by_row.setdefault(row_idx, record)
        return list(records_by_row.values()), total

    def _get_image_url(self, record: RemoteRecord, refresh: bool = False) -> str:
        if record.image_url and not refresh:
            return record.image_url
        from urllib.parse import parse_qs, urlparse

        query = {key: values[0] for key, values in parse_qs(urlparse(record.image_reference).query).items()}
        payload = self._query_json(ROWS_URL, query)
        rows = payload.get("rows", [])
        if len(rows) != 1:
            raise RemoteDatasetError(f"Could not refresh image reference for row {record.row_idx}.")
        row = rows[0].get("row", {})
        if row.get("label") != record.label_id:
            raise RemoteDatasetError(f"Row {record.row_idx} no longer matches its verified class label.")
        image = row.get("image")
        if not isinstance(image, dict) or not image.get("src"):
            raise RemoteDatasetError(f"No image bytes reference returned for row {record.row_idx}.")
        return str(image["src"])

    def fetch_image(self, record: RemoteRecord, min_dimension: int = 32) -> Image.Image:
        try:
            response = self._request(self._get_image_url(record))
        except RemoteDatasetError:
            if not record.image_url:
                raise
            response = self._request(self._get_image_url(record, refresh=True))
        raw = response.content
        try:
            with Image.open(io.BytesIO(raw)) as source:
                width, height = source.size
                if width < min_dimension or height < min_dimension or width > 12000 or height > 12000:
                    raise RemoteDatasetError(
                        f"Rejected image dimensions {width}x{height} at row {record.row_idx}."
                    )
                source.load()
                return source.convert("RGB")
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
            raise RemoteDatasetError(f"Corrupted or unsupported image at row {record.row_idx}: {error}") from error

    def write_index(
        self,
        classes: Sequence[ClassInfo],
        records_by_class: dict[str, Sequence[RemoteRecord]],
        available_by_class: dict[str, int],
        path: Path = DEFAULT_INDEX,
    ) -> None:
        index = {
            "dataset": DATASET_ID,
            "dataset_url": DATASET_URL,
            "dataset_viewer_filter_api": FILTER_URL,
            "split": SPLIT,
            "license": LICENSE,
            "attribution": ATTRIBUTION,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "cache_contents": "metadata only; image bytes and signed URLs are not stored",
            "classes": [],
        }
        for class_info in classes:
            class_records = records_by_class[class_info.dataset_label]
            index["classes"].append({
                **asdict(class_info),
                "available_rows": available_by_class[class_info.dataset_label],
                "records": [
                    {
                        "row_idx": record.row_idx,
                        "label_id": record.label_id,
                        "dataset_label": record.dataset_label,
                        "image_reference": record.image_reference,
                        "license": record.license,
                    }
                    for record in class_records
                ],
            })
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temp.replace(path)


class DimpsarRemoteDataset(Dataset):
    """PyTorch Dataset whose records are class-filtered and whose images stay in memory."""

    def __init__(
        self,
        records: Sequence[RemoteRecord],
        classes: Sequence[ClassInfo],
        client: DimpsarRemoteClient | None = None,
        transform: Callable[[Image.Image], Any] | None = None,
        output_size: tuple[int, int] = (224, 224),
    ) -> None:
        self.classes = tuple(classes)
        self.class_to_index = {info.dataset_label: index for index, info in enumerate(classes)}
        self.records = tuple(records)
        self.client = client or DimpsarRemoteClient()
        self.transform = transform
        self.output_size = output_size

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> tuple[Any, int]:
        record = self.records[index]
        image = self.client.fetch_image(record)
        if self.transform is not None:
            image_value: Any = self.transform(image)
        else:
            image = image.resize(self.output_size, Image.Resampling.BILINEAR)
            pixels = torch.frombuffer(bytearray(image.tobytes()), dtype=torch.uint8)
            image_value = pixels.reshape(image.height, image.width, 3).permute(2, 0, 1).float().div_(255.0)
        return image_value, self.class_to_index[record.dataset_label]


def deterministic_splits(
    records_by_class: dict[str, Sequence[RemoteRecord]],
    seed: int = DEFAULT_SEED,
    max_images_per_class: int | None = None,
) -> dict[str, dict[str, list[RemoteRecord]]]:
    """Balance by downsampling to the smallest class, then stratify deterministically."""
    if not records_by_class or any(not records for records in records_by_class.values()):
        raise ValueError("Every target class must have at least one available row.")
    target_count = min(len(records) for records in records_by_class.values())
    if max_images_per_class is not None:
        if max_images_per_class < 1:
            raise ValueError("max_images_per_class must be positive.")
        target_count = min(target_count, max_images_per_class)

    output = {name: {split: [] for split in ("train", "validation", "test")} for name in records_by_class}
    for class_offset, (label, class_records) in enumerate(records_by_class.items()):
        candidates = list(class_records)
        random.Random(seed + class_offset).shuffle(candidates)
        candidates = candidates[:target_count]
        n_train = int(target_count * 0.70 + 0.5)
        n_validation = int(target_count * 0.15 + 0.5)
        n_test = target_count - n_train - n_validation
        if min(n_train, n_validation, n_test) < 1:
            raise ValueError("Not enough examples per class for non-empty 70/15/15 splits.")
        output[label]["train"] = candidates[:n_train]
        output[label]["validation"] = candidates[n_train:n_train + n_validation]
        output[label]["test"] = candidates[n_train + n_validation:]
    return output


def collect_remote_index(
    client: DimpsarRemoteClient | None = None,
    class_csv: Path = CLASS_CSV,
    index_path: Path = DEFAULT_INDEX,
) -> tuple[DimpsarRemoteClient, list[ClassInfo], dict[str, list[RemoteRecord]], dict[str, int]]:
    client = client or DimpsarRemoteClient()
    classes, _ = client.discover_classes(class_csv)
    records_by_class: dict[str, list[RemoteRecord]] = {}
    available_by_class: dict[str, int] = {}
    for class_info in classes:
        records, available = client.fetch_class_rows(class_info)
        records_by_class[class_info.dataset_label] = records
        available_by_class[class_info.dataset_label] = available
        print(f"Indexed {class_info.dataset_label}: {len(records)} returned / {available} available", flush=True)
    client.write_index(classes, records_by_class, available_by_class, index_path)
    return client, classes, records_by_class, available_by_class


def load_remote_index(path: Path = DEFAULT_INDEX) -> tuple[list[ClassInfo], dict[str, list[RemoteRecord]]]:
    """Load the metadata-only index; image URLs will be refreshed per selected row."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("dataset") != DATASET_ID or payload.get("license") != LICENSE:
        raise RemoteDatasetError("Remote index dataset/license does not match DIMPSAR CC BY 4.0.")
    classes: list[ClassInfo] = []
    records_by_class: dict[str, list[RemoteRecord]] = {}
    for item in payload.get("classes", []):
        info = ClassInfo(
            dataset_label=str(item["dataset_label"]),
            common_name=str(item["common_name"]),
            scientific_name=str(item.get("scientific_name", "")),
            label_id=int(item["label_id"]),
        )
        classes.append(info)
        records_by_class[info.dataset_label] = [
            RemoteRecord(
                row_idx=int(record["row_idx"]),
                label_id=int(record["label_id"]),
                dataset_label=str(record["dataset_label"]),
                image_reference=str(record["image_reference"]),
                license=str(record["license"]),
            )
            for record in item.get("records", [])
        ]
    if not classes or any(not records_by_class.get(info.dataset_label) for info in classes):
        raise RemoteDatasetError("Remote metadata index has missing classes or row references.")
    return classes, records_by_class
