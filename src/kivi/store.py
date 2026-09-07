"""Thin DB row helpers shared by the learning/apply pipeline and the CLI.

All functions take an open connection; callers own commit/rollback so a whole
dictation is processed in one transaction.
"""
import sqlite3

from kivi import phonetics


def insert_dictation(
    conn: sqlite3.Connection,
    raw_asr: str,
    formatted_text: str,
    *,
    user_id: str = "default",
    is_explicit_correction: bool = False,
    correction_wrong: str | None = None,
    correction_right: str | None = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO dictations
           (user_id, raw_asr, formatted_text, is_explicit_correction,
            correction_wrong, correction_right)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, raw_asr, formatted_text, int(is_explicit_correction),
         correction_wrong, correction_right),
    )
    return cur.lastrowid


def set_memory_aware_text(conn: sqlite3.Connection, dictation_id: int, text: str) -> None:
    conn.execute(
        "UPDATE dictations SET memory_aware_text = ? WHERE id = ?", (text, dictation_id)
    )


def get_memories(conn: sqlite3.Connection, user_id: str = "default") -> list[sqlite3.Row]:
    """All non-retired memories for a user. Personal vocabularies are small
    (hundreds of entries), so phonetic matching filters in Python rather than
    relying on the exact phonetic_key index (near-miss metaphone codes would
    slip past an exact-key lookup)."""
    return conn.execute(
        """SELECT m.*,
                  (SELECT COUNT(*) FROM memory_variants v
                   WHERE v.memory_id = m.id AND v.signal_type = 'explicit_correction')
                  AS correction_count
           FROM memory_entries m
           WHERE m.user_id = ? AND m.status != 'retired'
           ORDER BY m.id""",
        (user_id,),
    ).fetchall()


def create_memory(
    conn: sqlite3.Connection,
    canonical_form: str,
    phonetic_key: str,
    *,
    user_id: str = "default",
    status: str = "candidate",
    confidence: float,
    category: str = "unknown",
) -> int:
    cur = conn.execute(
        """INSERT INTO memory_entries
           (user_id, canonical_form, phonetic_key, category, status, confidence)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, canonical_form, phonetic_key, category, status, confidence),
    )
    return cur.lastrowid


def update_memory(
    conn: sqlite3.Connection,
    memory_id: int,
    *,
    canonical_form: str | None = None,
    status: str | None = None,
    confidence: float | None = None,
    category: str | None = None,
    bump_evidence: bool = False,
) -> None:
    sets, params = ["updated_at = datetime('now')", "last_seen_at = datetime('now')"], []
    if canonical_form is not None:
        sets.append("canonical_form = ?")
        params.append(canonical_form)
        sets.append("phonetic_key = ?")
        params.append(phonetics.phonetic_key(canonical_form))
    if status is not None:
        sets.append("status = ?")
        params.append(status)
    if confidence is not None:
        sets.append("confidence = ?")
        params.append(confidence)
    if category is not None:
        sets.append("category = ?")
        params.append(category)
    if bump_evidence:
        sets.append("evidence_count = evidence_count + 1")
    params.append(memory_id)
    conn.execute(f"UPDATE memory_entries SET {', '.join(sets)} WHERE id = ?", params)


def insert_variant(
    conn: sqlite3.Connection,
    memory_id: int,
    surface_form: str,
    signal_type: str,
    source_dictation_id: int | None,
) -> None:
    conn.execute(
        """INSERT INTO memory_variants (memory_id, surface_form, signal_type, source_dictation_id)
           VALUES (?, ?, ?, ?)""",
        (memory_id, surface_form, signal_type, source_dictation_id),
    )


def insert_decision(
    conn: sqlite3.Connection,
    dictation_id: int,
    *,
    memory_id: int | None,
    token_span: str,
    action: str,
    confidence: float | None,
    reason: str,
) -> None:
    conn.execute(
        """INSERT INTO decisions
           (dictation_id, memory_id, token_span, action, confidence_at_decision, reason)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (dictation_id, memory_id, token_span, action, confidence, reason),
    )


def get_decisions(conn: sqlite3.Connection, dictation_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM decisions WHERE dictation_id = ? ORDER BY id", (dictation_id,)
    ).fetchall()


def delete_apply_decisions(conn: sqlite3.Connection, dictation_id: int) -> None:
    """Remove apply-phase decision rows (action not starting 'learned_'),
    leaving learn-phase rows untouched. Used when --llm overrides the
    deterministic apply step, so persisted decisions describe the code path
    that actually produced the output -- see pipeline.replace_apply_decisions."""
    conn.execute(
        "DELETE FROM decisions WHERE dictation_id = ? AND action NOT LIKE 'learned_%'",
        (dictation_id,),
    )


def get_variants(conn: sqlite3.Connection, memory_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM memory_variants WHERE memory_id = ? ORDER BY id", (memory_id,)
    ).fetchall()


def get_dictation(conn: sqlite3.Connection, dictation_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM dictations WHERE id = ?", (dictation_id,)
    ).fetchone()


def insert_category_signal(
    conn: sqlite3.Connection,
    memory_id: int,
    category: str,
    source: str,
    source_dictation_id: int | None,
) -> None:
    conn.execute(
        """INSERT INTO memory_category_signals
           (memory_id, category, source, source_dictation_id)
           VALUES (?, ?, ?, ?)""",
        (memory_id, category, source, source_dictation_id),
    )


def get_category_signals(conn: sqlite3.Connection, memory_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM memory_category_signals WHERE memory_id = ? ORDER BY id",
        (memory_id,),
    ).fetchall()
