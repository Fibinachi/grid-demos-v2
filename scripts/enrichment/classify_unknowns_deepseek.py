#!/usr/bin/env python3
"""
DeepSeek Unknown Classifier
===========================
Uses DeepSeek API to classify unknown churches by name+city,
then filters out non-religious organizations.

Strategy:
  1. Send batches of names to DeepSeek for classification
  2. Apply faith_tradition based on response
  3. Mark non-religious entities

Usage:
    python scripts/enrichment/classify_unknowns_deepseek.py
    python scripts/enrichment/classify_unknowns_deepseek.py --dry-run
    python scripts/enrichment/classify_unknowns_deepseek.py --limit 100
"""
import json, os, sqlite3, time, urllib.request, urllib.parse
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')
DEEPSEEK_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
DEEPSEEK_URL = 'https://api.deepseek.com/v1/chat/completions'
BATCH_SIZE = 30  # Names per API call
CHECKPOINT = os.path.join(PROJECT_DIR, 'data', 'unknowns_classified.json')

CLASSIFICATION_PROMPT = """You are classifying religious organization names. For each name, determine:
1. Faith tradition: christian, muslim, jewish, buddhist, hindu, sikh, other_religious, or non_religious
2. Confidence: 0.0-1.0

Rules:
- "Mikvah", "Shul", "Yeshiva", "Kollel", "Chabad" = jewish
- "Masjid", "Musallah", "Mosque", "Islamic", "Quran" = muslim
- "Gurdwara", "Sikh" = sikh
- "Mandir", "Temple" (Hindu context), "Ashram", "Hindu" = hindu
- "Vihara", "Wat", "Buddhist", "Dharma" = buddhist
- "Church", "Chapel", "Cathedral", "Ministry", "Gospel", "Bible" = christian
- "Mission" could be christian OR non_religious (rescue mission, homeless mission)
- "Association", "Center", "Foundation", "Council", "Society", "Institute" alone = non_religious
- "School", "Academy", "College", "University" = non_religious
- "Funeral Home", "Cemetery", "Florist", "Catering", "Banquet", "Vue", "Hall" = non_religious
- "Museum", "Gallery", "Theater" = non_religious
- "Hospital", "Clinic", "Medical", "Health" = non_religious
- "Food Bank", "Pantry", "Soup Kitchen" = non_religious
- "Diplomatic", "Consulate", "Mission (diplomatic)" = non_religious
- Hebrew names like "Ahavas Torah", "Bnai Israel", "Kehillat", "Agudath" = jewish
- Arabic names like "Al-Ansar", "Albaseerah", "Jamaat" = muslim
- Sanskrit names without temple/mandir context = non_religious

RESPOND ONLY with a JSON array of objects: [{"name":"...","faith":"...","confidence":0.0}]
"""


