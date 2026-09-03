"""Generate numbered map + matching table for Substack.
Simple approach: numbered markers (1-25) on map, matching numbered table below."""
import os, json, math, sqlite3, base64, urllib.parse
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright
from scripts.visualization.map_utils import TILE_LAYERS, tile_error_fallback_js

DB = Path('E:/grid/churches.db')

# ── Auth ──
DECODED = urllib.parse.unquote(os.environ.get('SUBSTACK_COOKIE', ''))
COOKIE = f'connect.sid={DECODED}; substack.sid={DECODED}'
H = {'Cookie': COOKIE, 'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'}
SUB = 'gridkeeper'

r = requests.get(f'https://substack.com/api/v1/user/profile/self', headers=H)
p = r.json()
pub = next(pu for pu in p['publicationUsers'] if pu['publication']['subdomain'] == SUB)
print(f'Auth: {p["handle"]}')

# ── Query top 25 with partners ──
db = sqlite3.connect(str(DB))
c = db.cursor()

c.execute("""
    SELECT rowid, name, city, state, flood_risk_score, faith, latitude, longitude
    FROM churches WHERE country='US' AND latitude BETWEEN 37.0 AND 39.0 
    AND longitude BETWEEN -86.0 AND -84.5 AND flood_risk_score >= 0.9
    ORDER BY flood_risk_score DESC, name LIMIT 25
""")
at_risk = []
for r in c.fetchall():
    at_risk.append({'rowid': r[0], 'name': r[1], 'city': r[2], 'state': r[3],
                    'risk': r[4], 'faith': r[5], 'lat': r[6], 'lon': r[7]})

def hdist(lat1, lon1, lat2, lon2):
    dlat = math.radians(lat2 - lat1); dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    return 2 * 6371 * math.asin(min(1, math.sqrt(a)))

c.execute("""
    SELECT rowid, name, latitude, longitude FROM churches 
    WHERE country='US' AND latitude BETWEEN 37.0 AND 39.0 
    AND longitude BETWEEN -86.0 AND -84.5 AND flood_risk_score = 0.5
    AND landmark_type NOT IN ('school','office','hospital','cemetery','foundation','rectory','community_center','other')
""")
hubs = [{'rowid': r[0], 'name': r[1], 'lat': r[2], 'lon': r[3]} for r in c.fetchall()]

for ar in at_risk:
    best = min(((h, hdist(ar['lat'], ar['lon'], h['lat'], h['lon'])) for h in hubs),
               key=lambda x: x[1])
    ar['partner'] = best[0]['name']
    ar['partner_dist'] = round(best[1], 1)

db.close()

# ── Generate numbered HTML map ──
min_lat = min(ar['lat'] for ar in at_risk)
max_lat = max(ar['lat'] for ar in at_risk)
min_lon = min(ar['lon'] for ar in at_risk)
max_lon = max(ar['lon'] for ar in at_risk)
center_lat = (min_lat + max_lat) / 2
center_lon = (min_lon + max_lon) / 2

# Build JS for numbered markers
markers_js = []
hubs_js = []
spokes_js = []

for i, ar in enumerate(at_risk, 1):
    markers_js.append(f"""L.marker([{ar['lat']}, {ar['lon']}], {{icon: L.divIcon({{
    className: 'num-marker',
    html: '<div class=num>{i}</div>',
    iconSize: [28, 28],
    iconAnchor: [14, 14]
}})}}).addTo(map).bindPopup('<b>{i}. {ar["name"]}</b><br>{ar["city"]}, {ar["state"]}<br>Risk: {ar["risk"]}<br>Partner: {ar["partner"]} ({ar["partner_dist"]}km)');""")
    
    # Find hub for spoke
    best_hub = min(hubs, key=lambda h: hdist(ar['lat'], ar['lon'], h['lat'], h['lon']))
    spokes_js.append(f"""L.polyline([[{ar['lat']}, {ar['lon']}], [{best_hub['lat']}, {best_hub['lon']}]], {{
    color: '#e94560', weight: 1.5, opacity: 0.5, dashArray: '4,4'
}}).addTo(map);""")

