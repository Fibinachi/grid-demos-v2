"""Publish clean KY flood map to Substack."""
import os, sys, json, math, sqlite3, base64, urllib.parse
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright

SUB = 'gridkeeper'
DECODED = urllib.parse.unquote(os.environ['SUBSTACK_COOKIE'])
COOKIE = f'connect.sid={DECODED}; substack.sid={DECODED}'
HEADERS = {'Cookie': COOKIE, 'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'}

# Auth
r = requests.get('https://substack.com/api/v1/user/profile/self', headers=HEADERS)
p = r.json()
pub = next(pu for pu in p['publicationUsers'] if pu['publication']['subdomain'] == SUB)
print(f'Auth: {p["handle"]}')

# Screenshot
OUT = Path('E:/grid/outputs/substack_maps')
OUT.mkdir(parents=True, exist_ok=True)
png = OUT / 'ky_flood_map.png'

with sync_playwright() as pw:
    br = pw.chromium.launch()
    pg = br.new_page(viewport={'width': 1400, 'height': 900})
    pg.goto('file:///E:/grid/docs/ky-flood-2026_map.html')
    pg.wait_for_timeout(3000)
    pg.screenshot(path=str(png), full_page=True)
    br.close()
print(f'Screenshot: {png}')

# Upload
with open(str(png), 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
r = requests.post(f'https://{SUB}.substack.com/api/v1/image', headers=HEADERS,
                  json={'image': f'data:image/png;base64,{b64}'})
img = r.json()
print(f'Uploaded: {img["url"]}')

# Query top 25
db = sqlite3.connect('E:/grid/churches.db')
c = db.cursor()

c.execute("""
    SELECT rowid, name, city, state, flood_risk_score, faith, latitude, longitude
    FROM churches WHERE country='US' AND latitude BETWEEN 37.0 AND 39.0 
    AND longitude BETWEEN -86.0 AND -84.5 AND flood_risk_score >= 0.9
    ORDER BY flood_risk_score DESC, name LIMIT 25
""")
ky25 = []
for r in c.fetchall():
    ky25.append({'rowid': r[0], 'name': r[1], 'city': r[2], 'state': r[3],
                  'risk': r[4], 'faith': r[5], 'latitude': r[6], 'longitude': r[7]})

def hdist(lat1, lon1, lat2, lon2):
    dlat = math.radians(lat2 - lat1); dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    return 2 * 6371 * math.asin(min(1, math.sqrt(a)))

c.execute("""
    SELECT rowid, name, faith, latitude, longitude FROM churches 
    WHERE country='US' AND latitude BETWEEN 37.0 AND 39.0 
    AND longitude BETWEEN -86.0 AND -84.5 AND flood_risk_score = 0.5
""")
hubs = []
for r in c.fetchall():
    hubs.append({'rowid': r[0], 'name': r[1], 'faith': r[2], 'latitude': r[3], 'longitude': r[4]})

for ar in ky25:
    best = min(((h, hdist(ar['latitude'], ar['longitude'], h['latitude'], h['longitude']))
                for h in hubs), key=lambda x: x[1])
    ar['partner'] = best[0]['name']
    ar['partner_dist'] = round(best[1], 1)

db.close()

# Build ProseMirror doc
def pm(*c): return {'type': 'doc', 'content': list(c)}
def h1(t): return {'type': 'heading', 'attrs': {'level': 1}, 'content': [{'type': 'text', 'text': t}]}
def pt(t): return {'type': 'paragraph', 'attrs': {'textAlign': None}, 'content': [{'type': 'text', 'text': t}]}
def img_node(i):
    return {'type': 'captionedImage', 'content': [{
        'type': 'image2', 'attrs': {
            'src': i['url'], 'srcNoWatermark': None, 'fullscreen': None, 'imageSize': None,
            'width': i.get('imageWidth', 1400), 'height': i.get('imageHeight', 900),
            'resizeWidth': None, 'bytes': i.get('bytes', 0),
            'alt': None, 'title': None, 'type': 'image/png',
            'href': None, 'belowTheFold': False, 'topImage': False, 'internalRedirect': None}}]}

doc = [
    h1('Kentucky Ohio River — 25 Most At-Risk Churches'),
    pt('State of emergency. Ohio River flooding and Bullitt County dam failure. Late June - July 2026.'),
    pt(f'After deduplication and cleanup: {len(ky25)} critically at-risk churches shown below.'),
    img_node(img),
    pt(''),
]
for i, ar in enumerate(ky25, 1):
    line = f"{i:2d}. {(ar['name'] or '?')[:45]:45s} | {ar['city'] or '?'}, {ar['state'] or '?'} | {ar['faith'] or '?'} | partner: {ar['partner'][:40]:40s} ({ar['partner_dist']}km)"
    doc.append(pt(line))

body = {
    'draft_title': 'GRID Flood Alert — Kentucky Ohio River — 25 Most At-Risk Churches',
    'draft_body': json.dumps(pm(*doc)),
    'type': 'newsletter',
    'draft_bylines': [{'id': p['id'], 'publicationUserId': pub['id']}],
}
r = requests.post(f'https://{SUB}.substack.com/api/v1/drafts', headers=HEADERS, json=body)
did = r.json()['id']
print(f'✅ https://{SUB}.substack.com/publish/post/{did}')
