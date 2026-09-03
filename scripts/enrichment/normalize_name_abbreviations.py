"""
Populate normalized_name with standardized church names.

Strategy:
  - Keep `name` as the original/legal name (source of truth)
  - Write standardized version to `normalized_name`
  - Uses TIGER/Census place names as authority for US place-based names

Normalizations applied to normalized_name:
  1. Strip leading "THE " / "THE"
  2. AME/AMEC/AMEZ → A.M.E. / A.M.E. ZION  (word-boundary)
  3. St. → SAINT  (US, unless TIGER says it's a place name)
  4. Mt./Mt → MOUNT  (US)
  5. Ft./Ft → FORT  (US)
  6. N./S./E./W. → NORTH/SOUTH/EAST/WEST  (US names, not addresses)
  7. Unicode dashes (—/–) → ASCII hyphen (-)
  8. & → AND

Usage:
    python scripts/enrichment/normalize_name_abbreviations.py
"""

import csv
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from gw_db import connect, Provenance

CHUNK_SIZE = 2000
SCRIPT_NAME = "normalize_name_abbreviations"
TIGER_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "tiger" / "2024_Gaz_place_national.txt"


# ── Load TIGER authority data ────────────────────────────────────────────

def load_tiger_bases() -> set:
    """Load TIGER place name bases (words after 'St.' in official names)."""
    bases = set()
    try:
        with open(TIGER_PATH, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                name = row.get("NAME", "").upper()
                m = re.search(r"\bST\.\s+(\w+)", name)
                if m:
                    bases.add(m.group(1).upper())
    except FileNotFoundError:
        print(f"  Warning: TIGER file not found at {TIGER_PATH}")
    return bases


# ── Normalization pipeline ───────────────────────────────────────────────

def normalize_name(name: str, tiger_bases: set) -> str:
    """Apply all normalizations to produce a standardized name."""
    if not name:
        return name

    n = name

    # 1. Strip leading "THE " (and variants)
    n = re.sub(r'^(THE|Th[Ee])\s+', '', n)

    # 2. AME / AMEC / AMEZ → A.M.E. / A.M.E. ZION
    n = re.sub(r'\bAMEZ\b', 'A.M.E. ZION', n, flags=re.IGNORECASE)
    n = re.sub(r'\bAMEC\b', 'A.M.E.', n, flags=re.IGNORECASE)
    n = re.sub(r'\bAME\s+ZION\b', 'A.M.E. ZION', n, flags=re.IGNORECASE)
    n = re.sub(r'\bAME\b', 'A.M.E.', n, flags=re.IGNORECASE)
    n = re.sub(r'\bA\s+M\s+E\b', 'A.M.E.', n, flags=re.IGNORECASE)

    # 3. St. / ST → SAINT — but keep "St." if TIGER says it's a US place name
    def st_replacer(m):
        word_after = m.group(1).upper()
        if word_after in tiger_bases:
            return m.group(0)  # keep original — it's a US place name
        return 'SAINT ' + m.group(1)

    n = re.sub(r'\b[Ss][Tt]\.\s+(\w+)', st_replacer, n)
    # St without dot (word boundary)
    n = re.sub(r'\b[Ss][Tt](?=\s+[A-Z])', 'SAINT', n)
    # Handle leading "ST " / "St "
    if n.startswith('SAINT ') and name.startswith(('ST ', 'St ')):
        pass  # already handled

    # 4. Mt. / MT → MOUNT
    n = re.sub(r'\b[Mm][Tt]\.\s*', 'MOUNT ', n)
    n = re.sub(r'\b[Mm][Tt](?=\s+[A-Z])', 'MOUNT', n)

    # 5. Ft. / FT → FORT
    n = re.sub(r'\b[Ff][Tt]\.\s*', 'FORT ', n)
    n = re.sub(r'\b[Ff][Tt](?=\s+[A-Z])', 'FORT', n)

    # 6. Directional N./S./E./W. → NORTH/SOUTH/EAST/WEST
    # Must NOT match inside A.M.E. or similar abbreviations (E. after dot)
    n = re.sub(r'(?<![A-Z.])N\.\s', 'NORTH ', n)
    n = re.sub(r'(?<![A-Z.])S\.\s', 'SOUTH ', n)
    n = re.sub(r'(?<![A-Z.])E\.\s', 'EAST ', n)
    n = re.sub(r'(?<![A-Z.])W\.\s', 'WEST ', n)

    # 7. Unicode dashes → ASCII hyphen
    n = n.replace('—', '-').replace('–', '-')

    # 8. & → AND
    n = re.sub(r'\s*&\s*', ' AND ', n)

    # Collapse multiple spaces
    n = re.sub(r'\s+', ' ', n).strip()

    return n


# ── Batch processing ─────────────────────────────────────────────────────

def process_all(db, tiger_bases):
    """Process all churches, populating normalized_name."""
    c = db.cursor()

    c.execute("SELECT COUNT(*) FROM churches")
    total = c.fetchone()[0]

    c.execute("SELECT MIN(rowid) FROM churches")
    min_rowid = c.fetchone()[0]
    c.execute("SELECT MAX(rowid) FROM churches")
    max_rowid = c.fetchone()[0]

    print(f"Total churches: {total:,}")
    print(f"Rowid range: {min_rowid} - {max_rowid}")

    processed = 0
    updated = 0
    batch = []
    start_time = time.time()

    with Provenance(db, SCRIPT_NAME, source="name_standardization",
                     action="updated", fields="normalized_name",
                     records_attempted=total) as prov:

        for offset in range(min_rowid, max_rowid + 1, CHUNK_SIZE):
            lo = offset
            hi = min(offset + CHUNK_SIZE - 1, max_rowid)

            c.execute("""
                SELECT rowid, name FROM churches
                WHERE rowid BETWEEN ? AND ?
            """, (lo, hi))

            rows = c.fetchall()
            if not rows:
                continue

            for rowid, name in rows:
                processed += 1
                normalized = normalize_name(name, tiger_bases)
                if normalized and normalized != name:
                    batch.append((normalized, rowid))
                    updated += 1
                    prov.churches_updated += 1

            if batch:
                c.executemany(
                    "UPDATE churches SET normalized_name = ? WHERE rowid = ?",
                    batch
                )
                db.commit()
                batch = []

            elapsed = time.time() - start_time
            pct = 100 * processed / total if total else 0
            rate = processed / elapsed if elapsed > 0 else 0
            print(f"  {processed:>8,}/{total:,} ({pct:5.1f}%) | {updated:,} updated | {rate:,.0f} rows/s", end="\r")

        if batch:
            c.executemany(
                "UPDATE churches SET normalized_name = ? WHERE rowid = ?",
                batch
            )
            db.commit()

    elapsed = time.time() - start_time
    print(f"\n\nDone: {updated:,} / {processed:,} records updated in {elapsed:.0f}s")


def main():
    print("Loading TIGER place name authority data...")
    tiger_bases = load_tiger_bases()
    print(f"  Loaded {len(tiger_bases)} TIGER saint-name bases")

    db = connect(timeout=120)
    db.execute("PRAGMA busy_timeout=120000")
    process_all(db, tiger_bases)


if __name__ == "__main__":
    main()

