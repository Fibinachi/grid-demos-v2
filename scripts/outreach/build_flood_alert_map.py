#!/usr/bin/env python3
"""
build_flood_alert_map.py — Flood Alert Map Generator for Substack
==================================================================
Hub-and-spoke model: identifies at-risk churches within a flood-affected
bounding box and pairs each with a low-risk partner church (hub) of the
same denomination for aid coordination.

Generates a self-contained Leaflet HTML map embeddable in Substack.

Usage:
    python scripts/outreach/build_flood_alert_map.py \\
        --bbox "37.0,-86.0,39.0,-84.5" \\
        --event "Kentucky Ohio River Flooding" \\
        --desc "Ohio River flooding, Bullitt Co dam failure" \\
        --output docs/flood_alert_ky.html

    python scripts/outreach/build_flood_alert_map.py \\
        --bbox "29.8,-99.5,30.6,-98.5" \\
        --event "Texas Hill Country Flash Floods" \\
        --desc "Guadalupe River, Kerr County, July 4-6 2026" \\
        --output docs/flood_alert_tx_hill.html
"""

import sys, os, json, sqlite3, math, argparse
from pathlib import Path
from datetime import datetime
from scripts.visualization.map_utils import TILE_LAYERS, tile_error_fallback_js

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / 'churches.db'

RISK_HIGH = 0.7      # At-risk threshold
RISK_LOW_MAX = 0.5   # Hub max risk
MAX_PARTNER_KM = 50  # Max hub-spoke distance


def haversine_km(lat1, lon1, lat2, lon2):
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    return 2 * 6371 * math.asin(min(1, math.sqrt(a)))


def risk_label(s):
    if s is None: return 'Unknown'
    if s >= 0.9: return 'Critical'
    if s >= 0.7: return 'High'
    if s >= 0.5: return 'Moderate'
    if s >= 0.3: return 'Low'
    return 'Minimal'


def risk_color(s):
    if s is None: return '#6c757d'
    if s >= 0.9: return '#dc3545'
    if s >= 0.7: return '#fd7e14'
    if s >= 0.5: return '#ffc107'
    if s >= 0.3: return '#20c997'
    return '#28a745'


def fetch_in_bbox(db, min_lat, min_lon, max_lat, max_lon):
    """Fetch all churches with GPS in a bounding box, split by flood risk."""
    c = db.cursor()
    rows = c.execute("""
        SELECT rowid, name, city, county, state,
               latitude, longitude, flood_risk_score,
               taxonomy_id
        FROM churches
        WHERE latitude BETWEEN ? AND ?
          AND longitude BETWEEN ? AND ?
    """, (min_lat, max_lat, min_lon, max_lon)).fetchall()

    at_risk = []
    hubs = []
    for r in rows:
        risk = r[7]
        if risk is not None and risk >= RISK_HIGH:
            at_risk.append(r)
        elif risk is None or risk <= RISK_LOW_MAX:
            hubs.append(r)
    return at_risk, hubs


def get_taxonomy(db, tid):
    if tid is None: return 'Unknown'
    r = db.execute("SELECT name FROM taxonomy WHERE id=?", (tid,)).fetchone()
    return r[0] if r else 'Unknown'


def match_hubs(at_risk, hubs, db):
    """Hub-and-spoke matching."""
    tax_cache = {}
    def tax(tid):
        if tid not in tax_cache:
            tax_cache[tid] = get_taxonomy(db, tid)
        return tax_cache[tid]

    # Index hubs by taxonomy
    hubs_by_tax = {}
    for h in hubs:
        tid = h[8]
        hubs_by_tax.setdefault(tid, []).append(h)

    matched = []
    unmatched = []

    for church in at_risk:
        clat, clon = float(church[5]), float(church[6])
        tid = church[8]
        candidates = hubs_by_tax.get(tid, [])
        if not candidates:
            candidates = hubs  # fallback to any hub
        best_dist = float('inf')
        best_hub = None
        for hub in candidates:
            d = haversine_km(clat, clon, float(hub[5]), float(hub[6]))
            if d < best_dist and d <= MAX_PARTNER_KM:
                best_dist = d
                best_hub = hub
        if best_hub:
            matched.append((church, best_hub, round(best_dist, 1)))
        else:
            unmatched.append(church)
    return matched, unmatched, tax