# Add hub markers
for h in hubs[:30]:  # Show top 30 hubs
    hubs_js.append(f"""L.circleMarker([{h['lat']}, {h['lon']}], {{
    radius: 3, fillColor: '#28a745', color: '#1a7a2e', weight: 1, fillOpacity: 0.6
}}).addTo(map).bindPopup('{h["name"]}');""")

html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>KY Flood - Numbered Map</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#1a1a2e}}
#map{{height:100vh;width:100%}}
.num-marker{{background:0 0!important;border:none!important}}
.num{{
  width:28px;height:28px;border-radius:50%;background:#e94560;color:#fff;
  font-size:13px;font-weight:bold;display:flex;align-items:center;justify-content:center;
  border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4)
}}
.leaflet-popup-content-wrapper{{border-radius:6px;font-size:12px}}
.leaflet-popup-content{{margin:8px 12px}}
</style></head><body>
<div id=map></div>
<script>
var map = L.map('map').setView([{center_lat:.4f}, {center_lon:.4f}], 9);
var baseSatellite=L.tileLayer('{TILE_LAYERS["satellite"]["url"]}',{json.dumps(TILE_LAYERS["satellite"]["options"])});
var baseDark=L.tileLayer('{TILE_LAYERS["carto_dark"]["url"]}',{json.dumps(TILE_LAYERS["carto_dark"]["options"])});
baseSatellite.addTo(map);
var baseLayers={{"🛰 Satellite":baseSatellite,"🌙 Dark":baseDark}};
L.control.layers(baseLayers,null,{{position:'topright'}}).addTo(map);
{tile_error_fallback_js("osm")}

{chr(10).join(spokes_js)}

{chr(10).join(hubs_js)}

{chr(10).join(markers_js)}

// Fit bounds with padding
var pts = [];
{"pts.push([" + str([ar['lat'] for ar in at_risk])[1:-1] + "]);" if False else ""}
{"pts.push([" + str([ar['lon'] for ar in at_risk])[1:-1] + "]);" if False else ""}
</script></body></html>'''

# Actually let me build it properly
min_lat = min(ar['lat'] for ar in at_risk) - 0.1
max_lat = max(ar['lat'] for ar in at_risk) + 0.1
min_lon = min(ar['lon'] for ar in at_risk) - 0.1
max_lon = max(ar['lon'] for ar in at_risk) + 0.1

spokes = []
markers = []
hubs_markers = []

for i, ar in enumerate(at_risk, 1):
    best = min(hubs, key=lambda h: hdist(ar['lat'], ar['lon'], h['lat'], h['lon']))
    spokes.append(f'[[{ar["lat"]},{ar["lon"]}],[{best["lat"]},{best["lon"]}]]')
    markers.append(f'[{ar["lat"]},{ar["lon"]},"{i}","{ar["name"]}","{ar["city"]}","{ar["partner"]}",{ar["partner_dist"]}]')

for h in hubs[:50]:
    hubs_markers.append(f'[{h["lat"]},{h["lon"]}]')

html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>KY Flood Numbered Map</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#1a1a2e}}
#map{{height:100vh;width:100%}}
.num-marker{{background:0 0!important;border:none!important}}
.num{{width:26px;height:26px;border-radius:50%;background:#e94560;color:#fff;font-size:12px;font-weight:bold;display:flex;align-items:center;justify-content:center;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.5)}}
</style></head><body>
<div id=map></div>
<script>
var map = L.map('map').fitBounds([[{min_lat},{min_lon}],[{max_lat},{max_lon}]],{{padding:[50,50]}});
var baseSatellite=L.tileLayer('{TILE_LAYERS["satellite"]["url"]}',{json.dumps(TILE_LAYERS["satellite"]["options"])});
var baseDark=L.tileLayer('{TILE_LAYERS["carto_dark"]["url"]}',{json.dumps(TILE_LAYERS["carto_dark"]["options"])});
baseSatellite.addTo(map);
var baseLayers={{"🛰 Satellite":baseSatellite,"🌙 Dark":baseDark}};
L.control.layers(baseLayers,null,{{position:'topright'}}).addTo(map);
{tile_error_fallback_js("osm")}

// Hubs
var h = [{",".join(hubs_markers)}];
h.forEach(function(p){{L.circleMarker(p,{{radius:3,fillColor:'#28a745',color:'#1a7a2e',weight:1,fillOpacity:.6}}).addTo(map);}});

// Spokes
var s = [{",".join(spokes)}];
s.forEach(function(p){{L.polyline([p[0],p[1]],{{color:'#e94560',weight:1,opacity:.4,dashArray:'3,3'}}).addTo(map);}});

// Numbered markers
var m = [{",".join(markers)}];
m.forEach(function(p){{
  var num = p[2], name = p[3], city = p[4], partner = p[5], dist = p[6];
  L.marker([p[0],p[1]],{{icon:L.divIcon({{className:'num-marker',html:'<div class=num>'+num+'</div>',iconSize:[26,26],iconAnchor:[13,13]}})}})
   .addTo(map).bindPopup('<b>'+num+'. '+name+'</b><br>'+city+'<br>Partner: '+partner+' ('+dist+'km)');
}});
</script></body></html>'''

