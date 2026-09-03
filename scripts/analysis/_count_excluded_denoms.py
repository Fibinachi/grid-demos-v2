"""Count non-TEC denominations that contain 'episcopal' in their names."""
from google.cloud import bigquery

client = bigquery.Client(project='american-rel-infra')
DATASET = 'american-rel-infra.American_Religious_Infrastructure'

queries = {
    'AME (African Methodist Episcopal)': "LOWER(name) LIKE '%methodist episcopal%' AND NOT LOWER(name) LIKE '%protestant episcopal%'",
    'AME (concatenated METHODISTEPISCOPAL)': "LOWER(name) LIKE '%methodistepiscopal%'",
    'AME Zion': "LOWER(name) LIKE '%ame zion%' OR LOWER(name) LIKE '%episcopal zion%'",
    'CME (Christian Methodist Episcopal)': "LOWER(name) LIKE '%cme church%' OR LOWER(name) LIKE '%christian methodist episcopal%'",
    'Reformed Episcopal': "LOWER(name) LIKE '%reformed episcopal%'",
    'Charismatic Episcopal': "LOWER(name) LIKE '%charismatic episcopal%'",
    'Pentecostal Episcopal': "LOWER(name) LIKE '%pentecostal episcopal%' OR LOWER(name) LIKE '%pentacostal episcopal%'",
    'Independent Episcopal': "LOWER(name) LIKE '%independent episcopal%'",
    'Continuing Anglican (Anglican Rite Catholic Apostolic)': "LOWER(name) LIKE '%anglican rite catholic apostolic%'",
    'Church of Uganda': "LOWER(name) LIKE '%anglican church of uganda%'",
    'Free Christian Church Episcopal': "LOWER(name) LIKE '%free christian church episcopal%'",
    'Anglican Fellowship Church (ACNA)': "LOWER(name) LIKE '%anglican fellowship church%'",
    'Evangelical Church of the Advent Anglican Communion': "LOWER(name) LIKE '%evangelical church of the advent anglican communion%'",
}

print('Excluded denominations breakdown:\n')
grand_total = 0
for label, filt in queries.items():
    n = list(client.query(f"SELECT COUNT(*) FROM `{DATASET}.vw_church_census` WHERE {filt}").result())[0][0]
    if n:
        print(f'  {label}: {n:,}')
        grand_total += n
    else:
        print(f'  {label}: 0')

# Total episcopal-name records
total = list(client.query(f"SELECT COUNT(*) FROM `{DATASET}.vw_church_census` WHERE LOWER(name) LIKE '%episcopal%'").result())[0][0]
print(f'\n  Total records with "Episcopal" in name: {total:,}')
print(f'  Excluded (non-TEC): {grand_total:,}')
print(f'  Remaining TEC: {total - grand_total:,}')
