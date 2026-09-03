"""
Update master church database schema for Phase 3 deep profiles.
Adds columns for pastor, staff, services, ministries, giving, etc.
"""

import sqlite3, os

DB_PATH = r"E:\grid\churches.db"

MIGRATIONS = [
    # Tier 1 fields
    "ALTER TABLE churches ADD COLUMN pastor_name TEXT DEFAULT ''",
    "ALTER TABLE churches ADD COLUMN staff_count INTEGER DEFAULT 0",
    "ALTER TABLE churches ADD COLUMN service_times TEXT DEFAULT ''",
    "ALTER TABLE churches ADD COLUMN languages TEXT DEFAULT ''",
    "ALTER TABLE churches ADD COLUMN livestream_link TEXT DEFAULT ''",
    "ALTER TABLE churches ADD COLUMN online_giving_link TEXT DEFAULT ''",
    "ALTER TABLE churches ADD COLUMN facebook_url TEXT DEFAULT ''",
    "ALTER TABLE churches ADD COLUMN instagram_url TEXT DEFAULT ''",
    "ALTER TABLE churches ADD COLUMN youtube_url TEXT DEFAULT ''",
    "ALTER TABLE churches ADD COLUMN statement_of_faith TEXT DEFAULT ''",
    "ALTER TABLE churches ADD COLUMN denomination_affiliation TEXT DEFAULT ''",
    "ALTER TABLE churches ADD COLUMN campus_count INTEGER DEFAULT 1",
    
    # Tier 2 fields
    "ALTER TABLE churches ADD COLUMN attendance_est INTEGER DEFAULT 0",
    "ALTER TABLE churches ADD COLUMN ministry_count INTEGER DEFAULT 0",
    "ALTER TABLE churches ADD COLUMN has_youth INTEGER DEFAULT 0",
    "ALTER TABLE churches ADD COLUMN has_children INTEGER DEFAULT 0",
    "ALTER TABLE churches ADD COLUMN has_food_pantry INTEGER DEFAULT 0",
    "ALTER TABLE churches ADD COLUMN has_preschool INTEGER DEFAULT 0",
    "ALTER TABLE churches ADD COLUMN has_daycare INTEGER DEFAULT 0",
    "ALTER TABLE churches ADD COLUMN has_seniors INTEGER DEFAULT 0",
    "ALTER TABLE churches ADD COLUMN has_esl INTEGER DEFAULT 0",
    "ALTER TABLE churches ADD COLUMN has_recovery INTEGER DEFAULT 0",
    "ALTER TABLE churches ADD COLUMN has_missions INTEGER DEFAULT 0",
    "ALTER TABLE churches ADD COLUMN has_counseling INTEGER DEFAULT 0",
    "ALTER TABLE churches ADD COLUMN has_sports INTEGER DEFAULT 0",
    "ALTER TABLE churches ADD COLUMN leadership_structure TEXT DEFAULT ''",
    
    # Tier 3 fields
    "ALTER TABLE churches ADD COLUMN is_church_plant INTEGER DEFAULT 0",
    "ALTER TABLE churches ADD COLUMN is_closed INTEGER DEFAULT 0",
    "ALTER TABLE churches ADD COLUMN doctrinal_alignment TEXT DEFAULT ''",
    "ALTER TABLE churches ADD COLUMN worship_style TEXT DEFAULT ''",
    "ALTER TABLE churches ADD COLUMN giving_platform TEXT DEFAULT ''",
    "ALTER TABLE churches ADD COLUMN has_annual_report INTEGER DEFAULT 0",
    "ALTER TABLE churches ADD COLUMN community_impact TEXT DEFAULT ''",
    "ALTER TABLE churches ADD COLUMN last_deep_scraped TEXT DEFAULT ''",
    
    # Indexes for new fields
    "CREATE INDEX IF NOT EXISTS idx_churches_pastor ON churches(pastor_name)",
    "CREATE INDEX IF NOT EXISTS idx_churches_size ON churches(attendance_est)",
    "CREATE INDEX IF NOT EXISTS idx_churches_giving ON churches(online_giving_link)",
    "CREATE INDEX IF NOT EXISTS idx_churches_youth ON churches(has_youth)",
    "CREATE INDEX IF NOT EXISTS idx_churches_closed ON churches(is_closed)",
]

def run_migrations():
    if not os.path.exists(DB_PATH):
        print(f"Database not found: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Check existing columns
    existing = {row[1] for row in cur.execute("PRAGMA table_info(churches)").fetchall()}
    print(f"Existing columns: {len(existing)}")
    
    ran = 0
    for migration in MIGRATIONS:
        if "ADD COLUMN" in migration:
            col_name = migration.split("ADD COLUMN ")[1].split(" ")[0]
            if col_name not in existing:
                try:
                    cur.execute(migration)
                    ran += 1
                    print(f"  + {col_name}")
                except Exception as e:
                    print(f"  ! {col_name}: {e}")
        else:
            # Index or other statement
            try:
                cur.execute(migration)
            except:
                pass
    
    conn.commit()
    
    # Stats
    total_cols = cur.execute("PRAGMA table_info(churches)").fetchall()
    print(f"\nTotal columns now: {len(total_cols)}")
    
    # Count records
    count = cur.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
    print(f"Total churches: {count:,}")
    
    conn.close()
    print(f"\nMigrations complete: {ran} new columns added")

if __name__ == "__main__":
    run_migrations()
