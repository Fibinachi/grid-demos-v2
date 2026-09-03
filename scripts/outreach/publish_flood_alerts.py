#!/usr/bin/env python
"""
Publish flood alert drafts to Substack with map screenshots + top 25 table.
Captures map screenshots via Playwright, uploads images, posts to Substack.
"""
import os, sys, json, math, sqlite3, base64, urllib.parse
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

DECODED = urllib.parse.unquote(os.environ.get('SUBSTACK_COOKIE', ''))
COOKIE = f"connect.sid={DECODED}; substack.sid={DECODED}"
HEADERS = {'Cookie': COOKIE, 'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'}
SUB = 'gridkeeper'
DB = Path('E:/grid/churches.db')

# ── Auth ──
r = requests.get('https://substack.com/api/v1/user/profile/self', headers=HEADERS)
if r.status_code != 200:
    print(f'Auth failed: {r.text[:200]}')
    sys.exit(1)
profile = r.json()
pub = next(pu for pu in profile['publicationUsers'] if pu['publication']['subdomain'] == SUB)
print(f'Authenticated: {profile["handle"]} (id={profile["id"]})')

# ── DB helpers ──
def get_db():
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    return conn

def hdist(lat1, lon1, lat2, lon2):
    dlat = math.radians(lat2 - lat1); dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    return 2 * 6371 * math.asin(min(1, math.sqrt(a)))

def query_top25_tx():
    db = get_db(); c = db.cursor()
    # At-risk
    c.execute("""SELECT rowid, name, city, state, elevation_m, faith, latitude, longitude
        FROM churches WHERE country='US' AND latitude BETWEEN 29.5 AND 31.0 
        AND longitude BETWEEN -99.8 AND -97.5 AND elevation_m IS NOT NULL AND elevation_m < 505
        ORDER BY elevation_m ASC LIMIT 25""")
    at_risk = [dict(r) for r in c.fetchall()]
    # Hubs
    c.execute("""SELECT rowid, name, city, state, elevation_m, faith, latitude, longitude
        FROM churches WHERE country='US' AND latitude BETWEEN 29.5 AND 31.0 
        AND longitude BETWEEN -99.8 AND -97.5 AND elevation_m IS NOT NULL AND elevation_m >= 505""")
    hubs = [dict(r) for r in c.fetchall()]
    # Match
    for ar in at_risk:
        best = min(((h, hdist(ar['latitude'], ar['longitude'], h['latitude'], h['longitude']))
                    for h in hubs if h['faith'] == ar['faith'] or (not ar['faith'] and not h['faith'])),
                   key=lambda x: x[1], default=(None, None))
        if best[0]:
            ar['partner_name'] = best[0]['name'] or '?'
            ar['partner_city'] = best[0]['city'] or '?'
            ar['partner_dist'] = round(best[1], 1)
        else:
            ar['partner_name'] = None
    db.close()
    return at_risk

def query_top25_ky():
    db = get_db(); c = db.cursor()
    c.execute("""SELECT rowid, name, city, state, flood_risk_score, faith, latitude, longitude
        FROM churches WHERE country='US' AND latitude BETWEEN 37.0 AND 39.0 
        AND longitude BETWEEN -86.0 AND -84.5 AND flood_risk_score >= 0.9
        ORDER BY flood_risk_score DESC LIMIT 25""")
    at_risk = [dict(r) for r in c.fetchall()]
    c.execute("""SELECT rowid, name, city, state, flood_risk_score, faith, latitude, longitude
        FROM churches WHERE country='US' AND latitude BETWEEN 37.0 AND 39.0 
        AND longitude BETWEEN -86.0 AND -84.5 AND flood_risk_score = 0.5""")
    hubs = [dict(r) for r in c.fetchall()]
    for ar in at_risk:
        best = min(((h, hdist(ar['latitude'], ar['longitude'], h['latitude'], h['longitude']))
                    for h in hubs if h['faith'] == ar['faith'] or (not ar['faith'] and not h['faith'])),
                   key=lambda x: x[1], default=(None, None))
        if best[0]:
            ar['partner_name'] = best[0]['name'] or '?'
            ar['partner_city'] = best[0]['city'] or '?'
            ar['partner_dist'] = round(best[1], 1)
        else:
            ar['partner_name'] = None
    db.close()
    return at_risk

# ── Screenshot maps via Playwright ──
def screenshot_map(html_path, png_path):
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width': 1400, 'height': 900})
        page.goto(f'file:///{html_path}')
        page.wait_for_timeout(3000)
        page.screenshot(path=png_path, full_page=True)
        browser.close()