def generate_html(matched, unmatched, tax, bbox, event_name, event_desc, output_path):
    """Generate self-contained Leaflet HTML."""
    min_lat, min_lon, max_lat, max_lon = bbox
    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2

    # Build GeoJSON
    at_risk_geojson = []
    hub_geojson = []
    spoke_geojson = []

    for church, hub, dist in matched:
        at_risk_geojson.append({
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [float(church[6]), float(church[5])]},
            'properties': {
                'type': 'at-risk',
                'name': church[1] or 'Unknown',
                'city': church[2] or '', 'county': church[3] or '',
                'risk': round(church[7], 2) if church[7] else 0,
                'denom': tax(church[8]),
                'partner': hub[1] or 'Unknown', 'dist_km': dist,
            }})
        hub_geojson.append({
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [float(hub[6]), float(hub[5])]},
            'properties': {
                'type': 'hub', 'name': hub[1] or 'Unknown',
                'city': hub[2] or '', 'county': hub[3] or '',
                'risk': round(hub[7], 2) if hub[7] else 0,
                'denom': tax(hub[8]),
            }})
        spoke_geojson.append({
            'type': 'Feature',
            'geometry': {'type': 'LineString', 'coordinates': [
                [float(church[6]), float(church[5])],
                [float(hub[6]), float(hub[5])]]},
            'properties': {'dist': dist}})

    for church in unmatched:
        at_risk_geojson.append({
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [float(church[6]), float(church[5])]},
            'properties': {
                'type': 'unmatched', 'name': church[1] or 'Unknown',
                'city': church[2] or '', 'county': church[3] or '',
                'risk': round(church[7], 2) if church[7] else 0,
                'denom': tax(church[8]),
                'partner': 'NONE', 'dist_km': 0,
            }})

    data = json.dumps({
        'at_risk': at_risk_geojson,
        'hubs': hub_geojson,
        'spokes': spoke_geojson,
    })

    hub_count = len(set(h[1] for h, _, _ in matched))
    now = datetime.now().strftime('%B %d, %Y')

    # Pre-compute tile options for JS embedding
    esri_labels_opts = {k: v for k, v in TILE_LAYERS["esri_labels"]["options"].items() if k != "is_overlay"}

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GRID Flood Alert — {event_name}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#f5f5f5; }}
#hd {{ background:#1a1a2e; color:white; padding:18px 24px; }}
#hd h1 {{ font-size:22px; margin-bottom:3px; }}
#hd .sub {{ color:#aaa; font-size:13px; }}
#hd .ev {{ color:#e94560; font-weight:bold; }}
#map {{ height:520px; }}
#bar {{ padding:12px 24px; background:white; border-bottom:1px solid #ddd; display:flex; gap:24px; font-size:13px; }}
#bar .n {{ font-size:22px; font-weight:bold; color:#1a1a2e; }}
#bar .l {{ color:#666; font-size:11px; text-transform:uppercase; }}
#leg {{ padding:10px 24px; background:white; font-size:12px; display:flex; gap:16px; flex-wrap:wrap; border-bottom:1px solid #eee; }}
#leg .i {{ display:flex; align-items:center; gap:5px; }}
#leg .dot {{ width:13px; height:13px; border-radius:50%; display:inline-block; }}
#leg .ln {{ width:26px; height:3px; display:inline-block; }}
#ft {{ padding:12px 24px; color:#888; font-size:11px; text-align:center; }}
.tbl {{ width:100%; font-size:12px; }}
.tbl td {{ padding:2px 5px; }}
.tbl td:first-child {{ font-weight:600; color:#555; width:80px; }}
</style>
</head>
<body>
<div id="hd">
<h1>🌊 GRID Flood Alert — <span class="ev">{event_name}</span></h1>
<div class="sub">{event_desc} | Generated {now}</div>
</div>
<div id="bar">
<div><div class="n">{len(matched)+len(unmatched)}</div><div class="l">At-Risk Churches</div></div>
<div><div class="n">{hub_count}</div><div class="l">Partner Hubs</div></div>
<div><div class="n">{len(unmatched)}</div><div class="l">Unmatched</div></div>
</div>
<div id="leg">
<div class="i"><span class="dot" style="background:#dc3545;"></span> Critical (≥0.9)</div>
<div class="i"><span class="dot" style="background:#fd7e14;"></span> High (0.7-0.9)</div>
<div class="i"><span class="dot" style="background:#28a745;border:2px solid #1a7a2e;"></span> Partner Hub</div>
<div class="i"><span class="ln" style="background:#6c757d;"></span> Connection</div>
<div class="i"><span class="dot" style="background:#6c757d;"></span> Unmatched</div>
</div>
<div id="map"></div>
<script>
const D = {data};
const map = L.map('map').setView([{center_lat:.4f}, {center_lon:.4f}], 10);

// ── Satellite default + dark/street alternates ──────────────────────
var baseSatellite = L.tileLayer('{TILE_LAYERS["satellite"]["url"]}', {json.dumps(TILE_LAYERS["satellite"]["options"])});
var baseDark = L.tileLayer('{TILE_LAYERS["carto_dark"]["url"]}', {json.dumps(TILE_LAYERS["carto_dark"]["options"])});
var esriLabels = L.tileLayer('{TILE_LAYERS["esri_labels"]["url"]}', {json.dumps(esri_labels_opts)});
baseSatellite.addTo(map);
esriLabels.addTo(map);
var baseLayers = {{"🛰 Satellite": baseSatellite, "🌙 Dark": baseDark}};
var labelOverlay = {{"🏷 Labels": esriLabels}};
L.control.layers(baseLayers, labelOverlay, {{position: 'topright'}}).addTo(map);
{tile_error_fallback_js("osm")}

function popup(p,isHub){{
let h=p.isHub?'⭐ ':'';
let r=p.risk||0;
let c=r>=0.9?'#dc3545':'#fd7e14';
let pi=p.partner&&p.partner!='NONE'
?'<tr><td>Partner</td><td>'+p.partner+' ('+p.dist_km+' km)</td></tr>'
:'<tr><td>Partner</td><td style="color:#dc3545;">NEEDS ASSIGNMENT</td></tr>';
return '<table class=tbl><tr><td>Name</td><td><b>'+h+p.name+'</b></td></tr>'
+'<tr><td>Location</td><td>'+(p.city||'')+', '+(p.county||'')+'</td></tr>'
+'<tr><td>Risk</td><td><b style=color:'+c+'>'+p.risk_label+' ('+r+')</b></td></tr>'
+'<tr><td>Denom</td><td>'+p.denom+'</td></tr>'
+(!p.isHub?pi:'')+'</table>';
}}

L.geoJSON({{type:'FeatureCollection',features:D.at_risk}},{{
pointToLayer:function(f,l){{
let c=f.properties.type=='unmatched'?'#6c757d':(f.properties.risk>=0.9?'#dc3545':'#fd7e14');
return L.circleMarker(l,{{radius:8,fillColor:c,color:'#fff',weight:2,fillOpacity:0.85}});
}},
onEachFeature:function(f,l){{
let p=f.properties; p.risk_label=((p.risk||0)>=0.9?'Critical':'High');
l.bindPopup(popup(p,false));
}}
}}).addTo(map);

L.geoJSON({{type:'FeatureCollection',features:D.hubs}},{{
pointToLayer:function(f,l){{
return L.circleMarker(l,{{radius:11,fillColor:'#28a745',color:'#1a7a2e',weight:3,fillOpacity:0.8}});
}},
onEachFeature:function(f,l){{
let p=f.properties; p.isHub=true;
l.bindPopup(popup(p,true));
}}
}}).addTo(map);

L.geoJSON({{type:'FeatureCollection',features:D.spokes}},{{
style:{{color:'#6c757d',weight:1.5,opacity:0.4,dashArray:'6,6'}}
}}).addTo(map);

let all=[];
D.at_risk.forEach(f=>all.push([f.geometry.coordinates[1],f.geometry.coordinates[0]]));
D.hubs.forEach(f=>all.push([f.geometry.coordinates[1],f.geometry.coordinates[0]]));
if(all.length) map.fitBounds(all,{{padding:[40,40]}});
</script>
<div id="ft">
<p>Data: GRID (Global Religious Infrastructure Database) • Flood Risk: FEMA NFHL + Global Model • Generated {now}</p>
<p>Contact: charlesaprescott@outlook.com</p>
</div>
</body>
</html>'''

    Path(output_path).write_text(html, encoding='utf-8')
    print(f'Written: {output_path} ({(Path(output_path).stat().st_size)/1024:.0f} KB)')
    print(f'  At-risk: {len(matched)+len(unmatched)} ({len(matched)} matched, {len(unmatched)} unmatched)')
    print(f'  Hubs: {hub_count}')


def main():
    p = argparse.ArgumentParser(description='Generate GRID Flood Alert Map')
    p.add_argument('--bbox', required=True,
                   help='Bounding box: min_lat,min_lon,max_lat,max_lon')
    p.add_argument('--event', required=True, help='Event name')
    p.add_argument('--desc', default='', help='Event description')
    p.add_argument('--output', required=True, help='Output HTML path')
    p.add_argument('--risk', type=float, default=0.7, help='Risk threshold (default 0.7)')
    p.add_argument('--max-dist', type=float, default=50, help='Max hub distance km (default 50)')
    args = p.parse_args()

    global RISK_HIGH, MAX_PARTNER_KM
    RISK_HIGH = args.risk
    MAX_PARTNER_KM = args.max_dist

    parts = [float(x) for x in args.bbox.replace(',', ' ').split()]
    if len(parts) != 4:
        print('Error: bbox must be min_lat min_lon max_lat max_lon')
        sys.exit(1)
    min_lat, min_lon, max_lat, max_lon = parts

    db = sqlite3.connect(str(DB_PATH))
    print(f'Querying bbox: {min_lat},{min_lon} to {max_lat},{max_lon}')
    at_risk, hubs = fetch_in_bbox(db, min_lat, min_lon, max_lat, max_lon)
    print(f'  At-risk: {len(at_risk):,}   Potential hubs: {len(hubs):,}')

    if not at_risk:
        print('No at-risk churches found. Try lowering --risk threshold.')
        db.close()
        return

    matched, unmatched, tax = match_hubs(at_risk, hubs, db)
    print(f'  Matched: {len(matched):,}   Unmatched: {len(unmatched):,}')

    generate_html(matched, unmatched, tax, parts,
                  args.event, args.desc, args.output)

    if matched:
        pair_counts = {}
        for _, hub, _ in matched:
            n = hub[1] or 'Unknown'
            pair_counts[n] = pair_counts.get(n, 0) + 1
        print(f'\nTop hubs:')
        for name, cnt in sorted(pair_counts.items(), key=lambda x: -x[1])[:10]:
            print(f'  {name}: {cnt} churches')

    db.close()


if __name__ == '__main__':
    main()
