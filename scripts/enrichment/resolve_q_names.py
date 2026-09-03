"""Resolve Wikidata Q-code church names to human-readable labels.

Strategy:
1. Fetch labels via wbgetentities API (no language filter = all languages)
2. Pick best label: English > major European > any other language
3. Fall back to description if no label exists
4. Batch 50 Q-IDs per request
"""
import sqlite3, requests, time, sys

DB = r'e:\grid\churches.db'
BATCH_SIZE = 50
RATE = 0.15  # seconds between API calls (~400 calls/hr, under Wikidata limits)

# Language preference for picking labels
LANG_PREFS = ['en', 'de', 'fr', 'es', 'it', 'pt', 'nl', 'pl', 'ru', 'ar', 'zh', 'ja', 'tr', 'id', 'uk']

def pick_label(labels):
    """Pick the best label from a dict of {lang: {language:, value:}}."""
    if not labels:
        return None
    for lang in LANG_PREFS:
        if lang in labels:
            return labels[lang]['value']
    # Any language
    first = next(iter(labels.values()))
    return first['value']

def pick_description(descriptions):
    """Pick best description as fallback name."""
    if not descriptions:
        return None
    for lang in LANG_PREFS:
        if lang in descriptions:
            return descriptions[lang]['value']
    first = next(iter(descriptions.values()))
    return first['value']

def main():
    db = sqlite3.connect(DB)
    
    # Get unique Q-IDs
    qids = [r[0] for r in db.execute("""
        SELECT DISTINCT name FROM churches 
        WHERE name GLOB 'Q[0-9]*' AND source='holy_sites_import'
        ORDER BY name
    """).fetchall()]
    
    print(f"Unique Q-IDs to resolve: {len(qids):,}")
    print(f"API calls: {len(qids)//BATCH_SIZE + 1}")
    print(f"ETA: {(len(qids)//BATCH_SIZE + 1) * RATE / 60:.1f} min at {RATE}s delay")
    
    session = requests.Session()
    session.headers.update({'User-Agent': 'GRID/1.0 (charlesaprescottjr@gmail.com)'})
    
    resolved = {}
    failed = []
    no_label = []
    total = len(qids)
    
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
                            # Use description as fallback
                            desc = pick_description(descs)
                            if desc:
                                resolved[qid] = desc
                                no_label.append(qid)
                            else:
                                failed.append(qid)
                        else:
                            failed.append(qid)
                else:
                    print(f"  ERROR: no entities in response: {list(data.keys())}")
                    failed.extend(batch)
            elif r.status_code == 429:
                print(f"  Rate limited at batch {i//BATCH_SIZE}, sleeping 30s...")
                time.sleep(30)
                # Retry this batch
                continue
            else:
                print(f"  HTTP {r.status_code} at batch {i//BATCH_SIZE}")
                failed.extend(batch)
        except Exception as e:
            print(f"  Exception at batch {i//BATCH_SIZE}: {e}")
            failed.extend(batch)
            time.sleep(2)
        
        # Progress
        done = i + len(batch)
        if done % 500 == 0 or done >= total:
            print(f"  Progress: {done:,}/{total:,} ({100*done/total:.0f}%) — resolved {len(resolved):,}, failed {len(failed):,}, no-label {len(no_label):,}")
        
        time.sleep(RATE)
    
    print(f"\n{'='*60}")
    print(f"RESULTS:")
    print(f"  Resolved (has label): {len(resolved):,}")
    print(f"  Resolved (desc fallback): {len(no_label):,}")
    print(f"  Failed (no label/desc): {len(failed):,}")
    print(f"  Total: {len(resolved) + len(failed):,}")
    
    # Apply updates
    if resolved:
        print(f"\nApplying {len(resolved):,} name updates to DB...")
        updated = 0
        for qid, label in resolved.items():
            c = db.execute("UPDATE churches SET name=? WHERE name=? AND source='holy_sites_import'", (label, qid))
            updated += c.rowcount
        
        db.commit()
        print(f"  Updated {updated:,} rows")
    
    # Show some examples
    print(f"\nSample resolutions:")
    for i, (qid, label) in enumerate(list(resolved.items())[:20]):
        print(f"  {qid} -> '{label}'")
    
    # Show failures
    if failed:
        print(f"\nSample failures:")
        for qid in failed[:10]:
            print(f"  {qid}")
    
    # Cleanup
    remaining = db.execute("SELECT COUNT(*) FROM churches WHERE name GLOB 'Q[0-9]*' AND source='holy_sites_import'").fetchone()[0]
    print(f"\nRemaining Q-names after fix: {remaining:,}")
    
    db.close()

if __name__ == '__main__':
    main()
