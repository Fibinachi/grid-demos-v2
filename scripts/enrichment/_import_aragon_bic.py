"""
Import Aragón BIC (Bienes de Interés Cultural) religious sites into churches.db.

Converts UTM (EPSG:25830) → WGS84, classifies by faith, and imports new entries.
"""
import csv
import re
import sys
import os
from collections import Counter

sys.path.insert(0, r'E:\grid')
from gw_db import connect, Provenance, log_change

try:
    from pyproj import Transformer
    HAS_PROJ = True
    TRANS_UTM2WGS = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)
except ImportError:
    HAS_PROJ = False
    print("WARNING: pyproj not installed. UTM coordinates will not be converted.")
    print("Install with: pip install pyproj")

CHUNK_SIZE = 500

def parse_utm_point(shape_text):
    """Parse 'POINT (x y)' UTM string to (lon, lat) in WGS84."""
    m = re.match(r'POINT\s*\(([\d.]+)\s+([\d.]+)\)', shape_text)
    if not m:
        return None, None
    x, y = float(m.group(1)), float(m.group(2))
    if HAS_PROJ:
        lon, lat = TRANS_UTM2WGS.transform(x, y)
        return round(lon, 6), round(lat, 6)
    return x, y  # raw UTM if no pyproj

def classify_entry(name, cat):
    """Classify a BIC entry by faith. Returns (taxonomy_id, faith_name, detail)."""
    upper = name.upper()
    
    # === Christian ===
    # Actual church/chapel/monastery/hermitage buildings
    christian_building_kw = ['IGLESIA', 'ERMITA', 'MONASTERIO', 'CONVENTO', 
                             'CATEDRAL', 'BASILICA', 'SANTUARIO', 'CAPILLA']
    
    for kw in christian_building_kw:
        if kw in upper:
            # Determine denomination detail
            if 'FORTIFICADA' in upper:
                return (2, 'Christian', 'Roman Catholic (fortified church)')
            if 'ERMITA' in upper:
                return (2, 'Christian', 'Hermitage')
            if 'MONASTERIO' in upper:
                return (2, 'Christian', 'Roman Catholic (monastery)')
            if 'CONVENTO' in upper:
                return (2, 'Christian', 'Roman Catholic (convent)')
            return (2, 'Christian', 'Roman Catholic Church')
    
    # Torre de la Iglesia / Torre aneja a la Iglesia — church towers
    if 'TORRE' in upper and ('IGLESIA' in upper or 'ERMITA' in upper):
        return (2, 'Christian', 'Roman Catholic (church tower)')
    
    # Peña de la Virgen — Marian devotion sites
    if 'VIRGEN' in upper:
        return (2, 'Christian', 'Roman Catholic (Marian site)')
    
    # === Pre-Christian / Ancient ===
    # Temple sites
    if 'TEMPLO' in upper and 'ROMANO' in upper:
        return (53, 'Pagan', 'Roman temple')
    if 'TEMPLO' in upper:
        return (53, 'Pagan', 'Ancient temple')
    
    # Altars
    if re.search(r'\bALTAR\b', upper) or re.search(r'\bARA\b', upper):
        return (53, 'Pagan', 'Ancient altar')
    
    # Celtiberian / Iberian religious sites
    if 'IBERICO' in upper or 'IBERICA' in upper:
        if any(w in upper for w in ['SANTUARIO', 'TEMPLO', 'NECROPOLIS', 'CABEZO']):
            return (53, 'Pagan', 'Iberian / Celtiberian sanctuary')
    
    return None  # Not clearly religious

