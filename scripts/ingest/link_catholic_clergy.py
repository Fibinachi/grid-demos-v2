"""
Link catholic_clergy to churches using 2021 directory as temporal bridge.

Temporal constraint: parish founded in 1958 can't have clergy in 1860.
Cascade: parishes don't move — link once, propagate to all years.

Usage:
  python scripts/ingest/link_catholic_clergy.py
  python scripts/ingest/link_catholic_clergy.py --stats
"""
import re, sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from gw_db import connect


def normalize_name(name):
    if not name: return ''
    n = name.lower().strip()
    n = re.sub(r'\bst\.?\s+', 'saint ', n)
    n = re.sub(r'\bss\.?\s+', 'saints ', n)
    n = re.sub(r'\bmt\.?\s+', 'mount ', n)
    n = re.sub(r'[^\w\s]', '', n)
    n = re.sub(r'\bsaint\s+(\w+)s\b', r'saint \1', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n


def norm_dio(name):
    if not name: return ''
    n = name.strip()
    n = re.sub(r'^(?:Archdiocese|Diocese)\s+of\s+', '', n, flags=re.IGNORECASE)
    n = re.sub(r'[\.\s,;:].*$', '', n)
    n = re.sub(r'\s+', ' ', n).strip().lower()
    n = n.replace('st.', 'saint')
    fixes = {'yincennes':'vincennes','nesqualy':'seattle','oregon city':'portland',
             'fbancisco':'francisco','new-york':'new york','new-orleans':'new orleans',
             'saut sainte marie':'marquette','pittsburgh':'pittsburg','makquette':'marquette'}
    n = re.sub(r'[^a-z\s]', '', n); n = re.sub(r'\s+', ' ', n).strip()
    for bad, good in fixes.items():
        if re.sub(r'[^a-z\s]', '', bad) in n: n = good; break
    return n


def build_2021_index(db):
    """{norm_diocese: {norm_name: [parish_info]}}"""
    print("Building 2021 parish index...")
    idx = defaultdict(lambda: defaultdict(list))
    for r in db.execute("SELECT diocese, parish_name, city, founded FROM catholic_parishes_2021").fetchall():
        d, n = norm_dio(r[0]), normalize_name(r[1])
        if d and n:
            idx[d][n].append({'diocese': r[0], 'parish': r[1], 'city': r[2] or '', 'founded': r[3]})
    total = sum(len(v) for d in idx.values() for v in d.values())
    print(f"  {total:,} parishes across {len(idx)} dioceses")
    return idx


# Diocese→state mapping (covers all US dioceses)
DIO_STATE = {
    'albany': 'NY', 'baltimore': 'MD', 'boston': 'MA', 'brooklyn': 'NY',
    'buffalo': 'NY', 'burlington': 'VT', 'charleston': 'SC', 'chicago': 'IL',
    'cincinnati': 'OH', 'cleveland': 'OH', 'covington': 'KY', 'detroit': 'MI',
    'dubuque': 'IA', 'erie': 'PA', 'fort wayne': 'IN', 'galveston': 'TX',
    'hartford': 'CT', 'louisville': 'KY', 'milwaukee': 'WI', 'mobile': 'AL',
    'nashville': 'TN', 'natchez': 'MS', 'new orleans': 'LA', 'new york': 'NY',
    'newark': 'NJ', 'philadelphia': 'PA', 'pittsburgh': 'PA', 'portland': 'OR',
    'richmond': 'VA', 'savannah': 'GA', 'st louis': 'MO', 'st paul': 'MN',
    'santa fe': 'NM', 'san francisco': 'CA', 'wheeling': 'WV',
    'alton': 'IL', 'quincy': 'IL', 'nesqualy': 'WA', 'seattle': 'WA',
    'little rock': 'AR', 'natchitoches': 'LA', 'monterey': 'CA',
    'los angeles': 'CA', 'san antonio': 'TX', 'dallas': 'TX', 'denver': 'CO',
    'omaha': 'NE', 'wichita': 'KS', 'sioux falls': 'SD', 'fargo': 'ND',
    'duluth': 'MN', 'winona': 'MN', 'sioux city': 'IA', 'lincoln': 'NE',
    'cheyenne': 'WY', 'helena': 'MT', 'boise': 'ID', 'tucson': 'AZ',
    'phoenix': 'AZ', 'las vegas': 'NV', 'reno': 'NV', 'honolulu': 'HI',
    'anchorage': 'AK', 'juneau': 'AK', 'fairbanks': 'AK',
    'sacramento': 'CA', 'oakland': 'CA', 'san jose': 'CA', 'fresno': 'CA',
    'san diego': 'CA', 'orange': 'CA', 'san bernardino': 'CA', 'stockton': 'CA',
    'santa rosa': 'CA', 'colorado springs': 'CO', 'pueblo': 'CO',
    'bridgeport': 'CT', 'norwich': 'CT', 'stamford': 'CT',
    'wilmington': 'DE', 'miami': 'FL', 'orlando': 'FL', 'palm beach': 'FL',
    'st petersburg': 'FL', 'st augustine': 'FL', 'pensacola': 'FL', 'venice': 'FL',
    'atlanta': 'GA', 'indianapolis': 'IN', 'evansville': 'IN', 'gary': 'IN',
    'lafayette': 'IN', 'davenport': 'IA', 'des moines': 'IA',
    'kansas city': 'KS', 'dodge city': 'KS',
    'leavenworth': 'KS', 'owensboro': 'KY', 'lexington': 'KY',
    'alexandria': 'LA', 'baton rouge': 'LA', 'houma': 'LA', 'lake charles': 'LA',
    'shreveport': 'LA', 'portland me': 'ME',
    'springfield': 'MA', 'worcester': 'MA', 'fall river': 'MA',
    'gaylord': 'MI', 'grand rapids': 'MI', 'kalamazoo': 'MI', 'lansing': 'MI',
    'marquette': 'MI', 'saginaw': 'MI',
    'crookston': 'MN', 'st cloud': 'MN',
    'biloxi': 'MS', 'jackson': 'MS',
    'jefferson city': 'MO', 'kansas city st joseph': 'MO',
    'great falls': 'MT', 'lincoln ne': 'NE', 'manchester': 'NH',
    'camden': 'NJ', 'metuchen': 'NJ', 'paterson': 'NJ', 'trenton': 'NJ',
    'gallup': 'NM', 'las cruces': 'NM',
    'ogdensburg': 'NY', 'rochester': 'NY', 'rockville centre': 'NY',
    'syracuse': 'NY', 'charlotte': 'NC', 'raleigh': 'NC',
    'bismarck': 'ND', 'toledo': 'OH', 'columbus': 'OH', 'steubenville': 'OH',
    'youngstown': 'OH', 'oklahoma city': 'OK', 'tulsa': 'OK',
    'allentown': 'PA', 'erie pa': 'PA', 'greensburg': 'PA', 'harrisburg': 'PA',
    'scranton': 'PA', 'providence': 'RI',
    'rapid city': 'SD', 'memphis': 'TN', 'knoxville': 'TN',
    'austin': 'TX', 'beaumont': 'TX', 'brownsville': 'TX', 'corpus christi': 'TX',
    'el paso': 'TX', 'fort worth': 'TX', 'lubbock': 'TX', 'san angelo': 'TX',
    'tyler': 'TX', 'victoria': 'TX',
    'salt lake city': 'UT', 'arlington': 'VA',
    'spokane': 'WA', 'yakima': 'WA', 'madison': 'WI', 'superior': 'WI',
    'green bay': 'WI', 'la crosse': 'WI',
    'pittsburg': 'PA', 'galyeston': 'TX', 'saint paul': 'MN', 'saint louis': 'MO',
    'vincennes': 'IN', 'alton il': 'IL',
}


def find_church(db, parish_name, diocese_2021, city_2021):
    """Find church_id using hardcoded diocese→state + name match."""
    dio_clean = diocese_2021.lower().replace('archdiocese of ', '').replace('diocese of ', '').strip()
    state = DIO_STATE.get(dio_clean)
    if not state:
        return None
    norm = normalize_name(parish_name)
    city_lower = (city_2021 or '').lower().strip()
    if city_lower:
        for r in db.execute("""SELECT rowid FROM churches WHERE state=? AND LOWER(city)=?
            AND LOWER(COALESCE(normalized_name, name))=?
            AND taxonomy_id IN (14,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100,101)
            LIMIT 1""", (state, city_lower, norm)).fetchall():
            return r[0]
    for r in db.execute("""SELECT rowid FROM churches WHERE state=?
        AND LOWER(COALESCE(normalized_name, name))=?
        AND taxonomy_id IN (14,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100,101)
        LIMIT 1""", (state, norm)).fetchall():
        return r[0]
    return None


def link_all(db):
    idx_2021 = build_2021_index(db)
    rows = db.execute("""SELECT id, year, diocese, city, parish FROM catholic_clergy
        WHERE church_id IS NULL AND year BETWEEN 1860 AND 1893
        ORDER BY year, diocese""").fetchall()

    print(f"\nLinking {len(rows):,} records with temporal constraint...")
    matched = 0; batch = []

    for i, row in enumerate(rows):
        cid, year, clergy_dio, city, parish = row
        dio_key = norm_dio(clergy_dio)
        norm_p = normalize_name(parish or '')
        if not dio_key or not norm_p:
            continue

        dio_2021 = idx_2021.get(dio_key)
        if not dio_2021:
            for k in idx_2021:
                if dio_key in k or k in dio_key:
                    dio_2021 = idx_2021[k]; break
        if not dio_2021 or norm_p not in dio_2021:
            continue

        candidates = [e for e in dio_2021[norm_p] if e['founded'] <= year]
        if not candidates:
            continue

        best = candidates[0]
        city_lower = (city or '').lower().strip()
        for e in candidates:
            if city_lower and e['city'].lower() == city_lower:
                best = e; break

        church_id = find_church(db, best['parish'], best['diocese'], best['city'])
        if church_id:
            batch.append((church_id, cid))
            matched += 1

        if len(batch) >= 500:
            db.executemany("UPDATE catholic_clergy SET church_id=? WHERE id=?", batch)
            db.commit(); batch = []

        if (i + 1) % 3000 == 0:
            print(f"  {i+1}/{len(rows)}: {matched} matched...")

    if batch:
        db.executemany("UPDATE catholic_clergy SET church_id=? WHERE id=?", batch)
        db.commit()

    print(f"\n2021 bridge: {matched:,} matched ({matched/len(rows)*100:.0f}%)")

    # Cascade
    print("Cascading parish links...")
    db.execute("""UPDATE catholic_clergy SET church_id = (
        SELECT c2.church_id FROM catholic_clergy c2
        WHERE c2.church_id IS NOT NULL AND c2.diocese = catholic_clergy.diocese
        AND c2.parish = catholic_clergy.parish LIMIT 1)
        WHERE church_id IS NULL AND EXISTS (
        SELECT 1 FROM catholic_clergy c2 WHERE c2.church_id IS NOT NULL
        AND c2.diocese = catholic_clergy.diocese AND c2.parish = catholic_clergy.parish)""")
    db.commit()
    t = db.execute("SELECT COUNT(*) FROM catholic_clergy WHERE church_id IS NOT NULL").fetchone()[0]
    print(f"After cascade: {t:,} linked")


def show_stats(db):
    rows = db.execute("""SELECT year, COUNT(*) t, SUM(CASE WHEN church_id IS NOT NULL THEN 1 ELSE 0 END) m,
        COUNT(DISTINCT CASE WHEN church_id IS NOT NULL THEN church_id END) u
        FROM catholic_clergy GROUP BY year ORDER BY year""").fetchall()
    print(f"{'Year':<6} {'Total':>7} {'Linked':>7} {'Rate':>7} {'Churches':>9}")
    print("-" * 42)
    for r in rows:
        rate = r[2]/r[1]*100 if r[1] else 0
        print(f"{r[0]:<6} {r[1]:>7,} {r[2]:>7,} {rate:>6.0f}% {r[3]:>9,}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--stats', action='store_true')
    args = ap.parse_args()
    db = connect()
    if args.stats:
        show_stats(db)
    else:
        link_all(db)
        show_stats(db)
    db.close()


if __name__ == '__main__':
    main()
