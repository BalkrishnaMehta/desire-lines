from __future__ import annotations

import math
from itertools import pairwise
from pathlib import Path
from typing import Any

import networkx as nx
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

from .geo import feature, geometry, read_geojson, to_metric, to_wgs84, write_geojson

CITY_BBOX = (5.075, 52.055, 5.155, 52.115)
ENDPOINT_CAP = 700


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


def _in_bbox(item: dict[str, Any], west: float, south: float, east: float, north: float) -> bool:
    geom = geometry(item)
    return not geom.bounds or (
        geom.bounds[2] >= west
        and geom.bounds[0] <= east
        and geom.bounds[3] >= south
        and geom.bounds[1] <= north
    )


def build_candidates(
    layer_dir: Path,
    output: Path,
    max_pairs: int = 60_000,
    bbox: tuple[float, float, float, float] = CITY_BBOX,
) -> dict[str, int]:
    paths = [item for item in read_geojson(layer_dir / "paths.geojson") if _in_bbox(item, *bbox)]
    greens = [
        to_metric(geometry(item))
        for item in read_geojson(layer_dir / "green.geojson")
        if _in_bbox(item, *bbox)
    ]
    greens = [park for park in greens if park.area >= 2_500]
    attractors = [
        to_metric(geometry(item))
        for item in read_geojson(layer_dir / "attractors.geojson")
        if _in_bbox(item, *bbox)
    ]
    park_union = None
    if greens:
        from shapely.ops import unary_union

        park_union = unary_union(greens).buffer(25)
    barriers = []
    if park_union is not None:
        for item in read_geojson(layer_dir / "barriers.geojson"):
            if not _in_bbox(item, *bbox):
                continue
            barrier = to_metric(geometry(item))
            if barrier.intersects(park_union):
                barriers.append(barrier)

    graph = nx.Graph()
    informal_lines = []
    for item in paths:
        line = to_metric(geometry(item))
        if item["properties"].get("informal"):
            informal_lines.append(line)
            continue
        for first, second in pairwise(line.coords):
            graph.add_edge(_node(first), _node(second), weight=math.dist(first, second))

    if graph.number_of_nodes() == 0 or not greens:
        write_geojson([], output)
        return {"candidates": 0, "informal": len(informal_lines), "bbox": list(bbox)}

    graph_nodes = list(graph.nodes)
    node_points = [Point(node) for node in graph_nodes]
    node_tree = STRtree(node_points)
    green_tree = STRtree(greens)
    informal_tree = STRtree(informal_lines) if informal_lines else None
    endpoint_nodes: set[tuple[float, float]] = set()
    for park in greens:
        for idx in node_tree.query(park.boundary.buffer(12)):
            endpoint_nodes.add(graph_nodes[int(idx)])
    for target in attractors:
        idx = node_tree.nearest(target)
        node = graph_nodes[int(idx)]
        if Point(node).distance(target) <= 80:
            endpoint_nodes.add(node)
    if len(endpoint_nodes) > ENDPOINT_CAP:
        sampled = sorted(endpoint_nodes)
        endpoint_nodes = set(sampled[:: max(1, len(sampled) // ENDPOINT_CAP)])

    spatial_index = STRtree(barriers) if barriers else None
    end_list = list(endpoint_nodes)
    end_tree = STRtree([Point(node) for node in end_list])
    print(
        f"predict graph_nodes={graph.number_of_nodes()} endpoints={len(end_list)} "
        f"barriers={len(barriers)} greens={len(greens)}",
        flush=True,
    )
    results: list[dict[str, Any]] = []
    seen: list[LineString] = []
    checked = 0
    distances: dict[tuple[float, float], dict[tuple[float, float], float]] = {}
    for start_index, start in enumerate(end_list):
        if start_index % 50 == 0:
            print(
                f"predict start={start_index}/{len(end_list)} checked={checked} candidates={len(results)}",
                flush=True,
            )
        if start not in distances:
            distances[start] = nx.single_source_dijkstra_path_length(
                graph, start, cutoff=1_200, weight="weight"
            )
        for idx in end_tree.query(Point(start).buffer(400)):
            end = end_list[int(idx)]
            if end <= start:
                continue
            straight_distance = math.dist(start, end)
            if not 20 <= straight_distance <= 400:
                continue
            checked += 1
            if checked > max_pairs:
                break
            candidate = LineString([start, end])
            park_hits = [greens[int(i)] for i in green_tree.query(candidate)]
            park_lengths = [
                candidate.intersection(park).length
                for park in park_hits
                if candidate.intersects(park)
            ]
            green_fraction = (
                min(1.0, sum(park_lengths) / candidate.length) if candidate.length else 0
            )
            local_barriers = (
                [barriers[int(i)] for i in spatial_index.query(candidate)] if spatial_index else []
            )
            network_distance = distances[start].get(end)
            if network_distance is None:
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
            nearest_informal = float("inf")
            if informal_tree is not None:
                for informal_idx in informal_tree.query(candidate.buffer(15)):
                    nearest_informal = min(
                        nearest_informal,
                        candidate.hausdorff_distance(informal_lines[int(informal_idx)]),
                    )
            angle_match = _angle_match(candidate, informal_lines, 20)
            seen.append(candidate)
            props = {
                "id": f"utrecht-{len(results) + 1:03d}",
                **{key: round(value, 3) for key, value in values.items()},
                "label": int(nearest_informal <= 12 and angle_match),
                "nearest_informal_m": round(min(nearest_informal, 9_999), 2),
                "source": "predicted",
            }
            results.append(feature(to_wgs84(candidate), props))
        if checked > max_pairs:
            break

    for informal in informal_lines:
        length = informal.length
        if not 20 <= length <= 400:
            continue
        park_hits = [greens[int(i)] for i in green_tree.query(informal)]
        green_fraction = (
            min(1.0, sum(informal.intersection(park).length for park in park_hits) / length)
            if length
            else 0
        )
        if green_fraction < 0.5:
            continue
        if any(informal.hausdorff_distance(other) < 8 for other in seen):
            continue
        seen.append(informal)
        props = {
            "id": f"utrecht-{len(results) + 1:03d}",
            "length_m": round(length, 3),
            "network_distance_m": round(length * 1.8, 3),
            "detour_ratio": 1.8,
            "distance_saved_m": round(length * 0.8, 3),
            "seconds_saved": round(length * 0.8 / 1.3, 3),
            "green_fraction": round(green_fraction, 3),
            "label": 1,
            "nearest_informal_m": 0.0,
            "source": "mapped_informal",
        }
        results.append(feature(to_wgs84(informal), props))

    write_geojson(results, output)
    positives = sum(item["properties"]["label"] for item in results)
    return {
        "candidates": len(results),
        "positives": positives,
        "informal": len(informal_lines),
        "endpoints": len(endpoint_nodes),
        "checked_pairs": checked,
        "bbox": list(bbox),
    }


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

