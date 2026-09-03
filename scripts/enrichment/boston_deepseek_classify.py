#!/usr/bin/env python3
"""
Boston DeepSeek Classifier
==========================
Uses DeepSeek API to classify ALL Boston-area church records by
name + address. Fixes misclassifications from keyword matching
(especially Christian→Judaism false positives, cemetery tagging, etc.).

Usage:
    python scripts/enrichment/boston_deepseek_classify.py
    python scripts/enrichment/boston_deepseek_classify.py --dry-run
    python scripts/enrichment/boston_deepseek_classify.py --limit 100
"""

import json, os, sys, time, urllib.request, urllib.parse, argparse
from datetime import datetime

PROJECT_DIR = r'E:\grid'
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')
DEEPSEEK_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
DEEPSEEK_URL = 'https://api.deepseek.com/v1/chat/completions'
BATCH_SIZE = 20
CHECKPOINT = os.path.join(PROJECT_DIR, 'data', 'boston_deepseek_classified.json')

BOSTON_CITIES = [
    'BOSTON', 'ALLSTON', 'BRIGHTON', 'CHARLESTOWN', 'DORCHESTER',
    'EAST BOSTON', 'HYDE PARK', 'JAMAICA PLAIN', 'MATTAPAN',
    'READVILLE', 'ROSLINDALE', 'ROXBURY', 'ROXBURY CROSSING',
    'SOUTH BOSTON', 'WEST ROXBURY',
]

CLASSIFICATION_PROMPT = """You are classifying Boston-area religious organization names. For each name, determine:
1. Faith: christian, muslim, jewish, buddhist, hindu, sikh, other_religious, or non_religious
2. Denomination: specific denomination if clear (e.g., Catholic, Baptist, Methodist, Lutheran, Episcopal, Orthodox, Pentecostal, Congregational, Presbyterian, Church of God, Church of Christ, Seventh-day Adventist, Salvation Army, Unitarian Universalist, Christian Science, Evangelical, Nazarene, LDS/Mormon, etc.) or null if uncertain
3. Landmark type: church, synagogue, mosque, temple, cemetery, hospital, school, convent, monastery, administrative_office, community_center, housing, religious_org (generic), or other

CRITICAL RULES:
- "ARCHDIOCESAN", "ROMAN CATHOLIC ARCH", "DIOCESAN", "PASTORAL CENTER" → christian/Catholic
- Any "ST." or "SAINT" followed by a saint name → christian/Catholic
- "BETH ISRAEL", "BNAI", "JESHURUN", "CONGREGATION" (Hebrew name), "SHALOM", "CHABAD", "YESHIVA", "MIKVAH" → jewish
- "MOSQUE", "ISLAMIC", "MUSLIM", "AL-ROWDA" → muslim
- "CHRIST SCIENTIST", "CHRISTIAN SCIENCE" → christian/Christian Science
- "CEMETERY" → landmark_type=cemetery
- "HOSPITAL", "MEDICAL CENTER", "DEACONESS" → landmark_type=hospital
- "SCHOOL", "ACADEMY", "ELEMENTARY" → landmark_type=school (even if church-affiliated)
- "CONVENT", "MONASTERY", "RECTORY", "PRIORY" → landmark_type=convent or religious_house
- "HOUSING", "APARTMENTS", "HOMES", "SHELTER" → landmark_type=housing
- "BAPTIST" in name → christian/Baptist
- "PENTECOSTAL" or "PENT APSTL" → christian/Pentecostal
- "METHODIST" or "UMC" → christian/Methodist
- "LUTHERAN" → christian/Lutheran
- "EPISCOPAL" → christian/Episcopal
- "ORTHODOX" (without "JEWISH") → christian/Orthodox
- "PRESBYTERIAN" → christian/Presbyterian
- "CONGREGATIONAL" or "UCC" → christian/Congregational
- "EVANGELICAL" → christian/Evangelical
- "CHURCH OF GOD" → christian/Church of God
- "JEHOVAH" → christian/Jehovah's Witnesses
- "SALVATION ARMY" → christian/Salvation Army
- "UNITARIAN" or "UNIVERSALIST" → christian/Unitarian Universalist
- "TRUST", "NOMINEE", "REALTY", "DEVELOPMENT", "CORPORATION" alone (no religious keywords) → non_religious
- "TEMPLE" alone (no other religious keywords) → probably jewish but check context
- "COMMONWEALTH OF", "CITY OF", "MASSACHUSETTS BAY" → non_religious

RESPOND ONLY with a JSON array of objects:
[{"id":N, "faith":"...", "denomination":null|"...", "landmark_type":"...", "confidence":0.0}]
"""

