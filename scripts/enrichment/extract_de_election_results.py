"""Extract 2025 Bundestag election results from ArcGIS GeoJSON → election_de_bt_results."""
import json, sqlite3, re
from pathlib import Path

DB = Path(r'E:\grid\churches.db')

# Load GeoJSON
with open(r'E:\grid\data\election_boundaries\DE_electoral.geojson') as f:
    data = json.load(f)

# Party mapping: ArcGIS field prefix → party name
# _1_ = Erststimme (candidate), _2_ = Zweitstimme (party list)
# _vorl = 2025 (vorläufig), _vorp = 2021 (Vorperiode)
PARTIES = {
    'spd': 'SPD',
    'cdu': 'CDU',
    'csu': 'CSU',
    'grün': 'Grüne',
    'fdp': 'FDP',
    'afd': 'AfD',
    'link': 'Die Linke',
    'bsw': 'BSW',
    'fw': 'Freie Wähler',
    'volt': 'Volt',
    'süd': 'SSW',
    'tier': 'Tierschutz',
    'pirat': 'Piraten',
    'ödp': 'ÖDP',
    'bd': 'Bündnis Deutschland',
    'werte': 'WerteUnion',
}

db = sqlite3.connect(str(DB))
c = db.cursor()

# Create results table
c.execute('DROP TABLE IF EXISTS election_de_bt_results')
cols = [
    'wahlkreis_nr INTEGER PRIMARY KEY',
    'wahlkreis_name TEXT',
    'land_nr TEXT',
    'land_name TEXT',
    'gewaehlt TEXT',  # Elected candidate
    'wahlberechtigte_2025 INTEGER',
    'wahlberechtigte_2021 INTEGER',
    'waehlende_erst_2025 INTEGER',
    'waehlende_erst_2021 INTEGER',
    'waehlende_zweit_2025 INTEGER',
    'waehlende_zweit_2021 INTEGER',
    'ungueltig_erst_2025 INTEGER',
    'ungueltig_erst_2021 INTEGER',
    'ungueltig_zweit_2025 INTEGER',
    'ungueltig_zweit_2021 INTEGER',
    'gueltig_erst_2025 INTEGER',
    'gueltig_erst_2021 INTEGER',
    'gueltig_zweit_2025 INTEGER',
    'gueltig_zweit_2021 INTEGER',
]

# Add party vote columns (Erststimme + Zweitstimme, 2025 + 2021)
for prefix, name in PARTIES.items():
    cols.append(f'{prefix}_erst_2025 INTEGER')
    cols.append(f'{prefix}_erst_2021 INTEGER')
    cols.append(f'{prefix}_zweit_2025 INTEGER')
    cols.append(f'{prefix}_zweit_2021 INTEGER')

cols.append('source TEXT')
cols.append('source_date TEXT')

c.execute(f'CREATE TABLE election_de_bt_results ({", ".join(cols)})')

# Parse and insert
inserted = 0
for feature in data['features']:
    p = feature['properties']
    
    row = {
        'wahlkreis_nr': int(p['WKR_NR']),
        'wahlkreis_name': p['WKR_NAME'],
        'land_nr': p['LAND_NR'],
        'land_name': p['LAND_NAME'],
        'gewaehlt': p.get('Gewählt', ''),
        'wahlberechtigte_2025': p.get('Wahlberechtigte_Erststimmen_Vor'),
        'wahlberechtigte_2021': p.get('Wahlb_Erststimmen_Vorperiode'),
        'waehlende_erst_2025': p.get('Wählende_Erststimmen_Vorläufig'),
        'waehlende_erst_2021': p.get('Wählende_Erststimmen_Vorperiode'),
        'waehlende_zweit_2025': p.get('Wählende_Zweitstimmen_Vorläufig'),
        'waehlende_zweit_2021': p.get('Wählende_Zweitstimmen_Vorperiod'),
        'ungueltig_erst_2025': p.get('Ungültige_Stimmen_1_vorl'),
        'ungueltig_erst_2021': p.get('ung_1_vorperiode'),
        'ungueltig_zweit_2025': p.get('ung_2_vorl'),
        'ungueltig_zweit_2021': p.get('ung_2_vorp'),
        'gueltig_erst_2025': p.get('Gültige_1_vorl'),
        'gueltig_erst_2021': p.get('gültige_1_vorp'),
        'gueltig_zweit_2025': p.get('gültige_2_vorl'),
        'gueltig_zweit_2021': p.get('gültige_2_vorp'),
    }
    
    # Party votes
    for prefix, name in PARTIES.items():
        row[f'{prefix}_erst_2025'] = p.get(f'{prefix}_1_vorl')
        row[f'{prefix}_erst_2021'] = p.get(f'{prefix}_1_vorp')
        row[f'{prefix}_zweit_2025'] = p.get(f'{prefix}_2_vorl')
        row[f'{prefix}_zweit_2021'] = p.get(f'{prefix}_2_vorp')
    
    row['source'] = 'Bundeswahlleiterin ArcGIS FeatureServer'
    row['source_date'] = '2025-02-23'
    
    # Build INSERT
    col_names = [c.split()[0] for c in cols if 'PRIMARY' not in c]
    col_names = [c for c in col_names if c not in ('source','source_date')]
    col_names += ['source', 'source_date']
    
    values = [row.get(c) for c in col_names]
    placeholders = ','.join('?' * len(values))
    col_str = ','.join(col_names)
    
    c.execute(f'INSERT INTO election_de_bt_results ({col_str}) VALUES ({placeholders})', values)
    inserted += 1

db.commit()

# Register in catalog
c.execute('''INSERT OR REPLACE INTO church_census_catalog 
    (country, table_name, category, geo_unit, description, row_count, source_date)
    VALUES (?,?,?,?,?,?,date('now'))''',
    ('DE', 'election_de_bt_results', 'election', 'wahlkreis',
     'Bundestag 2025 election results per wahlkreis (299 constituencies) — Erststimme + Zweitstimme for all parties',
     inserted))

# Verify
c.execute('SELECT COUNT(*) FROM election_de_bt_results')
print(f'Inserted {c.fetchone()[0]} wahlkreise with results')

# Sample
c.execute('SELECT wahlkreis_name, spd_zweit_2025, cdu_zweit_2025, grün_zweit_2025, afd_zweit_2025, bsw_zweit_2025, link_zweit_2025 FROM election_de_bt_results LIMIT 5')
print('\nSample Zweitstimme results:')
for r in c.fetchall():
    print(f'  {r[0]:30s} SPD={r[1]:>6,} CDU={r[2]:>6,} Grüne={r[3]:>6,} AfD={r[4]:>6,} BSW={r[5]:>6,} Linke={r[6]:>6,}')

# Now create the join view: church → wahlkreis → results
c.execute('''
    SELECT COUNT(*) FROM church_election_DE ce 
    JOIN election_de_bt_results er ON ce.dist_code = CAST(er.wahlkreis_nr AS TEXT)
''')
joined = c.fetchone()[0]
print(f'\n{joined:,} churches can join to election results via WKR_NR')

db.close()
print('\nDONE — election_de_bt_results created')
