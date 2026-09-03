from gw_db import connect, Provenance
conn=connect()
with Provenance(conn, 'fix_antarctic_countries.py', source='manual_fix', fields='country,denomination'):
    c=conn.cursor()
    c.execute("UPDATE churches SET country='US' WHERE rowid=1307573")
    print('Chapel of the Snows -> US')
    c.execute("UPDATE churches SET country='AR' WHERE rowid IN (1619743,1890082)")
    print('Chapel of Blessed Virgin (2 rows) -> AR')
    c.execute("UPDATE churches SET country='RU', denomination='Russian Orthodox' WHERE rowid=1884100")
    print('Trinity Church -> RU, Russian Orthodox')
conn.commit()
conn.close()
print('Done')
