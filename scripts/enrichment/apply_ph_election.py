"""
Apply existing PH election data: join churches → census districts → election results.
Generate PH election + religious landscape summary.
"""
import sqlite3, json

db = sqlite3.connect('churches.db')

print("=== PH ELECTION DATA — APPLYING WHAT WE HAVE ===\n")

# 1. How many churches have election data?
total = db.execute("SELECT COUNT(*) FROM church_election_PH").fetchone()[0]
districts = db.execute("SELECT COUNT(DISTINCT dist_name) FROM church_election_PH").fetchone()[0]
print(f"Churches with election data: {total:,} across {districts} provinces")

# 2. Election results by province
print(f"\n=== PROVINCIAL RESULTS ===")
print(f"{'Province':25s} {'Winner':25s} {'Win%':>6s} {'Total Votes':>12s} {'Churches':>9s}")
print("-" * 85)

for r in db.execute("""
    SELECT DISTINCT e.dist_name, e.winner, e.winner_pct, e.total_votes,
           COUNT(*) as church_count
    FROM church_election_PH e
    GROUP BY e.dist_name
    ORDER BY e.total_votes DESC
""").fetchall():
    name = r[0][:24]
    winner = r[1][:24]
    print(f"{name:25s} {winner:25s} {r[2]:5.1f}% {r[3]:>12,} {r[4]:>9,}")

# 3. Faith breakdown by province winner
print(f"\n=== FAITH BREAKDOWN BY WINNER ===")
for r in db.execute("""
    SELECT e.winner, c.faith, COUNT(*) as cnt
    FROM church_election_PH e
    JOIN church_census_PH cp ON e.church_rowid = cp.church_rowid
    JOIN churches c ON c.rowid = cp.church_rowid
    GROUP BY e.winner, c.faith
    ORDER BY e.winner, cnt DESC
""").fetchall():
    print(f"  {r[0][:25]:25s} {r[1]:15s}: {r[2]:,}")

# 4. Top churches in swing districts (close races)
print(f"\n=== SWING DISTRICTS (closest races) ===")
for r in db.execute("""
    SELECT DISTINCT e.dist_name, e.winner, e.winner_pct, e.total_votes,
           (SELECT COUNT(*) FROM church_election_PH WHERE dist_name = e.dist_name) as churches
    FROM church_election_PH e
    WHERE e.winner_pct < 55
    ORDER BY e.winner_pct
""").fetchall():
    print(f"  {r[0][:25]:25s} {r[1][:25]:25s} {r[2]:.1f}%  ({r[4]:,} churches)")

# 5. Candidate vote breakdown per province (JSON parsing)
print(f"\n=== DETAILED: Negros Occidental (closest race) ===")
row = db.execute("""
    SELECT candidate_votes, winner, winner_pct 
    FROM church_election_PH WHERE dist_name = 'Negros Occidental' LIMIT 1
""").fetchone()
if row:
    votes = json.loads(row[0])
    total = sum(votes.values())
    print(f"  Winner: {row[1]} ({row[2]:.1f}%)")
    for cand, v in sorted(votes.items(), key=lambda x: -x[1]):
        print(f"    {cand[:40]:40s}: {v:>10,} ({v/total*100:.1f}%)")

# 6. Generate map data JSON for Plotly
print(f"\n=== GENERATING PH ELECTION MAP DATA ===")
map_rows = db.execute("""
    SELECT c.id, c.name, c.latitude, c.longitude, c.faith,
           e.dist_name, e.winner, e.winner_pct, e.total_votes, e.candidate_votes
    FROM church_election_PH e
    JOIN church_census_PH cp ON e.church_rowid = cp.church_rowid
    JOIN churches c ON c.rowid = cp.church_rowid
    WHERE c.latitude IS NOT NULL
""").fetchall()

output = []
for r in map_rows:
    output.append({
        'id': r[0], 'name': r[1], 'lat': r[2], 'lon': r[3], 'faith': r[4],
        'province': r[5], 'winner': r[6], 'winner_pct': r[7],
        'total_votes': r[8]
    })

with open('outputs/ph_election_map.json', 'w') as f:
    json.dump(output, f)

print(f"  Saved {len(output):,} churches to outputs/ph_election_map.json")

# 7. Faith vs winner correlation
print(f"\n=== FAITH vs WINNER CORRELATION ===")
for r in db.execute("""
    SELECT e.winner, c.faith, COUNT(*) as cnt
    FROM church_election_PH e
    JOIN church_census_PH cp ON e.church_rowid = cp.church_rowid
    JOIN churches c ON c.rowid = cp.church_rowid
    GROUP BY e.winner, c.faith
    HAVING cnt > 10
    ORDER BY e.winner, cnt DESC
""").fetchall():
    pct = r[2] / total * 100
    print(f"  {r[0][:25]:25s} {r[1]:15s}: {r[2]:>5,} ({pct:.1f}%)")

db.close()
print("\nDone!")
