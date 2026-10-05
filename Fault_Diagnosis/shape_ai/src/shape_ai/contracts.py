from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np


CLASS_NAMES = ("Nominal", "LoE", "Friction", "Vibration")
CLASS_TO_INDEX = {name: idx for idx, name in enumerate(CLASS_NAMES)}


@dataclass(frozen=True)
class RepresentationSpec:
    name: str
    dataset: str
    family: str
    joints: int
    disk_shape: tuple[int, ...]
    tensor_shape: tuple[int, ...]


REPRESENTATIONS: dict[str, RepresentationSpec] = {
    "shape_cwt": RepresentationSpec(
        "shape_cwt", "/cwt/shape_log", "2d", 6, (448, 224, 6), (6, 224, 448)
    ),
    "torque_cwt": RepresentationSpec(
        "torque_cwt", "/cwt/torque_log", "2d", 6, (448, 224, 6), (6, 224, 448)
    ),
    "gmo_cwt": RepresentationSpec(
        "gmo_cwt", "/cwt/gmo_log", "2d", 6, (448, 224, 6), (6, 224, 448)
    ),
    "energy_cwt": RepresentationSpec(
        "energy_cwt", "/cwt/energy_log", "2d", 1, (448, 224, 1), (1, 224, 448)
    ),
    "shape_temporal": RepresentationSpec(
        "shape_temporal", "/temporal/shape", "1d", 6, (10001, 6), (6, 10001)
    ),
    "shape_fft": RepresentationSpec(
        "shape_fft", "/views/shape_fft_amplitude", "1d", 6, (1001, 6), (6, 1001)
    ),
}

CORE_DATASETS: dict[str, tuple[tuple[int, ...], str]] = {
    "/temporal/shape": ((10001, 6), "float32"),
    "/temporal/torque": ((10001, 6), "float32"),
    "/temporal/gmo": ((10001, 6), "float32"),
    "/temporal/energy": ((10001, 1), "float32"),
    "/cwt/shape_log": ((448, 224, 6), "float32"),
    "/cwt/torque_log": ((448, 224, 6), "float32"),
    "/cwt/gmo_log": ((448, 224, 6), "float32"),
    "/cwt/energy_log": ((448, 224, 1), "float32"),
    "/cwt/shape_magnitude": ((448, 224, 6), "float32"),
    "/cwt/torque_magnitude": ((448, 224, 6), "float32"),
    "/cwt/gmo_magnitude": ((448, 224, 6), "float32"),
    "/cwt/energy_magnitude": ((448, 224, 1), "float32"),
    "/views/shape_fft_amplitude": ((1001, 6), "float32"),
    "/coordinates/fft_frequency_hz": ((1001, 1), "float32"),
    "/coordinates/cwt_frequency_hz": ((224, 1), "float32"),
    "/coordinates/cwt_time_s": ((448, 1), "float32"),
    "/coordinates/telemetry_time_s": ((10001, 1), "float32"),
    "/quality/coi_valid_mask": ((448, 224), "uint8"),
    "/telemetry/q_meas": ((10001, 6), "float32"),
    "/telemetry/dq_meas": ((10001, 6), "float32"),
    "/telemetry/tau_cmd": ((10001, 6), "float32"),
    "/reference/q_ref": ((10001, 6), "float32"),
    "/reference/dq_ref": ((10001, 6), "float32"),
    "/reference/ddq_ref": ((10001, 6), "float32"),
    "/reference/tau_nom": ((10001, 6), "float32"),
}


def decode_attr(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray) and value.size == 1:
        return decode_attr(value.reshape(-1)[0])
    return value


def manifest_from_attr(value: Any) -> dict[str, Any]:
    decoded = decode_attr(value)
    if not isinstance(decoded, str):
        raise TypeError("manifest_record_json must decode to a JSON string")
    record = json.loads(decoded)
    if not isinstance(record, dict):
        raise TypeError("manifest_record_json must contain a JSON object")
    return record


def canonical_class(value: Any) -> str:
    text = str(decode_attr(value)).strip().lower()
    aliases = {
        "nominal": "Nominal",
        "loe": "LoE",
        "loss_of_effectiveness": "LoE",
        "friction": "Friction",
        "vibration": "Vibration",
    }
    if text not in aliases:
        raise ValueError(f"Unknown fault class: {value!r}")
    return aliases[text]


def to_model_array(array: np.ndarray, spec: RepresentationSpec) -> np.ndarray:
    if tuple(array.shape) != spec.disk_shape:
        raise ValueError(
            f"{spec.dataset} has shape {tuple(array.shape)}, expected {spec.disk_shape}"
        )
    if array.dtype != np.float32:
        raise TypeError(f"{spec.dataset} has dtype {array.dtype}, expected float32")
    if spec.family == "2d":
        result = array.transpose(2, 1, 0)
    else:
        result = array.transpose(1, 0)
    return np.ascontiguousarray(result, dtype=np.float32)
