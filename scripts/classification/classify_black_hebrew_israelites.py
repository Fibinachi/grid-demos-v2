"""
Classify Black Hebrew Israelites in the GRID database.

Black Hebrew Israelites (also: Hebrew Israelites, Black Hebrews) are a distinct
Abrahamic religious movement — NOT Christian, NOT mainstream Judaism. They believe
African Americans, Hispanics, and Native Americans are the true descendants of
biblical Israelites.

Taxonomy placement: Abrahamic(555) > Other Abrahamic (new) > Hebrew Israelite (new)
with sub-camps for specific groups.

Strategy:
1. Add taxonomy nodes
2. Pattern-based classification for known camps (high confidence)
3. DeepSeek classification for ambiguous candidates
4. Apply updates to churches table
"""

import sqlite3
import json
import os
import re
import sys
import time
import requests
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from gw_db import connect as get_db

# ─── PATTERN-BASED CLASSIFICATION ───────────────────────────────────

# High-confidence patterns: pattern → (camp_name, is_definitive)
# is_definitive=True means the pattern alone is enough
# is_definitive=False means we need DeepSeek to confirm

PATTERNS = [
    # === DEFINITIVE (name alone is diagnostic) ===
    ('%IUIC%', 'IUIC (Israel United in Christ)', True),
    ('%Israel United in Christ%', 'IUIC (Israel United in Christ)', True),
    ('%ISUPK%', 'ISUPK (Israelite School of Universal Practical Knowledge)', True),
    ('%Israelite School of Universal%', 'ISUPK (Israelite School of Universal Practical Knowledge)', True),
    ('%Church of God and Saints of Christ%', 'COGSOC (Church of God and Saints of Christ)', True),
    ('%Great Millstone%', 'GMS / Sicarii (Great Millstone)', True),
    ('%African Hebrew Israel%', 'African Hebrew Israelites of Jerusalem', True),
    ('%Nation of Yahweh%', 'Nation of Yahweh', True),
    ('%Yahweh Ben Yahweh%', 'Nation of Yahweh', True),
    # Church of the Living God "Pillar and Ground of the Truth" variant is Black Hebrew
    ("%Church of the Living God%Pillar%Ground%Truth%", 'COGSOC (Church of God and Saints of Christ)', True),
    ("%House of God%Church of the Living God%Pillar%", 'COGSOC (Church of God and Saints of Christ)', True),
    ('%Hebrew Israelite Nation%', 'African Hebrew Israelites of Jerusalem', True),
    ('%Kingdom of Yah%', 'Other Hebrew Israelite', True),
    ('%Sicarii%', 'GMS / Sicarii (Great Millstone)', True),

    # === NEED DEEPSEEK CONFIRMATION ===
    ('%Commandment Keeper%', 'Commandment Keepers', False),
    ('%Hebrew Israelite%', None, False),  # Could be any camp
    ('%Netzari%', None, False),
    ('%Natzari%', None, False),
    ('%Netzarim%', None, False),
    ('%Temple of Yah%', None, False),
    ('%House of Israel%', None, False),
    ('%True Israelite%', None, False),
    ('%First Israelite%', None, False),
    ('%New Israelite%', None, False),
]

def progress_bar(current, total, label='', width=50):
    """Display a progress bar."""
    pct = current / total if total > 0 else 0
    filled = int(width * pct)
    bar = '█' * filled + '░' * (width - filled)
    print(f'\r{label} [{bar}] {current}/{total} ({pct*100:.1f}%)', end='')
    if current >= total:
        print()


