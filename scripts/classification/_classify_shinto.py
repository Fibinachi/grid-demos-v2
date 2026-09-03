"""
_classify_shinto.py — Classify Shinto shrines and Japanese religious sites.

Targets: OSM osm_import entries with null faith, focusing on Japan.
Uses landmark_type + name patterns + country inference.

Pattern priority:
  Tier 1 — shrine in Japan → Shinto (landmark + country)
  Tier 2 — Japanese shrine keywords (神社, 神宮, 大社, jinja, jingu, etc.)
  Tier 3 — Japanese temple keywords (寺,  temple, -ji) → Buddhist (traded off)
"""
import sqlite3, time

DB = 'churches.db'
conn = sqlite3.connect(DB, timeout=60)
c = conn.cursor()
start = None

def log(label, count):
    if count:
        print(f"  {label}: {count:,}")

def remaining():
    c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith=''")
    return c.fetchone()[0]

# ═══════════════════════════════════════════════════════════════
print("=" * 60)
print("SHINTO CLASSIFIER")
print("=" * 60)
start_remain = remaining()
print(f"Starting null faith: {start_remain:,}\n")

# ── Tier 1: Shrine in Japan → Shinto ─────────────────────────
print("--- Tier 1: Shrine in Japan → Shinto ---")
c.execute("""
    UPDATE churches SET faith='Shinto'
    WHERE (faith IS NULL OR faith='')
      AND country='JP'
      AND landmark_type='shrine'
""")
log("JP shrine", c.rowcount)
conn.commit()

# ── Tier 2: Japanese shrine name patterns → Shinto ────────────
print("\n--- Tier 2: Japanese shrine name patterns → Shinto ---")
patterns = [
    ("神社 (jinja/shrine kanji)", "name LIKE '%神社%'"),
    ("神宮 (jingu/shrine kanji)", "name LIKE '%神宮%'"),
    ("大社 (taisha/grand shrine)", "name LIKE '%大社%'"),
    ("jinja/jingu/shrine romaji", "LOWER(name) LIKE '%jinja%' OR LOWER(name) LIKE '%jingu%' OR LOWER(name) LIKE '%taisha%' OR LOWER(name) LIKE '%shrines%'"),
    ("shinto keyword", "LOWER(name) LIKE '%shinto%'"),
]
for label, cond in patterns:
    c.execute(f"UPDATE churches SET faith='Shinto' WHERE (faith IS NULL OR faith='') AND country='JP' AND ({cond})")
    log(label, c.rowcount)
conn.commit()

# ── Tier 3: Other Shinto-associated terms ─────────────────────
print("\n--- Tier 3: Other Shinto-associated terms ---")
c.execute("""
    UPDATE churches SET faith='Shinto'
    WHERE (faith IS NULL OR faith='')
      AND country='JP'
      AND (LOWER(name) LIKE '%kami%'
        OR LOWER(name) LIKE '%mikoshi%'
        OR LOWER(name) LIKE '%matsuri%'
        OR LOWER(name) LIKE '%torii%'
        OR LOWER(name) LIKE '%fengxian%'
        OR LOWER(name) LIKE '%engi%'
        OR LOWER(name) LIKE '%sakura%'
        OR LOWER(name) LIKE '%chigi%'
        OR LOWER(name) LIKE '%haiden%'
        OR LOWER(name) LIKE '%honden%'
        OR LOWER(name) LIKE '%norito%')
""")
log("Shinto-associated terms", c.rowcount)
conn.commit()

# ── Tier 4: Remaining shrine entries in Japan → Shinto ────────
print("\n--- Tier 4: Remaining shrine landmarks in JP → Shinto ---")
c.execute("""
    UPDATE churches SET faith='Shinto'
    WHERE (faith IS NULL OR faith='')
      AND country='JP'
      AND landmark_type IN ('shrine', 'wayside_shrine', 'pagoda')
""")
log("JP shrine/wayside/pagoda", c.rowcount)
conn.commit()

# ── Summary ───────────────────────────────────────────────────
final_remain = remaining()
classified = start_remain - final_remain
print(f"\n{'=' * 60}")
print(f"Total classified as Shinto: {classified:,}")
print(f"Remaining null faith: {final_remain:,}")

# Provenance
c.execute("""
    INSERT INTO provenance_log (script_name, churches_updated, churches_inserted, notes, completed_at, status, fields_populated)
    VALUES ('_classify_shinto', ?, 0, ?, datetime('now'), 'completed', 'faith')
""", (classified, f"Classified {classified} Shinto entries from JP OSM data"))
conn.commit()
conn.close()
print("Done!")
