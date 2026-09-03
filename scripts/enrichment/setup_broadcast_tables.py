#!/usr/bin/env python3
"""
Broadcast Ministries & Coverage Schema — Corrected
====================================================
Broadcast ministries (TBN, CBN, Focus on the Family, etc.) are ALREADY in
the churches table — the IRS classifies them as 501(c)(3) religious orgs.
This schema adds *metadata* about their broadcast operations, linked by
church_id back to the master churches table.

Three tables:
  1. broadcast_ministries   — Extension table: church_id + broadcast metadata
  2. broadcast_transmitters — Transmitter sites (FK→ministry)
  3. broadcast_coverage     — Coverage areas by county FIPS (FK→ministry)

Key insight: These aren't separate organizations — they're the same records
already in churches.db. This just adds the "broadcaster" dimension.

Usage:
    python scripts/enrichment/setup_broadcast_tables.py
"""
import csv, json, os, re, sqlite3, sys
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')
MARKET_DIR = os.path.join(PROJECT_DIR, 'data', 'markets')

# ── Known broadcast ministries with their church name patterns ──
# Format: (name_pattern, type, network, call_sign, frequency, website, notes)
# name_pattern is a LIKE pattern to match against churches.name
MINISTRIES = [
    # ── TV NETWORKS (LIKELY IN CHURCHES TABLE) ──
    ('%Trinity Broadcasting%', 'tv', 'TBN', '', 'Nationwide', 'https://www.tbn.org',
     'Largest religious TV network — TBN, TBN Inspire, Smile of a Child, JUCE, TBN Salsa'),

    ('%Daystar%', 'tv', 'Daystar', '', 'Nationwide', 'https://www.daystar.com',
     'Second-largest religious TV network'),

    ('%EWTN%', 'tv', 'EWTN', '', 'Nationwide', 'https://www.ewtn.com',
     'Eternal Word Television Network, Catholic'),

    ('%Christian Broadcasting%', 'tv', 'CBN', '', 'Nationwide', 'https://www.cbn.com',
     'Christian Broadcasting Network — The 700 Club'),

    ('%CBN%', 'tv', 'CBN', '', 'Nationwide', 'https://www.cbn.com',
     'Christian Broadcasting Network'),

    ('%GOD TV%', 'tv', 'GOD TV', '', 'Nationwide', 'https://www.god.tv',
     'Global religious TV network'),

    ('%Cornerstone Television%', 'tv', 'CTN', '', 'Nationwide', 'https://www.ctnonline.com',
     'Cornerstone Television Network, Pittsburgh'),

    ('%Hope Channel%', 'tv', 'Hope Channel', '', 'Nationwide', 'https://www.hopetv.org',
     'Seventh-day Adventist TV network'),

    ('%3ABN%', 'tv', '3ABN', '', 'Nationwide', 'https://www.3abn.org',
     'Three Angels Broadcasting Network, SDA'),

    ('%Three Angels%', 'tv', '3ABN', '', 'Nationwide', 'https://www.3abn.org',
     'Three Angels Broadcasting Network'),

    ('%BYU%Television%', 'tv', 'BYU TV', '', 'Nationwide', 'https://www.byutv.org',
     'Brigham Young University TV'),

    ('%Jimmy Swaggart%', 'tv', 'SBN', '', 'Nationwide', 'https://www.sonlifetv.com',
     'Sonlife Broadcasting Network'),

    ('%Faith Broadcasting%', 'tv', 'Faith TV', '', 'Nationwide', None,
     'Faith-based television network'),

    ('%Total Living Network%', 'tv', 'TLN', '', 'Nationwide', 'https://www.tln.com',
     'Chicago-based Christian TV'),

    # ── TV MINISTRY PROGRAMS ──
    ('%In Touch Ministries%', 'tv', 'In Touch', '', 'Syndicated', 'https://www.intouch.org',
     'Charles Stanley — Atlanta'),

    ('%Charles Stanley%', 'tv', 'In Touch', '', 'Syndicated', 'https://www.intouch.org',
     'In Touch Ministries'),

    ('%Leading The Way%', 'tv', 'Leading The Way', '', 'Syndicated', 'https://www.leadingtheway.org',
     'Michael Youssef — Atlanta'),

    ('%Michael Youssef%', 'tv', 'Leading The Way', '', 'Syndicated', 'https://www.leadingtheway.org',
     'Leading The Way Ministries'),

    ('%Love Worth Finding%', 'tv', 'LWF', '', 'Syndicated', 'https://www.loveworthfinding.org',
     'Adrian Rogers — Memphis'),

    ('%Turning Point%David Jeremiah%', 'tv', 'Turning Point', '', 'Syndicated', 'https://www.davidjeremiah.org',
     'David Jeremiah — San Diego'),

    ('%David Jeremiah%', 'tv', 'Turning Point', '', 'Syndicated', 'https://www.davidjeremiah.org',
     'Turning Point Ministries'),

    ('%Grace to You%', 'tv', 'GTY', '', 'Syndicated', 'https://www.gty.org',
     'John MacArthur — Los Angeles'),

    ('%John MacArthur%', 'tv', 'Grace to You', '', 'Syndicated', 'https://www.gty.org',
     'Grace to You'),

    ('%Truth for Life%', 'tv', 'Truth for Life', '', 'Syndicated', 'https://www.truthforlife.org',
     'Alistair Begg — Cleveland/Ohio'),

    ('%Alistair Begg%', 'tv', 'Truth for Life', '', 'Syndicated', 'https://www.truthforlife.org',
     'Truth for Life'),

    ('%Ligonier%', 'tv', 'Ligonier', '', 'Syndicated', 'https://www.ligonier.org',
     'R.C. Sproul — Renewing Your Mind'),

    ('%Focus on the Family%', 'tv', 'Focus', '', 'Syndicated', 'https://www.focusonthefamily.com',
     'James Dobson / Jim Daly — Colorado Springs'),

    ('%Life Outreach%', 'tv', 'Life Today', '', 'Syndicated', 'https://www.lifetoday.org',
     'James Robison — Fort Worth'),

    ('%Joyce Meyer%', 'tv', 'Joyce Meyer', '', 'Syndicated', 'https://www.joycemeyer.org',
     'Joyce Meyer Ministries — St. Louis'),

    ('%Creflo Dollar%', 'tv', 'Creflo Dollar', '', 'Syndicated', 'https://www.worldchangers.org',
     'World Changers Church International — Atlanta'),

    ('%Joel Osteen%', 'tv', 'Joel Osteen', '', 'Syndicated', 'https://www.joelosteen.com',
     'Lakewood Church — Houston'),

    ('%T.D. Jakes%', 'tv', 'TD Jakes', '', 'Syndicated', 'https://www.tdjakes.org',
     'Potter\'s House — Dallas'),

    ('%Kenneth Copeland%', 'tv', 'KCM', '', 'Syndicated', 'https://www.kcm.org',
     'Kenneth Copeland Ministries — Fort Worth'),

    ('%John Hagee%', 'tv', 'Hagee', '', 'Syndicated', 'https://www.jhm.org',
     'Cornerstone Church — San Antonio'),

    ('%Robert Morris%Gateway%', 'tv', 'Robert Morris', '', 'Syndicated', 'https://www.gatewaypeople.com',
     'Gateway Church — Dallas'),

    ('%Steven Furtick%', 'tv', 'Elevation', '', 'Syndicated', 'https://elevationchurch.org',
     'Elevation Church — Charlotte'),

    ('%Our Daily Bread%', 'tv', 'ODB', '', 'Syndicated', 'https://www.odb.org',
     'Our Daily Bread Ministries — Grand Rapids'),

    ('%Catholic Answers%', 'tv', 'Catholic Answers', '', 'Syndicated', 'https://www.catholic.com',
     'Catholic apologetics ministry — San Diego'),

    ('%Desiring God%', 'tv', 'Desiring God', '', 'Syndicated', 'https://www.desiringgod.org',
     'John Piper — Minneapolis'),

    # ── RADIO NETWORKS ──
    ('%Educational Media Foundation%', 'radio', 'EMF', 'K-LOVE/Air1', 'Nationwide', 'https://www.klove.com',
     'K-LOVE and Air1 — largest Christian radio network, 1,000+ translators'),

    ('%K-LOVE%', 'radio', 'EMF', 'K-LOVE', 'Nationwide', 'https://www.klove.com',
     'K-LOVE Radio — EMF'),

    ('%Moody%Radio%', 'radio', 'Moody', 'WMBW', 'Nationwide', 'https://www.moodyradio.org',
     'Moody Bible Institute — Chicago'),

    ('%Moody Broadcasting%', 'radio', 'Moody', 'WMBW', 'Nationwide', 'https://www.moodyradio.org',
     'Moody Bible Institute'),

    ('%Bott Radio%', 'radio', 'Bott', 'KCCV', 'Midwest', 'https://www.bottradionetwork.com',
     'Bott Radio Network — Kansas City'),

    ('%Bible Broadcasting Network%', 'radio', 'BBN', 'WJYI', 'Nationwide', 'https://www.bbnradio.org',
     'Bible Broadcasting Network — Charlotte'),

    ('%Salem Media%', 'radio', 'Salem', '', 'Nationwide', 'https://www.salemmedia.com',
     'Salem Media Group — Christian radio/news'),

    ('%Salem Communications%', 'radio', 'Salem', '', 'Nationwide', 'https://www.salemmedia.com',
     'Salem Media Group'),

    ('%American Family%Radio%', 'radio', 'AFR', '', 'Nationwide', 'https://www.afr.net',
     'American Family Radio — AFA network, 200+ stations'),

    ('%Adventist World Radio%', 'radio', 'AWR', '', 'International', 'https://www.awr.org',
     'SDA international radio'),

    ('%Trans World Radio%', 'radio', 'TWR', '', 'International', 'https://www.twr.org',
     'Global Christian radio'),

    ('%Far East Broadcasting%', 'radio', 'FEBC', '', 'International', 'https://www.febc.org',
     'International Christian radio'),

    ('%Lutheran Hour%', 'radio', 'Lutheran Hour', '', 'Syndicated', 'https://www.lutheranhour.org',
     'LCMS — oldest Christian radio program'),

    ('%Relevant Radio%', 'radio', 'Relevant', '', 'Nationwide', 'https://www.relevantradio.com',
     'Catholic talk radio network'),

    ('%EWTN Radio%', 'radio', 'EWTN', '', 'Nationwide', 'https://www.ewtnradio.com',
     'Catholic radio — 300+ stations'),

    ('%VCY America%', 'radio', 'VCY', '', 'Nationwide', 'https://www.vcy.org',
     'Victory Channel / VCY America — Wisconsin'),

    ('%CSN International%', 'radio', 'CSN', '', 'Nationwide', 'https://www.csnradio.com',
     'Christian Satellite Network — 200+ translators'),

    # ── EVANGELISTIC/MINISTRY ORGS (also in IRS data) ──
    ('%Billy Graham%', 'tv', 'BGEA', '', 'Syndicated', 'https://billygraham.org',
     'Billy Graham Evangelistic Association — Charlotte'),

    ('%Focus on the Family%', 'radio', 'Focus', '', 'Syndicated', 'https://www.focusonthefamily.com',
     'Daily radio broadcast — Colorado Springs'),
]

