#!/usr/bin/env python3
"""Scrape Jehovah's Witness Kingdom Halls and LDS meeting houses from Overture Maps.

Iterates over all US states via bounding boxes, queries Overture Places,
filters by category + name, outputs JSONL with dedup.
"""
import overturemaps, json, os, sys, time

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# State bounding boxes (rough - covers land area well)
STATE_BBOXES = {
    "AK":[-179.0,51.0,-130.0,72.0],"AL":[-88.5,30.2,-84.9,35.0],"AR":[-94.6,33.0,-89.6,36.6],
    "AZ":[-114.8,31.3,-109.0,37.0],"CA":[-124.5,32.5,-114.1,42.0],"CO":[-109.1,37.0,-102.0,41.0],
    "CT":[-73.7,41.0,-71.8,42.1],"DE":[-75.8,38.4,-75.0,39.9],"FL":[-87.6,24.5,-80.0,31.0],
    "GA":[-85.6,30.4,-80.8,35.0],"HI":[-160.3,18.9,-154.8,22.3],"IA":[-96.7,40.4,-90.1,43.5],
    "ID":[-117.2,42.0,-111.0,49.0],"IL":[-91.5,36.9,-87.4,42.5],"IN":[-88.1,37.8,-84.8,41.8],
    "KS":[-102.1,37.0,-94.6,40.0],"KY":[-89.5,36.5,-81.9,39.1],"LA":[-94.1,29.0,-88.8,33.0],
    "MA":[-73.5,41.2,-70.0,42.9],"MD":[-79.5,37.9,-75.0,39.7],"ME":[-71.1,42.9,-66.9,47.5],
    "MI":[-90.5,41.7,-82.1,47.5],"MN":[-97.2,43.5,-89.5,49.4],"MO":[-95.8,36.0,-89.1,40.6],
    "MS":[-91.7,30.2,-88.1,35.0],"MT":[-116.0,44.4,-104.0,49.0],"NC":[-84.3,33.8,-75.5,36.6],
    "ND":[-104.1,45.9,-96.6,49.0],"NE":[-104.1,40.0,-95.3,43.0],"NH":[-72.6,42.7,-70.7,45.3],
    "NJ":[-75.6,38.9,-73.9,41.4],"NM":[-109.1,31.3,-103.0,37.0],"NV":[-120.0,35.0,-114.0,42.0],
    "NY":[-79.8,40.5,-71.9,45.0],"OH":[-84.8,38.4,-80.5,41.7],"OK":[-103.0,33.6,-94.4,37.0],
    "OR":[-124.6,42.0,-116.5,46.3],"PA":[-80.5,39.7,-74.7,42.3],"RI":[-71.9,41.1,-71.1,42.0],
    "SC":[-83.4,32.0,-78.5,35.2],"SD":[-104.1,42.5,-96.4,45.9],"TN":[-90.3,35.0,-81.6,36.7],
    "TX":[-106.6,25.8,-93.5,36.5],"UT":[-114.1,37.0,-109.0,42.0],"VA":[-83.7,36.5,-75.2,39.5],
    "VT":[-73.4,42.7,-71.5,45.0],"WA":[-124.8,45.5,-117.0,49.0],"WI":[-92.9,42.5,-86.8,47.0],
    "WV":[-82.6,37.2,-77.7,40.6],"WY":[-111.2,41.0,-104.0,45.0],
    "DC":[-77.2,38.8,-76.9,39.0],
}


def extract_address(addr_list):
    """Extract address from Overture addresses field (list/array of dicts)."""
    if addr_list is None:
        return {}, "", "", "", ""
    try:
        if len(addr_list) == 0:
            return {}, "", "", "", ""
        a = addr_list[0]
    except (TypeError, IndexError):
        return {}, "", "", "", ""
    if not isinstance(a, dict):
        return {}, "", "", "", ""
    freeform = a.get('freeform', '') or ''
    city = a.get('locality', '') or ''
    state = a.get('region', '') or ''
    zipcode = a.get('postcode', '') or ''
    return a, freeform, city, state, zipcode


def is_jw(categories, names):
    """Check if place is Jehovah's Witness."""
    if isinstance(categories, dict):
        if categories.get('primary') == 'jehovahs_witness_kingdom_hall':
            return True
    elif isinstance(categories, (list, tuple)):
        for c in categories:
            if isinstance(c, dict) and c.get('primary') == 'jehovahs_witness_kingdom_hall':
                return True
    # Name fallback
    if isinstance(names, dict):
        for v in names.values():
            if v and isinstance(v, str):
                vl = v.lower()
                if 'jehovah' in vl or 'kingdom hall' in vl:
                    return True
    elif isinstance(names, (list, tuple)):
        for v in names:
            if v and isinstance(v, str) and ('jehovah' in v.lower() or 'kingdom hall' in v.lower()):
                return True
    return False


def is_lds(names):
    """Check if place is LDS (Church of Jesus Christ of Latter-day Saints)."""
    if isinstance(names, dict):
        for v in names.values():
            if v and isinstance(v, str):
                if 'church of jesus christ' in v.lower() and 'latter-day' in v.lower():
                    return True
    elif isinstance(names, (list, tuple)):
        for v in names:
            if v and isinstance(v, str) and 'church of jesus christ' in v.lower() and 'latter-day' in v.lower():
                return True
    return False


