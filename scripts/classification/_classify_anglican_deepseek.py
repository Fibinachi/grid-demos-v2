"""
DeepSeek batch classifier for ALL Anglican communion entries.
Does in one pass per entry:
1. Verify if actually Anglican (or Catholic, Methodist, etc.)
2. Normalize name (St->Saint, drop trailing Church, proper case)
3. Set correct landmark_type

Batches 40 entries per API call. Single DB connection.
82K entries = ~2,069 API calls at ~$0.26 total.
"""
import sqlite3, json, requests, os, time, re, sys
from pathlib import Path
from collections import Counter

DB = "churches.db"
API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    import subprocess
    r = subprocess.run(["powershell", "-c", "[Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY','User')"], capture_output=True, text=True)
    API_KEY = r.stdout.strip()
BATCH_SIZE = 40
LOG_SOURCE = "deepseek_anglican_scan"
OUT = Path("outputs/enrichment")
OUT.mkdir(parents=True, exist_ok=True)

if not API_KEY:
    print("Set DEEPSEEK_API_KEY")
    exit(1)

ANGLICAN_TAX_IDS = [13, 74, 75, 76, 77, 78, 79, 80, 81, 82]
CATHOLIC_ID = 3

def classify_batch(items):
    """items: list of (name, landmark_type, country, tradition)
    Returns: list of dicts with is_anglican, correct_faith, normalized_name, landmark_type, confidence
    """
    lines = []
    for i, (name, lm, country, trad, city) in enumerate(items):
        lines.append(f'{i+1}. name="{name}" | type={lm or "unknown"} | country={country or "unknown"} | tradition={trad or "unknown"}')
    
    prompt = f"""You are classifying religious sites from the Anglican Communion dataset. Many entries may NOT be Anglican - they were included by name matching and need verification.

For each entry, determine:
1. **is_anglican**: Is this genuinely Anglican/Episcopal/Church of England/Anglican Church of Canada/etc?
2. **correct_faith**: Be SPECIFIC. For Anglican entries, identify the exact tradition: "Episcopal" (US Episcopal Church), "Church of England" (England/GB), "Anglican Church of Canada", "Anglican Church of Australia", "Church of Ireland", "Scottish Episcopal Church", "Church in Wales", "Anglican Church of Kenya", "Anglican Church of Nigeria", "Church of Uganda", "Anglican Church of Southern Africa", "Episcopal Church in the Philippines", "Anglican Church of Papua New Guinea", "Anglican Church in Aotearoa New Zealand and Polynesia", "Anglican Church of Tanzania", "Episcopal Church of South Sudan", "Anglican Church of Congo", "Anglican Church of Rwanda", "Church of Bangladesh", "Church of Pakistan", "Church of North India", "Church of South India", "Anglican Church in Japan", "Anglican Church of Korea", "Hong Kong Anglican Church", "Church of Melanesia", "Anglican Church of Myanmar", "Reformed Episcopal Church", "Anglican Church in North America (ACNA)", "Free Episcopal", "Charismatic Episcopal", or if truly generic just "Anglican".
If NOT Anglican, give the specific denomination: "Catholic", "Baptist", "Southern Baptist", "United Methodist", "African Methodist Episcopal (AME)", "Lutheran (ELCA)", "Lutheran (LCMS)", "Presbyterian (PCUSA)", "Orthodox", "Pentecostal", "Evangelical", "Other Christian", "Non-Christian".
3. **normalized_name**: CRITICAL - Clean the name following these STRICT rules:
   - ALWAYS translate non-English names to English for the normalized_name field. The original non-English name will be saved separately.
   - ALWAYS strip hierarchy/administrative prefixes like "Episcopal Diocese of", "Diocese of", "Province of", "Protestant Episcopal Church in", "Protestant Episcopal Church of", "Parish of", "Vestry of", "Rector of", "Rector Wardens Vestrymen of", "Board of", "Convention of", "Society of", "Trustees of", "Missionary District of", "General Council of", "General Theological Seminary of", "Friends of" - these are organizational structures, not site names
   - ALWAYS strip trailing location/place suffixes - town/city names, state codes (NC, MA, NY, etc.), "of [Place]" patterns at the end. The address field already has the location. E.g. "Saint John's Episcopal Tuckahoe" -> "Saint John's Episcopal", "Emmanuel Episcopal Holmesburg" -> "Emmanuel Episcopal", "Good Shepherd Tryon" -> "Good Shepherd", "Saint James Episcopal of Kittrell NC" -> "Saint James Episcopal"
   - ALWAYS expand "St" or "St." to "Saint" (BUT keep as "Street" when preceded by a number like "3rd St" or "42nd St")
   - REMOVE "Church" from the END ONLY when the word before it is possessive (ending in "'s" or "s'"), e.g. "Saint Paul's Church" -> "Saint Paul's" (possessive implies it), but KEEP "Church" in all other cases: "Seventh Day Adventist Church" stays "Seventh Day Adventist Church", "City of Refuge Foursquare Church" stays "City of Refuge Foursquare Church"
   - Fix capitalization to proper case for saint names
   - Examples: "ST. PAUL'S CHURCH" -> "Saint Paul's", "St. John's Episcopal Church" -> "Saint John's Episcopal", "Church of England" -> "Church of England", "3rd St. Baptist Church" -> "3rd Street Baptist", "EPISCOPAL DIOCESE OF NORTH CAROLINA SAINT PAULS EPISCOPAL CHURCH" -> "Saint Pauls", "PROTESTANT EPISCOPAL CHURCH IN THE UNITED STATES OF AMERICA" -> "Protestant Episcopal Church in the United States", "ST JAMES EPISCOPAL CHURCH OF KITTRELL NC" -> "Saint James Episcopal"
4. **original_name**: If the input name was not in English (e.g. French "Eglise Saint-Paul", Spanish "Iglesia de San Juan", Welsh "Eglwys y Drindod"), return the original name here for preservation. If the name was already in English, return empty string.
5. **location**: If the name contains a trailing town/city/place name or state code (like "Tuckahoe", "Holmesburg", "Kittrell NC", "Tryon", "Vernon Ct"), return just the place name here. Otherwise return empty string. This will be moved to the city field.
6. **landmark_type**: church, cathedral, chapel, school, monastery, seminary, diocese, shrine, cemetery, other

Return ONLY a JSON array, one object per entry in the same order:
[{{"is_anglican": true/false, "correct_faith": "...", "normalized_name": "...", "original_name": "...", "location": "...", "landmark_type": "...", "confidence": 0.0-1.0}}]

Entries:
{chr(10).join(lines)}"""

    try:
        r = requests.post("https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat",
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.0, "max_tokens": 6000}, timeout=30)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        content = re.sub(r"^```json\s*|```\s*$", "", content.strip())
        return json.loads(content)
    except Exception as e:
        err = str(e)[:120]
        prompt_preview = prompt[:200] if prompt else "empty"
        return [{"is_anglican": False, "correct_faith": "ERROR", 
                 "normalized_name": items[i][0], "landmark_type": "other",
                 "confidence": 0.0, "error": f"{err[:80]}"} for i in range(len(items))]


