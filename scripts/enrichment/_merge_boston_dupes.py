"""
Merge duplicate Boston church records by name.
Keeps the best record (most data), transfers missing fields,
and marks duplicates as merged.

Strategy:
  1. Group by UPPER(name) within Boston
  2. Score each record (GPS=+5, boston_pid=+3, boston_property_json=+2,
     denomination=+1, source priority)
  3. Keep the best, merge data from others, delete duplicates
"""
import sys, json
from datetime import datetime
sys.path.insert(0, r'E:\grid')
from gw_db import connect, log_change

BOSTON_CITIES = ['BOSTON','ALLSTON','BRIGHTON','CHARLESTOWN','DORCHESTER',
    'EAST BOSTON','HYDE PARK','JAMAICA PLAIN','MATTAPAN','READVILLE',
    'ROSLINDALE','ROXBURY','ROXBURY CROSSING','SOUTH BOSTON','WEST ROXBURY']
SOURCE = 'boston_dedup'
COLUMNS_TO_MERGE = [
    'faith', 'denomination', 'landmark_type', 'latitude', 'longitude',
    'address', 'city', 'state', 'zip', 'country',
    'boston_pid', 'boston_property_json',
    'phone', 'website', 'email',
]

SOURCE_PRIORITY = [
    'masstimes_nationwide+holy_sites_enrichment',
    'masstimes_nationwide',
    'overture_full+holy_sites_enrichment',
    'overture_full',
    'overture+holy_sites_enrichment',
    'overture_canada+holy_sites_enrichment',
    'overture_canada',
    'churchunion_scraper+holy_sites_enrichment',
    'churchunion_scraper',
    'holy_sites_import',
    'boston_property_assessment',
    'boston_nonpublic_schools',
]


def score_record(conn, id_):
    """Score a record's data richness."""
    r = conn.execute("""
        SELECT latitude, longitude, boston_pid, boston_property_json,
               denomination, faith, landmark_type
        FROM churches WHERE id = ?
    """, (id_,)).fetchone()
    
    score = 0
    if r[0] and r[1]: score += 5  # has GPS
    if r[2]: score += 3            # has boston_pid
    if r[3]: score += 2            # has property JSON
    if r[4]: score += 1            # has denomination
    return score


def row_to_dict(row, cols):
    """Convert a sqlite3.Row to dict using column names."""
    return {col: row[i] for i, col in enumerate(cols)}

def get_row(conn, id_):
    row = conn.execute("SELECT * FROM churches WHERE id = ?", (id_,)).fetchone()
    if not row:
        return None
    return row_to_dict(row, COLUMN_NAMES)

def merge_records(conn, keep_id, duplicate_ids, group_name):
    """Merge duplicate records into the kept record."""
    keep = get_row(conn, keep_id)
    if not keep:
        return []
    
    changes = []
    
    for dup_id in duplicate_ids:
        dup = get_row(conn, dup_id)
        if not dup:
            continue
        
        # Transfer missing data from duplicate to kept record
        for col in COLUMNS_TO_MERGE:
            if col in ('phone', 'website', 'email'):
                continue  # handled via contact_values
            if col in keep and col in dup:
                if not keep[col] and dup[col]:
                    old_val = keep[col]
                    conn.execute(f"UPDATE churches SET {col} = ? WHERE id = ?",
                                 (dup[col], keep_id))
                    log_change(conn, church_id=keep_id, field_name=col,
                               old_value=old_val, new_value=dup[col],
                               source=SOURCE)
                    changes.append(f"{col}: {dup[col][:30]}")
        
        # Transfer contact values
        contacts = conn.execute(
            "SELECT id, contact_type, value FROM church_contact_values WHERE church_id = ?",
            (dup_id,)
        ).fetchall()
        for cid, ctype, cval in contacts:
            # Check if keep already has this contact type
            existing = conn.execute(
                "SELECT id FROM church_contact_values WHERE church_id = ? AND contact_type = ? AND value = ?",
                (keep_id, ctype, cval)
            ).fetchone()
            if not existing:
                conn.execute(
                    "UPDATE church_contact_values SET church_id = ? WHERE id = ?",
                    (keep_id, cid)
                )
                changes.append(f"contact_{ctype}: {cval[:30]}")
        
        # Transfer boston_pid if missing
        if not keep.get('boston_pid') and dup.get('boston_pid'):
            conn.execute("UPDATE churches SET boston_pid = ? WHERE id = ?",
                         (dup['boston_pid'], keep_id))
            log_change(conn, church_id=keep_id, field_name='boston_pid',
                       old_value=None, new_value=dup['boston_pid'],
                       source=SOURCE)
            changes.append(f"boston_pid: {dup['boston_pid']}")
        
        # Transfer boston_property_json if missing
        if not keep.get('boston_property_json') and dup.get('boston_property_json'):
            conn.execute("UPDATE churches SET boston_property_json = ? WHERE id = ?",
                         (dup['boston_property_json'], keep_id))
            changes.append("boston_property_json")
        
        # Mark as merged
        conn.execute("UPDATE churches SET merged_into = ? WHERE id = ?",
                     (keep_id, dup_id))
        
        # Delete the duplicate's contact values (already transferred)
        conn.execute("DELETE FROM church_contact_values WHERE church_id = ?", (dup_id,))
    
    return changes


