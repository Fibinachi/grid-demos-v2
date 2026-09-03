"""
Investigate how many state-only records (null GPS, US, state only)
are potential duplicates of better-described churches with GPS.

Checks:
  1. Same name + same state (exact name match)
  2. Same name_transliterated + same state
  3. Normalized name (lower, stripped) + same state
  4. Same source + same state (same scraper batch)
  5. Name prefix match + same state (e.g. "First Baptist" -> "First Baptist Church of Springfield")
"""
import sqlite3
import time
import shutil

DB = 'E:/grid/churches.db'
t0 = time.time()

def progress_bar(current, total, start_time, extra=""):
    cols = shutil.get_terminal_size().columns - 20
    bar_w = max(10, cols - 40)
    pct = current / total if total else 0
    filled = int(bar_w * pct)
    bar = '█' * filled + '░' * (bar_w - filled)
    elapsed = time.time() - start_time
    rate = current / elapsed if elapsed > 0 and current > 0 else 0
    if rate > 0 and current < total:
        eta = (total - current) / rate
        eta_str = f"{eta:.0f}s"
    else:
        eta_str = "done!"
    print(f"\r  {current:>7,}/{total:<7,} [{bar}] {pct:>5.1f}% | {rate:>,.0f} rec/s | ETA {eta_str} {extra}", end='', flush=True)

db = sqlite3.connect(DB)
db.execute("PRAGMA synchronous=OFF")

# ── 1. Load state-only records (null GPS, US, state, no city/zip/address) ──
print("Loading state-only records...")
state_only = db.execute("""
    SELECT rowid, id, name, COALESCE(NULLIF(TRIM(name_transliterated),''), name) AS search_name,
           state, source, faith
    FROM churches
    WHERE latitude IS NULL AND longitude IS NULL
    AND country = 'US'
    AND state IS NOT NULL AND state != ''
    AND (city IS NULL OR city = '')
    AND (zip IS NULL OR zip = '')
    AND (address IS NULL OR address = '')
    ORDER BY rowid
""").fetchall()
print(f"  State-only records: {len(state_only):,}")

# ── 2. Load GPS-having records (for dedup matching) ──
print("Loading GPS-having records...")
gps_records = db.execute("""
    SELECT rowid, id,
           COALESCE(NULLIF(TRIM(name_transliterated),''), name) AS search_name,
           name AS raw_name, state, source, faith, city, address, zip
    FROM churches
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    AND country = 'US'
    AND state IS NOT NULL AND state != ''
    AND name IS NOT NULL AND name != ''
    ORDER BY rowid
""").fetchall()
print(f"  GPS-having records: {len(gps_records):,}")

db.close()

# ── 3. Build lookup structures ──
# Index by (state, lower_name) for fast matching
from collections import defaultdict

print("\n── DEDUP ANALYSIS ──\n")

# Build index: state -> {lower_name -> [records]}
state_name_index = defaultdict(lambda: defaultdict(list))
t_index = time.time()
for i, r in enumerate(gps_records):
    st = r[4]
    nm = r[2]  # search_name (transliterated or raw)
    if nm:
        key = nm.strip().lower()
        state_name_index[st][key].append(r)
    progress_bar(i + 1, len(gps_records), t_index, "| building index")
print()

# ── 4. Check each state-only record against index ──
# Categories:
# A: Exact name match in same state -> high confidence duplicate
# B: Name starts with match (prefix) in same state -> possible duplicate
# C: No name -> can't assess
# D: No match at all -> probably unique

cat_a_exact = []     # (state_only_rowid, state_only_name, matched_rowid, matched_name, state)
cat_b_prefix = []    # (state_only_rowid, state_only_name, matched_rowid, matched_name, state)
cat_b_reverse = []   # GPS record name starts with state-only name
cat_c_noname = 0
cat_d_nomatch = 0

