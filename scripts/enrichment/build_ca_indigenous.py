"""
Build Indigenous lands enrichment for Canadian churches.

Sources:
1. indigenous_pop from church_census_ca (DA-level Indigenous population)
2. Indigenous reserve CSD types from census
3. Treaty boundaries from NRCan (if available)

Creates:
- church_ca_indigenous: flag + Indigenous population % per church
"""
import sqlite3, math

DB = r'e:\grid\churches.db'

def build_indigenous_enrichment():
    db = sqlite3.connect(DB)
    
    print("=== Indigenous Population from DA-level Census ===")
    
    # Check the indigenous_pop column in church_census_ca
    total_da = db.execute("SELECT COUNT(*) FROM church_census_ca WHERE indigenous_pop IS NOT NULL").fetchone()[0]
    total_ca = db.execute("SELECT COUNT(*) FROM church_census_ca").fetchone()[0]
    print(f"DA rows with indigenous_pop: {total_da:,} / {total_ca:,} ({100*total_da/total_ca:.1f}%)")
    
    # Create enrichment table
    db.execute("DROP TABLE IF EXISTS church_ca_indigenous")
    db.execute("""
        CREATE TABLE church_ca_indigenous (
            church_rowid INTEGER PRIMARY KEY,
            indigenous_pop INTEGER,
            total_pop INTEGER,
            indigenous_pct REAL,
            is_indigenous_community INTEGER DEFAULT 0,
            source TEXT DEFAULT 'statcan_2021_da',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    
    # Populate from church_census_ca
    inserted = db.execute("""
        INSERT INTO church_ca_indigenous (church_rowid, indigenous_pop, total_pop)
        SELECT church_rowid, 
               CAST(indigenous_pop AS INTEGER),
               CAST(total_pop AS INTEGER)
        FROM church_census_ca
        WHERE indigenous_pop IS NOT NULL
    """).rowcount
    
    # Calculate percentages and flag
    db.execute("""
        UPDATE church_ca_indigenous
        SET indigenous_pct = CASE 
            WHEN total_pop > 0 THEN ROUND(100.0 * indigenous_pop / total_pop, 1)
            ELSE 0 
        END
    """)
    
    db.execute("""
        UPDATE church_ca_indigenous
        SET is_indigenous_community = CASE
            WHEN indigenous_pct >= 50 THEN 2  -- majority Indigenous
            WHEN indigenous_pct >= 20 THEN 1  -- significant Indigenous presence
            ELSE 0
        END
    """)
    
    db.commit()
    
    # Stats
    stats = db.execute("""
        SELECT 
            CASE 
                WHEN is_indigenous_community = 2 THEN 'Majority Indigenous (>50%)'
                WHEN is_indigenous_community = 1 THEN 'Significant Indigenous (20-50%)'
                ELSE '<20% Indigenous'
            END as category,
            COUNT(*) as churches,
            ROUND(AVG(indigenous_pct), 1) as avg_pct,
            SUM(indigenous_pop) as total_indigenous_pop
        FROM church_ca_indigenous
        WHERE total_pop > 0
        GROUP BY is_indigenous_community
        ORDER BY is_indigenous_community DESC
    """).fetchall()
    
    print(f"\nIndigenous Community Classification:")
    print(f"  Churches enriched: {inserted:,}")
    for cat, cnt, avg, total in stats:
        print(f"  {cat}: {cnt:,} churches (avg {avg}%, {total:,} Indigenous pop)")
    
    # By province
    print("\nBy Province (majority Indigenous communities):")
    province_names = {
        '10': 'NL', '11': 'PE', '12': 'NS', '13': 'NB', '24': 'QC',
        '35': 'ON', '46': 'MB', '47': 'SK', '48': 'AB', '59': 'BC',
        '60': 'YT', '61': 'NWT', '62': 'NU'
    }
    
    for r in db.execute("""
        SELECT d.province_code, COUNT(*) as churches, 
               ROUND(AVG(i.indigenous_pct), 1) as avg_pct
        FROM church_ca_indigenous i
        JOIN church_census_ca d ON d.church_rowid = i.church_rowid
        WHERE i.is_indigenous_community >= 1
        GROUP BY d.province_code
        ORDER BY COUNT(*) DESC
    """).fetchall():
        prov_code, cnt, avg = r
        prov_name = province_names.get(prov_code, prov_code or 'NULL')
        print(f"  {prov_name}: {cnt:,} churches (avg {avg}% Indigenous)")
    
    # Show examples
    print("\nExample Indigenous community churches:")
    for r in db.execute("""
        SELECT c.id, c.name, c.city, c.state, i.indigenous_pct, i.indigenous_pop, i.total_pop
        FROM church_ca_indigenous i
        JOIN churches c ON c.id = i.church_rowid
        WHERE i.is_indigenous_community = 2 AND i.total_pop > 100
        LIMIT 15
    """).fetchall():
        print(f"  #{r[0]} '{r[1][:55]}' {r[2]} {r[3]} — {r[4]:.0f}% Indigenous ({r[5]}/{r[6]})")
    
    # Update catalog
    db.execute("""
        INSERT OR REPLACE INTO church_census_catalog 
        (country, table_name, category, geo_unit, description, variable_count, row_count, source_date, refresh_date)
        VALUES ('CA', 'church_ca_indigenous', 'demographics', 'DA',
                'Indigenous population share and community flag at DA level from 2021 Census',
                3, ?, '2021', datetime('now'))
    """, (inserted,))
    
    db.commit()
    
    # Also create a summary of reserve-adjacent churches
    print(f"\n=== Reserve-Adjacent Flag ===")
    # Flag churches where >10% of DA population is Indigenous but <50% (proximity, not on-reserve)
    reserve_adjacent = db.execute("""
        SELECT COUNT(*) FROM church_ca_indigenous
        WHERE indigenous_pct >= 10 AND indigenous_pct < 50
    """).fetchone()[0]
    print(f"  Reserve-adjacent (10-50% Indigenous): {reserve_adjacent:,} churches")
    
    db.close()
    print("\nDone. Created church_ca_indigenous table.")

if __name__ == '__main__':
    build_indigenous_enrichment()
