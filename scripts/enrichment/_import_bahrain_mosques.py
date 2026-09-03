"""Import Bahrain religious places (mosques) from data.gov.bh API.

Source: https://www.data.gov.bh/explore/dataset/religious-places/table/
API: https://www.data.gov.bh/api/explore/v2.1/catalog/datasets/religious-places/records
License: Bahrain Government Open Data License (CC BY-like)

All 989 records are MOSQUES in Bahrain.
- 974 new records to import (15 already exist in DB)
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from gw_db import connect

CHUNK_SIZE = 500

def main():
    db = connect()
    
    # Load API data
    with open('data/bahrain_raw.json', 'r', encoding='utf-8') as f:
        api_records = json.load(f)
    
    print(f'API records: {len(api_records)}')
    
    # Get existing Bahrain entries with coordinates
    cur = db.execute("""
        SELECT id, name, latitude, longitude FROM churches WHERE country='BH'
    """)
    existing = cur.fetchall()
    print(f'Existing BH entries: {len(existing)}')
    
    # Build matching sets
    existing_coords = set()
    existing_names = {}
    for r in existing:
        eid, name, lat, lon = r
        if lat and lon:
            key = (round(lat, 4), round(lon, 4))
            existing_coords.add(key)
        existing_names[name.upper().strip()] = eid
    
    # Filter new records
    new_records = []
    for r in api_records:
        name = r['name']
        lat = r['y_latitude']
        lon = r['x_longitude']
        coord_key = (round(lat, 4), round(lon, 4))
        
        if coord_key in existing_coords:
            continue
        if name.upper().strip() in existing_names:
            continue
        new_records.append(r)
    
    print(f'New records to import: {len(new_records)}')
    
    if not new_records:
        print('Nothing to import.')
        return
    
    # Get max ID
    cur = db.execute("SELECT MAX(id) FROM churches")
    next_id = (cur.fetchone()[0] or 0) + 1
    print(f'Starting ID: {next_id}')
    
    # Column order from PRAGMA table_info(churches):
    cols = [
        'id','name','tradition','legacy','faith',
        'normalized_name','address','city','state','zip','zip5','zip4',
        'ein','ntee_code','latitude','longitude','geocode_source','fips',
        'country','source','denomination','address_source','holy_site_id',
        'landmark_type','is_landmark','heritage_status','height_m','width_m',
        'length_m','area_m2','capacity','building_year','source_primary',
        'source_secondary','osm_id','osm_type','osm_version','osm_timestamp',
        'wikidata_qid','wikidata_last_modified','overture_id','confidence_score',
        'cra_bn','cra_category','cra_sub_category','cra_designation',
        'mosque_type','canonical_status','heritage_source','dedication',
        'muslim_affiliation','muslim_confidence','muslim_classification_source',
        'muslim_updated','name_original','age_centuries','county','county_fips_5',
        'name_transliterated','continent','region_un','subregion','taxonomy_id',
        'civilizational_family','nearest_city_km','last_updated','diocese',
        'ministries','merged_into','jewish_confidence','jewish_classification_source',
        'jewish_updated','boston_pid','boston_property_json','boston_school_schid',
        'boston_school_type','sikh_affiliation','sikh_confidence',
        'sikh_classification_source','sikh_updated'
    ]
    
    col_str = ','.join(cols)
    placeholders = ','.join(['?'] * len(cols))
    
    sql = f'INSERT OR IGNORE INTO churches ({col_str}) VALUES ({placeholders})'
    
    from tqdm import tqdm
    total_inserted = 0
    
    for i in tqdm(range(0, len(new_records), CHUNK_SIZE), desc='Importing Bahrain mosques'):
        chunk = new_records[i:i+CHUNK_SIZE]
        batch = []
        for j, r in enumerate(chunk):
            row = (
                next_id + i + j,                    # id
                r['name'],                          # name
                'Sunni',                            # tradition
                None,                               # legacy
                'Islam',                            # faith
                None,                               # normalized_name
                None,                               # address
                None,                               # city
                None,                               # state
                None,                               # zip
                None,                               # zip5
                None,                               # zip4
                None,                               # ein
                None,                               # ntee_code
                r['y_latitude'],                    # latitude
                r['x_longitude'],                   # longitude
                'bahrain_gov',                      # geocode_source
                None,                               # fips
                'BH',                               # country
                'bahrain_gov',                      # source
                None,                               # denomination
                None,                               # address_source
                None,                               # holy_site_id
                'mosque',                           # landmark_type
                0,                                  # is_landmark
                None,                               # heritage_status
                0,                                  # height_m
                0,                                  # width_m
                0,                                  # length_m
                0,                                  # area_m2
                0,                                  # capacity
                0,                                  # building_year
                'bahrain_gov_api',                  # source_primary
                None,                               # source_secondary
                None,                               # osm_id
                None,                               # osm_type
                None,                               # osm_version
                None,                               # osm_timestamp
                None,                               # wikidata_qid
                None,                               # wikidata_last_modified
                None,                               # overture_id
                0.85,                               # confidence_score
                None,                               # cra_bn
                None,                               # cra_category
                None,                               # cra_sub_category
                None,                               # cra_designation
                None,                               # mosque_type
                None,                               # canonical_status
                None,                               # heritage_source
                None,                               # dedication
                None,                               # muslim_affiliation
                0.85,                               # muslim_confidence
                'bahrain_gov_api',                  # muslim_classification_source
                None,                               # muslim_updated
                None,                               # name_original
                None,                               # age_centuries
                None,                               # county
                None,                               # county_fips_5
                r['l_sm'],                          # name_transliterated (Arabic name)
                'Asia',                             # continent
                'Western Asia',                     # region_un
                None,                               # subregion
                4,                                  # taxonomy_id (Islam)
                'Islamic',                          # civilizational_family
                None,                               # nearest_city_km
                None,                               # last_updated
                None,                               # diocese
                None,                               # ministries
                None,                               # merged_into
                None,                               # jewish_confidence
                None,                               # jewish_classification_source
                None,                               # jewish_updated
                None,                               # boston_pid
                None,                               # boston_property_json
                None,                               # boston_school_schid
                None,                               # boston_school_type
                None,                               # sikh_affiliation
                None,                               # sikh_confidence
                None,                               # sikh_classification_source
                None,                               # sikh_updated
            )
            batch.append(row)
        
        db.executemany(sql, batch)
        db.commit()
        total_inserted += len(batch)
    
    print(f'\n✅ Imported {total_inserted} Bahrain mosques')
    print(f'ID range: {next_id} - {next_id + len(new_records) - 1}')
    
    # Verify
    cur = db.execute("SELECT COUNT(*) FROM churches WHERE country='BH'")
    print(f'Total Bahrain entries now: {cur.fetchone()[0]}')

if __name__ == '__main__':
    main()
