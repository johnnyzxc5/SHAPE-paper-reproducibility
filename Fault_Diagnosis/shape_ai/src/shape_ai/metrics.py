from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    roc_auc_score,
)

from .contracts import CLASS_NAMES


def classification_metrics(
    targets: np.ndarray, predictions: np.ndarray, probabilities: np.ndarray | None = None
) -> dict[str, Any]:
    labels = list(range(len(CLASS_NAMES)))
    precision, recall, f1, support = precision_recall_fscore_support(
        targets, predictions, labels=labels, zero_division=0
    )
    matrix = confusion_matrix(targets, predictions, labels=labels)
    row_sums = matrix.sum(axis=1, keepdims=True)
    normalized = np.divide(matrix, row_sums, out=np.zeros_like(matrix, dtype=float), where=row_sums > 0)
    specificity = []
    for index in labels:
        tp = matrix[index, index]
        fp = matrix[:, index].sum() - tp
        fn = matrix[index, :].sum() - tp
        tn = matrix.sum() - tp - fp - fn
        specificity.append(float(tn / (tn + fp)) if tn + fp else float("nan"))

    result: dict[str, Any] = {
        "samples": int(len(targets)),
        "accuracy": float(accuracy_score(targets, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(targets, predictions)),
        "macro_f1": float(f1_score(targets, predictions, average="macro")),
        "confusion_matrix": matrix.tolist(),
        "normalized_confusion_matrix": normalized.tolist(),
        "per_class": {
            name: {
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
                "specificity": specificity[index],
                "support": int(support[index]),
            }
            for index, name in enumerate(CLASS_NAMES)
        },
        "classification_report": classification_report(
            targets,
            predictions,
            labels=labels,
            target_names=list(CLASS_NAMES),
            zero_division=0,
            output_dict=True,
        ),
    }
    nominal = 0
    nominal_targets = targets == nominal
    non_nominal_targets = ~nominal_targets
    result["nominal_false_alarm_rate"] = float(
        np.mean(predictions[nominal_targets] != nominal)
    ) if nominal_targets.any() else float("nan")
    result["fault_missed_detection_rate"] = float(
        np.mean(predictions[non_nominal_targets] == nominal)
    ) if non_nominal_targets.any() else float("nan")
    if probabilities is not None and len(np.unique(targets)) == len(CLASS_NAMES):
        try:
            result["macro_roc_auc_ovr"] = float(
                roc_auc_score(targets, probabilities, labels=labels, multi_class="ovr", average="macro")
            )
        except ValueError:
            result["macro_roc_auc_ovr"] = None
    return result
