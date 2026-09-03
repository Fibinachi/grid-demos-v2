"""
Build Venezuela Catholic hierarchy: seats → dioceses → archdioceses → churches.

Phase 1: Fix state codes, identify cathedral seats, build archdiocese & diocese nodes
Phase 2: Map all VE Catholic churches to their diocese
Phase 3: Verify & log

Uses state code → name mapping + city-based disambiguation for multi-diocese states.
Matches the catholic_hierarchy schema pattern used for US and other countries.
"""
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from gw_db import connect

# ── State code → name mapping (OCEI codes from statoids.com) ──
OCEI_TO_STATE = {
    '01': 'Distrito Capital', '02': 'Amazonas', '03': 'Anzoátegui',
    '04': 'Apure', '05': 'Aragua', '06': 'Barinas', '07': 'Bolívar',
    '08': 'Carabobo', '09': 'Cojedes', '10': 'Delta Amacuro',
    '11': 'Falcón', '12': 'Guárico', '13': 'Lara', '14': 'Mérida',
    '15': 'Miranda', '16': 'Monagas', '17': 'Nueva Esparta',
    '18': 'Portuguesa', '19': 'Sucre', '20': 'Táchira', '21': 'Trujillo',
    '22': 'Yaracuy', '23': 'Zulia', '24': 'Vargas', '25': 'Dependencias Federales',
}

# ── Province name → Archdiocese name mapping (handles variants) ──
PROVINCE_ARCHDIOCESE = {
    'Caracas': 'Archdiocese of Caracas',
    'Maracaibo': 'Archdiocese of Maracaibo',
    'Mérida': 'Archdiocese of Mérida',
    'Valencia': 'Archdiocese of Valencia en Venezuela',
    'Barquisimeto': 'Archdiocese of Barquisimeto',
    'Ciudad Bolivar': 'Archdiocese of Ciudad Bolivar',
    'Cumana': 'Archdiocese of Cumana',
    'Coro': 'Archdiocese of Coro',
    'Calabozo': 'Archdiocese of Calabozo',
}

