"""
gw_db — Provenance-Aware SQLite Access for GrantWizard
=======================================================
Drop-in replacement for sqlite3.connect() that auto-logs provenance.
Every script that touches churches.db should import from here.

Usage — simplest (drop-in replacement):
    from gw_db import connect
    conn = connect()                 # auto-finds churches.db
    conn = connect("churches.db")    # explicit path
    conn = connect(timeout=30)       # passes through to sqlite3.connect

Usage — with provenance tracking:
    from gw_db import connect, Provenance

    with Provenance(conn, "my_script.py", source="irs",
                    action="enriched", fields="denomination,family"):
        c = conn.cursor()
        c.execute("UPDATE churches SET denomination=? WHERE id=?", ...)
        # Auto-logged on exit — no manual INSERT needed

Usage — per-change logging:
    from gw_db import log_change
    log_change(conn, church_id=12345, field="phone",
               old_value="555-0000", new_value="555-1234",
               source="e164_normalize")

What gets logged automatically:
    provenance_log   — one row per run (script, timestamps, counts, status)
    enrichment_change_log — per-field changes when using log_change()
"""

import sqlite3
import os
import sys
import time
import traceback
from datetime import datetime, timezone

# ── Schema: Column → Enrichment Table Mapping (2026-07-29) ──
# After the schema split, enrichment columns live in join tables, not in `churches`.
# Use this to route UPDATE/SELECT to the correct table.

ENRICHMENT_COLUMNS = {
    # church_location (addresses, admin boundaries, GPS supplements)
    "address": "church_location",
    "address_source": "church_location",
    "geocode_source": "church_location",
    "city": "church_location",
    "state": "church_location",
    "county": "church_location",
    "county_fips_5": "church_location",
    "fips": "church_location",
    "zip": "church_location",
    "zip5": "church_location",
    "zip4": "church_location",
    "country": "church_location",
    "continent": "church_location",
    "region_un": "church_location",
    "subregion": "church_location",
    "admin0_code": "church_location",
    "admin0_name": "church_location",
    "admin1_code": "church_location",
    "admin1_name": "church_location",
    "admin2_code": "church_location",
    "admin2_name": "church_location",
    "admin3_code": "church_location",
    "admin3_name": "church_location",
    "admin4_code": "church_location",
    "admin4_name": "church_location",
    "admin5_code": "church_location",
    "admin5_name": "church_location",
    # church_infrastructure (distances to amenities)
    "nearest_fire_km": "church_infrastructure",
    "nearest_police_km": "church_infrastructure",
    "security_updated": "church_infrastructure",
    "nearest_hospital_km": "church_infrastructure",
    "nearest_clinic_km": "church_infrastructure",
    "healthcare_updated": "church_infrastructure",
    "nearest_school_km": "church_infrastructure",
    "nearest_cemetery_km": "church_infrastructure",
    "nearest_mosque_km": "church_infrastructure",
    "nearest_synagogue_km": "church_infrastructure",
    "nearest_hindu_temple_km": "church_infrastructure",
    "nearest_buddhist_temple_km": "church_infrastructure",
    "nearest_sikh_gurdwara_km": "church_infrastructure",
    "nearest_other_faith_km": "church_infrastructure",
    "same_faith_count_1km": "church_infrastructure",
    "same_faith_count_5km": "church_infrastructure",
    "same_faith_count_10km": "church_infrastructure",
    "nearest_same_tradition_km": "church_infrastructure",
    "same_tradition_count_5km": "church_infrastructure",
    "interfaith_updated": "church_infrastructure",
    # church_environment (natural environment, population catchments)
    "elevation_m": "church_environment",
    "nearest_coast_km": "church_environment",
    "nearest_city_km": "church_environment",
    "flood_zone": "church_environment",
    "flood_risk_score": "church_environment",
    "pop_05km": "church_environment",
    "pop_10km": "church_environment",
    "pop_15km": "church_environment",
    "pop_20km": "church_environment",
    "pop_30km": "church_environment",
    "catchment_updated": "church_environment",
    "grid_source": "church_environment",
    "grid_import_date": "church_environment",
    # church_property (buildings, land, valuation)
    "building_sqft": "church_property",
    "parking_spots": "church_property",
    "capacity_estimate": "church_property",
    "building_source": "church_property",
    "building_year": "church_property",
    "closed_year": "church_property",
    "fl_parcel_id": "church_property",
    "fl_dor_uc": "church_property",
    "fl_market_value": "church_property",
    "fl_building_sqft": "church_property",
    "fl_year_built": "church_property",
    "tn_parcel_id": "church_property",
    "treasury_value": "church_property",
    "assessment_value": "church_property",
    "sale_price": "church_property",
    # church_census (government/regulatory data)
    "cra_bn": "church_census",
    "cra_category": "church_census",
    "cra_sub_category": "church_census",
    "cra_designation": "church_census",
    "mapping_saints_id": "church_census",
    "mapping_saints_place_type": "church_census",
    "mapping_saints_diocese": "church_census",
    "mapping_saints_saints": "church_census",
    "mapping_saints_bebr": "church_census",
    "mapping_saints_fmis": "church_census",
    "mapping_saints_matched": "church_census",
    "mapping_saints_updated": "church_census",
    "mapping_saints_wikidata": "church_census",
    "ntee_code": "church_census",
}

