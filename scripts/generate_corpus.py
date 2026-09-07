"""Generates seed/observations.jsonl and eval/cases.jsonl.

Kept as the source of truth for the corpus so it's reproducible and
extensible, per the brief's ask for "reproducible seed data" -- run this to
regenerate both files:

    PYTHONPATH=src .venv/bin/python scripts/generate_corpus.py

The corpus is organised around ~32 identities (20 person names, 12 product
names), each assigned one of four "arcs" describing how its memory should
end up after the seed replay: promoted by repetition, promoted then
explicitly corrected, left ambiguous, or left as a single-sighting
candidate. Eval cases are then generated to exercise every arc, plus a set
of hand-picked edge cases (negative controls, multi-token corrections,
sentence-start homographs) that no template loop would produce on its own.

This is deliberately not padded to hit a round number -- every generated
record exercises a specific, named behaviour. See the "why" comment above
each block.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kivi.phonetics import is_phonetic_match  # noqa: E402  (sanity-check pairs below)

# ---------------------------------------------------------------------------
# Identities. (correct, common_asr_error) -- verified with is_phonetic_match
# below before anything is generated from them.
# ---------------------------------------------------------------------------

NAMES_PROMOTED = [
    # "Mira" (a plausible ASR mishearing of Meera) is itself common English
    # (zipf 3.27) -- using it would make this an is_common_english_word case,
    # not a plain promoted-name case, so "Meira" is used instead.
    ("Priya", "Pria"), ("Meera", "Meira"), ("Nikhil", "Nikil"),
    ("Ananya", "Ananiya"), ("Sana", "Sanaa"), ("Arjun", "Arjoon"),
    ("Yash", "Yesh"), ("Aarav", "Arav"), ("Kavya", "Kaviya"), ("Riya", "Riyaa"),
]
NAMES_CORRECTED = [
    ("Aaditya", "Aditya"), ("Ishaan", "Ishan"), ("Vihaan", "Vihan"), ("Simran", "Simren"),
    # "Rohan" and "Diya" sit at/above COMMON_WORD_ZIPF_THRESHOLD (3.2) --
    # repetition learning is blocked outright for them, same as any common
    # word, so they can only ever be learned via explicit correction. A
    # genuine edge case, not a promoted-arc name.
    ("Rohan", "Rohaan"), ("Diya", "Dia"),
]
NAMES_AMBIGUOUS = [
    ("Ankith", "Ankit"), ("Kabir", "Cabir"),
]
NAMES_CANDIDATE = [
    ("Tanvi", "Tanavi"), ("Devansh", "Devanash"),
]

# Common-word collisions crossing COMMON_WORD_ZIPF_THRESHOLD (3.2) -- like the
# brief's own Kivi/kiwi example, these can only ever be learned via explicit
# correction (kivi.pipeline._learn_from_dictation skips repetition-learning
# for common words outright). "Flickr" belongs here too, somewhat by
# surprise: the *stylized* spelling itself has zipf 3.33 (>= threshold),
# because the real product was popular enough that "flickr" is common in the
# web text wordfreq is built from -- not just its dictionary-word neighbour
# "flicker" (3.10). Found by generating this corpus, not assumed in advance.
PRODUCTS_COLLISION_HIGH = [
    ("Kivi", "kiwi"), ("Lyft", "lift"), ("Xoom", "zoom"), ("Xero", "zero"), ("Fyre", "fire"),
    ("Flickr", "Flicker"),
]
# Near-miss collisions: superficially word-like, but *both* spellings sit
# below the zipf cutoff, so they behave like ordinary rare candidates -- a
# useful contrast showing the threshold is a deliberate line, not "anything
# word-shaped is risky".
PRODUCTS_NEAR_MISS = [
    ("Fiverr", "Fiver"), ("Scribd", "Scribed"),
]
PRODUCTS_PLAIN = [
    ("Sarvam", "Sarvaam"), ("Figma", "Figmaa"), ("Coda", "Codaa"),
    ("Asana", "Assana"), ("Canva", "Canvaa"),
]
PRODUCTS_CANDIDATE = [
    ("Loom", "Looum"),
]

ALL_PAIRS = (NAMES_PROMOTED + NAMES_CORRECTED + NAMES_AMBIGUOUS + NAMES_CANDIDATE
             + PRODUCTS_COLLISION_HIGH + PRODUCTS_NEAR_MISS + PRODUCTS_PLAIN + PRODUCTS_CANDIDATE)
for right, wrong in ALL_PAIRS:
    assert is_phonetic_match(right, wrong), f"{right} / {wrong} do not phonetically match"

NAME_TEMPLATES = [
    ("ask {x} to review the pull request", "Ask {x} to review the pull request."),
    ("can you loop in {x} before the call", "Can you loop in {x} before the call?"),
    ("send the invoice to {x} please", "Send the invoice to {x} please."),
    ("{x} is joining the standup at ten", "{x} is joining the standup at ten."),
    ("remind me to email {x} tomorrow", "Remind me to email {x} tomorrow."),
    ("schedule a sync with {x} and the design team", "Schedule a sync with {x} and the design team."),
    ("{x} mentioned the deadline moved to friday", "{x} mentioned the deadline moved to Friday."),
    ("forward this thread to {x}", "Forward this thread to {x}."),
    ("tell {x} the deck is ready for review", "Tell {x} the deck is ready for review."),
]
PRODUCT_TEMPLATES = [
    ("push the update to {x} before lunch", "Push the update to {x} before lunch."),
    ("check if {x} synced the latest changes", "Check if {x} synced the latest changes."),
    ("open {x} and pull the latest board", "Open {x} and pull the latest board."),
    ("the {x} integration needs testing", "The {x} integration needs testing."),
    ("file a bug against {x}", "File a bug against {x}."),
    ("can we move this conversation to {x}", "Can we move this conversation to {x}?"),
    ("restart the {x} service", "Restart the {x} service."),
    ("{x} just shipped a new release", "{x} just shipped a new release."),
]

seed_events = []
eval_cases = []


def add_seed(kind, **kw):
    seed_events.append({"type": kind, **kw})


def add_case(id_, name, raw, formatted, expected, should_intervene):
    eval_cases.append({
        "id": id_, "name": name, "raw": raw, "formatted": formatted,
        "expected": expected, "should_intervene": should_intervene,
    })


def name_sentence(word, i):
    raw_t, fmt_t = NAME_TEMPLATES[i % len(NAME_TEMPLATES)]
    return raw_t.format(x=word.lower()), fmt_t.format(x=word)


def product_sentence(word, i):
    raw_t, fmt_t = PRODUCT_TEMPLATES[i % len(PRODUCT_TEMPLATES)]
    return raw_t.format(x=word.lower()), fmt_t.format(x=word)


# ---------------------------------------------------------------------------
# Seed: promoted names -- 3 consistent repetitions of the RIGHT spelling ->
# active (0.75). Repetition can only ever lock in whatever spelling it
# actually saw -- seeding with the wrong form would teach the wrong form as
# canonical, which is exactly the mistake this generator caught on its first
# run (see git history / the note in the corpus-doc artifact).
# ---------------------------------------------------------------------------
for right, wrong in NAMES_PROMOTED:
    for i in range(3):
        raw, fmt = name_sentence(right, i)
        add_seed("dictation", raw=raw, formatted=fmt)

# ---------------------------------------------------------------------------
# Seed: corrected names -- 3 repetitions, then an explicit correction (0.95)
# ---------------------------------------------------------------------------
for right, wrong in NAMES_CORRECTED:
    for i in range(3):
        raw, fmt = name_sentence(wrong, i)
        add_seed("dictation", raw=raw, formatted=fmt)
    add_seed("correction", wrong=wrong, right=right)

# ---------------------------------------------------------------------------
# Seed: ambiguous names -- one spelling, then a conflicting spelling, no
# correction. Mirrors the brief's own "wait for a correction" stance.
# ---------------------------------------------------------------------------
for right, wrong in NAMES_AMBIGUOUS:
    raw, fmt = name_sentence(wrong, 0)
    add_seed("dictation", raw=raw, formatted=fmt)
    raw, fmt = name_sentence(right, 1)
    add_seed("dictation", raw=raw, formatted=fmt)

# ---------------------------------------------------------------------------
# Seed: candidate names -- a single sighting, deliberately left too weak.
# ---------------------------------------------------------------------------
for right, wrong in NAMES_CANDIDATE:
    raw, fmt = name_sentence(wrong, 0)
    add_seed("dictation", raw=raw, formatted=fmt)

# ---------------------------------------------------------------------------
# Seed: high-collision products -- explicit correction only (repetition is
# blocked outright for common words by pipeline._learn_from_dictation).
# ---------------------------------------------------------------------------
for right, wrong in PRODUCTS_COLLISION_HIGH:
    add_seed("correction", wrong=wrong, right=right)

# ---------------------------------------------------------------------------
# Seed: near-miss products -- below the common-word cutoff, so ordinary
# repetition promotion applies just like a plain rare product.
# ---------------------------------------------------------------------------
for right, wrong in PRODUCTS_NEAR_MISS:
    for i in range(3):
        raw, fmt = product_sentence(right, i)
        add_seed("dictation", raw=raw, formatted=fmt)

# ---------------------------------------------------------------------------
# Seed: plain products -- ordinary repetition promotion.
# ---------------------------------------------------------------------------
for right, wrong in PRODUCTS_PLAIN:
    for i in range(3):
        raw, fmt = product_sentence(right, i)
        add_seed("dictation", raw=raw, formatted=fmt)

# ---------------------------------------------------------------------------
# Seed: candidate product -- single sighting.
# ---------------------------------------------------------------------------
for right, wrong in PRODUCTS_CANDIDATE:
    raw, fmt = product_sentence(wrong, 0)
    add_seed("dictation", raw=raw, formatted=fmt)


# ===========================================================================
# EVAL CASES
# ===========================================================================

# --- promoted names: useful intervention on a *fresh* misspelling ---------
for right, wrong in NAMES_PROMOTED:
    raw, fmt = name_sentence(wrong, 7)  # a template not used during seeding
    raw2, fmt2 = name_sentence(right, 7)
    add_case(f"promoted-{right.lower()}", f"Repetition-promoted '{right}' fixes a fresh misspelling",
              raw, fmt, fmt2, True)

# a subset also get an "already correct, stay quiet" companion
for right, wrong in NAMES_PROMOTED[:4]:
    raw, fmt = name_sentence(right, 8)
    add_case(f"already-correct-{right.lower()}", f"'{right}' already spelled right: no decision, just quiet evidence",
              raw, fmt, fmt, False)

# --- corrected names: correction-tier confidence fixes a new misspelling --
# Template 4 (non-sentence-start, and not one of the 0/1/2 templates used
# during seeding) so this is a genuinely fresh sentence testing what it's
# meant to test -- whether explicit correction fires -- independent of the
# sentence-start gate below, which "Rohan"/"Diya" would otherwise also trip
# since both cross the common-word threshold.
for right, wrong in NAMES_CORRECTED:
    raw, fmt = name_sentence(wrong, 4)
    raw2, fmt2 = name_sentence(right, 4)
    add_case(f"corrected-{right.lower()}", f"Explicit correction for '{right}' fires on a fresh misspelling",
              raw, fmt, fmt2, True)

# --- known tradeoff: correction-backed but common-word-crossing NAMES hit
# the same sentence-start information gap as the collision products. Fixing
# the false-positive there (Kivi/kiwi) necessarily means this symmetric
# false-negative is possible too: "Rohaan mentioned..." and "Kiwi is my
# favorite fruit" are identical to the deterministic path (capitalized,
# sentence-start, common-word match, correction-backed) with opposite
# correct answers -- casing alone cannot distinguish them. Documented here
# deliberately, the same way the collision-product cases are, rather than
# left as an unexplained failure.
add_case("corrected-name-sentence-start-tradeoff",
          "KNOWN TRADEOFF: correction-backed common-word name misses at sentence start "
          "(same information gap as the collision-product cases, opposite ground truth)",
          "rohaan mentioned the deadline moved to friday",
          "Rohaan mentioned the deadline moved to Friday.",
          "Rohan mentioned the deadline moved to Friday.", True)

# --- ambiguous names: still waiting for a correction ----------------------
for right, wrong in NAMES_AMBIGUOUS:
    raw, fmt = name_sentence(right, 2)
    add_case(f"ambiguous-{right.lower()}", f"Conflicting evidence for '{right}': wait for a correction",
              raw, fmt, fmt, False)

# --- candidate names: too weak to fire -------------------------------------
for right, wrong in NAMES_CANDIDATE:
    raw, fmt = name_sentence(wrong, 3)
    add_case(f"candidate-{right.lower()}", f"Single-sighting candidate '{right}' must not fire yet",
              raw, fmt, fmt, False)

# --- high-collision products: three angles each ----------------------------
LITERAL_SENTENCES = {
    "kiwi": ("i ate a kiwi for breakfast", "I ate a kiwi for breakfast."),
    "lift": ("please lift the box carefully", "Please lift the box carefully."),
    "zoom": ("the car began to zoom down the highway", "The car began to zoom down the highway."),
    "zero": ("the counter reset back to zero", "The counter reset back to zero."),
    "fire": ("please put out the fire before we leave", "Please put out the fire before we leave."),
    "flicker": ("the candle started to flicker in the wind", "The candle started to flicker in the wind."),
}
SENTENCE_START_LITERAL = {
    "kiwi": ("kiwi is my favorite fruit", "Kiwi is my favorite fruit."),
    "lift": ("lift with your legs not your back", "Lift with your legs, not your back."),
    "zoom": ("zoom lenses are heavier than primes", "Zoom lenses are heavier than primes."),
    "zero": ("zero tolerance policies rarely work", "Zero tolerance policies rarely work."),
    "fire": ("fire drills happen every month here", "Fire drills happen every month here."),
    "flicker": ("flicker is a common symptom of a loose bulb", "Flicker is a common symptom of a loose bulb."),
}
for right, wrong in PRODUCTS_COLLISION_HIGH:
    key = wrong.lower()
    # (a) product context, capitalized by the formatter -> should correct
    raw, fmt = product_sentence(wrong.capitalize(), 5)
    raw2, fmt2 = product_sentence(right, 5)
    add_case(f"collision-{key}-product", f"'{wrong.capitalize()}' in product context corrected to '{right}'",
              raw, fmt, fmt2, True)
    # (b) literal / common meaning, lowercase, mid-sentence -> must not fire.
    # KNOWN LIMITATION for "flicker": is_common_english_word runs on the
    # token as written, and "flicker" (3.10) sits just *below*
    # COMMON_WORD_ZIPF_THRESHOLD (3.2) while its own canonical form "Flickr"
    # (3.33) sits *above* it -- so the lowercase-trust safety net never
    # engages for this spelling, even though it does for kiwi/lift/zoom/
    # zero/fire. Two spellings of one phonetic cluster straddling the same
    # threshold on opposite sides. Left as a documented failure, not hidden.
    lit_raw, lit_fmt = LITERAL_SENTENCES[key]
    lit_name = (f"KNOWN LIMITATION: 'flicker' below common-word threshold while "
                f"'Flickr' sits above it -- lowercase-trust rule never engages"
                if key == "flicker" else
                f"'{key}' used with its ordinary meaning: leave it alone")
    add_case(f"collision-{key}-literal", lit_name, lit_raw, lit_fmt, lit_fmt, False)
    # (c) sentence-start homograph -- KNOWN LIMITATION, see README
    ss_raw, ss_fmt = SENTENCE_START_LITERAL[key]
    add_case(f"collision-{key}-sentence-start", f"KNOWN LIMITATION: '{key}' at sentence start, casing signal lost",
              ss_raw, ss_fmt, ss_fmt, False)

# --- near-miss products: ordinary promotion, fresh misspelling ------------
for right, wrong in PRODUCTS_NEAR_MISS:
    raw, fmt = product_sentence(wrong, 6)
    raw2, fmt2 = product_sentence(right, 6)
    add_case(f"nearmiss-{right.lower()}", f"Near-miss product '{right}' (below common-word cutoff) still promotes normally",
              raw, fmt, fmt2, True)

# --- plain products ----------------------------------------------------------
for right, wrong in PRODUCTS_PLAIN:
    raw, fmt = product_sentence(wrong, 4)
    raw2, fmt2 = product_sentence(right, 4)
    add_case(f"plain-{right.lower()}", f"Plain product '{right}' fixes a fresh misspelling",
              raw, fmt, fmt2, True)

# --- candidate product ------------------------------------------------------
for right, wrong in PRODUCTS_CANDIDATE:
    raw, fmt = product_sentence(wrong, 3)
    add_case(f"candidate-{right.lower()}", f"Single-sighting product '{right}' must not fire yet",
              raw, fmt, fmt, False)

# --- hand-picked edge cases no template loop would produce -----------------
add_case("unknown-name", "Never-seen name: nothing to do but start learning",
          "loop in ramesh tomorrow", "Loop in Ramesh tomorrow.", "Loop in Ramesh tomorrow.", False)
add_case("common-word-plain", "Ordinary English sentence: zero decisions expected",
          "the notion of fairness matters", "The notion of fairness matters.",
          "The notion of fairness matters.", False)
add_case("common-word-capitalized-no-memory", "'Notion' the product, but no memory for it: hands off",
          "update the notion doc", "Update the Notion doc.", "Update the Notion doc.", False)
add_case("possessive-fresh", "Correction survives a possessive suffix on a name not in the original example",
          "send it to ishaan's team", "Send it to Ishaan's team.", "Send it to Ishaan's team.", False)
add_case("possessive-misspelled", "Possessive suffix on a misspelled, corrected name",
          "send it to ishan's team", "Send it to Ishan's team.", "Send it to Ishaan's team.", True)
add_case("multi-token-name-and-product",
          "Two independently-learned memories corrected in one sentence",
          "ask pria to check the fiver outage", "Ask Pria to check the Fiver outage.",
          "Ask Priya to check the Fiverr outage.", True)
add_case("lowercase-name-uncapitalized", "Formatter failed to capitalize a rare, corrected name: still fix it",
          "tell ishan it works", "Tell ishan it works.", "Tell Ishaan it works.", True)
add_case("exact-match-no-decision", "Token already equals the canonical form exactly: no decision at all",
          "priya approved the design", "Priya approved the design.", "Priya approved the design.", False)


def write_jsonl(path, records):
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    write_jsonl(ROOT / "seed" / "observations.jsonl", seed_events)
    write_jsonl(ROOT / "eval" / "cases.jsonl", eval_cases)
    print(f"wrote {len(seed_events)} seed events, {len(eval_cases)} eval cases "
          f"({len(seed_events) + len(eval_cases)} total records)")
