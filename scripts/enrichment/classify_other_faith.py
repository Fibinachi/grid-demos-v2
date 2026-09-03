#!/usr/bin/env python3
"""Classify the 'Other' faith bucket — same two-pass prompt, different target."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

# Monkey-patch the classify script to target Other faith
import classify_remaining_christians as crc

# Override constants
crc.CHECKPOINT = "data/classify_other_checkpoint.json"
crc.BATCH_SIZE = 8
crc.MAX_TOKENS = 8000

# Override source name
old_main = crc.main
def new_main():
    global old_main
    # Override the query to target Other instead of Christian
    import sqlite3
    from datetime import datetime, timezone
    
    limit = 0
    for a in sys.argv:
        if a.startswith("--limit="):
            limit = int(a.split("=", 1)[1])
    
    db = sqlite3.connect(crc.DB, timeout=30)
    c = db.cursor()
    existing = {r[1] for r in c.execute("PRAGMA table_info(churches)").fetchall()}
    for col, dtype in [("christ_class_confidence","TEXT"),("christ_class_source","TEXT"),("christ_class_date","TEXT"),("name_english","TEXT")]:
        if col not in existing:
            c.execute(f"ALTER TABLE churches ADD COLUMN {col} {dtype}")
    db.commit()
    
    query = """SELECT id, name, city, state, country FROM churches
               WHERE faith='Other' AND (tradition IS NULL OR tradition='')
               ORDER BY id"""
    if limit:
        query += f" LIMIT {limit}"
    c.execute(query)
    rows = c.fetchall()
    total = len(rows)
    crc.log(f"Other-faith churches to classify: {total:,}")
    
    if total == 0:
        crc.log("Nothing to do!")
        db.close()
        return
    
    cp = crc.load_checkpoint()
    start_idx = cp["processed"]
    if start_idx:
        crc.log(f"Resuming from checkpoint: {start_idx:,}")
    rows = rows[start_idx:]
    
    source_name = "deepseek_other_classifier"
    c.execute("""INSERT INTO provenance_log
        (source, script_name, started_at, status, records_attempted, fields_populated)
        VALUES (?,?,?,'running',?,?)""",
        (source_name, __file__, datetime.now(timezone.utc).isoformat(), total, "faith,tradition,landmark_type"))
    log_id = c.lastrowid
    db.commit()
    
    classified = cp["classified"]
    failed = cp["failed"]
    db_batch = []
    start_time = __import__('time').time()
    
    for batch_start in range(0, len(rows), crc.BATCH_SIZE):
        batch = rows[batch_start:batch_start + crc.BATCH_SIZE]
        items = [{"id": r[0],
                  "name": r[1].replace('"', "'").replace("\\", " "),
                  "city": (r[2] or "").replace('"', "'"),
                  "state": (r[3] or "").replace('"', "'"),
                  "country": (r[4] or "").replace('"', "'")}
                 for r in batch]
        
        print(f"\n{'─'*80}")
        print(f"📤 BATCH {batch_start//crc.BATCH_SIZE + 1} — {len(items)} Other-faith entries:")
        for item in items:
            loc = f"{item['city']}, {item['state']}" if item['state'] else item['country']
            print(f"  [{item['id']}] {item['name'][:55]:55s} | {loc[:30]}")
        
        prompt = crc.PROMPT.format(items=__import__('json').dumps(items, indent=2))
        try:
            resp = __import__('requests').post("https://api.deepseek.com/v1/chat/completions", json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.05, "max_tokens": crc.MAX_TOKENS
            }, headers={"Authorization": f"Bearer {crc.API_KEY}", "Content-Type": "application/json"}, timeout=120)
            
            if resp.status_code != 200:
                print(f"  ❌ HTTP {resp.status_code}: {resp.text[:200]}")
                failed += len(items)
                continue
            
            content = resp.json()["choices"][0]["message"]["content"]
            content = __import__('re').sub(r'^```json\s*', '', content.strip())
            content = __import__('re').sub(r'\s*```$', '', content.strip())
            
            try:
                results = __import__('json').loads(content)
            except:
                jm = __import__('re').search(r'\[.*\]', content, __import__('re').DOTALL)
                if jm:
                    results = __import__('json').loads(jm.group())
                else:
                    print(f"  ❌ No JSON: {content[:200]}")
                    failed += len(items)
                    continue
        except Exception as e:
            print(f"  ❌ API error: {e}")
            failed += len(items)
            continue
        
        print(f"\n📥 RESULTS:")
        batch_updates = []
        for result in results:
            cid = result.get("id")
            faith = result.get("faith", "Other")
            tradition = result.get("tradition", "")
            landmark = result.get("landmark_type", "")
            confidence = result.get("confidence", "medium")
            name_en = result.get("name_english", "")
            
            item = next((i for i in items if i["id"] == cid), None)
            name = item["name"] if item else "?"
            
            is_non_christian = faith not in ("Christian", "", "Other")
            if not tradition:
                tradition = faith
            
            tag = "🔄" if faith != "Other" else "✅"
            trans = f" → EN: {name_en[:35]}" if name_en and name_en != name else ""
            print(f"  {tag} [{cid}] {name[:40]:40s}{trans}")
            print(f"       → {faith[:15]:15s} / {tradition[:25]:25s} | {landmark[:12]} | {confidence}")
            
            batch_updates.append((faith, tradition, name_en or "", landmark, confidence, cid))
        
        for faith_v, trad_v, nen_v, lm_v, conf_v, cid in batch_updates:
            c.execute("""UPDATE churches SET faith=?, tradition=?, name_english=?, landmark_type=?, christ_class_confidence=?, christ_class_source=?, christ_class_date=? WHERE id=?""",
                      (faith_v, trad_v, nen_v, lm_v, conf_v, source_name, datetime.now(timezone.utc).isoformat(), cid))
            classified += 1
        db.commit()
        
        processed = start_idx + batch_start + len(batch)
        elapsed = __import__('time').time() - start_time
        rate = processed / elapsed if elapsed > 0 else 0
        eta = (total - processed) / rate if rate > 0 else 0
        crc.log(f"  {crc.progress_bar(processed, total)} | {rate:.0f}/s | ETA: {eta/60:.0f}m | +{classified}/{failed}")
        crc.save_checkpoint(processed, classified, failed)
        __import__('time').sleep(0.3)
    
    elapsed = __import__('time').time() - start_time
    c.execute("""UPDATE provenance_log SET status='completed', completed_at=?, churches_updated=?, records_matched=?, notes=? WHERE id=?""",
        (datetime.now(timezone.utc).isoformat(), classified, classified, f"{classified} classified, {failed} failed, {elapsed:.0f}s", log_id))
    db.commit()
    
    c.execute("SELECT COUNT(*) FROM churches WHERE faith='Other' AND (tradition IS NULL OR tradition='')")
    remaining = c.fetchone()[0]
    crc.log(f"\n{'='*60}")
    crc.log(f"COMPLETE in {elapsed/60:.1f}m — {classified:,} classified, {failed:,} failed, {remaining:,} remain")
    db.close()

crc.main = new_main
crc.main()
