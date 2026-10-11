from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Callable
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

INFORMAL_DISTANCE_SENTINEL = 9_999.0


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
    payload = _load_geojson(input_geojson)
    _write_json(input_geojson, payload)
    features = payload["features"]
    if len(features) < 4:
        metrics = {"error": "Need at least four candidates", "samples": len(features)}
        _save_results(payload, output_geojson, metrics_path, metrics)
        return metrics

    x = np.asarray(
        [[float(item["properties"].get(name, 0.0) or 0.0) for name in FEATURES] for item in features]
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

    model_factories: dict[str, Callable[[], Any]] = {
        "logistic_regression": lambda: make_pipeline(
            StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=1000)
        ),
        "hist_gradient_boosting": lambda: HistGradientBoostingClassifier(
            max_iter=100, max_depth=4, class_weight="balanced", random_state=42
        ),
    }

    predictions: dict[str, np.ndarray] = {}
    reports: dict[str, Any] = {}
    for name, factory in model_factories.items():
        report, pred = _cross_validate(factory, x, y, folds, len(features))
        reports[name] = report
        if "roc_auc" in report:
            predictions[name] = pred

    tabpfn_notes = _fit_tabpfn(reports, predictions, x, y, folds, len(features))

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

    ranked = [
        (name, reports[name]["roc_auc"])
        for name in predictions
        if isinstance(reports.get(name), dict) and "roc_auc" in reports[name]
    ]
    if any(name == "tabpfn" and "roc_auc" in reports.get(name, {}) for name in reports):
        primary = "tabpfn"
    elif ranked:
        primary = max(ranked, key=lambda item: item[1])[0]
    else:
        primary = "detour_wear_heuristic"
    chosen = predictions[primary]
    for index, item in enumerate(features):
        score = chosen[index]
        if np.isnan(score):
            score = heuristic[index]
        item["properties"]["score"] = round(float(score), 4)
        item["properties"]["model"] = primary
    features.sort(key=lambda item: item["properties"]["score"], reverse=True)
    metrics: dict[str, Any] = {
        "samples": len(features),
        "positives": int(y.sum()),
        "features": FEATURES,
        "spatial_folds": len(folds),
        "primary_model": primary,
        "models": reports,
    }
    metrics.update(tabpfn_notes)
    _save_results(payload, output_geojson, metrics_path, metrics)
    return metrics


def _fit_tabpfn(
    reports: dict[str, Any],
    predictions: dict[str, np.ndarray],
    x: np.ndarray,
    y: np.ndarray,
    folds: list[tuple[list[int], list[int]]],
    n_samples: int,
) -> dict[str, str]:
    notes: dict[str, str] = {}
    backends = _tabpfn_backends(notes)
    errors: list[str] = []
    for backend, factory in backends:
        report, pred = _cross_validate(factory, x, y, folds, n_samples)
        backend_error = report.get("error")
        if backend_error:
            errors.append(str(backend_error))
            notes[f"{backend}_error"] = str(backend_error)
            if _looks_like_license_error(backend_error):
                notes.setdefault("tabpfn_license_gate", str(backend_error))
        if "roc_auc" in report:
            reports["tabpfn"] = report
            predictions["tabpfn"] = pred
            notes["tabpfn_backend"] = backend
            return notes
    if backends or notes or errors:
        reports["tabpfn"] = {
            "error": "; ".join(dict.fromkeys(errors))
            or notes.get("tabpfn_import_error")
            or notes.get("tabpfn_client_import_error")
            or "unavailable"
        }
    return notes


def _tabpfn_backends(notes: dict[str, str]) -> list[tuple[str, Callable[[], Any]]]:
    backends: list[tuple[str, Callable[[], Any]]] = []
    try:
        from tabpfn import TabPFNClassifier

        backends.append(("tabpfn", lambda cls=TabPFNClassifier: cls(device="cpu")))
    except Exception as exc:  # license/import must not abort scoring
        message = f"{type(exc).__name__}: {exc}"
        notes["tabpfn_import_error"] = message
        if _looks_like_license_error(message):
            notes["tabpfn_license_gate"] = message
    try:
        from tabpfn_client import TabPFNClassifier as TabPFNClientClassifier

        backends.append(("tabpfn_client", lambda cls=TabPFNClientClassifier: cls()))
    except Exception as exc:  # optional cloud client must not abort scoring
        message = f"{type(exc).__name__}: {exc}"
        notes["tabpfn_client_import_error"] = message
        if _looks_like_license_error(message):
            notes.setdefault("tabpfn_license_gate", message)
    return backends


def _cross_validate(
    factory: Callable[[], Any],
    x: np.ndarray,
    y: np.ndarray,
    folds: list[tuple[list[int], list[int]]],
    n_samples: int,
) -> tuple[dict[str, Any], np.ndarray]:
    pred = np.full(n_samples, np.nan)
    errors: list[str] = []
    for train, test in folds:
        if len(np.unique(y[train])) < 2:
            errors.append("training fold has one class")
            continue
        try:
            model = factory()
            model.fit(x[train], y[train])
            pred[test] = model.predict_proba(x[test])[:, 1]
        except Exception as exc:  # optional models must not abort the pipeline
            errors.append(f"{type(exc).__name__}: {exc}")
    valid = ~np.isnan(pred)
    if valid.sum() >= 2 and len(np.unique(y[valid])) == 2:
        return _metrics(y[valid], pred[valid]), pred
    return {"error": "; ".join(dict.fromkeys(errors)) or "insufficient folds"}, pred


def _looks_like_license_error(message: object) -> bool:
    text = str(message)
    name = text.split(":", 1)[0]
    return name.endswith("LicenseError") or "TABPFN_TOKEN" in text or "license acceptance" in text.lower()


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


def _load_geojson(path: Path) -> dict[str, Any]:
    def parse_constant(name: str) -> float:
        mapping = {"Infinity": math.inf, "-Infinity": -math.inf, "NaN": math.nan}
        if name in mapping:
            return mapping[name]
        raise ValueError(f"Unknown JSON constant: {name}")

    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=parse_constant)
    return _sanitize(payload)


def _sanitize(value: Any, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {inner: _sanitize(inner_value, inner) for inner, inner_value in value.items()}
    if isinstance(value, list):
        return [_sanitize(item, key) for item in value]
    if isinstance(value, (np.floating, np.integer)):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        if key == "nearest_informal_m":
            return INFORMAL_DISTANCE_SENTINEL
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_sanitize(payload), indent=2, allow_nan=False), encoding="utf-8")


def _save_results(
    payload: dict[str, Any], output: Path, metrics_path: Path, metrics: dict[str, Any]
) -> None:
    _write_json(output, payload)
    _write_json(metrics_path, metrics)
