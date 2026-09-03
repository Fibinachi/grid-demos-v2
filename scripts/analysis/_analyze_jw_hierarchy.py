"""Analyze JW hierarchy patterns in the database."""
import sqlite3

db = sqlite3.connect(r'E:\grid\churches.db', timeout=120)
c = db.cursor()

queries = {
    'circuit': """
        SELECT name, COUNT(*) as cnt FROM churches 
        WHERE name LIKE '%Circuit%' AND (name LIKE '%Jehov%' OR name LIKE '%Witness%') 
        GROUP BY name ORDER BY cnt DESC LIMIT 20
    """,
    'congregation': """
        SELECT name, COUNT(*) as cnt FROM churches 
        WHERE name LIKE '%Congregation%Jehov%' OR name LIKE '%Congregation%Witness%'
        OR name LIKE '%Congregation%Jehova%' OR name LIKE '%Congregation%Wtnss%'
        GROUP BY name ORDER BY cnt DESC LIMIT 20
    """,
    'assembly_hall': """
        SELECT name, COUNT(*) as cnt FROM churches 
        WHERE (name LIKE '%Assembly%Hall%' AND (name LIKE '%Jehov%' OR name LIKE '%Witness%'))
        GROUP BY name ORDER BY cnt DESC LIMIT 20
    """,
    'study': """
        SELECT name, COUNT(*) as cnt FROM churches 
        WHERE (name LIKE '%Study%' OR name LIKE '%Bible Study%' OR name LIKE '%Bible%Study%')
        AND (name LIKE '%Jehov%' OR name LIKE '%Witness%')
        GROUP BY name ORDER BY cnt DESC LIMIT 20
    """,
    'convention': """
        SELECT name, COUNT(*) as cnt FROM churches 
        WHERE name LIKE '%Convention%' AND (name LIKE '%Jehov%' OR name LIKE '%Witness%')
        GROUP BY name ORDER BY cnt DESC LIMIT 10
    """,
    'JW_main': """
        SELECT COUNT(*) FROM churches 
        WHERE (name LIKE '%Kingdom%Hall%' OR name LIKE '%Jehovah%' OR name LIKE '%Jehova%'
           OR name LIKE '%Salon%Reino%' OR name LIKE '%Salon%Reino%' OR name LIKE '%Salao%Reino%'
           OR name LIKE '%Salao%Reino%' OR name LIKE '%Assembly%Hall%Jehov%'
           OR name LIKE '%Testigos%Jehova%' OR name LIKE '%Testemunha%Jeova%'
           OR name LIKE '%Witnesses%')
        AND name NOT LIKE '%Universal%' AND name NOT LIKE '%IURD%'
        AND name NOT LIKE '%JIREH%' AND name NOT LIKE '%Jireh%'
        AND name NOT LIKE '%BAPTIST%' AND name NOT LIKE '%Baptist%'
        AND name NOT LIKE '%LUTHERAN%' AND name NOT LIKE '%Lutheran%'
        AND name NOT LIKE '%SHAMMAH%' AND name NOT LIKE '%RAPHA%'
        AND name NOT LIKE '%MINISTRIES%' AND name NOT LIKE '%Ministries%'
        AND name NOT LIKE '%METHODIST%' AND name NOT LIKE '%Pentecostal%'
        AND name NOT LIKE '%PENTECOSTAL%' AND name NOT LIKE '%CHRISTIAN%'
        AND name NOT LIKE '%FELLOWSHIP%' AND name NOT LIKE '%Fellowship%'
        AND name NOT LIKE '%PRAISE%' AND name NOT LIKE '%Praise%'
        AND name NOT LIKE '%WORSHIP%' AND name NOT LIKE '%Worship%'
        AND name NOT LIKE '%COMMUNITY%' AND name NOT LIKE '%Community%'
        AND name NOT LIKE '%MISSIONARY%' AND name NOT LIKE '%Missionary%'
        AND name NOT LIKE '%DELIVERANCE%' AND name NOT LIKE '%NISSI%'
        AND name NOT LIKE '%Nissi%' AND name NOT LIKE '%SAMA%'
        AND name NOT LIKE '%Sama%' AND name NOT LIKE '%SHALOM%'
        AND name NOT LIKE '%Shalom%' AND name NOT LIKE '%CHURCH OF%'
        AND name NOT LIKE '%Church of%' AND name NOT LIKE '%GOSPEL%'
        AND name NOT LIKE '%Gospel%' AND name NOT LIKE '%ROI%'
        AND name NOT LIKE '%Rohi%' AND name NOT LIKE '%EL BUEN PASTOR%'
        AND name NOT LIKE '%PRAYER%' AND name NOT LIKE '%Prayer%'
        AND name NOT LIKE '%HOUSE OF%' AND name NOT LIKE '%House of%'
    """
}

# Get main JW total
jw_total = c.execute(queries['JW_main']).fetchone()[0]
print(f'\nTotal JW-matching entries: {jw_total:,}')
del queries['JW_main']

for label, q in queries.items():
    rows = c.execute(q).fetchall()
    total = sum(r[1] for r in rows)
    print(f'\n=== {label.upper()} ({total} entries, {len(rows)} unique) ===')
    for name, cnt in rows:
        print(f'  [{cnt:3d}] {name[:120]}')

db.close()
