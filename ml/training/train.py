"""Train the seven-class DIMPSAR classifier from the verified local split index."""

from __future__ import annotations

import argparse
import csv
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import yaml
from torch.utils.data import DataLoader
from torchvision import transforms

from ml.dataset.dimpsar_local_dataset import DEFAULT_INDEX, DimpsarLocalDataset, TARGET_CLASSES
from ml.models.architecture import create_mobilenet_v3_small

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "ml/training/config.yaml"
MODEL_DIR = PROJECT_ROOT / "ml/models"
EVALUATION_DIR = PROJECT_ROOT / "ml/evaluation"
MODEL_PATH = MODEL_DIR / "plantmitra_mobilenetv3_small.pth"
METADATA_PATH = MODEL_DIR / "plantmitra_model_metadata.json"
HISTORY_PATH = EVALUATION_DIR / "training_history.csv"


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if config["dataset_index"] != str(DEFAULT_INDEX.relative_to(PROJECT_ROOT)).replace("\\", "/"):
        raise ValueError("Training must use the verified local DIMPSAR index.")
    return config


def class_mapping(index: dict[str, Any]) -> list[dict[str, Any]]:
    mapping = []
    for class_index, label in enumerate(TARGET_CLASSES):
        stats = index["target_classes"].get(label)
        if not stats or stats["total"] < 1:
            raise RuntimeError(f"Verified local split has no usable images for {label}.")
        sample = next(item for item in index["records"] if item["dataset_label"] == label)
        if sample["class_index"] != class_index:
            raise RuntimeError(f"Stored class index differs for {label}.")
        mapping.append(
            {
                "class_index": class_index,
                "dataset_label": label,
                "common_name": sample["common_name"],
                "scientific_name": sample["scientific_name"],
                "source_class_id": sample["class_id"],
            }
        )
    return mapping


def image_transforms(config: dict[str, Any]) -> tuple[Any, Any]:
    size = int(config["image_size"])
    mean = config["normalization"]["mean"]
    std = config["normalization"]["std"]
    train_transform = transforms.Compose(
        [
            transforms.RandomResizedCrop(size, scale=(0.78, 1.0)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomRotation(degrees=10),
            transforms.ColorJitter(brightness=0.10, contrast=0.10, saturation=0.08),
            transforms.ToTensor(),
            transforms.Normalize(mean=mean, std=std),
        ]
    )
    evaluation_transform = transforms.Compose(
        [
            transforms.Resize(int(size * 256 / 224)),
            transforms.CenterCrop(size),
            transforms.ToTensor(),
            transforms.Normalize(mean=mean, std=std),
        ]
    )
    return train_transform, evaluation_transform


def make_loader(
    split: str,
    config: dict[str, Any],
    generator: torch.Generator,
) -> DataLoader:
    train_transform, evaluation_transform = image_transforms(config)
    transform = train_transform if split == "train" else evaluation_transform
    dataset = DimpsarLocalDataset(index_path=DEFAULT_INDEX, split=split, transform=transform)
    return DataLoader(
        dataset,
        batch_size=int(config["batch_size"]),
        shuffle=(split == "train"),
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
        generator=generator if split == "train" else None,
    )


def set_backbone_trainable(model: torch.nn.Module, enabled: bool) -> None:
    for parameter in model.features.parameters():
        parameter.requires_grad = False
    if enabled:
        for block in list(model.features.children())[-2:]:
            for parameter in block.parameters():
                parameter.requires_grad = True


def make_optimizer(model: torch.nn.Module, config: dict[str, Any], fine_tune: bool):
    groups = [{"params": model.classifier.parameters(), "lr": config["learning_rate"]}]
    if fine_tune:
        groups.append(
            {
                "params": [p for p in model.features.parameters() if p.requires_grad],
                "lr": config["backbone_learning_rate"],
            }
        )
    return torch.optim.AdamW(groups, weight_decay=float(config["weight_decay"]))


def run_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    loss_fn: torch.nn.Module,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None = None,
    train_backbone: bool = False,
) -> dict[str, float | int]:
    training = optimizer is not None
    model.train(training)
    if training and not train_backbone:
        model.features.eval()
    loss_sum = 0.0
    correct = 0
    count = 0
    with torch.set_grad_enabled(training):
        for images, labels in loader:
            images = images.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            if optimizer is not None:
                optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            loss = loss_fn(logits, labels)
            if optimizer is not None:
                loss.backward()
                optimizer.step()
            batch = labels.numel()
            loss_sum += float(loss.detach().item()) * batch
            correct += int((logits.detach().argmax(dim=1) == labels).sum().item())
            count += batch
    if count == 0:
        raise RuntimeError("The verified local split is empty.")
    return {"loss": loss_sum / count, "accuracy": correct / count, "count": count}


