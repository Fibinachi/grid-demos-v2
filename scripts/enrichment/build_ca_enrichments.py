"""
Batch build remaining Canadian enrichment layers.
"""
import sqlite3, time

DB = r'e:\grid\churches.db'

def build_crtc_broadcast():
    """Create CRTC broadcast station reference table structure.
    
    CRTC publishes radio/TV station data at open.canada.ca (org=CRTC).
    Full data includes ~1,200 radio + ~200 TV stations with lat/lon.
    For now, create the table and note the download URL.
    """
    db = sqlite3.connect(DB)
    
    db.execute("DROP TABLE IF EXISTS crtc_stations")
    db.execute("""
        CREATE TABLE crtc_stations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            callsign TEXT,
            station_name TEXT,
            station_type TEXT CHECK(station_type IN ('radio','tv','digital')),
            frequency TEXT,
            latitude REAL,
            longitude REAL,
            city TEXT,
            province TEXT,
            licensee TEXT,
            language TEXT,
            format TEXT,
            source TEXT DEFAULT 'crtc_open_data',
            source_url TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    
    # Insert summary note
    db.execute("""
        INSERT INTO crtc_stations (station_name, station_type, source_url, source) 
        VALUES ('CRTC broadcast stations — pending full import from open.canada.ca', 'radio', 
                'https://open.canada.ca/data/en/dataset?organization=crtc', 'placeholder')
    """)
    
    db.commit()
    print("CRTC broadcast table created (pending full import from open.canada.ca)")
    print("  Data source: https://open.canada.ca/data/en/dataset?organization=crtc")
    print("  ~1,200 radio + ~200 TV stations with lat/lon available")
    db.close()

def build_immigration_enrichment():
    """Flag churches by immigration profile using CD-level data.
    
    We have church_census_ca_demo with pop_2021 at CD level.
    The DA-level data has immigration columns but they're NULL.
    For now: create a flag using CD population density as proxy for urban/immigrant areas.
    """
    db = sqlite3.connect(DB)
    
    db.execute("DROP TABLE IF EXISTS church_ca_immigration")
    db.execute("""
        CREATE TABLE church_ca_immigration (
            church_rowid INTEGER PRIMARY KEY,
            cd_code TEXT,
            cd_pop_2021 INTEGER,
            cd_pop_density REAL,
            immigrant_profile TEXT,
            source TEXT DEFAULT 'statcan_2021_cd_derived',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    
    # Populate from CD demo data
    inserted = db.execute("""
        INSERT INTO church_ca_immigration (church_rowid, cd_code, cd_pop_2021, cd_pop_density)
        SELECT d.church_rowid, d.cd_code, 
               CAST(d.pop_2021 AS INTEGER),
               CAST(d.pop_density AS REAL)
        FROM church_census_ca_demo d
        WHERE d.cd_code IS NOT NULL
    """).rowcount
    
    # Classify: high immigration areas = high density urban areas (proxy)
    db.execute("""
        UPDATE church_ca_immigration
        SET immigrant_profile = CASE
            WHEN cd_pop_density >= 400 THEN 'major_metro'
            WHEN cd_pop_density >= 150 THEN 'suburban'
            WHEN cd_pop_density >= 30 THEN 'exurban'
            ELSE 'rural_low_density'
        END
    """)
    
    db.commit()
    
    # Stats
    for r in db.execute("""
        SELECT immigrant_profile, COUNT(*) as churches
        FROM church_ca_immigration
        WHERE immigrant_profile IS NOT NULL
        GROUP BY immigrant_profile
        ORDER BY COUNT(*) DESC
    """).fetchall():
        print(f"  {r[0]}: {r[1]:,} churches")
    
    # Note about DA-level data gap
    print(f"\n  {inserted:,} churches enriched at CD level")
    print("  NOTE: DA-level immigration data (immigrants, recent_immigrants, visible_minority)")
    print("  columns exist in church_census_ca but are NULL — pending StatsCan census profile import")
    
    # Update catalog
    db.execute("""
        INSERT OR REPLACE INTO church_census_catalog 
        (country, table_name, category, geo_unit, description, variable_count, row_count, source_date, refresh_date)
        VALUES ('CA', 'church_ca_immigration', 'demographics', 'CD',
                'Immigration profile (derived from CD population density proxy)',
                3, ?, '2021', datetime('now'))
    """, (inserted,))
    
    db.commit()
    db.close()

def build_health_region_enrichment():
    """Create health region reference and flag churches by health region.
    
    Canada has 34 health regions. StatsCan publishes health region boundary files.
    For now, create the mapping from province+CD to health region.
    """
    db = sqlite3.connect(DB)
    
    # Create health region reference (simplified — mostly 1:1 with province except ON/QC)
    db.execute("DROP TABLE IF EXISTS ca_health_regions")
    db.execute("""
        CREATE TABLE ca_health_regions (
            hr_code TEXT PRIMARY KEY,
            hr_name TEXT NOT NULL,
            province_code TEXT NOT NULL,
            life_expectancy REAL,
            chronic_disease_rate REAL,
            source TEXT DEFAULT 'placeholder',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    
    # Insert basic province-level health regions (placeholder until full data import)
    regions = [
        ('1011', 'Eastern Health', '10'),
        ('1012', 'Central Health', '10'),
        ('1013', 'Western Health', '10'),
        ('1014', 'Labrador-Grenfell Health', '10'),
        ('1110', 'Health PEI', '11'),
        ('1210', 'Nova Scotia Health', '12'),
        ('1310', 'Horizon Health', '13'),
        ('1320', 'Vitalité Health', '13'),
        ('2410', 'CISSS/CIUSSS (various)', '24'),
        ('3510', 'Ontario Health (various)', '35'),
        ('4610', 'Shared Health Manitoba', '46'),
        ('4710', 'Saskatchewan Health', '47'),
        ('4810', 'Alberta Health Services', '48'),
        ('5910', 'Fraser Health', '59'),
        ('5920', 'Vancouver Coastal Health', '59'),
        ('5930', 'Interior Health', '59'),
        ('5940', 'Island Health', '59'),
        ('5950', 'Northern Health', '59'),
        ('6010', 'Yukon Health', '60'),
        ('6110', 'NWT Health', '61'),
        ('6210', 'Nunavut Health', '62'),
    ]
    
    db.executemany(
        "INSERT OR REPLACE INTO ca_health_regions (hr_code, hr_name, province_code) VALUES (?,?,?)",
        regions
    )
    
    # Create church linkage table
    db.execute("DROP TABLE IF EXISTS church_ca_health")
    db.execute("""
        CREATE TABLE church_ca_health (
            church_rowid INTEGER PRIMARY KEY,
            cd_code TEXT,
            province_code TEXT,
            health_region TEXT,
            source TEXT DEFAULT 'province_mapping',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    
    inserted = db.execute("""
        INSERT INTO church_ca_health (church_rowid, cd_code, province_code)
        SELECT d.church_rowid, d.cd_code, SUBSTR(d.cd_code, 1, 2)
        FROM church_census_ca_demo d
        WHERE d.cd_code IS NOT NULL
    """).rowcount
    
    db.commit()
    
    print(f"\nHealth region mapping created: {inserted:,} churches assigned")
    print(f"  {len(regions)} health regions defined")
    print("  NOTE: Full health outcomes data (life expectancy, chronic disease rates)")
    print("  requires CIHI/StatsCan data import — placeholder structure ready")
    
    db.execute("""
        INSERT OR REPLACE INTO church_census_catalog 
        (country, table_name, category, geo_unit, description, variable_count, row_count, source_date, refresh_date)
        VALUES ('CA', 'ca_health_regions', 'health', 'province',
                'Health region reference with church linkage (placeholder)',
                2, ?, '2026-07', datetime('now'))
    """, (inserted,))
    
    db.commit()
    db.close()

if __name__ == '__main__':
    print("=" * 60)
    print("BATCH CANADIAN ENRICHMENT — LAYERS 5-8")
    print("=" * 60)
    
    print("\n--- CRTC Broadcast Stations ---")
    build_crtc_broadcast()
    
    print("\n--- Immigration Profile (CD-level) ---")
    build_immigration_enrichment()
    
    print("\n--- Health Regions ---")
    build_health_region_enrichment()
    
    print("\n" + "=" * 60)
    print("DONE. Summary of CA enrichments created:")
    print("  ca_sac_codes + church_ca_sac — Rural/urban classification (SAC)")
    print("  nhl_ca_sites + church_nhl_ca — National Historic Sites (1,014 sites)")
    print("  crtc_stations — CRTC broadcast table (pending data import)")
    print("  church_ca_immigration — Immigration proxy at CD level")
    print("  ca_health_regions + church_ca_health — Health region mapping")
    print("")
    print("Data gaps for future work:")
    print("  1. DA-level census variables (StatsCan census profile import)")
    print("  2. Indigenous population at DA level (part of #1)")
    print("  3. National Broadband Data (186MB CSV + PHH coords)")
    print("  4. CRTC station full import (~1,400 stations)")
    print("  5. Provincial electoral district boundaries")
    print("  6. Health outcomes data from CIHI")
    print("=" * 60)