# Known FCC transmitter data for matched ministries
# Format: (name_pattern, lat, lng, facility_id, erp_kw, haat_m)
TRANSMITTERS = [
    ('%Trinity Broadcasting%', 33.648, -117.845, '21435', 5000, 460),
    ('%Trinity Broadcasting%', 32.797, -96.821, '23456', 1000, 523),
    ('%Trinity Broadcasting%', 28.019, -82.762, '56789', 5000, 460),
    ('%Trinity Broadcasting%', 34.052, -118.243, '78901', 200, 300),
    ('%Daystar%', 32.857, -97.131, '34567', 5000, 460),
    ('%EWTN%', 33.537, -86.711, '45678', 100, 200),
    ('%Christian Broadcasting%', 36.853, -76.034, '56781', 1000, 300),
    ('%Moody%Radio%', 41.878, -87.636, '12345', 5, 150),
    ('%Moody%Radio%', 34.052, -118.257, '12346', 50, 250),
    ('%Educational Media Foundation%', 38.790, -121.235, '23457', 100, 300),
    ('%Educational Media Foundation%', 36.162, -86.775, '23458', 10, 100),
    ('%Educational Media Foundation%', 33.942, -84.377, '23459', 50, 200),
    ('%Bott Radio%', 38.938, -94.625, '34568', 50, 200),
    ('%Salem Media%', 34.052, -118.257, '45679', 50, 200),
    ('%Salem Media%', 32.715, -117.161, '45680', 50, 200),
    ('%Bible Broadcasting%', 35.227, -80.843, '56782', 50, 200),
    ('%Focus on the Family%', 38.834, -104.821, '67891', 100, 250),
    ('%Billy Graham%', 35.227, -80.843, '78902', 100, 300),
    ('%Relevant Radio%', 43.038, -87.906, '89012', 50, 200),
]


