# The Words Kivi Keeps — phonetic memory

Kivi's word-level correction system: it learns, through ordinary use, how a
specific person spells the words that ASR keeps getting wrong — names,
products, invented terms — and applies that knowledge to future transcripts.
The smallest system that makes Kivi feel like it has met this person before.

```
raw ASR:       ask aditya to review the sarvam kiwi service
formatted:     Ask Aditya to review the Sarvam Kiwi service.
memory-aware:  Ask Aaditya to review the Sarvam Kivi service.
```

See **RUN.md** for setup and the demo walkthrough.

## Why this problem is structural

ASR picks the transcript that maximizes `P(audio|text) × P(text)`, and that
language-model prior is trained on the general population. Personal proper
nouns are exactly the words starved of training-data support, so they lose to
common homophones — "kiwi" beats "Kivi" every time. Homophones like
Aditya/Aaditya are *acoustically identical*; no better acoustic model can fix
this, because the disambiguating signal is not in the audio. It's in the
user's history. The formatting LLM then polishes whatever ASR handed it — it
doesn't re-derive correctness — so the error survives to the final text.

Hence a third stage that consults per-user memory. Its retrieval key is
**sound, not meaning**: `spoken-form-cluster → correct surface form`. Kivi the
product and kiwi the fruit are semantically unrelated but phonetically
identical; an embedding retriever would never cluster them, a phonetic one
must.

## What "remembering a word" means here

A memory is a phonetic cluster with one canonical spelling and a graduated
lifecycle:

```
                 3 consistent sightings
   candidate ───────────────────────────────► active (0.75)
   (0.20)  │
           │ conflicting spelling observed
           └───────────────────────────────► ambiguous (frozen until corrected)

   explicit correction ────────────────────► active (0.95), overrides everything
```

Two kinds of evidence, deliberately unequal:

- **Repetition** — a rare capitalized token showing up in formatted output.
  Weak: it mostly tells us what the formatter already does. Three consistent
  sightings promote a memory; it can fix *misspellings* of rare words but can
  never overwrite a real English word.
- **Explicit correction** — the user saying "you wrote X, I meant Y". Strong:
  instantly active at 0.95, overrides prior spellings, resolves ambiguity, and
  is the only evidence that unlocks correcting common English words.

The asymmetry is the core design stance. Missing a correction is mildly
annoying; silently "fixing" a word that was already right corrupts text the
user never asked to change. The system is built to earn trust through
restraint, and the eval scores restraint explicitly.

Each memory also has a `category` (e.g. `person`, `product`). It is never
inferred from spelling or repetition alone -- phonetic evidence tells us how a
word sounds, not what it refers to. Two ways it can be set, at different
trust levels:

- **Explicit** (`kivi correct WRONG RIGHT --category person`) -- stated by the
  person; sets `category` immediately.
- **LLM-inferred** (`--llm` mode only) -- the model reports what it thinks each
  substituted/considered term refers to, as a schema-constrained tool call, not
  free text. A single guess is recorded as evidence, not fact (`kivi show
  <id>` lists it under "category evidence"); it only promotes `category` after
  two consistent inferences with no conflict, and never overrides a category
  the person already stated. Conflicting inferences leave it `unknown` rather
  than guessing which one is right.

Anything never corrected or consistently inferred stays `unknown`, honestly.

## When it deliberately does nothing

Every non-intervention is a recorded decision with a reason:

| abstention | example |
|---|---|
| below confidence threshold | single-sighting candidate (`Figma`, 0.20 < 0.70) |
| ambiguous cluster | saw both `Ankit` and `Ankith`; waits for a correction |
| common word, no correction evidence | repetition alone never rewrites real English |
| common word kept lowercase by formatter | "ate a kiwi" — the formatter read it as the fruit; that casing is a context signal we trust |
| no matching memory | unknown name → learn a candidate, touch nothing |

## Architecture

```
dictation (raw ASR + formatted) ──► APPLY ──► memory-aware text + decisions
                                      │
                                      ▼
                                    LEARN ──► candidates / promotions / ambiguity
```

- **Apply before learn**, and learning reads only the *formatted* text — never
  our own output — so the system cannot amplify its own corrections in a
  feedback loop.
