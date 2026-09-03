"""Import Gyeongsangbuk-do temple shapefile into churches.db.

Source: data.go.kr - Gyeongsangbuk-do Spatial Information of Temples (id=15095512)
License: 이용허락범위 제한 없음 (Unrestricted use)
167 Buddhist temples, EPSG:5174 coords, one-time data from 2020-09-21.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from gw_db import connect

import shapefile
import pyproj
from tqdm import tqdm

CHUNK_SIZE = 100

# Korean TM (Bessel central origin) → WGS84
# EPSG:5174 = Bessel 1841 ellipsoid, central meridian 127°E, TM projection
src_crs = pyproj.CRS("EPSG:5174")
dst_crs = pyproj.CRS("EPSG:4326")
transformer = pyproj.Transformer.from_crs(src_crs, dst_crs, always_xy=True)

shapefile_path = r"E:\grid\data\gyeongbuk_temples\경상북도_사찰_공간정보.shp"

def main():
    db = connect()
    
    # Read shapefile
    sf = shapefile.Reader(shapefile_path)
    records = sf.shapeRecords()
    print(f"Shapefile records: {len(records)}")
    
    # Check existing KR entries to avoid duplicates
    existing_coords = set()
    cur = db.execute("SELECT latitude, longitude FROM churches WHERE country='KR'")
    for row in cur.fetchall():
        lat, lon = row
        if lat and lon:
            existing_coords.add((round(lat, 4), round(lon, 4)))
    print(f"Existing KR entries with coords: {len(existing_coords)}")
    
    # Get max ID
    cur = db.execute("SELECT MAX(id) FROM churches")
    next_id = (cur.fetchone()[0] or 0) + 1
    
    new_records = []
    skipped = 0
    
    for sr in records:
        props = sr.record.as_dict()
        x, y = props['x'], props['y']
        
        # Convert coordinates
        lon, lat = transformer.transform(x, y)
        
        # Check for duplicates
        if (round(lat, 4), round(lon, 4)) in existing_coords:
            skipped += 1
            continue
        
        temple_name = props['temple_nm']
        sgg_nm = props['sgg_nm']  # city/county
        address = props['org_rd_adr'] or props.get('ref_rd_adr', '')
        phone = props.get('tel_num', '')
        
        new_records.append({
            'id': next_id + len(new_records),
            'temple_nm': temple_name,
            'sgg_nm': sgg_nm,
            'address': address,
            'phone': phone,
            'lat': lat,
            'lon': lon,
        })
    
    print(f"New to import: {len(new_records)}")
    print(f"Skipped (coord match): {skipped}")
    
    if not new_records:
        print("Nothing to import.")
        return
    
    cols = [
        'id','name','faith','tradition','normalized_name','address',
        'city','state','zip','zip5','zip4','ein','ntee_code',
        'latitude','longitude','geocode_source','fips','country',
        'source','denomination','address_source','holy_site_id',
        'landmark_type','is_landmark','heritage_status','height_m','width_m',
        'length_m','area_m2','capacity','building_year',
        'source_primary','source_secondary','osm_id','osm_type',
        'osm_version','osm_timestamp','wikidata_qid',
        'wikidata_last_modified','overture_id','confidence_score',
        'cra_bn','cra_category','cra_sub_category','cra_designation',
        'mosque_type','canonical_status','heritage_source','dedication',
        'muslim_affiliation','muslim_confidence','muslim_classification_source',
        'muslim_updated','name_original','age_centuries','county',
        'county_fips_5','name_transliterated','continent','region_un',
        'subregion','taxonomy_id','civilizational_family','nearest_city_km',
        'last_updated','diocese','ministries','merged_into',
        'jewish_confidence','jewish_classification_source','jewish_updated',
        'boston_pid','boston_property_json','boston_school_schid',
        'boston_school_type','sikh_affiliation','sikh_confidence',
        'sikh_classification_source','sikh_updated'
    ]
    col_str = ','.join(cols)
    placeholders = ','.join(['?'] * len(cols))
    
    from gw_db import log_change
    
    for i in tqdm(range(0, len(new_records), CHUNK_SIZE), desc="Importing Korean temples"):
        chunk = new_records[i:i+CHUNK_SIZE]
        batch = []
        for r in chunk:
            row = (
                r['id'],                              # id
                r['temple_nm'],                       # name
                'Buddhist',                           # faith
                'Korean Buddhism',                    # tradition
                None,                                 # normalized_name
                r['address'],                         # address
                r['sgg_nm'],                          # city
                'Gyeongsangbuk-do',                   # state
                None,                                 # zip
                None,                                 # zip5
                None,                                 # zip4
                None,                                 # ein
                None,                                 # ntee_code
                r['lat'],                             # latitude
                r['lon'],                             # longitude
                'korea_shapefile',                    # geocode_source
                None,                                 # fips
                'KR',                                 # country
                'korea_gov',                          # source
                None,                                 # denomination
                None,                                 # address_source
                None,                                 # holy_site_id
                'temple',                             # landmark_type
                0,                                    # is_landmark
                None,                                 # heritage_status
                0,                                    # height_m
                0,                                    # width_m
                0,                                    # length_m
                0,                                    # area_m2
                0,                                    # capacity
                0,                                    # building_year
                'korea_gov_api',                      # source_primary
                None,                                 # source_secondary
                None,                                 # osm_id
                None,                                 # osm_type
                None,                                 # osm_version
                None,                                 # osm_timestamp
                None,                                 # wikidata_qid
                None,                                 # wikidata_last_modified
                None,                                 # overture_id
                0.85,                                 # confidence_score
                None,                                 # cra_bn
                None,                                 # cra_category
                None,                                 # cra_sub_category
                None,                                 # cra_designation
                None,                                 # mosque_type
                None,                                 # canonical_status
                None,                                 # heritage_source
                None,                                 # dedication
                None,                                 # muslim_affiliation
                None,                                 # muslim_confidence
                None,                                 # muslim_classification_source
                None,                                 # muslim_updated
                None,                                 # name_original
                None,                                 # age_centuries
                None,                                 # county
                None,                                 # county_fips_5
                None,                                 # name_transliterated
                'Asia',                               # continent
                'Eastern Asia',                       # region_un
                None,                                 # subregion
                65,                                   # taxonomy_id (Korean Buddhism)
                'Buddhist',                           # civilizational_family
                None,                                 # nearest_city_km
                None,                                 # last_updated
                None,                                 # diocese
                None,                                 # ministries
                None,                                 # merged_into
                None,                                 # jewish_confidence
                None,                                 # jewish_classification_source
                None,                                 # jewish_updated
                None,                                 # boston_pid
                None,                                 # boston_property_json
                None,                                 # boston_school_schid
                None,                                 # boston_school_type
                None,                                 # sikh_affiliation
                None,                                 # sikh_confidence
                None,                                 # sikh_classification_source
                None,                                 # sikh_updated
            )
            batch.append(row)
        
        sql = f'INSERT OR IGNORE INTO churches ({col_str}) VALUES ({placeholders})'
        db.executemany(sql, batch)
        db.commit()
    
    # Also add phone numbers to church_contact_values
    print("\nAdding phone numbers to church_contact_values...")
    phone_count = 0
    for r in new_records:
        if r['phone']:
            db.execute(
                "INSERT OR IGNORE INTO church_contact_values (church_id, contact_type, value, confidence, source) VALUES (?, ?, ?, ?, ?)",
                (r['id'], 'phone', r['phone'], 0.85, 'korea_gov_api')
            )
            phone_count += 1
    db.commit()
    
    print(f"\n✅ Imported {len(new_records)} Korean Buddhist temples")
    print(f"  Phone numbers added: {phone_count}")
    print(f"  ID range: {new_records[0]['id']} - {new_records[-1]['id']}")
    
    # Verify
    cur = db.execute("SELECT COUNT(*) FROM churches WHERE country='KR'")
    print(f"  Total KR entries: {cur.fetchone()[0]}")

if __name__ == '__main__':
    main()