def add_taxonomy_nodes(db):
    """Add taxonomy nodes for Black Hebrew Israelites."""
    cur = db.execute("SELECT MAX(id) FROM taxonomy")
    max_id = cur.fetchone()[0]

    node_map = {}  # name → id
    next_id = max_id + 1

    # Insert Other Abrahamic (depth=1, under Abrahamic/555)
    full_path = 'Abrahamic/Other Abrahamic'
    db.execute(
        "INSERT INTO taxonomy (id, name, parent_id, full_path, depth, root_id) VALUES (?, ?, ?, ?, ?, ?)",
        (next_id, 'Other Abrahamic', 555, full_path, 1, 555))
    other_abrahamic_id = next_id
    node_map['Other Abrahamic'] = next_id
    next_id += 1

    # Insert Hebrew Israelite under Other Abrahamic (depth=2)
    full_path = 'Abrahamic/Other Abrahamic/Hebrew Israelite'
    db.execute(
        "INSERT INTO taxonomy (id, name, parent_id, full_path, depth, root_id) VALUES (?, ?, ?, ?, ?, ?)",
        (next_id, 'Hebrew Israelite', other_abrahamic_id, full_path, 2, 555))
    hebrew_israelite_id = next_id
    node_map['Hebrew Israelite'] = next_id
    next_id += 1

    # Insert Black Hebrew Israelite under Hebrew Israelite (depth=3)
    full_path = 'Abrahamic/Other Abrahamic/Hebrew Israelite/Black Hebrew Israelite'
    db.execute(
        "INSERT INTO taxonomy (id, name, parent_id, full_path, depth, root_id) VALUES (?, ?, ?, ?, ?, ?)",
        (next_id, 'Black Hebrew Israelite', hebrew_israelite_id, full_path, 3, 555))
    bhi_id = next_id
    node_map['Black Hebrew Israelite'] = next_id
    next_id += 1

    # Insert camps under Black Hebrew Israelite (depth=4)
    camps = [
        'IUIC (Israel United in Christ)',
        'ISUPK (Israelite School of Universal Practical Knowledge)',
        'GMS / Sicarii (Great Millstone)',
        'COGSOC (Church of God and Saints of Christ)',
        'Commandment Keepers',
        'African Hebrew Israelites of Jerusalem',
        'Nation of Yahweh',
        'House of Israel',
        'Other Hebrew Israelite',
    ]
    camp_ids = {}
    base_path = 'Abrahamic/Other Abrahamic/Hebrew Israelite/Black Hebrew Israelite'
    for camp in camps:
        full_path = f'{base_path}/{camp}'
        db.execute(
            "INSERT INTO taxonomy (id, name, parent_id, full_path, depth, root_id) VALUES (?, ?, ?, ?, ?, ?)",
            (next_id, camp, bhi_id, full_path, 4, 555))
        camp_ids[camp] = next_id
        node_map[camp] = next_id
        next_id += 1

    db.commit()
    print(f'Added {len(node_map)} taxonomy nodes (IDs {max_id+1}–{next_id-1})')
    print(f'  Other Abrahamic: {other_abrahamic_id}')
    print(f'  Hebrew Israelite: {hebrew_israelite_id}')
    print(f'  Black Hebrew Israelite: {bhi_id}')
    print(f'  {len(camps)} camps: {list(camp_ids.values())}')
    return node_map, camp_ids, bhi_id


def find_candidates(db):
    """Find all candidate entries matching Black Hebrew patterns."""
    all_ids = set()
    definitive = {}  # id → camp_name
    needs_deepseek = {}  # id → suggested_camp_or_None

    for pattern, camp, is_definitive in PATTERNS:
        cur = db.execute(f"SELECT id FROM churches WHERE name LIKE ?", (pattern,))
        ids = {row[0] for row in cur}
        new_ids = ids - all_ids
        all_ids |= ids

        for cid in new_ids:
            if is_definitive and camp:
                definitive[cid] = camp
            else:
                needs_deepseek[cid] = camp

    # Remove from needs_deepseek if already in definitive
    needs_deepseek = {k: v for k, v in needs_deepseek.items() if k not in definitive}

    print(f'Total unique candidates: {len(all_ids)}')
    print(f'  Definitive (pattern match): {len(definitive)}')
    print(f'  Needs DeepSeek verification: {len(needs_deepseek)}')
    return definitive, needs_deepseek


def get_api_key():
    """Get DeepSeek API key from environment."""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        import subprocess
        r = subprocess.run(
            ["powershell", "-c", "[Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY','User')"],
            capture_output=True, text=True
        )
        api_key = r.stdout.strip()
    return api_key


