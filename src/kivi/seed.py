"""Replay a fixed observation script so a reviewer (or the eval harness)
reaches a known, interesting memory state without hand-typing dictations."""
import json
from pathlib import Path

from kivi.config import ROOT_DIR
from kivi.pipeline import learn_correction, process_dictation

SEED_PATH = Path(ROOT_DIR) / "seed" / "observations.jsonl"


def load_events(path: Path = SEED_PATH) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def replay(conn, events: list[dict], user_id: str = "default") -> int:
    for event in events:
        if event["type"] == "dictation":
            process_dictation(conn, event["raw"], event["formatted"], user_id=user_id)
        elif event["type"] == "correction":
            learn_correction(conn, event["wrong"], event["right"], user_id=user_id)
        else:
            raise ValueError(f"unknown seed event type: {event['type']}")
    return len(events)
