"""Memory injection into the formatting prompt.

The default pipeline applies corrections deterministically (span replacement)
so decisions are exact, explainable, and free. This module covers the other
half of the story: in the real Kivi app, corrections happen inside the LLM
formatting pass, so retrieved memories must be rendered into that prompt.
`render_memory_context` builds that block; `apply_with_llm` runs it (used by
`kivi dictate --llm` when ANTHROPIC_API_KEY is set).
"""
from kivi.config import ANTHROPIC_API_KEY, APPLY_CONFIDENCE_THRESHOLD, LLM_MODEL
from kivi.phonetics import is_common_english_word, is_phonetic_match, tokenize


def relevant_memories(text: str, memories) -> list:
    """Only memories whose cluster is actually touched by this text are
    injected -- the prompt must not grow with the size of the whole memory."""
    tokens = tokenize(text)
    return [m for m in memories
            if m["status"] == "active" and m["confidence"] >= APPLY_CONFIDENCE_THRESHOLD
            and any(is_phonetic_match(t, m["canonical_form"]) for t in tokens)]


def render_memory_context(memories) -> str:
    if not memories:
        return ""
    lines = []
    for m in memories:
        line = f"- \"{m['canonical_form']}\" (confidence {m['confidence']:.2f})"
        if is_common_english_word(m["canonical_form"]):
            line += (" -- CAUTION: this also spells an ordinary English word with an "
                     "unrelated meaning. Only substitute it when the sentence's meaning "
                     "clearly points to the personal term; if the sentence reads naturally "
                     "as the ordinary word, leave it as the ordinary word.")
        lines.append(line)
    return (
        "This user's personal vocabulary (learned from their usage):\n"
        + "\n".join(lines)
        + "\n\nIf a word in the text sounds like one of these personal terms, spell it "
        "the user's way -- but judge each case from the sentence's actual meaning, not "
        "sound alone, especially where a caution is noted above. Only substitute words "
        "that sound alike; never change meaning, add words, or alter anything else."
    )


# Forced tool call instead of asking for "JSON" in prose: the API guarantees
# the response matches this schema, so there is no free-text parsing to get
# wrong. Categories are still just the model's inference from context, not
# observed evidence -- see pipeline.record_category_signals for how little
# trust a single guess gets.
EMIT_RESULT_TOOL = {
    "name": "emit_memory_aware_text",
    "description": (
        "Return the corrected dictation text. Also report, for each personal "
        "vocabulary term above that you substituted or deliberately left alone, "
        "what kind of thing it refers to -- key the map by the exact canonical "
        "spelling shown in the vocabulary list, not the word as it appeared in "
        "the input text."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "output": {"type": "string", "description": "The corrected text."},
            "categories": {
                "type": "object",
                "description": "canonical form (from the vocabulary list) -> category",
                "additionalProperties": {
                    "type": "string",
                    "enum": ["person", "product", "place", "other"],
                },
            },
        },
        "required": ["output", "categories"],
    },
}


def apply_with_llm(formatted_text: str, memories) -> tuple[str, dict[str, str]]:
    """Re-run the formatting step with the personal-vocabulary block injected.

    Returns (corrected_text, categories). `categories` maps a canonical form
    to the LLM's guess at what kind of thing it is -- an inference, not
    observed evidence. Callers must not write it into memory_entries.category
    directly; route it through pipeline.record_category_signals so it earns
    trust the same way spelling evidence does.
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set; use the default deterministic mode.")
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    context = render_memory_context(memories)
    valid_forms = {m["canonical_form"] for m in memories}

    response = client.messages.create(
        model=LLM_MODEL,
        max_tokens=1024,
        system="You are the final pass of a dictation formatter. " + context,
        messages=[{"role": "user", "content": formatted_text}],
        tools=[EMIT_RESULT_TOOL],
        tool_choice={"type": "tool", "name": "emit_memory_aware_text"},
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "emit_memory_aware_text":
            data = block.input
            output = data.get("output", formatted_text).strip()
            raw_categories = data.get("categories") or {}
            # The schema constrains each value to the enum, but not the key --
            # drop anything the model tagged that isn't a term we actually
            # asked about, rather than trusting an invented key.
            categories = {k: v for k, v in raw_categories.items() if k in valid_forms}
            return output, categories
    raise RuntimeError(f"no tool_use block in LLM response: {response.content!r}")