COLUMN_NAMES = [
    'id', 'name', 'tradition', 'legacy', 'faith', 'normalized_name',
    'address', 'city', 'state', 'zip', 'zip5', 'zip4', 'ein', 'ntee_code',
    'latitude', 'longitude', 'geocode_source', 'fips', 'country', 'source',
    'denomination', 'address_source', 'holy_site_id', 'landmark_type',
    'is_landmark', 'heritage_status', 'height_m', 'width_m', 'length_m',
    'area_m2', 'capacity', 'building_year', 'source_primary', 'source_secondary',
    'osm_id', 'osm_type', 'osm_version', 'osm_timestamp', 'wikidata_qid',
    'wikidata_last_modified', 'overture_id', 'confidence_score', 'cra_bn',
    'cra_category', 'cra_sub_category', 'cra_designation', 'mosque_type',
    'canonical_status', 'heritage_source', 'dedication', 'muslim_affiliation',
    'muslim_confidence', 'muslim_classification_source', 'muslim_updated',
    'name_original', 'age_centuries', 'county', 'county_fips_5',
    'name_transliterated', 'continent', 'region_un', 'subregion', 'taxonomy_id',
    'civilizational_family', 'nearest_city_km', 'last_updated', 'diocese',
    'ministries', 'merged_into', 'jewish_confidence', 'jewish_classification_source',
    'jewish_updated', 'boston_pid', 'boston_property_json',
    'boston_school_schid', 'boston_school_type',
]


def main():
    conn = connect(r'E:\grid\churches.db')
    p = ','.join('?' for _ in BOSTON_CITIES)
    
    # Find duplicate names in Boston area
    dupes = conn.execute(f"""
        SELECT UPPER(name) as upper_name, COUNT(*) as cnt,
               GROUP_CONCAT(id) as ids
        FROM churches 
        WHERE state='MA' AND UPPER(city) IN ({p})
        GROUP BY UPPER(name)
        HAVING cnt > 1
        ORDER BY cnt DESC
    """, BOSTON_CITIES).fetchall()
    
    print(f"Found {len(dupes)} duplicate name groups ({sum(d[1]-1 for d in dupes)} extra records)")
    
    total_merged = 0
    total_deleted = 0
    
    for name, cnt, ids_str in dupes:
        ids = [int(x) for x in ids_str.split(',')]
        
        # Score each record
        scored = [(score_record(conn, id_), id_) for id_ in ids]
        scored.sort(key=lambda x: -x[0])
        
        keep_id = scored[0][1]
        duplicate_ids = [sid for _, sid in scored[1:]]
        
        # Check if any of these already have merged_into set
        already_merged = conn.execute(
            "SELECT COUNT(*) FROM churches WHERE id IN ({}) AND merged_into IS NOT NULL".format(
                ','.join('?' for _ in ids)), ids
        ).fetchone()[0]
        
        if already_merged:
            # Skip groups that already have merges
            continue
        
        changes = merge_records(conn, keep_id, duplicate_ids, name)
        
        if changes:
            print(f"\n  {name[:50]:50s} ({cnt}x)")
            print(f"    KEEP #{keep_id}  MERGED: {', '.join(changes[:5])}")
            if len(changes) > 5:
                print(f"    ... and {len(changes)-5} more")
            for dup_id in duplicate_ids:
                print(f"    -> #{dup_id} merged & removed")
        
        total_merged += 1
        total_deleted += len(duplicate_ids)
        
        if total_merged % 20 == 0:
            conn.commit()
    
    conn.commit()
    
    # Final count
    remaining_dupes = conn.execute(f"""
        SELECT COUNT(*) FROM (
            SELECT UPPER(name) FROM churches 
            WHERE state='MA' AND UPPER(city) IN ({p})
            GROUP BY UPPER(name) HAVING COUNT(*) > 1
        )
    """, BOSTON_CITIES).fetchone()[0]
    
    total_remaining = conn.execute(f"""
        SELECT COUNT(*) FROM churches 
        WHERE state='MA' AND UPPER(city) IN ({p})
    """, BOSTON_CITIES).fetchone()[0]
    
    print(f"\n{'='*60}")
    print(f"MERGE COMPLETE")
    print(f"{'='*60}")
    print(f"  Groups merged:  {total_merged}")
    print(f"  Records deleted: {total_deleted}")
    print(f"  Remaining name dupes: {remaining_dupes}")
    print(f"  Total Boston records: {total_remaining}")
    
    conn.close()


if __name__ == '__main__':
    main()
