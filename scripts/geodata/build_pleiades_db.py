"""
Build standalone Pleiades reference database from CSV data dump.

Pleiades is a gazetteer of ancient places (CC BY 3.0). This script creates
a normalized SQLite database (~50K places, ~29K point locations, ~45K names,
~15K connections, ~5.7K linestrings, ~4.4K polygons) for spatial queries
independent of the main churches.db.

Source: data/pleiades/data/gis/pleiades_gis_data.zip (extracted CSVs)
Output: data/pleiades/pleiades.db

Usage:
    .venv\Scripts\python.exe scripts\geodata\build_pleiades_db.py

Tables:
    places             — 49,473 places (id, title, lat, lon, bbox, precision)
    names              — 45,255 ancient/modern names linked to places
    location_points    — 28,989 point locations with WKT geometry
    location_polygons  — 4,433 polygon locations with WKT geometry
    location_linestrings — 5,731 linestring locations with WKT geometry
    connections        — 14,797 connections between places
    places_place_types — 52,400 place→type mappings
    places_accuracy    — 42,170 accuracy assessments
    place_types        — 233 place type vocabulary
    connection_types   — 43 connection type vocabulary
    archaeological_remains — 7 archaeological remains vocabulary
    association_certainty  — 3 association certainty vocabulary
    name_types         — 6 name type vocabulary
    languages_and_scripts  — 129 language/script codes
    transcription_accuracy    — 3 transcription accuracy vocabulary
    transcription_completeness — 3 transcription completeness vocabulary
    time_periods       — 220 time period definitions
    location_rtree     — R-tree spatial index on location_points
"""

import csv
import os
import sqlite3
import sys
import time
from pathlib import Path

# ── Config ──
DATA_DIR = Path(r'E:\grid\data\pleiades\data\gis')
DB_PATH = Path(r'E:\grid\data\pleiades\pleiades.db')
CHUNK_SIZE = 2000
BATCH_COMMIT = 10000


def progress_bar(current, total, label="", width=50):
    """Draw a progress bar. Returns nothing — prints to stderr."""
    pct = current / total if total > 0 else 1.0
    filled = int(width * pct)
    bar = '█' * filled + '░' * (width - filled)
    sys.stderr.write(f'\r  {label} [{bar}] {current:,}/{total:,} ({pct*100:.1f}%)')
    sys.stderr.flush()


