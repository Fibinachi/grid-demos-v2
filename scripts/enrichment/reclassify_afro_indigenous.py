"""
reclassify_afro_indigenous.py — Reclassify Afro-Diasporic and Indigenous traditions.

These are currently miscategorized as Christian (or random faiths) by name heuristics.
They get tagged Christian because many contain 'church', 'temple', 'igreja', 'dios', 'cristo'
in their names, but their theology is NOT Christian (no central role for Jesus as redeemer).

New classification:
  faith = 'Other'
  faith_tradition = 'Afro-Diasporic' or 'Indigenous'
  subtradition = specific tradition (e.g. 'Umbanda', 'Candomblé', 'Native American Church')

Usage:
    python scripts/enrichment/reclassify_afro_indigenous.py          # full run
    python scripts/enrichment/reclassify_afro_indigenous.py --limit 10  # test
    python scripts/enrichment/reclassify_afro_indigenous.py --preview   # dry run
"""
import argparse, os, sys, time, sqlite3, re

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)
from gw_db import connect, Provenance

DB_PATH = os.path.join(PROJECT, 'churches.db')

# ── AFRO-DIASPORIC PATTERNS ──────────────────────────────────────
# (keyword, subtradition) — ordered most-specific first

AFRO_PATTERNS = [
    # Candomble
    (r'\bcandombl[ée]\b', 'Candomblé'),
    (r'\b(roça|barracão)\s+(de\s+)?candombl[ée]\b', 'Candomblé'),
    (r'\b(casa|terreiro|templo)\s+de\s+candombl[ée]\b', 'Candomblé'),
    (r'\bilê?\s+as[ée]\b.*\b(ogum|xango|iemanja|oxala|oxossi|iansa)\b', 'Candomblé'),
    
    # Umbanda
    (r'\bumbanda\b', 'Umbanda'),
    (r'\btenda\s+de\s+umbanda\b', 'Umbanda'),
    (r'\bcentro\s+esp[ií]rita\b.*\bumbanda\b', 'Umbanda'),
    (r'\bterreiro\s+de\s+umbanda\b', 'Umbanda'),
    
    # Santeria / Lukumi
    (r'\bsanter[ií]a\b', 'Santería'),
    (r'\blukum[ií]\b', 'Santería'),
    (r'\blucum[ií]\b', 'Santería'),
    
    # Vodou
    (r'\bvodou[n]?\b', 'Vodou'),
    (r'\bvoodoo\b', 'Vodou'),
    (r'\bvodoun?\b', 'Vodou'),
    (r'\bperistyle\b', 'Vodou'),
    (r'\bhoun?for\b', 'Vodou'),
    
    # Yoruba/Ifa
    (r'\byoruba\b', 'Yoruba/Ifá'),
    (r'\bifa\b', 'Yoruba/Ifá'),
    (r'\borisha\b', 'Yoruba/Ifá'),
    (r'\borixa\b', 'Yoruba/Ifá'),
    (r'\boricha\b', 'Yoruba/Ifá'),
    (r'\bbabalawo\b', 'Yoruba/Ifá'),
    (r'\b(orixá|orixa)\s+(ogum|xango|iemanja|oxala|oxossi|iansa)\b', 'Yoruba/Ifá'),
    
    # Macumba (derogatory in some contexts but used as self-identifier in data)
    (r'\bmacumba\b', 'Macumba'),
    
    # Generic Afro-Brazilian terreiro
    (r'\bterreiro\b', 'Umbanda'),
    (r'\bilê\s+ax[ée]\b', 'Candomblé'),
    
    # Deity names in context (only if not already matched above)
    (r'\bxang[ôo]\b', 'Candomblé'),
    (r'\bchango\b', 'Santería'),
    (r'\biemanj[áa]\b', 'Candomblé'),
    (r'\boxal[áa]\b', 'Candomblé'),
    (r'\box[óo]ssi\b', 'Candomblé'),
    (r'\bogum\b', 'Candomblé'),
    (r'\bians[ãa]\b', 'Candomblé'),
    (r'\biansa\b', 'Candomblé'),
]

# ── INDIGENOUS PATTERNS ──────────────────────────────────────────

INDIGENOUS_PATTERNS = [
    (r'\bnative\s+american\s+church\b', 'Native American Church'),
    (r'\bpeyote\s+church\b', 'Native American Church'),
    (r'\bpeyote\s+way\b', 'Native American Church'),
    (r'^(peyote|peyotism)$', 'Peyotism'),
    (r'\blonghouse\b', 'Indigenous Longhouse Tradition'),
    (r'\bsweat\s+lodge\b', 'Indigenous (Sweat Lodge)'),
    (r'\bmedicine\s+wheel\b', 'Indigenous (Medicine Wheel)'),
    (r'\bsun\s+dance\b', 'Indigenous (Sun Dance)'),
]

# ── FALSE POSITIVE EXCLUSIONS ────────────────────────────────────
# Records matching these patterns should NOT be reclassified