def deepseek_classify(db, needs_deepseek, camp_ids, bhi_id):
    """Use DeepSeek API to classify ambiguous candidates."""
    if not needs_deepseek:
        return {}, 0, 0, {}

    api_key = get_api_key()
    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY not set")
        return {}, 0, 0, {}

    results = {}  # id → {camp, confidence}
    confirmed = 0
    rejected = 0
    errors = 0

    ids_list = list(needs_deepseek.keys())
    total = len(ids_list)

    # Process in batches of 10
    BATCH_SIZE = 10
    for batch_start in range(0, total, BATCH_SIZE):
        batch_ids = ids_list[batch_start:batch_start + BATCH_SIZE]

        # Build batch prompt
        lines = []
        for i, church_id in enumerate(batch_ids):
            cur = db.execute(
                "SELECT name, city, state, country, faith, tradition FROM churches WHERE id=?",
                (church_id,)
            )
            row = cur.fetchone()
            if not row:
                lines.append(f'{i+1}. id={church_id} | N/A')
                continue
            name, city, state, country, faith, tradition = row
            lines.append(
                f'{i+1}. name="{name}" | city={city or "?"} | state={state or "?"} | '
                f'country={country or "?"} | faith={faith or "?"} | tradition={tradition or "?"}'
            )

        prompt = f"""Classify each religious site as Black Hebrew Israelite or not.

Black Hebrew Israelites (Hebrew Israelites): African American religious movement believing they are the true descendants of biblical Israelites. NOT Christian (reject trinity, Jesus as God) and NOT mainstream Judaism.

Camps: IUIC (Israel United in Christ), ISUPK (Israelite School of Universal Practical Knowledge), GMS/Sicarii (Great Millstone), COGSOC (Church of God and Saints of Christ founded by William Saunders Crowdy), Commandment Keepers (founded by Wentworth Arthur Matthew), African Hebrew Israelites of Jerusalem (Dimona, Israel based), Nation of Yahweh (Yahweh Ben Yahweh group), House of Israel (local congregations), Other Hebrew Israelite.

Return ONLY a JSON array, one object per entry in the same order:
[{{"is_bh": true/false, "camp": "IUIC|ISUPK|GMS/Sicarii|COGSOC|Commandment Keepers|African Hebrew Israelites|Nation of Yahweh|House of Israel|Other Hebrew Israelite|null", "confidence": 0.0-1.0, "reason": "one sentence"}}]

Entries:
{chr(10).join(lines)}"""

        try:
            r = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 2000
                },
                timeout=60
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            # Clean JSON
            import re
            content = re.sub(r"^```json\s*|```\s*$", "", content.strip())
            batch_results = json.loads(content)

            for i, result in enumerate(batch_results):
                if i < len(batch_ids):
                    church_id = batch_ids[i]
                    if result.get('is_bh') and result.get('confidence', 0) >= 0.7:
                        camp = result.get('camp', 'Other Hebrew Israelite')
                        if camp not in camp_ids:
                            camp = 'Other Hebrew Israelite'
                        results[church_id] = {
                            'camp': camp,
                            'confidence': result.get('confidence', 0.85)
                        }
                        confirmed += 1
                    else:
                        rejected += 1

            print(f'\rDeepSeek: {min(batch_start + BATCH_SIZE, total)}/{total} ({confirmed} confirmed, {rejected} rejected)', end='')

        except Exception as e:
            errors += len(batch_ids)
            print(f'\n  Batch error at {batch_start}: {e}')

        time.sleep(1.5)

    print(f'\nDeepSeek results: {confirmed} confirmed, {rejected} rejected, {errors} errors')
    return results, confirmed, rejected, None


