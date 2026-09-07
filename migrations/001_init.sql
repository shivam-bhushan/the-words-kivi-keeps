-- Kivi phonetic memory: initial schema.
-- Applied in order by src/kivi/db.py:init_db(). Filenames sort lexically -> execution order.

CREATE TABLE IF NOT EXISTS dictations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'default',
    raw_asr TEXT NOT NULL,
    formatted_text TEXT NOT NULL,
    memory_aware_text TEXT,
    is_explicit_correction INTEGER NOT NULL DEFAULT 0,
    correction_wrong TEXT,
    correction_right TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS memory_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'default',
    canonical_form TEXT NOT NULL,
    phonetic_key TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'unknown',
    status TEXT NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate', 'active', 'ambiguous', 'retired')),
    confidence REAL NOT NULL DEFAULT 0.2,
    evidence_count INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_memory_entries_phonetic ON memory_entries(user_id, phonetic_key);

CREATE TABLE IF NOT EXISTS memory_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id INTEGER NOT NULL REFERENCES memory_entries(id) ON DELETE CASCADE,
    surface_form TEXT NOT NULL,
    source_dictation_id INTEGER REFERENCES dictations(id) ON DELETE SET NULL,
    signal_type TEXT NOT NULL CHECK (signal_type IN ('explicit_correction', 'repetition')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_memory_variants_memory ON memory_variants(memory_id);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dictation_id INTEGER NOT NULL REFERENCES dictations(id) ON DELETE CASCADE,
    memory_id INTEGER REFERENCES memory_entries(id) ON DELETE SET NULL,
    token_span TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN (
        'applied', 'abstained_low_confidence', 'abstained_ambiguous',
        'abstained_no_match', 'abstained_common_word', 'learned_candidate',
        'learned_promoted', 'learned_correction', 'learned_ambiguous'
    )),
    confidence_at_decision REAL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_decisions_dictation ON decisions(dictation_id);
