import sqlite3
conn = sqlite3.connect('churches.db')

print('=== MX CLASSIFICATION RESULTS ===')

total_mx = conn.execute("SELECT COUNT(*) FROM churches WHERE country='MX'").fetchone()[0]
classified = conn.execute("SELECT COUNT(*) FROM churches WHERE country='MX' AND faith_tradition IS NOT NULL AND faith_tradition != ''").fetchone()[0]
print(f'Total MX: {total_mx:,} | Classified: {classified:,} ({100*classified/total_mx:.1f}%)')

print('\nBy faith_tradition + subtradition:')
for r in conn.execute("""
    SELECT faith_tradition, subtradition, COUNT(*) n, 
           ROUND(AVG(confidence_score),2) avg_conf,
           classification_source
    FROM churches WHERE country='MX' AND faith_tradition IS NOT NULL AND faith_tradition != ''
    GROUP BY 1, 2, classification_source
    ORDER BY 3 DESC LIMIT 20
"""):
    print(f'  {r[0] or "?":20s} {r[1] or "?":25s} {r[2]:>8,}  conf={r[3]}  src={r[4]}')

print('\n=== FAITH TRADITION SUMMARY ===')
for r in conn.execute("""
    SELECT faith_tradition, COUNT(*) n, ROUND(AVG(confidence_score),2) avg_conf
    FROM churches WHERE country='MX'
    GROUP BY 1 ORDER BY 2 DESC
"""):
    print(f'  {r[0] or "NULL":25s} {r[1]:>8,}  conf={r[2]}')

# Show some samples
print('\n=== SAMPLES BY CATEGORY ===')
for ft, sub in [('christian','catholic'), ('christian','baptist'), 
                ('christian','non_denominational'), ('christian','evangelical'),
                ('christian','pentecostal'), ('jewish',None), ('unknown',None)]:
    row = conn.execute("""
        SELECT name, city, state, confidence_score, classification_source
        FROM churches WHERE country='MX' AND faith_tradition=? AND COALESCE(subtradition,'')=COALESCE(?, '')
        LIMIT 3
    """, (ft, sub or '')).fetchall()
    if row:
        print(f'\n  {ft}/{sub or "none"}:')
        for r in row:
            print(f'    "{r[0][:50]:50s}" {r[1]:15s} {r[2]}  conf={r[3]}  src={r[4]}')

# Also check if US churches got classified (they shouldn't have)
us_classified = conn.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND faith_tradition IS NOT NULL AND faith_tradition != ''").fetchone()[0]
print(f'\nUS classified (should be 0 from this run): {us_classified:,}')

conn.close()
