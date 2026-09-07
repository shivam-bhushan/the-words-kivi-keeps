-- LLM-inferred category evidence, kept separate from memory_entries.category.
-- An inference is not observed evidence the way repetition/correction is for
-- spelling, so it earns trust the same way: repeated, consistent signals (or
-- an explicit statement) before it's allowed to set the trusted column.

CREATE TABLE IF NOT EXISTS memory_category_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id INTEGER NOT NULL REFERENCES memory_entries(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('llm_inferred', 'explicit')),
    source_dictation_id INTEGER REFERENCES dictations(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_category_signals_memory ON memory_category_signals(memory_id);
