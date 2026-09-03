#!/usr/bin/env python3
"""
Import German city POI datasets: Gelsenkirchen (Kirche + Gemeindezentrum), Norderstedt (Kirche)

Spatially matches against existing churches.db entries within 100m.
New churches get imported with full contact details.
Existing matches get enriched with contact info.
"""
import json
import sqlite3
import zipfile
import io
from datetime import datetime
from pathlib import Path
from collections import Counter

DB = Path(r'E:\grid\churches.db')
DATA_DIR = Path(r'E:\grid\data\de_city_pois')
SOURCE_NAME = 'de_city_poi_import'
CHUNK_SIZE = 100

def progress_bar(i, total, label='', width=40):
    pct = (i + 1) / total
    filled = int(width * pct)
    bar = '█' * filled + '░' * (width - filled)
    print(f'\r  {label} [{bar}] {pct*100:.0f}% ({i+1}/{total})', end='', flush=True)

def load_json(path):
    """Load JSON, handling both .json files and zipped .json."""
    if path.suffix == '.zip':
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            json_name = [n for n in names if n.endswith('.json')][0]
            with zf.open(json_name) as f:
                return json.load(io.TextIOWrapper(f, encoding='utf-8'))
    else:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

def main():
    db = sqlite3.connect(str(DB))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    c = db.cursor()

    print("GERMAN CITY POI IMPORT")
    print("=" * 60)

    # ── Load all datasets ──
    datasets = {}

    # Gelsenkirchen Kirche
    print("\n📥 Loading Gelsenkirchen Kirche...")
    gk = load_json(DATA_DIR / 'gelsenkirchen_kirche_json.zip')
    features = gk['features']
    print(f"  {len(features)} churches loaded")

    # Gelsenkirchen Gemeindezentrum
    print("📥 Loading Gelsenkirchen Gemeindezentrum...")
    gz = load_json(DATA_DIR / 'gelsenkirchen_gemeindezentrum_json.zip')
    features_gz = gz['features']
    print(f"  {len(features_gz)} gemeindezentren loaded")

    # Norderstedt Kirche
    print("📥 Loading Norderstedt Kirche...")
    nk = load_json(DATA_DIR / 'norderstedt_kirche.json')
    features_nk = nk['features']
    print(f"  {len(features_nk)} churches loaded")

    # ── Parse all into unified list ──
    all_pois = []

    # Gelsenkirchen Kirche
    for f in features:
        props = f['properties']
        coords = f['geometry']['coordinates']  # [lon, lat]
        all_pois.append({
            'source': 'gelsenkirchen_kirche',
            'name': props.get('Name', '').strip(),
            'lat': coords[1],
            'lon': coords[0],
            'address': props.get('Strasse', ''),
            'postal_code': str(props.get('PLZ', '')),
            'city': 'Gelsenkirchen',
            'phone': props.get('Telefon', ''),
            'fax': props.get('Fax', ''),
            'email': props.get('EMail', ''),
            'website': props.get('INTERNET', ''),
            'traeger': props.get('Traeger', ''),
            'art': props.get('ARTBEZ', ''),
            'info': props.get('Info', ''),
            'bezirk': props.get('Bezirk', ''),
            'stadtteil': props.get('Stadtteil', ''),
            'raw_props': props,
        })

    # Gelsenkirchen Gemeindezentrum
    for f in features_gz:
        props = f['properties']
        coords = f['geometry']['coordinates']
        all_pois.append({
            'source': 'gelsenkirchen_gemeindezentrum',
            'name': props.get('Name', '').strip(),
            'lat': coords[1],
            'lon': coords[0],
            'address': props.get('Strasse', ''),
            'postal_code': str(props.get('PLZ', '')),
            'city': 'Gelsenkirchen',
            'phone': props.get('Telefon', ''),
            'fax': props.get('Fax', ''),
            'email': props.get('EMail', ''),
            'website': props.get('INTERNET', ''),
            'traeger': props.get('Traeger', ''),
            'art': props.get('ARTBEZ', 'Gemeindezentrum'),
            'info': props.get('Info', ''),
            'bezirk': props.get('Bezirk', ''),
            'stadtteil': props.get('Stadtteil', ''),
            'raw_props': props,
        })

    # Norderstedt Kirche
    for f in features_nk:
        props = f['properties']
        coords = f['geometry']['coordinates']
        name = props.get('bezeich', '').strip()
        all_pois.append({
            'source': 'norderstedt_kirche',
            'name': name,
            'lat': coords[1],
            'lon': coords[0],
            'address': props.get('anschrift', ''),
            'postal_code': str(props.get('plz', '')),
            'city': 'Norderstedt',
            'phone': '',
            'fax': '',
            'email': '',
            'website': props.get('homepage', ''),
            'traeger': props.get('thema', ''),
            'art': props.get('thema', 'Kirche'),
            'info': '',
            'bezirk': '',
            'stadtteil': '',
            'raw_props': props,
        })

    print(f"\n📊 Total POIs loaded: {len(all_pois)}")

    # ── Spatial match against churches.db ──
    print("\n🔍 Spatial matching against churches.db (100m radius)...")

    c.execute("SELECT MAX(id) FROM churches")
    max_id = c.fetchone()[0] or 0

    matched = 0
    new_count = 0
    contact_added = 0

    for i, poi in enumerate(all_pois):
        progress_bar(i, len(all_pois), 'Matching')

        lat, lon = poi['lat'], poi['lon']

        # Find nearest church within 100m
        c.execute("""
            SELECT id, name, latitude, longitude,
                   (6371000 * acos(cos(radians(?)) * cos(radians(latitude)) *
                    cos(radians(longitude) - radians(?)) + sin(radians(?)) * sin(radians(latitude))))
                   AS distance
            FROM churches
            WHERE latitude IS NOT NULL
              AND latitude BETWEEN ? AND ?
              AND longitude BETWEEN ? AND ?
            ORDER BY distance
            LIMIT 1
        """, (lat, lon, lat, lat - 0.001, lat + 0.001, lon - 0.001, lon + 0.001))

        row = c.fetchone()
        distance = row[4] if row else None

        if row and distance is not None and distance <= 100:
            # Match found — enrich contacts
            church_id = row[0]
            matched += 1

            # Add contacts if not already present
            contacts_to_add = []
            if poi['phone']:
                contacts_to_add.append(('phone', poi['phone']))
            if poi['email']:
                contacts_to_add.append(('email', poi['email']))
            if poi['website']:
                contacts_to_add.append(('website', poi['website']))

            for ctype, cval in contacts_to_add:
                c.execute("""
                    SELECT COUNT(*) FROM church_contact_values
                    WHERE church_id=? AND contact_type=? AND value=?
                """, (church_id, ctype, cval))
                if c.fetchone()[0] == 0:
                    c.execute("""
                        INSERT INTO church_contact_values (church_id, contact_type, value, confidence, source, last_verified)
                        VALUES (?, ?, ?, 0.80, ?, ?)
                    """, (church_id, ctype, cval, SOURCE_NAME, datetime.now().isoformat()))
                    contact_added += 1

            print(f'\r  ✅ {church_id} | {row[1][:50]} | {poi["name"][:40]} | {distance:.0f}m | {len(contacts_to_add)} contacts')

        else:
            # New church — insert
            new_count += 1
            max_id += 1

            # Determine faith/tradition from traeger
            traeger_lower = poi['traeger'].lower()
            if 'kath' in traeger_lower:
                faith, tradition = 'Christian', 'Catholic'
            elif 'evang' in traeger_lower or 'prot' in traeger_lower or 'luth' in traeger_lower:
                faith, tradition = 'Christian', 'Protestant'
            elif 'muslim' in traeger_lower or 'islam' in traeger_lower or 'moschee' in traeger_lower:
                faith, tradition = 'Islam', 'Islam (general)'
            elif 'jüd' in traeger_lower or 'jud' in traeger_lower or 'synagoge' in traeger_lower:
                faith, tradition = 'Judaism', 'Rabbinic'
            elif 'zeugen jehovas' in traeger_lower or 'jehovah' in traeger_lower:
                faith, tradition = 'Christian', "Jehovah's Witnesses"
            elif 'freikirch' in traeger_lower or 'feg' in traeger_lower:
                faith, tradition = 'Christian', 'Protestant'
            elif 'baptist' in traeger_lower:
                faith, tradition = 'Christian', 'Baptist'
            elif 'orthodox' in traeger_lower:
                faith, tradition = 'Christian', 'Orthodox'
            else:
                faith, tradition = 'Christian', 'Protestant'  # default for Germany

            # Determine landmark_type
            art_lower = poi['art'].lower()
            name_lower = poi['name'].lower()
            if 'gemeindezentrum' in art_lower or 'gemeindezentrum' in name_lower:
                landmark_type = 'community_center'
            elif 'moschee' in art_lower or 'moschee' in name_lower:
                landmark_type = 'mosque'
            elif 'synagoge' in art_lower or 'synagoge' in name_lower:
                landmark_type = 'synagogue'
            else:
                landmark_type = 'church'

            full_address = f"{poi['address']}, {poi['postal_code']} {poi['city']}".strip(', ')

            c.execute("""
                INSERT INTO churches (id, name, latitude, longitude, address, zip, city,
                                     country, faith, tradition, landmark_type,
                                     source, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'DE', ?, ?, ?, ?, ?)
            """, (
                max_id, poi['name'], poi['lat'], poi['lon'],
                full_address, poi['postal_code'], poi['city'],
                faith, tradition, landmark_type,
                SOURCE_NAME, datetime.now().isoformat()
            ))

            # Add contacts
            contacts_added_local = 0
            if poi['phone']:
                c.execute("""
                    INSERT INTO church_contact_values (church_id, contact_type, value, confidence, source, last_verified)
                    VALUES (?, 'phone', ?, 0.80, ?, ?)
                """, (max_id, poi['phone'], SOURCE_NAME, datetime.now().isoformat()))
                contacts_added_local += 1
            if poi['email']:
                c.execute("""
                    INSERT INTO church_contact_values (church_id, contact_type, value, confidence, source, last_verified)
                    VALUES (?, 'email', ?, 0.80, ?, ?)
                """, (max_id, poi['email'], SOURCE_NAME, datetime.now().isoformat()))
                contacts_added_local += 1
            if poi['website']:
                c.execute("""
                    INSERT INTO church_contact_values (church_id, contact_type, value, confidence, source, last_verified)
                    VALUES (?, 'website', ?, 0.80, ?, ?)
                """, (max_id, poi['website'], SOURCE_NAME, datetime.now().isoformat()))
                contacts_added_local += 1

            contact_added += contacts_added_local
            print(f'\r  🆕 {max_id} | {poi["name"][:40]} | {poi["city"]} | {faith}/{tradition} | {contacts_added_local} contacts')

    print(f'\n  ✅ Done matching')

    # ── Summary ──
    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    print(f"  Total POIs processed: {len(all_pois)}")
    print(f"  Matched to existing:   {matched}")
    print(f"  New churches created:  {new_count}")
    print(f"  Contacts added:        {contact_added}")

    # ── Source breakdown ──
    sources = Counter(p['source'] for p in all_pois)
    print(f"\n  Source breakdown:")
    for src, cnt in sources.most_common():
        print(f"    {src}: {cnt}")

    db.commit()
    db.close()
    print(f"\n✅ Import complete. Changes committed.")

if __name__ == '__main__':
    main()
