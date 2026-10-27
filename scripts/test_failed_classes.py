"""One-page selective-access test for DIMPSAR Amla and Ashwagandha."""

from __future__ import annotations

import gc
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.dataset.dimpsar_remote_dataset import (  # noqa: E402
    CLASS_CSV,
    DATASET_ID,
    FILTER_URL,
    INFO_URL,
    ROWS_URL,
    ClassInfo,
    DimpsarRemoteClient,
    RemoteRecord,
    RemoteDatasetError,
)

TARGETS = (("Amla", 1), ("Ashwagandha", 5))


def row_fallback(client: DimpsarRemoteClient, record: RemoteRecord) -> RemoteRecord:
    """Refresh one already-selected row; /rows cannot search by class label."""
    payload = client._query_json(
        ROWS_URL,
        {
            "dataset": DATASET_ID,
            "config": "default",
            "split": "train",
            "offset": record.row_idx,
            "length": 1,
        },
    )
    rows = payload.get("rows", [])
    if len(rows) != 1:
        raise RemoteDatasetError(f"/rows returned no unique row for global row index {record.row_idx}.")
    row = rows[0].get("row", {})
    if row.get("label") != record.label_id:
        raise RemoteDatasetError(
            f"/rows label mismatch for {record.dataset_label}: got {row.get('label')!r}."
        )
    image = row.get("image", {})
    if not isinstance(image, dict) or not image.get("src"):
        raise RemoteDatasetError(f"/rows provided no image reference for row {record.row_idx}.")
    return replace(record, image_url=str(image["src"]))


def main() -> int:
    client = DimpsarRemoteClient(page_size=5, max_retries=0, backoff_seconds=1.0, timeout=(8.0, 25.0))
    target_metadata = {}
    with CLASS_CSV.open(encoding="utf-8-sig", newline="") as stream:
        import csv

        for item in csv.DictReader(stream):
            if item["common_name"] in {"Amla", "Ashwagandha"}:
                target_metadata[item["common_name"]] = item

    # Verify the supplied numeric IDs against the live ClassLabel schema once.
    schema_error = None
    try:
        schema = client._query_json(
            INFO_URL,
            {"dataset": DATASET_ID, "config": "default", "split": "train"},
        )
        info = schema.get("dataset_info", {}).get("default", schema.get("dataset_info", {}))
        labels = info.get("features", {}).get("label", {}).get("names", [])
        for name, label_id in TARGETS:
            if label_id >= len(labels) or labels[label_id] != name:
                raise RuntimeError(f"Live label schema does not map {label_id} to {name!r}.")
    except Exception as error:
        schema_error = str(error)
        labels = []

    results = []
    print(f"Dataset: {DATASET_ID}")
    print("Filter strategy: one request/class, length=5, offset=0; no retries")
    print("Fallback: /rows only for already identified global row indices")

    for common_name, label_id in TARGETS:
        metadata = target_metadata.get(common_name, {})
        dataset_label = metadata.get("dataset_label", common_name)
        result = {
            "class": common_name,
            "class_id": label_id,
            "method": "Dataset Viewer /filter (length=5)",
            "tested": 0,
            "successful": 0,
            "failed": 0,
            "bytes": 0,
        }
        before_bytes = client.response_bytes

        if schema_error:
            result["method"] = "schema verification failed"
            result["failed"] = 1
            print(f"  {common_name}: live class-ID verification failed: {schema_error}")
        else:
            class_info = ClassInfo(
                dataset_label=dataset_label,
                common_name=common_name,
                scientific_name=metadata.get("scientific_name", ""),
                label_id=label_id,
            )
            try:
                records, _available = client.fetch_class_rows(class_info)
                for record in records[:5]:
                    result["tested"] += 1
                    image = None
                    try:
                        image = client.fetch_image(record)
                        if image.mode != "RGB" or image.width < 32 or image.height < 32:
                            raise RuntimeError(f"Invalid decoded size/mode: {image.size}, {image.mode}.")
                        result["successful"] += 1
                        print(
                            f"  {common_name}: row={record.row_idx}, label={record.dataset_label}, "
                            f"size={image.width}x{image.height}, PIL={image.mode}"
                        )
                    except Exception as image_error:
                        # One direct-row lookup is useful only after /filter supplied a row index.
                        try:
                            refreshed = row_fallback(client, record)
                            image = client.fetch_image(refreshed)
                            if image.mode != "RGB" or image.width < 32 or image.height < 32:
                                raise RuntimeError(f"Invalid decoded size/mode: {image.size}, {image.mode}.")
                            result["successful"] += 1
                            result["method"] = "Dataset Viewer /filter + /rows fallback"
                            print(
                                f"  {common_name}: row={record.row_idx}, label={record.dataset_label}, "
                                f"size={image.width}x{image.height}, PIL={image.mode} (via /rows refresh)"
                            )
                        except Exception as fallback_error:
                            result["failed"] += 1
                            print(
                                f"  FAILED {common_name} row={record.row_idx}: "
                                f"image={image_error}; /rows fallback={fallback_error}"
                            )
                    finally:
                        if image is not None:
                            image.close()
                            del image
                        gc.collect()
                if len(records) < 5:
                    result["failed"] += 5 - len(records)
            except Exception as filter_error:
                result["method"] = "Dataset Viewer /filter failed; /rows cannot class-filter"
                result["failed"] = 1
                print(
                    f"  FAILED {common_name} (id={label_id}): {filter_error}\n"
                    "  /rows fallback unavailable: no matching global row indexes; /rows accepts only offset/length."
                )

        result["bytes"] = client.response_bytes - before_bytes
        results.append(result)

    print("\nClass | class ID | access method | images tested | successful | failed | bytes transferred")
    for row in results:
        print(
            f"{row['class']} | {row['class_id']} | {row['method']} | {row['tested']} | "
            f"{row['successful']} | {row['failed']} | {row['bytes']:,}"
        )
    print(f"\nTotal images tested: {sum(int(row['tested']) for row in results)}")
    print(f"Total successful: {sum(int(row['successful']) for row in results)}")
    print(f"Total failed: {sum(int(row['failed']) for row in results)}")
    print(f"Approximate response bytes: {client.response_bytes:,}")
    print(f"Additional /rows refresh calls: {sum(1 for row in results if '/rows fallback' in str(row['method']))}")
    print("Complete Parquet downloaded: NO")
    print("Image files saved locally: NO")
    return 0 if all(int(row["successful"]) == 5 for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