sys.path.insert(0, PROJECT_DIR)
from gw_db import connect


def get_boston_records(conn):
    """Get all Boston-area records needing classification."""
    placeholders = ','.join('?' for _ in BOSTON_CITIES)
    rows = conn.execute(f"""
        SELECT id, name, city, address, latitude, longitude, source,
               faith, denomination, landmark_type
        FROM churches 
        WHERE state='MA' AND UPPER(city) IN ({placeholders})
        ORDER BY source, id
    """, BOSTON_CITIES).fetchall()
    return rows


def call_deepseek(batch):
    """Send a batch of records to DeepSeek for classification."""
    # Build name+address context for each record
    names_text = '\n'.join(
        f"{r[0]}. {r[1]}" + (f" — {r[3]}, {r[2]}" if r[3] else f" — {r[2]}")
        for r in batch
    )
    
    payload = json.dumps({
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': CLASSIFICATION_PROMPT},
            {'role': 'user', 'content': f'Classify these Boston religious property records:\n{names_text}'}
        ],
        'temperature': 0.1,
        'max_tokens': 3000,
    }).encode()
    
    req = urllib.request.Request(DEEPSEEK_URL, data=payload, headers={
        'Authorization': f'Bearer {DEEPSEEK_KEY}',
        'Content-Type': 'application/json',
        'User-Agent': 'GrantWizard/1.0',
    })
    
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read())
        content = result['choices'][0]['message']['content']
        # Extract JSON array from response
        start = content.find('[')
        end = content.rfind(']') + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])
        print(f'    WARNING: No JSON array in response: {content[:200]}')
        return None
    except Exception as e:
        print(f'    API error: {e}')
        return None


