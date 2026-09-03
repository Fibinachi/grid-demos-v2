#!/usr/bin/env python3
"""
GrantWizard Enrichment Pipeline — Canonical Implementation
===========================================================
Merges multi-source data into a single unified table using a strict
confidence hierarchy: IRS > Google KG > Scrape > ZeroBounce > Heuristics > Unknown

Usage:
    python pipeline/enrich_pipeline.py                          # all steps
    python pipeline/enrich_pipeline.py --step classify          # faith classification only
    python pipeline/enrich_pipeline.py --step normalize         # name normalization only
    python pipeline/enrich_pipeline.py --step kg                # Google KG enrichment
    python pipeline/enrich_pipeline.py --step zerobounce       # email validation only
"""

import sqlite3, csv, os, re, json, sys, time, math, urllib.request, urllib.error
from datetime import datetime, timezone
from gw_filters import faith

# ── Config ────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
IRS_PATH = os.path.join(PROJECT_DIR, "data", "irs", "irs_churches.csv")
ZEROBOUNCE_KEY = os.environ.get("ZEROBOUNCE_API_KEY", "")
KG_API_KEY = os.environ.get("GOOGLE_KG_API_KEY", "")

BATCH_SIZE = 1000
KG_DAILY_QUOTA = 100  # Free tier: 100K/day, be conservative

# ── Faith classification — migrated to gw_filters/faith.py ────────
# NTEE_MAP, NAME_HEURISTICS, KG_RELIGION_MAP, KG_DESC_KEYWORDS
# are now in gw_filters.faith — use faith.from_ntee(), faith.from_name(), etc.

# ── Immutable fields — never overwritten once set ─────────────────
IMMUTABLE_FIELDS = {"ein", "ntee_code", "faith_tradition", "classification_source"}

# ── Helpers ────────────────────────────────────────────────────────

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db

def ensure_columns(db, columns):
    """Add columns if they don't exist."""
    cur = db.execute("PRAGMA table_info(churches)")
    existing = {c[1] for c in cur.fetchall()}
    for col_name, col_type in columns.items():
        if col_name not in existing:
            db.execute(f"ALTER TABLE churches ADD COLUMN {col_name} {col_type}")
    db.commit()

def ensure_log_table(db):
    """Create the enrichment_change_log table if it doesn't exist."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS enrichment_change_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            church_id INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            change_source TEXT,
            enrichment_version INTEGER,
            changed_at TEXT DEFAULT (datetime('now'))
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_ecl_church ON enrichment_change_log(church_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_ecl_field ON enrichment_change_log(field_name)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_ecl_time ON enrichment_change_log(changed_at)")
    db.commit()

def log_change(db, church_id, field, old_value, new_value, source):
    """Write a single field-level change to the audit log."""
    if old_value == new_value:
        return  # skip no-op
    try:
        ver = db.execute(
            "SELECT enrichment_version FROM churches WHERE id = ?", (church_id,)
        ).fetchone()
        version = ver[0] if ver and ver[0] else 0
        db.execute(
            """INSERT INTO enrichment_change_log
               (church_id, field_name, old_value, new_value, change_source, enrichment_version)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (church_id, field,
             str(old_value)[:500] if old_value is not None else None,
             str(new_value)[:500] if new_value is not None else None,
             source, version)
        )
    except Exception:
        pass  # fail gracefully, don't block enrichment

def update_field(db, church_id, field, new_value, source):
    """
    Update a single field with immutability enforcement.
    Fields in IMMUTABLE_FIELDS are never written if they already have a non-null value.
    Returns True if updated, False if skipped.
    """
    if field in IMMUTABLE_FIELDS:
        current = db.execute(
            f"SELECT {field} FROM churches WHERE id = ?", (church_id,)
        ).fetchone()
        if current and current[0] is not None and str(current[0]).strip():
            return False  # immutable and already set
    db.execute(
        f"UPDATE churches SET {field} = ? WHERE id = ?",
        (new_value, church_id)
    )
    return True

def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    print(f"[{t}] {msg}")