# ── Diocese definitions ──
# city_filter discriminates for states with multiple dioceses.
DIOCESES = {
    # Province: Caracas
    'Archdiocese of Caracas': {
        'cath_type': 'archdiocese', 'province': 'Caracas',
        'states': ['Distrito Capital', 'Miranda', 'Vargas', 'Dependencias Federales'],
        'seat_city': 'Caracas',
    },
    'Diocese of Guarenas': {
        'cath_type': 'diocese', 'province': 'Caracas',
        'states': ['Miranda'], 'city_filter': ['guarenas', 'guatire'],
        'seat_city': 'Guarenas',
    },
    'Diocese of La Guaira': {
        'cath_type': 'diocese', 'province': 'Caracas',
        'states': ['Vargas'], 'seat_city': 'La Guaira',
    },
    'Diocese of Los Teques': {
        'cath_type': 'diocese', 'province': 'Caracas',
        'states': ['Miranda'],
        'city_filter': ['los teques', 'san antonio de los altos', 'charallave',
                        'cua', 'ocumare del tuy', 'santa teresa', 'santa lucia'],
        'seat_city': 'Los Teques',
    },
    'Diocese of Petare': {
        'cath_type': 'diocese', 'province': 'Caracas',
        'states': ['Miranda'],
        'city_filter': ['petare', 'chacao', 'baruta', 'el hatillo'],
        'seat_city': 'Petare',
    },
    # Province: Maracaibo
    'Archdiocese of Maracaibo': {
        'cath_type': 'archdiocese', 'province': 'Maracaibo',
        'states': ['Zulia'], 'seat_city': 'Maracaibo',
    },
    'Diocese of Cabimas': {
        'cath_type': 'diocese', 'province': 'Maracaibo',
        'states': ['Zulia'],
        'city_filter': ['cabimas', 'ciudad ojeda', 'lagunillas', 'santa rita'],
        'seat_city': 'Cabimas',
    },
    'Diocese of El Vigia-San Carlos del Zulia': {
        'cath_type': 'diocese', 'province': 'Maracaibo',
        'states': ['Zulia'],
        'city_filter': ['el vigia', 'san carlos del zulia', 'santa barbara'],
        'seat_city': 'El Vigia',
    },
    'Diocese of Machiques': {
        'cath_type': 'diocese', 'province': 'Maracaibo',
        'states': ['Zulia'],
        'city_filter': ['machiques', 'rosario de perija'],
        'seat_city': 'Machiques',
    },
    # Province: Mérida
    'Archdiocese of Mérida': {
        'cath_type': 'archdiocese', 'province': 'Mérida',
        'states': ['Mérida'], 'seat_city': 'Mérida',
    },
    'Diocese of Barinas': {
        'cath_type': 'diocese', 'province': 'Mérida',
        'states': ['Barinas'], 'seat_city': 'Barinas',
    },
    'Diocese of Guasdualito': {
        'cath_type': 'diocese', 'province': 'Mérida',
        'states': ['Apure'], 'city_filter': ['guasdualito', 'elorza'],
        'seat_city': 'Guasdualito',
    },
    'Diocese of San Cristobal de Venezuela': {
        'cath_type': 'diocese', 'province': 'Mérida',
        'states': ['Táchira'], 'seat_city': 'San Cristóbal',
    },
    'Diocese of Trujillo': {
        'cath_type': 'diocese', 'province': 'Mérida',
        'states': ['Trujillo'], 'seat_city': 'Trujillo',
    },
    # Province: Valencia
    'Archdiocese of Valencia en Venezuela': {
        'cath_type': 'archdiocese', 'province': 'Valencia',
        'states': ['Carabobo'], 'seat_city': 'Valencia',
    },
    'Diocese of Maracay': {
        'cath_type': 'diocese', 'province': 'Valencia',
        'states': ['Aragua'], 'seat_city': 'Maracay',
    },
    'Diocese of Puerto Cabello': {
        'cath_type': 'diocese', 'province': 'Valencia',
        'states': ['Carabobo'], 'city_filter': ['puerto cabello', 'moron'],
        'seat_city': 'Puerto Cabello',
    },
    'Diocese of San Carlos de Venezuela': {
        'cath_type': 'diocese', 'province': 'Valencia',
        'states': ['Cojedes'], 'seat_city': 'San Carlos',
    },
    # Province: Barquisimeto
    'Archdiocese of Barquisimeto': {
        'cath_type': 'archdiocese', 'province': 'Barquisimeto',
        'states': ['Lara'], 'seat_city': 'Barquisimeto',
    },
    'Diocese of Acarigua-Araure': {
        'cath_type': 'diocese', 'province': 'Barquisimeto',
        'states': ['Portuguesa'], 'city_filter': ['acarigua', 'araure'],
        'seat_city': 'Acarigua',
    },
    'Diocese of Carora': {
        'cath_type': 'diocese', 'province': 'Barquisimeto',
        'states': ['Lara'], 'city_filter': ['carora'],
        'seat_city': 'Carora',
    },
    'Diocese of Guanare': {
        'cath_type': 'diocese', 'province': 'Barquisimeto',
        'states': ['Portuguesa'], 'city_filter': ['guanare'],
        'seat_city': 'Guanare',
    },
    'Diocese of San Felipe': {
        'cath_type': 'diocese', 'province': 'Barquisimeto',
        'states': ['Yaracuy'], 'seat_city': 'San Felipe',
    },
    # Province: Ciudad Bolivar
    'Archdiocese of Ciudad Bolivar': {
        'cath_type': 'archdiocese', 'province': 'Ciudad Bolivar',
        'states': ['Bolívar'], 'seat_city': 'Ciudad Bolívar',
    },
    'Diocese of Ciudad Guayana': {
        'cath_type': 'diocese', 'province': 'Ciudad Bolivar',
        'states': ['Bolívar'],
        'city_filter': ['ciudad guayana', 'puerto ordaz', 'san felix', 'upata'],
        'seat_city': 'Ciudad Guayana',
    },
    'Diocese of Maturin': {
        'cath_type': 'diocese', 'province': 'Ciudad Bolivar',
        'states': ['Monagas'], 'seat_city': 'Maturín',
    },
    # Province: Cumana
    'Archdiocese of Cumana': {
        'cath_type': 'archdiocese', 'province': 'Cumana',
        'states': ['Sucre'], 'seat_city': 'Cumaná',
    },
    'Diocese of Barcelona': {
        'cath_type': 'diocese', 'province': 'Cumana',
        'states': ['Anzoátegui'],
        'city_filter': ['barcelona', 'puerto la cruz', 'lecheria', 'guanta'],
        'seat_city': 'Barcelona',
    },
    'Diocese of Carupano': {
        'cath_type': 'diocese', 'province': 'Cumana',
        'states': ['Sucre'],
        'city_filter': ['carupano', 'rio caribe', 'guiria'],
        'seat_city': 'Carúpano',
    },
    'Diocese of El Tigre': {
        'cath_type': 'diocese', 'province': 'Cumana',
        'states': ['Anzoátegui'],
        'city_filter': ['el tigre', 'el tigrito', 'san jose de guanipa', 'anaco', 'cantaura'],
        'seat_city': 'El Tigre',
    },
    'Diocese of Margarita': {
        'cath_type': 'diocese', 'province': 'Cumana',
        'states': ['Nueva Esparta'], 'seat_city': 'La Asunción',
    },
    # Province: Coro
    'Archdiocese of Coro': {
        'cath_type': 'archdiocese', 'province': 'Coro',
        'states': ['Falcón'], 'seat_city': 'Coro',
    },
    'Diocese of Punto Fijo': {
        'cath_type': 'diocese', 'province': 'Coro',
        'states': ['Falcón'],
        'city_filter': ['punto fijo', 'judibana', 'punta cardon'],
        'seat_city': 'Punto Fijo',
    },
    # Province: Calabozo
    'Archdiocese of Calabozo': {
        'cath_type': 'archdiocese', 'province': 'Calabozo',
        'states': ['Guárico'], 'seat_city': 'Calabozo',
    },
    'Diocese of San Fernando de Apure': {
        'cath_type': 'diocese', 'province': 'Calabozo',
        'states': ['Apure'], 'seat_city': 'San Fernando de Apure',
    },
    'Diocese of Valle de la Pascua': {
        'cath_type': 'diocese', 'province': 'Calabozo',
        'states': ['Guárico'],
        'city_filter': ['valle de la pascua', 'zaraza', 'tucupido'],
        'seat_city': 'Valle de la Pascua',
    },
    # Exempt (directly under Holy See)
    'Vicariate Apostolic of Caroni': {
        'cath_type': 'vicariate', 'province': 'Exempt (Holy See)',
        'states': ['Bolívar'],
        'city_filter': ['santa elena de uairen', 'la gran sabana', 'ikabaru'],
        'seat_city': 'Santa Elena de Uairén',
    },
    'Vicariate Apostolic of Puerto Ayacucho': {
        'cath_type': 'vicariate', 'province': 'Exempt (Holy See)',
        'states': ['Amazonas'], 'seat_city': 'Puerto Ayacucho',
    },
    'Vicariate Apostolic of Tucupita': {
        'cath_type': 'vicariate', 'province': 'Exempt (Holy See)',
        'states': ['Delta Amacuro'], 'seat_city': 'Tucupita',
    },
}


