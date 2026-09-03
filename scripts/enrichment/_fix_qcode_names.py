"""
Fix 39,861 churches with Q-code names — resolve via Wikidata API.
Batch resolves labels for Q-IDs that were stored as names during import.
"""
import sqlite3, json, urllib.request, time
from collections import defaultdict

DB = "E:/grid/churches.db"
BATCH = 500
COMMIT_INTERVAL = 5000

print("Loading Q-code entries...")
db = sqlite3.connect(DB)
db.execute("PRAGMA journal_mode=WAL")
db.execute("PRAGMA busy_timeout=60000")

# Get unique Q-codes used as names
q_codes = db.execute(
    "SELECT DISTINCT name FROM churches WHERE name GLOB 'Q[0-9]*' AND LENGTH(name) BETWEEN 3 AND 12 ORDER BY name"
).fetchall()

unique_qs = [r[0] for r in q_codes]
print(f"Unique Q-codes to resolve: {len(unique_qs)}")
print(f"Total rows with Q-code names: {db.execute('SELECT COUNT(1) FROM churches WHERE name GLOB ? AND LENGTH(name) BETWEEN 3 AND 12', ('Q[0-9]*',)).fetchone()[0]:,}")

# Resolve labels via Wikidata API
print("\nResolving labels...")
labels = {}
failed = 0
resolved = 0

for i, qid in enumerate(unique_qs):
    if (i + 1) % 100 == 0:
        print(f"  {i+1}/{len(unique_qs)}: resolved={resolved}, failed={failed}")

    url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    req = urllib.request.Request(url, headers={"User-Agent": "GRID/1.0 (charlesaprescottjr@gmail.com)"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        entity = data.get("entities", {}).get(qid, {})
        label = entity.get("labels", {}).get("en", {}).get("value", "")
        if label:
            labels[qid] = label
            resolved += 1
            print(f"  ✅ {qid} -> {label[:60]}")
        else:
            any_label = list(entity.get("labels", {}).values())
            if any_label:
                labels[qid] = any_label[0]["value"]
                resolved += 1
                print(f"  🌐 {qid} -> {any_label[0]['value'][:60]} (non-EN)")
            else:
                failed += 1
                print(f"  ❌ {qid} — no label found")
    except Exception as e:
        failed += 1
        print(f"  ❌ {qid} — {str(e)[:40]}")
    time.sleep(0.1)

print(f"\nResolved: {resolved}, Failed: {failed}")
print(f"Coverage: {resolved*100/len(unique_qs):.1f}%")

# Apply fixes
if labels:
    print("\nApplying fixes...")
    updated = 0
    for qid, label in labels.items():
        # Only update if label is different and non-empty
        if label and label != qid:
            cnt = db.execute(
                "UPDATE churches SET name=? WHERE name=?",
                (label, qid)
            ).rowcount
            updated += cnt
            if updated % 5000 == 0:
                db.commit()
                print(f"  Updated {updated:,} rows...")

    db.commit()
    print(f"\nTotal rows updated: {updated:,}")

# Count still remaining
remaining = db.execute(
    "SELECT COUNT(1) FROM churches WHERE name GLOB 'Q[0-9]*' AND LENGTH(name) BETWEEN 3 AND 12"
).fetchone()[0]
print(f"Remaining Q-code names: {remaining:,}")

db.close()
print("Done!")