def normalize_name(name):
    """Normalize a church name: strip legal suffixes, collapse whitespace."""
    if not name:
        return ""
    n = name.strip().upper()
    # Remove common legal suffixes
    suffixes = [r'\s+INC\b', r'\s+LLC\b', r'\s+CORP\b', r'\s+PC\b', r'\s+PA\b',
                r'\s+THE\b', r'\s+A\s+', r'\s+AN\s+']
    for s in suffixes:
        n = re.sub(s, ' ', n)
    # Collapse whitespace
    n = re.sub(r'\s+', ' ', n).strip()
    # Remove leading "THE "
    n = re.sub(r'^THE\s+', '', n)
    return n

def ntee_to_faith(ntee):
    """Map IRS NTEE code to faith tradition."""
    if not ntee:
        return None, None
    code = ntee.strip().upper()
    for prefix, faith in sorted(NTEE_MAP.items(), key=lambda x: -len(x[0])):
        if code.startswith(prefix):
            return faith, "irs"
    if code.startswith("X"):
        return "unknown", "irs"
    return None, None

def name_to_faith(name):
    """Classify faith tradition from name heuristics (via gw_filters.faith)."""
    if not name:
        return "unknown", "no_name"
    tradition = faith.from_name(name)
    return (tradition, "name_heuristic") if tradition != "unknown" else (None, None)

def kg_category_to_faith(categories, description=""):
    """Map Google KG result to faith tradition (via gw_filters.faith)."""
    # Check description for faith keywords
    if description:
        tradition = faith.from_kg_description(description)
        if tradition != "unknown":
            return tradition, "kg"
    # Fall back to @type matching
    if not categories:
        return None, None
    for cat in categories:
        cat_id = cat.get("@id", "").lower()
        cat_name = cat.get("name", "").lower()
        tradition = faith.from_kg_type(cat_name) if cat_name else "unknown"
        if tradition != "unknown":
            return tradition, "kg"
        tradition = faith.from_kg_type(cat_id) if cat_id else "unknown"
        if tradition != "unknown":
            return tradition, "kg"
    return None, None

def normalize_phone(phone):
    """Normalize phone to E.164 format. Returns None if invalid."""
    if not phone:
        return None
    digits = re.sub(r'\D', '', str(phone))
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return None


# ── Step 1: Schema Migration ──────────────────────────────────────

def step_schema():
    """Add required columns for the canonical schema."""
    log("Step 1: Schema migration")
    db = get_db()
    ensure_columns(db, {
        "normalized_name": "TEXT",
        "faith_tradition": "TEXT",
        "classification_source": "TEXT",
        # Scrape tracking — marks which records have been checked
        "website_scrape_status": "TEXT DEFAULT 'pending'",
        "email_scrape_status": "TEXT DEFAULT 'pending'",
        # Per-field confidence scores (0.0 - 1.0)
        "website_confidence": "REAL",
        "email_confidence": "REAL",
        "phone_confidence": "REAL",
        "geocode_confidence": "REAL",
        "scrape_confidence": "REAL",
        "kg_confidence": "REAL",
        "zb_confidence": "REAL",
        # Last-verified timestamps (ISO 8601)
        "website_last_verified": "TEXT",
        "email_last_verified": "TEXT",
        "phone_last_verified": "TEXT",
        "geocode_last_verified": "TEXT",
        "enrichment_version": "INTEGER",
        "spanish_language": "TEXT",
        "spanish_detection_source": "TEXT",
    })
    # Set enrichment_version default if null
    db.execute("UPDATE churches SET enrichment_version = 1 WHERE enrichment_version IS NULL")
    # Migrate existing religion_type -> faith_tradition if not yet populated
    db.execute("""
        UPDATE churches SET faith_tradition = religion_type, classification_source = 'name_heuristic'
        WHERE faith_tradition IS NULL AND religion_type IS NOT NULL AND religion_type != ''
    """)
    db.commit()
    count = db.execute("SELECT COUNT(*) FROM churches WHERE classification_source IS NOT NULL").fetchone()[0]
    count = db.execute("SELECT COUNT(*) FROM churches WHERE classification_source IS NOT NULL").fetchone()[0]
    log(f"  {count:,} churches have classification_source set")
    ensure_log_table(db)
    log("  Change log table ready")
    db.close()


# ── Step 2: Name Normalization ────────────────────────────────────

