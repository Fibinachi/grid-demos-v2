#!/usr/bin/env python3
"""
_backfill_jewish_confidence.py — Add Jewish confidence columns & backfill scores.

Creates jewish_confidence, jewish_classification_source, jewish_updated columns
(mirroring the Muslim pattern) and backfills with tiered confidence scores.

Confidence Tiers:
  0.95 — DeepSeek AI-verified (scanned by any deepseek_* scan)
  0.85 — Explicit tradition + non-default (Reform, Conservative, Orthodox, etc.)
  0.70 — Has generic confidence_score >= 0.7 from original import
  0.50 — Has any confidence_score or tradition assigned
  0.35 — Faith='Judaism' only, no additional signals
"""
import sqlite3, time, sys
from datetime import datetime, timezone

DB = "churches.db"
SCRIPT_NAME = "backfill_jewish_confidence"
STARTED_AT = datetime.now(timezone.utc).isoformat()
CHUNK_SIZE = 500

conn = sqlite3.connect(f"E:\\grid\\{DB}", timeout=60)
c = conn.cursor()
c.execute("PRAGMA busy_timeout=30000")
c.execute("PRAGMA journal_mode=WAL")

def progress_bar(current, total, label="", width=40):
    pct = current / total if total else 0
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    print(f"\r{label} [{bar}] {current:,}/{total:,} ({pct*100:.1f}%)", end="", flush=True)

# ── Step 1: Add columns ──
print("Step 1: Adding jewish_* columns...")
for col, col_type in [
    ("jewish_confidence", "REAL"),
    ("jewish_classification_source", "TEXT"),
    ("jewish_updated", "TEXT"),
]:
    try:
        c.execute(f"ALTER TABLE churches ADD COLUMN {col} {col_type}")
        print(f"  Added {col} ({col_type})")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print(f"  {col} already exists — skipping")
        else:
            raise

conn.commit()

# ── Step 2: Identify DeepSeek-verified entries ──
print("\nStep 2: Identifying DeepSeek-verified entries...")
c.execute("""SELECT DISTINCT church_id FROM enrichment_change_log 
WHERE change_source LIKE 'deepseek%'""")
deepseek_ids = set(r[0] for r in c.fetchall())
print(f"  {len(deepseek_ids):,} unique churches touched by DeepSeek")

# Cross with Judaism
c.execute(f"""SELECT id FROM churches WHERE faith='Judaism' AND id IN 
({','.join('?' for _ in deepseek_ids)})""", list(deepseek_ids))
deepseek_jewish = set(r[0] for r in c.fetchall())
print(f"  {len(deepseek_jewish):,} are Judaism faith")

# ── Step 3: Build per-church signal map ──
print("\nStep 3: Loading all Judaism entries...")
c.execute("""SELECT id, tradition, confidence_score, landmark_type, denomination 
FROM churches WHERE faith='Judaism'""")
rows = c.fetchall()
total = len(rows)
print(f"  {total:,} entries to process")

# Tier assignment
tier_095 = []  # DeepSeek verified
tier_085 = []  # Explicit tradition
tier_070 = []  # confidence_score >= 0.7
tier_050 = []  # Any signal
tier_035 = []  # Faith only

CANONICAL_TRADITIONS = {
    'Rabbinic', 'Orthodox', 'Orthodox (Chabad)', 'Orthodox (Hasidic)',
    'Orthodox (Modern)', 'Orthodox (Yeshiva)', 'Reform', 'Conservative',
    'Reconstructionist', 'Sephardic', 'Mizrahi', 'Humanistic', 'Karaite'
}

for church_id, tradition, conf_score, lm_type, denom in rows:
    source_parts = []
    
    # Check DeepSeek (highest signal)
    if church_id in deepseek_jewish:
        tier_095.append(church_id)
        source_parts.append("deepseek_ai")
        continue
    
    # Check explicit tradition
    if tradition and tradition in CANONICAL_TRADITIONS:
        tier_085.append(church_id)
        source_parts.append(f"tradition:{tradition}")
        continue
    
    # Check confidence_score
    if conf_score is not None and conf_score >= 0.7:
        tier_070.append(church_id)
        source_parts.append(f"confidence:{conf_score}")
        continue
    
    # Any signal at all
    if conf_score is not None or (tradition and tradition not in ('Jewish', 'Judaism', 'JEWISH', 'Chabad', 'Chabad-Lubavitch', 'Chabad-Lubavitch (Orthodox)', 'Unspecified')):
        tier_050.append(church_id)
        source_parts.append("weak_signal")
        continue
    
    # Faith only
    tier_035.append(church_id)
    source_parts.append("faith_only")