- **Matching** (`phonetics.py`): metaphone equality, or near-miss metaphone
  (code edit distance 1 + same first letter + surface edit distance 1), gated
  by Levenshtein distance. The near-miss rule exists because metaphone alone
  splits kiwi/kivi (KW/KF) and aditya/aaditya — the exact pairs this system
  is for. Common-word detection uses wordfreq zipf scores.
- **Application is deterministic** span replacement, not an LLM call: exact,
  explainable, sub-millisecond, free, and reproducible in evals. `llm.py`
  shows how the same retrieved memories are rendered into the real formatting
  prompt (`kivi dictate --llm` runs it); only memories phonetically touched by
  the current text are injected, so the prompt never grows with total memory.
- **Storage** (SQLite, `migrations/001_init.sql`): `memory_entries` (cluster,
  canonical form, status, confidence), `memory_variants` (every observed
  surface form with its signal type and source dictation — the evidence
  trail), `decisions` (every intervention *and* abstention with a
  human-readable reason), `dictations` (the transcript levels).

## Evaluation

`python eval/run_eval.py` — deterministic, no network. Each of the 58 cases
resets the DB, replays the identical seed script, runs one dictation, and is
classified as **useful_intervention / correct_abstention /
incorrect_intervention / missed_correction** — separating useful from
unnecessary interventions rather than reporting pass/fail. Per-case records
keep inputs, expected, actual, decision reasons, relevant memory state, and
latency.

Both the seed corpus (`seed/observations.jsonl`, 88 events) and the eval
corpus (`eval/cases.jsonl`, 58 cases) are generated by
`scripts/generate_corpus.py` — 32 identities (20 names, 12 products) spanning
every state a memory can be in (promoted, explicitly corrected, ambiguous,
single-sighting candidate), plus 6 spelling-collision products (Kivi/kiwi and
5 more built the same way: Lyft/lift, Xoom/zoom, Xero/zero, Fyre/fire,
Flickr/flicker) so the brief's one worked example isn't the only collision
type exercised. Regenerate with:
`PYTHONPATH=src .venv/bin/python scripts/generate_corpus.py`.

Current results (`eval/results/`): 32 useful interventions, 20 correct
abstentions, 6 incorrect interventions, 0 missed corrections — intervention
precision 0.842, recall 1.0, avg latency <1 ms, 0 LLM calls, DB ≈ 80 KB after
seeding. All 6 incorrect interventions are the same documented limitation
(sentence-start homographs, below) reproduced across all 6 collision
products — not 6 different bugs, and not hidden by curating them out.

## Limitations

- **Sentence-start homographs**: a correction-backed memory will wrongly fire
  on "Kiwi is my favorite fruit." (see above). Reproduces identically across
  all 6 collision products in the eval corpus, not just Kivi/kiwi — sentence-
  start capitalization is indistinguishable from intentional capitalization
  using casing alone. Fixing this needs semantic context, which is a
  different memory system by design.
- **Commonness is checked per spelling, not per cluster** — found and fixed
  during corpus expansion: `Flickr` (the stylized product spelling, zipf
  3.33) sits *above* `COMMON_WORD_ZIPF_THRESHOLD` while `flicker` (the
  ordinary word, zipf 3.10) sits just *below* it, so the common-word caution
  used to check only the token as written and missed the lowercase literal
  case entirely. Fixed by checking both the token and its matched canonical
  form; verified against the full 58-case suite with zero regressions.
- **Nicknames are out of scope**: "Abhishek" → "Abhi" is an entity
  relationship, not a phonetic one; merging them would break the sound-based
  contract.
- **English-centric**: metaphone and wordfreq are tuned for English;
  code-switched Hindi dictation would need a different phonetic encoder.
- **Single canonical form per cluster**: a user who genuinely knows both an
  Aditya and an Aaditya will see the cluster go ambiguous and stay hands-off
  (safe, but never auto-corrects for either).
- **No decay**: stale memories keep their confidence forever; `last_seen_at`
  is stored so decay could be added, but wasn't needed for this scope.
- **Trusts corrections absolutely**: a mistaken correction takes effect
  immediately; `kivi correct` again (or the `retired` status) is the undo.

## AI use

Built with Claude Code: design discussion, implementation, and eval design
were done in conversation; all decisions above were made deliberately and the
code was reviewed and tested end-to-end (`eval/run_eval.py` plus manual CLI
runs) by the author.
