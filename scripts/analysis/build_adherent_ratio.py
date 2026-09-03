"""
Expected vs Actual Religious Infrastructure — US County-Level Model
===================================================================
Merges ARDA 2020 adherent counts with GRID church counts per county.
Identifies over/under-served regions.

Creates: adherent_ratio_us table
"""
import sqlite3
from datetime import datetime

DB = r'E:\grid\churches.db'
db = sqlite3.connect(DB)
c = db.cursor()

# ── Schema ──
c.execute("""CREATE TABLE IF NOT EXISTS adherent_ratio_us (
    county_fips TEXT PRIMARY KEY, county_name TEXT, state TEXT,
    catholic_adherents INTEGER DEFAULT 0, evangelical_adherents INTEGER DEFAULT 0,
    mainline_adherents INTEGER DEFAULT 0, black_prot_adherents INTEGER DEFAULT 0,
    orthodox_adherents INTEGER DEFAULT 0, other_christian_adherents INTEGER DEFAULT 0,
    muslim_adherents INTEGER DEFAULT 0, jewish_adherents INTEGER DEFAULT 0,
    other_adherents INTEGER DEFAULT 0, total_adherents INTEGER DEFAULT 0,
    catholic_churches INTEGER DEFAULT 0, evangelical_churches INTEGER DEFAULT 0,
    mainline_churches INTEGER DEFAULT 0, black_prot_churches INTEGER DEFAULT 0,
    orthodox_churches INTEGER DEFAULT 0, other_christian_churches INTEGER DEFAULT 0,
    muslim_mosques INTEGER DEFAULT 0, jewish_synagogues INTEGER DEFAULT 0,
    other_facilities INTEGER DEFAULT 0, total_facilities INTEGER DEFAULT 0,
    total_population INTEGER DEFAULT 0,
    adherence_rate REAL DEFAULT 0,
    catholic_ratio REAL DEFAULT 0, evangelical_ratio REAL DEFAULT 0,
    mainline_ratio REAL DEFAULT 0, overall_ratio REAL DEFAULT 0,
    saturation TEXT DEFAULT 'unknown',
    source TEXT DEFAULT 'ARDA 2020 + GRID', updated TEXT
)""")
c.execute("DELETE FROM adherent_ratio_us")

# ── ARDA denom_code → broad tradition ──
arda_map = {
    'CATH': 'catholic', 'CC': 'catholic', 'EORD': 'catholic',
    'SBC': 'evangelical', 'NDP': 'evangelical', 'AG': 'evangelical',
    'LCMS': 'evangelical', 'PCA': 'evangelical', 'COC': 'evangelical',
    'CG': 'evangelical', 'FWB': 'evangelical', 'NAZ': 'evangelical',
    'WSL': 'evangelical', 'CMA': 'evangelical', 'FGC': 'evangelical',
    'EC': 'evangelical', 'EFC': 'evangelical', 'BSQ': 'evangelical',
    'CCCS': 'evangelical', 'VTN': 'evangelical', 'SOC': 'evangelical',
    'ADV': 'evangelical', 'PNT': 'evangelical', 'BNT': 'evangelical',
    'UMC': 'mainline', 'ELCA': 'mainline', 'PCUSA': 'mainline',
    'TEC': 'mainline', 'UCC': 'mainline', 'ABC': 'mainline',
    'DOC': 'mainline', 'RC': 'mainline', 'MOR': 'mainline',
    'NBC': 'black_prot', 'PNBC': 'black_prot', 'NHBC': 'black_prot',
    'AME': 'black_prot', 'AMEZ': 'black_prot', 'CME': 'black_prot',
    'COGIC': 'black_prot', 'FBH': 'black_prot',
    'GOR': 'orthodox', 'ROR': 'orthodox', 'AOR': 'orthodox',
    'LDS': 'other_christian', 'JW': 'other_christian',
    'MUS': 'muslim', 'JEW': 'jewish',
    'BUD': 'other', 'HIN': 'other', 'BAH': 'other', 'SIK': 'other',
}

# ── Aggregate ARDA by county ──
print("Aggregating ARDA adherents by county...")
county_adh = {}
for code, tradition in arda_map.items():
    c.execute("""SELECT county_fips, SUM(arda_adherents) 
        FROM arda_counts WHERE denom_code=? GROUP BY county_fips""", (code,))
    for fips, adh in c.fetchall():
        county_adh.setdefault(fips, dict.fromkeys(
            ['catholic','evangelical','mainline','black_prot','orthodox',
             'other_christian','muslim','jewish','other'], 0))
        county_adh[fips][tradition] += (adh or 0)