def scrape_state(st, bbox):
    """Query Overture for a single state. Returns (jw_list, lds_list)."""
    reader = overturemaps.record_batch_reader(overture_type='place', bbox=bbox)
    df = reader.read_pandas()
    
    # Vectorized: extract primary category
    df['prim_cat'] = df['categories'].apply(
        lambda c: c.get('primary') if isinstance(c, dict) else ''
    )
    
    # Vectorized: extract name as string for searching
    df['name_str'] = df['names'].apply(
        lambda n: str(n.get('primary', '')).lower() if isinstance(n, dict) else ''
    )
    
    # JW: category-based
    jw_mask = df['prim_cat'] == 'jehovahs_witness_kingdom_hall'
    
    # JW: name fallback (for entries without proper category)
    jw_name_mask = df['name_str'].str.contains('jehovah|kingdom hall', na=False)
    jw_mask = jw_mask | (~jw_mask & jw_name_mask)
    
    # LDS: name contains "Church of Jesus Christ" + exclude non-LDS matches
    lds_mask = df['name_str'].str.contains(r'church of jesus christ.*latter.day|latter.day saint', na=False)
    
    # Process JW results
    jw_recs = []
    for _, r in df[jw_mask].iterrows():
        ids = r.get('id', '')
        names = r.get('names', {}) or {}
        name = names.get('primary', names.get('common', '')) if isinstance(names, dict) else ''
        addresses = r.get('addresses')
        _, freeform, city, state_r, zipcode = extract_address(addresses)
        phones = r.get('phones')
        phone = str(phones[0]) if isinstance(phones, (list, tuple)) and len(phones) > 0 else ''
        websites = r.get('websites')
        website = str(websites[0]) if isinstance(websites, (list, tuple)) and len(websites) > 0 else ''
        jw_recs.append({
            'id': ids, 'name': name, 'address': freeform, 'city': city,
            'state': state_r or st, 'zip': zipcode, 'phone': phone,
            'website': website, 'faith': 'jw',
        })
    
    # Process LDS results
    lds_recs = []
    for _, r in df[lds_mask].iterrows():
        ids = r.get('id', '')
        names = r.get('names', {}) or {}
        name = names.get('primary', names.get('common', '')) if isinstance(names, dict) else ''
        addresses = r.get('addresses')
        _, freeform, city, state_r, zipcode = extract_address(addresses)
        phones = r.get('phones')
        phone = str(phones[0]) if isinstance(phones, (list, tuple)) and len(phones) > 0 else ''
        websites = r.get('websites')
        website = str(websites[0]) if isinstance(websites, (list, tuple)) and len(websites) > 0 else ''
        lds_recs.append({
            'id': ids, 'name': name, 'address': freeform, 'city': city,
            'state': state_r or st, 'zip': zipcode, 'phone': phone,
            'website': website, 'faith': 'lds',
        })
    
    return jw_recs, lds_recs


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', default='', help='Single state abbrev')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('-o', '--output', default='')
    parser.add_argument('--limit', type=int, default=0, help='Limit to first N states')
    args = parser.parse_args()
    
    states = sorted(STATE_BBOXES.keys())
    if args.state:
        wanted = [s.strip().upper() for s in args.state.split(',')]
        states = [s for s in states if s in wanted]
    if args.limit:
        states = states[:args.limit]
    
    output = args.output or os.path.join(PROJECT_DIR, 'data', 'denom', 'overture_jw_lds.jsonl')
    os.makedirs(os.path.dirname(output), exist_ok=True)
    
    print(f'=== Overture Maps — JW Kingdom Halls + LDS Meeting Houses ===')
    print(f'{len(states)} states')
    print()
    
    all_jw, all_lds = [], []
    jw_ids, lds_ids = set(), set()
    errors = 0
    
    for si, st in enumerate(states):
        print(f'  [{si+1:2d}/{len(states)}] {st}...', end=' ', flush=True)
        t0 = time.time()
        try:
            jw, lds = scrape_state(st, STATE_BBOXES[st])
            elapsed = time.time() - t0
            
            jw_new = [r for r in jw if r['id'] not in jw_ids]
            for r in jw_new: jw_ids.add(r['id'])
            all_jw.extend(jw_new)
            
            lds_new = [r for r in lds if r['id'] not in lds_ids]
            for r in lds_new: lds_ids.add(r['id'])
            all_lds.extend(lds_new)
            
            print(f'{len(jw)} JW, {len(lds)} LDS ({elapsed:.0f}s)')
            
            # Write incrementally
            with open(output, 'a', encoding='utf-8') as f:
                for r in jw_new + lds_new:
                    f.write(json.dumps(r) + '\n')
                    
        except Exception as e:
            errors += 1
            print(f'ERR: {e} ({time.time()-t0:.0f}s)')
    
    print(f'\n=== RESULTS ===')
    print(f'Total JW Kingdom Halls: {len(all_jw):,}')
    print(f'Total LDS meeting houses: {len(all_lds):,}')
    print(f'Grand total: {len(all_jw) + len(all_lds):,}')
    print(f'Errors: {errors}')
    print(f'Saved to: {output}')
    
    if all_jw:
        with_addr = sum(1 for r in all_jw if r.get('address'))
        with_phone = sum(1 for r in all_jw if r.get('phone'))
        print(f'\nJW samples:')
        for r in all_jw[:5]:
            print(f'  {r["name"][:50]:50s} | {r.get("address",""):30s} | {r.get("city",""):20s} {r.get("state","")}')
    
    if all_lds:
        with_addr = sum(1 for r in all_lds if r.get('address'))
        with_phone = sum(1 for r in all_lds if r.get('phone'))
        print(f'\nLDS samples:')
        for r in all_lds[:5]:
            print(f'  {r["name"][:50]:50s} | {r.get("address",""):30s} | {r.get("city",""):20s} {r.get("state","")}')
    
    print('\nDone!')


if __name__ == '__main__':
    main()
