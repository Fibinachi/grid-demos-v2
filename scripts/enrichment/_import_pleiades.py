"""
Import ancient religious sites from Pleiades gazetteer (CC BY 3.0).
Filters for pre-Christian religious place types: temple, sanctuary, shrine, altar, grove, pyramid.
Tags to appropriate ancient faith taxonomy nodes.
"""
import csv
import sys
import re
from collections import Counter, defaultdict

sys.path.insert(0, r'E:\grid')
from gw_db import connect, Provenance

DATA_DIR = r'E:\grid\data\pleiades\data\gis'
CHUNK_SIZE = 500

# Place types to include (pre-Christian religious sites)
RELIGIOUS_TYPES = {
    'temple': 618,       # Roman Religion (general pagan temple)
    'temple-2': 618,     # Roman Religion
    'sanctuary': 614,    # Ancient Mediterranean (regional - need specifics)
    'shrine': 614,       # Ancient Mediterranean
    'altar': 618,        # Roman Religion
    'grove': 614,        # Ancient Mediterranean (sacred grove)
    'pyramid': 620,      # Ancient Egyptian
    # Expanded: sanctuary-adjacent religious features
    'theatre': 614,      # Theaters at sanctuary complexes (Delphi, Epidaurus)
    'spring': 614,       # Sacred springs (Castalian Spring)
    'cave': 614,         # Oracular/religious caves (Corycian Cave)
    'stadion': 614,      # Athletic venues at panhellenic sanctuaries
    'gymnasium': 614,    # Training facilities at sanctuary sites
    'stoa': 614,         # Sacred porticoes in sanctuaries
    'treasury': 614,     # Treasuries at sanctuaries (Delphi treasuries)
    'tumulus': 614,      # Burial mounds (hero cult, Egyptian mortuary)
    'acropolis': 614,    # Religious acropolises
    'fountain': 614,     # Sacred fountains
    'odeon': 614,        # Music venues at sanctuaries
    'monument': 614,     # Religious monuments
    'tomb': 620,         # Tombs (default Egyptian for keyword matching)
}

# Keywords to refine taxonomy assignment
ROMAN_KW = ['roman', 'romae', 'romanus', 'romana', 'romani', 'imperium']
GREEK_KW = ['greek', 'graec', 'hellen', 'hellas', 'athen', 'spart', 'corinth',
            'thessalon', 'delphi', 'epidaurus', 'olympia', 'eleusis', 'mycenae',
            'knossos', 'phaistos', 'delos', 'samos', 'chios', 'lesbos', 'rhodes',
            'miletus', 'ephesus', 'halicarnassus', 'priene', 'didyma', 'pergamon',
            'phocaea', 'byzantium', 'heraklion', 'argos', 'thebes', 'megara',
            'marathon', 'thermopylae', 'salamis', 'naucratis', 'cyrene',
            'paestum', 'selinus', 'acragas', 'syracuse', 'taras', 'metapontum']
EGYPTIAN_KW = ['egypt', 'aegypt', 'theba', 'memph', 'alexand', 'nil']
MESOPOTAMIAN_KW = ['mesopotam', 'babylon', 'assyria', 'sumer', 'akkad']
PARTHIAN_KW = ['parth', 'persepol', 'ctesiphon']
CELTIBERIAN_KW = ['celtiber', 'lusitan', 'iberia', 'hispania']

def assign_taxonomy(title, description, place_type):
    """Assign taxonomy_id based on place name, description, and type."""
    text = (title + ' ' + (description or '')).lower()
    
    # Check for specific regional keywords
    if any(kw in text for kw in EGYPTIAN_KW):
        return 620  # Ancient Egyptian Religion
    if any(kw in text for kw in MESOPOTAMIAN_KW):
        return 630  # Mesopotamian Religion
    if any(kw in text for kw in PARTHIAN_KW):
        return 631  # Parthian Religion
    if any(kw in text for kw in GREEK_KW):
        return 619  # Hellenistic Religion
    if any(kw in text for kw in ROMAN_KW):
        return 618  # Roman Religion
    if any(kw in text for kw in CELTIBERIAN_KW):
        return 624  # Celtiberian Religion
    
    # Default by type
    type_defaults = {
        'temple': 618,      # Roman Religion (most general)
        'temple-2': 618,
        'sanctuary': 614,   # Ancient Mediterranean catch-all
        'shrine': 614,
        'altar': 618,
        'grove': 614,
        'pyramid': 620,     # Ancient Egyptian
    }
    return type_defaults.get(place_type, 614)