db = sqlite3.connect(DB, timeout=30)
db.execute("PRAGMA journal_mode=WAL")
db.row_factory = sqlite3.Row

# Get ALL hierarchy entries
entries = db.execute("""
    SELECT DISTINCT c.id, c.name, c.landmark_type, c.country, c.tradition, c.taxonomy_id, c.city
    FROM anglican_hierarchy ah
    JOIN churches c ON ah.church_id = c.id
    WHERE c.name IS NOT NULL AND c.name != ''
    ORDER BY c.id
""").fetchall()

print(f"Entries to classify: {len(entries):,}")
print(f"Batches of {BATCH_SIZE}: {len(entries)//BATCH_SIZE + 1} API calls")
print(f"Estimated cost at DeepSeek pricing: ~${len(entries)*0.00005:.2f}")
print()
sys.stdout.flush()

# Stats
faith_counts = Counter()
anglican_count = 0
not_anglican_count = 0
name_changed = 0
errors = 0
start = time.time()

OUT_FILE = OUT / "anglican_deepseek_results.jsonl"

# Resume: load already-processed IDs from existing output
processed_ids = set()
if OUT_FILE.exists():
    with open(OUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    data = json.loads(line)
                    processed_ids.add(data["church_id"])
                except json.JSONDecodeError:
                    pass
    print(f"Resume mode: {len(processed_ids):,} entries already processed, skipping...")

if processed_ids:
    entries = [e for e in entries if e["id"] not in processed_ids]
    print(f"Remaining to classify: {len(entries):,}")
    print(f"Batches of {BATCH_SIZE}: {len(entries)//BATCH_SIZE + 1} API calls")
    print(f"Estimated cost at DeepSeek pricing: ~${len(entries)*0.00005:.2f}")
    print()
    sys.stdout.flush()

out_file = open(OUT_FILE, "a", encoding="utf-8")

# Pre-load taxonomy names
tax_names = {}
for tid in ANGLICAN_TAX_IDS + [3]:
    r = db.execute("SELECT name FROM taxonomy WHERE id=?", (tid,)).fetchone()
    if r:
        tax_names[tid] = r[0]

for bs in range(0, len(entries), BATCH_SIZE):
    print(f"  Batch {bs//BATCH_SIZE + 1}/{(len(entries)-1)//BATCH_SIZE + 1} starting...", end=" ")
    sys.stdout.flush()
    batch = entries[bs:bs+BATCH_SIZE]
    items = [(row["name"] or "", row["landmark_type"] or "", row["country"] or "", row["tradition"] or "", row["city"] or "") for row in batch]
    ids = [row["id"] for row in batch]
    old_taxes = [row["taxonomy_id"] for row in batch]
    
    results = classify_batch(items)
    
    for i, rid in enumerate(ids):
        res = results[i] if i < len(results) else {"is_anglican": False, "correct_faith": "ERROR", "error": "missing"}
        name = items[i][0]
        old_tax = old_taxes[i]
        
        if res.get("error"):
            errors += 1
            continue
        
        is_ang = res.get("is_anglican", False)
        faith = str(res.get("correct_faith", "Other Christian"))
        new_name = str(res.get("normalized_name", name))
        original_name = str(res.get("original_name", ""))
        lm = str(res.get("landmark_type", "other"))
        location = str(res.get("location", ""))
        conf = res.get("confidence", 0.0)
        faith_counts[faith] += 1
        
        # Map correct_faith to taxonomy_id for Anglicans
        faith_to_tax = {
            "Episcopal": 79, "Episcopal Church": 80, "Protestant Episcopal": 79,
            "Church of England": 78, "Anglican Church of Canada": 76,
            "Anglican Church in North America": 75, "Anglican Church in North America (ACNA)": 75,
            "Anglican Church of Australia": 13, "Church of Ireland": 13,
            "Scottish Episcopal Church": 79, "Church in Wales": 13,
            "Reformed Episcopal Church": 82, "Reformed Episcopal": 82,
            "Free Episcopal": 13, "Charismatic Episcopal": 81,
            "Anglican Church of Kenya": 13, "Anglican Church of Nigeria": 13,
            "Church of Uganda": 13, "Anglican Church of Southern Africa": 13,
            "Anglican Church of Tanzania": 13, "Anglican Church of Papua New Guinea": 13,
            "Anglican Church in Aotearoa New Zealand and Polynesia": 13,
            "Church of Melanesia": 13, "Anglican Church of Myanmar": 13,
            "Episcopal Church of South Sudan": 13, "Anglican Church of Congo": 13,
            "Anglican Church of Rwanda": 13, "Church of Bangladesh": 13,
            "Church of Pakistan": 13, "Church of North India": 13,
            "Church of South India": 13, "Anglican Church in Japan": 13,
            "Anglican Church of Korea": 13, "Hong Kong Anglican Church": 13,
        }
        
        # Build change description
        changes = []
        if new_name != name and new_name:
            changes.append(f"name: \"{name[:50]}\" -> \"{new_name[:50]}\"")
        if location and items[i][4] != location:
            changes.append(f"city: {location}")
        if original_name and original_name != name:
            changes.append(f"orig: saved")
        if is_ang and conf >= 0.6:
            if old_tax not in ANGLICAN_TAX_IDS:
                tn = tax_names.get(old_tax, str(old_tax))
                changes.append(f"tax: {tn} -> Anglican")
            old_trad = items[i][3]
            if old_trad != "Anglican" and (not old_trad or old_trad in ("Christian", "Protestant", "Other Christian")):
                changes.append(f"trad: \"{old_trad}\" -> Anglican")
            if lm != items[i][1] and items[i][1] != lm:
                changes.append(f"type: {items[i][1]} -> {lm}")
        
        # PRINT EVERY ENTRY - input -> output side by side
        sym = "[+]" if is_ang else "[-]" if not is_ang else "[?]"
        inp = name[:40]
        outp = new_name[:40] if new_name != name else ""
        if outp:
            extra = "; ".join(changes) if changes else ""
            print(f"  [{bs+i+1}/{len(entries)}] ID={rid} {sym} {faith:20s} conf={conf:.2f} input: \"{inp}\" -> output: \"{outp}\" {extra}")
        elif changes:
            print(f"  [{bs+i+1}/{len(entries)}] ID={rid} {sym} {faith:20s} conf={conf:.2f} {'; '.join(changes)} | input: \"{inp}\"")
        else:
            print(f"  [{bs+i+1}/{len(entries)}] ID={rid} {sym} {faith:20s} conf={conf:.2f} | {inp}")
        sys.stdout.flush()
        
        # Log result
        out_file.write(json.dumps({
            "church_id": rid, "name": name, "is_anglican": is_ang,
            "correct_faith": faith, "normalized_name": new_name,
            "original_name": original_name, "location": location, "landmark_type": lm,
            "confidence": conf, "old_taxonomy_id": old_tax
        }) + "\n")
        
        updates = []
        
        # Name normalization
        if new_name != name and new_name:
            updates.append(("name", name, new_name))
        
        # Original name (non-English) preservation
        if original_name and original_name != name and original_name != new_name:
            db.execute("UPDATE churches SET name_original=? WHERE id=?", (original_name, rid))
        
        # Taxonomy fix for confirmed Anglicans with wrong taxonomy
        if is_ang and conf >= 0.6:
            target_tax = faith_to_tax.get(faith, 13)
            if old_tax not in ANGLICAN_TAX_IDS or old_tax != target_tax:
                updates.append(("taxonomy_id", str(old_tax), str(target_tax)))
            
            # Set tradition to the specific faith name
            old_trad = items[i][3]
            if old_trad != faith and (not old_trad or old_trad in ("Christian", "Protestant", "Other Christian", "Anglican")):
                updates.append(("tradition", old_trad or "", faith))
            
            # Landmark type
            if lm != items[i][1] and items[i][1] != lm:
                updates.append(("landmark_type", items[i][1] or "", lm))
            
            # City (location extracted from name)
            if location and not items[i][4]:
                updates.append(("city", items[i][4] or "", location))
        
        # Apply updates if any
        if updates:
            for field, old_val, new_val in updates:
                if field == "name":
                    db.execute("UPDATE churches SET name=? WHERE id=?", (new_val, rid))
                elif field == "taxonomy_id":
                    db.execute("UPDATE churches SET taxonomy_id=? WHERE id=?", (int(new_val), rid))
                elif field == "tradition":
                    db.execute("UPDATE churches SET tradition=? WHERE id=?", (new_val, rid))
                elif field == "landmark_type":
                    db.execute("UPDATE churches SET landmark_type=? WHERE id=?", (new_val, rid))
                elif field == "city":
                    db.execute("UPDATE churches SET city=? WHERE id=?", (new_val, rid))
                
                db.execute("""
                    INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source)
                    VALUES (?, ?, ?, ?, ?)
                """, (rid, field, str(old_val), str(new_val), LOG_SOURCE))
            
            if new_name != name:
                name_changed += 1
        
        # COUNT every entry regardless of whether updates were needed
        if conf >= 0.6:
            if is_ang:
                anglican_count += 1
            else:
                not_anglican_count += 1
                # Log non-Anglican suggestions
                if not updates:
                    db.execute("""
                        INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source)
                        VALUES (?, 'deepseek_suggested_faith', ?, ?, ?)
                    """, (rid, items[i][3] or "", faith, LOG_SOURCE))
    
    db.commit()
    out_file.flush()
    
    # Progress
    elapsed = time.time() - start
    rate = (bs + BATCH_SIZE) / elapsed if elapsed > 0 else 0
    eta = (len(entries) - bs - BATCH_SIZE) / rate if rate > 0 else 0
    done = min(bs + BATCH_SIZE, len(entries))
    pct = done / len(entries) * 100
    
    print(f"  [{done:>6,}/{len(entries):,}] {pct:5.1f}% | Anglican: {anglican_count:,} | Not: {not_anglican_count:,} | Names: {name_changed:,} | {rate:.1f}/s | ETA {eta/60:.0f}m")
    sys.stdout.flush()
    
    if bs + BATCH_SIZE < len(entries):
        time.sleep(0.5)

out_file.close()

# Final stats
elapsed = time.time() - start
print()
print(f"{'='*60}")
print(f"ANGLICAN DEEPSEEK SCAN COMPLETE")
print(f"{'='*60}")
print(f"Processed:   {len(entries):,}")
print(f"Anglican:    {anglican_count:,}")
print(f"Not Anglican:{not_anglican_count:,}")
print(f"Names fixed: {name_changed:,}")
print(f"Errors:      {errors:,}")
print(f"Time:        {elapsed/60:.1f} min")
print()
print("Faith breakdown:")
for faith, cnt in faith_counts.most_common():
    pct = cnt / len(entries) * 100
    print(f"  {faith:30s} {cnt:6,d} ({pct:5.1f}%)")
print()
print(f"Results saved to: {OUT / 'anglican_deepseek_results.jsonl'}")

# Final Anglican count
final_anglican = db.execute("""
    SELECT COUNT(1) FROM churches c
    JOIN taxonomy t ON c.taxonomy_id = t.id
    WHERE t.name LIKE '%Anglican%' OR t.name LIKE '%Episcopal%' OR t.name LIKE '%Church of England%'
""").fetchone()[0]
trad_anglican = db.execute("""
    SELECT COUNT(1) FROM churches
    WHERE tradition LIKE '%Anglican%' OR tradition LIKE '%Episcopal%'
       OR tradition LIKE '%Church of England%' OR tradition LIKE '%Church of Ireland%'
       OR tradition LIKE '%Anglican Church of%'
""").fetchone()[0]
print(f"\nFinal Anglican (taxonomy): {final_anglican:,}")
print(f"Final Anglican (tradition): {trad_anglican:,}")

db.close()