def load_csv(path):
    """Load a CSV file and return list of dicts."""
    with open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def create_tables(db):
    """Create all tables with appropriate schemas."""
    
    # ── Vocabulary tables ──
    db.executescript("""
        CREATE TABLE IF NOT EXISTS place_types (
            key TEXT PRIMARY KEY,
            term TEXT NOT NULL,
            definition TEXT,
            same_as TEXT,
            uri TEXT
        );
        
        CREATE TABLE IF NOT EXISTS connection_types (
            key TEXT PRIMARY KEY,
            term TEXT NOT NULL,
            definition TEXT,
            same_as TEXT,
            uri TEXT
        );
        
        CREATE TABLE IF NOT EXISTS archaeological_remains (
            key TEXT PRIMARY KEY,
            term TEXT NOT NULL,
            definition TEXT,
            same_as TEXT,
            uri TEXT
        );
        
        CREATE TABLE IF NOT EXISTS association_certainty (
            key TEXT PRIMARY KEY,
            term TEXT NOT NULL,
            definition TEXT,
            same_as TEXT,
            uri TEXT
        );
        
        CREATE TABLE IF NOT EXISTS name_types (
            key TEXT PRIMARY KEY,
            term TEXT NOT NULL,
            definition TEXT,
            same_as TEXT,
            uri TEXT
        );
        
        CREATE TABLE IF NOT EXISTS languages_and_scripts (
            key TEXT PRIMARY KEY,
            term TEXT NOT NULL,
            definition TEXT,
            same_as TEXT,
            uri TEXT
        );
        
        CREATE TABLE IF NOT EXISTS transcription_accuracy (
            key TEXT PRIMARY KEY,
            term TEXT NOT NULL,
            definition TEXT,
            same_as TEXT,
            uri TEXT
        );
        
        CREATE TABLE IF NOT EXISTS transcription_completeness (
            key TEXT PRIMARY KEY,
            term TEXT NOT NULL,
            definition TEXT,
            same_as TEXT,
            uri TEXT
        );
        
        CREATE TABLE IF NOT EXISTS time_periods (
            key TEXT PRIMARY KEY,
            term TEXT NOT NULL,
            definition TEXT,
            lower_bound INTEGER,
            upper_bound INTEGER,
            same_as TEXT
        );
    """)
    
    # ── Main data tables ──
    db.executescript("""
        CREATE TABLE IF NOT EXISTS places (
            id TEXT PRIMARY KEY,
            created TEXT,
            title TEXT NOT NULL,
            description TEXT,
            details TEXT,
            provenance TEXT,
            uri TEXT,
            representative_latitude REAL,
            representative_longitude REAL,
            bounding_box_wkt TEXT,
            location_precision TEXT
        );
        
        CREATE TABLE IF NOT EXISTS names (
            id TEXT PRIMARY KEY,
            created TEXT,
            description TEXT,
            details TEXT,
            provenance TEXT,
            title TEXT,
            uri TEXT,
            place_id TEXT NOT NULL REFERENCES places(id),
            name_type TEXT,
            language_tag TEXT,
            attested_form TEXT,
            romanized_form_1 TEXT,
            romanized_form_2 TEXT,
            romanized_form_3 TEXT,
            association_certainty TEXT,
            transcription_accuracy TEXT,
            transcription_completeness TEXT,
            year_after_which INTEGER,
            year_before_which INTEGER
        );
        
        CREATE TABLE IF NOT EXISTS location_points (
            id TEXT PRIMARY KEY,
            created TEXT,
            description TEXT,
            details TEXT,
            provenance TEXT,
            title TEXT,
            uri TEXT,
            place_id TEXT NOT NULL REFERENCES places(id),
            accuracy_assessment_uri TEXT,
            accuracy_radius REAL,
            archaeological_remains TEXT,
            association_certainty TEXT,
            geometry_wkt TEXT NOT NULL,
            year_after_which INTEGER,
            year_before_which INTEGER,
            location_precision TEXT,
            -- Extracted lat/lon for spatial queries
            longitude REAL,
            latitude REAL
        );
        
        CREATE TABLE IF NOT EXISTS location_polygons (
            id TEXT PRIMARY KEY,
            created TEXT,
            description TEXT,
            details TEXT,
            provenance TEXT,
            title TEXT,
            uri TEXT,
            place_id TEXT NOT NULL REFERENCES places(id),
            accuracy_assessment_uri TEXT,
            accuracy_radius REAL,
            archaeological_remains TEXT,
            association_certainty TEXT,
            geometry_wkt TEXT NOT NULL,
            year_after_which INTEGER,
            year_before_which INTEGER,
            location_precision TEXT
        );
        
        CREATE TABLE IF NOT EXISTS location_linestrings (
            id TEXT PRIMARY KEY,
            created TEXT,
            description TEXT,
            details TEXT,
            provenance TEXT,
            title TEXT,
            uri TEXT,
            place_id TEXT NOT NULL REFERENCES places(id),
            accuracy_assessment_uri TEXT,
            accuracy_radius REAL,
            archaeological_remains TEXT,
            association_certainty TEXT,
            geometry_wkt TEXT NOT NULL,
            year_after_which INTEGER,
            year_before_which INTEGER,
            location_precision TEXT
        );
        
        CREATE TABLE IF NOT EXISTS connections (
            id TEXT PRIMARY KEY,
            created TEXT,
            description TEXT,
            details TEXT,
            provenance TEXT,
            title TEXT,
            uri TEXT,
            place_id TEXT NOT NULL REFERENCES places(id),
            connection_type TEXT NOT NULL,
            connects_to TEXT NOT NULL,
            association_certainty TEXT,
            year_after_which INTEGER,
            year_before_which INTEGER
        );
        
        CREATE TABLE IF NOT EXISTS places_place_types (
            place_id TEXT NOT NULL REFERENCES places(id),
            place_type TEXT NOT NULL,
            PRIMARY KEY (place_id, place_type)
        );
        
        CREATE TABLE IF NOT EXISTS places_accuracy (
            place_id TEXT PRIMARY KEY REFERENCES places(id),
            title TEXT,
            uri TEXT,
            location_precision TEXT,
            accuracy_hull TEXT,
            max_accuracy_meters REAL,
            min_accuracy_meters REAL,
            accuracy_bases TEXT,
            location_types TEXT
        );
    """)
    
    # ── Spatial index ──
    db.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS location_rtree USING rtree(
            id,              -- integer PK for rtree
            min_lon, max_lon,
            min_lat, max_lat
        );
    """)


def bulk_insert(db, table_name, rows, column_map=None):
    """
    Bulk insert rows into table. column_map maps CSV column names → DB column names.
    If column_map is None, uses all CSV columns as-is.
    """
    if not rows:
        return 0
    
    if column_map is None:
        columns = list(rows[0].keys())
        col_names = columns
    else:
        columns = list(column_map.keys())
        col_names = [column_map[c] for c in columns]
    
    placeholders = ','.join(['?' for _ in columns])
    col_list = ','.join(col_names)
    sql = f'INSERT OR IGNORE INTO {table_name} ({col_list}) VALUES ({placeholders})'
    
    total = len(rows)
    batch = []
    inserted = 0
    
    for i, row in enumerate(rows):
        values = [row.get(c, None) for c in columns]
        batch.append(values)
        
        if len(batch) >= CHUNK_SIZE:
            db.executemany(sql, batch)
            inserted += len(batch)
            batch = []
            if i % BATCH_COMMIT == 0:
                db.commit()
                progress_bar(i, total, f"  {table_name}")
    
    if batch:
        db.executemany(sql, batch)
        inserted += len(batch)
    
    progress_bar(total, total, f"  {table_name}")
    sys.stderr.write('\n')
    db.commit()
    return inserted


def extract_point_coords(wkt):
    """Extract lat/lon from POINT (lon lat) WKT."""
    if not wkt:
        return None, None
    wkt = wkt.strip()
    if wkt.startswith('POINT ('):
        inner = wkt[7:-1]
        parts = inner.split()
        if len(parts) >= 2:
            return float(parts[0]), float(parts[1])
    elif wkt.startswith('POINT('):
        inner = wkt[6:-1]
        parts = inner.split()
        if len(parts) >= 2:
            return float(parts[0]), float(parts[1])
    return None, None


def build_spatial_index(db):
    """Build R-tree spatial index from location_points."""
    print("\n  Building spatial index on location_points...")
    
    db.execute("DELETE FROM location_rtree")
    
    rows = db.execute("""
        SELECT rowid, longitude, latitude FROM location_points
        WHERE longitude IS NOT NULL AND latitude IS NOT NULL
    """).fetchall()
    
    total = len(rows)
    batch = []
    
    for i, (rowid, lon, lat) in enumerate(rows):
        batch.append((rowid, lon, lon, lat, lat))
        if len(batch) >= CHUNK_SIZE:
            db.executemany(
                "INSERT INTO location_rtree VALUES (?, ?, ?, ?, ?)",
                batch
            )
            batch = []
            if i % BATCH_COMMIT == 0:
                db.commit()
                progress_bar(i, total, "  spatial_index")
    
    if batch:
        db.executemany(
            "INSERT INTO location_rtree VALUES (?, ?, ?, ?, ?)",
            batch
        )
    
    progress_bar(total, total, "  spatial_index")
    sys.stderr.write('\n')
    db.commit()
    print(f"  {total:,} points indexed")


def create_indices(db):
    """Create secondary indices for common JOIN patterns."""
    print("\n  Creating indices...")
    indices = [
        ("idx_names_place", "names(place_id)"),
        ("idx_names_language", "names(language_tag)"),
        ("idx_names_attested", "names(attested_form)"),
        ("idx_names_romanized", "names(romanized_form_1)"),
        ("idx_location_points_place", "location_points(place_id)"),
        ("idx_location_polygons_place", "location_polygons(place_id)"),
        ("idx_location_linestrings_place", "location_linestrings(place_id)"),
        ("idx_connections_place", "connections(place_id)"),
        ("idx_connections_connects_to", "connections(connects_to)"),
        ("idx_connections_type", "connections(connection_type)"),
        ("idx_places_place_types_type", "places_place_types(place_type)"),
        ("idx_places_lat_lon", "places(representative_latitude, representative_longitude)"),
        ("idx_places_precision", "places(location_precision)"),
        ("idx_location_points_coords", "location_points(latitude, longitude)"),
    ]
    
    for name, definition in indices:
        try:
            db.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {definition}")
        except sqlite3.OperationalError as e:
            print(f"  ⚠ {name}: {e}")
    
    print(f"  {len(indices)} indices created")
    db.commit()


def main():
    start = time.time()
    
    # Verify data exists
    if not DATA_DIR.exists():
        print(f"ERROR: Data directory not found: {DATA_DIR}")
        print("Download pleiades_gis_data.zip from https://pleiades.stoa.org/downloads")
        sys.exit(1)
    
    places_csv = DATA_DIR / 'places.csv'
    if not places_csv.exists():
        print(f"ERROR: places.csv not found in {DATA_DIR}")
        sys.exit(1)
    
    # ── Create DB ──
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Remove old DB if exists
    if DB_PATH.exists():
        print(f"Removing existing database: {DB_PATH}")
        DB_PATH.unlink()
    
    print(f"Creating Pleiades database: {DB_PATH}")
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute("PRAGMA cache_size=-64000")  # 64 MB cache
    db.execute("PRAGMA foreign_keys=ON")
    
    # ── Create schema ──
    print("\n=== Step 1: Create schema ===")
    create_tables(db)
    db.commit()
    print("  Done")
    
    # ── Import vocabulary tables ──
    print("\n=== Step 2: Import vocabulary tables ===")
    vocab_tables = [
        'place_types', 'connection_types', 'archaeological_remains',
        'association_certainty', 'name_types', 'languages_and_scripts',
        'transcription_accuracy', 'transcription_completeness', 'time_periods'
    ]
    
    for table in vocab_tables:
        csv_path = DATA_DIR / f'{table}.csv'
        if csv_path.exists():
            rows = load_csv(csv_path)
            n = bulk_insert(db, table, rows)
            print(f"  {table}: {n} rows")
    
    db.commit()
    
    # ── Import places ──
    print("\n=== Step 3: Import places (49,473 rows) ===")
    rows = load_csv(DATA_DIR / 'places.csv')
    n = bulk_insert(db, 'places', rows)
    print(f"  places: {n} rows")
    
    # ── Import names ──
    print("\n=== Step 4: Import names (45,255 rows) ===")
    rows = load_csv(DATA_DIR / 'names.csv')
    n = bulk_insert(db, 'names', rows)
    print(f"  names: {n} rows")
    
    # ── Import locations ──
    print("\n=== Step 5: Import location_points (28,989 rows) ===")
    rows = load_csv(DATA_DIR / 'location_points.csv')
    
    # Pre-extract lat/lon from WKT for spatial queries
    for r in rows:
        lon, lat = extract_point_coords(r.get('geometry_wkt', ''))
        r['longitude'] = lon
        r['latitude'] = lat
    
    column_map_pts = {c: c for c in rows[0].keys()}
    n = bulk_insert(db, 'location_points', rows, column_map_pts)
    print(f"  location_points: {n} rows")
    
    print("\n  Importing location_polygons (4,433 rows)...")
    rows = load_csv(DATA_DIR / 'location_polygons.csv')
    n = bulk_insert(db, 'location_polygons', rows)
    print(f"  location_polygons: {n} rows")
    
    print("\n  Importing location_linestrings (5,731 rows)...")
    rows = load_csv(DATA_DIR / 'location_linestrings.csv')
    n = bulk_insert(db, 'location_linestrings', rows)
    print(f"  location_linestrings: {n} rows")
    
    # ── Import connections ──
    print("\n=== Step 6: Import connections (14,797 rows) ===")
    rows = load_csv(DATA_DIR / 'connections.csv')
    n = bulk_insert(db, 'connections', rows)
    print(f"  connections: {n} rows")
    
    # ── Import places_place_types ──
    print("\n=== Step 7: Import places_place_types (52,400 rows) ===")
    rows = load_csv(DATA_DIR / 'places_place_types.csv')
    n = bulk_insert(db, 'places_place_types', rows)
    print(f"  places_place_types: {n} rows")
    
    # ── Import places_accuracy ──
    print("\n=== Step 8: Import places_accuracy (42,170 rows) ===")
    rows = load_csv(DATA_DIR / 'places_accuracy.csv')
    n = bulk_insert(db, 'places_accuracy', rows)
    print(f"  places_accuracy: {n} rows")
    
    # ── Build spatial index ──
    print("\n=== Step 9: Build spatial index ===")
    build_spatial_index(db)
    
    # ── Create secondary indices ──
    print("\n=== Step 10: Create secondary indices ===")
    create_indices(db)
    
    # ── Finalize ──
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    db.commit()
    
    elapsed = time.time() - start
    db_size = os.path.getsize(str(DB_PATH)) / 1024 / 1024
    
    # ── Summary ──
    print(f"\n{'='*60}")
    print(f"  Pleiades database built successfully!")
    print(f"  Path: {DB_PATH}")
    print(f"  Size: {db_size:.1f} MB")
    print(f"  Time: {elapsed:.1f}s")
    print(f"{'='*60}")
    
    # Print table stats
    tables = [
        'places', 'names', 'location_points', 'location_polygons',
        'location_linestrings', 'connections', 'places_place_types',
        'places_accuracy', 'place_types', 'connection_types',
        'archaeological_remains', 'association_certainty', 'name_types',
        'languages_and_scripts', 'transcription_accuracy',
        'transcription_completeness', 'time_periods'
    ]
    print(f"\n  Table summary:")
    for t in tables:
        count = db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"    {t:<30} {count:>8,}")
    
    # Sample spatial query
    print(f"\n  Spatial index ready — example queries:")
    print(f"    -- Find places within 50km of Athens (37.9838, 23.7275)")
    print(f"    SELECT p.title, p.id, lp.geometry_wkt")
    print(f"    FROM location_rtree lr")
    print(f"    JOIN location_points lp ON lp.rowid = lr.id")
    print(f"    JOIN places p ON p.id = lp.place_id")
    print(f"    WHERE lr.min_lon >= 23.2275 AND lr.max_lon <= 24.2275")
    print(f"      AND lr.min_lat >= 37.4838 AND lr.max_lat <= 38.4838")
    print(f"    LIMIT 20;")
    
    db.close()


if __name__ == '__main__':
    main()
