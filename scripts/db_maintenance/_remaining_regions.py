import sqlite3

with open('E:/grid/_osm_checkpoint.txt') as f:
    done = {line.strip() for line in f if line.strip()}

gconn = sqlite3.connect('E:/grid/data/natural_earth/world_borders.db')
gc = gconn.cursor()
gc.execute("SELECT iso_a2, name FROM world_borders WHERE iso_a2 NOT IN ('-99','') AND iso_a2 IS NOT NULL ORDER BY iso_a2")
all_codes = {row[0]: row[1] for row in gc.fetchall()}
gconn.close()

SKIP = {'US','IN','BR','GB','DE','FR','IT','ES','PL','NL','JP','KR','AU','CA','MX',
    'AR','CO','CL','PE','ZA','NZ','IE','AT','CH','BE','SE','NO','DK','FI','PT',
    'GR','CZ','SK','HU','RO','BG','HR','SI','LT','LV','EE','IS','LU','MT','CY',
    'SG','HK','TW','IL','AE','KW','QA','BH','OM','UY','CR','PA','DO','JM','TT',
    'PH','TH','VN','MY','ID','LK','NP','KE','GH','ZW','ZM','MW','TZ','UG','AO',
    'NA','BW','LS','SZ','CG','GA','GQ','CV','ST','SC','MU','BN',
    'KI','NR','TV','TO','WS','PW','FM','MH','CK','NU','TK','WF','FJ','SB','VU','PG','TL'}

remaining = []
for code, name in sorted(all_codes.items()):
    if code not in SKIP and code not in done:
        remaining.append(f'{code} ({name})')

print(f'SKIP: {len(SKIP)} countries')
print(f'Done: {len(done)} countries')
print(f'Remaining: {len(remaining)} countries')
print()
for r in remaining:
    print(r)
