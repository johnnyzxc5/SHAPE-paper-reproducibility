from __future__ import annotations

from collections.abc import Sequence

import torch
from torch import nn

from .contracts import REPRESENTATIONS


class SharedEncoder2D(nn.Module):
    def __init__(self, embedding_dim: int = 128, channels: Sequence[int] = (16, 32, 64, 128, 256)):
        super().__init__()
        blocks: list[nn.Module] = []
        input_channels = 1
        for output_channels in channels:
            blocks.extend(
                [
                    nn.Conv2d(input_channels, output_channels, kernel_size=3, padding=1, bias=False),
                    nn.BatchNorm2d(output_channels),
                    nn.ReLU(inplace=True),
                    nn.MaxPool2d(2),
                ]
            )
            input_channels = output_channels
        blocks.append(nn.AdaptiveAvgPool2d((1, 1)))
        self.features = nn.Sequential(*blocks)
        self.projection = nn.Sequential(nn.Flatten(), nn.Linear(input_channels, embedding_dim), nn.ReLU())

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.projection(self.features(x))


class SharedEncoder1D(nn.Module):
    def __init__(self, embedding_dim: int = 128, channels: Sequence[int] = (16, 32, 64, 128, 256)):
        super().__init__()
        blocks: list[nn.Module] = []
        input_channels = 1
        for output_channels in channels:
            blocks.extend(
                [
                    nn.Conv1d(input_channels, output_channels, kernel_size=7, padding=3, bias=False),
                    nn.BatchNorm1d(output_channels),
                    nn.ReLU(inplace=True),
                    nn.MaxPool1d(2),
                ]
            )
            input_channels = output_channels
        blocks.append(nn.AdaptiveAvgPool1d(1))
        self.features = nn.Sequential(*blocks)
        self.projection = nn.Sequential(nn.Flatten(), nn.Linear(input_channels, embedding_dim), nn.ReLU())

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.projection(self.features(x))


class MultiJointClassifier(nn.Module):
    """Shared per-joint encoder followed by late fusion, matching the legacy topology."""

    def __init__(
        self,
        family: str,
        joints: int,
        embedding_dim: int = 128,
        head_dim: int = 256,
        dropout: float = 0.5,
        num_classes: int = 4,
    ):
        super().__init__()
        if family not in {"1d", "2d"}:
            raise ValueError(f"Unsupported family {family}")
        self.family = family
        self.joints = joints
        self.embedding_dim = embedding_dim
        self.encoder = (
            SharedEncoder2D(embedding_dim=embedding_dim)
            if family == "2d"
            else SharedEncoder1D(embedding_dim=embedding_dim)
        )
        self.classifier = nn.Sequential(
            nn.Linear(joints * embedding_dim, head_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(head_dim, num_classes),
        )

    def forward(self, x: torch.Tensor, return_features: bool = False):
        if x.ndim != (4 if self.family == "2d" else 3):
            raise ValueError(f"Unexpected input rank {x.ndim} for {self.family}")
        batch, joints = x.shape[:2]
        if joints != self.joints:
            raise ValueError(f"Expected {self.joints} joints/channels, received {joints}")
        if self.family == "2d":
            encoded = self.encoder(x.reshape(batch * joints, 1, x.shape[2], x.shape[3]))
        else:
            encoded = self.encoder(x.reshape(batch * joints, 1, x.shape[2]))
        joint_features = encoded.reshape(batch, joints, self.embedding_dim)
        fused = joint_features.flatten(1)
        logits = self.classifier(fused)
        if return_features:
            return logits, fused, joint_features
        return logits


def build_model(
    representation: str,
    embedding_dim: int = 128,
    head_dim: int = 256,
    dropout: float = 0.5,
    num_classes: int = 4,
) -> MultiJointClassifier:
    spec = REPRESENTATIONS[representation]
    return MultiJointClassifier(
        family=spec.family,
        joints=spec.joints,
        embedding_dim=embedding_dim,
        head_dim=head_dim,
        dropout=dropout,
        num_classes=num_classes,
    )


def parameter_count(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