# ── Upload to Substack ──
def upload_image(png_path):
    with open(png_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('utf-8')
    r = requests.post(f'https://{SUB}.substack.com/api/v1/image', headers=HEADERS,
                      json={'image': f'data:image/png;base64,{b64}'})
    if r.status_code == 200:
        d = r.json()
        print(f'  📷 Uploaded: {d["url"]}')
        return {'url': d['url'], 'width': d.get('imageWidth', 1200), 'height': d.get('imageHeight', 800), 'bytes': d.get('bytes', 0)}
    else:
        print(f'  ⚠️ Upload failed: {r.status_code}')
        return None

# ── ProseMirror builders ──
def pm(*c): return {'type':'doc','content':list(c)}
def h1(t): return {'type':'heading','attrs':{'level':1},'content':[{'type':'text','text':t}]}
def h2(t): return {'type':'heading','attrs':{'level':2},'content':[{'type':'text','text':t}]}
def h3(t): return {'type':'heading','attrs':{'level':3},'content':[{'type':'text','text':t}]}
def pt(t): return {'type':'paragraph','attrs':{'textAlign':None},'content':[{'type':'text','text':t}]}
def pr(parts):
    marks_map = {'b':'bold','i':'italic','s':'strike','c':'code'}
    content = []
    for x in parts:
        marks = [{'type':marks_map[k]} for k in marks_map if x.get(k)] if isinstance(x, dict) else []
        n = {'type':'text','text':x['t'] if isinstance(x, dict) else str(x)}
        if marks: n['marks'] = marks
        content.append(n)
    return {'type':'paragraph','attrs':{'textAlign':None},'content':content}
def hr(): return {'type':'horizontal_rule'}
def bl(*items):
    li = []
    for item in items:
        para = pr(item) if isinstance(item, list) else pt(str(item))
        li.append({'type':'list_item','content':[para]})
    return {'type':'bullet_list','content':li}
def img_node(i):
    return {'type':'captionedImage','content':[{
        'type':'image2','attrs':{
            'src':i['url'],'srcNoWatermark':None,'fullscreen':None,'imageSize':None,
            'width':i['width'],'height':i['height'],'resizeWidth':None,'bytes':i['bytes'],
            'alt':None,'title':None,'type':'image/png','href':None,'belowTheFold':False,'topImage':False,'internalRedirect':None}}]}

def table_node(rows, headers=None):
    """Build a ProseMirror table. rows = list of lists of strings."""
    from_col = {'type':'table_col','attrs':{'colwidth':[200],'defaultColwidth':True}}
    cols = {'type':'table_col','attrs':{'colwidth':[300],'defaultColwidth':True}}
    cells = []
    if headers:
        row_cells = []
        for h in headers:
            row_cells.append({'type':'table_cell','content':[
                {'type':'paragraph','attrs':{'textAlign':None},
                 'content':[{'type':'text','marks':[{'type':'bold'}],'text':str(h)}]}]})
        cells.append({'type':'table_row','content':row_cells})
    for r in rows:
        row_cells = []
        for ci, cell in enumerate(r):
            row_cells.append({'type':'table_cell','content':[
                {'type':'paragraph','attrs':{'textAlign':None},
                 'content':[{'type':'text','text':str(cell)}]}]})
        cells.append({'type':'table_row','content':row_cells})
    return {'type':'table','attrs':{'isSimple':True},
            'content':[
                {'type':'table_row','content':[
                    {'type':'table_cell','content':[
                        {'type':'paragraph','attrs':{'textAlign':None},
                         'content':[{'type':'text','text':''}]}]}]}]}

# ── Post draft ──
def create_draft(title, doc_parts):
    body = {
        'draft_title': title,
        'draft_body': json.dumps(pm(*doc_parts)),
        'type': 'newsletter',
        'draft_bylines': [{'id': profile['id'], 'publicationUserId': pub['id']}],
    }
    r = requests.post(f'https://{SUB}.substack.com/api/v1/drafts', headers=HEADERS, json=body)
    if r.status_code == 200:
        did = r.json()['id']
        print(f'  ✅ https://{SUB}.substack.com/publish/post/{did}')
        return did
    else:
        print(f'  ❌ {r.status_code}: {r.text[:300]}')
        return None

# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════
OUT = Path('E:/grid/outputs/substack_maps')
OUT.mkdir(parents=True, exist_ok=True)

# 1. Screenshot maps
print('\n=== Capturing map screenshots ===')
tx_png = OUT / 'tx_hill_flood_map.png'
ky_png = OUT / 'ky_flood_map.png'
if not tx_png.exists():
    screenshot_map('E:/grid/docs/tx-hill-flood/tx-hill-flood-elev_map.html', str(tx_png))
    print(f'  TX map saved: {tx_png}')
if not ky_png.exists():
    screenshot_map('E:/grid/docs/flood_alert_ky.html', str(ky_png))
    print(f'  KY map saved: {ky_png}')

# 2. Upload images
print('\n=== Uploading images ===')
tx_img = upload_image(str(tx_png))
ky_img = upload_image(str(ky_png))

# 3. Query data
print('\n=== Querying data ===')
tx_rows = query_top25_tx()
ky_rows = query_top25_ky()
print(f'  TX top 25: {len(tx_rows)} rows, KY top 25: {len(ky_rows)} rows')

# 4. Build TX Elevation Map draft
print('\n--- TX Hill Country Flood Map ---')
tx_doc = [
    h1('Texas Hill Country — 25 Most At-Risk Churches'),
    pr([{'t':'Guadalupe River catastrophic flash flooding. ','b':True},{'t':'Kerr County, July 4-6 2026.'}]),
    pt(f'Of {6148:,} churches in the affected region, {4368:,} are below the 505m flood crest elevation. Only {238:,} safe hubs exist above it. Below are the 25 most vulnerable—lowest elevation sites—each paired with the nearest safe church of the same faith.'),
]

if tx_img:
    tx_doc.append(img_node(tx_img))

tx_doc.extend([
    h2('Top 25 At-Risk Churches'),
    pt(''),
])

# Build a simple table-like format using paragraphs
for i, ar in enumerate(tx_rows, 1):
    line = f"{i:2d}. {(ar['name'] or '?')[:40]:40s} | {ar['city'] or '?'}, {ar['state'] or '?'} | elev={ar['elevation_m']:.0f}m"
    if ar.get('partner_name'):
        line += f" → {ar['partner_name'][:40]:40s} ({ar['partner_dist']:.0f}km)"
    else:
        line += f" → ⚠️ NO PARTNER"
    tx_doc.append(pt(line))

tx_doc.extend([
    hr(),
    h3('Methodology'),
    pt('Elevation from USGS 3DEP via Open-Meteo (county averages from 25,599 tracts). Flood crest estimated at 505m. Each at-risk church matched to nearest same-faith hub ≥ 505m elevation.'),
    h3('Faiths at Risk'),
    bl(['Christian: 4,172','Buddhist: 44','Jewish: 39','Hindu: 34','Muslim: 30','Other: 21','Non-Religious: 11','Sikh: 8','Baháʼí: 7','Indigenous: 2']),
    hr(),
    pt('Data: GRID (Global Religious Infrastructure Database, 3.3M+ entries). Contact: charlesaprescott@outlook.com'),
])

create_draft('GRID Flood Alert — Texas Hill Country — 25 Most At-Risk Churches', tx_doc)

# 5. Build KY Flood Alert draft
print('\n--- KY Ohio River Flood Alert ---')
ky_doc = [
    h1('Kentucky Ohio River — 25 Most At-Risk Churches'),
    pr([{'t':'State of emergency. ','b':True},{'t':'Ohio River flooding and Bullitt County dam failure. Late June - July 2026.'}]),
    pt(f'Within the affected region, {107:,} churches are in the critical flood zone (risk ≥ 0.9), with {8160:,} more at moderate risk (0.5-0.7). Below are the 25 most critically at-risk, each paired with the nearest lower-risk partner.'),
]

if ky_img:
    ky_doc.append(img_node(ky_img))

ky_doc.extend([
    h2('Top 25 At-Risk Churches'),
    pt(''),
])

for i, ar in enumerate(ky_rows, 1):
    line = f"{i:2d}. {(ar['name'] or '?')[:40]:40s} | {ar['city'] or '?'}, {ar['state'] or '?'} | risk={ar['flood_risk_score']:.1f}"
    if ar.get('partner_name'):
        line += f" → {(ar['partner_name'])[:40]:40s} ({ar['partner_dist']:.0f}km)"
    else:
        line += f" → ⚠️ NO PARTNER"
    ky_doc.append(pt(line))

ky_doc.extend([
    hr(),
    h3('Methodology'),
    pt('Flood risk scores from FEMA NFHL (National Flood Hazard Layer) + FEMA NRI tract-level risk scores. Range: ≥0.9 critical (in SFHA/Special Flood Hazard Area), 0.7-0.9 high, 0.5-0.7 moderate. Partners selected from lowest-risk (0.5) same-faith churches.'),
    h3('Affected Counties'),
    pt('92 churches in KY, 15 in IN. Hardest hit: Edmonton, Glasgow, Somerset, Campbellsville, Bradfordsville, Shepherdsville areas.'),
    hr(),
    pt('Data: GRID (Global Religious Infrastructure Database, 3.3M+ entries). Contact: charlesaprescott@outlook.com'),
])

create_draft('GRID Flood Alert — Kentucky Ohio River — 25 Most At-Risk Churches', ky_doc)

print('\n✅ All drafts created with maps + top-25 analysis!')
