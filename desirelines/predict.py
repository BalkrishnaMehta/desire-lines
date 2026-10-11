from __future__ import annotations

import math
from itertools import combinations, pairwise
from pathlib import Path
from typing import Any

import networkx as nx
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

from .geo import feature, geometry, read_geojson, to_metric, to_wgs84, write_geojson


def candidate_features(
    *,
    straight_distance: float,
    network_distance: float,
    green_fraction: float,
    candidate: LineString,
    barriers: list,
) -> dict[str, float] | None:
    if (
        straight_distance < 20
        or straight_distance > 400
        or network_distance <= straight_distance
        or green_fraction < 0.8
        or any(candidate.crosses(barrier) or candidate.within(barrier) for barrier in barriers)
    ):
        return None
    saved = network_distance - straight_distance
    ratio = network_distance / straight_distance
    if ratio < 1.25 or saved < 15:
        return None
    return {
        "length_m": straight_distance,
        "network_distance_m": network_distance,
        "detour_ratio": ratio,
        "distance_saved_m": saved,
        "seconds_saved": saved / 1.3,
        "green_fraction": green_fraction,
    }


def build_candidates(layer_dir: Path, output: Path, max_pairs: int = 50_000) -> dict[str, int]:
    paths = read_geojson(layer_dir / "paths.geojson")
    greens_wgs = [geometry(item) for item in read_geojson(layer_dir / "green.geojson")]
    greens = [to_metric(item) for item in greens_wgs]
    barriers = [to_metric(geometry(item)) for item in read_geojson(layer_dir / "barriers.geojson")]
    attractors_wgs = [geometry(item) for item in read_geojson(layer_dir / "attractors.geojson")]

    graph = nx.Graph()
    official_lines = []
    informal_lines = []
    for item in paths:
        line = to_metric(geometry(item))
        if item["properties"].get("informal"):
            informal_lines.append(line)
            continue
        official_lines.append(line)
        coords = list(line.coords)
        for first, second in pairwise(coords):
            length = math.dist(first, second)
            graph.add_edge(_node(first), _node(second), weight=length)

    if graph.number_of_nodes() == 0:
        write_geojson([], output)
        return {"candidates": 0, "informal": len(informal_lines)}

    graph_nodes = list(graph.nodes)
    node_tree = STRtree([Point(node) for node in graph_nodes])
    endpoint_nodes: set[tuple[float, float]] = set()
    for park in greens:
        boundary = park.boundary
        near = [node for node in graph_nodes if Point(node).distance(boundary) <= 12]
        endpoint_nodes.update(near[:: max(1, len(near) // 30)])
    for target in attractors_wgs:
        metric_target = to_metric(target)
        idx = node_tree.nearest(metric_target)
        node = graph_nodes[int(idx)]
        if Point(node).distance(metric_target) <= 100:
            endpoint_nodes.add(node)

    spatial_index = STRtree(barriers) if barriers else None
    results: list[dict[str, Any]] = []
    seen: list[LineString] = []
    checked = 0
    for start, end in combinations(sorted(endpoint_nodes), 2):
        straight_distance = math.dist(start, end)
        if not 20 <= straight_distance <= 400:
            continue
        checked += 1
        if checked > max_pairs:
            break
        candidate = LineString([start, end])
        park_lengths = [candidate.intersection(park).length for park in greens if candidate.intersects(park)]
        green_fraction = min(1.0, sum(park_lengths) / candidate.length) if candidate.length else 0
        local_barriers = (
            [barriers[int(idx)] for idx in spatial_index.query(candidate)] if spatial_index else []
        )
        try:
            network_distance = nx.shortest_path_length(graph, start, end, weight="weight")
        except nx.NetworkXNoPath:
            continue
        values = candidate_features(
            straight_distance=straight_distance,
            network_distance=network_distance,
            green_fraction=green_fraction,
            candidate=candidate,
            barriers=local_barriers,
        )
        if values is None or any(candidate.hausdorff_distance(other) < 8 for other in seen):
            continue
        seen.append(candidate)
        nearest_informal = min(
            (candidate.hausdorff_distance(item) for item in informal_lines), default=float("inf")
        )
        angle_match = _angle_match(candidate, informal_lines, 20)
        label = int(nearest_informal <= 10 and angle_match)
        props = {
            "id": f"utrecht-{len(results) + 1:03d}",
            **{key: round(value, 3) for key, value in values.items()},
            "label": label,
            "nearest_informal_m": round(nearest_informal, 2),
        }
        results.append(feature(to_wgs84(candidate), props))

    write_geojson(results, output)
    positives = sum(item["properties"]["label"] for item in results)
    return {"candidates": len(results), "positives": positives, "informal": len(informal_lines)}


def _node(coord: tuple[float, float]) -> tuple[float, float]:
    return round(coord[0], 2), round(coord[1], 2)


def _angle(line: LineString) -> float:
    (x1, y1), (x2, y2) = line.coords[0], line.coords[-1]
    return math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180


def _angle_match(candidate: LineString, lines: list[LineString], tolerance: float) -> bool:
    candidate_angle = _angle(candidate)
    for line in lines:
        if candidate.distance(line) > 15:
            continue
        delta = abs(candidate_angle - _angle(line))
        if min(delta, 180 - delta) <= tolerance:
            return True
    return False

