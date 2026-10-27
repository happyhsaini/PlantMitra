"""One-pass final test evaluation for the selected DIMPSAR checkpoint."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import torch
import yaml
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

from ml.dataset.dimpsar_local_dataset import DEFAULT_INDEX, DimpsarLocalDataset, TARGET_CLASSES
from ml.models.architecture import create_mobilenet_v3_small, inference_transform
from torch.utils.data import DataLoader

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "ml/evaluation"
MODEL_PATH = PROJECT_ROOT / "ml/models/plantmitra_mobilenetv3_small.pth"
METADATA_PATH = PROJECT_ROOT / "ml/models/plantmitra_model_metadata.json"
CONFIG_PATH = PROJECT_ROOT / "ml/training/config.yaml"


def evaluate_saved_checkpoint(write_outputs: bool = True) -> dict[str, Any]:
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    classes = metadata["classes"]
    if [row["dataset_label"] for row in classes] != list(TARGET_CLASSES):
        raise ValueError("Saved checkpoint metadata has an unexpected class ordering.")
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    dataset = DimpsarLocalDataset(
        index_path=DEFAULT_INDEX,
        split="test",
        transform=inference_transform(),
    )
    loader = DataLoader(dataset, batch_size=int(config["batch_size"]), shuffle=False, num_workers=0)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = create_mobilenet_v3_small(len(classes), device)
    checkpoint = torch.load(MODEL_PATH, map_location=device, weights_only=True)
    if checkpoint["classes"] != classes:
        raise ValueError("Checkpoint class mapping differs from model metadata.")
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    model.eval()
    truths: list[int] = []
    predictions: list[int] = []
    loss_total = 0.0
    criterion = torch.nn.CrossEntropyLoss(reduction="sum")
    with torch.inference_mode():
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            logits = model(images)
            loss_total += float(criterion(logits, labels).item())
            truths.extend(labels.cpu().tolist())
            predictions.extend(logits.argmax(dim=1).cpu().tolist())
    if len(truths) != len(dataset):
        raise RuntimeError(f"Evaluated {len(truths)} test samples; expected {len(dataset)}.")

    label_ids = list(range(len(classes)))
    matrix = confusion_matrix(truths, predictions, labels=label_ids)
    precision, recall, f1, support = precision_recall_fscore_support(
        truths, predictions, labels=label_ids, zero_division=0
    )
    per_class = []
    for index, row in enumerate(classes):
        per_class.append(
            {
                "class_index": index,
                "dataset_label": row["dataset_label"],
                "common_name": row["common_name"],
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
                "support": int(support[index]),
            }
        )
    result = {
        "test_images": len(truths),
        "accuracy": sum(a == b for a, b in zip(truths, predictions)) / len(truths),
        "loss": loss_total / len(truths),
        "macro_precision": float(precision.mean()),
        "macro_recall": float(recall.mean()),
        "macro_f1": float(f1.mean()),
        "per_class": per_class,
        "confusion_matrix": matrix.tolist(),
    }
    if write_outputs:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        report_path = OUTPUT_DIR / "classification_report.csv"
        with report_path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=list(per_class[0]))
            writer.writeheader()
            writer.writerows(per_class)
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        names = [row["common_name"] for row in classes]
        figure, axis = plt.subplots(figsize=(8, 7), constrained_layout=True)
        plot = axis.imshow(matrix, cmap="Greens")
        figure.colorbar(plot, ax=axis, fraction=0.046, pad=0.04)
        axis.set_xticks(label_ids, names, rotation=40, ha="right")
        axis.set_yticks(label_ids, names)
        axis.set_xlabel("Predicted class")
        axis.set_ylabel("True class")
        axis.set_title("DIMPSAR test confusion matrix")
        threshold = matrix.max() / 2 if matrix.size else 0
        for row in range(matrix.shape[0]):
            for column in range(matrix.shape[1]):
                axis.text(
                    column,
                    row,
                    str(matrix[row, column]),
                    ha="center",
                    va="center",
                    color="white" if matrix[row, column] > threshold else "black",
                )
        figure.savefig(OUTPUT_DIR / "confusion_matrix.png", dpi=180)
        plt.close(figure)
        (OUTPUT_DIR / "final_test_metrics.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return result


if __name__ == "__main__":
    print(json.dumps(evaluate_saved_checkpoint(), indent=2, ensure_ascii=False))
