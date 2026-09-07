"""Reproducible evaluation of the phonetic memory system.

For every case: reset the DB, replay the full seed script (identical learned
state each time -- no cross-case contamination), run the dictation, and
classify the outcome:

    useful_intervention    changed the text, and to exactly the expected result
    correct_abstention     left the text alone, and that was right
    incorrect_intervention changed the text when it should not have,
                           or changed it to the wrong thing
    missed_correction      left the text alone when it should have intervened

The distinction the brief asks for -- useful vs. unnecessary/incorrect --
falls out of the classification directly. The run is deterministic: no LLM
calls, fixed seed, fixed cases.

Usage: python eval/run_eval.py            (writes eval/results/)
"""
import json
import os
import sys
import time
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
ROOT = EVAL_DIR.parent
DB_PATH = EVAL_DIR / "results" / "eval.db"
os.environ["KIVI_DB_PATH"] = str(DB_PATH)  # must precede kivi imports
sys.path.insert(0, str(ROOT / "src"))

from kivi import store                      # noqa: E402
from kivi.db import get_connection, init_db  # noqa: E402
from kivi.phonetics import is_phonetic_match, tokenize  # noqa: E402
from kivi.pipeline import process_dictation  # noqa: E402
from kivi.seed import load_events, replay   # noqa: E402


def classify(case, actual: str) -> str:
    intervened = actual != case["formatted"]
    if intervened:
        return "useful_intervention" if actual == case["expected"] else "incorrect_intervention"
    return "missed_correction" if case["formatted"] != case["expected"] else "correct_abstention"


def relevant_memory_state(conn, text: str) -> list[dict]:
    tokens = tokenize(text)
    return [dict(m) for m in store.get_memories(conn)
            if any(is_phonetic_match(t.split("'")[0], m["canonical_form"]) for t in tokens if t)]


def main() -> None:
    cases = [json.loads(l) for l in (EVAL_DIR / "cases.jsonl").read_text().splitlines() if l.strip()]
    seed_events = load_events()
    records, latencies = [], []

    for case in cases:
        init_db(reset=True)
        conn = get_connection()
        try:
            replay(conn, seed_events)
            memory_before = relevant_memory_state(conn, case["formatted"])
            t0 = time.perf_counter()
            result = process_dictation(conn, case["raw"], case["formatted"])
            latency_ms = (time.perf_counter() - t0) * 1000
        finally:
            conn.close()

        latencies.append(latency_ms)
        outcome = classify(case, result.memory_aware_text)
        records.append({
            "id": case["id"],
            "name": case["name"],
            "inputs": {"raw_asr": case["raw"], "formatted": case["formatted"]},
            "expected": case["expected"],
            "actual": result.memory_aware_text,
            "should_intervene": case["should_intervene"],
            "outcome": outcome,
            "decisions": [{"token": d.token, "action": d.action, "reason": d.reason,
                           "confidence": d.confidence, "replacement": d.replacement}
                          for d in result.decisions],
            "relevant_memory_state": memory_before,
            "latency_ms": round(latency_ms, 2),
        })

    counts = {k: 0 for k in ("useful_intervention", "correct_abstention",
                             "incorrect_intervention", "missed_correction")}
    for r in records:
        counts[r["outcome"]] += 1
    interventions = counts["useful_intervention"] + counts["incorrect_intervention"]
    should = sum(1 for r in records if r["should_intervene"])
    precision = counts["useful_intervention"] / interventions if interventions else 1.0
    recall = counts["useful_intervention"] / should if should else 1.0

    db_bytes = DB_PATH.stat().st_size
    conn = get_connection()
    row_counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("dictations", "memory_entries", "memory_variants", "decisions")}
    conn.close()

    summary = {
        "total_cases": len(records),
        "outcomes": counts,
        "intervention_precision": round(precision, 3),
        "intervention_recall": round(recall, 3),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
        "max_latency_ms": round(max(latencies), 2),
        "llm_calls": 0,
        "llm_cost_usd": 0.0,
        "db_size_bytes_after_seed_plus_one_dictation": db_bytes,
        "db_rows_last_run": row_counts,
    }

    results_dir = EVAL_DIR / "results"
    results_dir.mkdir(exist_ok=True)
    (results_dir / "results.json").write_text(
        json.dumps({"summary": summary, "cases": records}, indent=2) + "\n")

    lines = ["# Eval results", "",
             f"{summary['total_cases']} cases | precision {summary['intervention_precision']} "
             f"| recall {summary['intervention_recall']} "
             f"| avg latency {summary['avg_latency_ms']}ms | LLM calls: 0", "",
             "| case | outcome | actual |", "|---|---|---|"]
    for r in records:
        lines.append(f"| {r['id']} | {r['outcome']} | {r['actual']} |")
    lines += ["", "## Outcome counts", ""]
    lines += [f"- {k}: {v}" for k, v in counts.items()]
    (results_dir / "summary.md").write_text("\n".join(lines) + "\n")

    print(json.dumps(summary, indent=2))
    for r in records:
        mark = {"useful_intervention": "+", "correct_abstention": "=",
                "incorrect_intervention": "!", "missed_correction": "-"}[r["outcome"]]
        print(f" [{mark}] {r['id']:24} {r['outcome']}")
    print(f"\nwrote {results_dir}/results.json and summary.md")


if __name__ == "__main__":
    main()