print(f"  {len(county_adh):,} counties from ARDA")

# ── GRID facility counts per county ──
print("Counting GRID facilities per county...")
# Map specific Protestant taxonomy IDs → subtype
# Only count churches with SPECIFIC denominational taxonomy IDs (not umbrella nodes)
# IDs sourced from taxonomy table inspection

# Evangelical Protestant taxonomy IDs
evan_ids = (207,208,212,213,217,218,274,276,281,283,284,285,286,287,290,291,293,294,295,296,297,
    303,304,305,306,309,310,311,312,314,315,316,345,346,347,348,349,350,352,355,356,357,359,360,
    361,365,375,376,377,378,379,402,407,408,409,412,413,414,415,416,417,418,421,423,426,427,428,
    434,435,436,437,697)
# Mainline Protestant (UMC, ELCA, PCUSA, TEC, UCC, ABC, DOC, etc.)
main_ids = (279,289,351,353,354,358,362,364,380,381,382,383,424,425,429,430,431,432,433)
# Black Protestant (NBC, AME, AMEZ, CME, COGIC, Progressive Baptist)
blk_ids = (299,300,301,302,307,308,369,370,371,372,373,374,422)
# Catholic
# Catholic
cath_ids = (14,86,92,100)
# Orthodox — use faith-based fallback since taxonomy coverage is sparse
orth_ids = ()
# Other Christian (LDS, JW handled via hierarchy tables; catch-all for remaining)
other_christian_ids = ()

c.execute(f"""SELECT county_fips_5,
    SUM(CASE WHEN taxonomy_id IN ({','.join('?' for _ in cath_ids)}) THEN 1 ELSE 0 END) as cath,
    SUM(CASE WHEN taxonomy_id IN ({','.join('?' for _ in evan_ids)}) THEN 1 ELSE 0 END) as evan,
    SUM(CASE WHEN taxonomy_id IN ({','.join('?' for _ in main_ids)}) THEN 1 ELSE 0 END) as main,
    SUM(CASE WHEN taxonomy_id IN ({','.join('?' for _ in blk_ids)}) THEN 1 ELSE 0 END) as blk_prot,
    SUM(CASE WHEN faith='Islam' THEN 1 ELSE 0 END) as mus,
    SUM(CASE WHEN faith='Judaism' THEN 1 ELSE 0 END) as jew,
    COUNT(*) as total
    FROM churches WHERE country='US' AND county_fips_5 IS NOT NULL AND county_fips_5 != ''
    GROUP BY county_fips_5""",
    cath_ids + evan_ids + main_ids + blk_ids)
grid = {}
for r in c.fetchall():
    fips, cath, evan, main, blk_prot, mus, jew, total = r
    other_christian_total = evan + main + blk_prot
    
    grid[fips] = {'catholic': cath, 'evangelical': evan, 'mainline': main, 
                  'black_prot': blk_prot, 'other_christian': other_christian_total,
                  'muslim': mus, 'jewish': jew, 'total': total}
print(f"  {len(grid):,} counties with GRID facilities")

# ── Add LDS meetinghouses from hierarchy table (they're undercounted in churches.taxonomy) ──
print("Adding LDS meetinghouses from hierarchy...")
c.execute("""SELECT c.county_fips_5, COUNT(*) as lds_count
    FROM lds_hierarchy h 
    JOIN churches c ON h.church_id = c.id
    WHERE h.lds_type = 'meetinghouse' AND c.country = 'US' 
    AND c.county_fips_5 IS NOT NULL AND c.county_fips_5 != ''
    GROUP BY c.county_fips_5""")
lds_added = 0
lds_counties = set()
for fips, lds_cnt in c.fetchall():
    if fips not in grid:
        grid[fips] = {'catholic': 0, 'evangelical': 0, 'mainline': 0, 'black_prot': 0,
                      'other_christian': 0, 'muslim': 0, 'jewish': 0, 'total': 0}
    grid[fips]['other_christian'] += lds_cnt
    grid[fips]['total'] += lds_cnt
    lds_added += lds_cnt
    lds_counties.add(fips)
print(f"  Added {lds_added:,} LDS meetinghouses across {len(lds_counties)} counties")

# ── Add JW Kingdom Halls from hierarchy table ──
print("Adding JW Kingdom Halls from hierarchy...")
c.execute("""SELECT c.county_fips_5, COUNT(*) as jw_count
    FROM jw_hierarchy h 
    JOIN churches c ON h.church_id = c.id
    WHERE h.jw_type = 'kingdom_hall' AND c.country = 'US'
    AND c.county_fips_5 IS NOT NULL AND c.county_fips_5 != ''
    GROUP BY c.county_fips_5""")