def step_normalize():
    """Normalize church names."""
    log("Step 2: Name normalization")
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
    for offset in range(0, total, BATCH_SIZE):
        rows = db.execute(
            "SELECT id, name FROM churches WHERE normalized_name IS NULL OR normalized_name = '' LIMIT ? OFFSET ?",
            (BATCH_SIZE, offset)
        ).fetchall()
        if not rows:
            break
        for row in rows:
            normalized = normalize_name(row["name"])
            db.execute("UPDATE churches SET normalized_name = ? WHERE id = ?", (normalized, row["id"]))
        db.commit()
        if (offset + BATCH_SIZE) % 10000 == 0:
            log(f"  Normalized {min(offset + BATCH_SIZE, total):,} / {total:,}")
    db.close()
    log("  Name normalization complete")


# ── Step 3: Faith Classification ───────────────────────────────────

def step_classify():
    """
    Classify faith tradition using the confidence hierarchy:
    IRS NTEE > Google KG > Name Heuristics > Unknown
    """
    log("Step 3: Faith classification")

    # Load NTEE codes from IRS CSV
    ntee_map = {}
    log("  Loading IRS NTEE codes...")
    with open(IRS_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ein = row.get("EIN", "").strip()
            ntee = row.get("NTEE_CD", "").strip()
            if ein:
                ntee_map[ein] = ntee
    log(f"  Loaded {len(ntee_map):,} EIN -> NTEE mappings")

    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM churches").fetchone()[0]

    # A. IRS NTEE codes (highest confidence)
    log("  A. Classifying by IRS NTEE...")
    irs_count = 0
    for offset in range(0, total, BATCH_SIZE):
        rows = db.execute(
            "SELECT id, ein, ntee_code FROM churches WHERE ein IS NOT NULL AND ein != '' LIMIT ? OFFSET ?",
            (BATCH_SIZE, offset)
        ).fetchall()
        for row in rows:
            ein = row["ein"].strip()
            ntee = ntee_map.get(ein, row["ntee_code"] or "")
            faith, source = ntee_to_faith(ntee)
            if faith:
                cid = row["id"]
                if update_field(db, cid, "faith_tradition", faith, source):
                    update_field(db, cid, "classification_source", source, source)
                    update_field(db, cid, "ntee_code", ntee, source)
                    irs_count += 1
        db.commit()
    log(f"    IRS-classified: {irs_count:,}")

    # B. Name heuristics for remaining
    log("  B. Classifying by name heuristics...")
    heur_count = 0
    for offset in range(0, total, BATCH_SIZE):
        rows = db.execute(
            "SELECT id, name FROM churches WHERE faith_tradition IS NULL LIMIT ? OFFSET ?",
            (BATCH_SIZE, offset)
        ).fetchall()
        for row in rows:
            faith, source = name_to_faith(row["name"])
            if faith:
                cid = row["id"]
                if update_field(db, cid, "faith_tradition", faith, source):
                    update_field(db, cid, "classification_source", source, source)
                    heur_count += 1
        db.commit()
    log(f"    Heuristic-classified: {heur_count:,}")

    # C. Remaining -> unknown
    unknown = db.execute("SELECT COUNT(*) FROM churches WHERE faith_tradition IS NULL").fetchone()[0]
    if unknown:
        db.execute("UPDATE churches SET faith_tradition = 'unknown', classification_source = 'none' WHERE faith_tradition IS NULL")
        db.commit()
        log(f"    Set unknown: {unknown:,}")

    # Summary
    summary = db.execute(
        "SELECT classification_source, COUNT(*) FROM churches GROUP BY classification_source ORDER BY COUNT(*) DESC"
    ).fetchall()
    for row in summary:
        log(f"    {row['classification_source']:20s}: {row[1]:>7,}")

    db.close()


# ── Step: Detect Spanish-language churches ─────────────────────────

def step_spanish():
    """
    Detect Spanish-language churches using up to 5 signals:
      1. Name heuristics
      2. Website keywords (if scraped)
      3. Service times (if structured)
      4. KG categories (if available)
      5. Denomination mapping (known Hispanic districts/conferences)
    """
    log("Step: Spanish-language detection")
    db = get_db()

    ensure_columns(db, {
        "spanish_language": "TEXT",
        "spanish_detection_source": "TEXT",
    })

    # ── 1. Name heuristics ──────────────────────────────────────────
    log("  1. Name heuristics...")
    name_kw = [
        'iglesia', 'iglecia', 'templo', 'ministerio', 'ministerio hispano',
        'cristiana', 'cristiano', 'pentecostal hispana', 'pentecostal hispano',
        'iglesia de dios', 'iglesia cristiana', 'iglesia pentecostal',
        'dios', 'señor', 'senor', 'jesucristo', 'cristo', 'jesus',
        'asamblea de dios', 'asambleas de dios', 'asamblea',
        'casa de dios', 'casa de oracion', 'casa de', 'palabra de',
        'evangelio', 'evangelica', 'evangelico',
        'mision', 'misionero', 'misionera', 'misiones',
        'santa', 'santo', 'santidad',
        'alabanza', 'adoracion', 'adoración', 'salvacion', 'salvación',
        'bendicion', 'bendición', 'espiritu', 'espíritu',
        'nueva', 'nuevo', 'nueva vida', 'nuevo amanecer',
        'comunidad', 'poder de dios', 'poder',
        'vida', 'vida nueva', 'vida eterna',
        'paz', 'paz de dios', 'esperanza', 'gracia',
        'fe', 'fe en dios', 'luz', 'verdad', 'camino',
        'corazon', 'corazón', 'alma', 'cielo', 'gloria',
        'familia', 'familia de dios', 'rey de reyes', 'rey',
        'amor de dios', 'amor', 'milagro', 'aleluya',
        'hermano', 'hermana', 'vision', 'visión',
        'templo bethel', 'templo biblico', 'templo cristiano',
    ]
    conditions = ' OR '.join([f"LOWER(name) LIKE '%{kw}%'" for kw in name_kw])
    db.execute(f"""
        UPDATE churches SET
            spanish_language = 'true',
            spanish_detection_source = 'name'
        WHERE ({conditions})
    """)
    db.commit()

    # Log Spanish denom-based changes
    db.execute("""
        INSERT INTO enrichment_change_log (church_id, field_name, new_value, change_source, enrichment_version)
        SELECT id, 'spanish_language', 'true', 'denom_mapping', enrichment_version
        FROM churches WHERE spanish_language = 'true' AND spanish_detection_source LIKE '%denomination%'
    """)
    db.commit()

    # ── 5. Denomination mapping ──────────────────────────────────────
    log("  5. Denomination mapping...")
    # Known Hispanic denomination indicators
    db.execute("""
        UPDATE churches SET
            spanish_language = 'true',
            spanish_detection_source =
                CASE WHEN spanish_detection_source IS NULL OR spanish_detection_source = '' OR spanish_detection_source = 'denomination'
                     THEN 'denomination' ELSE spanish_detection_source || ',denomination' END
        WHERE (
            LOWER(denomination) LIKE '%hispanic%'
            OR LOWER(denomination) LIKE '%latino%'
            OR LOWER(denomination) LIKE '%español%'
            OR LOWER(denomination) LIKE '%spanish%'
            OR LOWER(name) LIKE '%hispana%'
            OR LOWER(name) LIKE '%hispano%'
            OR LOWER(name) LIKE '%latina%'
            OR LOWER(name) LIKE '%latino%'
        )
    """)
    db.commit()

    # ── Summary ─────────────────────────────────────────────────────
    true_cnt = db.execute("SELECT COUNT(*) FROM churches WHERE spanish_language = 'true'").fetchone()[0]
    false_cnt = db.execute("SELECT COUNT(*) FROM churches WHERE spanish_language = 'false'").fetchone()[0]
    unknown_cnt = db.execute("SELECT COUNT(*) FROM churches WHERE spanish_language IS NULL OR spanish_language = 'unknown'").fetchone()[0]
    log(f"    Spanish=true:  {true_cnt:,}")
    log(f"    Spanish=false: {false_cnt:,}")
    log(f"    Spanish=unknown: {unknown_cnt:,}")

    # Source breakdown
    sources = db.execute(
        "SELECT spanish_detection_source, COUNT(*) FROM churches WHERE spanish_language = 'true' GROUP BY spanish_detection_source ORDER BY COUNT(*) DESC"
    ).fetchall()
    for src, cnt in sources:
        log(f"      via {src}: {cnt:,}")
    db.close()


# ── Step 4: Google Knowledge Graph Enrichment ─────────────────────

def kg_search(name, city, state):
    """Query Google Knowledge Graph API for a church."""
    if not KG_API_KEY or not name:
        return None
    query = f"{name} {city or ''} {state or ''}".strip()[:100]
    url = (
        f"https://kgsearch.googleapis.com/v1/entities:search"
        f"?query={urllib.parse.quote(query)}&key={KG_API_KEY}&limit=3&types=Thing"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
            items = data.get("itemListElement", [])
            if items:
                result = items[0].get("result", {})
                return {
                    "name": result.get("name", ""),
                    "description": result.get("description", ""),
                    "website": (result.get("url", "") or ""),
                    "sameAs": ";".join(result.get("detailedDescription", {}).get("url", "") if isinstance(result.get("detailedDescription"), dict) else []),
                    "categories": [c.get("name", "") for c in result.get("@type", [])],
                    "score": items[0].get("resultScore", 0),
                }
    except Exception:
        pass
    return None

def step_kg():
    """Enrich with Google Knowledge Graph data. Rate-limited to KG_DAILY_QUOTA."""
    log("Step 4: Google KG enrichment")
    if not KG_API_KEY:
        log("  ❌ No GOOGLE_KG_API_KEY set")
        return

    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM churches WHERE faith_tradition = 'unknown' OR classification_source IS NULL").fetchone()[0]
    log(f"  {total:,} candidates for KG enrichment")

    enriched = 0
    for offset in range(0, min(total, KG_DAILY_QUOTA), 1):
        row = db.execute(
            "SELECT id, name, city, state FROM churches WHERE (faith_tradition = 'unknown' OR classification_source IS NULL) LIMIT 1 OFFSET ?",
            (offset,)
        ).fetchone()
        if not row:
            break

        kg = kg_search(row["name"], row["city"], row["state"])
        if kg and kg["score"] > 50:
            faith, source = kg_category_to_faith(kg.get("categories", []), kg.get("description", ""))
            if faith:
                cid = row["id"]
                if update_field(db, cid, "faith_tradition", faith, source):
                    update_field(db, cid, "classification_source", source, source)
                    update_field(db, cid, "kg_confidence", kg["score"], source)
                    enriched += 1
                    if kg["website"] and not row_has_working_website(db, row["id"]):
                        db.execute("UPDATE churches SET website = ? WHERE id = ?", (kg["website"], row["id"]))

        if (offset + 1) % 5 == 0:
            db.commit()
            log(f"    KG enriched: {enriched:,}")
        time.sleep(0.3)  # Rate limit

    db.commit()
    log(f"  Total KG enriched: {enriched:,}")
    db.close()


def row_has_working_website(db, row_id):
    """Check if a row already has a non-empty website."""
    val = db.execute("SELECT website FROM churches WHERE id = ?", (row_id,)).fetchone()
    return bool(val and val["website"])


# ── Step 5: ZeroBounce Email Validation ───────────────────────────

def zb_validate(email):
    """Validate email via ZeroBounce API."""
    if not ZEROBOUNCE_KEY or not email:
        return None
    url = f"https://api.zerobounce.net/v2/validate?api_key={ZEROBOUNCE_KEY}&email={urllib.parse.quote(email)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return {
                "status": data.get("status", ""),
                "score": data.get("score"),
                "sub_status": data.get("sub_status", ""),
            }
    except Exception:
        return None

def step_zerobounce():
    """Validate email addresses via ZeroBounce. Updates zb_confidence."""
    log("Step 5: ZeroBounce email validation")
    if not ZEROBOUNCE_KEY:
        log("  ❌ No ZEROBOUNCE_API_KEY set")
        return

    db = get_db()
    total = db.execute(
        "SELECT COUNT(*) FROM churches WHERE email IS NOT NULL AND email != '' AND (zb_confidence IS NULL OR zb_confidence = 0)"
    ).fetchone()[0]
    log(f"  {total:,} emails to validate")

    validated = 0
    for offset in range(0, total, 1):
        row = db.execute(
            "SELECT id, email FROM churches WHERE email IS NOT NULL AND email != '' AND (zb_confidence IS NULL OR zb_confidence = 0) LIMIT 1 OFFSET ?",
            (offset,)
        ).fetchone()
        if not row:
            break

        zb = zb_validate(row["email"])
        if zb:
            score = zb.get("score") or 0
            db.execute(
                "UPDATE churches SET zb_confidence = ?, email_validated = ? WHERE id = ?",
                (score, 1 if score >= 0.5 else 0, row["id"])
            )
            validated += 1

        if (offset + 1) % 10 == 0:
            db.commit()
            log(f"    Validated: {validated:,} / {total:,}")
        time.sleep(0.2)  # Rate limit

    db.commit()
    log(f"  Total validated: {validated:,}")
    db.close()


# ── Step 6: Phone Normalization ───────────────────────────────────

def step_phones():
    """Normalize phone numbers to E.164 format and set confidence."""
    log("Step 6: Phone normalization")
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    total = db.execute("SELECT COUNT(*) FROM churches WHERE phone IS NOT NULL AND phone != ''").fetchone()[0]
    cleaned = 0
    rejected = 0
    for offset in range(0, total, BATCH_SIZE):
        rows = db.execute(
            "SELECT id, phone FROM churches WHERE phone IS NOT NULL AND phone != '' LIMIT ? OFFSET ?",
            (BATCH_SIZE, offset)
        ).fetchall()
        for row in rows:
            normalized = normalize_phone(row["phone"])
            if normalized:
                old = row["phone"]
                db.execute(
                    "UPDATE churches SET phone = ?, phone_confidence = 1.0, phone_last_verified = ? WHERE id = ?",
                    (normalized, now, row["id"])
                )
                log_change(db, row["id"], "phone", old, normalized, "e164_normalize")
                log_change(db, row["id"], "phone_confidence", "0.5", "1.0", "e164_normalize")
                cleaned += 1
            else:
                db.execute(
                    "UPDATE churches SET phone_confidence = 0.3, phone_last_verified = ? WHERE id = ?",
                    (now, row["id"])
                )
                rejected += 1
        db.commit()

    log(f"  Normalized {cleaned:,} / rejected {rejected:,} phone numbers")


# ── Step 7: Confidence Scoring ────────────────────────────────────

def step_confidence():
    """Set per-field confidence scores based on source provenance."""
    log("Step 7: Confidence scoring")
    db = get_db()
    now = datetime.utcnow().isoformat()

    # Website confidence: based on source and SSL validity
    log("  Scoring websites...")
    db.execute("""
        UPDATE churches SET
            website_confidence = CASE
                WHEN website IS NOT NULL AND website != '' THEN 0.7
                WHEN website IS NOT NULL THEN 0.3
                ELSE NULL
            END,
            website_last_verified = CASE
                WHEN website IS NOT NULL AND website != '' THEN ?
                ELSE website_last_verified
            END
        WHERE website_confidence IS NULL
    """, (now,))
    db.commit()
    log(f"    {db.execute('SELECT COUNT(*) FROM churches WHERE website_confidence IS NOT NULL').fetchone()[0]:,} scored")

    # Email confidence: use zb_confidence if available, else heuristic
    log("  Scoring emails...")
    db.execute("""
        UPDATE churches SET
            email_confidence = CASE
                WHEN zb_confidence IS NOT NULL AND zb_confidence > 0 THEN zb_confidence
                WHEN email IS NOT NULL AND email != '' THEN 0.5
                ELSE NULL
            END,
            email_last_verified = CASE
                WHEN email IS NOT NULL AND email != '' THEN ?
                ELSE email_last_verified
            END
        WHERE email_confidence IS NULL
    """, (now,))
    db.commit()
    log(f"    {db.execute('SELECT COUNT(*) FROM churches WHERE email_confidence IS NOT NULL').fetchone()[0]:,} scored")

    # Geocode confidence: based on source precision
    log("  Scoring geocodes...")
    db.execute("""
        UPDATE churches SET
            geocode_confidence = CASE
                WHEN geocode_source = 'census_street' THEN 0.95
                WHEN geocode_source = 'zip_centroid' THEN 0.6
                WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 0.3
                ELSE NULL
            END,
            geocode_last_verified = CASE
                WHEN latitude IS NOT NULL THEN ?
                ELSE geocode_last_verified
            END
        WHERE geocode_confidence IS NULL
    """, (now,))
    db.commit()
    log(f"    {db.execute('SELECT COUNT(*) FROM churches WHERE geocode_confidence IS NOT NULL').fetchone()[0]:,} scored")

    # Bump enrichment_version
    db.execute("UPDATE churches SET enrichment_version = COALESCE(enrichment_version, 0) + 1")
    db.commit()
    ver = db.execute("SELECT DISTINCT enrichment_version FROM churches LIMIT 1").fetchone()[0]
    log(f"  enrichment_version incremented to {ver}")
    db.close()


# ── Step 8: Data Sanity (email-state mismatch cleanup) ────────────

CITY_STATE_MAP = {
    "orlando": "FL", "columbus": "OH", "wichita": "KS",
    "chicago": "IL", "newyork": "NY", "losangeles": "CA",
    "dallas": "TX", "houston": "TX", "phoenix": "AZ",
    "philadelphia": "PA", "sanantonio": "TX", "sandiego": "CA",
    "seattle": "WA", "denver": "CO", "boston": "MA",
    "nashville": "TN", "portland": "OR", "memphis": "TN",
    "atlanta": "GA", "miami": "FL", "tampa": "FL",
    "jacksonville": "FL", "indianapolis": "IN",
    "springfield": "IL", "sacramento": "CA",
    "birmingham": "AL", "charlotte": "NC", "raleigh": "NC",
    "richmond": "VA", "austin": "TX", "elpaso": "TX",
    "fortworth": "TX", "detroit": "MI", "minneapolis": "MN",
    "stlouis": "MO", "kansascity": "MO", "omaha": "NE",
    "tulsa": "OK", "pittsburgh": "PA", "baltimore": "MD",
    "neworleans": "LA", "louisville": "KY", "albany": "NY",
    "buffalo": "NY", "rochester": "NY", "columbia": "SC",
    "charleston": "SC", "greenville": "SC",
}

def step_sanity():
    """
    Check email domains against church state for obvious mismatches.
    If an email domain contains a major city name that doesn't match
    the church's state, clear the email (it's cross-contaminated data).
    """
    log("Step 8: Email-state sanity check")
    db = get_db()
    
    rows = db.execute("SELECT id, name, city, state, email FROM churches WHERE email IS NOT NULL AND email != ''").fetchall()
    log(f"  Checking {len(rows):,} emails for state mismatches...")
    
    cleared = 0
    for r in rows:
        email_domain = r[4].split('@')[1].lower() if '@' in r[4] else ''
        church_state = r[3]
        if not church_state or not email_domain:
            continue
        for city, expected_state in CITY_STATE_MAP.items():
            if city in email_domain and church_state != expected_state:
                db.execute("UPDATE churches SET email = '', email_confidence = NULL, zb_confidence = NULL WHERE id = ?", (r[0],))
                log_change(db, r[0], "email", r[4], "", f"sanity_clean_{city}_{expected_state}")
                cleared += 1
                break
    
    db.commit()
    log(f"  Cleared {cleared} mismatched emails")
    db.close()

def main():
    import argparse
    parser = argparse.ArgumentParser(description="GrantWizard Enrichment Pipeline")
    parser.add_argument("--step", type=str, default="all",
                        choices=["all", "schema", "normalize", "classify", "kg", "zerobounce", "phones", "confidence", "spanish", "sanity"])
    args = parser.parse_args()

    steps = {
        "schema": step_schema,
        "normalize": step_normalize,
        "classify": step_classify,
        "kg": step_kg,
        "zerobounce": step_zerobounce,
        "phones": step_phones,
        "confidence": step_confidence,
        "spanish": step_spanish,
        "sanity": step_sanity,
    }

    if args.step == "all":
        log("Running full enrichment pipeline")
        for name, func in steps.items():
            log(f"\n{'='*60}")
            func()
            log(f"{'='*60}\n")
    else:
        steps[args.step]()

    log("Pipeline complete")


if __name__ == "__main__":
    main()
