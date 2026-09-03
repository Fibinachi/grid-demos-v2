"""
Batch Review Tool: Show and apply candidate record transformations.

Usage:
    python _review_batch.py                      # show batch 1 (default, phase2)
    python _review_batch.py --batch 2            # show batch 2
    python _review_batch.py --apply              # apply batch 1 changes to DB
    python _review_batch.py --batch 2 --apply    # apply batch 2
    python _review_batch.py --rule phase2        # Phase 2: ST/MT/FT/CTR expansion
    python _review_batch.py --rule phase3        # Phase 3: possessive apostrophe
    python _review_batch.py --rule phase4        # Phase 4: INC stripping
    python _review_batch.py --rule all           # all rules combined
"""

import re
import sys
import sqlite3
from datetime import datetime, timezone

BATCH_SIZE = 100
DB_PATH = r'E:\grid\churches.db'

# ── Parse args ──────────────────────────────────────────────────────
args = [a for a in sys.argv[1:] if not a.startswith('-')]
batch_num = 1
rule = 'phase2'  # default
apply_mode = False

for i, a in enumerate(sys.argv):
    if a == '--batch' and i + 1 < len(sys.argv):
        batch_num = int(sys.argv[i + 1])
    if a == '--rule' and i + 1 < len(sys.argv):
        rule = sys.argv[i + 1]
    if a == '--apply':
        apply_mode = True


# ── Transformation Rules ────────────────────────────────────────────
# Phase 2: Word-boundary abbreviation expansion
PHASE2_PATTERNS = [
    (re.compile(r'\b1ST\b', re.IGNORECASE), 'FIRST', '1ST -> FIRST'),
    # STE (abbreviated Sainte, French feminine) — not "Suite" (address)
    (re.compile(r'\bSTE\.(?!\s*\d)', re.IGNORECASE), 'SAINTE', 'STE. -> SAINTE'),
    (re.compile(r'\bSTE\b(?!\s*\d)', re.IGNORECASE), 'SAINTE', 'STE -> SAINTE'),
    (re.compile(r'\bST(?!REET)\b', re.IGNORECASE), 'SAINT', 'ST/St -> SAINT (word boundary)'),
    (re.compile(r'\bCTR\b', re.IGNORECASE), 'CENTER', 'CTR -> CENTER'),
    (re.compile(r'\bMT\b', re.IGNORECASE), 'MOUNT', 'MT -> MOUNT'),
    (re.compile(r'\bFT\b', re.IGNORECASE), 'FORT', 'FT -> FORT'),
]

# Phase 3: Possessive apostrophe
PHASE3_PAT = re.compile(r"\b(SAINT\s+\w+)\s+S(?=\s|$)")

# Phase 4: Strip INC/INC.
STRIP_INC_RE = re.compile(r',?\s*INC\.?\s*$')
MID_INC_RE = re.compile(r',?\s*INC\.?\s+')

# ── Street Name Exclusion ───────────────────────────────────────────
# These look like "ST = Saint" but are actually "ST = Street" in
# names like "MAIN ST UNITED CHURCH", "FIRST ST BAPTIST CHURCH".
ST_STREET_EXCLUDE = re.compile(
    r'\b(?:MAIN|FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH'
    r'|NINTH|TENTH|OAK|ELM|MAPLE|PINE|CEDAR|BIRCH|WALNUT|CHERRY|BEECH'
    r'|PARK|LAKE|RIVER|HILL|RIDGE|VIEW|VALE|GROVE|CREST|BROOK|MEADOW'
    r'|HIGH|LOW|BROAD|NORTH|SOUTH|EAST|WEST|CENTRAL|GRAND|ROYAL|QUEEN'
    r'|KING|PRINCE|VICTORIA|WELLINGTON|MARKET|CHURCH)\s+ST\b',
    re.IGNORECASE
)
# ── Support Org Classification ──────────────────────────────────────
# These are real organizations but not churches - trusts, foundations,
# boards, councils, societies (charitable), etc. They support churches.
# We tag them rather than expanding abbreviations.
SUPPORT_ORG_PATTERNS = [
    # Trusts / estates / bequests / foundations
    (r'\bTRUST\b', 'trust/estate'),
    (r'\bESTATE\b', 'trust/estate'),
    (r'\bBEQUEST\b', 'trust/estate'),
    (r'\bFOUNDATION\b', 'foundation'),
    (r'\bTRUSTEE\S*\b', 'trustee'),
    # Boards and councils
    (r'\bBOARD\s+OF\b', 'board/council'),
    (r'\bCOUNCIL\b', 'board/council'),
    (r'\bCOMMITTEE\b', 'board/council'),
    # Wardens
    (r'\bWARDEN\b', 'warden'),
    # Charitable societies (not religious congregations)
    (r'\bSOCIETY\s+OF\s+ST\b', 'society'),
    (r'\bSOCIETY\s+OF\s+SAINT\b', 'society'),
    (r'\bSOCIETY\s+FOR\b', 'society'),
    # Church support - friends of, league, auxiliary
    (r'\bFRIENDS\s+OF\b', 'support_group'),
    (r'\bLEAGUE\b', 'support_group'),
    (r'\bGUILD\b', 'support_group'),
    (r'\bAUXILIARY\b', 'support_group'),
    # YMCA (not a church)
    (r'\bY\s*M\s*C\s*A\b', 'ymca'),
]

