"""The core loop: apply existing memories to a dictation, then learn from it.

Order matters: we APPLY first (using only what was known before this
dictation), then LEARN from the formatted text. Learning reads the formatted
text -- never our own memory-aware output -- so the system cannot reinforce
its own corrections in a feedback loop.

Every intervention and every deliberate non-intervention is written to the
`decisions` table with a human-readable reason.
"""
from dataclasses import dataclass, field

from kivi import store
from kivi.config import (
    APPLY_CONFIDENCE_THRESHOLD,
    CANDIDATE_CONFIDENCE,
    CATEGORY_PROMOTION_COUNT,
    CORRECTION_CONFIDENCE,
    PROMOTION_CONFIDENCE,
    PROMOTION_REPETITION_COUNT,
)
from kivi.phonetics import (
    is_candidate_token,
    is_common_english_word,
    is_phonetic_match,
    phonetic_key,
    tokenize_with_spans,
)

SENTENCE_END = ".!?"


@dataclass
class Decision:
    token: str
    action: str
    reason: str
    memory_id: int | None = None
    confidence: float | None = None
    replacement: str | None = None


@dataclass
class CategorySignal:
    canonical_form: str
    category: str
    outcome: str  # "recorded" | "promoted" | "conflict_ignored" | "skipped_already_known"
    reason: str


@dataclass
class DictationResult:
    dictation_id: int
    raw_asr: str
    formatted_text: str
    memory_aware_text: str
    decisions: list[Decision] = field(default_factory=list)


def _is_sentence_start(text: str, token_start: int) -> bool:
    """A token starts a sentence if only whitespace/quotes separate it from
    the text start or a sentence-ending punctuation mark."""
    i = token_start - 1
    while i >= 0 and text[i] in " \t\n\"'‘’“”":
        i -= 1
    return i < 0 or text[i] in SENTENCE_END


def _matches(token: str, memories) -> list:
    return [m for m in memories if is_phonetic_match(token, m["canonical_form"])]