t_match = time.time()
for i, so in enumerate(state_only):
    so_rowid, so_id, so_raw_name, so_sname, so_state, so_source, so_faith = so
    so_key = so_sname.strip().lower() if so_sname else ''

    if not so_key:
        cat_c_noname += 1
        progress_bar(i + 1, len(state_only), t_match, f"| A:{len(cat_a_exact)} B:{len(cat_b_prefix)} D:{cat_d_nomatch}")
        continue

    matches = state_name_index.get(so_state, {})

    # Exact match check
    if so_key in matches:
        for matched in matches[so_key]:
            cat_a_exact.append((so_rowid, so_raw_name, matched[0], matched[2], so_state, so_source, matched[5]))
        progress_bar(i + 1, len(state_only), t_match, f"| A:{len(cat_a_exact)} B:{len(cat_b_prefix)} D:{cat_d_nomatch}")
        continue

    # Prefix match: does any GPS name start with the state-only name (or vice versa)?
    found_prefix = False
    for gps_key, gps_list in matches.items():
        # GPS name starts with state-only name
        if gps_key.startswith(so_key) and len(gps_key) > len(so_key):
            for matched in gps_list:
                cat_b_prefix.append((so_rowid, so_raw_name, matched[0], matched[2], so_state, 'gps_starts_with_so'))
            found_prefix = True
        # State-only name starts with GPS name
        elif so_key.startswith(gps_key) and len(so_key) > len(gps_key):
            for matched in gps_list:
                cat_b_prefix.append((so_rowid, so_raw_name, matched[0], matched[2], so_state, 'so_starts_with_gps'))
            found_prefix = True

    if found_prefix:
        progress_bar(i + 1, len(state_only), t_match, f"| A:{len(cat_a_exact)} B:{len(cat_b_prefix)} D:{cat_d_nomatch}")
    else:
        cat_d_nomatch += 1
        progress_bar(i + 1, len(state_only), t_match, f"| A:{len(cat_a_exact)} B:{len(cat_b_prefix)} D:{cat_d_nomatch}")

print()

# ── 5. Report ──
print(f"\n{'='*60}")
print(f"STATE-ONLY DUPLICATE ANALYSIS")
print(f"{'='*60}")
print(f"Total state-only records: {len(state_only):,}")
print(f"\nCategory A (EXACT name + state match): {len(cat_a_exact):,}")
print(f"  -> High confidence duplicate: same name in same state as a GPS-having record")
print(f"\nCategory B (PARTIAL name + state match): {len(cat_b_prefix):,}")
print(f"  -> Possible duplicate: one name is a prefix of the other")
print(f"\nCategory C (NO name to match): {cat_c_noname:,}")
print(f"  -> Can't assess: state-only record has no name")
print(f"\nCategory D (NO match found): {cat_d_nomatch:,}")
print(f"  -> Probably unique: no name overlap with GPS records in same state")

# Deduplicate the match counts (one state-only record might match multiple GPS records)
unique_a = len(set(r[0] for r in cat_a_exact))
unique_b = len(set(r[0] for r in cat_b_prefix))
unique_any = len(set(r[0] for r in cat_a_exact + cat_b_prefix))
print(f"\n── Unique state-only records affected ──")
print(f"  Exact match (A):    {unique_a:,}")
print(f"  Partial match (B):  {unique_b:,}")
print(f"  Any match (A|B):    {unique_any:,}")
print(f"  No match (C|D):     {cat_c_noname + cat_d_nomatch:,}")

# ── 6. Sample for manual review ──
print(f"\n── SAMPLE: Exact matches (first 20) ──")
for r in cat_a_exact[:20]:
    so_rid, so_name, gps_rid, gps_name, st, so_src, gps_src = r
    print(f"  SO: {so_name:.50s} ({st}) [{so_src:.20s}]")
    print(f"  GPS: {gps_name:.50s} ({st}) [{gps_src:.20s}]")
    print()

print(f"\n── SAMPLE: Partial matches (first 20) ──")
for r in cat_b_prefix[:20]:
    so_rid, so_name, gps_rid, gps_name, st, match_type = r
    print(f"  SO:     {so_name:.60s} ({st})")
    print(f"  GPS:    {gps_name:.60s} ({st})")
    print(f"  Type:   {match_type}")
    print()

# ── 7. Check source overlap for exact matches ──
if cat_a_exact:
    from collections import Counter
    sources_so = Counter()
    sources_gps = Counter()
    for r in cat_a_exact:
        sources_so[r[5]] += 1
        sources_gps[r[6]] += 1
    print(f"\n── Exact match source breakdown ──")
    print("  State-only sources:")
    for src, cnt in sources_so.most_common():
        print(f"    {src:.30s}: {cnt:,}")
    print("  GPS-having sources:")
    for src, cnt in sources_gps.most_common():
        print(f"    {src:.30s}: {cnt:,}")

# ── 8. Faith distribution ──
faith_so = Counter()
for r in state_only:
    faith_so[r[6]] += 1
print(f"\n── State-only faith distribution ──")
for f, cnt in faith_so.most_common(20):
    print(f"  {f if f else 'NULL':.20s}: {cnt:,}")

print(f"\nElapsed: {time.time()-t0:.1f}s")
