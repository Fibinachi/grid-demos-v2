"""
Batch classify all remaining unclassified Jain entries via DeepSeek.
Batches 40 names per API call for speed. Single DB connection to avoid locks.
"""
import sqlite3, json, requests, os, time, re
from pathlib import Path
from collections import Counter

DB = "churches.db"
API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    import subprocess
    r = subprocess.run(["powershell", "-c", "[Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY','User')"], capture_output=True, text=True)
    API_KEY = r.stdout.strip()
BATCH_SIZE = 40
OUT = Path("outputs/enrichment")
OUT.mkdir(parents=True, exist_ok=True)

if not API_KEY:
    print("Set DEEPSEEK_API_KEY")
    exit(1)


def classify_batch(names):
    names_list = list(names)
    prompt = f"""Classify each of these {len(names_list)} Jain religious site names. Return ONLY a JSON array, one object per name in the same order.

For each entry return: {{\"tradition\": \"Digambar|Shwetambar|Sthanakvasi|Mixed|Unclear\", \"landmark_type\": \"temple|community_center|school|dharamshala|shrine|prayer_hall|dining_hall|hospital|library|museum|meditation_center|other\", \"is_english\": true/false, \"english_name\": \"transliteration or same if English\"}}

Names:
{chr(10).join(f"{i+1}. {n}" for i, n in enumerate(names_list))}"""

    try:
        r = requests.post("https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat",
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.0, "max_tokens": 3000}, timeout=60)
        content = r.json()["choices"][0]["message"]["content"]
        content = re.sub(r"^```json\s*|```\s*$", "", content.strip())
        return json.loads(content)
    except Exception as e:
        return [{"tradition": "ERROR", "landmark_type": "ERROR", "is_english": True,
                 "english_name": n, "error": str(e)[:60]} for n in names_list]


db = sqlite3.connect(DB, timeout=30)
db.execute("PRAGMA journal_mode=WAL")
db.row_factory = sqlite3.Row

entries = db.execute("""SELECT id, name FROM churches
    WHERE faith='Jain' AND (tradition IS NULL OR tradition='Jain' OR tradition='')
    ORDER BY RANDOM()""").fetchall()

print(f"Remaining: {len(entries)}, batches of {BATCH_SIZE} = ~{len(entries)//BATCH_SIZE+1} calls")

traditions_count = Counter()
landmark_count = Counter()
errors = 0
start = time.time()

for bs in range(0, len(entries), BATCH_SIZE):
    batch = entries[bs:bs+BATCH_SIZE]
    pairs = [(row["name"] or "", row["id"]) for row in batch]
    results = classify_batch([p[0] for p in pairs])

    for i, (name, rid) in enumerate(pairs):
        res = results[i] if i < len(results) else {"tradition": "ERROR", "landmark_type": "ERROR", "error": "missing"}
        if res.get("error"):
            errors += 1
            print(f"[{bs+i+1}/{len(entries)}] ID={rid} | {name[:50]:50s} | ERROR: {str(res['error'])[:40]}")
        else:
            trad = str(res.get("tradition", "Unclear"))
            lm = str(res.get("landmark_type", "other"))
            eng = res.get("is_english", True)
            trans = str(res.get("english_name", name))
            traditions_count[trad] += 1
            landmark_count[lm] += 1
            note = f" -> {trans[:40]}" if not eng and trans != name else ""
            print(f"[{bs+i+1}/{len(entries)}] ID={rid} | {name[:50]:50s} | {trad:15s} | {lm:20s}{note}")
            db.execute("UPDATE churches SET tradition=?, landmark_type=? WHERE id=?", (trad, lm, rid))

    db.commit()
    elapsed = time.time() - start
    rate = (bs + BATCH_SIZE) / elapsed if elapsed > 0 else 0
    eta = (len(entries) - bs - BATCH_SIZE) / rate if rate > 0 else 0
    print(f"  [{bs+BATCH_SIZE}/{len(entries)}] {rate:.0f}/sec, ETA {eta/60:.0f}min")
    time.sleep(0.5)

db.close()

print(f"\n{'='*60}\nJAIN CLASSIFICATION COMPLETE\n{'='*60}")
print(f"Processed: {len(entries)}, Errors: {errors} ({errors/len(entries)*100:.1f}%)")
print("\nTradition breakdown:")
for t, c in traditions_count.most_common():
    print(f"  {t:15s} {c:5d}")
print("\nLandmark type breakdown:")
for t, c in landmark_count.most_common():
    print(f"  {t:20s} {c:5d}")

db2 = sqlite3.connect(DB)
total = db2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jain'").fetchone()[0]
classified = db2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jain' AND tradition NOT IN ('Jain','','')").fetchone()[0]
db2.close()
print(f"\nTotal Jain: {total}, Classified: {classified} ({classified/total*100:.1f}%)")