FALSE_POSITIVES = [
    # "Santeria" false positives
    r'\bsanter[ií]a\b.*\bcatólica\b',          # "Santeria Católica" — actually Catholic
    r'\bsanter[ií]a\b.*\bcristo\b',              # "Santeria Cristo" — actually Catholic
    r'\bsanter[ií]a\b.*\bpablo\b',               # "Santeria San Pablo" — Catholic saint shop
    
    # "Kiva" false positives
    r'\bakiva\b',                                 # Jewish name
    
    # "Falun" town in Sweden
    r'\b(in|i|i\s)\s*falun\b',
    r'^(falun|faluns?)\s',
]


def is_false_positive(name, patterns=FALSE_POSITIVES):
    """Check if a name is a known false positive."""
    if not name:
        return False
    for pat in patterns:
        if re.search(pat, name, re.IGNORECASE):
            return True
    return False


def classify_record(name, current_faith):
    """
    Classify a single record. Returns (faith, faith_tradition, subtradition) or None.
    """
    if not name:
        return None
    
    if is_false_positive(name):
        return None
    
    name_lower = name.lower()
    
    # Check Afro-Diasporic patterns
    for pattern, subtrad in AFRO_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            return ('Other', 'Afro-Diasporic', subtrad)
    
    # Check Indigenous patterns
    for pattern, subtrad in INDIGENOUS_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            return ('Other', 'Indigenous', subtrad)
    
    return None


def main():
    parser = argparse.ArgumentParser(description='Reclassify Afro-Diasporic and Indigenous traditions')
    parser.add_argument('--limit', type=int, default=None, help='Limit to N records (test)')
    parser.add_argument('--preview', action='store_true', help='Dry run — show what would change')
    args = parser.parse_args()
    
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    c = conn.cursor()
    
    # Get all records with names that might match
    all_groups = [p[0] for p in AFRO_PATTERNS + INDIGENOUS_PATTERNS]
    
    # Build a single WHERE clause from all patterns
    where_parts = []
    params = []
    for pat in all_groups:
        # Convert regex to LIKE-friendly patterns for initial filtering
        # We use broad LIKE patterns then filter with regex
        where_parts.append("name LIKE ?")
        params.append(f'%{pat.strip("\\b()^$[]+*?")[:10]}%')
    
    # Deduplicate params
    unique_params = []
    seen = set()
    for p in params:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            unique_params.append(p)
    
    where = " OR ".join(where_parts[:len(unique_params)])
    
    if not where:
        print("No patterns to match")
        return
    
    query = "SELECT id, name, faith, faith_tradition, subtradition FROM churches WHERE " + " OR ".join([f"name LIKE ?" for _ in unique_params])
    
    rows = c.execute(query, unique_params).fetchall()
    print(f"Candidate records (broad match): {len(rows):,}")
    
    # Classify each
    changes = []
    for row in rows:
        rid, name, cur_faith, cur_trad, cur_sub = row
        
        result = classify_record(name, cur_faith)
        if result is None:
            continue
        
        faith, tradition, subtradition = result
        
        # Skip if already correctly classified
        if cur_faith == faith and cur_trad == tradition and cur_sub == subtradition:
            continue
        
        changes.append((rid, name, cur_faith, cur_trad, cur_sub, faith, tradition, subtradition))
    
    print(f"Records to reclassify: {len(changes):,}")
    print()
    
    # Summarize
    from collections import Counter
    trad_counts = Counter()
    sub_counts = Counter()
    for c in changes:
        trad_counts[c[6]] += 1
        sub_counts[c[7]] += 1
    
    print("By faith_tradition:")
    for trad, cnt in trad_counts.most_common():
        print(f"  {trad:20s}: {cnt:>5,}")
    print()
    print("By subtradition:")
    for sub, cnt in sub_counts.most_common():
        print(f"  {sub:30s}: {cnt:>5,}")
    
    if args.preview:
        print(f"\n--- PREVIEW MODE — no changes made ---")
        conn.close()
        return
    
    if args.limit:
        changes = changes[:args.limit]
        print(f"\n  (limited to {args.limit})")
    
    if not changes:
        print("\nNo changes needed.")
        conn.close()
        return
    
    # Apply changes
    print(f"\nApplying {len(changes):,} reclassifications...")
    updated = 0
    errors = 0
    
    for change in changes:
        rid, name, cur_faith, cur_trad, cur_sub, faith, tradition, subtradition = change
        try:
            c.execute("""
                UPDATE churches
                SET faith = ?, faith_tradition = ?, subtradition = ?
                WHERE id = ?
            """, (faith, tradition, subtradition, rid))
            updated += 1
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error ID={rid}: {e}")
    
    conn.commit()
    print(f"  Updated: {updated:,}")
    print(f"  Errors:  {errors:,}")
    
    # Log provenance
    conn.close()
    
    # Use gw_db for provenance
    prov_conn = sqlite3.connect(DB_PATH, timeout=60)
    with Provenance(prov_conn, 'reclassify_afro_indigenous.py', source='classification_fix',
                    action='updated', fields='faith,faith_tradition,subtradition',
                    details=f'Reclassified {updated} records: Afro-Diasporic and Indigenous traditions under faith=Other'):
        pass
    
    print(f"\nDone. {updated:,} records reclassified.")
    print(f"  Afro-Diasporic: {sum(1 for c in changes if c[6] == 'Afro-Diasporic'):,}")
    print(f"  Indigenous: {sum(1 for c in changes if c[6] == 'Indigenous'):,}")


if __name__ == '__main__':
    main()