def main():
    # Load CSV
    with open(r'E:\grid\data\aragon_bic_puntos.csv', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"Total BIC entries: {len(rows)}")
    
    # Classify all entries
    classified = []  # (taxonomy_id, faith, detail, row)
    for r in rows:
        result = classify_entry(r['denominaci'], r['categoria'])
        if result:
            classified.append((*result, r))
    
    # Stats
    by_faith = Counter(c[1] for c in classified)
    print(f"\nReligious entries: {len(classified)}")
    for faith, n in by_faith.most_common():
        print(f"  {faith}: {n}")
    
    # Connect to DB
    db = connect()
    
    # Build lookup of existing Spanish churches for dedup
    existing_lookup = set()
    cur = db.execute("SELECT id, name, city FROM churches WHERE country = 'ES'")
    for r in cur.fetchall():
        key = (r[1][:30].upper(), (r[2] or '')[:20].upper())
        existing_lookup.add(key)
    
    new_entries = []
    for tax_id, faith, detail, r in classified:
        name = r['denominaci'].strip()
        city = r['municipio'].strip()
        province = r['provincia'].strip().upper()
        # Normalize province
        province_map = {'HUESCA': 'Huesca', 'TERUEL': 'Teruel', 'ZARAGOZA': 'Zaragoza', 'TERUE': 'Teruel'}
        province = province_map.get(province, province.title() if province.isupper() else province)
        
        # Check if exists by name match
        lookup_key = (name[:30].upper(), city[:20].upper())
        name_only_key = (name[:30].upper(), '')
        
        if lookup_key in existing_lookup or name_only_key in existing_lookup:
            continue
        
        # Parse coordinates
        lon, lat = parse_utm_point(r['shape'])
        
        new_entries.append({
            'name': name,
            'city': city,
            'state': province,
            'country': 'ES',
            'latitude': lat,
            'longitude': lon,
            'taxonomy_id': tax_id,
            'faith': faith,
            'denomination': detail,
            'source_ref': f"Aragón BIC (objectid={r['objectid']})",
            'bic_numera': r['numera'],
            'bic_categoria': r['categoria'],
            'bic_comarca': r['comarca'],
        })
    
    print(f"\nNew entries to import: {len(new_entries)}")
    for e in new_entries:
        print(f"  {e['name']:50s} | {e['city']:25s} | {e['state']:10s} | ({e['latitude']}, {e['longitude']}) | {e['faith']}")
    
    # === IMPORT ===
    if not new_entries:
        print("\nNothing to import.")
        return
    
    # Ask for confirmation
    print(f"\nProceeding with import of {len(new_entries)} entries...")
    
    with Provenance(db, source="aragon_bic", action="inserted", 
                    fields="name,city,state,country,lat,lon,taxonomy_id,denomination,source",
                    records_attempted=len(new_entries)) as prov:
        
        for i in range(0, len(new_entries), CHUNK_SIZE):
            batch = new_entries[i:i+CHUNK_SIZE]
            for e in batch:
                try:
                    # Get next available id (id column has UNIQUE constraint, not autoincrement)
                    cur = db.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM churches")
                    next_id = cur.fetchone()[0]
                    cur = db.execute("""
                        INSERT INTO churches 
                            (id, name, city, state, country, latitude, longitude, taxonomy_id, 
                             denomination, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        next_id,
                        e['name'], e['city'], e['state'], e['country'],
                        e['latitude'], e['longitude'], e['taxonomy_id'],
                        e['faith'] + ' (' + e['denomination'] + ')',
                        e['source_ref']
                    ))
                    church_id = cur.lastrowid
                    prov.churches_inserted += 1
                    
                    # Also log enrichment
                    log_change(db, church_id, 'source', 
                               new_value=e['source_ref'],
                               source='aragon_bic')
                    
                except Exception as ex:
                    print(f"  ERROR inserting {e['name']}: {ex}")
            
            db.commit()
            print(f"  Batch {i//CHUNK_SIZE + 1}: {prov.churches_inserted} inserted so far...")
        
        prov.records_matched = len(new_entries)
    
    print(f"\n✓ Import complete: {prov.churches_inserted} new entries from Aragón BIC")

    # Print summary
    print("\n=== Import Summary ===")
    for e in new_entries:
        print(f"  {e['name']:50s} | {e['city']:25s} | {e['faith']:15s} | ({e['latitude']}, {e['longitude']})")

if __name__ == '__main__':
    main()