def _apply_memories(conn, dictation_id, formatted_text, memories) -> tuple[str, list[Decision]]:
    """Produce memory-aware text from formatted text. Deterministic span
    replacement; each intervention or abstention becomes a decision row."""
    decisions: list[Decision] = []
    replacements: list[tuple[int, int, str]] = []

    for token, start, end in tokenize_with_spans(formatted_text):
        # Match on the stem so "Aditya's" still hits the memory for "Aaditya";
        # the suffix is re-attached on replacement.
        stem, suffix = token, ""
        if "'" in token:
            idx = token.index("'")
            stem, suffix = token[:idx], token[idx:]
        if not stem:
            continue

        matches = _matches(stem, memories)
        if not matches:
            if is_candidate_token(stem, is_sentence_start=_is_sentence_start(formatted_text, start)):
                decisions.append(Decision(
                    token=token, action="abstained_no_match",
                    reason=f"'{token}' looks like a personal term but no memory matches it.",
                ))
            continue

        # A token that already equals a remembered canonical form needs nothing.
        if any(stem == m["canonical_form"] for m in matches):
            continue

        actives = [m for m in matches
                   if m["status"] == "active" and m["confidence"] >= APPLY_CONFIDENCE_THRESHOLD]

        if len(actives) > 1:
            names = ", ".join(m["canonical_form"] for m in actives)
            decisions.append(Decision(
                token=token, action="abstained_ambiguous",
                reason=f"'{token}' matches multiple active memories ({names}); cannot pick one safely.",
            ))
            continue

        if len(actives) == 1:
            m = actives[0]
            # Check both spellings' commonness, not just the token as written:
            # a stylized canonical form can itself be common (e.g. "Flickr" at
            # 3.33 zipf) even when the ordinary-word spelling of the same
            # phonetic cluster sits just under the threshold (e.g. "flicker"
            # at 3.10) -- checking only `stem` let that case slip past the
            # caution entirely.
            if is_common_english_word(stem) or is_common_english_word(m["canonical_form"]):
                if m["correction_count"] == 0:
                    decisions.append(Decision(
                        token=token, action="abstained_common_word",
                        memory_id=m["id"], confidence=m["confidence"],
                        reason=(f"'{token}' is common English; repetition evidence alone is not "
                                f"enough to overwrite it with '{m['canonical_form']}'. "
                                "An explicit correction would unlock this."),
                    ))
                    continue
                if stem.islower() and m["canonical_form"][0].isupper():
                    # The formatter left a common word lowercase -- it read the
                    # context as the ordinary English word (kiwi the fruit), not
                    # a name. Trust that context signal and stay out.
                    decisions.append(Decision(
                        token=token, action="abstained_common_word",
                        memory_id=m["id"], confidence=m["confidence"],
                        reason=(f"'{token}' is common English and the formatter kept it "
                                f"lowercase, so context suggests the ordinary word, not "
                                f"'{m['canonical_form']}'. Leaving it alone."),
                    ))
                    continue
            replacements.append((start, end, m["canonical_form"] + suffix))
            decisions.append(Decision(
                token=token, action="applied",
                memory_id=m["id"], confidence=m["confidence"],
                replacement=m["canonical_form"] + suffix,
                reason=(f"'{token}' phonetically matches active memory "
                        f"'{m['canonical_form']}' (confidence {m['confidence']:.2f})."),
            ))
            continue

        best = max(matches, key=lambda m: m["confidence"])
        if best["status"] == "ambiguous":
            decisions.append(Decision(
                token=token, action="abstained_ambiguous",
                memory_id=best["id"], confidence=best["confidence"],
                reason=(f"Memory for '{best['canonical_form']}' has conflicting spelling "
                        "evidence; waiting for an explicit correction."),
            ))
        else:
            decisions.append(Decision(
                token=token, action="abstained_low_confidence",
                memory_id=best["id"], confidence=best["confidence"],
                reason=(f"'{token}' matches candidate '{best['canonical_form']}' but its "
                        f"confidence {best['confidence']:.2f} is below the apply "
                        f"threshold {APPLY_CONFIDENCE_THRESHOLD}."),
            ))

    memory_aware = formatted_text
    for start, end, new in sorted(replacements, reverse=True):
        memory_aware = memory_aware[:start] + new + memory_aware[end:]

    for d in decisions:
        store.insert_decision(conn, dictation_id, memory_id=d.memory_id, token_span=d.token,
                              action=d.action, confidence=d.confidence, reason=d.reason)
    return memory_aware, decisions


def _learn_from_dictation(conn, dictation_id, formatted_text, memories, user_id) -> list[Decision]:
    """Update memory from the formatted text: create candidates, accumulate
    repetition evidence, promote, or flag conflicts as ambiguous.

    Evidence is counted at most once per memory per dictation, so saying a
    word three times in one breath does not fake three days of usage.
    """
    decisions: list[Decision] = []
    touched_memory_ids: set[int] = set()
    created_keys: set[str] = set()

    for token, start, end in tokenize_with_spans(formatted_text):
        if "'" in token:
            continue  # possessives etc. -- out of scope, see README limitations
        if not is_candidate_token(token, is_sentence_start=_is_sentence_start(formatted_text, start)):
            continue
        if is_common_english_word(token):
            continue  # common words only enter memory via explicit correction

        matches = _matches(token, memories)
        if not matches:
            key = phonetic_key(token)
            if key in created_keys:
                continue
            created_keys.add(key)
            memory_id = store.create_memory(
                conn, token, key, user_id=user_id, confidence=CANDIDATE_CONFIDENCE)
            store.insert_variant(conn, memory_id, token, "repetition", dictation_id)
            d = Decision(token=token, action="learned_candidate", memory_id=memory_id,
                         confidence=CANDIDATE_CONFIDENCE,
                         reason=f"First sighting of '{token}'; stored as a candidate, not yet applied.")
            decisions.append(d)
            continue

        m = max(matches, key=lambda m: m["confidence"])
        if m["id"] in touched_memory_ids:
            continue
        touched_memory_ids.add(m["id"])

        if token.lower() == m["canonical_form"].lower():
            new_count = m["evidence_count"] + 1
            store.insert_variant(conn, m["id"], token, "repetition", dictation_id)
            if m["status"] == "candidate" and new_count >= PROMOTION_REPETITION_COUNT:
                store.update_memory(conn, m["id"], status="active",
                                    confidence=PROMOTION_CONFIDENCE, bump_evidence=True)
                decisions.append(Decision(
                    token=token, action="learned_promoted", memory_id=m["id"],
                    confidence=PROMOTION_CONFIDENCE,
                    reason=(f"'{m['canonical_form']}' seen consistently {new_count} times; "
                            "promoted to active."),
                ))
            else:
                store.update_memory(conn, m["id"], bump_evidence=True)
        else:
            # Same phonetic cluster, different spelling.
            store.insert_variant(conn, m["id"], token, "repetition", dictation_id)
            if m["correction_count"] > 0 or m["status"] == "active":
                # An established memory outranks a stray variant; the apply
                # phase already corrected (or deliberately skipped) this token.
                store.update_memory(conn, m["id"])
            elif m["status"] == "candidate":
                store.update_memory(conn, m["id"], status="ambiguous")
                decisions.append(Decision(
                    token=token, action="learned_ambiguous", memory_id=m["id"],
                    confidence=m["confidence"],
                    reason=(f"Seen both '{m['canonical_form']}' and '{token}' for the same "
                            "sound; marked ambiguous until an explicit correction resolves it."),
                ))

    for d in decisions:
        store.insert_decision(conn, dictation_id, memory_id=d.memory_id, token_span=d.token,
                              action=d.action, confidence=d.confidence, reason=d.reason)
    return decisions


