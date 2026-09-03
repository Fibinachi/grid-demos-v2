"""
Analyze partial match source breakdown — to confirm garbage records come from scrapers.
"""
import sqlite3
import time
import shutil
from collections import defaultdict

DB = 'E:/grid/churches.db'
t0 = time.time()

def progress_bar(current, total, t0, extra=''):
    cols = shutil.get_terminal_size().columns - 20
    bar_w = max(10, cols - 40)
    pct = current / total if total else 0
    filled = int(bar_w * pct)
    bar = '█' * filled + '░' * (bar_w - filled)
    elapsed = time.time() - t0
    rate = current / elapsed if elapsed > 0 and current > 0 else 0
    eta = (total - current) / rate if rate > 0 and current < total else 0
    print(f'\r  {current:>7,}/{total:<7,} [{bar}] {pct:>5.1f}% | {rate:>,.0f}/s | ETA {eta:.0f}s {extra}', end='', flush=True)

db = sqlite3.connect(DB)
db.execute('PRAGMA synchronous=OFF')

# Load state-only records
so = db.execute("""
    SELECT rowid, name, state, source
    FROM churches
    WHERE latitude IS NULL AND longitude IS NULL
    AND country = 'US' AND state IS NOT NULL AND state != ''
    AND (city IS NULL OR city = '') AND (zip IS NULL OR zip = '')
    AND (address IS NULL OR address = '')
    ORDER BY rowid
""").fetchall()

# Load GPS records
gps = db.execute("""
    SELECT rowid, COALESCE(NULLIF(TRIM(name_transliterated),''), name) AS sn, state, source
    FROM churches
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    AND country = 'US' AND state IS NOT NULL AND state != ''
    AND name IS NOT NULL AND name != ''
    ORDER BY rowid
""").fetchall()
db.close()

# Build index
idx = defaultdict(lambda: defaultdict(list))
t_idx = time.time()
for i, r in enumerate(gps):
    st, nm = r[2], r[1]
    if nm:
        idx[st][nm.strip().lower()].append(r)
    progress_bar(i + 1, len(gps), t_idx, '| index')
print()

# Classify partial matches by source and match type
cat_b_source = defaultdict(int)
cat_b_details = []

t_match = time.time()
for i, s in enumerate(so):
    so_rid, so_name, so_state, so_src = s
    if not so_name:
        continue
    so_key = so_name.strip().lower()
    matches_in_state = idx.get(so_state, {})

    found = False
    for gps_key, gps_list in matches_in_state.items():
        if gps_key.startswith(so_key) and len(gps_key) > len(so_key):
            cat_b_source[(so_src or 'NULL', 'so_prefix_of_gps')] += 1
            first_gps = gps_list[0]
            cat_b_details.append((so_name, so_state, so_src, first_gps[3], 'so_prefix_of_gps'))
            found = True
        elif so_key.startswith(gps_key) and len(so_key) > len(gps_key):
            cat_b_source[(so_src or 'NULL', 'gps_prefix_of_so')] += 1
            first_gps = gps_list[0]
            cat_b_details.append((so_name, so_state, so_src, first_gps[3], 'gps_prefix_of_so'))
            found = True

    progress_bar(i + 1, len(so), t_match, f'| found:{sum(cat_b_source.values()):,}')
print()

# Aggregate by source
src_totals = defaultdict(lambda: {'so_prefix': 0, 'gps_prefix': 0, 'total': 0})
for (src, mtype), cnt in sorted(cat_b_source.items(), key=lambda x: -x[1]):
    src_totals[src]['so_prefix' if 'so_prefix' in mtype else 'gps_prefix'] += cnt
    src_totals[src]['total'] += cnt

print()
print('=' * 70)
print('PARTIAL MATCH SOURCE BREAKDOWN')
print('=' * 70)
print(f"  {'Source':30s} {'SO->GPS':>10s} {'GPS->SO':>10s} {'Total':>10s}")
print(f"  {'-'*30} {'-'*10} {'-'*10} {'-'*10}")
for src in sorted(src_totals, key=lambda s: -src_totals[s]['total']):
    d = src_totals[src]
    print(f"  {src[:30]:30s} {d['so_prefix']:>10,} {d['gps_prefix']:>10,} {d['total']:>10,}")

# Garbage indicators by source
print()
print('=' * 70)
print('GARBAGE INDICATORS BY SOURCE')
print('=' * 70)
GARBAGE_KEYWORDS = ['JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'MAY', 'JUNE',
                    'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER',
                    'DECEMBER', ' TODAY', 'TONIGHT', 'THIS WEEK', 'ANNUAL',
                    'CONFERENCE', 'WORKSHOP', 'SEMINAR', 'BANQUET', 'LUNCHEON',
                    'BREAKFAST', 'DINNER', 'FUNDRAISER', 'BENEFIT', 'CONCERT',
                    'FESTIVAL', 'GALA', 'VACATION BIBLE', 'LENTEN', 'ADVENT']

for src in sorted(src_totals, key=lambda s: -src_totals[s]['total']):
    this_src = [d for d in cat_b_details if d[2] == src]
    long_names = [d for d in this_src if len(d[0] or '') > 80]
    comma_heavy = [d for d in this_src if (d[0] or '').count(',') >= 3]
    date_like = [d for d in this_src if any(kw in (d[0] or '').upper() for kw in GARBAGE_KEYWORDS)]

    print(f"  {src[:30]:30s} | total: {len(this_src):>5,} | long: {len(long_names):>5,} | commas>=3: {len(comma_heavy):>5,} | date/event: {len(date_like):>5,}")

# Unique state-only records per source
print()
print('=' * 70)
print('UNIQUE STATE-ONLY RECORDS PER SOURCE (ALL 17,878)')
print('=' * 70)
src_total = defaultdict(int)
for s in so:
    src_total[s[3] or 'NULL'] += 1
for src, cnt in sorted(src_total.items(), key=lambda x: -x[1]):
    print(f"  {src[:30]:30s} {cnt:>9,}")

print(f'\nElapsed: {time.time() - t0:.1f}s')