jw_added = 0
for fips, jw_cnt in c.fetchall():
    if fips not in grid:
        grid[fips] = {'catholic': 0, 'evangelical': 0, 'mainline': 0, 'black_prot': 0,
                      'other_christian': 0, 'muslim': 0, 'jewish': 0, 'total': 0}
    grid[fips]['other_christian'] += jw_cnt
    grid[fips]['total'] += jw_cnt
    jw_added += jw_cnt
print(f"  Added {jw_added:,} JW Kingdom Halls")

# ── County names ──
c.execute("SELECT county_fips, county_name, population FROM county_fips_lookup")
fips_info = {r[0]: (r[1], r[2] or 0) for r in c.fetchall()}

# ── Merge and insert ──
print("Merging and computing ratios...")
now = datetime.now().isoformat()
all_fips = set(county_adh) | set(grid)
inserted = 0

for fips in all_fips:
    a = county_adh.get(fips, {})
    g = grid.get(fips, {})
    info = fips_info.get(fips, ('Unknown', 0))
    
    cath_adh = a.get('catholic', 0) or 0
    evan_adh = a.get('evangelical', 0) or 0
    main_adh = a.get('mainline', 0) or 0
    blk_adh = a.get('black_prot', 0) or 0
    orth_adh = a.get('orthodox', 0) or 0
    oth_adh = a.get('other_christian', 0) or 0
    mus_adh = a.get('muslim', 0) or 0
    jew_adh = a.get('jewish', 0) or 0
    other_adh = a.get('other', 0) or 0
    
    cath_ch = g.get('catholic', 0) or 0
    evan_ch = g.get('evangelical', 0) or 0
    main_ch = g.get('mainline', 0) or 0
    blk_ch = g.get('black_prot', 0) or 0
    mus_ch = g.get('muslim', 0) or 0
    jew_ch = g.get('jewish', 0) or 0
    total_ch = g.get('total', 0) or 0  # ALL churches (including unclassified umbrella-taxonomy)
    # other_christian = all non-Catholic, non-Muslim, non-Jewish churches
    prot_ch = total_ch - cath_ch - mus_ch - jew_ch
    
    # Distribute Protestant churches across subtypes (already done in count)
    # evan_ch, main_ch, blk_ch already have the real taxonomy counts
    
    total_adh = cath_adh + evan_adh + main_adh + blk_adh + orth_adh + oth_adh + mus_adh + jew_adh + other_adh
    
    cath_ratio = cath_adh / cath_ch if cath_ch else 0
    evan_ratio = evan_adh / evan_ch if evan_ch else 0
    main_ratio = main_adh / main_ch if main_ch else 0
    overall_ratio = total_adh / total_ch if total_ch else 0
    adherence_rate = (total_adh / info[1] * 100) if info[1] else 0
    
    # Saturation: incorporates adherence rate for urban secularism context
    # National baseline: ~84 adherents/facility (ARDA adherents / ALL GRID facilities)
    # Urban counties with low adherence need fewer facilities per adherent
    if total_ch == 0:
        sat = 'no_facilities'
    elif overall_ratio < 25:
        sat = 'oversaturated'          # >40 facilities per 1000 adherents
    elif overall_ratio < 200:
        if adherence_rate > 0 and adherence_rate < 15:
            sat = 'balanced_secular'   # adequate facilities, low religious population (urban)
        else:
            sat = 'balanced'
    elif overall_ratio < 1000:
        if adherence_rate > 0 and adherence_rate < 15:
            sat = 'underserved_secular'  # underserved + low adherence = possible data gap
        else:
            sat = 'underserved'
    else:
        sat = 'severely_underserved'
    
    state = fips[:2] if len(fips) >= 2 else ''
    
    cols = '''county_fips,county_name,state,
        catholic_adherents,evangelical_adherents,mainline_adherents,black_prot_adherents,orthodox_adherents,other_christian_adherents,muslim_adherents,jewish_adherents,other_adherents,total_adherents,
        catholic_churches,evangelical_churches,mainline_churches,black_prot_churches,orthodox_churches,other_christian_churches,muslim_mosques,jewish_synagogues,other_facilities,total_facilities,
        total_population,adherence_rate,catholic_ratio,evangelical_ratio,mainline_ratio,overall_ratio,saturation,source,updated'''
    vals = (fips, info[0], state,
         cath_adh, evan_adh, main_adh, blk_adh, orth_adh, oth_adh, mus_adh, jew_adh, other_adh, total_adh,
         cath_ch, evan_ch, main_ch, blk_ch, 0, prot_ch, mus_ch, jew_ch, 0, total_ch,
         info[1], adherence_rate, cath_ratio, evan_ratio, main_ratio, overall_ratio,
         sat, 'ARDA 2020 + GRID', now)
    c.execute(f"INSERT INTO adherent_ratio_us ({cols}) VALUES ({','.join('?'*len(vals))})", vals)
    inserted += 1