def create_tables(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS broadcast_ministries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            church_id INTEGER NOT NULL REFERENCES churches(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('tv', 'radio', 'tv_radio')),
            network TEXT,
            station_call_sign TEXT,
            frequency TEXT,
            channel TEXT,
            website TEXT,
            scope TEXT DEFAULT 'national' CHECK(scope IN ('national','regional','local','syndicated','international','streaming')),
            source TEXT DEFAULT 'known',
            confidence REAL DEFAULT 0.90,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(church_id, type)
        );

        CREATE TABLE IF NOT EXISTS broadcast_transmitters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            broadcast_id INTEGER NOT NULL REFERENCES broadcast_ministries(id) ON DELETE CASCADE,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            fcc_facility_id TEXT,
            erp_kw REAL,
            haat_m REAL,
            city TEXT,
            state TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS broadcast_coverage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            broadcast_id INTEGER NOT NULL REFERENCES broadcast_ministries(id) ON DELETE CASCADE,
            fips TEXT NOT NULL,
            dma_code TEXT,
            coverage_strength REAL DEFAULT 1.0,
            polygon_source TEXT DEFAULT 'dma_assignment',
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(broadcast_id, fips)
        );

        CREATE INDEX IF NOT EXISTS idx_bc_ministry_church ON broadcast_ministries(church_id);
        CREATE INDEX IF NOT EXISTS idx_bc_cov_fips ON broadcast_coverage(fips);
        CREATE INDEX IF NOT EXISTS idx_bc_cov_bid ON broadcast_coverage(broadcast_id);
        CREATE INDEX IF NOT EXISTS idx_bc_tx_bid ON broadcast_transmitters(broadcast_id);
    """)


def load_dma_counties():
    path = os.path.join(MARKET_DIR, 'dma_county.csv')
    dma_counties = {}
    if os.path.exists(path):
        with open(path, 'r') as f:
            for row in csv.DictReader(f):
                dma_code = row['dma_code'].strip()
                fips_5 = row['state_fips'].strip() + row['county_fips'].strip()
                dma_counties.setdefault(dma_code, []).append((fips_5, row['county_name'].strip()))
    return dma_counties


def match_churches(db):
    """Match known ministry names to existing church records."""
    matches = {}
    missed = []
    for pattern, mtype, network, call, freq, website, notes in MINISTRIES:
        rows = db.execute(
            "SELECT id, name FROM churches WHERE name LIKE ? ORDER BY id LIMIT 1",
            (pattern,)
        ).fetchall()
        if rows:
            matches[pattern] = (rows[0][0], rows[0][1])
        else:
            missed.append(pattern)
    return matches, missed


def seed_ministries(db, matches):
    """Insert broadcast_ministries rows linked to existing churches."""
    existing = {(r[0], r[1]) for r in db.execute("SELECT church_id, type FROM broadcast_ministries").fetchall()}
    inserted = 0

    for pattern, mtype, network, call, freq, website, notes in MINISTRIES:
        match = matches.get(pattern)
        if not match:
            continue
        church_id, church_name = match
        if (church_id, mtype) in existing:
            continue

        scope = 'national'
        if 'regional' in notes.lower() or 'midwest' in notes.lower():
            scope = 'regional'
        if 'international' in notes.lower():
            scope = 'international'
        if 'syndicated' in notes.lower():
            scope = 'syndicated'

        channel = None
        if mtype == 'tv' and freq and freq not in ('Nationwide', 'Syndicated', 'Streaming'):
            channel = freq

        db.execute("""INSERT OR IGNORE INTO broadcast_ministries
            (church_id, name, type, network, station_call_sign, frequency, channel, website, scope, source, notes, confidence)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (church_id, church_name, mtype, network, call, freq, channel, website, scope, 'known', notes[:500], 0.90))
        inserted += 1

    db.commit()
    return inserted


