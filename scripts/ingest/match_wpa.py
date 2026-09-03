"""
WPA → churches.db Matcher v2
Handles records with and without city/state.
Matches by: name+city+state (best), name+state (good), name only (fuzzy).
Enriches building_year for matched records.
"""
import sqlite3, re
from collections import defaultdict

WPA_DB = 'E:/grid/wpa.db'
CHURCHES_DB = 'E:/grid/churches.db'

def normalize_name(name):
    if not name: return ''
    n = name.lower().strip()
    n = re.sub(r'[|{}[\]~`@#$%^*+=/\\<>]', ' ', n)
    n = re.sub(r'\s+', ' ', n).strip()
    n = re.sub(r'\bst\.?\s+', 'saint ', n)
    n = re.sub(r'\bmt\.?\s+', 'mount ', n)
    n = re.sub(r'\([^)]*\)', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n

def normalize_city(city):
    if not city: return ''
    return re.sub(r'[^a-z\s]', '', city.lower().strip())

def name_similarity(a, b):
    if not a or not b: return 0.0
    wa = set(a.split()); wb = set(b.split())
    if not wa or not wb: return 0.0
    return len(wa & wb) / len(wa | wb)

def main():
    wpa = sqlite3.connect(WPA_DB)
    churches = sqlite3.connect(CHURCHES_DB)
    
    print('Building churches index...')
    by_state = defaultdict(list)
    by_name_stub = defaultdict(list)
    
    for row in churches.execute(
        "SELECT id, name, city, state, building_year FROM churches WHERE name != ''"
    ):
        cid, name, city, state, byear = row
        nn = normalize_name(name)
        if state:
            by_state[state].append({
                'id': cid, 'name': name, 'norm_name': nn,
                'city': normalize_city(city), 'building_year': byear
            })
        if len(nn) >= 6:
            by_name_stub[nn[:6]].append({
                'id': cid, 'name': name, 'norm_name': nn,
                'state': state, 'city': normalize_city(city), 'building_year': byear
            })
    
    total = sum(len(v) for v in by_state.values())
    print(f'  {total:,} churches indexed across {len(by_state)} states')
    
    wpa_recs = wpa.execute('''
        SELECT r.id, r.church_name, r.city, r.county, r.state, r.denomination,
               r.confidence, v.year, v.ia_id
        FROM wpa_records r
        JOIN wpa_volumes v ON r.volume_id = v.id
        WHERE r.church_name != ''
    ''').fetchall()
    
    print(f'Matching {len(wpa_recs):,} WPA records...\n')
    
    matched = 0; unmatched = 0; enriched = 0
    match_batch = []; enrich_batch = []
    
    for i, rec in enumerate(wpa_recs):
        wpa_id, wpa_name, wpa_city, wpa_county, wpa_state, wpa_denom, conf, vol_year, ia_id = rec
        nn = normalize_name(wpa_name)
        nc = normalize_city(wpa_city)
        
        if len(nn) < 4:
            unmatched += 1
            continue
        
        best = None; best_score = 0.0
        
        if wpa_state and nc:
            candidates = [c for c in by_state.get(wpa_state, []) if c['city'] == nc]
            for cand in candidates[:30]:
                score = name_similarity(nn, cand['norm_name'])
                if score > best_score:
                    best_score = score; best = cand
        
        if best_score < 0.7 and wpa_state:
            for cand in by_state.get(wpa_state, [])[:100]:
                score = name_similarity(nn, cand['norm_name'])
                if score > best_score:
                    best_score = score; best = cand
        
        if best_score < 0.5 and len(nn) >= 6:
            for cand in by_name_stub.get(nn[:6], [])[:20]:
                score = name_similarity(nn, cand['norm_name'])
                if wpa_state and cand['state'] and wpa_state != cand['state']:
                    score -= 0.2
                if score > best_score:
                    best_score = score; best = cand
        
        if best_score >= 0.80:
            method = 'name_city_state' if (wpa_state and nc) else 'name_state' if wpa_state else 'name_fuzzy'
            match_batch.append((wpa_id, best['id'], method, round(best_score, 3), 0, ''))
            matched += 1
            if vol_year and (not best['building_year'] or vol_year < best['building_year']):
                enrich_batch.append((vol_year, 'wpa_historical_records_survey', best['id']))
                enriched += 1
        elif best_score >= 0.55:
            match_batch.append((wpa_id, best['id'], 'fuzzy_low', round(best_score, 3), 0, 'needs review'))
            matched += 1
        else:
            unmatched += 1
        
        if (i + 1) % 5000 == 0:
            wpa.executemany(
                'INSERT INTO wpa_matches (wpa_record_id, church_id, match_method, match_score, verified, notes) VALUES (?,?,?,?,?,?)',
                match_batch
            ); match_batch = []
            if enrich_batch:
                churches.executemany(
                    'UPDATE churches SET building_year=?, building_source=? WHERE id=? AND (building_year IS NULL OR building_year > ?)',
                    [(y, s, cid, y) for y, s, cid in enrich_batch]
                ); enrich_batch = []
            wpa.commit(); churches.commit()
            print(f'  [{i+1:>6,}/{len(wpa_recs):,}] matched={matched:,}  new={unmatched:,}  bldg_year={enriched:,}', flush=True)
    
    if match_batch:
        wpa.executemany(
            'INSERT INTO wpa_matches (wpa_record_id, church_id, match_method, match_score, verified, notes) VALUES (?,?,?,?,?,?)',
            match_batch
        )
    if enrich_batch:
        churches.executemany(
            'UPDATE churches SET building_year=?, building_source=? WHERE id=? AND (building_year IS NULL OR building_year > ?)',
            [(y, s, cid, y) for y, s, cid in enrich_batch]
        )
    wpa.commit(); churches.commit()
    
    print(f'\n{"="*60}')
    print(f'MATCHING COMPLETE')
    print(f'  Total:      {len(wpa_recs):>8,}')
    print(f'  Matched:    {matched:>8,}')
    print(f'  New:        {unmatched:>8,}')
    print(f'  Bldg years: {enriched:>8,}')
    
    for method, count in wpa.execute(
        "SELECT match_method, COUNT(*) FROM wpa_matches GROUP BY match_method ORDER BY COUNT(*) DESC"
    ).fetchall():
        print(f'    {method:25s} {count:>8,}')
    
    wpa.close(); churches.close()
    print('\nDone.')

if __name__ == '__main__':
    main()