# Columns still on the core `churches` table
CORE_COLUMNS = {
    "id", "name", "normalized_name", "name_original", "name_transliterated",
    "name_english", "faith", "tradition", "legacy", "movement",
    "civilizational_family", "taxonomy_id",
    "faith_id", "culture_id", "legacy_id", "tradition_id", "movement_id",
    "latitude", "longitude", "source", "confidence_score",
    "landmark_type", "is_landmark", "last_updated", "notes",
    "christ_class_confidence", "christ_class_source", "christ_class_date",
    "bh_confidence", "bh_classification_source", "bh_updated",
    "shinto_confidence", "shinto_classification_source", "shinto_updated",
}


def get_table_for_column(col_name):
    """Return the enrichment table name for a column, or 'churches' if core."""
    if col_name.lower() in ENRICHMENT_COLUMNS:
        return ENRICHMENT_COLUMNS[col_name.lower()]
    return "churches"


# ── DB_PATH resolution ──
def _find_db():
    """Find churches.db relative to project root."""
    # Try common locations
    candidates = [
        os.path.join(os.path.dirname(__file__), '..', 'churches.db'),
        'churches.db',
        'E:/grid/churches.db',
    ]
    for p in candidates:
        p = os.path.abspath(p)
        if os.path.exists(p):
            return p
    # Fallback: return the most likely path even if it doesn't exist yet
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'churches.db'))

DB_PATH = _find_db()

