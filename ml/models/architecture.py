"""Shared MobileNetV3-Small construction and pretrained checkpoint checks."""

from __future__ import annotations

import hashlib
from pathlib import Path

import torch
from torch import nn
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRETRAINED_PATH = PROJECT_ROOT / "ml/.cache/torch/hub/checkpoints/mobilenet_v3_small-047dcff4.pth"


def load_pretrained_state() -> dict:
    if not PRETRAINED_PATH.is_file():
        raise FileNotFoundError(f"Expected cached ImageNet weights at {PRETRAINED_PATH}")
    digest = hashlib.sha256(PRETRAINED_PATH.read_bytes()).hexdigest()
    if not digest.startswith("047dcff4"):
        raise ValueError(f"Cached MobileNet weights failed SHA-256 prefix check: {digest}")
    return torch.load(PRETRAINED_PATH, map_location="cpu", weights_only=True)


def create_mobilenet_v3_small(
    num_classes: int,
    device: torch.device | str = "cpu",
    *,
    load_pretrained: bool = True,
) -> nn.Module:
    model = mobilenet_v3_small(weights=None)
    if load_pretrained:
        model.load_state_dict(load_pretrained_state(), strict=True)
    model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, num_classes)
    return model.to(device)


def inference_transform():
    return MobileNet_V3_Small_Weights.IMAGENET1K_V1.transforms()
