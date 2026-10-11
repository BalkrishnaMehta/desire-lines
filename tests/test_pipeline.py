from __future__ import annotations

import json
from pathlib import Path

import pytest
from shapely.geometry import LineString, Polygon


def test_tag_classifier_extracts_layers() -> None:
    from desirelines.fetch import classify_tags

    assert classify_tags({"highway": "path", "informal": "yes"}) == {"path", "informal"}
    assert classify_tags({"leisure": "park"}) == {"green"}
    assert classify_tags({"barrier": "fence"}) == {"barrier"}
    assert classify_tags({"public_transport": "platform"}) == {"attractor"}


def test_candidate_features_reward_useful_shortcuts() -> None:
    from desirelines.predict import candidate_features

    feature = candidate_features(
        straight_distance=80,
        network_distance=150,
        green_fraction=0.95,
        candidate=LineString([(0, 0), (80, 0)]),
        barriers=[],
    )
    assert feature is not None
    assert feature["detour_ratio"] == pytest.approx(1.875)
    assert feature["seconds_saved"] == pytest.approx(70 / 1.3)


def test_candidate_features_reject_barrier_crossing() -> None:
    from desirelines.predict import candidate_features

    feature = candidate_features(
        straight_distance=80,
        network_distance=150,
        green_fraction=0.95,
        candidate=LineString([(0, 0), (80, 0)]),
        barriers=[LineString([(40, -10), (40, 10)])],
    )
    assert feature is None


def test_excess_green_and_wear_score() -> None:
    import numpy as np

    from desirelines.imagery import excess_green, wear_score

    image = np.zeros((20, 20, 3), dtype=np.uint8)
    image[:, :] = [40, 140, 40]
    image[:, 9:11] = [150, 100, 70]
    exg = excess_green(image)
    corridor = np.zeros((20, 20), dtype=bool)
    corridor[:, 9:11] = True
    controls = np.zeros((20, 20), dtype=bool)
    controls[:, 4:7] = True
    controls[:, 13:16] = True
    result = wear_score(exg, corridor, controls)
    assert result["wear"] > 1
    assert result["continuity"] > 0.9


def test_spatial_blocks_do_not_split_a_cell() -> None:
    from desirelines.score import spatial_block_folds

    points = [(0, 0), (10, 10), (120, 0), (130, 10), (240, 0), (250, 10)]
    folds = spatial_block_folds(points, block_size=100, n_splits=3)
    for train, test in folds:
        assert set(train).isdisjoint(test)
        assert train and test


def test_route_and_exports(tmp_path: Path) -> None:
    from desirelines.walk import export_gpx, route_candidates

    candidates = [
        {"id": "a", "score": 0.9, "geometry": [[5.0, 52.0], [5.001, 52.001]]},
        {"id": "b", "score": 0.8, "geometry": [[5.002, 52.001], [5.003, 52.0]]},
    ]
    route = route_candidates(candidates, max_items=2)
    assert {item["id"] for item in route} == {"a", "b"}
    target = tmp_path / "walk.gpx"
    export_gpx(route, target)
    assert "<gpx" in target.read_text(encoding="utf-8")
    assert "Desire line a" in target.read_text(encoding="utf-8")


def test_review_fallback_is_structured() -> None:
    from desirelines.review import fallback_review

    candidate = {
        "id": "utrecht-001",
        "length_m": 38,
        "seconds_saved": 52,
        "wear": 2.4,
        "continuity": 0.8,
    }
    review = fallback_review(candidate)
    assert review["verdict"] == "yes"
    assert review["title"].startswith("Formalise")
    json.dumps(review)


def test_clip_bbox_is_inside_green_polygon() -> None:
    from desirelines.geo import fraction_inside

    line = LineString([(0, 0), (10, 0)])
    park = Polygon([(0, -1), (8, -1), (8, 1), (0, 1)])
    assert fraction_inside(line, [park]) == pytest.approx(0.8)


def test_site_builder_publishes_data(tmp_path: Path) -> None:
    from desirelines.site import build_site

    generated = tmp_path / "generated"
    site = tmp_path / "site"
    generated.mkdir()
    collection = {"type": "FeatureCollection", "features": []}
    (generated / "reviewed.geojson").write_text(json.dumps(collection), encoding="utf-8")
    (generated / "metrics.json").write_text(
        json.dumps({"samples": 0, "primary_model": "demo"}), encoding="utf-8"
    )
    result = build_site(generated, site)
    assert result["features"] == 0
    assert (site / "data" / "desire-lines.geojson").exists()
    assert "Pull requests the city never merged" in (site / "index.html").read_text(
        encoding="utf-8"
    )

