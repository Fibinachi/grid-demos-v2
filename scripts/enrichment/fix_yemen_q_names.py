"""
Fix Q-code names in Yemen (and globally for Wikidata-sourced entries).
Then launch focused reverse geocode for Yemen.
"""
import sqlite3, requests, time, json, os

DB = r'e:\grid\churches.db'
CACHE = r'e:\grid\outputs\q_names_yemen.json'

# Phase 1: Count and resolve Q-code names where source is a Wikidata URL
db = sqlite3.connect(DB)

# Count Q-named entries with Wikidata URL sources (not holy_sites_import — those already fixed)
total_q = db.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE name GLOB 'Q[0-9][0-9][0-9][0-9][0-9]*' 
    AND source LIKE 'https://www.wikidata%'
""").fetchone()[0]

print(f"Q-code named entries with Wikidata URL source: {total_q:,}")

if total_q == 0:
    print("Nothing to fix!")
    db.close()
    exit(0)

# Get unique Q-IDs
qids = [r[0] for r in db.execute("""
    SELECT DISTINCT name FROM churches 
    WHERE name GLOB 'Q[0-9][0-9][0-9][0-9][0-9]*' 
    AND source LIKE 'https://www.wikidata%'
    ORDER BY name
""").fetchall()]

print(f"Unique Q-IDs: {len(qids):,}")

# Resolve via Wikidata API (same as before)
BATCH = 50
LANG_PREFS = ['en', 'de', 'fr', 'es', 'ar', 'it', 'pt', 'nl', 'ru', 'zh', 'ja', 'tr', 'id', 'uk']

def pick_label(labels):
    if not labels: return None
    for lang in LANG_PREFS:
        if lang in labels: return labels[lang]['value']
    return next(iter(labels.values()))['value']

session = requests.Session()
session.headers.update({'User-Agent': 'GRID/1.0 (charlesaprescottjr@gmail.com)'})

resolved = {}
failed = []

for i in range(0, len(qids), BATCH):
    batch = qids[i:i+BATCH]
    ids_str = '|'.join(batch)
    
    try:
        r = session.get('https://www.wikidata.org/w/api.php', params={
            'action': 'wbgetentities', 'ids': ids_str,
            'props': 'labels|descriptions', 'format': 'json'
        }, timeout=30)
        
        if r.status_code == 200:
            data = r.json()
            if 'entities' in data:
                for qid, entity in data['entities'].items():
                    labels = entity.get('labels', {})
                    label = pick_label(labels)
                    if label:
                        resolved[qid] = label
                    else:
                        descs = entity.get('descriptions', {})
                        for lang in LANG_PREFS:
                            if lang in descs:
                                resolved[qid] = f"[{descs[lang]['value']}]"
                                break
                        if qid not in resolved:
                            failed.append(qid)
        elif r.status_code == 429:
            time.sleep(30)
            continue
    except Exception as e:
        if i % 500 == 0:
            print(f"  Error at batch {i//BATCH}: {e}")
        time.sleep(2)
    
    if (i + BATCH) % 500 == 0 or (i + BATCH) >= len(qids):
        print(f"  {min(i+BATCH, len(qids)):,}/{len(qids):,} — {len(resolved):,} resolved, {len(failed):,} failed")
    
    time.sleep(0.1)

print(f"\nResolved: {len(resolved):,} | Failed: {len(failed):,}")

# Save cache
os.makedirs(os.path.dirname(CACHE), exist_ok=True)
with open(CACHE, 'w', encoding='utf-8') as f:
    json.dump({'resolved': resolved, 'failed': failed}, f, ensure_ascii=False)

# Apply to DB
if resolved:
    db.execute("CREATE TEMP TABLE IF NOT EXISTS _q_fix (qid TEXT PRIMARY KEY, label TEXT)")
    db.execute("DELETE FROM _q_fix")
    
    items = list(resolved.items())
    for i in range(0, len(items), 500):
        db.executemany("INSERT OR REPLACE INTO _q_fix VALUES (?, ?)", items[i:i+500])
    
    updated = db.execute("""
        UPDATE churches SET name = (SELECT label FROM _q_fix WHERE qid = churches.name)
        WHERE name IN (SELECT qid FROM _q_fix)
        AND source LIKE 'https://www.wikidata%'
    """).rowcount
    
    db.commit()
    print(f"Updated {updated:,} names")

# Yemen-specific stats after fix
ye_q_left = db.execute("SELECT COUNT(*) FROM churches WHERE country='YE' AND name GLOB 'Q[0-9][0-9][0-9][0-9][0-9]*'").fetchone()[0]
print(f"\nYemen Q-names remaining after fix: {ye_q_left:,}")

# Show fixed examples
print("\nFixed Yemen names:")
for r in db.execute("""
    SELECT id, name, city FROM churches WHERE country='YE' 
    AND name NOT GLOB 'Q[0-9][0-9][0-9][0-9][0-9]*'
    AND source LIKE 'https://www.wikidata%'
    LIMIT 10
""").fetchall():
    print(f"  #{r[0]} '{r[1][:70]}' city={r[2]}")

# Show still unresolved
if ye_q_left > 0:
    print(f"\nStill Q-named in Yemen:")
    for r in db.execute("""
        SELECT id, name FROM churches WHERE country='YE' 
        AND name GLOB 'Q[0-9][0-9][0-9][0-9][0-9]*'
        LIMIT 5
    """).fetchall():
        print(f"  #{r[0]} {r[1]}")

db.close()
print("\nDone. Ready for reverse geocode.")
