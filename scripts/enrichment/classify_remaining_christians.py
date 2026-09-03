#!/usr/bin/env python3
"""
DeepSeek Christian Tradition Classifier
========================================
Classifies remaining unclassified Christian churches using DeepSeek API.

Features:
- Full CFTLM taxonomy embedded in prompt for precise classification
- Live streaming of every input name and output classification
- Machine translation: DeepSeek reads Spanish, Turkish, Indonesian, etc. natively
- Garbage bucket: "Other Christian" for unclassifiable entries
- Checkpoint/resume support
- Progress bar

Usage:
    python scripts/enrichment/classify_remaining_christians.py            # Full run
    python scripts/enrichment/classify_remaining_christians.py --limit 50 # Test
"""
import sqlite3, os, json, requests, sys, re, time
from datetime import datetime, timezone

DB = "churches.db"
API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    print("ERROR: DEEPSEEK_API_KEY not set!")
    sys.exit(1)

BATCH_SIZE = 8  # churches per API call (fewer = more reliable JSON)
MAX_TOKENS = 8000  # enough for 8 detailed classifications
CHECKPOINT = "data/classify_remaining_christians_checkpoint.json"

def load_taxonomy():
    """Load the Christian taxonomy tree for the prompt."""
    db = sqlite3.connect(DB)
    c = db.cursor()
    # Christian root is taxonomy id=2 (under Abrahamic id=555)
    christian_ids = []
    root = (2,)  # Christian root node
    # BFS to get all descendants
    queue = [root[0]]
    while queue:
        tid = queue.pop(0)
        christian_ids.append(tid)
        c.execute("SELECT id FROM taxonomy WHERE parent_id=?", (tid,))
        queue.extend(r[0] for r in c.fetchall())
    
    # Get node details
    nodes = {}
    for tid in christian_ids:
        c.execute("SELECT id, name, parent_id FROM taxonomy WHERE id=?", (tid,))
        r = c.fetchone()
        if r:
            nodes[r[0]] = {"name": r[1], "parent_id": r[2]}
    
    db.close()
    
    # Build tree text
    def build_tree(pid, indent=0):
        lines = []
        children = [(tid, n) for tid, n in nodes.items() if n["parent_id"] == pid]
        children.sort(key=lambda x: x[1]["name"])
        for tid, n in children:
            prefix = "  " * indent + ("- " if indent > 0 else "")
            lines.append(f"{prefix}{n['name']} (id={tid})")
            lines.extend(build_tree(tid, indent + 1))
        return lines
    
    return "\n".join(build_tree(2))  # Start from Christian root (id=2)

PROMPT = """Classify each religious site. 

PASS 1 - Faith: Is this Christian, Islam, Judaism, Hindu, Buddhist, Sikh, Shinto, or Other?
- Synagogue: Temple/Congregation + Hebrew names (Beth, Bnai, Adath, Sholom, Shalom, Torah, Jeshurun, Israel, Emanuel, Chabad)
- Mosque: Masjid, Mosque, Islamic, Jami, Musalla, Arabic prayer names
- Hindu: Mandir, Hindu, Ashram, ISKCON, Sanskrit deity names
- Buddhist: Wat, Vihara, Stupa, Buddhist
- Sikh: Gurdwara
- If not Christian, return correct faith with appropriate tradition and landmark_type.

PASS 2 - Christian denomination (only if Christian):
- Catholic: Saint/Eglise/Iglesia + Catholic indicators, monastery, convent, abbey, basilica
- Orthodox: Greek/Russian/Serbian/Coptic/Armenian/Syriac/Malankara, Ι.Ν./Crkva/Manastiri
- Pentecostal: Assemblies of God, Church of God, Foursquare, GPdI/GBI/GBT/GSJA (Indonesian)
- Baptist: Baptist/Bautista in name
- Methodist: Methodist/Wesleyan/AME
- Anglican: Anglican/Episcopal/Church of England
- Lutheran: Lutheran in name
- Presbyterian: Presbyterian in name
- Evangelical: "Evangelical/Evangelique/Evangelica" in name
- If uncertain: "Christian (general)" with low confidence

Return ONLY JSON: [{{"id":N,"faith":"...","tradition":"...","landmark_type":"...","confidence":"...","name_english":"..."}}]

name_english: English translation. Preserve original meaning. If already English, return original.

## Entries

{items}"""

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def load_checkpoint():
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            return json.load(f)
    return {"processed": 0, "classified": 0, "failed": 0}