def classify_support_org(name):
    """Classify a name as a support org. Returns category label or None."""
    upper = name.upper()
    for pat, category in SUPPORT_ORG_PATTERNS:
        if re.search(pat, upper):
            return category
    return None

SUPPORT_TAG = '[SUPPORT ORG]'

def apply_rules(name, rule_set):
    """Apply the selected rule set to a name, return (new_name, rule_desc_or_None, support_tag_or_None)."""
    original = name
    changes = []
    support_tag = classify_support_org(name)

    # Skip abbreviation expansion for support orgs only
    if rule_set in ('phase2', 'all') and not support_tag:
        for i, (pat, repl, desc) in enumerate(PHASE2_PATTERNS):
            if pat.search(name):
                # Skip ST->SAINT if this is actually a street name (e.g., "MAIN ST")
                if repl == 'SAINT' and ST_STREET_EXCLUDE.search(name):
                    continue
                name = pat.sub(repl, name)
                changes.append(desc)

    if rule_set in ('phase3', 'all') and not support_tag:
        m = PHASE3_PAT.search(name)
        m2 = re.compile(r"\b(SAINT\s+\w+'\w+)\s+S(?=\s|$)").search(name)
        if m and not m2:
            name = PHASE3_PAT.sub(r"\1'S", name)
            changes.append("Possessive apostrophe")

    if rule_set in ('phase4', 'all') and not support_tag:
        new_name = STRIP_INC_RE.sub('', name)
        new_name = MID_INC_RE.sub(' ', new_name).strip()
        # Strip corporate legal suffixes: LLC, PLLC, LTD (not identifiers like MEDICAL CENTER)
        new_name = re.sub(r'\s*,?\s*(?:LLC\.?|PLLC\.?|LTD\.?)', '', new_name).strip()
        new_name = re.sub(r'\s{2,}', ' ', new_name)
        if new_name and new_name != name:
            name = new_name
            changes.append("Strip INC/LLC/LTD")

    if name != original:
        return name, ', '.join(changes), support_tag
    return original, None, support_tag


# ── Query candidates ────────────────────────────────────────────────
def build_query(rule_set):
    """Build SQL query for candidates based on rule set."""
    if rule_set == 'phase2':
        return """
            SELECT rowid, name FROM churches
            WHERE ((name LIKE '% ST %' AND name NOT LIKE '% STREET %' AND name NOT LIKE '% ST.%')
                OR (name LIKE '% CTR %')
                OR (name LIKE '% MT %' AND name NOT LIKE '% MT.%')
                OR (name LIKE '% FT %' AND name NOT LIKE '% FT.%')
                OR (name LIKE '% STE %' OR name LIKE '% STE.%' OR name LIKE '%-STE %'))
            ORDER BY rowid
        """
    elif rule_set == 'phase3':
        return """
            SELECT rowid, name FROM churches
            WHERE (name LIKE '% SAINT % S' OR name LIKE 'SAINT % S')
              AND name NOT LIKE '% INC' AND name NOT LIKE '% INC.'
            ORDER BY rowid
        """
    elif rule_set == 'phase4':
        return """
            SELECT rowid, name FROM churches
            WHERE name LIKE '% INC' OR name LIKE '% INC.'
            ORDER BY rowid
        """
    else:  # 'all'
        return """
            SELECT rowid, name FROM churches
            WHERE ((name LIKE '% ST %' AND name NOT LIKE '% STREET %' AND name NOT LIKE '% ST.%')
                OR (name LIKE '% CTR %')
                OR (name LIKE '% MT %' AND name NOT LIKE '% MT.%')
                OR (name LIKE '% FT %' AND name NOT LIKE '% FT.%')
                OR (name LIKE '% STE %' OR name LIKE '% STE.%' OR name LIKE '%-STE %')
                OR (name LIKE '% SAINT % S' OR name LIKE 'SAINT % S')
                OR name LIKE '% INC' OR name LIKE '% INC.')
            ORDER BY rowid
        """