def find_diocese(city, state_name):
    """Match a church to its diocese based on state + city."""
    city_lower = (city or '').lower()
    candidates = []
    for dname, dinfo in DIOCESES.items():
        if state_name in dinfo.get('states', []):
            candidates.append((dname, dinfo))

    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0][0]

    # Multi-diocese state — filter by city
    for dname, dinfo in candidates:
        for cf in dinfo.get('city_filter', []):
            if cf in city_lower:
                return dname

    # Default: return archdiocese
    for dname, dinfo in candidates:
        if dinfo['cath_type'] == 'archdiocese':
            return dname
    return candidates[0][0]


def find_diocese_fallback(city):
    """When state is garbage, try matching city to a known diocese."""
    city_lower = (city or '').lower()
    # Check if city matches any diocese seat city or city_filter
    for dname, dinfo in DIOCESES.items():
        if city_lower == dinfo.get('seat_city', '').lower():
            return dname
        for cf in dinfo.get('city_filter', []):
            if cf == city_lower or cf in city_lower:
                return dname
    
    # Hardcoded mappings for VE cities with garbage state codes
    VE_CITY_FALLBACK = {
        'la guaira': 'Diocese of La Guaira',
        'catia la mar': 'Diocese of La Guaira',
        'macuto': 'Diocese of La Guaira',
        'maiquetia': 'Diocese of La Guaira',
        'caraballeda': 'Diocese of La Guaira',
        'naiguata': 'Diocese of La Guaira',
        'el junko': 'Diocese of La Guaira',
        'caricuao': 'Archdiocese of Caracas',
        'caracas': 'Archdiocese of Caracas',
        'petare': 'Diocese of Petare',
        'chacao': 'Diocese of Petare',
        'baruta': 'Diocese of Petare',
        'los teques': 'Diocese of Los Teques',
        'guarenas': 'Diocese of Guarenas',
        'guatire': 'Diocese of Guarenas',
        'santa teresa': 'Diocese of Los Teques',
        'ocumare del tuy': 'Diocese of Los Teques',
        'cua': 'Diocese of Los Teques',
        'charallave': 'Diocese of Los Teques',
        'puerto cabello': 'Diocese of Puerto Cabello',
        'valencia': 'Archdiocese of Valencia en Venezuela',
        'maracay': 'Diocese of Maracay',
        'maracaibo': 'Archdiocese of Maracaibo',
        'cabimas': 'Diocese of Cabimas',
        'ciudad ojeda': 'Diocese of Cabimas',
        'barquisimeto': 'Archdiocese of Barquisimeto',
        'coro': 'Archdiocese of Coro',
        'punto fijo': 'Diocese of Punto Fijo',
        'merida': 'Archdiocese of Mérida',
        'san cristobal': 'Diocese of San Cristobal de Venezuela',
        'trujillo': 'Diocese of Trujillo',
        'barinas': 'Diocese of Barinas',
        'barcelona': 'Diocese of Barcelona',
        'puerto la cruz': 'Diocese of Barcelona',
        'ciudad bolivar': 'Archdiocese of Ciudad Bolivar',
        'ciudad guayana': 'Diocese of Ciudad Guayana',
        'puerto ordaz': 'Diocese of Ciudad Guayana',
        'maturin': 'Diocese of Maturin',
        'cumana': 'Archdiocese of Cumana',
        'carupano': 'Diocese of Carupano',
        'el tigre': 'Diocese of El Tigre',
        'porlamar': 'Diocese of Margarita',
        'la asuncion': 'Diocese of Margarita',
        'san fernando de apure': 'Diocese of San Fernando de Apure',
        'san carlos': 'Diocese of San Carlos de Venezuela',
        'guanare': 'Diocese of Guanare',
        'acarigua': 'Diocese of Acarigua-Araure',
        'puerto ayacucho': 'Vicariate Apostolic of Puerto Ayacucho',
        'tucupita': 'Vicariate Apostolic of Tucupita',
    }
    return VE_CITY_FALLBACK.get(city_lower)