Path('E:/grid/docs/ky-numbered-map.html').write_text(html, encoding='utf-8')
print('✅ Map generated: docs/ky-numbered-map.html')

# ── Screenshot ──
png = Path('E:/grid/outputs/substack_maps/ky_numbered.png')
with sync_playwright() as pw:
    br = pw.chromium.launch()
    pg = br.new_page(viewport={'width': 1200, 'height': 800})
    pg.goto(f'file:///E:/grid/docs/ky-numbered-map.html')
    pg.wait_for_timeout(3000)
    pg.screenshot(path=str(png), full_page=False, clip={'x': 0, 'y': 0, 'width': 1200, 'height': 800})
    br.close()
print(f'Screenshot: {png}')

# ── Upload image ──
with open(str(png), 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
r = requests.post(f'https://{SUB}.substack.com/api/v1/image', headers=H,
                  json={'image': f'data:image/png;base64,{b64}'})
img = r.json()
print(f'Uploaded: {img["url"]}')

# ── Build Post with numbered table ──
# Build a simple ProseMirror doc: image + matching numbered table
table_rows = []
for i, ar in enumerate(at_risk, 1):
    table_rows.append(
        f'{i}. {ar["name"]} — {ar["city"]}, {ar["state"]} → {ar["partner"]} ({ar["partner_dist"]}km)'
    )

table_text = '\n'.join(table_rows)

pm_doc = {
    'type': 'doc',
    'content': [
        {'type': 'heading', 'attrs': {'level': 1}, 'content': [{'type': 'text', 'text': 'Kentucky Ohio River — 25 Most At-Risk Churches'}]},
        {'type': 'paragraph', 'attrs': {'textAlign': None}, 'content': [{'type': 'text', 'text': 'Ohio River flooding + Bullitt County dam failure. Numbered markers on the map match the list below.'}]},
        {'type': 'captionedImage', 'content': [{'type': 'image2', 'attrs': {
            'src': img['url'], 'srcNoWatermark': None, 'fullscreen': None, 'imageSize': None,
            'width': img.get('imageWidth', 1200), 'height': img.get('imageHeight', 800),
            'resizeWidth': None, 'bytes': img.get('bytes', 0),
            'alt': None, 'title': None, 'type': 'image/png',
            'href': None, 'belowTheFold': False, 'topImage': False, 'internalRedirect': None}}]},
        {'type': 'heading', 'attrs': {'level': 2}, 'content': [{'type': 'text', 'text': 'Matching Table'}]},
    ]
}

# Add each row as a paragraph
for i, ar in enumerate(at_risk, 1):
    line = f'{i}. {ar["name"]} — {ar["city"]}, {ar["state"]} | Risk: {ar["risk"]} | Partner: {ar["partner"]} ({ar["partner_dist"]}km)'
    pm_doc['content'].append({
        'type': 'paragraph', 'attrs': {'textAlign': None},
        'content': [{'type': 'text', 'text': line}]
    })

body = {
    'draft_title': 'KY Flood — 25 At-Risk Churches (Numbered Map)',
    'draft_body': json.dumps(pm_doc),
    'type': 'newsletter',
    'draft_bylines': [{'id': p['id'], 'publicationUserId': pub['id']}],
}
r = requests.post(f'https://{SUB}.substack.com/api/v1/drafts', headers=H, json=body)
did = r.json()['id']
print(f'✅ https://{SUB}.substack.com/publish/post/{did}')
