"""Explore Nigerian election + church data for Substack post."""
import sqlite3
db = sqlite3.connect('e:/grid/churches.db')
db.row_factory = sqlite3.Row

print('=== election_results_NG ===')
for r in db.execute('PRAGMA table_info(election_results_NG)'): print(f'  {r[1]} {r[2]}')
print()
for r in db.execute('SELECT * FROM election_results_NG LIMIT 5'): print(dict(r))
print(f'Rows: {db.execute("SELECT COUNT(*) FROM election_results_NG").fetchone()[0]}')

print()
print('=== election_zone_NG ===')
for r in db.execute('PRAGMA table_info(election_zone_NG)'): print(f'  {r[1]} {r[2]}')
print()
for r in db.execute('SELECT * FROM election_zone_NG'): print(dict(r))

print()
print('=== church_election_NG ===')
for r in db.execute('PRAGMA table_info(church_election_NG)'): print(f'  {r[1]} {r[2]}')
print(f'Rows: {db.execute("SELECT COUNT(*) FROM church_election_NG").fetchone()[0]}')
for r in db.execute('SELECT * FROM church_election_NG LIMIT 3'): print(dict(r))

print()
print('=== lga_census_NG ===')
for r in db.execute('PRAGMA table_info(lga_census_NG)'): print(f'  {r[1]} {r[2]}')
print(f'Rows: {db.execute("SELECT COUNT(*) FROM lga_census_NG").fetchone()[0]}')
for r in db.execute('SELECT * FROM lga_census_NG LIMIT 3'): print(dict(r))

print()
print('=== NG churches ===')
total = db.execute("SELECT COUNT(*) FROM churches WHERE country='NG'").fetchone()[0]
with_lga = db.execute("SELECT COUNT(*) FROM churches WHERE country='NG' AND county IS NOT NULL").fetchone()[0]
print(f'Total NG: {total:,}')
print(f'With LGA: {with_lga:,}')
print()
for r in db.execute("SELECT faith, COUNT(*) n FROM churches WHERE country='NG' GROUP BY faith ORDER BY n DESC"):
    print(f'  {r[0]}: {r[1]:,}')

# Deep dive into election results
print()
print('=== Full election_results_NG ===')
for r in db.execute('SELECT * FROM election_results_NG ORDER BY state'):
    print(dict(r))

# Check state names in churches
print()
print('=== NG church states ===')
for r in db.execute("SELECT state, COUNT(*) n FROM churches WHERE country='NG' GROUP BY state ORDER BY n DESC LIMIT 20"):
    print(f'  {r[0]}: {r[1]:,}')

# Church-election join
print()
print('=== Church-election join check ===')
for r in db.execute('''
    SELECT e.state, e.tinubu_pct, e.obi_pct, e.atiku_pct, e.turnout,
           COUNT(ce.church_id) as churches
    FROM election_results_NG e
    LEFT JOIN church_election_NG ce ON e.id = ce.election_id
    GROUP BY e.id
    ORDER BY e.state
'''):
    print(f'  {r["state"]}: Tinubu {r["tinubu_pct"]:.1f}% Obi {r["obi_pct"]:.1f}% Atiku {r["atiku_pct"]:.1f}% | Turnout {r["turnout"]}% | {r["churches"]:,} churches')

db.close()