def save_checkpoint(processed, classified, failed):
    os.makedirs(os.path.dirname(CHECKPOINT), exist_ok=True)
    with open(CHECKPOINT, "w") as f:
        json.dump({"processed": processed, "classified": classified, "failed": failed,
                   "last": datetime.now().isoformat()}, f)

def progress_bar(n, total, width=50):
    pct = n / total if total else 0
    filled = int(width * pct)
    return f"[{'='*filled}{'-'*(width-filled)}] {pct*100:.1f}% ({n:,}/{total:,})"

def main():
    limit = 0
    for a in sys.argv:
        if a.startswith("--limit="):
            limit = int(a.split("=", 1)[1])

    # ── Start ──
    log("Starting DeepSeek classifier (two-pass: Faith → Denomination)...")
    full_prompt = PROMPT  # No taxonomy embedding needed — prompt has inline rules

    # Load churches needing classification
    db = sqlite3.connect(DB, timeout=30)
    c = db.cursor()
    # Ensure classification columns exist
    existing = {r[1] for r in c.execute("PRAGMA table_info(churches)").fetchall()}
    for col, dtype in [
        ("christ_class_confidence", "TEXT"),
        ("christ_class_source", "TEXT"),
        ("christ_class_date", "TEXT"),
        ("name_english", "TEXT"),
    ]:
        if col not in existing:
            c.execute(f"ALTER TABLE churches ADD COLUMN {col} {dtype}")
            log(f"  Added column: {col}")
    db.commit()

    query = """SELECT id, name, city, state, country
               FROM churches
               WHERE faith='Christian'
                 AND (tradition IS NULL OR tradition='')
               ORDER BY id"""
    if limit:
        query += f" LIMIT {limit}"
    c.execute(query)
    rows = c.fetchall()
    total = len(rows)
    log(f"Churches to classify: {total:,}")

    if total == 0:
        log("Nothing to do!")
        db.close()
        return

    # Checkpoint
    cp = load_checkpoint()
    start_idx = cp["processed"]
    if start_idx:
        log(f"Resuming from checkpoint: {start_idx:,}")
    rows = rows[start_idx:]

    # Provenance
    source_name = "deepseek_christian_classifier"
    c.execute("""INSERT INTO provenance_log
        (source, script_name, started_at, status, records_attempted, fields_populated)
        VALUES (?,?,?,'running',?,?)""",
        (source_name, __file__, datetime.now(timezone.utc).isoformat(),
         total, "tradition,denomination,landmark_type"))
    log_id = c.lastrowid
    db.commit()

    classified = cp["classified"]
    failed = cp["failed"]
    start_time = time.time()
    taxonomy_tree = None  # Free memory - already embedded in full_prompt

    for batch_start in range(0, len(rows), BATCH_SIZE):
        batch = rows[batch_start:batch_start + BATCH_SIZE]

        # Build sanitized items list
        items = [{"id": r[0],
                  "name": r[1].replace('"', "'").replace("\\", " "),
                  "city": (r[2] or "").replace('"', "'"),
                  "state": (r[3] or "").replace('"', "'"),
                  "country": (r[4] or "").replace('"', "'")}
                 for r in batch]

        # ── STREAM INPUT ──
        print(f"\n{'─'*80}")
        print(f"📤 BATCH {batch_start//BATCH_SIZE + 1} — SENDING {len(items)} churches:")
        for item in items:
            loc = f"{item['city']}, {item['state']}" if item['state'] else item['country']
            print(f"  [{item['id']}] {item['name'][:60]:60s} | {loc[:30]}")

        # Call DeepSeek
        prompt = full_prompt.format(items=json.dumps(items, indent=2))
        try:
            resp = requests.post("https://api.deepseek.com/v1/chat/completions", json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.05, "max_tokens": MAX_TOKENS
            }, headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}, timeout=120)

            if resp.status_code != 200:
                print(f"  ❌ HTTP {resp.status_code}: {resp.text[:200]}")
                failed += len(items)
                continue

            content = resp.json()["choices"][0]["message"]["content"]

            # Strip code fences if present
            content = re.sub(r'^```json\s*', '', content.strip())
            content = re.sub(r'\s*```$', '', content.strip())

            # Parse JSON
            try:
                results = json.loads(content)
            except json.JSONDecodeError:
                # Fallback: try to find JSON array in response
                jm = re.search(r'\[.*\]', content, re.DOTALL)
                if jm:
                    try:
                        results = json.loads(jm.group())
                    except json.JSONDecodeError:
                        print(f"  ❌ JSON parse error: {content[:200]}")
                        failed += len(items)
                        continue
                else:
                    print(f"  ❌ No JSON found: {content[:200]}")
                    failed += len(items)
                    continue

        except Exception as e:
            print(f"  ❌ API error: {e}")
            failed += len(items)
            continue

        # ── STREAM OUTPUT ──
        print(f"\n📥 RESULTS:")
        batch_updates = []
        for result in results:
            cid = result.get("id")
            faith = result.get("faith", "Christian")
            tradition = result.get("tradition", "")
            landmark = result.get("landmark_type", "")
            confidence = result.get("confidence", "medium")
            name_en = result.get("name_english", "")

            # Find the matching original
            item = next((i for i in items if i["id"] == cid), None)
            name = item["name"] if item else "?"

            # Handle non-Christian results from Pass 1
            is_non_christian = faith not in ("Christian", "")
            if is_non_christian:
                tag = "🔄 "
                tradition_final = tradition
                faith_final = faith
            else:
                # Garbage bucket for Christian
                is_garbage = (
                    confidence == "low" or
                    tradition in ("Christian (general)", "Christian", "Other Christian", "Other") or
                    not tradition
                )
                if is_garbage:
                    tag = "🗑️ "
                    tradition_final = "Christian (general)"
                    faith_final = "Christian"
                else:
                    tag = "✅ "
                    tradition_final = tradition
                    faith_final = "Christian"

            trans = f" → EN: {name_en[:40]}" if name_en and name_en != name else ""
            if is_non_christian:
                print(f"  {tag}[{cid}] {name[:40]:40s}{trans}")
                print(f"       → {faith_final} / {tradition_final[:25]} | {landmark} | {confidence}")
            else:
                print(f"  {tag}[{cid}] {name[:40]:40s}{trans}")
                print(f"       {tradition_final[:35]:35s} | {landmark[:15]} | {confidence}")

            # DB update
            batch_updates.append((faith_final, tradition_final, name_en or "", landmark, confidence, cid))

        # ── DB UPDATE ──
        for faith_val, tradition_val, name_en_val, landmark_val, confidence_val, cid in batch_updates:
            c.execute("""UPDATE churches
                         SET faith=?, tradition=?, name_english=?, landmark_type=?,
                             christ_class_confidence=?, christ_class_source=?, christ_class_date=?
                         WHERE id=?""",
                      (faith_val, tradition_val, name_en_val, landmark_val,
                       confidence_val, source_name, datetime.now(timezone.utc).isoformat(), cid))
            classified += 1
        db.commit()

        # ── PROGRESS ──
        processed = start_idx + batch_start + len(batch)
        elapsed = time.time() - start_time
        rate = processed / elapsed if elapsed > 0 else 0
        eta_sec = (total - processed) / rate if rate > 0 else 0
        log(f"  {progress_bar(processed, total)} | {rate:.0f}/s | ETA: {eta_sec/60:.0f}m | +{classified}/{failed}")
        save_checkpoint(processed, classified, failed)

        time.sleep(0.5)  # Rate limit

    # ── FINAL ──
    elapsed = time.time() - start_time
    c.execute("""UPDATE provenance_log SET status='completed', completed_at=?,
        churches_updated=?, records_matched=?, notes=? WHERE id=?""",
        (datetime.now(timezone.utc).isoformat(), classified, classified,
         f"{classified} classified, {failed} failed, {elapsed:.0f}s, {total/elapsed:.0f}/s", log_id))
    db.commit()

    c.execute("SELECT COUNT(*) FROM churches WHERE faith='Christian' AND (tradition IS NULL OR tradition='')")
    remaining = c.fetchone()[0]
    log(f"\n{'='*60}")
    log(f"COMPLETE in {elapsed/60:.1f}m")
    log(f"  Classified: {classified:,}")
    log(f"  Failed: {failed:,}")
    log(f"  Remaining without tradition: {remaining:,}")
    log(f"  Rate: {total/elapsed:.0f}/sec")

    db.close()

if __name__ == "__main__":
    main()