# ── Main ────────────────────────────────────────────────────────────
def main():
    db = sqlite3.connect(DB_PATH)
    
    # Get total
    sql = build_query(rule)
    c = db.execute(f"SELECT COUNT(*) FROM ({sql})")
    total = c.fetchone()[0]
    
    offset = (batch_num - 1) * BATCH_SIZE
    c = db.execute(f"{sql} LIMIT {BATCH_SIZE} OFFSET {offset}")
    rows = c.fetchall()

    if not rows:
        print(f"No more candidates (batch {batch_num}, offset {offset}).")
        db.close()
        return

    rule_label = {
        'phase2': 'Phase 2 - Abbreviation expansion',
        'phase3': 'Phase 3 - Possessive apostrophe',
        'phase4': 'Phase 4 - Strip INC/INC.',
        'all': 'All rules combined',
    }.get(rule, rule)

    if apply_mode:
        # ── APPLY MODE ──────────────────────────────────────────────
        print(f"{'='*80}")
        print(f"  APPLYING: {rule_label}")
        print(f"  Batch {batch_num} (records {offset+1}-{offset+len(rows)} of {total:,} total candidates)")
        print(f"{'='*80}")
        
        applied = 0
        skipped_support = 0
        skipped_street = 0
        skipped_nochange = 0
        
        for i, (church_id, name) in enumerate(rows):
            new_name, rule_desc, support_tag = apply_rules(name, rule)
            
            if support_tag:
                skipped_support += 1
                print(f"  [{offset+i+1:3d}] SKIP (support org: {support_tag}) \"{name[:70]}\"")
                continue
            
            if not rule_desc:
                skipped_nochange += 1
                continue
            
            # Check if street-name exclusion already handled (no change)
            if new_name == name:
                skipped_street += 1
                print(f"  [{offset+i+1:3d}] SKIP (street name) \"{name[:70]}\"")
                continue
            
            # Apply the change
            db.execute("UPDATE churches SET name = ? WHERE rowid = ?", (new_name, church_id))
            applied += 1
            print(f"  [{offset+i+1:3d}] APPLIED [{rule_desc:30s}] \"{name[:60]}\"")
            print(f"         -> \"{new_name[:60]}\"")
        
        # Log batch provenance
        now = datetime.now(timezone.utc).isoformat()
        db.execute("""
            INSERT INTO provenance_log
                (source, script_name, started_at, completed_at,
                 churches_updated, churches_inserted, records_attempted, notes)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?)
        """, ('phase2_expansion', '_review_batch.py',
              now, now, applied, len(rows),
              f"Batch {batch_num} Phase2 expansions (ST->SAINT, MT->MOUNT, FT->FORT, CTR->CENTER, 1ST->FIRST)"))
        
        db.commit()
        
        db.commit()
        print()
        print(f"{'─'*80}")
        print(f"  Applied: {applied} | Skipped (support org): {skipped_support} | Skipped (no change): {skipped_nochange} | Total: {len(rows)}")
        print(f"  Run: python _review_batch.py --batch {batch_num + 1} --rule {rule}")
        print(f"  (add --apply to apply next batch, or omit --apply to review first)")
    
    else:
        # ── SHOW MODE ────────────────────────────────────────────────
        print(f"{'='*80}")
        print(f"  RULE: {rule_label}")
        print(f"  Batch {batch_num} (records {offset+1}-{offset+len(rows)} of {total:,} total candidates)")
        print(f"{'='*80}")
        print()
        
        changed_count = 0
        support_count = 0
        for i, (church_id, name) in enumerate(rows):
            new_name, rule_desc, support_tag = apply_rules(name, rule)
            num = offset + i + 1
            
            name_len = len(name)
            if support_tag:
                support_count += 1
                print(f"  [{num:3d}] {SUPPORT_TAG} ({support_tag})")
                print(f"        (row={church_id}) (len={name_len}) \"{name[:80]}\"")
                print(f"         (skip expansion - not a church)")
            elif rule_desc:
                changed_count += 1
                print(f"  [{num:3d}] (row={church_id}) (len={name_len}) \"{name[:80]}\"")
                print(f"         {rule_desc:30s} -> \"{new_name[:80]}\"")
            else:
                print(f"  [{num:3d}] (row={church_id}) (len={name_len}) \"{name[:80]}\"")

            print()
    
        print(f"{'─'*80}")
        print(f"  Batch: {changed_count} changed | {support_count} support orgs (tagged) | {len(rows)} total shown")
        print(f"  Run: python _review_batch.py --batch {batch_num + 1} --rule {rule}")

    db.close()


if __name__ == '__main__':
    main()