def apply_results(conn, results, dry_run=False):
    """Apply DeepSeek classification results to the database."""
    changes = 0
    for r in results:
        rid = r.get('id')
        faith = r.get('faith')
        denom = r.get('denomination')
        lm_type = r.get('landmark_type')
        conf = r.get('confidence', 0.0)
        
        if not rid or conf < 0.5:
            continue
        
        # Map faith values
        faith_map = {
            'christian': 'Christian', 'muslim': 'Islam', 'jewish': 'Judaism',
            'buddhist': 'Buddhist', 'hindu': 'Hindu', 'sikh': 'Sikh',
            'other_religious': 'Other', 'non_religious': None,
        }
        mapped_faith = faith_map.get(faith, faith)
        
        if dry_run:
            changes += 1
            continue
        
        updates = []
        params = []
        
        if mapped_faith:
            updates.append("faith = ?")
            params.append(mapped_faith)
        if denom:
            updates.append("denomination = ?")
            params.append(denom)
        if lm_type:
            updates.append("landmark_type = ?")
            params.append(lm_type)
        
        if updates:
            updates.append("last_updated = date('now')")
            sql = f"UPDATE churches SET {', '.join(updates)} WHERE id = ?"
            params.append(rid)
            try:
                conn.execute(sql, params)
                changes += 1
            except Exception as e:
                print(f'    ERROR updating #{rid}: {e}')
        
        if changes % 100 == 0:
            conn.commit()
    
    conn.commit()
    return changes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    
    if not DEEPSEEK_KEY:
        print('ERROR: DEEPSEEK_API_KEY not set')
        return
    
    print("=" * 70)
    print("Boston DeepSeek Classifier")
    print("=" * 70)
    
    conn = connect(DB_PATH)
    
    # Get records
    all_records = get_boston_records(conn)
    print(f"\nTotal Boston area records: {len(all_records)}")
    
    # Show current faith breakdown
    faith_counts = {}
    for r in all_records:
        f = r[7] or 'NULL'
        faith_counts[f] = faith_counts.get(f, 0) + 1
    print("Current faith breakdown:")
    for f, c in sorted(faith_counts.items(), key=lambda x: -x[1]):
        print(f"  {f}: {c}")
    
    # Check for NULL id records — we need to fix those first
    null_ids = [r for r in all_records if r[0] is None]
    if null_ids:
        print(f"\n⚠️  {len(null_ids)} records have NULL id — fixing via boston_pid...")
        for r in null_ids[:5]:
            print(f"    name={r[1][:40]} pid={r[4] if len(r)>4 else '?'}")
        
        # Fix: assign rowid to id for records with NULL id
        conn.execute("""
            UPDATE churches SET id = rowid 
            WHERE id IS NULL AND source = 'boston_property_assessment'
        """)
        conn.commit()
        print(f"  Fixed NULL IDs — re-fetching records...")
        
        # Re-fetch
        all_records = get_boston_records(conn)
        # Verify
        still_null = [r for r in all_records if r[0] is None]
        if still_null:
            print(f"⚠️  {len(still_null)} records still have NULL id — using boston_pid fallback")
    
    # Apply limit
    if args.limit and args.limit < len(all_records):
        all_records = all_records[:args.limit]
        print(f"\nLimited to {args.limit} records")
    
    # Load checkpoint for resume
    classified_ids = set()
    if args.resume and os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            checkpoint = json.load(f)
        for r in checkpoint:
            classified_ids.add(r.get('id'))
        all_records = [r for r in all_records if r[0] not in classified_ids]
        print(f"Resuming: {len(classified_ids)} already classified, {len(all_records)} remaining")
    
    # Process in batches
    total_batches = (len(all_records) + BATCH_SIZE - 1) // BATCH_SIZE
    all_results = []
    api_calls = 0
    errors = 0
    
    for i in range(0, len(all_records), BATCH_SIZE):
        batch = all_records[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        
        print(f"\n  Batch {batch_num}/{total_batches} (records {i+1}-{i+len(batch)})...")
        
        # Show what we're sending
        for r in batch:
            ctx = f"{r[1][:50]:50s} | {r[3] or '':30s} | {r[2]}"
            print(f"    {ctx}")
        
        result = call_deepseek(batch)
        
        if result:
            all_results.extend(result)
            api_calls += 1
            print(f"    ✅ Got {len(result)} classifications")
        else:
            errors += 1
            print(f"    ❌ Failed")
        
        # Save checkpoint periodically
        if all_results and (api_calls % 5 == 0 or errors >= 3):
            with open(CHECKPOINT, 'w') as f:
                json.dump(all_results, f, indent=2)
            if not args.dry_run:
                conn.commit()
        
        # Rate limiting
        if i + BATCH_SIZE < len(all_records):
            time.sleep(0.5)
        
        if errors >= 5:
            print("\nToo many errors, stopping")
            break
    
    # Save final checkpoint
    if all_results:
        with open(CHECKPOINT, 'w') as f:
            json.dump(all_results, f, indent=2)
    
    # Apply results
    print(f"\n{'='*70}")
    print(f"Applying {len(all_results)} classifications to database...")
    changes = apply_results(conn, all_results, dry_run=args.dry_run)
    
    print(f"\n{'='*70}")
    print(f"RESULTS")
    print(f"{'='*70}")
    print(f"  API calls: {api_calls}")
    print(f"  Errors:    {errors}")
    print(f"  Records classified: {len(all_results)}")
    print(f"  DB updates:        {changes}")
    
    if not args.dry_run:
        # Show new faith breakdown
        updated = get_boston_records(conn)
        faith_counts = {}
        for r in updated:
            f = r[7] or 'NULL'
            faith_counts[f] = faith_counts.get(f, 0) + 1
        print("\nUpdated faith breakdown:")
        for f, c in sorted(faith_counts.items(), key=lambda x: -x[1]):
            print(f"  {f}: {c}")
    
    conn.close()
    print(f"\nDone. Checkpoint saved to: {CHECKPOINT}")


if __name__ == '__main__':
    main()
