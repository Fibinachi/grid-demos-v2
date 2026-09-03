"""Create the classification_history table for pipeline provenance."""
import sqlite3

DB = r"E:\grid\churches.db"
conn = sqlite3.connect(DB, timeout=30)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")

conn.executescript("""
    CREATE TABLE IF NOT EXISTS classification_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        church_id INTEGER NOT NULL REFERENCES churches(id),
        stage TEXT NOT NULL,
        action TEXT NOT NULL CHECK(action IN ('classified', 'kickback', 'resolved')),
        field_name TEXT,
        old_value TEXT,
        new_value TEXT,
        confidence REAL,
        reasoning TEXT,
        kickback_target TEXT CHECK(kickback_target IN ('stage1', 'stage2', 'stage3', 'stage4')),
        kickback_reason TEXT,
        batch_id TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_ch_stage ON classification_history(stage);
    CREATE INDEX IF NOT EXISTS idx_ch_church ON classification_history(church_id);
    CREATE INDEX IF NOT EXISTS idx_ch_action ON classification_history(stage, action);
    CREATE INDEX IF NOT EXISTS idx_ch_kickback ON classification_history(action, kickback_target);
""")

conn.commit()
print("classification_history table created.")
rows = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE '%ch_%'").fetchall()
print(f"Indexes: {[r[0] for r in rows]}")
conn.close()
print("Done.")