def plot_training_history(history: list[dict[str, Any]]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    epochs = [row["epoch"] for row in history]
    figure, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    axes[0].plot(epochs, [row["train_loss"] for row in history], label="Train")
    axes[0].plot(epochs, [row["validation_loss"] for row in history], label="Validation")
    axes[0].set(title="Loss", xlabel="Epoch", ylabel="Cross-entropy")
    axes[0].legend()
    axes[1].plot(epochs, [row["train_accuracy"] for row in history], label="Train")
    axes[1].plot(epochs, [row["validation_accuracy"] for row in history], label="Validation")
    axes[1].set(title="Accuracy", xlabel="Epoch", ylabel="Accuracy", ylim=(0, 1))
    axes[1].legend()
    figure.savefig(EVALUATION_DIR / "training_curves.png", dpi=160)
    plt.close(figure)


def train(config_path: Path = CONFIG_PATH) -> dict[str, Any]:
    from ml.evaluation.evaluate import evaluate_saved_checkpoint

    config = load_config(config_path)
    index_path = PROJECT_ROOT / config["dataset_index"]
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index.get("license") != "CC BY 4.0" or index.get("rows") != 5945:
        raise RuntimeError("The local DIMPSAR index does not match the verified dataset.")
    if index.get("usable_target_images") != 1041:
        raise RuntimeError("Verified image count changed; review the index before training.")
    classes = class_mapping(index)
    expected_splits = {"train": 728, "validation": 157, "test": 156}
    actual_splits = {
        split: sum(record["split"] == split for record in index["records"])
        for split in expected_splits
    }
    if actual_splits != expected_splits:
        raise RuntimeError(f"Verified split counts changed: {actual_splits}")
    train_counts = [index["target_classes"][name]["train"] for name in TARGET_CLASSES]
    imbalance_ratio = max(train_counts) / min(train_counts)
    weighted_loss = imbalance_ratio >= float(config["imbalance_weight_threshold"])

    seed = int(config["seed"])
    random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(int(config["cpu_threads"]))
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    generator = torch.Generator().manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = create_mobilenet_v3_small(len(classes), device)
    set_backbone_trainable(model, enabled=False)
    optimizer = make_optimizer(model, config, fine_tune=False)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=2, min_lr=float(config["minimum_learning_rate"])
    )
    if weighted_loss:
        weights = torch.tensor(
            [len(TARGET_CLASSES) * sum(train_counts) / (len(train_counts) * count) for count in train_counts],
            dtype=torch.float32,
            device=device,
        )
        loss_fn = torch.nn.CrossEntropyLoss(weight=weights)
        weighting = {name: round(float(weights[i]), 6) for i, name in enumerate(TARGET_CLASSES)}
    else:
        loss_fn = torch.nn.CrossEntropyLoss()
        weighting = None

    train_loader = make_loader("train", config, generator)
    validation_loader = make_loader("validation", config, generator)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    EVALUATION_DIR.mkdir(parents=True, exist_ok=True)
    best_checkpoint = MODEL_DIR / "plantmitra_mobilenetv3_small.best.pth"
    history: list[dict[str, Any]] = []
    best_accuracy = -1.0
    best_loss = float("inf")
    best_epoch = 0
    best_train_accuracy = 0.0
    stale_epochs = 0
    fine_tuned = False
    head_phase_baseline: tuple[float, float] | None = None
    started = time.perf_counter()

    for epoch in range(1, int(config["epochs"]) + 1):
        phase_fine_tuned = fine_tuned
        phase_head_lr = optimizer.param_groups[0]["lr"]
        phase_backbone_lr = optimizer.param_groups[1]["lr"] if fine_tuned else 0.0
        train_metrics = run_epoch(
            model,
            train_loader,
            loss_fn,
            device,
            optimizer=optimizer,
            train_backbone=fine_tuned,
        )
        validation_metrics = run_epoch(
            model,
            validation_loader,
            loss_fn,
            device,
        )
        if epoch == 1:
            head_phase_baseline = (
                float(validation_metrics["accuracy"]),
                float(validation_metrics["loss"]),
            )
        if epoch > int(config["freeze_epochs"]) and not fine_tuned and head_phase_baseline:
            head_improved = best_accuracy > head_phase_baseline[0] or (
                best_accuracy == head_phase_baseline[0] and best_loss < head_phase_baseline[1]
            )
            if head_improved:
                set_backbone_trainable(model, enabled=True)
                optimizer = make_optimizer(model, config, fine_tune=True)
                scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
                    optimizer,
                    mode="min",
                    factor=0.5,
                    patience=2,
                    min_lr=float(config["minimum_learning_rate"]),
                )
                fine_tuned = True
                print("Unfroze the final two MobileNet feature blocks after validation improvement.")
        scheduler.step(float(validation_metrics["loss"]))
        improved = validation_metrics["accuracy"] > best_accuracy or (
            validation_metrics["accuracy"] == best_accuracy and validation_metrics["loss"] < best_loss
        )
        if improved:
            best_accuracy = float(validation_metrics["accuracy"])
            best_loss = float(validation_metrics["loss"])
            best_train_accuracy = float(train_metrics["accuracy"])
            best_epoch = epoch
            stale_epochs = 0
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "classes": classes,
                    "architecture": "MobileNetV3-Small",
                    "epoch": epoch,
                },
                best_checkpoint,
            )
        else:
            stale_epochs += 1
        row = {
            "epoch": epoch,
            "train_loss": float(train_metrics["loss"]),
            "train_accuracy": float(train_metrics["accuracy"]),
            "validation_loss": float(validation_metrics["loss"]),
            "validation_accuracy": float(validation_metrics["accuracy"]),
            "head_learning_rate": phase_head_lr,
            "backbone_learning_rate": phase_backbone_lr,
            "fine_tuned": phase_fine_tuned,
        }
        history.append(row)
        print(
            f"Epoch {epoch}/{config['epochs']} | train loss {row['train_loss']:.4f} "
            f"acc {row['train_accuracy']:.4f} | val loss {row['validation_loss']:.4f} "
            f"acc {row['validation_accuracy']:.4f}"
        , flush=True)
        if stale_epochs >= int(config["early_stopping_patience"]):
            print("Early stopping: validation-selected model stopped improving.")
            break

    elapsed = time.perf_counter() - started
    if not best_checkpoint.is_file():
        raise RuntimeError("No validation-selected checkpoint was saved.")
    training_date = datetime.now(timezone.utc).isoformat()
    metadata = {
        "model_name": "MobileNetV3-Small",
        "num_classes": len(classes),
        "classes": classes,
        "image_size": [int(config["image_size"]), int(config["image_size"])],
        "normalization": config["normalization"],
        "model_version": config["model_version"],
        "dataset": "DIMPSAR",
        "dataset_url": index["dataset_url"],
        "dataset_revision": index["revision"],
        "dataset_license": index["license"],
        "seed": seed,
        "training_date": training_date,
        "split_counts": actual_splits,
        "unique_images_by_class": {
            name: index["target_classes"][name]["total"] for name in TARGET_CLASSES
        },
        "pretrained_weights": "MobileNet_V3_Small_Weights.IMAGENET1K_V1",
        "input_transform": "train: RandomResizedCrop(224), horizontal flip, 10-degree rotation, mild ColorJitter; eval: Resize(256), CenterCrop(224)",
        "loss": "CrossEntropyLoss",
        "class_weighting": weighting,
        "training_examples_per_epoch": int(actual_splits["train"]),
        "validation_examples": int(actual_splits["validation"]),
        "test_examples": int(actual_splits["test"]),
        "best_epoch": best_epoch,
        "epochs_completed": len(history),
        "best_validation_accuracy": best_accuracy,
        "best_validation_loss": best_loss,
        "best_epoch_train_accuracy": best_train_accuracy,
        "training_time_seconds": elapsed,
        "device": str(device),
        "train_minus_validation_accuracy": best_train_accuracy - best_accuracy,
        "confidence_note": "Softmax model confidence is not a calibrated probability of correctness.",
        "uncertainty_threshold": float(config["confidence_threshold"]),
    }
    checkpoint = torch.load(best_checkpoint, map_location="cpu", weights_only=True)
    torch.save(checkpoint, MODEL_PATH)
    METADATA_PATH.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with HISTORY_PATH.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(history[0]))
        writer.writeheader()
        writer.writerows(history)
    plot_training_history(history)

    # The test loader is constructed only after the validation-selected model is fixed.
    test_result = evaluate_saved_checkpoint(write_outputs=True)
    metadata["test_accuracy"] = test_result["accuracy"]
    metadata["test_macro_precision"] = test_result["macro_precision"]
    metadata["test_macro_recall"] = test_result["macro_recall"]
    metadata["test_macro_f1"] = test_result["macro_f1"]
    metadata["test_per_class"] = test_result["per_class"]
    metadata["test_evaluations"] = 1
    METADATA_PATH.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    best_checkpoint.unlink(missing_ok=True)
    return {"metadata": metadata, "test_result": test_result}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    args = parser.parse_args()
    result = train(args.config)
    print(json.dumps({"metadata": result["metadata"], "test_result": result["test_result"]}, indent=2))


if __name__ == "__main__":
    main()