def process_dictation(conn, raw_asr: str, formatted_text: str,
                      user_id: str = "default") -> DictationResult:
    dictation_id = store.insert_dictation(conn, raw_asr, formatted_text, user_id=user_id)
    memories = store.get_memories(conn, user_id)
    memory_aware, apply_decisions = _apply_memories(conn, dictation_id, formatted_text, memories)
    learn_decisions = _learn_from_dictation(conn, dictation_id, formatted_text, memories, user_id)
    store.set_memory_aware_text(conn, dictation_id, memory_aware)
    conn.commit()
    return DictationResult(dictation_id, raw_asr, formatted_text, memory_aware,
                           apply_decisions + learn_decisions)


def learn_correction(conn, wrong: str, right: str, user_id: str = "default",
                     category: str | None = None) -> DictationResult:
    """Explicit user correction: 'you wrote WRONG, it should be RIGHT'.
    Strongest evidence we have -- creates or overrides a memory at high
    confidence and resolves any ambiguity in the cluster.

    `category` is optional and only ever set from an explicit statement by
    the person, never inferred from spelling or repetition -- we have no
    phonetic evidence for what kind of thing a word refers to, only for how
    it should be spelled."""
    dictation_id = store.insert_dictation(
        conn, wrong, right, user_id=user_id, is_explicit_correction=True,
        correction_wrong=wrong, correction_right=right)
    memories = store.get_memories(conn, user_id)
    matches = [m for m in memories
               if is_phonetic_match(right, m["canonical_form"])
               or is_phonetic_match(wrong, m["canonical_form"])]

    if matches:
        m = max(matches, key=lambda m: m["confidence"])
        store.update_memory(conn, m["id"], canonical_form=right, status="active",
                            confidence=CORRECTION_CONFIDENCE, category=category,
                            bump_evidence=True)
        memory_id = m["id"]
        reason = (f"Explicit correction '{wrong}' -> '{right}' overrides existing memory "
                  f"'{m['canonical_form']}' (was {m['status']}, {m['confidence']:.2f}).")
    else:
        memory_id = store.create_memory(
            conn, right, phonetic_key(right), user_id=user_id,
            status="active", confidence=CORRECTION_CONFIDENCE,
            category=category or "unknown")
        reason = f"Explicit correction '{wrong}' -> '{right}' stored as new active memory."

    store.insert_variant(conn, memory_id, wrong, "explicit_correction", dictation_id)
    if category:
        store.insert_category_signal(conn, memory_id, category, "explicit", dictation_id)
    decision = Decision(token=wrong, action="learned_correction", memory_id=memory_id,
                        confidence=CORRECTION_CONFIDENCE, replacement=right, reason=reason)
    store.insert_decision(conn, dictation_id, memory_id=memory_id, token_span=wrong,
                          action="learned_correction", confidence=CORRECTION_CONFIDENCE,
                          reason=reason)
    store.set_memory_aware_text(conn, dictation_id, right)
    conn.commit()
    return DictationResult(dictation_id, wrong, right, right, [decision])


