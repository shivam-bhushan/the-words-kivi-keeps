# RUN.md

Tested with Python 3.13 on macOS; any Python ≥ 3.10 should work.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export PYTHONPATH=src
alias kivi=".venv/bin/python -m kivi.cli"
```

No API key is needed for the default (deterministic) mode. To try the optional
LLM-apply mode, copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`.

Environment variables (all optional, see `.env.example`):

- `KIVI_DB_PATH` — SQLite file location (default `./kivi.db`)
- `ANTHROPIC_API_KEY` — only for `dictate --llm`
- `KIVI_LLM_MODEL` — model for `--llm` mode (default `claude-sonnet-5`)

## Demo walkthrough

```bash
kivi init                 # create the database
kivi seed                 # replay seed/observations.jsonl -> known memory state
kivi memories             # inspect what Kivi remembers

# the brief's flagship example — both words fixed:
kivi dictate "ask aditya to review the sarvam kiwi service" \
             "Ask Aditya to review the Sarvam Kiwi service."

# deliberate abstention — kiwi the fruit is left alone:
kivi dictate "i ate a kiwi for breakfast" "I ate a kiwi for breakfast."

# teach an explicit correction:
kivi correct "Ankit" "Ankith"         # (wrong-form, right-form) — also resolves the ambiguous cluster
kivi correct "Ankit" "Ankith" --category person   # optional: state what kind of term this is
                                                    # (never guessed from spelling — see kivi memories)

# --llm mode also reports inferred categories (person/product/place/other) via
# a forced tool call; run the flagship dictate --llm twice to see one promote:
kivi dictate --llm "ask aditya to review the sarvam kiwi service" \
             "Ask Aditya to review the Sarvam Kiwi service."

kivi show 2               # one memory with its full evidence trail, incl. category evidence
kivi explain 12           # replay every decision for dictation #12
kivi history              # recent dictations
kivi reset                # wipe everything and start over
```

Every `dictate` prints the three transcript levels (raw ASR, formatted,
memory-aware) and one line per decision explaining why the system intervened
or deliberately did not.

## Evaluation

```bash
.venv/bin/python eval/run_eval.py
```

Deterministic, no network, no API key. For each case it resets the DB, replays
the full seed script, runs the dictation, and classifies the outcome. Writes
`eval/results/results.json` (full per-case records: inputs, expected, actual,
decisions, relevant memory state, latency) and `eval/results/summary.md`.

## Reset

```bash
kivi reset -y             # or: rm -f kivi.db && kivi init
```

## Versions

Pinned in `requirements.txt`: typer 0.27.2, jellyfish 1.1.0, wordfreq 3.1.1,
anthropic 0.34.2, python-dotenv 1.0.1, rich 13.8.1.