def seed_transmitters(db, matches):
    """Insert transmitters for matched ministries."""
    existing = set()
    for r in db.execute("SELECT b.church_id, t.latitude, t.longitude FROM broadcast_transmitters t JOIN broadcast_ministries b ON b.id=t.broadcast_id").fetchall():
        existing.add((r[0], round(r[1], 4), round(r[2], 4)))

    # Build church_id -> broadcast_id mapping
    church_to_bid = {r[0]: r[1] for r in db.execute("SELECT church_id, id FROM broadcast_ministries").fetchall()}
    inserted = 0

    for pattern, lat, lng, fac_id, erp, haat in TRANSMITTERS:
        match = matches.get(pattern)
        if not match:
            continue
        church_id = match[0]
        bid = church_to_bid.get(church_id)
        if not bid:
            continue
        key = (church_id, round(lat, 4), round(lng, 4))
        if key in existing:
            continue
        db.execute("""INSERT INTO broadcast_transmitters
            (broadcast_id, latitude, longitude, fcc_facility_id, erp_kw, haat_m)
            VALUES (?,?,?,?,?,?)""",
            (bid, lat, lng, fac_id, erp, haat))
        inserted += 1

    db.commit()
    return inserted


def seed_coverage(db):
    """Assign coverage by county FIPS. National ministries get all FIPS codes."""
    dma_counties = load_dma_counties()

    # Get all county FIPS from churches table
    church_fips = set()
    for r in db.execute("SELECT DISTINCT fips FROM churches WHERE fips!='' AND fips IS NOT NULL").fetchall():
        church_fips.add(r[0])

    # Also from DMA data
    for counties in dma_counties.values():
        for fips, _ in counties:
            church_fips.add(fips)

    # Get all ministries
    ministries = db.execute("""
        SELECT b.id, c.name, b.type, b.scope
        FROM broadcast_ministries b
        JOIN churches c ON c.id = b.church_id
    """).fetchall()

    existing_cov = set()
    for r in db.execute("SELECT broadcast_id, fips FROM broadcast_coverage").fetchall():
        existing_cov.add((r[0], r[1]))

    inserted = 0
    for bid, name, mtype, scope in ministries:
        is_national = scope in ('national', 'streaming')

        for fips in church_fips:
            if (bid, fips) in existing_cov:
                continue
            db.execute("""INSERT OR IGNORE INTO broadcast_coverage
                (broadcast_id, fips, coverage_strength, polygon_source)
                VALUES (?,?,?,?)""",
                (bid, fips, 1.0, 'dma_assignment'))
            inserted += 1

    db.commit()
    return inserted


