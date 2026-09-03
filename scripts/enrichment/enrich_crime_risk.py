"""
enrich_crime_risk.py — Add FBI crime rate columns to church_enrichment
======================================================================
Joins US churches to fbi_srs_state by state_abbr for the latest available
year, then writes violent_crime_rate, property_crime_rate, homicide_rate,
and composite crime_risk_score to church_enrichment.

Usage:
    python scripts/enrichment/enrich_crime_risk.py
    python scripts/enrichment/enrich_crime_risk.py --dry-run
"""

import sqlite3, sys, time
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT / "churches.db"

CHUNK_SIZE = 500
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

# ── Progress bar ──────────────────────────────────────────────────
def progress_bar(current, total, label='', width=40):
    if total == 0:
        return
    pct = current / total
    filled = int(width * pct)
    bar = chr(0x2588) * filled + chr(0x2591) * (width - filled)
    sys.stderr.write(f'\r{label} [{bar}] {current:,}/{total:,} ({pct*100:.1f}%)')
    sys.stderr.flush()
    if current >= total:
        sys.stderr.write('\n')

# ══════════════════════════════════════════════════════════════════

def main(dry_run=False):
    db = sqlite3.connect(str(DB_PATH), timeout=120)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=OFF")

    t0 = time.time()

    # ── Step 1: Load state-level crime data for latest year ──
    print("=== FBI CRIME RISK ENRICHMENT ===\n")

    # Find the latest year with full state coverage (most states stop at 2021)
    latest_year = db.execute("""
        SELECT year, COUNT(DISTINCT state_abbr) as n
        FROM fbi_srs_state
        WHERE state_abbr != ''
        GROUP BY year
        HAVING n >= 50
        ORDER BY year DESC
        LIMIT 1
    """).fetchone()
    year = latest_year['year']
    n_states = latest_year['n']
    print(f"Crime data year: {year} ({n_states} states)")

    # Build in-memory state → crime rates dict
    crime_by_state = {}
    for row in db.execute("""
        SELECT state_abbr, population,
               violent_crime, property_crime, homicide,
               robbery, burglary, larceny, motor_vehicle_theft
        FROM fbi_srs_state
        WHERE year = ? AND state_abbr != ''
    """, [year]):
        pop = max(row['population'], 1)
        crime_by_state[row['state_abbr']] = {
            'violent_rate': round(row['violent_crime'] * 100000.0 / pop, 2),
            'property_rate': round(row['property_crime'] * 100000.0 / pop, 2),
            'homicide_rate': round(row['homicide'] * 100000.0 / pop, 2),
            'robbery_rate': round(row['robbery'] * 100000.0 / pop, 2),
            'burglary_rate': round(row['burglary'] * 100000.0 / pop, 2),
            'larceny_rate': round(row['larceny'] * 100000.0 / pop, 2),
            'mv_theft_rate': round(row['motor_vehicle_theft'] * 100000.0 / pop, 2),
            'population': pop,
        }
    print(f"Loaded {len(crime_by_state)} states with crime rates\n")

    # ── Step 2: Compute national percentile ranks ──
    # (for composite crime_risk_score)
    vrates = sorted([s['violent_rate'] for s in crime_by_state.values()])
    prates = sorted([s['property_rate'] for s in crime_by_state.values()])

    def percentile(val, sorted_list):
        if not sorted_list:
            return 0.5
        rank = sum(1 for x in sorted_list if x <= val)
        return round(rank / len(sorted_list), 4)

    for abbr, s in crime_by_state.items():
        vpct = percentile(s['violent_rate'], vrates)
        ppct = percentile(s['property_rate'], prates)
        # Composite: 0-100, weighted 50% violent + 50% property
        s['crime_risk_score'] = round((vpct + ppct) * 50, 1)

    # ── Step 3: Add columns to church_enrichment if needed ──
    enrich_cols = [
        ('crime_violent_rate', 'REAL'),
        ('crime_property_rate', 'REAL'),
        ('crime_homicide_rate', 'REAL'),
        ('crime_robbery_rate', 'REAL'),
        ('crime_burglary_rate', 'REAL'),
        ('crime_larceny_rate', 'REAL'),
        ('crime_mv_theft_rate', 'REAL'),
        ('crime_risk_score', 'REAL'),
        ('crime_data_year', 'INTEGER'),
        ('crime_population', 'INTEGER'),
        ('crime_enriched_at', 'TEXT'),
    ]

    existing_cols = {r[1] for r in db.execute("PRAGMA table_info(church_enrichment)")}
    for col_name, col_type in enrich_cols:
        if col_name not in existing_cols:
            print(f"  + Adding column church_enrichment.{col_name} ({col_type})")
            if not dry_run:
                db.execute(f"ALTER TABLE church_enrichment ADD COLUMN {col_name} {col_type}")

    db.commit()

    # ── Step 4: Query US churches to enrich ──
    print("\nQuerying US churches...")
    churches = db.execute("""
        SELECT c.id, c.state
        FROM churches c
        WHERE c.country = 'US'
          AND c.state IS NOT NULL
    """).fetchall()

    total = len(churches)
    print(f"  {total:,} US churches to enrich")

    # ── Step 5: Ensure enrichment rows exist ──
    print("\nEnsuring church_enrichment rows exist...")
    existing_ids = {r[0] for r in db.execute("SELECT church_id FROM church_enrichment")}
    missing = [(c['id'],) for c in churches if c['id'] not in existing_ids]
    if missing:
        print(f"  Creating {len(missing):,} enrichment rows...")
        if not dry_run:
            for i in range(0, len(missing), CHUNK_SIZE):
                batch = missing[i:i + CHUNK_SIZE]
                db.executemany(
                    "INSERT OR IGNORE INTO church_enrichment (church_id) VALUES (?)",
                    batch
                )
                db.commit()
                progress_bar(i + len(batch), len(missing), '  Creating enrichment rows')
    else:
        print(f"  All {total:,} churches already have enrichment rows")

    # ── Step 6: Batch-update crime data ──
    print(f"\nUpdating crime rates (year={year}, {len(crime_by_state)} states)...")
    updated = 0
    skipped = 0
    no_data = 0
    batch_updates = []

    for c in churches:
        church_id = c['id']
        state = c['state']
        crime = crime_by_state.get(state)
        if not crime:
            no_data += 1
            skipped += 1
            continue

        batch_updates.append((
            crime['violent_rate'], crime['property_rate'], crime['homicide_rate'],
            crime['robbery_rate'], crime['burglary_rate'], crime['larceny_rate'],
            crime['mv_theft_rate'], crime['crime_risk_score'],
            year, crime['population'], NOW,
            church_id,
        ))

        if len(batch_updates) >= CHUNK_SIZE:
            if not dry_run:
                db.executemany("""
                    UPDATE church_enrichment SET
                        crime_violent_rate = ?,
                        crime_property_rate = ?,
                        crime_homicide_rate = ?,
                        crime_robbery_rate = ?,
                        crime_burglary_rate = ?,
                        crime_larceny_rate = ?,
                        crime_mv_theft_rate = ?,
                        crime_risk_score = ?,
                        crime_data_year = ?,
                        crime_population = ?,
                        crime_enriched_at = ?
                    WHERE church_id = ?
                """, batch_updates)
                db.commit()
            updated += len(batch_updates)
            batch_updates = []
            progress_bar(updated + skipped, total,
                        f'  {updated:,} updated, {skipped:,} skipped')

    # Final batch
    if batch_updates:
        if not dry_run:
            db.executemany("""
                UPDATE church_enrichment SET
                    crime_violent_rate = ?,
                    crime_property_rate = ?,
                    crime_homicide_rate = ?,
                    crime_robbery_rate = ?,
                    crime_burglary_rate = ?,
                    crime_larceny_rate = ?,
                    crime_mv_theft_rate = ?,
                    crime_risk_score = ?,
                    crime_data_year = ?,
                    crime_population = ?,
                    crime_enriched_at = ?
                WHERE church_id = ?
            """, batch_updates)
            db.commit()
        updated += len(batch_updates)

    progress_bar(updated + skipped, total,
                f'  {updated:,} updated, {skipped:,} skipped')

    # ── Step 7: Verify ──
    elapsed = time.time() - t0
    print(f"\n\n=== ENRICHMENT COMPLETE ({elapsed:.1f}s) ===\n")

    verify = db.execute("""
        SELECT COUNT(*) as n,
               COUNT(crime_violent_rate) as with_violent,
               COUNT(crime_property_rate) as with_property,
               COUNT(crime_risk_score) as with_risk,
               ROUND(AVG(crime_risk_score), 1) as avg_risk,
               ROUND(MAX(crime_risk_score), 1) as max_risk,
               ROUND(MIN(crime_risk_score), 1) as min_risk
        FROM church_enrichment
        WHERE crime_enriched_at IS NOT NULL
    """).fetchone()

    print(f"  Enriched: {verify['n']:,} churches")
    print(f"  With violent rate: {verify['with_violent']:,}")
    print(f"  With property rate: {verify['with_property']:,}")
    print(f"  With risk score: {verify['with_risk']:,}")
    print(f"  Risk score range: {verify['min_risk']} - {verify['max_risk']} (avg {verify['avg_risk']})")
    print(f"  States with no data: {no_data}")

    # Show top/worst states
    print(f"\n  Top 10 highest crime risk states:")
    for row in db.execute("""
        SELECT c.state, ROUND(AVG(ce.crime_risk_score), 1) as avg_risk,
               ROUND(AVG(ce.crime_violent_rate), 1) as avg_v,
               ROUND(AVG(ce.crime_property_rate), 1) as avg_p,
               COUNT(*) as n
        FROM church_enrichment ce
        JOIN churches c ON c.id = ce.church_id
        WHERE ce.crime_risk_score IS NOT NULL
        GROUP BY c.state
        ORDER BY avg_risk DESC
        LIMIT 10
    """):
        print(f"    {row['state']:4s}: risk {row['avg_risk']:5.1f} | "
              f"violent {row['avg_v']:6.1f}/100K | property {row['avg_p']:7.1f}/100K | "
              f"{row['n']:,} churches")

    print(f"\n  Top 10 lowest crime risk states:")
    for row in db.execute("""
        SELECT c.state, ROUND(AVG(ce.crime_risk_score), 1) as avg_risk,
               ROUND(AVG(ce.crime_violent_rate), 1) as avg_v,
               ROUND(AVG(ce.crime_property_rate), 1) as avg_p,
               COUNT(*) as n
        FROM church_enrichment ce
        JOIN churches c ON c.id = ce.church_id
        WHERE ce.crime_risk_score IS NOT NULL
        GROUP BY c.state
        ORDER BY avg_risk ASC
        LIMIT 10
    """):
        print(f"    {row['state']:4s}: risk {row['avg_risk']:5.1f} | "
              f"violent {row['avg_v']:6.1f}/100K | property {row['avg_p']:7.1f}/100K | "
              f"{row['n']:,} churches")

    if dry_run:
        print(f"\n⚠️ DRY RUN — no changes written. Remove --dry-run to commit.")

    db.close()

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    main(dry_run=dry_run)
