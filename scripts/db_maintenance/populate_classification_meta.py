"""
SCRIPT: populate_classification_meta.py
PURPOSE:
  Populate church_classification_meta table from:
    1. church_enrichment — zb_confidence → scrape_confidence
    2. churches.faith + faith_tradition + denomination → liturgical_tradition
    3. church_enrichment classification timestamps
  Sets classification_version = '1.0', source = 'ag_derived'

USAGE:
    python scripts/db_maintenance/populate_classification_meta.py
    python scripts/db_maintenance/populate_classification_meta.py --dry-run
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from gw_db import connect, Provenance

DB_PATH = "churches.db"

# ─── Liturgical tradition mapping ──────────────────────────────────────────
# Maps faith (+ optional faith_tradition) → broad liturgical tradition categories

TRADITION_MAP_FAITH = {
    "Christian": "Christian (General)",
    "Catholic": "Liturgical (Western)",
    "Protestant": "Christian (General)",
    "Jewish": "Jewish",
    "Islam": "Islamic",
    "Muslim": "Islamic",
    "Buddhist": "Buddhist",
    "Hindu": "Hindu",
    "Shinto": "Shinto",
    "Taoist": "Taoist",
    "Sikh": "Sikh",
    "Bahai": "Bahai",
    "Jain": "Jain",
    "Zoroastrian": "Zoroastrian",
    "Confucian": "Confucian",
    "Animist": "Animist",
    "Pagan": "Pagan",
    "Other": "Other",
}

TRADITION_MAP_TRAIT = {
    "Catholic": "Liturgical (Western)",
    "Eastern Catholic": "Liturgical (Eastern Catholic)",
    "Orthodox": "Liturgical (Eastern)",
    "Oriental Orthodox": "Liturgical (Eastern)",
    "Eastern Orthodox": "Liturgical (Eastern)",
    "Anglican": "Liturgical (Anglican)",
    "Episcopal": "Liturgical (Anglican)",
    "Lutheran": "Liturgical (Western)",
    "Methodist": "Liturgical (Wesleyan)",
    "Wesleyan": "Liturgical (Wesleyan)",
    "Presbyterian": "Reformed",
    "Reformed": "Reformed",
    "Congregational": "Reformed (Congregational)",
    "United Church of Christ": "Reformed (Congregational)",
    "Baptist": "Non-liturgical",
    "Evangelical": "Non-liturgical",
    "Nondenominational": "Non-liturgical",
    "Independent": "Non-liturgical",
    "Pentecostal": "Charismatic",
    "Assemblies of God": "Charismatic",
    "Charismatic": "Charismatic",
    "Holiness": "Holiness",
    "Adventist": "Adventist",
    "Mormon": "Mormon",
    "LDS": "Mormon",
    "Jehovah's Witness": "Jehovah's Witness",
    "Quaker": "Quaker",
    "Salvation Army": "Holiness (Military)",
    "Messianic": "Messianic Jewish",
    "Judaism": "Jewish",
    "Reform": "Jewish (Reform)",
    "Conservative Judaism": "Jewish (Conservative)",
    "Orthodox Judaism": "Jewish (Orthodox)",
    "Sephardic": "Jewish (Sephardic)",
    "Hasidic": "Jewish (Hasidic)",
    "Chabad": "Jewish (Hasidic)",
    "Sunni": "Islamic (Sunni)",
    "Shia": "Islamic (Shia)",
    "Sufi": "Islamic (Sufi)",
    "Ahmadiyya": "Islamic (Ahmadiyya)",
    "Salafi": "Islamic (Salafi)",
    "Deobandi": "Islamic (Deobandi)",
    "Ibadi": "Islamic (Ibadi)",
    "Theravada": "Buddhist (Theravada)",
    "Mahayana": "Buddhist (Mahayana)",
    "Vajrayana": "Buddhist (Vajrayana)",
    "Tibetan Buddhist": "Buddhist (Vajrayana)",
    "Zen": "Buddhist (Mahayana)",
    "Shaivism": "Hindu (Shaivism)",
    "Vaishnavism": "Hindu (Vaishnavism)",
    "Shaktism": "Hindu (Shaktism)",
    "Smarta": "Hindu (Smarta)",
    "ISKCON": "Hindu (Vaishnavism)",
    "Hellenism": "Other (Hellenic)",
    "Roman": "Other (Roman)",
    "Masonic": "Other (Masonic)",
    "Vodou": "Other (Vodou)",
    "Native American": "Other (Indigenous)",
    "Chinese Folk": "Other (Chinese Folk)",
    "Falun Gong": "Other (Chinese Folk)",
    "Sikhism": "Sikh",
    "Baháʼí": "Bahai",
    "Baha'i": "Bahai",
}

# Denomination → tradition overrides (more specific than faith_tradition)
DENOM_TRADITION_MAP = {}
# Populate from common denom patterns
_CATHOLIC_KW = ["catholic", "roman catholic"]
_ORTHO_KW = ["orthodox", "eastern orthodox", "oriental orthodox"]
_ANGLICAN_KW = ["anglican", "episcopal", "episcopalian"]
_LUTHERAN_KW = ["lutheran", "missouri synod", "elca"]
_METHODIST_KW = ["methodist", "united methodist", "ame", "ame zion", "wesleyan"]
_BAPTIST_KW = ["baptist", "southern baptist", "american baptist"]
_PENTECOSTAL_KW = ["pentecostal", "assemblies of god", "church of god"]
_PRESBYTERIAN_KW = ["presbyterian", "pca", "pcusa"]
_REFORMED_KW = ["reformed", "dutch reformed", "christian reformed"]
_EVANGELICAL_KW = ["evangelical", "evangelical free", "evangelical covenant"]


def derive_tradition(
    faith: str | None,
    faith_tradition: str | None,
    denomination: str | None,
) -> str | None:
    """Derive liturgical tradition from faith + faith_tradition + denomination."""
    # 1. Try faith_tradition map (most specific)
    if faith_tradition:
        ft = faith_tradition.strip()
        if ft in TRADITION_MAP_TRAIT:
            return TRADITION_MAP_TRAIT[ft]
        # Partial match on faith_tradition
        for key, val in TRADITION_MAP_TRAIT.items():
            if key.lower() in ft.lower() or ft.lower() in key.lower():
                return val

    # 2. Try denomination keywords
    if denomination:
        denom_lower = denomination.lower().strip()
        for kw_group, tradition in [
            (_CATHOLIC_KW, "Liturgical (Western)"),
            (_ORTHO_KW, "Liturgical (Eastern)"),
            (_ANGLICAN_KW, "Liturgical (Anglican)"),
            (_LUTHERAN_KW, "Liturgical (Western)"),
            (_METHODIST_KW, "Liturgical (Wesleyan)"),
            (_BAPTIST_KW, "Non-liturgical"),
            (_PENTECOSTAL_KW, "Charismatic"),
            (_PRESBYTERIAN_KW, "Reformed"),
            (_REFORMED_KW, "Reformed"),
            (_EVANGELICAL_KW, "Non-liturgical"),
        ]:
            if any(kw in denom_lower for kw in kw_group):
                return tradition

    # 3. Try faith map (broad)
    if faith:
        for key, val in TRADITION_MAP_FAITH.items():
            if faith.strip().lower() == key.lower():
                return val

    return None


def get_classification_timestamp(
    row: dict,
) -> str | None:
    """Get the most recent classification timestamp from enrichment fields."""
    timestamps = []
    for col in [
        "jewish_updated",
        "muslim_updated",
        "buddhist_updated",
        "hindu_updated",
        "sikh_updated",
        "jain_updated",
        "nrm_updated",
        "geocode_last_attempt",
    ]:
        val = row.get(col)
        if val:
            timestamps.append(str(val))
    if timestamps:
        return max(timestamps)
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Populate church_classification_meta from enrichment data"
    )
    parser.add_argument("--dry-run", action="store_true", help="Print counts and exit")
    args = parser.parse_args()

    db = connect(DB_PATH)
    c = db.cursor()
    start_ts = datetime.now(timezone.utc).isoformat()

    # ─── Step 1: Count existing data ────────────────────────────────────
    print("=== church_classification_meta population ===\n")

    c.execute("SELECT COUNT(*) FROM church_classification_meta")
    existing = c.fetchone()[0]
    print(f"Existing rows in church_classification_meta: {existing}")
    if existing > 0 and not args.dry_run:
        print("WARNING: Table already has data. Delete first if re-running.")

    c.execute("SELECT COUNT(*) FROM church_enrichment WHERE zb_confidence IS NOT NULL")
    with_confidence = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM churches")
    total_churches = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NOT NULL")
    with_faith = c.fetchone()[0]

    print(f"Churches with zb_confidence in enrichment: {with_confidence}")
    print(f"Churches with faith set: {with_faith:,} / {total_churches:,}")
    print()

    if args.dry_run:
        return

    # ─── Step 2: Derive liturgical_tradition for ALL churches ────────────
    print("Deriving liturgical traditions for all churches...")
    c.execute("""
        SELECT rowid, id, faith, faith_tradition, denomination
        FROM churches
        WHERE (faith IS NOT NULL OR faith_tradition IS NOT NULL)
          AND id IS NOT NULL
    """)
    rows = c.fetchall()
    tradition_updates = []
    for row in rows:
        church_rowid = row[0]
        church_id = row[1]
        faith = row[2]
        faith_tradition = row[3]
        denom = row[4]
        tradition = derive_tradition(faith, faith_tradition, denom)
        if tradition and church_id:
            tradition_updates.append((church_id, tradition))

    print(f"  {len(tradition_updates):,} churches with derivable tradition")

    # Insert tradition data in batches
    BATCH = 400  # SQLite limit: 999 vars, 2 per row = max 499
    tradition_inserted = 0
    total = len(tradition_updates)
    try:
        for i in range(0, total, BATCH):
            batch = tradition_updates[i : i + BATCH]
            db.executemany(
                """
                INSERT OR IGNORE INTO church_classification_meta
                    (church_id, liturgical_tradition, classification_version, source, created_at)
                VALUES (?, ?, '1.0', 'ag_derived', datetime('now'))
                """,
                batch,
            )
            tradition_inserted += len(batch)
            if tradition_inserted % 100000 == 0:
                print(f"    Progress: {tradition_inserted:,}/{total:,}")
            if i > 0 and i % 20000 == 0:
                db.commit()
        db.commit()
    except Exception:
        db.rollback()
        raise
    print(f"  Inserted {tradition_inserted:,} tradition rows\n")

    # ─── Step 3: Update scrape_confidence from enrichment ────────────────
    print("Updating scrape_confidence from enrichment...")
    c.execute("""
        SELECT e.church_id, e.zb_confidence,
               e.jewish_updated, e.muslim_updated,
               e.buddhist_updated, e.hindu_updated,
               e.sikh_updated, e.jain_updated,
               e.nrm_updated, e.geocode_last_attempt
        FROM church_enrichment e
        WHERE e.zb_confidence IS NOT NULL AND e.church_id IS NOT NULL
    """)
    enrich_rows = c.fetchall()
    print(f"  {len(enrich_rows)} enrichment rows with zb_confidence")

    updated = 0
    skipped_no_church = 0
    for row in enrich_rows:
        church_id = row[0]
        if church_id is None:
            skipped_no_church += 1
            continue
        scrape_conf = row[1]

        # Get latest timestamp
        timestamps = [str(v) for v in row[2:] if v is not None]
        class_ts = max(timestamps) if timestamps else start_ts

        # Check if church already has a row in meta
        c.execute(
            "SELECT id FROM church_classification_meta WHERE church_id = ?",
            (church_id,),
        )
        existing_row = c.fetchone()
        if existing_row:
            db.execute(
                """
                UPDATE church_classification_meta
                SET scrape_confidence = ?,
                    classification_timestamp = ?,
                    source = COALESCE(source, 'enrichment_import')
                WHERE church_id = ?
                """,
                (scrape_conf, class_ts, church_id),
            )
        else:
            db.execute(
                """
                INSERT INTO church_classification_meta
                    (church_id, scrape_confidence, classification_timestamp,
                     classification_version, source, created_at)
                VALUES (?, ?, ?, '1.0', 'enrichment_import', ?)
                """,
                (church_id, scrape_conf, class_ts, start_ts),
            )
        updated += 1

    db.commit()
    print(f"  Updated {updated} rows, {skipped_no_church} skipped (NULL church_id)\n")

    # ─── Step 4: Summary ─────────────────────────────────────────────────
    c.execute("SELECT COUNT(*) FROM church_classification_meta")
    final_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM church_classification_meta WHERE scrape_confidence IS NOT NULL")
    with_scrape = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM church_classification_meta WHERE liturgical_tradition IS NOT NULL")
    with_tradition = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM church_classification_meta WHERE classification_version IS NOT NULL")
    with_version = c.fetchone()[0]

    print("=== Summary ===")
    print(f"  Total rows: {final_count:,}")
    print(f"  With scrape_confidence: {with_scrape:,}")
    print(f"  With liturgical_tradition: {with_tradition:,}")
    print(f"  With classification_version: {with_version:,}")

    # ─── Provenance ──────────────────────────────────────────────────────
    with Provenance(
        conn=db,
        source="ag_derived",
        script_name="populate_classification_meta.py",
        details=f"Populated church_classification_meta: {tradition_inserted} traditions, {updated} confidence scores",
    ) as p:
        p.records_updated = max(tradition_inserted, updated)
        p.fields_populated = "liturgical_tradition,scrape_confidence,classification_version,classification_timestamp"
        p.notes = f"Traditions derived from faith+faith_tradition+denom. Confidence from zb_confidence."

    print("\nDone.")


if __name__ == "__main__":
    main()
