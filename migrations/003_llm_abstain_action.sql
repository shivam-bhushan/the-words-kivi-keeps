-- Widen decisions.action to allow 'abstained_llm', for LLM-mediated apply
-- decisions that don't map onto the deterministic path's specific
-- abstention reasons (ambiguous/common-word/etc are deterministic-path
-- concepts; the LLM's abstention reasoning is free text, not one of those
-- categories). SQLite can't alter a CHECK constraint in place, so this
-- recreates the table.

PRAGMA foreign_keys = OFF;

ALTER TABLE decisions RENAME TO decisions_old;

CREATE TABLE decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dictation_id INTEGER NOT NULL REFERENCES dictations(id) ON DELETE CASCADE,
    memory_id INTEGER REFERENCES memory_entries(id) ON DELETE SET NULL,
    token_span TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN (
        'applied', 'abstained_low_confidence', 'abstained_ambiguous',
        'abstained_no_match', 'abstained_common_word', 'abstained_llm',
        'learned_candidate', 'learned_promoted', 'learned_correction', 'learned_ambiguous'
    )),
    confidence_at_decision REAL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO decisions SELECT * FROM decisions_old;
DROP TABLE decisions_old;

CREATE INDEX IF NOT EXISTS idx_decisions_dictation ON decisions(dictation_id);

PRAGMA foreign_keys = ON;
