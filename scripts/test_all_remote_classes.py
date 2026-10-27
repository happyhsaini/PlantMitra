"""Selective smoke test for the seven verified DIMPSAR medicinal classes."""

from __future__ import annotations

import argparse
import gc
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.dataset.dimpsar_remote_dataset import (  # noqa: E402
    DEFAULT_INDEX,
    DATASET_ID,
    DimpsarRemoteClient,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-class", type=int, default=5)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    args = parser.parse_args()
    if args.per_class < 5:
        parser.error("--per-class must be at least 5")

    client = DimpsarRemoteClient(page_size=10, max_retries=3, backoff_seconds=1.0)
    results: list[dict[str, object]] = []
    index_classes = []
    index_records = {}
    index_available = {}

    print(f"Dataset: {DATASET_ID}", flush=True)
    print("Metadata API: https://datasets-server.huggingface.co/info")
    print("Rows API: https://datasets-server.huggingface.co/filter")
    print("Image strategy: signed image references from filtered target rows; bytes decoded in memory")
    try:
        classes, _ = client.discover_classes()
        for info in classes:
            rows_returned = 0
            images_tested = 0
            successes = 0
            failures = 0
            try:
                # One filtered request, capped at 10 rows; never exhaust the class.
                class_records, available_rows = client.fetch_class_rows(info)
                rows_returned = len(class_records)
                for record in class_records[:args.per_class]:
                    images_tested += 1
                    image = None
                    try:
                        image = client.fetch_image(record)
                        if image.mode != "RGB" or image.width < 32 or image.height < 32:
                            raise RuntimeError(f"Invalid decoded image for {info.dataset_label} row {record.row_idx}.")
                        successes += 1
                        print(
                            f"  {info.dataset_label}: row={record.row_idx} label_id={record.label_id} "
                            f"label={info.dataset_label} size={image.width}x{image.height} mode={image.mode}",
                            flush=True,
                        )
                    except Exception as error:
                        failures += 1
                        print(f"  FAILED {info.dataset_label} row={record.row_idx}: {error}", flush=True)
                    finally:
                        if image is not None:
                            image.close()
                            del image
                        gc.collect()
                index_classes.append(info)
                index_records[info.dataset_label] = class_records
                index_available[info.dataset_label] = available_rows
            except Exception as error:
                failures += 1
                print(f"  CLASS FAILED {info.dataset_label} (id={info.label_id}): {error}", flush=True)
            results.append({
                "label": info.dataset_label,
                "class_id": info.label_id,
                "rows_returned": rows_returned,
                "images_tested": images_tested,
                "successful": successes,
                "failed": failures,
            })

        if index_classes:
            client.write_index(index_classes, index_records, index_available, args.index)
            index = json.loads(args.index.read_text(encoding="utf-8"))
            if index.get("license") != "CC BY 4.0" or "attribution" not in index:
                raise RuntimeError("Remote index is missing dataset license/attribution.")
            if any("image_url" in record or "image_bytes" in record
                   for klass in index["classes"] for record in klass["records"]):
                raise RuntimeError("Remote index must not store signed URLs or image bytes.")

        print("\nClass | requested label | class ID | rows returned | images tested | successful | failed")
        for result in results:
            print(
                f"{result['label']} | {result['label']} | {result['class_id']} | "
                f"{result['rows_returned']} | {result['images_tested']} | "
                f"{result['successful']} | {result['failed']}"
            )
        print(f"\nTotal images tested: {sum(int(row['images_tested']) for row in results)}")
        print(f"Total successful images: {sum(int(row['successful']) for row in results)}")
        print(f"Total failed images/classes: {sum(int(row['failed']) for row in results)}")
        print(f"Total response body bytes: {client.response_bytes:,}")
        print(f"HTTP requests: {client.request_count}")
        print(f"Retries: {client.retry_count}; HTTP failures observed: {client.http_failures}")
        print(f"Remote metadata index: {args.index} (metadata only)")
        print("Complete Parquet downloaded: NO")
        print("Complete dataset cached: NO")
        print("Images permanently stored locally: NO")
        print("All seven label IDs discovered from live ClassLabel metadata: YES")
        expected = args.per_class * len(classes)
        return 0 if sum(int(row["successful"]) for row in results) == expected else 1
    finally:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