db.commit()
print(f"  Inserted {inserted:,} county ratios")

# ── Summary ──
print("\n" + "=" * 60)
print("US RELIGIOUS INFRASTRUCTURE RATIO MODEL")
print("=" * 60)

c.execute("""SELECT COUNT(*), SUM(total_adherents), SUM(total_facilities),
    CAST(SUM(total_adherents) AS REAL)/NULLIF(SUM(total_facilities),0)
    FROM adherent_ratio_us""")
r = c.fetchone()
print(f"Counties: {r[0]:,}  |  Total adherents: {r[1]:,}  |  Total facilities: {r[2]:,}")
print(f"National ratio: {r[3]:,.0f} adherents per facility")

c.execute("""SELECT AVG(adherence_rate), MIN(adherence_rate), MAX(adherence_rate)
    FROM adherent_ratio_us WHERE total_population > 0 AND total_adherents > 0""")
rr = c.fetchone()
print(f"Adherence rate: avg={rr[0]:.1f}%  min={rr[1]:.1f}%  max={rr[2]:.1f}%")

print("\n--- Saturation Distribution ---")
for r in c.execute("""SELECT saturation, COUNT(*), SUM(total_facilities) 
    FROM adherent_ratio_us GROUP BY saturation ORDER BY COUNT(*) DESC"""):
    print(f"  {r[0]:25s}: {r[1]:>5,} counties  ({r[2]:>8,} facilities)")

print("\n--- Urban Secularism: balanced vs balanced_secular ---")
for r in c.execute("""SELECT saturation, COUNT(*), ROUND(AVG(adherence_rate),1), ROUND(AVG(overall_ratio),0)
    FROM adherent_ratio_us WHERE saturation IN ('balanced','balanced_secular','underserved','underserved_secular')
    GROUP BY saturation ORDER BY saturation"""):
    print(f"  {r[0]:25s}: {r[1]:>5,} counties  avg_adh_rate={r[2]}%  avg_ratio={r[3]:,.0f}/facility")

print("\n--- Top 10 Most Underserved ---")
for r in c.execute("""SELECT county_name, state, total_adherents, total_facilities, overall_ratio
    FROM adherent_ratio_us WHERE total_facilities > 0 ORDER BY overall_ratio DESC LIMIT 10"""):
    print(f"  {r[0]}, {r[1]}: {r[2]:,} adh / {r[3]} facilities = {r[4]:,.0f}/facility")

print("\n--- Top 10 Most Oversaturated ---")
for r in c.execute("""SELECT county_name, state, total_adherents, total_facilities, overall_ratio
    FROM adherent_ratio_us WHERE total_facilities > 0 ORDER BY overall_ratio ASC LIMIT 10"""):
    print(f"  {r[0]}, {r[1]}: {r[2]:,} adh / {r[3]} facilities = {r[4]:,.0f}/facility")

print("\n--- Urban vs Rural Adherence ---")
for r in c.execute("""SELECT 
    CASE 
        WHEN total_population > 500000 THEN 'urban'
        WHEN total_population > 50000 THEN 'suburban'
        ELSE 'rural'
    END as category,
    COUNT(*), ROUND(AVG(adherence_rate),1), ROUND(AVG(overall_ratio),0)
    FROM adherent_ratio_us WHERE total_population > 0
    GROUP BY category ORDER BY AVG(total_population)"""):
    print(f"  {r[0]:10s}: {r[1]:>5,} counties  avg_adh_rate={r[2]}%  avg_ratio={r[3]:,.0f}/facility")

print("\nDone.")

# Provenance
c.execute("""INSERT INTO provenance_log (source, script_name, started_at, completed_at,
    churches_updated, fields_populated, records_attempted, status)
    VALUES ('adherent_ratio_model', 'build_adherent_ratio.py', ?, ?, ?, 'adherent_ratio', ?, 'completed')""",
    (now, datetime.now().isoformat(), inserted, inserted))
db.commit()
db.close()
print("\nDone.")
