"""
Show samples of NULL-faith records grouped by source, to help develop
classification rules.
"""
import sqlite3
from collections import Counter

conn = sqlite3.connect('churches.db', timeout=30)
c = conn.cursor()

# ── 1. Overall NULL faith breakdown ─────────────────────────────────────────
c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL")
total_null = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches")
total_all = c.fetchone()[0]
print(f"NULL faith: {total_null:,} / {total_all:,} ({total_null/total_all*100:.1f}%)")

# By source
c.execute("""
    SELECT source, COUNT(*) as cnt 
    FROM churches WHERE faith IS NULL 
    GROUP BY source ORDER BY cnt DESC
""")
print("\n=== NULL faith by source ===")
for src, cnt in c.fetchall():
    print(f"  {str(src or 'NULL'):<50} {cnt:>8,}")

# By country (top 15)
c.execute("""
    SELECT country, COUNT(*) as cnt 
    FROM churches WHERE faith IS NULL 
    GROUP BY country ORDER BY cnt DESC LIMIT 15
""")
print("\n=== NULL faith by country (top 15) ===")
for country, cnt in c.fetchall():
    print(f"  {country or 'NULL':<8} {cnt:>8,}")

# ── 2. Sample 50 records per major source ────────────────────────────────────
print("\n" + "=" * 100)
print("SAMPLES BY SOURCE (50 each, with NTEE codes where available)")
print("=" * 100)

for source in ['irs+holy_sites_enrichment', 'holy_sites_import', 
               'overture_discovery+holy_sites_enrichment', 'overture_full+holy_sites_enrichment',
               'overture+holy_sites_enrichment', 'csv_import+holy_sites_enrichment',
               'sbc_directory+holy_sites_enrichment', 'contacts+holy_sites_enrichment',
               'churchunion_scraper+holy_sites_enrichment', 'ou_api+holy_sites_enrichment']:
    
    c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL AND source = ?", (source,))
    count = c.fetchone()[0]
    if count == 0:
        continue
    
    c.execute("""
        SELECT name, city, state, country, ntee_code, denomination
        FROM churches WHERE faith IS NULL AND source = ?
        ORDER BY RANDOM() LIMIT 50
    """, (source,))
    rows = c.fetchall()
    
    print(f"\n--- {source} ({count:,} total, showing 50) ---")
    
    # Also show common NTEE codes for this source
    c.execute("""
        SELECT ntee_code, COUNT(*) FROM churches 
        WHERE faith IS NULL AND source = ? AND ntee_code IS NOT NULL AND ntee_code != ''
        GROUP BY ntee_code ORDER BY COUNT(*) DESC LIMIT 8
    """, (source,))
    ntee_codes = c.fetchall()
    if ntee_codes:
        print(f"  Top NTEE: {', '.join(f'{n}={c}' for n,c in ntee_codes)}")
    
    for name, city, state, country, ntee, denom in rows[:50]:
        n = str(name)[:65] if name else ''
        ci = str(city or '')[:15]
        st = str(state or '')[:4]
        co = str(country or '')[:4]
        nt = str(ntee or '')[:8]
        dn = str(denom or '')[:30]
        # Handle encoding issues
        try:
            print(f"  {n:<65} | {ci:<15} | {st:<4} | {co:<4} | {nt:<8} | {dn}")
        except UnicodeEncodeError:
            n_ascii = n.encode('ascii', errors='replace').decode()
            print(f"  {n_ascii:<65} | {ci:<15} | {st:<4} | {co:<4} | {nt:<8} | {dn}")

    # Common words in names for this source
    words = Counter()
    for name, *_ in rows:
        if name:
            for w in str(name).lower().split():
                if len(w) > 3 and w not in ('the', 'and', 'for', 'inc.', 'inc', 'of', 'a', 'an', 'in', 'to', 'on', 'by', 'at', 'is', 'it', 'as', 'be', 'or', 'no', 'we', 'he', 'me', 'my', 'our', 'us', 'all', 'are', 'was', 'has', 'had', 'its', 'not', 'but', 'one', 'two', 'new', 'old', 'with', 'from', 'that', 'this', 'they', 'have', 'been', 'will', 'can', 'may', 'also', 'into', 'over', 'such', 'only', 'other', 'some', 'each', 'more', 'most', 'very', 'what', 'when', 'were', 'them', 'than', 'then', 'just', 'like', 'make', 'made', 'many', 'much', 'well', 'your', 'which', 'their', 'there', 'about', 'after', 'these', 'those', 'would', 'could', 'shall', 'being', 'board', 'foundation', 'center', 'church', 'temple', 'ministries'):
                    words[w] += 1
    if words:
        top_words = words.most_common(15)
        print(f"  Common words: {', '.join(f'{w}({c})' for w,c in top_words)}")

conn.close()
