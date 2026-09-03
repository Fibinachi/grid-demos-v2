"""Quick sample of state-code-only MX records south of 32°N"""
import sqlite3
db = sqlite3.connect(r"E:\grid\churches.db")
c = db.cursor()
us_states = ('AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
    'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI',
    'MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND',
    'OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT',
    'VA','WA','WV','WI','WY','DC')
c.execute(f"""SELECT source, state, city, faith, COUNT(*) as cnt FROM churches 
    WHERE country='MX' AND state IN ({','.join(['?']*len(us_states))})
    AND NOT (latitude >= 32 AND longitude BETWEEN -125 AND -65)
    GROUP BY source, state, city, faith ORDER BY cnt DESC LIMIT 20""", us_states)
print("State-code-only MX records (south of 32):")
for r in c.fetchall():
    src = str(r[0] or "NULL")[:48]
    city = str(r[2] or "NULL")[:25]
    faith = str(r[3] or "NULL")[:20]
    print(f"  {src:48s} {r[1]:4s} {city:25s} {faith:20s} {r[4]:>5}")
db.close()