def call_deepseek(batch):
    """Send a batch of names to DeepSeek for classification."""
    names_text = '\n'.join(f"{i+1}. {n}" for i, n in enumerate(batch))
    
    payload = json.dumps({
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': CLASSIFICATION_PROMPT},
            {'role': 'user', 'content': f'Classify these organization names:\n{names_text}'}
        ],
        'temperature': 0.1,
        'max_tokens': 2000,
    }).encode()
    
    req = urllib.request.Request(DEEPSEEK_URL, data=payload, headers={
        'Authorization': f'Bearer {DEEPSEEK_KEY}',
        'Content-Type': 'application/json',
        'User-Agent': 'GrantWizard/1.0',
    })
    
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
        content = result['choices'][0]['message']['content']
        # Extract JSON array from response
        start = content.find('[')
        end = content.rfind(']') + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])
        return None
    except Exception as e:
        print(f'    API error: {e}')
        return None


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    
    if not DEEPSEEK_KEY:
        print('ERROR: DEEPSEEK_API_KEY not set')
        return
    
    db = sqlite3.connect(DB_PATH, timeout=60)
    
    # Get unknown names grouped
    rows = db.execute("""
        SELECT LOWER(name), COUNT(*) as cnt
        FROM churches 
        WHERE (faith_tradition IS NULL OR faith_tradition = '')
        AND name != '' AND name IS NOT NULL
        GROUP BY name
        ORDER BY cnt DESC
    """).fetchall()
    
    print(f'Unknown records: {sum(r[1] for r in rows):,}')
    print(f'Distinct names: {len(rows):,}')
    
    if args.limit:
        rows = rows[:args.limit]
    
    # Load checkpoint
    classified = {}
    if args.resume and os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            classified = json.load(f)
        print(f'Resuming: {len(classified)} names already classified')
    
    # Process in batches
    all_results = {}
    remaining = [r for r in rows if r[0] not in classified]
    print(f'Remaining to classify: {len(remaining):,} names')
    
    if args.dry_run:
        for name, cnt in remaining[:10]:
            print(f'  {name[:55]:55s} {cnt:>4}')
        db.close()
        return
    
    for i in range(0, len(remaining), BATCH_SIZE):
        batch = remaining[i:i+BATCH_SIZE]
        names = [r[0] for r in batch]
        
        print(f'  Batch {i//BATCH_SIZE + 1}/{(len(remaining)-1)//BATCH_SIZE + 1} ({len(batch)} names)...', end=' ', flush=True)
        
        results = call_deepseek(names)
        if results:
            for r in results:
                name = r.get('name', '').lower().strip()
                faith = r.get('faith', 'non_religious')
                conf = r.get('confidence', 0.5)
                all_results[name] = {'faith': faith, 'confidence': conf}
            print(f'OK')
        else:
            print(f'FAILED')
        
        time.sleep(0.5)
        
        # Save checkpoint periodically
        if len(all_results) % 100 < BATCH_SIZE and all_results:
            classified.update(all_results)
            os.makedirs(os.path.dirname(CHECKPOINT), exist_ok=True)
            with open(CHECKPOINT, 'w') as f:
                json.dump(classified, f, indent=2)
    
    # Save final checkpoint
    classified.update(all_results)
    with open(CHECKPOINT, 'w') as f:
        json.dump(classified, f, indent=2)
    
    # Apply to DB
    print(f'\nApplying {len(all_results):,} classifications to DB...')
    
    stats = {'christian': 0, 'muslim': 0, 'jewish': 0, 'buddhist': 0,
             'hindu': 0, 'sikh': 0, 'other_religious': 0, 'non_religious': 0, 'unknown': 0}
    
    for name, data in all_results.items():
        faith = data['faith']
        conf = data['confidence']
        
        if faith in stats:
            stats[faith] += 1
        else:
            stats['unknown'] += 1
        
        # Update all records with this name
        if faith == 'non_religious':
            db.execute("""
                UPDATE churches SET
                    faith_tradition = CASE WHEN faith_tradition IS NULL OR faith_tradition = '' THEN 'non_religious' ELSE faith_tradition END,
                    last_updated = datetime('now')
                WHERE LOWER(name) = ? AND (faith_tradition IS NULL OR faith_tradition = '')
            """, (name,))
        elif faith in ('christian', 'muslim', 'jewish', 'buddhist', 'hindu', 'sikh'):
            db.execute("""
                UPDATE churches SET
                    faith_tradition = CASE WHEN faith_tradition IS NULL OR faith_tradition = '' THEN ? ELSE faith_tradition END,
                    last_updated = datetime('now')
                WHERE LOWER(name) = ? AND (faith_tradition IS NULL OR faith_tradition = '')
            """, (faith, name))
        else:
            # other_religious
            db.execute("""
                UPDATE churches SET
                    faith_tradition = CASE WHEN faith_tradition IS NULL OR faith_tradition = '' THEN 'other' ELSE faith_tradition END,
                    last_updated = datetime('now')
                WHERE LOWER(name) = ? AND (faith_tradition IS NULL OR faith_tradition = '')
            """, (name,))
    
    db.commit()
    
    print(f'\nResults:')
    for k, v in sorted(stats.items(), key=lambda x: -x[1]):
        print(f'  {k:20s} {v:>6,}')
    
    # Final report
    r = db.execute("SELECT COUNT(*) FROM churches WHERE faith_tradition IS NULL OR faith_tradition = ''").fetchone()
    print(f'\nRemaining unknowns: {r[0]:,}')
    
    r = db.execute("SELECT COUNT(*) FROM churches WHERE faith_tradition = 'non_religious'").fetchone()
    print(f'Non-religious tagged: {r[0]:,}')
    
    db.close()
    print('\nDone!')


if __name__ == '__main__':
    main()