print(f"\n  Tier 0.95 (DeepSeek): {len(tier_095):,}")
print(f"  Tier 0.85 (explicit tradition): {len(tier_085):,}")
print(f"  Tier 0.70 (confidence >= 0.7): {len(tier_070):,}")
print(f"  Tier 0.50 (any signal): {len(tier_050):,}")
print(f"  Tier 0.35 (faith only): {len(tier_035):,}")

# ── Step 4: Apply tiers in batches ──
print("\nStep 4: Applying confidence scores...")

def apply_tier(ids, confidence, source_label):
    if not ids:
        return 0
    total_batch = len(ids)
    applied = 0
    now = datetime.now(timezone.utc).isoformat()
    
    for i in range(0, total_batch, CHUNK_SIZE):
        chunk = ids[i:i+CHUNK_SIZE]
        placeholders = ','.join('?' for _ in chunk)
        
        c.execute(f"""UPDATE churches SET 
            jewish_confidence = ?,
            jewish_classification_source = ?,
            jewish_updated = ?
        WHERE id IN ({placeholders})""", [confidence, source_label, now] + chunk)
        
        applied += c.rowcount
        progress_bar(i + len(chunk), total_batch, f"  Tier {confidence}")
    
    print()  # newline after progress bar
    return applied

now = datetime.now(timezone.utc).isoformat()
total_applied = 0
total_applied += apply_tier(tier_095, 0.95, f"deepseek_ai_scan:{now}")
total_applied += apply_tier(tier_085, 0.85, f"explicit_tradition:{now}")
total_applied += apply_tier(tier_070, 0.70, f"confidence_score:{now}")
total_applied += apply_tier(tier_050, 0.50, f"weak_signal:{now}")
total_applied += apply_tier(tier_035, 0.35, f"faith_only:{now}")

conn.commit()

# ── Step 5: Clean up messy traditions ──
print("\nStep 5: Cleaning up non-canonical tradition values...")
TRADITION_CLEANUP = {
    'Jewish': 'Rabbinic',
    'Judaism': 'Rabbinic',
    'JEWISH': 'Rabbinic',
    'Chabad': 'Orthodox (Chabad)',
    'Chabad-Lubavitch': 'Orthodox (Chabad)',
    'Chabad-Lubavitch (Orthodox)': 'Orthodox (Chabad)',
}

for old_val, new_val in TRADITION_CLEANUP.items():
    c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND tradition=?", (old_val,))
    count = c.fetchone()[0]
    if count > 0:
        c.execute("UPDATE churches SET tradition=? WHERE faith='Judaism' AND tradition=?", (new_val, old_val))
        print(f"  {old_val} → {new_val}: {count:,}")

conn.commit()

# ── Step 6: Log provenance ──
print("\nStep 6: Logging provenance...")
c.execute("""INSERT INTO provenance_log (script_name, started_at, completed_at, notes) 
VALUES (?, ?, ?, ?)""", (
    SCRIPT_NAME, STARTED_AT, datetime.now(timezone.utc).isoformat(),
    f"Backfilled jewish_confidence for {total_applied:,} entries. "
    f"Tiers: 0.95={len(tier_095)}, 0.85={len(tier_085)}, 0.70={len(tier_070)}, 0.50={len(tier_050)}, 0.35={len(tier_035)}. "
    f"Cleaned up {sum(1 for v in TRADITION_CLEANUP.values())} non-canonical tradition values."
))
conn.commit()

# ── Step 7: Summary ──
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND jewish_confidence IS NOT NULL")
final = c.fetchone()[0]
print(f"  Jewish confidence coverage: {final:,} / {total:,} ({final/total*100:.1f}%)")

c.execute("""SELECT jewish_confidence, COUNT(*) FROM churches 
WHERE faith='Judaism' AND jewish_confidence IS NOT NULL 
GROUP BY jewish_confidence ORDER BY jewish_confidence DESC""")
print("\n  Confidence distribution:")
for row in c.fetchall():
    print(f"    {row[0]:.2f}: {row[1]:,}")

c.execute("""SELECT tradition, COUNT(*) FROM churches 
WHERE faith='Judaism' GROUP BY tradition ORDER BY COUNT(*) DESC LIMIT 15""")
print("\n  Tradition distribution (post-cleanup):")
for row in c.fetchall():
    print(f"    {row[0]}: {row[1]:,}")

conn.close()
print("\nDone.")