def apply_updates(db, definitive, deepseek_results, camp_ids, bhi_id):
    """Apply classification updates to the churches table."""
    all_updates = {}

    # Merge definitive pattern matches
    for church_id, camp in definitive.items():
        all_updates[church_id] = {'camp': camp, 'confidence': 0.95}

    # Merge DeepSeek results
    for church_id, result in deepseek_results.items():
        all_updates[church_id] = {
            'camp': result['camp'],
            'confidence': result['confidence']
        }

    print(f'\nApplying updates to {len(all_updates)} churches...')

    updated = 0
    faith_updates = 0
    tax_updates = 0

    for i, (church_id, info) in enumerate(all_updates.items()):
        progress_bar(i + 1, len(all_updates), 'Apply updates')

        camp = info['camp']
        confidence = info['confidence']

        # Determine the taxonomy_id for this camp
        tax_id = camp_ids.get(camp, camp_ids.get('Other Hebrew Israelite', bhi_id))

        # Get current values
        cur = db.execute(
            "SELECT faith, taxonomy_id, tradition FROM churches WHERE id=?",
            (church_id,)
        )
        row = cur.fetchone()
        if not row:
            continue

        current_faith, current_tax_id, current_tradition = row

        # Build update
        updates = []
        params = []

        # Determine faith: these are Abrahamic, not Christian/Jewish/Islam
        new_faith = 'Other Abrahamic'

        if current_faith != new_faith:
            updates.append("faith = ?")
            params.append(new_faith)
            faith_updates += 1

        if current_tax_id != tax_id:
            updates.append("taxonomy_id = ?")
            params.append(tax_id)
            tax_updates += 1

        # Always set tradition
        if current_tradition != camp:
            updates.append("tradition = ?")
            params.append(camp)

        # Set confidence columns
        updates.append("bh_confidence = ?")
        params.append(confidence)
        updates.append("bh_classification_source = ?")
        params.append('pattern_match' if church_id in definitive else 'deepseek')
        updates.append("bh_updated = ?")
        params.append(datetime.now().isoformat())

        # Fix landmark_type if currently wrong (e.g., temple→church for non-Hindu)
        cur = db.execute("SELECT landmark_type FROM churches WHERE id=?", (church_id,))
        lt = cur.fetchone()[0]
        if lt in ('temple',) and current_faith in ('Christian', 'Hindu', 'Islam'):
            updates.append("landmark_type = ?")
            params.append('other')

        if updates:
            sql = f"UPDATE churches SET {', '.join(updates)} WHERE id = ?"
            params.append(church_id)
            db.execute(sql, params)
            updated += 1

    db.commit()
    progress_bar(len(all_updates), len(all_updates), 'Apply updates')
    print(f'\n  {updated} churches updated')
    print(f'  {faith_updates} faith corrections')
    print(f'  {tax_updates} taxonomy corrections')
    return updated


def main():
    db = get_db()

    print('=' * 60)
    print('Black Hebrew Israelite Classification')
    print('=' * 60)

    # Step 1: Add taxonomy nodes
    print('\n1. Adding taxonomy nodes...')
    node_map, camp_ids, bhi_id = add_taxonomy_nodes(db)

    # Step 2: Find candidates
    print('\n2. Finding candidates...')
    definitive, needs_deepseek = find_candidates(db)

    # Step 3: DeepSeek classification for ambiguous ones
    print('\n3. DeepSeek classification...')
    deepseek_results, confirmed, rejected, enrichment_log = deepseek_classify(
        db, needs_deepseek, camp_ids, bhi_id
    )

    # Step 4: Ensure enrichment columns exist
    print('\n4. Ensuring enrichment columns...')
    import sqlite3 as sqlite3_direct
    raw_conn = sqlite3_direct.connect('churches.db')
    for col in ['bh_confidence', 'bh_classification_source', 'bh_updated']:
        try:
            raw_conn.execute(f"ALTER TABLE churches ADD COLUMN {col} TEXT")
            print(f'  Added column: {col}')
        except sqlite3_direct.OperationalError:
            pass  # Column already exists
    raw_conn.commit()
    raw_conn.close()

    # Step 5: Apply updates
    print('\n5. Applying updates...')
    updated = apply_updates(db, definitive, deepseek_results, camp_ids, bhi_id)

    # Summary
    total_classified = len(definitive) + len(deepseek_results)
    print(f'\n{"=" * 60}')
    print(f'SUMMARY')
    print(f'  Total classified: {total_classified}')
    print(f'  Pattern match: {len(definitive)}')
    print(f'  DeepSeek confirmed: {confirmed}')
    print(f'  DeepSeek rejected: {rejected}')
    print(f'  DB updates applied: {updated}')
    print(f'  Taxonomy nodes added: {len(node_map)}')
    print(f'{"=" * 60}')

    return total_classified


if __name__ == '__main__':
    main()
