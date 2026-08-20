"""AI eval harness (AI-ARCHITECTURE.md §8, ROADMAP Phase 6 exit).

Runs the deterministic stub pipeline (the standing-in provider when no API key
is configured) over a golden set and records metrics — the same harness in CI
runs against the real gateway once keys exist. Metrics land in
``services/api/eval/metrics.json``; category accuracy must stay above the floor.
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
from pathlib import Path
from typing import Any

from tk_api.ai.gateway import StubGateway
from tk_api.ai.similarity import similarity

ACCURACY_FLOOR = 0.5

GOLDEN_SET: list[dict[str, Any]] = [
    {
        "title": "Classroom windows broken on ground floor",
        "description": "Sharp glass edges at child height near the playground",
        "expected": "school",
    },
    {
        "title": "School washroom taps have no water",
        "description": "Children queue for water every morning",
        "expected": "school",
    },
    {
        "title": "Loose school furniture in corridors",
        "description": "Broken benches block the corridor exit",
        "expected": "school",
    },
    {
        "title": "Deep pothole on the main road",
        "description": "Vehicles swerve dangerously near the bus stop",
        "expected": "road",
    },
    {
        "title": "Streetlight out for three weeks",
        "description": "Dark stretch of road at night near the market",
        "expected": "road",
    },
    {
        "title": "Missing signage on the highway curve",
        "description": "No warning board before the sharp bend",
        "expected": "road",
    },
    {
        "title": "Drinking water pipe leaking at the junction",
        "description": "Clean water wasting for days",
        "expected": "water",
    },
    {
        "title": "No water supply in the colony",
        "description": "Taps run dry since Tuesday",
        "expected": "water",
    },
    {
        "title": "Garbage pile near the drain",
        "description": "Waste blocks water flow and breeds mosquitoes",
        "expected": "sanitation",
    },
    {
        "title": "Open sewage channel flooded",
        "description": "Stagnant water overflows onto the lane",
        "expected": "sanitation",
    },
    {
        "title": "Library roof leaks during rain",
        "description": "Books are getting damaged",
        "expected": "school",
    },
    {
        "title": "New community library opened in ward 12",
        "description": "Announcement about the upcoming facility",
        "expected": "school",
    },
]

DUPLICATE_PAIRS: list[tuple[str, str]] = [
    (
        "Deep pothole on the main road before the bus stop",
        "Large pothole on the main road near the bus stop",
    ),
    (
        "Classroom fans stopped working today",
        "All classroom ceiling fans are not working",
    ),
]
DISSIMILAR_PAIR = (
    "Deep pothole on the main road",
    "Drinking water pipe leaking at the junction",
)


async def run() -> dict[str, Any]:
    gateway = StubGateway(model_id="deepseek-chat")
    correct = 0
    by_category: dict[str, list[str]] = {}
    for entry in GOLDEN_SET:
        result = await gateway.analyze(prompt=f"{entry['title']} {entry['description']}")
        suggested = result.content["suggested_category"]
        by_category.setdefault(entry["expected"], []).append(suggested)
        if suggested == entry["expected"]:
            correct += 1

    dup_scores = [similarity(a, b) for a, b in DUPLICATE_PAIRS]
    dissim_score = similarity(*DISSIMILAR_PAIR)

    accuracy = correct / len(GOLDEN_SET)
    metrics = {
        "gateway": gateway.provider,
        "model_id": gateway.model_id,
        "golden_size": len(GOLDEN_SET),
        "category_accuracy": round(accuracy, 4),
        "duplicate_pair_similarity": round(min(dup_scores), 4),
        "dissimilar_pair_similarity": round(dissim_score, 4),
        "per_category_accuracy": {
            cat: round(sum(1 for s in votes if s == cat) / len(votes), 4)
            for cat, votes in sorted(by_category.items())
        },
    }
    out = Path(__file__).resolve().parent.parent / "eval" / "metrics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2))
    return metrics


async def main() -> int:
    metrics = await run()
    print(json.dumps(metrics, indent=2))
    ok = (
        metrics["category_accuracy"] >= ACCURACY_FLOOR
        and metrics["duplicate_pair_similarity"] > metrics["dissimilar_pair_similarity"]
    )
    if not ok:
        print(f"EVAL FAILED (floor {ACCURACY_FLOOR})", file=sys.stderr)
        return 1
    print("EVAL OK: metrics recorded to eval/metrics.json")
    return 0


if __name__ == "__main__":
    random.seed(0)
    raise SystemExit(asyncio.run(main()))
