from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import requests

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["yes", "no", "unclear"]},
        "evidence": {"type": "string"},
        "surface": {"type": "string"},
    },
    "required": ["verdict", "evidence", "surface"],
}


def fallback_review(candidate: dict[str, Any]) -> dict[str, Any]:
    wear = float(candidate.get("wear", 0))
    continuity = float(candidate.get("continuity", 0))
    verdict = "yes" if wear >= 1 and continuity >= 0.55 else "unclear"
    length = round(float(candidate.get("length_m", 0)))
    saved = round(float(candidate.get("seconds_saved", 0)))
    return {
        "verdict": verdict,
        "evidence": (
            f"Open aerial imagery shows a greenness drop of {wear:.1f}σ "
            f"with {continuity:.0%} corridor continuity."
        ),
        "surface": "worn vegetation" if verdict == "yes" else "needs a field check",
        "title": f"Formalise {length} m pedestrian shortcut",
        "diff": f"+{length} m informal path; saves about {saved} seconds",
        "action": "Field-check, then formalise or reroute without blocking pedestrian access.",
        "source": "deterministic fallback",
    }


def review_candidates(
    input_geojson: Path,
    output_geojson: Path,
    chip_dir: Path,
    *,
    limit: int = 20,
    ollama_url: str = "http://127.0.0.1:11434",
    model: str | None = None,
) -> dict[str, Any]:
    payload = json.loads(input_geojson.read_text(encoding="utf-8"))
    selected = payload["features"][:limit]
    selected_ids = {item["properties"]["id"] for item in selected}
    active_model = model or _find_gemma(ollama_url)
    used_model = 0
    for item in payload["features"]:
        props = item["properties"]
        result = fallback_review(props)
        if props["id"] in selected_ids and active_model and props.get("chip"):
            chip = chip_dir / Path(props["chip"]).name
            if chip.exists():
                try:
                    vision = _ollama_vision(chip, active_model, ollama_url)
                    result.update(vision)
                    result["source"] = active_model
                    result["title"] = (
                        f"Formalise {round(float(props['length_m']))} m pedestrian shortcut"
                    )
                    result["diff"] = (
                        f"+{round(float(props['length_m']))} m informal path; "
                        f"saves about {round(float(props['seconds_saved']))} seconds"
                    )
                    result["action"] = _action_for(vision["verdict"])
                    used_model += 1
                except (requests.RequestException, ValueError, KeyError, json.JSONDecodeError):
                    pass
        props["review"] = result
    output_geojson.parent.mkdir(parents=True, exist_ok=True)
    output_geojson.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "reviewed": len(selected),
        "model_reviews": used_model,
        "model": active_model or "deterministic fallback",
    }


def _find_gemma(url: str) -> str | None:
    try:
        response = requests.get(f"{url}/api/tags", timeout=3)
        response.raise_for_status()
        names = [item["name"] for item in response.json().get("models", [])]
        return next((name for name in names if "gemma" in name.lower()), None)
    except requests.RequestException:
        return None


def _ollama_vision(chip: Path, model: str, url: str) -> dict[str, str]:
    prompt = (
        "This is open aerial imagery. The red line is a predicted pedestrian shortcut. "
        "Decide only whether a narrow continuous worn track is visible under the red line. "
        "Do not infer people, intent, safety, or legal status. Choose unclear when trees, "
        "shadows, resolution, or pavement prevent a defensible answer."
    )
    response = requests.post(
        f"{url}/api/chat",
        json={
            "model": model,
            "stream": False,
            "format": REVIEW_SCHEMA,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [base64.b64encode(chip.read_bytes()).decode("ascii")],
                }
            ],
            "options": {"temperature": 0},
        },
        timeout=240,
    )
    response.raise_for_status()
    parsed = json.loads(response.json()["message"]["content"])
    if parsed["verdict"] not in {"yes", "no", "unclear"}:
        raise ValueError("Unexpected Gemma verdict")
    return parsed


def _action_for(verdict: str) -> str:
    if verdict == "yes":
        return "Field-check, then formalise or reroute without blocking pedestrian access."
    if verdict == "no":
        return "Do not map from imagery; archive unless a field survey finds a path."
    return "Send a mapper to inspect this location before making any map edit."

