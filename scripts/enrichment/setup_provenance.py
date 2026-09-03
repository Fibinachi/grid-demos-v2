#!/usr/bin/env python3
"""
Provenance & Sources System
============================
Creates a proper sources tracking system:
- sources table: what was scraped, from where, when
- church_sources junction table: which source each church came from

Usage:
    python scripts/enrichment/setup_provenance.py          # Create tables
    python scripts/enrichment/setup_provenance.py --migrate # Migrate existing source data
    python scripts/enrichment/setup_provenance.py --report  # Show provenance report
"""
import sqlite3, os, sys
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
for _ in range(5):
    if os.path.exists(os.path.join(PROJECT_DIR, "churches.db")):
        break
    parent = os.path.dirname(PROJECT_DIR)
    if parent == PROJECT_DIR:
        break
    PROJECT_DIR = parent

DB_PATH = os.path.join(PROJECT_DIR, "churches.db")

def log(msg):
    print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg))

def create_tables():
    """Create the provenance tracking tables."""
    log("Creating provenance tables...")
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    
    # Main sources registry
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sources (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL UNIQUE,
            source_type     TEXT NOT NULL DEFAULT 'import',
            description     TEXT DEFAULT '',
            url             TEXT DEFAULT '',
            scrape_date     TEXT DEFAULT (date('now')),
            record_count    INTEGER DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now')),
            notes           TEXT DEFAULT '',
            
            -- Refresh / scheduling fields
            refreshable     INTEGER DEFAULT 0,
            refresh_url     TEXT DEFAULT '',
            refresh_type    TEXT DEFAULT '',
            refresh_freq    TEXT DEFAULT '',
            last_success    TEXT DEFAULT '',
            next_scheduled  TEXT DEFAULT '',
            update_url      TEXT DEFAULT ''
        )
    """)
    
    # Church-to-source junction table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS church_sources (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            church_id       INTEGER NOT NULL REFERENCES churches(id),
            source_id       INTEGER NOT NULL REFERENCES sources(id),
            confidence      REAL DEFAULT 1.0,
            created_at      TEXT DEFAULT (datetime('now')),
            UNIQUE(church_id, source_id)
        )
    """)
    
    # Index for fast lookups
    cur.execute("CREATE INDEX IF NOT EXISTS idx_church_sources_church ON church_sources(church_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_church_sources_source ON church_sources(source_id)")
    
    # Add refresh columns if upgrading existing table
    for col, col_type in [("refreshable", "INTEGER DEFAULT 0"), ("refresh_url", "TEXT DEFAULT ''"),
                          ("refresh_type", "TEXT DEFAULT ''"), ("refresh_freq", "TEXT DEFAULT ''"),
                          ("last_success", "TEXT DEFAULT ''"), ("next_scheduled", "TEXT DEFAULT ''"),
                          ("update_url", "TEXT DEFAULT ''")]:
        try:
            cur.execute(f"ALTER TABLE sources ADD COLUMN {col} {col_type}")
        except:
            pass  # Column already exists
    
    db.commit()
    
    # Seed known sources with refresh info
    known_sources = [
        # (name, type, desc, url, scrape_date, refreshable, refresh_url, refresh_type, refresh_freq)
        ("irs_efile", "import", "IRS Form 990 e-file database", "", "",
         1, "", "annual_import", "yearly"),
        ("sbc_api", "api", "SBC churches.sbc.net WP-JSON API", "https://churches.sbc.net/wp-json/wp/v2/church", "2026-06-11",
         1, "https://churches.sbc.net/wp-json/wp/v2/church?per_page=100", "api", "monthly"),
        ("sbc_scrape", "web_scrape", "SBC individual church page scrape", "", "2026-06-11",
         0, "", "", ""),
        ("umc_conference_scrape", "web_scrape", "UMC Annual Conference websites", "", "2026-06-11",
         1, "", "web_scrape", "monthly"),
        ("arda_2020", "import", "ARDA Religious Congregations & Membership Study 2020", "", "",
         0, "", "", ""),
        ("overture_maps", "api", "Overture Maps places dataset", "", "",
         1, "", "api", "quarterly"),
        ("batch_finder", "script", "Batch website finder script", "", "",
         1, "", "script", "monthly"),
        ("contacts_import", "import", "Legacy contacts CSV import", "", "",
         0, "", "", ""),
        ("chabad_scrape", "web_scrape", "Chabad.org directory scrape", "", "2026-06-11",
         1, "https://www.chabad.org/directory", "web_scrape", "monthly"),
        ("urj_scrape", "web_scrape", "URJ synagogue directory scrape", "", "2026-06-11",
         1, "https://urj.org/congregations", "web_scrape", "monthly"),
        ("facebook_scrape", "web_scrape", "Facebook Pages discovery scraper", "", "",
         1, "", "script", "monthly"),
        ("us_census_acs", "api", "US Census American Community Survey API", "", "",
         1, "https://api.census.gov/data/2022/acs/acs5", "api", "yearly"),
        ("here_geocode", "api", "HERE Maps geocoding API", "", "",
         1, "", "api", "on_demand"),
    ]
    
    for row in known_sources:
        name, stype, desc, url, sdate = row[:5]
        refreshable = row[5] if len(row) > 5 else 0
        refresh_url = row[6] if len(row) > 6 else ""
        refresh_type = row[7] if len(row) > 7 else ""
        refresh_freq = row[8] if len(row) > 8 else ""
        try:
            cur.execute("""
                INSERT OR IGNORE INTO sources 
                (name, source_type, description, url, scrape_date, refreshable, refresh_url, refresh_type, refresh_freq)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (name, stype, desc, url, sdate, refreshable, refresh_url, refresh_type, refresh_freq))
        except:
            pass
    
    db.commit()
    
    # Show what we have
    cur.execute("SELECT id, name, source_type, record_count, scrape_date FROM sources ORDER BY id")
    log("Available sources:")
    for r in cur.fetchall():
        log(f"  ID={r[0]:2d} | {r[1]:25s} | {r[2]:12s} | {r[3]:6d} records | scraped {r[4]}")
    
    db.close()

def migrate_existing():
    """Migrate existing source values from churches table into new system."""
    log("Migrating existing source data...")
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    
    # Get all unique source values
    cur.execute("SELECT DISTINCT source FROM churches WHERE source != '' AND source IS NOT NULL")
    raw_sources = [r[0] for r in cur.fetchall()]
    
    # Parse comma-separated sources and create mapping
    source_map = {}  # raw_value -> source_id
    for raw in raw_sources:
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        for part in parts:
            if part not in source_map:
                # Check if this source exists in sources table
                cur.execute("SELECT id FROM sources WHERE name=?", (part,))
                row = cur.fetchone()
                if row:
                    source_map[part] = row[0]
                else:
                    # Create new source entry
                    stype = "import"
                    if "scrape" in part or "scraped" in part:
                        stype = "web_scrape"
                    elif "api" in part:
                        stype = "api"
                    cur.execute("INSERT INTO sources (name, source_type) VALUES (?,?)", (part, stype))
                    source_map[part] = cur.lastrowid
    
    # Link churches to sources
    linked = 0
    cur.execute("SELECT id, source FROM churches WHERE source != '' AND source IS NOT NULL")
    for cid, raw in cur.fetchall():
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        for part in parts:
            if part in source_map:
                try:
                    cur.execute("INSERT OR IGNORE INTO church_sources (church_id, source_id) VALUES (?,?)",
                               (cid, source_map[part]))
                    linked += 1
                except:
                    pass
    
    db.commit()
    log(f"  Linked {linked} church-source relationships")
    
    # Update record counts
    cur.execute("UPDATE sources SET record_count = (SELECT COUNT(*) FROM church_sources WHERE source_id = sources.id)")
    db.commit()
    
    db.close()

def report():
    """Show provenance report with refresh schedule."""
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    
    print("\n=== PROVENANCE & REFRESH REPORT ===")
    print(f"{'Source':30s} {'Type':12s} {'Records':>10s} {'Scraped':12s} {'Refresh':8s} {'Freq':10s} {'URL'}")
    print("="*120)
    cur.execute("""
        SELECT s.name, s.source_type, s.record_count, s.scrape_date, 
               s.refreshable, s.refresh_freq, s.refresh_url
        FROM sources s ORDER BY s.record_count DESC
    """)
    for r in cur.fetchall():
        ref = "✓" if r[4] else "✗"
        url = (r[6] or r[2] or "")[:40]
        print(f"  {r[0]:30s} {r[1]:12s} {r[2]:>8,d}  {r[3] or '':10s}  {ref:6s}  {r[5] or '':10s} {url}")
    
    print(f"\nTotal records: {sum(r[0] for r in cur.execute('SELECT COUNT(*) FROM churches'))}")
    
    print("\n=== REFRESH SCHEDULE ===")
    cur.execute("SELECT name, refresh_freq, refresh_url, last_success FROM sources WHERE refreshable=1 ORDER BY refresh_freq")
    for r in cur.fetchall():
        print(f"  {r[0]:30s} | every {r[1]:10s} | {r[2][:50] or '[same URL]'} | last: {r[3] or 'never'}")
    
    db.close()

def schedule():
    """Show what needs refreshing."""
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    
    print("\n=== DATA REFRESH SCHEDULE ===")
    print(f"{'Source':30s} {'Type':12s} {'Last':14s} {'Freq':10s} {'Status':15s} {'Action'}")
    print("="*90)
    
    from datetime import date, timedelta
    today = date.today()
    
    cur.execute("SELECT name, source_type, scrape_date, refresh_freq, refresh_url, record_count FROM sources WHERE refreshable=1 ORDER BY refresh_freq")
    for r in cur.fetchall():
        name, stype, sdate, freq, url, count = r
        
        # Determine status
        status = "NEEDS UPDATE"
        action = f"python scripts/scrapers/scrape_{name.split('_')[0]}.py"
        
        if sdate:
            try:
                last = date.fromisoformat(sdate)
                days_since = (today - last).days
                
                if freq == "daily" and days_since < 1:
                    status = "✓ fresh"
                elif freq == "weekly" and days_since < 7:
                    status = f"✓ {days_since}d old"
                elif freq == "monthly" and days_since < 30:
                    status = f"✓ {days_since}d old"
                elif freq == "quarterly" and days_since < 90:
                    status = f"✓ {days_since}d old"
                elif freq == "yearly" and days_since < 365:
                    status = f"✓ {days_since}d old"
                else:
                    status = f"⚠ {days_since}d overdue"
            except:
                status = "no date"
        else:
            status = "never scraped"
            if name == "irs_efile":
                action = "python scripts/irs/refresh_irs.py"
            elif name == "facebook_scrape":
                action = "python scripts/enrichment/facebook_scraper_ec2.py"
        
        print(f"  {name:30s} {stype:12s} {(sdate or '--'):14s} {freq:10s} {status:15s} {action}")
    
    db.close()

if __name__ == "__main__":
    args = sys.argv[1:]
    
    if "--migrate" in args:
        migrate_existing()
    elif "--report" in args:
        report()
    elif "--schedule" in args:
        schedule()
    else:
        create_tables()
        if "--all" in args:
            migrate_existing()
            report()
