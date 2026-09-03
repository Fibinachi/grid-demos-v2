"""
Geocode ACT Heritage Register entries using suburb centroids.

Nominatim is returning 403, so using known suburb coordinates directly.
"""
import sys
sys.path.insert(0, r'E:\grid')
from gw_db import connect, Provenance

CHUNK_SIZE = 500

# Suburb centroids for Canberra, ACT
SUBURB_COORDS = {
    'Ainslie': (-35.262, 149.145),
    'Calwell': (-35.441, 149.107),
    'Deakin': (-35.322, 149.108),
    'Forrest': (-35.316, 149.129),
    'Griffith': (-35.325, 149.137),
    'Kingston': (-35.315, 149.145),
    'Lyneham': (-35.253, 149.127),
    "O'Connor": (-35.258, 149.122),
    'Phillip': (-35.347, 149.086),
    'Reid': (-35.282, 149.137),
    'Tharwa': (-35.508, 149.072),
    'Turner': (-35.268, 149.125),
    'Weetangera': (-35.250, 149.048),
}


def main():
    db = connect()
    
    cur = db.execute(
        "SELECT id, name, city FROM churches "
        "WHERE source='act_heritage_register' AND latitude IS NULL"
    )
    entries = cur.fetchall()
    print(f"Entries to geocode: {len(entries)}")
    
    if not entries:
        print("Nothing to geocode.")
        db.close()
        return
    
    failed = []
    
    with Provenance(db, source="act_heritage_geocode", action="updated",
                    fields="latitude,longitude,geocode_source",
                    records_attempted=len(entries)) as prov:
        
        for i in range(0, len(entries), CHUNK_SIZE):
            batch = entries[i:i+CHUNK_SIZE]
            
            for eid, name, city in batch:
                suburb = (city or '').strip()
                
                if suburb in SUBURB_COORDS:
                    lat, lon = SUBURB_COORDS[suburb]
                    db.execute(
                        "UPDATE churches SET latitude=?, longitude=?, geocode_source='known_suburb' WHERE id=?",
                        (lat, lon, eid)
                    )
                    prov.churches_updated += 1
                    print(f"  OK: {name[:48]:48s} ({suburb:12s}) -> ({lat:.4f}, {lon:.4f})")
                else:
                    failed.append((eid, name, suburb))
                    print(f"  FAIL: {name[:48]:48s} ({suburb:12s}) - no coords")
            
            db.commit()
            print(f"  Batch committed ({prov.churches_updated} geocoded)")
    
    print(f"\n=== Results ===")
    print(f"  Geocoded via suburb centroid: {prov.churches_updated}")
    print(f"  Failed (unknown suburb): {len(failed)}")
    for eid, name, suburb in failed:
        print(f"    id={eid} {name[:50]} ({suburb})")
    
    db.close()


if __name__ == '__main__':
    main()
