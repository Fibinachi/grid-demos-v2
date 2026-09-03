#!/usr/bin/env python3
"""
Import the 2021 Catholic Directory into catholic_directory.db.

Reads pre-parsed JSON files from data/directories/2021/ and inserts every
entity (parish, cathedral, school, friary, convent, hospital, cemetery,
shrine, seminary, chancery, etc.) with all clergy assignments and bishops.

Usage:
    python scripts/ingest/_import_catholic_dir_2021.py           # Import all
    python scripts/ingest/_import_catholic_dir_2021.py --dry-run # Preview only
"""

import json
import sqlite3
import re
import sys
from pathlib import Path
from datetime import datetime

# ── Paths ──
DB_PATH = Path("E:/grid/data/catholic_directory.db")
DATA_DIR = Path("E:/grid/data/directories/2021")
ENTRIES_FILE = DATA_DIR / "all_parishes_2021.json"
BISHOPS_FILE = DATA_DIR / "bishops_2021.json"
CONTACTS_FILE = DATA_DIR / "contacts_2021.json"
DIR_YEAR = 2021
CHUNK_SIZE = 500


# ── Entity type classifier ──
def classify_entity_type(name, clergy_roles):
    """
    Classify an entry as parish, cathedral, school, etc. based on name
    and clergy role patterns.
    """
    n = (name or "").lower()
    roles_lower = " ".join(r.lower() for r in clergy_roles) if clergy_roles else ""

    # Cathedral
    if "cathedral" in n or "co-cathedral" in n or "pro-cathedral" in n:
        return "cathedral"

    # Basilica (usually also a parish, but mark as basilica)
    if "basilica" in n:
        return "basilica"

    # Shrine
    if "shrine" in n or "national shrine" in n:
        return "shrine"

    # Schools / education
    school_patterns = [
        "school", "academy", "high school", "elementary", "middle school",
        "grade school", "preparatory", "prep school", "regional school",
        "catholic school", "central school", "junior high", "primary school",
        "montessori", "grammar school", "day school", "kindergarten",
        "nursery school", "preschool", "child development", "head start",
        "learning center", "education center", "catholic education",
        "religious education", "ccd", "faith formation",
    ]
    for pat in school_patterns:
        if pat in n:
            return "school"

    # Universities / Colleges / Seminaries
    if any(w in n for w in ["university", "college", "seminary", "theological", "divinity school", "school of theology"]):
        if "seminary" in n or "theological" in n or "divinity" in n:
            return "seminary"
        return "college"

    # Cemeteries
    if any(w in n for w in ["cemetery", "cemetaries", "mausoleum", "calvary cemetery", "holy cross cemetery", "holy sepulchre", "gate of heaven"]):
        return "cemetery"

    # Hospitals / Healthcare
    if any(w in n for w in ["hospital", "medical center", "health center", "health care", "healthcare", "infirmary", "hospice", "nursing home", "rehabilitation"]):
        return "hospital"

    # Homes / Residential
    if any(w in n for w in ["home for", "residence", "friary", "monastery", "abbey", "priory", "motherhouse", "convent", "rectory", "presbytery"]):
        if "friary" in n:
            return "friary"
        if "monastery" in n or "abbey" in n or "priory" in n:
            return "monastery"
        if "convent" in n or "motherhouse" in n:
            return "convent"
        return "residence"

    # Orphanages / child services
    if any(w in n for w in ["orphanage", "children's home", "foundling", "boy's home", "girl's home", "youth center", "youth ministry", "foster care"]):
        return "orphanage"

    # Charities / social services
    if any(w in n for w in ["catholic charities", "catholic social services", "catholic community services", "catholic relief", "st. vincent de paul", "society of st. vincent"]):
        return "charity"

    # Retreat centers / camps
    if any(w in n for w in ["retreat", "spiritual center", "spirituality center", "renewal center", "prayer center", "camp"]):
        return "retreat_center"

    # Chancery / administrative
    if any(w in n for w in ["chancery", "diocesan office", "pastoral center", "catholic center", "catholic conference", "archdiocesan", "diocesan administration"]):
        return "chancery"

    # Chapel
    if "chapel" in n:
        return "chapel"

    # Mission
    if "mission" in n and "missionary" not in n:
        return "mission"

    # Oratory
    if "oratory" in n:
        return "oratory"

    # Deanery
    if "deanery" in n:
        return "deanery"

    # Religious orders / provincial houses
    if any(w in n for w in ["provincial house", "provincialate", "generalate", "curia", "motherhouse"]):
        return "religious_house"

    # Shrine markers
    if "grotto" in n:
        return "shrine"

    # Look for parish indicators: clergy roles
    parish_roles = {"pastor", "parochial_vicar", "parochial vicar", "administrator",
                    "deacon", "parish deacon", "rector"}
    if any(r.lower() in parish_roles for r in clergy_roles):
        return "parish"

    # Name contains "church" or "parish" → likely parish
    if "church" in n or "parish" in n:
        return "parish"

    # Name contains Catholic saints or standard parish naming
    saint_pattern = r'\bst\.?\s+(mary|joseph|patrick|john|peter|paul|michael|anthony|therese|francis|elizabeth|ann[e]?|james|thomas|augustine|monica|teresa|cecilia|agnes|rose|bernard|charles|lawrence|stephen|vincent|dominic|catherine|rita|philip|andrew|matthew|mark|luke|ignatius|joan|margaret|clare|benedict|martin|louis|edward|gregory|jerome|bonaventure|brigid|bridget|helena|veronica|gabriel|raphael|sebastian|george|nicholas|lucy|gertrude)\b'
    if re.search(saint_pattern, n):
        return "parish"

    # Our Lady / Blessed / Holy etc.
    if re.search(r'\b(our lady|blessed|holy|sacred heart|immaculate|holy family|divine|precious blood|christ the king|good shepherd|holy spirit|holy cross|holy name|holy rosary|holy trinity|most holy|most precious|queen of|mary queen)\b', n):
        return "parish"

    # Fallback
    return "other"


