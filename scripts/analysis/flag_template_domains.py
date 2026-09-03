"""
Flag template/shared church website domains and try to resolve actual ownership.
Identifies domains shared by multiple churches, checks if they're template
hosting platforms, and flags them on the churches table.
"""
import sqlite3, urllib.request, json, re, ssl

conn = sqlite3.connect('churches.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Find all domains shared by 2+ churches (exclude known junk patterns)
cur.execute("""
    SELECT LOWER(TRIM(website)) as w, COUNT(*) as cnt,
           GROUP_CONCAT(id) as ids,
           GROUP_CONCAT(name, '||') as names,
           GROUP_CONCAT(city, '||') as cities,
           GROUP_CONCAT(state, '||') as states,
           GROUP_CONCAT(denomination, '||') as denoms
    FROM churches 
    WHERE website != '' AND website IS NOT NULL
      AND website NOT LIKE '%google.com/maps%'
      AND website NOT LIKE '%facebook.com%'
      AND website NOT LIKE '%churches.sbc.net%'
      AND LENGTH(TRIM(website)) > 5
      AND website != 'https://'
      AND website != 'http://'
    GROUP BY LOWER(TRIM(website))
    HAVING cnt > 1
    ORDER BY cnt DESC
""")

rows = cur.fetchall()
print(f"Found {len(rows)} shared domains")
print()

# Classify each domain
TEMPLATE_PATTERNS = []

for r in rows:
    url = r['w']
    cnt = r['cnt']
    ids = [int(x) for x in r['ids'].split(',')]
    names = r['names'].split('||')
    cities = r['cities'].split('||')
    states = r['states'].split('||')
    denoms = r['denoms'].split('||')
    
    # Extract domain from URL
    domain = re.sub(r'^https?://(www\.)?', '', url).strip('/')
    
    # Check if it's a name-matching template
    # e.g., immanuel-lutheran-church.org shared by 72 Immanuel Lutheran Churches
    # The domain name matches the church name pattern
    
    # Count unique cities and states
    unique_states = set(s.strip() for s in states)
    unique_cities = set(c.strip() for c in cities)
    
    # Count unique denominations
    unique_denoms = set(d.strip() for d in denoms if d.strip())
    
    # Determine if this is a template domain
    is_template = False
    template_type = None
    likely_owner = None
    
    if cnt >= 5 and len(unique_states) >= 2:
        # Shared across multiple states = almost certainly a template
        is_template = True
        template_type = 'multi_state_template'
    elif cnt >= 3 and len(unique_cities) >= 2:
        is_template = True
        template_type = 'multi_city_template'
    
    # Special known template patterns
    lutheran_domains = [
        'immanuel-lutheran-church.org', 'trinity-lutheran-church.com',
        'zion-lutheran-church.com', 'grace-lutheran-church.com',
        'redeemer-lutheran-church.org', 'christ-lutheran-church.org',
        'first-lutheran-church.com', 'bethlehem-lutheran-church.com',
        'our-redeemer-lutheran-church.org', 'messiah-lutheran-church.com',
        'st-johns-lutheran-church.com', 'st-pauls-lutheran-church.com',
        'peace-lutheran-church.org', 'faith-lutheran-church.org',
        'hope-lutheran-church.com', 'st-lukes-lutheran-church.com',
    ]
    
    if domain in lutheran_domains:
        is_template = True
        template_type = 'lutheran_template_host'
    
    # Check for ministries.org - known placeholder
    if 'ministries.org' in domain:
        is_template = True
        template_type = 'placeholder_host'
    
    # Check for iglesiatijuana.org - all same city, Overture import
    if 'iglesiatijuana' in domain:
        is_template = True
        template_type = 'import_artifact'
    
    # Flag churches using this domain
    if is_template and cnt > 0:
        flag_sql = """
            UPDATE churches 
            SET website_source = 'template_host',
                website_confidence = 0.05,
                notes = CASE 
                    WHEN notes != '' AND notes IS NOT NULL THEN notes || ' | Template domain: ' || ?
                    ELSE 'Template domain: ' || ?
                END
            WHERE id IN ({})
        """.format(','.join('?' * len(ids)))
        cur.execute(flag_sql, [domain, domain] + ids)
        
        TEMPLATE_PATTERNS.append({
            'domain': domain,
            'count': cnt,
            'states': len(unique_states),
            'cities': len(unique_cities),
            'denoms': unique_denoms,
            'type': template_type,
            'ids': ids,
            'names_sample': names[:5],
            'cities_sample': cities[:5],
        })

conn.commit()
conn.close()

# Print summary
print(f"Flagged {sum(t['count'] for t in TEMPLATE_PATTERNS)} churches across {len(TEMPLATE_PATTERNS)} template domains")
print()

for t in sorted(TEMPLATE_PATTERNS, key=lambda x: -x['count']):
    denom_str = ', '.join(list(t['denoms'])[:3])
    print(f"[{t['count']:>4}x] {t['domain']:45s} ({t['type']:30s}) - {t['states']} states, {t['cities']} cities")
    if t['denoms']:
        print(f"      Denoms: {denom_str}")
    for i, (n, ci) in enumerate(zip(t['names_sample'], t['cities_sample'])):
        print(f"      {n:50s} {ci}")
    print()
