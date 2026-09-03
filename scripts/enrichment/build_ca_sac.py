"""
Build CA rural-urban classification from existing census data.
Canadian equivalent of US RUCC codes.

Uses:
- church_census_ca_demo (CD-level demographics: pop density, population)
- CD name patterns (CTY=county=rural, CDR=census division=urban core, etc.)
- Population density thresholds

Creates:
- ca_sac_codes: reference table with SAC type per CD
- church_ca_sac: bridge table linking churches to SAC classification
"""
import sqlite3, time

DB = r'e:\grid\churches.db'

def build_sac_classification():
    """Build a SAC-like classification from CD data."""
    db = sqlite3.connect(DB)
    
    # Get unique CDs with population density and name info
    cds = db.execute("""
        SELECT DISTINCT cd_code, cd_name, pop_2021, pop_density, land_area_sqkm
        FROM church_census_ca_demo
        WHERE cd_code IS NOT NULL
        ORDER BY cd_code
    """).fetchall()
    
    print(f"Unique CDs: {len(cds)}")
    
    # Classification rules for Canadian rural-urban
    # Based on StatsCan's Statistical Area Classification (SAC) logic:
    # 1 = CMA (Census Metropolitan Area) — urban core >100K
    # 2 = CA (Census Agglomeration) — urban core >10K
    # 3 = Strong MIZ — >30% commute to CMA/CA
    # 4 = Moderate MIZ — 5-30% commute
    # 5 = Weak MIZ — 1-5% commute
    # 6 = No MIZ — <1% commute or no CMA/CA influence
    # 7 = Territories
    
    classifications = []
    
    for cd_code, cd_name, pop_2021, pop_density, land_area in cds:
        # Determine province from CD code (first 2 digits)
        province = cd_code[:2] if cd_code else ''
        
        # Territory provinces: 60=YT, 61=NWT, 62=NU
        if province in ('60', '61', '62'):
            sac_type = '7_territories'
            sac_label = 'Territories'
        elif cd_name:
            name_upper = cd_name.upper()
            
            # Check for CMA indicators in CD name
            # CDR = Census Division (often urbanized, contains CMA)
            # RM = Regional Municipality (metro Toronto, York, etc.)
            # CTY = County (rural)
            # DIS = District (rural, northern)
            # TÉ = Territoire équivalent (QC)
            # MRC = Municipalité régionale de comté (QC, rural)
            # UC = United Counties (rural)
            # DM = District Municipality (BC rural)
            # RD = Regional District (BC)
            
            if any(w in name_upper for w in ['REGIONAL MUNICIPALITY', 'RM)', 'CITY)']):
                sac_type = '1_cma_core'
                sac_label = 'CMA — Urban Core'
            elif any(w in name_upper for w in ['CDR)', 'CENSUS DIVISION']) and pop_density and pop_density > 200:
                sac_type = '1_cma_core'
                sac_label = 'CMA — Urban Core'
            elif pop_density and pop_density > 400:
                sac_type = '1_cma_core'
                sac_label = 'CMA — Urban Core'
            elif pop_density and pop_density > 150:
                sac_type = '2_ca_suburban'
                sac_label = 'CA — Suburban/Fringe'
            elif any(w in name_upper for w in ['DIS)', 'DISTRICT', 'TERRITOIRE']):
                sac_type = '5_weak_miz'
                sac_label = 'Weak/No MIZ — Remote'
            elif pop_density and pop_density > 30:
                sac_type = '3_strong_miz'
                sac_label = 'Strong MIZ — Exurban'
            elif pop_density and pop_density > 10:
                sac_type = '4_moderate_miz'
                sac_label = 'Moderate MIZ — Rural'
            else:
                sac_type = '5_weak_miz'
                sac_label = 'Weak/No MIZ — Remote'
        else:
            if pop_density and pop_density > 400:
                sac_type = '1_cma_core'
                sac_label = 'CMA — Urban Core'
            elif pop_density and pop_density > 30:
                sac_type = '3_strong_miz'
                sac_label = 'Strong MIZ — Exurban'
            else:
                sac_type = '5_weak_miz'
                sac_label = 'Weak/No MIZ — Remote'
        
        classifications.append((cd_code, sac_type, sac_label, pop_density or 0, pop_2021 or 0, land_area or 0))
    
    # Create reference table
    db.execute("DROP TABLE IF EXISTS ca_sac_codes")
    db.execute("""
        CREATE TABLE ca_sac_codes (
            cd_code TEXT PRIMARY KEY,
            sac_type TEXT NOT NULL,
            sac_label TEXT NOT NULL,
            pop_density REAL,
            population_2021 INTEGER,
            land_area_sqkm REAL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    
    db.executemany("INSERT INTO ca_sac_codes VALUES (?,?,?,?,?,?,datetime('now'))", classifications)
    
    # Stats
    print("\nSAC Distribution:")
    for r in db.execute("""
        SELECT sac_type, sac_label, COUNT(*) as cnt, 
               SUM(population_2021) as total_pop
        FROM ca_sac_codes 
        GROUP BY sac_type, sac_label 
        ORDER BY sac_type
    """).fetchall():
        print(f"  {r[0]}: {r[1]} — {r[2]} CDs, {r[3]:,} pop")
    
    db.commit()
    
    # Create church bridge table
    print("\nBuilding church_ca_sac bridge...")
    db.execute("DROP TABLE IF EXISTS church_ca_sac")
    db.execute("""
        CREATE TABLE church_ca_sac (
            church_rowid INTEGER PRIMARY KEY,
            cd_code TEXT,
            sac_type TEXT,
            sac_label TEXT,
            source TEXT DEFAULT 'statcan_2021_cd_derived',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    
    # Join churches to CDs via church_census_ca_demo
    inserted = db.execute("""
        INSERT INTO church_ca_sac (church_rowid, cd_code, sac_type, sac_label)
        SELECT d.church_rowid, d.cd_code, s.sac_type, s.sac_label
        FROM church_census_ca_demo d
        JOIN ca_sac_codes s ON d.cd_code = s.cd_code
        WHERE d.cd_code IS NOT NULL
    """).rowcount
    
    db.commit()
    print(f"  Linked {inserted:,} churches to SAC classification")
    
    # Show sample
    print("\nSample churches with SAC:")
    for r in db.execute("""
        SELECT c.id, c.name, c.city, c.state, s.sac_label
        FROM church_ca_sac s
        JOIN churches c ON c.id = s.church_rowid
        LIMIT 15
    """).fetchall():
        print(f"  ID={r[0]} '{r[1][:60]}' {r[2]} {r[3]} -> {r[4]}")
    
    # Province-level summary
    print("\nSAC by Province:")
    # Map province codes to names
    province_names = {
        '10': 'NL', '11': 'PE', '12': 'NS', '13': 'NB', '24': 'QC',
        '35': 'ON', '46': 'MB', '47': 'SK', '48': 'AB', '59': 'BC',
        '60': 'YT', '61': 'NWT', '62': 'NU'
    }
    
    for r in db.execute("""
        SELECT SUBSTR(s.cd_code, 1, 2) as prov, 
               s.sac_label, 
               COUNT(*) as churches
        FROM church_ca_sac s
        GROUP BY prov, s.sac_label
        ORDER BY prov, s.sac_type
    """).fetchall():
        prov_code, sac_label, churches = r
        prov_name = province_names.get(prov_code, prov_code)
        print(f"  {prov_name}: {sac_label} — {churches:,} churches")
    
    # Update catalog
    db.execute("""
        INSERT OR REPLACE INTO church_census_catalog 
        (country, table_name, category, geo_unit, description, variable_count, row_count, source_date, refresh_date)
        VALUES ('CA', 'church_ca_sac', 'classification', 'CD', 
                'Rural-urban classification (SAC-like) derived from census division population density and type',
                3, ?, '2021', datetime('now'))
    """, (inserted,))
    
    db.commit()
    db.close()
    
    print("\nDone. Created ca_sac_codes + church_ca_sac tables.")

if __name__ == '__main__':
    build_sac_classification()
