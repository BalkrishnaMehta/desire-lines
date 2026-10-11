from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = [
    "length_m",
    "network_distance_m",
    "detour_ratio",
    "distance_saved_m",
    "seconds_saved",
    "green_fraction",
    "wear",
    "continuity",
]


def spatial_block_folds(
    points: list[tuple[float, float]], block_size: float, n_splits: int
) -> list[tuple[list[int], list[int]]]:
    groups: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, (x, y) in enumerate(points):
        groups[(math.floor(x / block_size), math.floor(y / block_size))].append(index)
    buckets: list[list[int]] = [[] for _ in range(min(n_splits, len(groups)))]
    for index, key in enumerate(sorted(groups)):
        buckets[index % len(buckets)].extend(groups[key])
    universe = set(range(len(points)))
    return [
        (sorted(universe - set(test)), sorted(test))
        for test in buckets
        if test and universe - set(test)
    ]


def evaluate_models(input_geojson: Path, output_geojson: Path, metrics_path: Path) -> dict[str, Any]:
    payload = json.loads(input_geojson.read_text(encoding="utf-8"))
    features = payload["features"]
    if len(features) < 4:
        metrics = {"error": "Need at least four candidates", "samples": len(features)}
        _save_results(payload, output_geojson, metrics_path, metrics)
        return metrics

    x = np.asarray(
        [[float(item["properties"].get(name, 0.0)) for name in FEATURES] for item in features]
    )
    y = np.asarray([int(item["properties"].get("label", 0)) for item in features])
    points = [
        (
            float(item["geometry"]["coordinates"][0][0]) * 70_000,
            float(item["geometry"]["coordinates"][0][1]) * 111_000,
        )
        for item in features
    ]
    folds = spatial_block_folds(points, block_size=1000, n_splits=5)
    if not folds:
        folds = [(list(range(len(features) // 2)), list(range(len(features) // 2, len(features))))]

    model_factories = {
        "logistic_regression": lambda: make_pipeline(
            StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=1000)
        ),
        "hist_gradient_boosting": lambda: HistGradientBoostingClassifier(
            max_iter=100, max_depth=4, class_weight="balanced", random_state=42
        ),
    }
    tabpfn_error = None
    try:
        from tabpfn import TabPFNClassifier

        model_factories["tabpfn"] = lambda: TabPFNClassifier(device="cpu")
    except (ImportError, RuntimeError, OSError) as exc:  # pragma: no cover
        tabpfn_error = f"{type(exc).__name__}: {exc}"

    predictions: dict[str, np.ndarray] = {}
    reports: dict[str, Any] = {}
    for name, factory in model_factories.items():
        pred = np.full(len(features), np.nan)
        errors = []
        for train, test in folds:
            if len(np.unique(y[train])) < 2:
                errors.append("training fold has one class")
                continue
            try:
                model = factory()
                model.fit(x[train], y[train])
                pred[test] = model.predict_proba(x[test])[:, 1]
            except (ValueError, RuntimeError, OSError, AttributeError) as exc:
                errors.append(f"{type(exc).__name__}: {exc}")
        valid = ~np.isnan(pred)
        if valid.sum() >= 2 and len(np.unique(y[valid])) == 2:
            reports[name] = _metrics(y[valid], pred[valid])
            predictions[name] = pred
        else:
            reports[name] = {"error": "; ".join(dict.fromkeys(errors)) or "insufficient folds"}

    heuristic = np.asarray(
        [
            _sigmoid(
                1.4 * (row[FEATURES.index("detour_ratio")] - 1.25)
                + 0.7 * row[FEATURES.index("wear")]
                + 0.8 * row[FEATURES.index("continuity")]
            )
            for row in x
        ]
    )
    reports["detour_wear_heuristic"] = (
        _metrics(y, heuristic) if len(np.unique(y)) == 2 else {"error": "one label class"}
    )
    predictions["detour_wear_heuristic"] = heuristic
    primary = (
        "tabpfn"
        if "tabpfn" in predictions
        else "hist_gradient_boosting"
        if "hist_gradient_boosting" in predictions
        else "detour_wear_heuristic"
    )
    chosen = predictions[primary]
    for index, item in enumerate(features):
        score = chosen[index]
        if np.isnan(score):
            score = heuristic[index]
        item["properties"]["score"] = round(float(score), 4)
        item["properties"]["model"] = primary
    features.sort(key=lambda item: item["properties"]["score"], reverse=True)
    metrics = {
        "samples": len(features),
        "positives": int(y.sum()),
        "features": FEATURES,
        "spatial_folds": len(folds),
        "primary_model": primary,
        "models": reports,
    }
    if tabpfn_error:
        metrics["tabpfn_import_error"] = tabpfn_error
    _save_results(payload, output_geojson, metrics_path, metrics)
    return metrics


def _metrics(y_true: np.ndarray, scores: np.ndarray) -> dict[str, float]:
    order = np.argsort(scores)[::-1]
    k = min(10, len(y_true))
    return {
        "roc_auc": round(float(roc_auc_score(y_true, scores)), 4),
        "pr_auc": round(float(average_precision_score(y_true, scores)), 4),
        "precision_at_10": round(float(np.mean(y_true[order[:k]])), 4),
    }


def _sigmoid(value: float) -> float:
    return 1 / (1 + math.exp(-max(min(value, 20), -20)))


def _save_results(
    payload: dict[str, Any], output: Path, metrics_path: Path, metrics: dict[str, Any]
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