def match_seat(churches_by_city, dio_name, dio_info):
    """Find the best cathedral seat match for a diocese."""
    seat_city = dio_info.get('seat_city', '').lower()
    candidates = churches_by_city.get(seat_city, [])
    if not candidates:
        return None
    # Prefer entries with cathedral/basilica in name
    for r in candidates:
        name_lower = (r[1] or '').lower()
        if any(kw in name_lower for kw in ['catedral', 'cathedral', 'basilica', 'basílica']):
            return r
    return candidates[0]


def main():
    db = connect()

    print("=" * 70)
    print("VE CATHOLIC HIERARCHY BUILDER")
    print("Seats -> Dioceses -> Archdioceses -> Churches")
    print("=" * 70)

    # ── Step 0: Fix numeric state codes ──
    print("\n-- Step 0: Fix numeric state codes --")
    total_fixed = 0
    for code, name in OCEI_TO_STATE.items():
        cur = db.execute("SELECT COUNT(*) FROM churches WHERE country='VE' AND state=?", (code,))
        cnt = cur.fetchone()[0]
        if cnt > 0:
            db.execute("UPDATE churches SET state=? WHERE country='VE' AND state=?",
                       (name, code))
            total_fixed += cnt
    db.commit()
    print(f"  Fixed {total_fixed} numeric state codes -> state names")

    # ── Step 1: Load all VE Catholic churches ──
    print("\n-- Step 1: Load VE Catholic churches --")
    rows = db.execute("""
        SELECT c.rowid, c.name, c.city, c.state, c.latitude, c.longitude,
               c.source, t.full_path
        FROM churches c
        JOIN taxonomy t ON c.taxonomy_id = t.id
        WHERE c.country='VE' AND t.full_path LIKE '%Catholic%'
    """).fetchall()

    print(f"  VE Catholic churches: {len(rows):,}")

    # Index by city (lowercase) for seat matching
    churches_by_city = defaultdict(list)
    for r in rows:
        city = (r[2] or '').lower()
        churches_by_city[city].append(r)
    print(f"  Unique cities: {len(churches_by_city)}")

    # ── Step 2: Clear existing VE entries ──
    existing = db.execute("""
        SELECT COUNT(*) FROM catholic_hierarchy ch
        JOIN churches c ON ch.church_id = c.rowid
        WHERE c.country='VE'
    """).fetchone()[0]
    existing_virtual = db.execute(
        "SELECT COUNT(*) FROM catholic_hierarchy WHERE country='VE' AND church_id IS NULL"
    ).fetchone()[0]
    print(f"\n-- Step 2: Clear existing VE hierarchy ({existing} church + {existing_virtual} virtual) --")
    if existing > 0:
        db.execute("DELETE FROM catholic_hierarchy WHERE church_id IN "
                   "(SELECT c.rowid FROM churches c WHERE c.country='VE')")
    if existing_virtual > 0:
        db.execute("DELETE FROM catholic_hierarchy WHERE country='VE' AND church_id IS NULL")
    db.commit()
    print("  Cleared")

    # ── Step 3: Insert archdiocese nodes (seats first!) ──
    print(f"\n-- Step 3: Archdiocese Nodes (seats first) --")
    archdiocese_ids = {}
    seat_church_ids = set()  # track which churches are seats

    for dio_name, dio_info in DIOCESES.items():
        if dio_info['cath_type'] != 'archdiocese':
            continue

        seat = match_seat(churches_by_city, dio_name, dio_info)
        church_id = seat[0] if seat else None
        lat = seat[4] if seat else None
        lon = seat[5] if seat else None
        city = seat[2] if seat else dio_info.get('seat_city')

        db.execute("""
            INSERT INTO catholic_hierarchy
            (church_id, name, cath_type, province, diocese, archdiocese,
             relationship, city, state, country, lat, lon, notes)
            VALUES (?, ?, 'archdiocese', ?, NULL, NULL,
                    'belongs_to_province', ?, ?, 'VE', ?, ?, ?)
        """, (church_id, dio_name, dio_info['province'],
              city, dio_info.get('states', [''])[0], lat, lon,
              f"Seat: {dio_info.get('seat_city','?')}" +
              (f" | church_id={church_id}" if church_id else " | virtual")))

        hier_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        archdiocese_ids[dio_name] = hier_id
        if church_id:
            seat_church_ids.add(church_id)

        icon = "OK" if seat else "+"
        print(f"  [{icon}] {dio_name} | seat={'id='+str(church_id) if church_id else 'virtual'} "
              f"| hier_id={hier_id}")

    db.commit()

    # ── Step 4: Insert diocese/vicariate nodes ──
    print(f"\n-- Step 4: Diocese & Vicariate Nodes --")
    diocese_ids = {}

    for dio_name, dio_info in DIOCESES.items():
        if dio_info['cath_type'] == 'archdiocese':
            continue

        seat = match_seat(churches_by_city, dio_name, dio_info)
        church_id = seat[0] if seat else None
        lat = seat[4] if seat else None
        lon = seat[5] if seat else None
        city = seat[2] if seat else dio_info.get('seat_city')

        # Parent: archdiocese, or Holy See (1) for exempt
        if dio_info['province'].startswith('Exempt'):
            parent_id = 1  # Holy See
            parent_arch = None
        else:
            parent_arch = PROVINCE_ARCHDIOCESE.get(dio_info['province'],
                            f"Archdiocese of {dio_info['province']}")
            parent_id = archdiocese_ids.get(parent_arch)

        db.execute("""
            INSERT INTO catholic_hierarchy
            (parent_id, church_id, name, cath_type, province, diocese, archdiocese,
             relationship, city, state, country, lat, lon, notes)
            VALUES (?, ?, ?, ?, ?, NULL, ?,
                    'suffragan_of', ?, ?, 'VE', ?, ?, ?)
        """, (parent_id, church_id, dio_name, dio_info['cath_type'],
              dio_info['province'], parent_arch,
              city, dio_info.get('states', [''])[0], lat, lon,
              f"Seat: {dio_info.get('seat_city','?')}" +
              (f" | church_id={church_id}" if church_id else " | virtual")))

        hier_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        diocese_ids[dio_name] = hier_id
        if church_id:
            seat_church_ids.add(church_id)

        icon = "OK" if seat else "+"
        print(f"  [{icon}] {dio_name} ({dio_info['cath_type']}) | "
              f"seat={'id='+str(church_id) if church_id else 'virtual'} | "
              f"parent={parent_id} | hier_id={hier_id}")

    db.commit()

    # ── Step 5: Map churches to dioceses ──
    print(f"\n-- Step 5: Church -> Diocese Mapping ({len(rows):,} churches) --")
    print(f"  Seat churches excluded: {len(seat_church_ids)}")

    matched = 0
    unmatched = 0
    batch = []
    CHUNK = 500

    for i, r in enumerate(rows):
        rowid = r[0]
        city = r[2] or ''
        state = r[3] or ''

        # Skip seat churches (already inserted as archdiocese/diocese nodes)
        if rowid in seat_church_ids:
            continue

        diocese = find_diocese(city, state)
        if not diocese:
            diocese = find_diocese_fallback(city)  # Try city-only match for garbage state codes

        if diocese:
            parent_id = diocese_ids.get(diocese) or archdiocese_ids.get(diocese)
            if parent_id:
                batch.append((rowid, parent_id, diocese))
                matched += 1
            else:
                unmatched += 1
        else:
            unmatched += 1

        if len(batch) >= CHUNK:
            db.executemany("""
                INSERT INTO catholic_hierarchy
                (church_id, parent_id, name, cath_type, diocese, relationship, country)
                VALUES (?, ?, ?, 'church', ?, 'belongs_to', 'VE')
            """, [(b[0], b[1], b[2], b[2]) for b in batch])
            db.commit()
            batch = []

        if (i + 1) % 300 == 0:
            pct = (i + 1) / len(rows) * 100
            print(f"  {i+1:,}/{len(rows):,} ({pct:.0f}%) | matched={matched:,} "
                  f"| unmatched={unmatched}")

    # Flush remaining
    if batch:
        db.executemany("""
            INSERT INTO catholic_hierarchy
            (church_id, parent_id, name, cath_type, diocese, relationship, country)
            VALUES (?, ?, ?, 'church', ?, 'belongs_to', 'VE')
        """, [(b[0], b[1], b[2], b[2]) for b in batch])
        db.commit()

    total_mapped = matched + len(seat_church_ids)
    print(f"\n  Done! churches mapped: {matched:,} | seats: {len(seat_church_ids)} "
          f"| unmatched: {unmatched} | total linked: {total_mapped:,}")

    # ── Step 6: Verify ──
    print(f"\n-- Step 6: Verification --")
    for htype in ['archdiocese', 'diocese', 'vicariate', 'church']:
        cnt = db.execute("""
            SELECT COUNT(*) FROM catholic_hierarchy WHERE country='VE' AND cath_type=?
        """, (htype,)).fetchone()[0]
        print(f"  {htype}: {cnt:,}")

    total = db.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE country='VE'").fetchone()[0]
    print(f"  TOTAL VE hierarchy: {total:,}")

    covered = db.execute("""
        SELECT COUNT(DISTINCT church_id) FROM catholic_hierarchy
        WHERE country='VE' AND church_id IS NOT NULL
    """).fetchone()[0]
    print(f"  Coverage: {covered:,} / {len(rows):,} ({covered/len(rows)*100:.1f}%)")

    # ── Log provenance ──
    arch_cnt = len([d for d in DIOCESES.values() if d['cath_type'] == 'archdiocese'])
    dio_cnt = len([d for d in DIOCESES.values() if d['cath_type'] != 'archdiocese'])
    db.execute("""
        INSERT INTO provenance_log
        (source, script_name, churches_updated, churches_inserted,
         fields_populated, status, notes)
        VALUES ('build_ve_hierarchy', 'scripts/enrichment/build_ve_hierarchy.py',
                ?, ?, 'catholic_hierarchy', 'completed',
                ?)
    """, (total_mapped, total_mapped,
          f"VE Catholic hierarchy: {len(seat_church_ids)} seats + {matched} churches "
          f"across {arch_cnt} archdioceses/{dio_cnt} dioceses-vicariates. "
          f"{unmatched} unmatched."))
    db.commit()

    print(f"\nDone! Provenance logged.")
    db.close()


if __name__ == '__main__':
    main()
