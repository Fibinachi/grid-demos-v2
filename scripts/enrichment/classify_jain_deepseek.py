"""
DeepSeek batch classification for ~4,000 unclassified Jain entries.
~$6 total at DeepSeek pricing (~$0.14/M input tokens).

For each entry: name + landmark_type → tradition (Digambar/Shwetambar/Sthanakvasi)
+ refined landmark_type + any jain_affiliation.
"""
import sqlite3, json, time, os, re
from pathlib import Path
from collections import Counter

DB = "churches.db"
BATCH_SIZE = 100  # Entries per API call (grouped)
OUT = Path("outputs/enrichment")
OUT.mkdir(parents=True, exist_ok=True)

# DeepSeek API
DEEPSEEK_KEY = None
# Try common env vars / config locations
for key_name in ["DEEPSEEK_API_KEY", "DEEPSEEK_KEY"]:
    val = os.environ.get(key_name)
    if val:
        DEEPSEEK_KEY = val
        break

if not DEEPSEEK_KEY:
    # Try from local config
    config_path = Path.home() / ".deepseek" / "config.json"
    if config_path.exists():
        import json
        DEEPSEEK_KEY = json.loads(config_path.read_text()).get("api_key", "")

if not DEEPSEEK_KEY:
    print("No DeepSeek API key found. Set DEEPSEEK_API_KEY env var.")
    print("Using name-pattern fallback only.")
    DEEPSEEK_KEY = "MISSING"

def classify_batch(entries_batch):
    """Send a batch of entries to DeepSeek for classification."""
    if DEEPSEEK_KEY == "MISSING":
        return fallback_classify(entries_batch)
    
    prompt = """Classify each Jain religious site by tradition and landmark type.
For each entry, respond with JSON: {"tradition": "Digambar"|"Shwetambar"|"Sthanakvasi"|"Mixed"|"Unknown", "landmark_type": "temple"|"community_center"|"school"|"dharamshala"|"shrine"|"dining_hall"|"hospital"|"library"|"other", "jain_affiliation": "Gurdwara/Temple/Mandir/Upashraya/Stambh/Dharamshala/etc"}

Entries to classify:
"""
    for e in entries_batch:
        prompt += f"\n- ID {e['id']}: \"{e['name'][:120]}\" (current landmark: {e['landmark_type'] or 'none'})"
    
    prompt += "\n\nRespond ONLY with a JSON array."
    
    try:
        r = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 2000
            },
            timeout=30
        )
        if r.status_code == 200:
            content = r.json()["choices"][0]["message"]["content"]
            # Extract JSON array
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        else:
            print(f"  API error: {r.status_code}")
            return None
    except Exception as e:
        print(f"  Error: {e}")
        return None

def fallback_classify(entries_batch):
    """Simple heuristic fallback when no API key."""
    results = []
    for e in entries_batch:
        name = e['name'].upper()
        tradition = "Unknown"
        lm = e['landmark_type'] or "temple"
        
        if re.search(r'\bDIGAMBAR\b|\bDIGAMBER\b|\bDIG\.\b', name):
            tradition = "Digambar"
        elif re.search(r'\bSHWETAMBAR\b|\bSHWETAMBER\b|\bSHVETAMBAR\b|\bDERASAR\b', name):
            tradition = "Shwetambar"
        elif re.search(r'\bSTHANAK\b', name):
            tradition = "Sthanakvasi"
        
        # Fix bad landmark types
        if lm in ("church", "shrine", "basadi"):
            lm = "temple"
        elif lm in ("center", "ghat"):
            # Check name for clues
            if re.search(r'\bBHAVAN\b|\bSAMAJ\b|\bSANGH\b|\bSOCIETY\b', name):
                lm = "community_center"
            elif re.search(r'\bUPASHRAY\b|\bSTHANAK\b', name):
                lm = "community_center"
            elif re.search(r'\bDHARAMSHALA\b|\bDHARMSHALA\b|\bREST HOUSE\b', name):
                lm = "dharamshala"
            else:
                lm = "temple"
        elif lm == "Tirth":
            lm = "temple"
        
        results.append({
            "tradition": tradition,
            "landmark_type": lm,
            "jain_affiliation": "Temple"
        })
    return results

# Load unclassified entries
import requests
db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

entries = db.execute("""
    SELECT id, name, landmark_type, source
    FROM churches
    WHERE faith = 'Jain'
      AND (tradition IS NULL OR tradition = 'Jain' OR tradition = '')
    ORDER BY id
""").fetchall()

print(f"Unclassified Jain entries: {len(entries)}")

# Batch and classify
all_results = []
for i in range(0, len(entries), BATCH_SIZE):
    batch = entries[i:i+BATCH_SIZE]
    batch_dicts = [{"id": r["id"], "name": r["name"] or "", "landmark_type": r["landmark_type"] or ""} for r in batch]
    
    results = classify_batch(batch_dicts)
    if results and len(results) == len(batch):
        all_results.extend(results)
    else:
        # Fallback for failed batch
        all_results.extend(fallback_classify(batch_dicts))
    
    if (i // BATCH_SIZE) % 5 == 0:
        print(f"  Processed {min(i+BATCH_SIZE, len(entries))}/{len(entries)}...")
    
    time.sleep(0.5)  # Rate limit

# Apply results
updates = {0: [], 1: [], 2: []}  # tradition, landmark, affiliation
for entry, result in zip(entries, all_results):
    tradition = result.get("tradition", "Unknown")
    lm = result.get("landmark_type", "temple")
    
    if tradition not in ("Unknown",):
        db.execute("UPDATE churches SET tradition = ? WHERE id = ?", (tradition, entry["id"]))
        updates[0].append(entry["id"])
    
    if lm and lm != (entry["landmark_type"] or ""):
        db.execute("UPDATE churches SET landmark_type = ? WHERE id = ?", (lm, entry["id"]))
        updates[1].append(entry["id"])

db.commit()

# Summary
trad_counts = Counter()
lm_counts = Counter()
for r in all_results:
    trad_counts[r.get("tradition", "Unknown")] += 1
    lm_counts[r.get("landmark_type", "temple")] += 1

print(f"\n=== Results ===")
print(f"Processed: {len(all_results)}")
print(f"\nTradition breakdown:")
for t, c in trad_counts.most_common():
    print(f"  {t}: {c}")
print(f"\nLandmark types:")
for t, c in lm_counts.most_common():
    print(f"  {t}: {c}")

total_jain = db.execute("SELECT COUNT(*) FROM churches WHERE faith='Jain'").fetchone()[0]
classified = db.execute("SELECT COUNT(*) FROM churches WHERE faith='Jain' AND tradition NOT IN ('Jain','') AND tradition IS NOT NULL").fetchone()[0]
print(f"\nTotal Jain: {total_jain}")
print(f"Classified: {classified} ({classified/total_jain*100:.1f}%)")
print(f"Unclassified: {total_jain - classified}")

db.close()