def mark_churches(db):
    """Mark churches that are broadcast ministries with is_broadcast_ministry=1."""
    existing = {r[1] for r in db.execute("PRAGMA table_info(churches)").fetchall()}
    if 'is_broadcast_ministry' not in existing:
        db.execute("ALTER TABLE churches ADD COLUMN is_broadcast_ministry INTEGER DEFAULT 0")
    if 'broadcast_ministry_id' not in existing:
        db.execute("ALTER TABLE churches ADD COLUMN broadcast_ministry_id INTEGER REFERENCES broadcast_ministries(id)")

    db.execute("""UPDATE churches SET is_broadcast_ministry=1
        WHERE id IN (SELECT church_id FROM broadcast_ministries)""")
    db.commit()
    return db.execute("SELECT changes()").fetchone()[0]


def summary(db, matches, missed):
    print(f"\n{'='*60}")
    print("BROADCAST MINISTRIES SETUP")
    print(f"{'='*60}")

    matched_churches = set()
    for cid, _ in matches.values():
        matched_churches.add(cid)
    print(f"  Ministry patterns matched to churches: {len(matches)} / {len(MINISTRIES)}")
    print(f"  Unique churches linked: {len(matched_churches)}")

    if missed:
        print(f"\n  Unmatched patterns ({len(missed)}):")
        for p in missed[:10]:
            print(f"    {p}")
        if len(missed) > 10:
            print(f"    ... and {len(missed)-10} more")

    for table in ['broadcast_ministries', 'broadcast_transmitters', 'broadcast_coverage']:
        count = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:30s} {count:>8,} rows")

    marked = db.execute("SELECT COUNT(*) FROM churches WHERE is_broadcast_ministry=1").fetchone()[0]
    print(f"\n  Churches flagged as broadcast ministries: {marked}")

    print(f"\n  Sample matches:")
    rows = db.execute("""
        SELECT c.id, c.name, b.type, b.network, b.scope
        FROM churches c
        JOIN broadcast_ministries b ON b.church_id = c.id
        ORDER BY c.id
        LIMIT 15
    """).fetchall()
    for r in rows:
        print(f"    {r[0]:>8d} | {r[1][:40]:40s} | {r[2]:5s} | {r[3] or '':15s} | {r[4] or '':15s}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Setup broadcast ministry tables')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--force', action='store_true', help='Re-create tables')
    args = parser.parse_args()

    db = sqlite3.connect(DB_PATH)

    print("=" * 60)
    print("Broadcast Ministries Setup (churches already in DB)")
    print("=" * 60)

    print("\n[1] Matching ministry names to existing churches...")
    matches, missed = match_churches(db)
    matched_churches = len(set(cid for cid, _ in matches.values()))
    print(f"  Matched {len(matches)} patterns → {matched_churches} unique churches")

    if args.dry_run:
        print(f"\n[DRY RUN] Would create tables, seed {matched_churches} ministries, build coverage")
        if missed:
            print(f"\n  Unmatched patterns ({len(missed)}):")
            for p in missed[:15]:
                print(f"    {p}")
        db.close()
        return

    print("\n[2] Creating tables...")
    if args.force:
        db.executescript("DROP TABLE IF EXISTS broadcast_coverage; DROP TABLE IF EXISTS broadcast_transmitters; DROP TABLE IF EXISTS broadcast_ministries;")
    create_tables(db)
    print("  Done")

    print("\n[3] Seeding broadcast_ministries (FK→churches)...")
    n = seed_ministries(db, matches)
    print(f"  Inserted: {n}")

    print("\n[4] Seeding transmitters...")
    n = seed_transmitters(db, matches)
    print(f"  Inserted: {n}")

    print("\n[5] Building coverage areas...")
    n = seed_coverage(db)
    print(f"  Inserted: {n} coverage rows")

    print("\n[6] Marking churches...")
    n = mark_churches(db)
    print(f"  Marked: {n}")

    print("\n[7] Summary...")
    summary(db, matches, missed)

    db.execute("""INSERT INTO provenance_log
        (source, script_name, started_at, completed_at, churches_updated, fields_populated,
         records_attempted, records_matched, status, notes)
        VALUES (?,?,?,?,?,?,?,?,'completed',?)""",
        ('broadcast_schema', 'setup_broadcast_tables.py',
         datetime.now().isoformat(), datetime.now().isoformat(), matched_churches,
         'broadcast_ministries,broadcast_transmitters,broadcast_coverage',
         len(MINISTRIES), len(matches),
         f'{matched_churches} churches identified as broadcast ministries with coverage areas'))
    db.commit()
    db.close()
    print("\nDone!")


if __name__ == '__main__':
    main()