def record_category_signals(conn, dictation_id: int, categories: dict[str, str],
                            memories) -> list[CategorySignal]:
    """Persist LLM-inferred categories as low-trust evidence and promote to
    memory_entries.category only after repeated, consistent agreement -- the
    same trust-tiering used for spelling. Never overrides a category already
    set (whether by an earlier promotion or an explicit correction)."""
    by_form = {m["canonical_form"]: m for m in memories}
    signals: list[CategorySignal] = []

    for canonical_form, category in categories.items():
        m = by_form.get(canonical_form)
        if m is None:
            continue  # defensive; llm.apply_with_llm already filters to known forms

        store.insert_category_signal(conn, m["id"], category, "llm_inferred", dictation_id)

        if m["category"] != "unknown":
            signals.append(CategorySignal(
                canonical_form, category, "skipped_already_known",
                f"'{canonical_form}' already has category '{m['category']}'; "
                "inference recorded but not used to change it."))
            continue

        history = store.get_category_signals(conn, m["id"])
        inferred = [s for s in history if s["source"] == "llm_inferred"]
        matching = [s for s in inferred if s["category"] == category]
        conflicting = [s for s in inferred if s["category"] != category]

        if conflicting:
            signals.append(CategorySignal(
                canonical_form, category, "conflict_ignored",
                f"Inferred both '{category}' and conflicting categories for "
                f"'{canonical_form}'; leaving as 'unknown' until an explicit "
                "correction resolves it."))
        elif len(matching) >= CATEGORY_PROMOTION_COUNT:
            store.update_memory(conn, m["id"], category=category)
            signals.append(CategorySignal(
                canonical_form, category, "promoted",
                f"'{canonical_form}' inferred as '{category}' consistently "
                f"{len(matching)} times; promoted from 'unknown'."))
        else:
            signals.append(CategorySignal(
                canonical_form, category, "recorded",
                f"'{canonical_form}' inferred as '{category}' ({len(matching)}/"
                f"{CATEGORY_PROMOTION_COUNT} needed); not yet trusted."))

    conn.commit()
    return signals


def replace_apply_decisions(conn, dictation_id: int, llm_decisions: list[dict],
                            memories) -> list[Decision]:
    """When --llm overrides the deterministic apply step's text, the
    deterministic apply_decisions rows already persisted for this dictation
    describe a different code path than the one that actually produced the
    output. Delete those rows and replace them with the LLM's own account of
    what it did per term, so `kivi explain` and `kivi dictate` both describe
    the same reasoning as the text on screen. Learn-phase rows (candidate/
    promotion/ambiguity) are untouched -- learning always reads the
    formatted text via the same deterministic path regardless of which
    apply mode ran."""
    store.delete_apply_decisions(conn, dictation_id)
    by_form = {m["canonical_form"]: m for m in memories}

    decisions: list[Decision] = []
    for d in llm_decisions:
        term = d.get("term", "")
        applied = bool(d.get("applied"))
        reason = d.get("reason", "")
        m = by_form.get(term)
        decision = Decision(
            token=term,
            action="applied" if applied else "abstained_llm",
            memory_id=m["id"] if m else None,
            confidence=m["confidence"] if m else None,
            replacement=term if applied else None,
            reason=reason,
        )
        decisions.append(decision)
        store.insert_decision(conn, dictation_id, memory_id=decision.memory_id,
                              token_span=decision.token, action=decision.action,
                              confidence=decision.confidence, reason=decision.reason)

    conn.commit()
    return decisions
