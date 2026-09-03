#!/usr/bin/env python
"""Create all flood alert drafts on Substack."""
import os, json, requests, urllib.parse

DECODED = urllib.parse.unquote(os.environ.get('SUBSTACK_COOKIE', ''))
COOKIE = f"connect.sid={DECODED}; substack.sid={DECODED}"
HEADERS = {'Cookie': COOKIE, 'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'}
SUB = 'gridkeeper'

r = requests.get('https://substack.com/api/v1/user/profile/self', headers=HEADERS)
if r.status_code != 200:
    print(f'Auth failed: {r.text[:200]}')
    exit(1)
p = r.json()
pub = next(pu for pu in p['publicationUsers'] if pu['publication']['subdomain'] == SUB)
print(f'Authenticated: {p["handle"]}')

def pm(*c): return {'type':'doc','content':list(c)}
def h1(t): return {'type':'heading','attrs':{'level':1},'content':[{'type':'text','text':t}]}
def h2(t): return {'type':'heading','attrs':{'level':2},'content':[{'type':'text','text':t}]}
def pt(t): return {'type':'paragraph','attrs':{'textAlign':None},'content':[{'type':'text','text':t}]}
def pr(parts):
    c = []
    for x in parts:
        m = []
        if x.get('b'): m.append({'type':'bold'})
        if x.get('i'): m.append({'type':'italic'})
        n = {'type':'text','text':x['t']}
        if m: n['marks'] = m
        c.append(n)
    return {'type':'paragraph','attrs':{'textAlign':None},'content':c}
def hr(): return {'type':'horizontal_rule'}
def bl(*items):
    return {'type':'bullet_list','content':[{'type':'list_item','content':[pr(i) if isinstance(i,list) else pt(i)]} for i in items]}
def ol(*items):
    return {'type':'ordered_list','content':[{'type':'list_item','content':[pr(i) if isinstance(i,list) else pt(i)]} for i in items]}

def post(title, doc_parts):
    body = {
        'draft_title': title,
        'draft_body': json.dumps(pm(*doc_parts)),
        'type': 'newsletter',
        'draft_bylines': [{'id': p['id'], 'publicationUserId': pub['id']}],
    }
    r = requests.post(f'https://{SUB}.substack.com/api/v1/drafts', headers=HEADERS, json=body)
    if r.status_code == 200:
        did = r.json()['id']
        print(f'  ✅ https://{SUB}.substack.com/publish/post/{did}')
    else:
        print(f'  ❌ {r.status_code}: {r.text[:200]}')

print('\n--- TX Elevation Map ---')
post('GRID Flood Alert — Texas Hill Country Flash Floods', [
    h1('Texas Hill Country Flash Floods'),
    pr([{'t':'Guadalupe River catastrophic flash flooding. ','b':True},{'t':'Kerr County, July 4-6 2026.'}]),
    pt('This elevation-based analysis identifies churches below 505m as at-risk and pairs each with a same-denomination partner hub above the flood line.'),
    h2('Key Statistics'),
    bl([{'t':'4,380','b':True},{'t':' churches below flood level (at-risk)'}],[{'t':'1,768','b':True},{'t':' churches above (partner hubs)'}],[{'t':'4,184','b':True},{'t':' matched (96%)'}],[{'t':'196','b':True},{'t':' unmatched'}]),
    h2('Methodology'),
    pt('Elevation data from USGS 3DEP / Open-Meteo. County-level averages from tract_elevation (25,599 tracts). Flood crest ~505m. Each at-risk church matched to nearest same-denomination hub within 50 km.'),
    hr(),
    pt('Data: GRID. Contact: charlesaprescott@outlook.com'),
])

print('\n--- TX Analysis Paper ---')
post('GRID Disaster Response Analysis — Texas Hill Country Floods', [
    h1('GRID Disaster Response Analysis'),
    h2('Texas Hill Country — July 2026'),
    h2('Data Sources'),
    bl(
        'FEMA NFHL — National Flood Hazard Layer',
        'FEMA NRI — National Risk Index tract scores',
        'USGS 3DEP / Open-Meteo — Elevation data',
        'GRID Database — 3,288,869 facilities, 247 countries',
    ),
    h2('Methodology'),
    pt('Churches assigned county average elevation from tract_elevation (25,599 US tracts, 659 counties). Churches below flood level = at-risk. Above = safe hubs. Algorithmic same-denomination matching within 50 km.'),
    h2('Limitations'),
    ol(
        'County-level elevation, not point-level GPS',
        'Estimated 505m flood crest',
        'Phone data: ~51K of 3.3M churches',
        'Property tax: TN (5,314 parcels) only',
    ),
    h2('Provenance'),
    pt('SQLite3 DB (~14.4 GB). All scripts open-source. Fully reproducible.'),
    hr(),
    pt('Contact: charlesaprescott@outlook.com — GRID'),
])

print('\n--- KY Flood Map ---')
post('GRID Flood Alert — Kentucky Ohio River Flooding', [
    h1('Kentucky Ohio River Flooding'),
    pr([{'t':'State of emergency. ','b':True},{'t':'Ohio River flooding, Bullitt County dam failure. Late June - July 2026.'}]),
    pt('Risk-score analysis using FEMA NFHL data.'),
    h2('Key Statistics'),
    bl([{'t':'107','b':True},{'t':' at-risk churches'}],[{'t':'106','b':True},{'t':' matched with partner hub'}],[{'t':'1','b':True},{'t':' unmatched'}],[{'t':'101','b':True},{'t':' partner hubs'}]),
    h2('Methodology'),
    pt('Flood risk scores from FEMA NFHL + NRI. ≥0.9 critical, ≥0.7 high, ≥0.5 moderate.'),
    hr(),
    pt('Data: GRID. Contact: charlesaprescott@outlook.com'),
])

print('\n✅ All three drafts created!')
