"""
Import PH 2022 presidential election results from GMA Eleksyon data.
Source: AstroMC98/GMA-Eleksyon-2022-Data (GitHub)
Data: Province-level results with vote counts for all presidential candidates.
Matches to church_census_PH dist_name (86 ADM2 districts).
"""
import sqlite3, requests, json, re
from datetime import datetime

db = sqlite3.connect('churches.db')

# 1. Fetch data
print("Fetching GMA election data...")
url = 'https://raw.githubusercontent.com/AstroMC98/GMA-Eleksyon-2022-Data/main/gma_election_data.json'
data = requests.get(url, timeout=30).json()

# 2. Extract presidential results per province (latest snapshot)
print("Extracting presidential results...")
results = {}  # province_name -> {candidate: votes}

for region_name, region in data.items():
    if region_name == 'OAV':
        continue
    
    provincial_data = region.get('PROVINCIAL_DATA', {})
    prov_names = list(provincial_data.keys())
    
    for province_name in prov_names:
        province = provincial_data[province_name]
        # Get latest snapshot (highest key number)
        snapshots = {int(k): v for k, v in province.items() if k.isdigit()}
        if not snapshots:
            continue
        
        latest_key = max(snapshots.keys())
        latest = snapshots[latest_key]
        
        # Find PRESIDENT PHILIPPINES contest
        president_contest = None
        for contest in latest.get('result', []):
            if 'PRESIDENT PHILIPPINES' in contest.get('contest', ''):
                president_contest = contest
                break
        
        if not president_contest:
            continue
        
        # Extract candidate votes
        province_votes = {}
        for candidate in president_contest.get('candidates', []):
            name = candidate.get('name', '')  # field is 'name' not 'candidate_name'
            votes_str = str(candidate.get('vote_count', '0'))  # field is 'vote_count'
            votes = int(votes_str.replace(',', ''))
            province_votes[name] = votes
        
        if province_votes:
            results[province_name] = {
                'votes': province_votes,
                'total_processed': latest.get('total_voters_processed', ''),
                'er_processed': latest.get('election_returns_processed', ''),
            }

print(f"  Got results for {len(results)} provinces")
print(f"  Province names: {sorted(results.keys())}")

# 3. Get our PH district names for matching
ph_districts = db.execute("SELECT DISTINCT dist_name FROM church_census_PH").fetchall()
ph_district_names = {r[0].upper().strip(): r[0] for r in ph_districts}
print(f"  GRID has {len(ph_district_names)} PH districts")

# 4. Match province names to district names
matched = 0
unmatched = []

for prov_name, prov_data in results.items():
    prov_upper = prov_name.upper().strip()
    
    # Direct match
    if prov_upper in ph_district_names:
        matched += 1
        continue
    
    # Try fuzzy: remove "PROVINCE OF" prefix, etc.
    cleaned = prov_upper.replace('PROVINCE OF ', '').replace('CITY OF ', '')
    if cleaned in ph_district_names:
        matched += 1
        continue
    
    # Check if any district contains this province name
    found = False
    for dist_upper, dist_orig in ph_district_names.items():
        if prov_upper in dist_upper or dist_upper in prov_upper:
            found = True
            matched += 1
            break
    
    if not found:
        unmatched.append(prov_name)

print(f"  Matched: {matched}, Unmatched: {len(unmatched)}")
if unmatched:
    print(f"  Unmatched provinces: {unmatched}")

# 5. Print summary of matched results
print(f"\n=== PH 2022 PRESIDENTIAL RESULTS (sample) ===")
for prov_name in sorted(list(results.keys()))[:5]:
    prov = results[prov_name]
    total = sum(prov['votes'].values())
    print(f"\n  {prov_name} ({prov['total_processed']})")
    for cand, votes in sorted(prov['votes'].items(), key=lambda x: -x[1])[:3]:
        pct = votes / total * 100 if total else 0
        print(f"    {cand[:30]:30s}: {votes:>12,} ({pct:.1f}%)")

# 6. Create election table
print(f"\n=== CREATING church_election_PH ===")

# Get all candidate names across all provinces
all_candidates = set()
for prov in results.values():
    all_candidates.update(prov['votes'].keys())
all_candidates = sorted(all_candidates)
print(f"  Candidates: {all_candidates}")

# Build election data per district
db.execute("DROP TABLE IF EXISTS church_election_PH")
db.execute("""
    CREATE TABLE church_election_PH (
        church_rowid INTEGER PRIMARY KEY,
        dist_code TEXT,
        dist_name TEXT,
        total_votes INTEGER,
        winner TEXT,
        winner_votes INTEGER,
        winner_pct REAL,
        candidate_votes TEXT,
        source TEXT,
        source_date TEXT
    )
""")

now = datetime.now().isoformat()
imported = 0

# Get church -> district mapping
church_districts = db.execute("""
    SELECT church_rowid, dist_code, dist_name FROM church_census_PH
""").fetchall()

# Map district names to province results
dist_to_result = {}
for prov_name, prov_data in results.items():
    prov_upper = prov_name.upper().strip()
    for dist_upper, dist_orig in ph_district_names.items():
        if prov_upper == dist_upper or prov_upper in dist_upper or dist_upper in prov_upper:
            dist_to_result[dist_orig] = prov_data
            break

print(f"  Districts with election results: {len(dist_to_result)}")

for church_rowid, dist_code, dist_name in church_districts:
    prov_data = dist_to_result.get(dist_name)
    if not prov_data:
        continue
    
    votes = prov_data['votes']
    total = sum(votes.values())
    if total == 0:
        continue
    
    # Find winner
    winner = max(votes, key=votes.get)
    winner_votes = votes[winner]
    winner_pct = round(winner_votes / total * 100, 1)
    
    # Store all candidate votes as JSON
    candidate_json = json.dumps(votes)
    
    db.execute("""
        INSERT OR REPLACE INTO church_election_PH 
        (church_rowid, dist_code, dist_name, total_votes, winner, winner_votes, winner_pct, candidate_votes, source, source_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'gma-eleksyon-2022', ?)
    """, (church_rowid, dist_code, dist_name, total, winner, winner_votes, winner_pct, candidate_json, now))
    imported += 1

db.commit()

# Verify
total = db.execute("SELECT COUNT(*) FROM church_election_PH").fetchone()[0]
districts_with = db.execute("SELECT COUNT(DISTINCT dist_name) FROM church_election_PH").fetchone()[0]
print(f"\n  Imported: {imported:,} church-election rows")
print(f"  Districts covered: {districts_with}/{len(ph_district_names)}")

# Sample
print(f"\n=== SAMPLE: PH election data ===")
for r in db.execute("SELECT DISTINCT dist_name, winner, winner_pct, total_votes FROM church_election_PH ORDER BY total_votes DESC LIMIT 5"):
    print(f"  {r[0][:30]:30s} Winner: {r[1][:20]:20s} {r[2]:.1f}%  ({r[3]:,} votes)")

db.close()
print("\nDone!")
