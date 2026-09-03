"""Generate report of ALL TEC congregations (no poverty filter) for review."""
from google.cloud import bigquery

client = bigquery.Client(project='american-rel-infra')
DATASET = 'american-rel-infra.American_Religious_Infrastructure'

CLEAN_FILTER = """
    denomination = 'Episcopal Church'
    AND (LOWER(name) LIKE '%church%' OR LOWER(name) LIKE '%parish%' 
         OR LOWER(name) LIKE '%cathedral%' OR LOWER(name) LIKE '%chapel%'
         OR LOWER(name) LIKE '%congregation%')
    AND NOT (LOWER(name) LIKE '%foundation%' OR LOWER(name) LIKE '%endowment%' OR LOWER(name) LIKE '% trust%')
    AND NOT (LOWER(name) LIKE '%school%' OR LOWER(name) LIKE '%academy%')
    AND NOT (LOWER(name) LIKE 'diocese of % protestant episcopal church%')
    AND NOT (LOWER(name) LIKE 'diocese of the % anglican episcopal church%')
    AND NOT (LOWER(name) LIKE 'diocese of the % reformed episcopal church%')
    AND NOT (LOWER(name) LIKE 'episcopal church diocese of %')
    AND NOT (LOWER(name) LIKE '%protestant episcopal church in the diocese of%')
    AND NOT (LOWER(name) LIKE '%protestant episcopal church diocese of%')
    AND NOT (
      LOWER(name) LIKE '%diocese%' 
      AND NOT (LOWER(name) LIKE '%church%' OR LOWER(name) LIKE '%parish%' 
               OR LOWER(name) LIKE '%cathedral%' OR LOWER(name) LIKE '%chapel%'
               OR LOWER(name) LIKE '%mission%' OR LOWER(name) LIKE '%congregation%')
    )
    AND NOT (LOWER(name) LIKE '%methodist episcopal%' AND NOT LOWER(name) LIKE '%protestant episcopal%')
    AND NOT (LOWER(name) LIKE '%methodistepiscopal%')
    AND NOT (LOWER(name) LIKE '%reformed episcopal%')
    AND NOT (LOWER(name) LIKE '%charismatic episcopal%')
    AND NOT (LOWER(name) LIKE '%independent episcopal%')
    AND NOT (LOWER(name) LIKE '%independnet episcopal%')  -- misspelling of Independent
    AND NOT (LOWER(name) LIKE '%united episcopal church%')
    AND NOT (LOWER(name) LIKE '%christian episcopal church%')
    AND NOT (LOWER(name) LIKE '%union methodist episcopal%')
    AND NOT (LOWER(name) LIKE '%union american methodist episcopal%')
    AND NOT (LOWER(name) LIKE '%wesleyan methodist episcopal%')
    AND NOT (LOWER(name) LIKE '%african methodist episcopal%')
    AND NOT (LOWER(name) LIKE '%african medhodist episcopal%')
    AND NOT (LOWER(name) LIKE '%african metholdist episcopal%')
    AND NOT (LOWER(name) LIKE '%african medethodist episcopal%')
    AND NOT (LOWER(name) LIKE '%episcopal zion%')
    AND NOT (LOWER(name) LIKE '%pentecostal episcopal%')
    AND NOT (LOWER(name) LIKE '%pentacostal episcopal%')
    AND NOT (LOWER(name) LIKE '%retirement%' OR LOWER(name) LIKE '%housing%')
    AND NOT (LOWER(name) LIKE '%bishop%')
    AND NOT (LOWER(name) LIKE '%convention%')
    AND NOT (LOWER(name) LIKE '%rector and vestry%')
    AND NOT (LOWER(name) LIKE '%rector wardens vestry%')  -- legal holding entity
    AND NOT (LOWER(name) LIKE '%wardens vestrymen%')  -- legal holding entity
    AND NOT (LOWER(name) LIKE '%proprietors of%')  -- legal holding entity
    AND NOT (LOWER(name) LIKE '% fund for % episcopal%')  -- fund LLC subentity
    AND NOT (LOWER(name) LIKE '% fund of % episcopal%')  -- fund LLC subentity
    AND NOT (LOWER(name) LIKE '%trustees of donations to the protestant episcopal%')
    AND NOT (LOWER(name) LIKE '%igbo%')
    AND NOT (LOWER(name) LIKE '%ministries inc%')
    AND NOT (LOWER(name) LIKE '%episcopal mission%')
    AND NOT (LOWER(name) LIKE 'protestant episcopal church in the united states of a%')
    AND NOT (LOWER(name) LIKE 'protestant episcopal church in the us%')  -- national body, not congregation
    AND NOT (LOWER(name) LIKE '%the protestant episcopal church in the usa%')  -- national body variant
    AND NOT (LOWER(name) LIKE '%south sudanese%episcopal%')  -- separate Anglican province, not TEC
    AND NOT (LOWER(name) LIKE '%episcopal church in the united states of %')
    AND NOT (LOWER(name) LIKE '%church women%')
    AND NOT (LOWER(name) LIKE '%church home%')
    AND NOT (LOWER(name) LIKE '%seminary%')
    AND NOT (LOWER(name) LIKE '%communion of episcopal%')
    AND NOT (LOWER(name) LIKE '%episcopal church council%')  -- governance body, not congregation
"""

print('Querying all TEC congregations...', end=' ', flush=True)
rows = list(client.query(f"""
    SELECT name, city, state, county_name, county_poverty_rate
    FROM `{DATASET}.vw_church_census`
    WHERE {CLEAN_FILTER}
    ORDER BY state, county_name, name
""").result())
print(f'{len(rows):,} rows')

with open('reports/episcopal_all_congregations.txt', 'w', encoding='utf-8') as f:
    f.write(f'ALL TEC CONGREGATIONS — {len(rows):,} total\n')
    f.write(f'Generated: 2026-06-16\n')
    f.write('=' * 100 + '\n\n')
    f.write(f'{"#":>5}  {"Name":<65} {"City":<25} {"St":<3} {"County":<25} {"Pov":>6}\n')
    f.write(f'{"-"*5}  {"-"*65} {"-"*25} {"-"*3} {"-"*25} {"-"*6}\n')

    for i, (name, city, state, county_name, pov) in enumerate(rows, 1):
        nm = (name or '')[:65]
        ct = (city or '')[:25]
        st = (state or '')[:3]
        cn = (county_name or '')[:25]
        pv = f'{pov*1:.1f}%' if pov else ''
        f.write(f'{i:5}  {nm:<65} {ct:<25} {st:<3} {cn:<25} {pv:>6}\n')

print(f'Saved reports/episcopal_all_congregations.txt')