def progress_bar(current, total, width=50):
    """Simple progress bar."""
    pct = current / total if total > 0 else 1
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    return f"│{bar}│ {pct*100:5.1f}% ({current:,}/{total:,})"


def import_2021(dry_run=False):
    """Import all 2021 Catholic directory data."""

    # ── Check inputs ──
    if not ENTRIES_FILE.exists():
        print(f"❌ Missing: {ENTRIES_FILE}")
        return
    if not BISHOPS_FILE.exists():
        print(f"⚠️  Missing: {BISHOPS_FILE} — bishops will be skipped")
    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        print("   Run: python scripts/ingest/_build_catholic_dir_db.py")
        return

    # ── Load data ──
    print("Loading 2021 data...")
    with open(ENTRIES_FILE, "r", encoding="utf-8") as f:
        entries_raw = json.load(f)
    print(f"  Entries: {len(entries_raw):,}")

    bishops_raw = []
    if BISHOPS_FILE.exists():
        with open(BISHOPS_FILE, "r", encoding="utf-8") as f:
            bishops_raw = json.load(f)
        print(f"  Bishops: {len(bishops_raw):,}")

    contacts_raw = []
    if CONTACTS_FILE.exists():
        with open(CONTACTS_FILE, "r", encoding="utf-8") as f:
            contacts_raw = json.load(f)
        print(f"  Contacts: {len(contacts_raw):,}")

    if dry_run:
        print("\n── DRY RUN ──")
        # Show entity type distribution
        type_counts = {}
        for e in entries_raw:
            clergy_roles = [p.get("r", "") for p in e.get("p", [])]
            etype = classify_entity_type(e.get("n", ""), clergy_roles)
            type_counts[etype] = type_counts.get(etype, 0) + 1

        print(f"\nEntity type distribution ({len(entries_raw):,} total):")
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"  {t:20s} {c:>8,}")

        # Show diocese breakdown
        diocese_counts = {}
        for e in entries_raw:
            d = e.get("d", "Unknown")
            diocese_counts[d] = diocese_counts.get(d, 0) + 1
        print(f"\nTop 20 dioceses:")
        for d, c in sorted(diocese_counts.items(), key=lambda x: -x[1])[:20]:
            print(f"  {d:40s} {c:>8,}")

        # Show bishop breakdown
        if bishops_raw:
            print(f"\nBishop types:")
            bt = {}
            for b in bishops_raw:
                t = b.get("type", "UNKNOWN")
                bt[t] = bt.get(t, 0) + 1
            for t, c in sorted(bt.items(), key=lambda x: -x[1]):
                print(f"  {t:20s} {c:>6,}")
        return

    # ── Connect to DB ──
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=OFF")  # speed up bulk import
    conn.execute("PRAGMA foreign_keys=OFF")  # defer FK checks until after bulk load

    # ── Clear existing 2021 data ──
    print("\nClearing existing 2021 data...")
    conn.execute("DELETE FROM dir_contacts WHERE entry_id IN (SELECT id FROM dir_entries WHERE directory_year=?)", (DIR_YEAR,))
    conn.execute("DELETE FROM dir_clergy WHERE directory_year=?", (DIR_YEAR,))
    conn.execute("DELETE FROM dir_bishops WHERE directory_year=?", (DIR_YEAR,))
    conn.execute("DELETE FROM dir_entries WHERE directory_year=?", (DIR_YEAR,))
    conn.execute("DELETE FROM dir_provenance WHERE source LIKE 'catholic_dir_2021%'", ())
    conn.commit()

    # ── Import entries ──
    total = len(entries_raw)
    total_clergy = 0
    type_counts = {}

    print(f"\nImporting {total:,} entries...")
    batch_entries = []
    batch_clergy = []

    for i, e in enumerate(entries_raw):
        name = (e.get("n") or "").strip()
        city = (e.get("c") or "").strip()
        state = (e.get("s") or "").strip()
        diocese = (e.get("d") or "").strip()
        clergy_list = e.get("p", [])

        clergy_roles = [p.get("r", "") for p in clergy_list]
        etype = classify_entity_type(name, clergy_roles)
        type_counts[etype] = type_counts.get(etype, 0) + 1

        batch_entries.append((
            DIR_YEAR,
            str(i),           # source_entry_id
            name,
            city if city else None,
            state if state else None,
            diocese if diocese else None,
            etype,
            None,             # address — not in abbreviated source
            None,             # zip
            None,             # phone
            None,             # website
            None,             # email
            None,             # year_founded
            None,             # landmark_type
            None,             # grid_church_id
            None,             # notes
            json.dumps(e, ensure_ascii=False),  # source_raw
        ))

        # Clergy
        for p in clergy_list:
            cname = (p.get("name") or "").strip()
            crole = (p.get("r") or "").strip()
            if cname:
                batch_clergy.append((i, DIR_YEAR, cname, crole, None, None, None))
                total_clergy += 1

        # Commit batch
        if len(batch_entries) >= CHUNK_SIZE:
            _flush_entries(conn, batch_entries, batch_clergy)
            batch_entries.clear()
            batch_clergy.clear()
            print(f"  {progress_bar(i+1, total)}  parishes:{type_counts.get('parish',0):,} cath:{type_counts.get('cathedral',0)} school:{type_counts.get('school',0):,} other:{sum(c for t,c in type_counts.items() if t not in ('parish','cathedral','school')):,}", end="\r")

    # Final flush
    if batch_entries:
        _flush_entries(conn, batch_entries, batch_clergy)

    conn.commit()
    print(f"\n  {progress_bar(total, total)}")

    # ── Fix clergy entry_id references ──
    print("Linking clergy to entry IDs...")
    # First, insert clergy where entry_id is integer (source_entry_id)
    # Use -1 as temp placeholder so FK doesn't block
    cursor = conn.execute("""
        UPDATE dir_clergy SET entry_id = (
            SELECT COALESCE(
                (SELECT de.id FROM dir_entries de
                 WHERE de.directory_year = dir_clergy.directory_year
                 AND de.source_entry_id = CAST(dir_clergy.entry_id AS TEXT)),
                -1
            )
        )
        WHERE dir_clergy.directory_year = ? AND dir_clergy.entry_id >= 0
    """, (DIR_YEAR,))
    print(f"  Linked {cursor.rowcount} clergy records")
    
    # Delete any clergy that couldn't be linked (orphaned)
    conn.execute("DELETE FROM dir_clergy WHERE entry_id = -1")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.commit()

    # ── Import bishops ──
    if bishops_raw:
        print(f"Importing {len(bishops_raw):,} bishops...")
        for b in bishops_raw:
            conn.execute("""
                INSERT INTO dir_bishops (directory_year, name, title, diocese,
                    bishop_type, status, appointed_year, consecrated_year,
                    birth_year, cathedral, source_raw)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                DIR_YEAR,
                b.get("name", "").strip(),
                b.get("title", "").strip() or None,
                b.get("diocese", "").strip() or None,
                b.get("type", "").strip() or None,
                b.get("status", "").strip() or None,
                None, None, None, None,
                json.dumps(b, ensure_ascii=False),
            ))
        conn.commit()

    # ── Import contacts ──
    if contacts_raw:
        print(f"Importing {len(contacts_raw):,} contacts...")
        # Contacts need entry_id mapping — defer to second pass
        # For now, insert with entry_id NULL and link later
        for c in contacts_raw:
            conn.execute("""
                INSERT INTO dir_contacts (entry_id, contact_type, value, source)
                VALUES (NULL, ?, ?, ?)
            """, (
                c.get("type", "other"),
                c.get("value", ""),
                "catholic_dir_2021",
            ))
        conn.commit()

    # ── Log provenance ──
    conn.execute("""
        INSERT INTO dir_provenance (source, description, entry_count,
            clergy_count, bishop_count)
        VALUES (?, ?, ?, ?, ?)
    """, (
        "catholic_dir_2021",
        f"Full import of 2021 Catholic Directory — {total:,} entries across {len(set(e.get('d','') for e in entries_raw))} dioceses",
        total,
        total_clergy,
        len(bishops_raw) if bishops_raw else 0,
    ))
    conn.commit()

    # ── Summary ──
    print(f"\n{'='*60}")
    print(f"✅ 2021 Import Complete")
    print(f"{'='*60}")
    print(f"  Entries:  {total:>10,}")
    print(f"  Clergy:   {total_clergy:>10,}")
    print(f"  Bishops:  {len(bishops_raw):>10,}")
    print(f"\nEntity types:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t:25s} {c:>8,}")

    # Verify
    verified = conn.execute("SELECT COUNT(*) FROM dir_entries WHERE directory_year=?", (DIR_YEAR,)).fetchone()[0]
    print(f"\n  Verified in DB: {verified:,} entries")

    conn.close()
    print("Done.")


def _flush_entries(conn, entries, clergy_list):
    """Batch insert entries and clergy. Clergy use source_entry_id as temp FK (fixed later)."""
    conn.executemany("""
        INSERT INTO dir_entries (directory_year, source_entry_id, name, city,
            state, diocese, entity_type, address, zip, phone, website, email,
            year_founded, landmark_type, grid_church_id, notes, source_raw)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, entries)

    # Clergy: entry_id holds the source_entry_id (index) temporarily
    if clergy_list:
        conn.executemany("""
            INSERT INTO dir_clergy (entry_id, directory_year, name, role,
                prefix, suffix, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, clergy_list)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Import 2021 Catholic Directory")
    p.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    args = p.parse_args()
    import_2021(dry_run=args.dry_run)
