"""Resolve Wikidata Q-code church names to human-readable labels — V2 with batching.

Phase 1: Resolve all Q-IDs via Wikidata API, save to JSON
Phase 2: Batch-update churches table from JSON
"""
import sqlite3, requests, time, json, sys, os

DB = r'e:\grid\churches.db'
CACHE_FILE = r'e:\grid\outputs\q_names_resolved.json'
BATCH_SIZE = 50
RATE = 0.15

LANG_PREFS = ['en', 'de', 'fr', 'es', 'it', 'pt', 'nl', 'pl', 'ru', 'ar', 'zh', 'ja', 'tr', 'id', 'uk']

def pick_label(labels):
    if not labels:
        return None
    for lang in LANG_PREFS:
        if lang in labels:
            return labels[lang]['value']
    return next(iter(labels.values()))['value']

def pick_description(descriptions):
    if not descriptions:
        return None
    for lang in LANG_PREFS:
        if lang in descriptions:
            return descriptions[lang]['value']
    return next(iter(descriptions.values()))['value']

def phase1_resolve():
    """Resolve all Q-IDs via Wikidata API."""
    db = sqlite3.connect(DB)
    
    qids = [r[0] for r in db.execute("""
        SELECT DISTINCT name FROM churches 
        WHERE name GLOB 'Q[0-9][0-9][0-9][0-9][0-9]*' AND source='holy_sites_import'
        ORDER BY name
    """).fetchall()]
    db.close()
    
    if not qids:
        print("No Q-code names to resolve!")
        return {}
    
    print(f"Unique Q-IDs to resolve: {len(qids):,}")
    print(f"API calls: {len(qids)//BATCH_SIZE + 1}")
    
    session = requests.Session()
    session.headers.update({'User-Agent': 'GRID/1.0 (charlesaprescottjr@gmail.com)'})
    
    resolved = {}
    failed = []
    total = len(qids)
    errors = 0
    
    for i in range(0, total, BATCH_SIZE):
        batch = qids[i:i+BATCH_SIZE]
        ids_str = '|'.join(batch)
        
        try:
            r = session.get('https://www.wikidata.org/w/api.php', params={
                'action': 'wbgetentities',
                'ids': ids_str,
                'props': 'labels|descriptions',
                'format': 'json'
            }, timeout=30)
            
            if r.status_code == 200:
                data = r.json()
                if 'entities' in data:
                    for qid, entity in data['entities'].items():
                        labels = entity.get('labels', {})
                        descs = entity.get('descriptions', {})
                        
                        label = pick_label(labels)
                        if label:
                            resolved[qid] = label
                        elif descs:
                            desc = pick_description(descs)
                            if desc:
                                resolved[qid] = f"[{desc}]"
                            else:
                                failed.append(qid)
                        else:
                            failed.append(qid)
                elif 'error' in data:
                    errors += 1
                    if errors <= 3:
                        print(f"  API error at batch {i//BATCH_SIZE}: {data['error'].get('info', 'unknown')}")
                    failed.extend(batch)
            elif r.status_code == 429:
                print(f"  Rate limited, sleeping 30s...")
                time.sleep(30)
                continue
            else:
                print(f"  HTTP {r.status_code} at batch {i//BATCH_SIZE}")
                failed.extend(batch)
        except Exception as e:
            print(f"  Exception at batch {i//BATCH_SIZE}: {e}")
            failed.extend(batch)
            time.sleep(2)
        
        done = i + len(batch)
        if done % 500 == 0 or done >= total:
            print(f"  Progress: {done:,}/{total:,} ({100*done/total:.0f}%) - {len(resolved):,} resolved, {len(failed):,} failed")
        
        time.sleep(RATE)
    
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump({'resolved': resolved, 'failed': failed}, f, ensure_ascii=False, indent=2)
    
    print(f"\nSaved to {CACHE_FILE}")
    print(f"Resolved: {len(resolved):,} | Failed: {len(failed):,}")
    
    return resolved

def phase2_apply(resolved):
    """Apply resolved names to DB using temp table + JOIN."""
    if not resolved:
        print("Nothing to apply.")
        return
    
    db = sqlite3.connect(DB)
    db.execute('PRAGMA journal_mode=WAL')
    
    print(f"\nApplying {len(resolved):,} name updates...")
    
    db.execute("CREATE TEMP TABLE IF NOT EXISTS _q_names (qid TEXT PRIMARY KEY, label TEXT)")
    db.execute("DELETE FROM _q_names")
    
    CHUNK = 500
    items = list(resolved.items())
    for i in range(0, len(items), CHUNK):
        batch = items[i:i+CHUNK]
        db.executemany("INSERT OR REPLACE INTO _q_names VALUES (?, ?)", batch)
    
    db.commit()
    
    updated = db.execute("""
        UPDATE churches SET name = (
            SELECT label FROM _q_names WHERE qid = churches.name
        )
        WHERE name IN (SELECT qid FROM _q_names)
        AND source = 'holy_sites_import'
    """).rowcount
    
    db.commit()
    print(f"  Updated {updated:,} rows")
    
    remaining = db.execute("SELECT COUNT(*) FROM churches WHERE name GLOB 'Q[0-9][0-9][0-9][0-9][0-9]*' AND source='holy_sites_import'").fetchone()[0]
    print(f"  Remaining Q-names: {remaining:,}")
    
    print(f"\nSample resolutions:")
    for r in db.execute("""
        SELECT id, name, country FROM churches 
        WHERE source='holy_sites_import' 
        AND name NOT GLOB 'Q[0-9][0-9][0-9][0-9][0-9]*'
        AND id IN (2315632, 2315633, 2313350, 2310287)
        LIMIT 10
    """).fetchall():
        print(f"  ID={r[0]} name='{r[1]}' ({r[2]})")
    
    db.close()

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--apply-only':
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        phase2_apply(data['resolved'])
    else:
        resolved = phase1_resolve()
        phase2_apply(resolved)