def main():
    # Load places
    print("Loading places.csv...")
    with open(f'{DATA_DIR}/places.csv', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        places = {}
        for r in reader:
            places[r['id']] = r
    print(f"  {len(places)} places loaded")
    
    # Load place types
    print("Loading places_place_types.csv...")
    with open(f'{DATA_DIR}/places_place_types.csv', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        place_types = list(reader)
    print(f"  {len(place_types)} type assignments")
    
    # Link places to their types
    type_to_places = defaultdict(list)
    for pt in place_types:
        type_to_places[pt['place_type']].append(pt['place_id'])
    
    # Collect religious sites
    print(f"\nCollecting religious sites...")
    religious_places = {}  # place_id -> tax_id
    for ptype, tax_id_default in RELIGIOUS_TYPES.items():
        pids = type_to_places.get(ptype, [])
        for pid in pids:
            if pid in places and pid not in religious_places:
                religious_places[pid] = pid  # placeholder
    
    print(f"  Found {len(religious_places)} pre-Christian religious sites")
    
    # Stats by type
    type_stats = Counter()
    for pt in place_types:
        if pt['place_id'] in religious_places:
            type_stats[pt['place_type']] += 1
    print("\n=== By type ===")
    for t, n in type_stats.most_common():
        print(f"  {t:30s} {n}")
    
    # Load existing entries in DB to avoid duplicates
    db = connect()
    existing = set()
    cur = db.execute("SELECT id, name FROM churches WHERE source LIKE '%pleiades%'")
    for r in cur.fetchall():
        existing.add(r[1][:60])
    
    # Also check by Pleiades URI
    existing_uris = set()
    cur = db.execute("SELECT source FROM churches WHERE source LIKE '%pleiades.stoa.org%'")
    for r in cur.fetchall():
        existing_uris.add(r[0])
    
    # Prepare new entries
    new_entries = []
    for pid in sorted(religious_places.keys()):
        p = places[pid]
        title = p['title'].strip()
        
        # Get place types for this place
        ptypes = [pt['place_type'] for pt in place_types if pt['place_id'] == pid]
        primary_type = ptypes[0] if ptypes else 'unknown'
        
        # Assign taxonomy
        tax_id = assign_taxonomy(title, p.get('description', ''), primary_type)
        
        # Dedup
        if title[:60] in existing:
            continue
        
        pleiades_uri = f"https://pleiades.stoa.org/places/{pid}"
        if pleiades_uri in existing_uris:
            continue
        
        lat = p.get('representative_latitude')
        lon = p.get('representative_longitude')
        
        if not lat or not lon:
            continue
        
        # Determine country from context (rough - from description or leave blank)
        country = guess_country(title, p.get('description', ''))
        
        new_entries.append({
            'name': title,
            'description': p.get('description', '')[:200],
            'latitude': float(lat),
            'longitude': float(lon),
            'taxonomy_id': tax_id,
            'country': country,
            'types': ', '.join(ptypes),
            'pleiades_id': pid,
            'uri': pleiades_uri,
        })
    
    print(f"\nNew entries to import: {len(new_entries)}")
    
    if not new_entries:
        print("Nothing to import.")
        return
    
    # Preview
    by_tax = Counter(e['taxonomy_id'] for e in new_entries)
    print("\n=== By taxonomy ===")
    for tid, n in by_tax.most_common():
        tname = {618: 'Roman Religion', 619: 'Hellenistic', 620: 'Egyptian', 
                 614: 'Ancient Med.', 630: 'Mesopotamian', 631: 'Parthian', 
                 624: 'Celtiberian', 637: 'Megalithic', 636: 'Neolithic'}.get(tid, str(tid))
        print(f"  {tname:25s} ({tid}): {n}")
    
    # Show first 10
    print("\n=== Sample entries ===")
    for e in new_entries[:10]:
        print(f"  {e['name'][:50]:50s} | ({e['latitude']:.4f}, {e['longitude']:.4f}) | tax={e['taxonomy_id']} | {e['country']}")
    
    # Import
    print(f"\nImporting {len(new_entries)} entries...")
    with Provenance(db, source="pleiades", action="inserted",
                    fields="name,latitude,longitude,taxonomy_id,source",
                    records_attempted=len(new_entries)) as prov:
        
        for i in range(0, len(new_entries), CHUNK_SIZE):
            batch = new_entries[i:i+CHUNK_SIZE]
            for e in batch:
                try:
                    cur = db.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM churches")
                    next_id = cur.fetchone()[0]
                    
                    denom = type_name(e['types'].split(',')[0])
                    
                    db.execute("""
                        INSERT INTO churches 
                            (id, name, city, country, latitude, longitude, taxonomy_id, 
                             landmark_type, source, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        next_id,
                        e['name'],
                        '',  # city not available from Pleiades directly
                        e['country'],
                        e['latitude'],
                        e['longitude'],
                        e['taxonomy_id'],
                        denom,
                        'pleiades',
                        e['uri'] + ' | ' + e.get('types', '')
                    ))
                    prov.churches_inserted += 1
                    
                except Exception as ex:
                    print(f"  ERROR: {e['name'][:40]} - {ex}")
            
            db.commit()
            print(f"  Batch {i//CHUNK_SIZE + 1}: {prov.churches_inserted} inserted...")
        
        prov.records_matched = len(new_entries)
    
    print(f"\n✓ Done: {prov.churches_inserted} Pleiades ancient sites imported")

def type_name(raw_type):
    """Convert place type to readable denomination."""
    names = {
        'temple': 'Ancient temple',
        'temple-2': 'Ancient temple',
        'sanctuary': 'Religious sanctuary',
        'shrine': 'Shrine',
        'altar': 'Altar',
        'grove': 'Sacred grove',
        'pyramid': 'Pyramid',
        'theatre': 'Ancient theatre',
        'spring': 'Sacred spring',
        'cave': 'Sacred cave',
        'stadion': 'Stadium',
        'gymnasium': 'Gymnasium',
        'stoa': 'Stoa',
        'treasury': 'Treasury',
        'tumulus': 'Tumulus / burial mound',
        'acropolis': 'Acropolis',
        'fountain': 'Fountain',
        'odeon': 'Odeon',
        'monument': 'Monument',
        'tomb': 'Tomb',
    }
    return names.get(raw_type, f'Ancient religious site ({raw_type})')

def guess_country(title, description):
    """Rough country guess from text - very approximate."""
    text = (title + ' ' + (description or '')).lower()
    country_map = {
        'italy': 'IT', 'italia': 'IT', 'rome': 'IT', 'pompeii': 'IT',
        'greece': 'GR', 'hellas': 'GR', 'athens': 'GR', 'crete': 'GR',
        'egypt': 'EG', 'egyptian': 'EG', 'alexandria': 'EG', 'thebes': 'EG',
        'france': 'FR', 'gaul': 'FR', 'massalia': 'FR',
        'spain': 'ES', 'hispania': 'ES', 'iberia': 'ES',
        'turkey': 'TR', 'turkey': 'TR', 'asia minor': 'TR', 'anatolia': 'TR',
        'iraq': 'IQ', 'mesopotamia': 'IQ', 'babylon': 'IQ',
        'iran': 'IR', 'persia': 'IR', 'parthia': 'IR',
        'syria': 'SY', 'levant': 'SY',
        'tunisia': 'TN', 'carthage': 'TN', 'north africa': 'TN',
        'england': 'GB', 'britain': 'GB', 'london': 'GB',
        'germany': 'DE', 'germania': 'DE',
        'portugal': 'PT', 'lusitania': 'PT',
        'china': 'CN', 'india': 'IN',
    }
    for key, code in country_map.items():
        if key in text:
            return code
    return ''

if __name__ == '__main__':
    main()