# ── Wrapped Connection ──
class Connection:
    """sqlite3.Connection wrapper that tracks operations for provenance."""

    def __init__(self, conn, db_path):
        self._conn = conn
        self.db_path = db_path
        self.row_factory = conn.row_factory

    # Delegate everything to the underlying connection
    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def execute(self, *args, **kwargs):
        return self._conn.execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        return self._conn.executemany(*args, **kwargs)

    def executescript(self, *args, **kwargs):
        return self._conn.executescript(*args, **kwargs)

    def create_function(self, *args, **kwargs):
        return self._conn.create_function(*args, **kwargs)

    def create_aggregate(self, *args, **kwargs):
        return self._conn.create_aggregate(*args, **kwargs)

    def set_trace_callback(self, *args, **kwargs):
        return self._conn.set_trace_callback(*args, **kwargs)

    def set_progress_handler(self, *args, **kwargs):
        return self._conn.set_progress_handler(*args, **kwargs)

    def enable_load_extension(self, *args, **kwargs):
        return self._conn.enable_load_extension(*args, **kwargs)

    def load_extension(self, *args, **kwargs):
        return self._conn.load_extension(*args, **kwargs)

    def iterdump(self, *args, **kwargs):
        return self._conn.iterdump(*args, **kwargs)

    def backup(self, *args, **kwargs):
        return self._conn.backup(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        self._conn.close()
        return False

    def __getattr__(self, name):
        return getattr(self._conn, name)


def connect(db_path=None, **kwargs):
    """
    Connect to churches.db with provenance-aware wrapper.

    Args:
        db_path: Path to SQLite DB. Defaults to project's churches.db.
        **kwargs: Passed through to sqlite3.connect (timeout, etc.)

    Returns:
        Connection wrapper (drop-in for sqlite3.Connection)
    """
    if db_path is None:
        db_path = DB_PATH
    kwargs.setdefault('timeout', 30)
    raw = sqlite3.connect(db_path, **kwargs)
    # Enable WAL mode for better concurrency
    raw.execute("PRAGMA journal_mode=WAL")
    raw.execute("PRAGMA busy_timeout=30000")
    return Connection(raw, db_path)


# ── Provenance Context Manager ──
class Provenance:
    """
    Context manager that auto-logs a provenance_log entry.

    Usage:
        with Provenance(conn, "my_script.py", source="irs",
                        action="enriched", fields="denomination"):
            # do work...
        # provenance_log INSERT happens automatically on exit
    """

    def __init__(self, conn, script_name=None, source=None,
                 action="updated", fields=None, params=None,
                 records_attempted=0):
        self.conn = conn
        self.script_name = script_name or _caller_script()
        self.source = source or "unknown"
        self.action = action
        self.fields = fields
        self.params = params
        self.records_attempted = records_attempted
        self.start_time = None
        self.churches_updated = 0
        self.churches_inserted = 0
        self.records_matched = 0
        self.status = "started"
        self.error_msg = None

    def __enter__(self):
        self.start_time = datetime.now(timezone.utc).isoformat()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = datetime.now(timezone.utc).isoformat()
        if exc_type is not None:
            self.status = "failed"
            self.error_msg = f"{exc_type.__name__}: {exc_val}"
        else:
            self.status = "completed"

        _insert_provenance_log(
            self.conn,
            source=self.source,
            script_name=self.script_name,
            started_at=self.start_time,
            completed_at=end_time,
            churches_updated=self.churches_updated,
            churches_inserted=self.churches_inserted,
            fields_populated=self.fields,
            parameters=self.params,
            records_attempted=self.records_attempted,
            records_matched=self.records_matched,
            status=self.status,
            error=self.error_msg,
        )
        return False  # Don't suppress exceptions


# ── Per-Change Logging ──
def log_change(conn, church_id, field_name, old_value=None, new_value=None,
               source="unknown", enrichment_version=None):
    """
    Record a single field change in enrichment_change_log.

    Usage:
        log_change(conn, 12345, "phone", old_value="555-0000",
                   new_value="555-1234", source="e164_normalize")
    """
    c = conn.cursor()
    c.execute("""
        INSERT INTO enrichment_change_log
            (church_id, field_name, old_value, new_value,
             change_source, enrichment_version, changed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        church_id, field_name,
        str(old_value) if old_value is not None else None,
        str(new_value) if new_value is not None else None,
        source, enrichment_version,
        datetime.now(timezone.utc).isoformat()
    ))


def log_changes_batch(conn, changes, source="unknown", enrichment_version=None):
    """
    Record multiple field changes in enrichment_change_log efficiently.

    Args:
        conn: gw_db.Connection
        changes: list of (church_id, field_name, old_value, new_value) tuples
        source: change source identifier
    """
    c = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    c.executemany("""
        INSERT INTO enrichment_change_log
            (church_id, field_name, old_value, new_value,
             change_source, enrichment_version, changed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        (ch_id, field, str(old) if old is not None else None,
         str(new) if new is not None else None,
         source, enrichment_version, now)
        for ch_id, field, old, new in changes
    ])


# ── Source Registry ──
def register_source(conn, name, source_type, description=None, url=None,
                    refreshable=False, refresh_url=None, refresh_type=None,
                    refresh_freq=None):
    """Register a data source in the sources table (idempotent)."""
    c = conn.cursor()
    c.execute("SELECT id FROM sources WHERE name=?", (name,))
    existing = c.fetchone()
    if existing:
        return existing[0]
    c.execute("""
        INSERT INTO sources (name, source_type, description, url,
                            refreshable, refresh_url, refresh_type, refresh_freq,
                            created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, source_type, description, url,
          int(refreshable), refresh_url, refresh_type, refresh_freq,
          datetime.now(timezone.utc).isoformat()))
    return c.lastrowid


# ── Internal Helpers ──
def _caller_script():
    """Heuristic to find the calling script's filename."""
    frame = sys._getframe(3)  # Provenance.__init__ → __enter__ → caller
    fname = frame.f_code.co_filename
    return os.path.basename(fname) if fname else "unknown"


def _insert_provenance_log(conn, source, script_name, started_at, completed_at,
                           churches_updated, churches_inserted, fields_populated,
                           parameters, records_attempted, records_matched,
                           status, error):
    """Insert a row into provenance_log. Does NOT commit (caller should)."""
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO provenance_log
                (source, script_name, started_at, completed_at,
                 churches_updated, churches_inserted, fields_populated,
                 parameters, records_attempted, records_matched,
                 status, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            source, script_name, started_at, completed_at,
            churches_updated, churches_inserted, fields_populated,
            parameters, records_attempted, records_matched,
            status, error,
        ))
    except sqlite3.OperationalError:
        # Table might not exist yet — non-fatal
        pass


# ── Convenience: ensure provenance tables exist ──
def ensure_provenance_tables(conn):
    """Create provenance_log and enrichment_change_log if they don't exist."""
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS provenance_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            script_name TEXT,
            started_at TEXT,
            completed_at TEXT,
            churches_updated INTEGER DEFAULT 0,
            churches_inserted INTEGER DEFAULT 0,
            fields_populated TEXT,
            parameters TEXT,
            records_attempted INTEGER DEFAULT 0,
            records_matched INTEGER DEFAULT 0,
            status TEXT,
            notes TEXT,
            error TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS enrichment_change_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            church_id INTEGER,
            field_name TEXT,
            old_value TEXT,
            new_value TEXT,
            change_source TEXT,
            enrichment_version INTEGER,
            changed_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            source_type TEXT,
            description TEXT,
            url TEXT,
            scrape_date TEXT,
            record_count INTEGER,
            created_at TEXT,
            notes TEXT,
            refreshable INTEGER DEFAULT 0,
            refresh_url TEXT,
            refresh_type TEXT,
            refresh_freq TEXT,
            last_success TEXT,
            next_scheduled TEXT,
            update_url TEXT
        )
    """)
