import requests, json, re

# Debug: check what fields IA actually returns
r = requests.get('https://archive.org/advancedsearch.php', params={
    'q': 'identifier:gastoniagastonco1976unse',
    'output': 'json', 'rows': 1
})
doc = r.json()['response']['docs'][0]
print('Available fields:', sorted(doc.keys()))
print()

# Now check the actual search
r = requests.get('https://archive.org/advancedsearch.php', params={
    'q': 'title:(city directory) AND year:[1960 TO 1980]',
    'output': 'json', 'rows': 10, 'sort': 'date'
})
docs = r.json()['response']['docs']
print(f'Total: {r.json()["response"]["numFound"]}, showing {len(docs)}\n')

# Extract city/state from each title
state_map = {'N.C.': 'NC', 'S.C.': 'SC', 'Va.': 'VA', 'Calif.': 'CA',
             'Mass.': 'MA', 'Mich.': 'MI', 'Ill.': 'IL', 'Fla.': 'FL',
             'Tex.': 'TX', 'Ont.': 'ON', 'Ontario': 'ON', 'Ga.': 'GA',
             'Ala.': 'AL', 'Miss.': 'MS', 'Tenn.': 'TN', 'Ind.': 'IN',
             'Ohio': 'OH', 'Wis.': 'WI', 'Minn.': 'MN', 'Mo.': 'MO',
             'Kan.': 'KS', 'Neb.': 'NE', 'Colo.': 'CO', 'Oreg.': 'OR',
             'Wash.': 'WA', 'Ariz.': 'AZ', 'Conn.': 'CT', 'Md.': 'MD',
             'Pa.': 'PA', 'N.Y.': 'NY', 'N.J.': 'NJ', 'Ky.': 'KY',
             'La.': 'LA', 'Okla.': 'OK', 'Iowa': 'IA', 'Vt.': 'VT',
             'N.H.': 'NH', 'Me.': 'ME', 'R.I.': 'RI', 'Del.': 'DE',
             'W.Va.': 'WV', 'Nev.': 'NV', 'N.M.': 'NM', 'Wyo.': 'WY',
             'Mont.': 'MT', 'S.D.': 'SD', 'N.D.': 'ND', 'Idaho': 'ID',
             'Ark.': 'AR'}

for doc in docs[:30]:
    title = doc.get('title', '')
    ident = doc.get('identifier', '')
    subjects = doc.get('subject', [])
    
    # Try to extract city from various title formats
    city, state = None, None
    
    # Format 1: "City (County, ST) city directory"
    m = re.match(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s*\([^)]+,\s*([A-Z]{2}|[A-Z][a-z]+\.)\s*\)', title)
    if m:
        city, state = m.group(1), state_map.get(m.group(2), m.group(2))
    
    # Format 2: "Polk's City (County, ST) city directory"
    if not city:
        m = re.search(r"(?:Polk's|Hill's|Might's|Vernon's)?\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s*\([^)]+,\s*([A-Z]{2}|[A-Z][a-z]+\.)\s*\)", title)
        if m:
            city, state = m.group(1), state_map.get(m.group(2), m.group(2))
    
    # Format 3: "YEAR Vernon's City City Directory" or "YEAR City City Directory"
    if not city:
        m = re.match(r'\d{4}\s+(?:Vernon\'s|Polk\'s|Hill\'s|Might\'s)?\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s+City\s+Directory', title)
        if m:
            city = m.group(1)
            # Infer state from subjects
            for subj in subjects:
                if subj.endswith('ON') or subj.endswith('ON.'):
                    state = 'ON'
                elif '--' in subj:
                    st_part = subj.split('--')[-1].strip()
                    if st_part in state_map:
                        state = state_map[st_part]
                    elif len(st_part) == 2 and st_part.isupper():
                        state = st_part
    
    # Format 4: "City, State, city directory"
    if not city:
        m = re.match(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)*),\s*([A-Z]{2})\b', title)
        if m:
            city, state = m.group(1), m.group(2)
    
    state_s = state or '?'
    city_s = city or '?'
    print(f'{city_s:25s} {state_s:4s} | {ident[:45]:45s} | {title[:70]}')
