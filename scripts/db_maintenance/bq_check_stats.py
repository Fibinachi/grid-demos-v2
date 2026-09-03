from google.cloud import bigquery
client = bigquery.Client(project='american-rel-infra')

queries = [
    ('Total', "SELECT COUNT(*) FROM American_Religious_Infrastructure.churches"),
    ('Websites', "SELECT COUNT(*) FROM American_Religious_Infrastructure.churches WHERE website IS NOT NULL AND website != ''"),
    ('Emails', "SELECT COUNT(*) FROM American_Religious_Infrastructure.churches WHERE email IS NOT NULL AND email != ''"),
    ('Phones', "SELECT COUNT(*) FROM American_Religious_Infrastructure.churches WHERE phone IS NOT NULL AND phone != ''"),
    ('Denominated', "SELECT COUNT(*) FROM American_Religious_Infrastructure.churches WHERE denomination IS NOT NULL AND denomination != ''"),
    ('Attendance', "SELECT SUM(estimated_attendance) FROM American_Religious_Infrastructure.churches"),
    ('Top Denoms', "SELECT denomination, COUNT(*) as cnt FROM American_Religious_Infrastructure.churches WHERE denomination IS NOT NULL AND denomination != '' GROUP BY denomination ORDER BY cnt DESC LIMIT 15"),
]

for label, q in queries:
    try:
        rows = client.query(q).result()
        if label == 'Top Denoms':
            print('Top 15 Denominations:')
            for r in rows:
                print(f'  {r[0][:45]:<45} {r[1]:>8,}')
        else:
            for r in rows:
                val = list(r.values())[0]
                if isinstance(val, float):
                    print(f'{label}: {int(val):,}')
                else:
                    print(f'{label}: {val:,}')
    except Exception as e:
        print(f'{label}: ERROR - {e}')
