#!/usr/bin/env python3
"""
grind_response.py — One-shot GRID disaster response post generator
====================================================================
Takes a bounding box and event info, generates:
  1. Interactive flood alert Leaflet map (HTML for Substack embed)
  2. Analysis paper (Markdown for Substack)

Usage:
    python scripts/outreach/grind_response.py \
        --bbox "37.0,-86.0,39.0,-84.5" \
        --event "Kentucky Ohio River Flooding" \
        --slug "ky-flood-2026" \
        --desc "State of emergency after Ohio River flooding" \
        --output-dir "docs/ky-flood"
        
    # Elevation mode (requires elevation_m data):
    python scripts/outreach/grind_response.py \
        --bbox "29.5,-99.8,31.0,-97.5" \
        --event "Texas Hill Country Flash Floods" \
        --slug "tx-hill-flood" \
        --flood-level 450 \
        --desc "Guadalupe River crest at 450m" \
        --output-dir "docs/tx-hill-flood"
"""

import sys, os, json, sqlite3, math, argparse
from pathlib import Path
from datetime import datetime
from scripts.visualization.map_utils import TILE_LAYERS, tile_error_fallback_js

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / 'churches.db'
RISK_HIGH = 0.7
RISK_LOW_MAX = 0.5
MAX_PARTNER_KM = 50


def haversine_km(lat1, lon1, lat2, lon2):
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    return 2 * 6371 * math.asin(min(1, math.sqrt(a)))


RISK_HIGH = 0.7
RISK_LOW_MAX = 0.5
MAX_PARTNER_KM = 50
FLOOD_LEVEL = None  # elevation mode: meters above sea level


def fetch_in_bbox(db, min_lat, min_lon, max_lat, max_lon):
    """Fetch churches in bbox.
    
    Two modes:
      - Elevation mode (FLOOD_LEVEL set): risk = elevation below flood level
      - Risk-score mode (default): risk = flood_risk_score
    """
    c = db.cursor()
    rows = c.execute("""
        SELECT rowid, name, city, county, state, country,
               latitude, longitude, flood_risk_score,
               taxonomy_id, elevation_m
        FROM churches
        WHERE latitude BETWEEN ? AND ?
          AND longitude BETWEEN ? AND ?
          AND landmark_type NOT IN ('school','office','hospital','cemetery','foundation','rectory','community_center','other')
    """, (min_lat, max_lat, min_lon, max_lon)).fetchall()
    at_risk, hubs = [], []
    for r in rows:
        elev = r[10]
        if FLOOD_LEVEL is not None and elev is not None:
            if elev < FLOOD_LEVEL:
                at_risk.append(r)
            else:
                hubs.append(r)
        else:
            risk = r[8]
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
    tax_cache = {}
    def tax(tid):
        if tid not in tax_cache:
            tax_cache[tid] = get_taxonomy(db, tid)
        return tax_cache[tid]
    hubs_by_tax = {}
    for h in hubs:
        hubs_by_tax.setdefault(h[9], []).append(h)
    matched, unmatched = [], []
    for church in at_risk:
        clat, clon = float(church[6]), float(church[7])
        tid = church[9]
        candidates = hubs_by_tax.get(tid, hubs)
        best_dist, best_hub = float('inf'), None
        for hub in candidates:
            d = haversine_km(clat, clon, float(hub[6]), float(hub[7]))
            if d < best_dist and d <= MAX_PARTNER_KM:
                best_dist, best_hub = d, hub
        if best_hub:
            matched.append((church, best_hub, round(best_dist, 1)))
        else:
            unmatched.append(church)
    return matched, unmatched, tax


# ═══════════════════════════════════════════════════════════════════
def generate_map(matched, unmatched, tax, bbox, event, desc, output):
    """Generate interactive Leaflet map HTML."""
    min_lat, min_lon, max_lat, max_lon = bbox
    center_lat, center_lon = (min_lat+max_lat)/2, (min_lon+max_lon)/2

    a_js, h_js, s_js = [], [], []
    for church, hub, dist in matched:
        elev = church[10]
        a_js.append({'type':'Feature','geometry':{'type':'Point',
            'coordinates':[float(church[7]),float(church[6])]},
            'properties':{'type':'at-risk','name':church[1] or 'Unknown',
            'city':church[2] or '','county':church[3] or '',
            'risk':round(church[8],2)if church[8]else 0,
            'elev':round(elev,1)if elev else 0,
            'denom':tax(church[9]),'partner':hub[1]or'Unknown','dist_km':dist}})
        h_js.append({'type':'Feature','geometry':{'type':'Point',
            'coordinates':[float(hub[7]),float(hub[6])]},
            'properties':{'type':'hub','name':hub[1]or'Unknown',
            'city':hub[2]or'','county':hub[3]or'',
            'risk':round(hub[8],2)if hub[8]else 0,
            'elev':round(hub[10],1)if hub[10]else 0,
            'denom':tax(hub[9])}})
        s_js.append({'type':'Feature','geometry':{'type':'LineString',
            'coordinates':[[float(church[7]),float(church[6])],
                           [float(hub[7]),float(hub[6])]]},'properties':{'d':dist}})
    for church in unmatched:
        elev = church[10]
        a_js.append({'type':'Feature','geometry':{'type':'Point',
            'coordinates':[float(church[7]),float(church[6])]},
            'properties':{'type':'unmatched','name':church[1]or'Unknown',
            'city':church[2]or'','county':church[3]or'',
            'risk':round(church[8],2)if church[8]else 0,
            'elev':round(elev,1)if elev else 0,
            'denom':tax(church[9]),'partner':'NONE','dist_km':0}})

    data = json.dumps({'a':a_js,'h':h_js,'s':s_js})
    hub_count = len(set(h[1] for h,_,_ in matched))
    now = datetime.now().strftime('%B %d, %Y')
    # Pre-compute tile options for JS embedding
    esri_labels_opts = {k: v for k, v in TILE_LAYERS["esri_labels"]["options"].items() if k != "is_overlay"}
    html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>GRID Flood Alert — {event}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f5f5f5}}
#hd{{background:#1a1a2e;color:white;padding:18px 24px}}
#hd h1{{font-size:22px;margin-bottom:3px}}
#hd .sub{{color:#aaa;font-size:13px}}
#hd .ev{{color:#e94560;font-weight:bold}}
#map{{height:520px}}
#bar{{padding:12px 24px;background:white;border-bottom:1px solid #ddd;display:flex;gap:24px;font-size:13px}}
#bar .n{{font-size:22px;font-weight:bold;color:#1a1a2e}}
#bar .l{{color:#666;font-size:11px;text-transform:uppercase}}
#leg{{padding:10px 24px;background:white;font-size:12px;display:flex;gap:16px;flex-wrap:wrap;border-bottom:1px solid #eee}}
#leg .i{{display:flex;align-items:center;gap:5px}}
#leg .dot{{width:13px;height:13px;border-radius:50%;display:inline-block}}
#leg .ln{{width:26px;height:3px;display:inline-block}}
#ft{{padding:12px 24px;color:#888;font-size:11px;text-align:center}}
.tbl{{width:100%;font-size:12px}}
.tbl td{{padding:2px 5px}}
.tbl td:first-child{{font-weight:600;color:#555;width:80px}}
</style></head><body>
<div id=hd><h1>🌊 GRID Flood Alert — <span class=ev>{event}</span></h1>
<div class=sub>{desc} | Generated {now}</div></div>
<div id=bar>
<div><div class=n>{len(matched)+len(unmatched)}</div><div class=l>At-Risk Churches</div></div>
<div><div class=n>{hub_count}</div><div class=l>Partner Hubs</div></div>
<div><div class=n>{len(unmatched)}</div><div class=l>Unmatched</div></div></div>
<div id=leg>
<div class=i><span class=dot style=background:#dc3545></span> Critical (≥0.9)</div>
<div class=i><span class=dot style=background:#fd7e14></span> High (0.7-0.9)</div>
<div class=i><span class=dot style=background:#28a745;border:2px solid #1a7a2e></span> Partner Hub</div>
<div class=i><span class=ln style=background:#6c757d></span> Connection</div>
<div class=i><span class=dot style=background:#6c757d></span> Unmatched</div></div>
<div id=map></div>
<script>
const D={data};const map=L.map('map').setView([{center_lat:.4f},{center_lon:.4f}],10);

// Satellite default + dark alternate
var baseSatellite=L.tileLayer('{TILE_LAYERS["satellite"]["url"]}',{json.dumps(TILE_LAYERS["satellite"]["options"])});
var baseDark=L.tileLayer('{TILE_LAYERS["carto_dark"]["url"]}',{json.dumps(TILE_LAYERS["carto_dark"]["options"])});
var esriLabels=L.tileLayer('{TILE_LAYERS["esri_labels"]["url"]}',{json.dumps(esri_labels_opts)});
baseSatellite.addTo(map);esriLabels.addTo(map);
var baseLayers={{"🛰 Satellite":baseSatellite,"🌙 Dark":baseDark}};
var labelOverlay={{"🏷 Labels":esriLabels}};
L.control.layers(baseLayers,labelOverlay,{{position:'topright'}}).addTo(map);
{tile_error_fallback_js("osm")}
function popup(p,i){{
let h=i?'⭐ ':'',r=p.risk||0,e=p.elev||0,c=r>=.9?'#dc3545':'#fd7e14';
let ei=p.elev?'<tr><td>Elevation</td><td>'+p.elev+' m</td></tr>':'';
let pi=p.partner&&p.partner!='NONE'
?'<tr><td>Partner</td><td>'+p.partner+' ('+p.dist_km+' km)</td></tr>'
:'<tr><td>Partner</td><td style=color:#dc3545>NEEDS ASSIGNMENT</td></tr>';
return'<table class=tbl><tr><td>Name</td><td><b>'+h+p.name+'</b></td></tr>'
+'<tr><td>Location</td><td>'+(p.city||'')+', '+(p.county||'')+'</td></tr>'
+'<tr><td>Risk</td><td><b style=color:'+c+'>'+(r>=.9?'Critical':'High')+' ('+r+')</b></td></tr>'
+ei+'<tr><td>Denom</td><td>'+p.denom+'</td></tr>'+(!i?pi:'')+'</table>';}}
L.geoJSON({{type:'FeatureCollection',features:D.a}},{{
pointToLayer:function(f,l){{
let c=f.properties.type=='unmatched'?'#6c757d':(f.properties.risk>=.9?'#dc3545':'#fd7e14');
return L.circleMarker(l,{{radius:8,fillColor:c,color:'#fff',weight:2,fillOpacity:.85}});
}},onEachFeature:function(f,l){{l.bindPopup(popup(f.properties,false));}}}}).addTo(map);
L.geoJSON({{type:'FeatureCollection',features:D.h}},{{
pointToLayer:function(f,l){{
return L.circleMarker(l,{{radius:11,fillColor:'#28a745',color:'#1a7a2e',weight:3,fillOpacity:.8}});
}},onEachFeature:function(f,l){{l.bindPopup(popup(f.properties,true));}}}}).addTo(map);
L.geoJSON({{type:'FeatureCollection',features:D.s}},{{
style:{{color:'#6c757d',weight:1.5,opacity:.4,dashArray:'6,6'}}}}).addTo(map);
let p=[];D.a.forEach(f=>p.push([f.geometry.coordinates[1],f.geometry.coordinates[0]]));
D.h.forEach(f=>p.push([f.geometry.coordinates[1],f.geometry.coordinates[0]]));
if(p.length)map.fitBounds(p,{{padding:[40,40]}});
</script>
<div id=ft><p>Data: GRID (Global Religious Infrastructure Database) • Flood Risk: FEMA NFHL + Global Model • {now}</p>
<p>Contact: charlesaprescott@outlook.com | Generated by GRID</p></div></body></html>'''

    Path(output).write_text(html, encoding='utf-8')
    return hub_count, len(output)


# ═══════════════════════════════════════════════════════════════════
def generate_analysis(matched, unmatched, tax, bbox, event, desc, slug,
                      db, state_str, output):
    """Generate analysis paper markdown."""
    min_lat, min_lon, max_lat, max_lon = bbox
    now = datetime.now().strftime('%B %d, %Y')

    # Gather stats
    all_churches = matched + [(c, None, 0) for c in unmatched]
    total_at_risk = len(all_churches)
    total_matched = len(matched)
    total_unmatched = len(unmatched)
    hub_ids = set(h[0] for _, h, _ in matched)
    total_hubs = len(hub_ids)

    # Denomination breakdown
    tax_counts = {}
    for church, _, _ in all_churches:
        d = tax(church[9])
        tax_counts[d] = tax_counts.get(d, 0) + 1
    top_denoms = sorted(tax_counts.items(), key=lambda x: -x[1])[:10]

    # County breakdown
    county_counts = {}
    for church, _, _ in all_churches:
        co = church[3] or 'Unknown'
        county_counts[co] = county_counts.get(co, 0) + 1
    top_counties = sorted(county_counts.items(), key=lambda x: -x[1])[:15]

    # Flood risk distribution
    risk_buckets = {0: 0, 0.7: 0, 0.8: 0, 0.9: 0}
    for church, _, _ in all_churches:
        r = church[8]
        if r is None: risk_buckets[0] += 1
        elif r >= 0.9: risk_buckets[0.9] += 1
        elif r >= 0.8: risk_buckets[0.8] += 1
        elif r >= 0.7: risk_buckets[0.7] += 1

    total_in_bbox = db.execute("SELECT COUNT(*) FROM churches WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?", (min_lat, max_lat, min_lon, max_lon)).fetchone()[0]
    low_risk_count = total_in_bbox - total_at_risk - len(set(h[1] for _, h, _ in matched if h))
    pair_counts = {}
    for _, hub, _ in matched:
        n = hub[1] or 'Unknown'
        pair_counts[n] = pair_counts.get(n, 0) + 1
    top_hubs = sorted(pair_counts.items(), key=lambda x: -x[1])[:10]

    # Global flood model info
    global_risk = db.execute(
        "SELECT country_code, risk_score, risk_cat FROM flood_risk_global "
        "WHERE country_code='US'"
    ).fetchone()

    md = f'''# GRID Disaster Response Analysis
## {event}

**Generated:** {now}  **Bounding Box:** {min_lat},{min_lon} to {max_lat},{max_lon}
**Description:** {desc}

---

## Executive Summary

This report identifies **{total_at_risk} religious infrastructure facilities** at elevated flood risk within the {event} affected area. Using the GRID (Global Religious Infrastructure Database) flood risk model — calibrated against FEMA NFHL zones and global flood hazard data — we have mapped at-risk churches and paired each with a same-denomination, low-risk partner church for aid coordination.

| Metric | Count |
|--------|:-----:|
| Total churches in affected bbox | {total_in_bbox} |
| At-risk (flood_risk ≥ 0.7) | {total_at_risk} |
| Matched with partner hub | {total_matched} ({total_matched/total_at_risk*100:.0f}%) |
| Unmatched (no nearby same-denom hub) | {total_unmatched} |
| Partner hubs activated | {total_hubs} |

---

## Flood Risk Methodology

### Data Sources

| Source | Description | Coverage |
|--------|-------------|----------|
| **FEMA NFHL** | National Flood Hazard Layer — 100-year floodplains, regulatory floodways | US-wide |
| **FEMA NRI** | National Risk Index — tract-level composite risk scores | US-wide |
| **flood_county_risk** | County-level FEMA-derived risk proxy (0-1 scale) | All US counties |
| **flood_risk_global** | World Bank / Global flood hazard model (0-1 scale) | Global |

### How flood_risk_score is calculated

For US churches, flood risk is a composite of:
1. **FEMA NFHL zone** — whether the church falls inside a mapped Special Flood Hazard Area (SFHA), derived from the `nfhl_flood_zones` table ({db.execute("SELECT COUNT(*) FROM nfhl_flood_zones").fetchone()[0]:,} zones)
2. **FEMA NRI tract score** — the National Risk Index's flood component at the census tract level ({db.execute("SELECT COUNT(*) FROM fema_nri_tract").fetchone()[0]:,} tracts)
3. **County flood proxy** — where higher-resolution data is unavailable, county-level FEMA claims and flood insurance data

Score values:
- **≥ 0.9** — Critical (in mapped floodway/high-risk SFHA + high NRI)
- **≥ 0.7** — High (in SFHA or elevated NRI score)
- **≥ 0.5** — Moderate (proximate to flood zone or moderate NRI)
- **< 0.5** — Low/Minimal (outside mapped hazard areas)

For non-US churches, the `flood_risk_global` model uses World Bank flood hazard data. Country-level scores:

| Country | Global Risk Score | Category |
|---------|:-:|:--------:|
{'  | '.join([f'{r[0]}|{r[1]}|{r[2]}' for r in db.execute("SELECT country_code, risk_score, risk_cat FROM flood_risk_global WHERE risk_score IS NOT NULL ORDER BY risk_score DESC LIMIT 15").fetchall()]).replace('| ', '|\n| ') + ' |'}

The US global score: **{global_risk[1] if global_risk else 'N/A'}** ({global_risk[2] if global_risk else 'N/A'}) — refined by higher-resolution FEMA data.

---

## Affected Area Breakdown

### By County
| County | At-Risk Churches |
|--------|:-:|
{'| '.join([f'{c[0]}|{c[1]}' for c in top_counties]) + ' |'}

### By Denomination
| Denomination | At-Risk |
|--------------|:------:|
{'| '.join([f'{d[0]}|{d[1]}' for d in top_denoms]) + ' |'}

### Risk Score Distribution
| Bucket | Count |
|--------|:-----:|
| 0.7–0.79 (High) | {risk_buckets[0.7]} |
| 0.8–0.89 | {risk_buckets[0.8]} |
| 0.9+ (Critical) | {risk_buckets[0.9]} |
| Unknown | {risk_buckets[0]} |

---

## Hub Partner Assignments

Each at-risk church was algorithmically assigned to the nearest low-risk (flood_risk ≤ {RISK_LOW_MAX}) church of the **same denomination** within {MAX_PARTNER_KM} km. This hub-and-spoke model ensures:

1. **Same faith** — partners share denominational structures for aid coordination
2. **Close proximity** — hubs are within practical relief distance
3. **Low risk** — hubs are safe staging areas outside flood hazard zones

### Top Partner Hubs
| Hub Name | Spoke Churches |
|----------|:-------------:|
{'| '.join([f'{n}|{c}' for n, c in top_hubs]) + ' |'}

---

## Database Provenance

### Key Tables Used

| Table | Rows | Purpose |
|-------|:----:|---------|
| `churches` | {db.execute("SELECT COUNT(*) FROM churches").fetchone()[0]:,} | Master religious infrastructure registry |
| `church_flood` | {db.execute("SELECT COUNT(*) FROM church_flood").fetchone()[0]:,} | Church-NFHL zone intersections (US) |
| `nfhl_flood_zones` | {db.execute("SELECT COUNT(*) FROM nfhl_flood_zones").fetchone()[0]:,} | FEMA National Flood Hazard Layer zones |
| `fema_nri_tract` | {db.execute("SELECT COUNT(*) FROM fema_nri_tract").fetchone()[0]:,} | FEMA National Risk Index (tract-level) |
| `flood_risk_global` | {db.execute("SELECT COUNT(*) FROM flood_risk_global").fetchone()[0]:,} | Global flood hazard scores by country |
| `flood_county_risk` | {db.execute("SELECT COUNT(*) FROM flood_county_risk").fetchone()[0]:,} | County-level risk proxy |
| `taxonomy` | {db.execute("SELECT COUNT(*) FROM taxonomy").fetchone()[0]:,} | CFTLM taxonomy tree |

### Last Updated
- Flood risk scores: {db.execute("SELECT DISTINCT MAX(provenance_log.started_at) FROM provenance_log WHERE source='flood_risk'").fetchone()[0] or 'Multiple dates'}
- FEMA NFHL data: {db.execute("SELECT DISTINCT MAX(provenance_log.started_at) FROM provenance_log WHERE source='nfhl_import'").fetchone()[0] or 'Multiple dates'}

---

## Limitations & Caveats

1. **Risk scores are modeled estimates** — they indicate relative hazard, not guaranteed flooding
2. **Global model (non-US) is coarser** — country-level scores lack local floodplain resolution
3. **Phone contact data is limited** — only {db.execute("SELECT COUNT(*) FROM church_contact_values WHERE contact_type='phone'").fetchone()[0]:,} of 3.3M churches have phone numbers in the database
4. **Property tax valuations** are only available for select states (TN: {db.execute("SELECT COUNT(*) FROM churches WHERE tn_parcel_id IS NOT NULL").fetchone()[0]:,} parcels, FL staging: {db.execute("SELECT COUNT(*) FROM fl_parcels_staging").fetchone()[0]:,})
5. **Building square footage** is available for {db.execute("SELECT COUNT(*) FROM churches WHERE building_sqft IS NOT NULL").fetchone()[0]:,} churches and can be used for preliminary value estimation

---

## Reproducibility

This analysis is fully reproducible. The GRID database is SQLite3 and all scripts are open-source:

- **Map generation:** `scripts/outreach/grind_response.py`
- **Flood risk import:** `scripts/enrichment/import_flood_maps.py`
- **Database:** `churches.db` (SQLite3, ~14.4 GB)

Contact: **charlesaprescott@outlook.com**

---

*Generated by GRID (Global Religious Infrastructure Database) — tracking {db.execute("SELECT COUNT(*) FROM churches").fetchone()[0]:,} religious facilities across 247 countries.*
'''

    Path(output).write_text(md, encoding='utf-8')
    return len(md)


# ═══════════════════════════════════════════════════════════════════
def main():
    p = argparse.ArgumentParser(description='GRID Disaster Response Generator')
    p.add_argument('--bbox', required=True, help='min_lat,min_lon,max_lat,max_lon')
    p.add_argument('--event', required=True, help='Event name (e.g. "Kentucky Ohio River Flooding")')
    p.add_argument('--slug', required=True, help='URL slug (e.g. "ky-flood-2026")')
    p.add_argument('--desc', default='', help='Short event description')
    p.add_argument('--output-dir', default='docs', help='Output directory')
    p.add_argument('--risk', type=float, default=0.7)
    p.add_argument('--max-dist', type=float, default=50)
    p.add_argument('--flood-level', type=float, default=None,
                   help='Flood water level in meters above sea level. Uses elevation_m data.')
    args = p.parse_args()

    global RISK_HIGH, MAX_PARTNER_KM, FLOOD_LEVEL
    RISK_HIGH = args.risk
    MAX_PARTNER_KM = args.max_dist
    FLOOD_LEVEL = args.flood_level

    parts = [float(x) for x in args.bbox.replace(',', ' ').split()]
    if len(parts) != 4:
        print('Error: bbox must be 4 floats: min_lat min_lon max_lat max_lon')
        sys.exit(1)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    db = sqlite3.connect(str(DB_PATH))
    print(f'Querying bbox: {parts}')
    at_risk, hubs = fetch_in_bbox(db, *parts)
    print(f'  At-risk: {len(at_risk):,}   Hubs: {len(hubs):,}')

    if not at_risk:
        print('No at-risk churches. Try lowering --risk threshold.')
        # Still generate analysis showing zero findings
        matched, unmatched = [], at_risk
        tax_fn = lambda tid: get_taxonomy(db, tid)
    else:
        matched, unmatched, tax_fn = match_hubs(at_risk, hubs, db)
        print(f'  Matched: {len(matched):,}   Unmatched: {len(unmatched):,}')

    # Generate map
    map_path = out_dir / f'{args.slug}_map.html'
    hub_count, map_kb = generate_map(
        matched, unmatched, tax_fn, parts,
        args.event, args.desc, str(map_path))
    print(f'  Map: {map_path} ({map_kb} KB)')

    # Generate analysis
    analysis_path = out_dir / f'{args.slug}_analysis.md'
    md_len = generate_analysis(
        matched, unmatched, tax_fn, parts,
        args.event, args.desc, args.slug, db, args.bbox, str(analysis_path))
    print(f'  Analysis: {analysis_path} ({md_len/1024:.0f} KB)')

    print(f'\n===== PUBLISHING KIT READY =====')
    print(f'  Post 1 (Map):   {map_path}')
    print(f'  Post 2 (Analysis): {analysis_path}')
    print(f'\n  To embed the map in Substack:')
    print(f'    1. Open Substack post editor')
    print(f'    2. Paste <iframe src="YOUR_HOSTED_URL/{args.slug}_map.html" width="100%" height="650px"></iframe>')
    print(f'    3. Or paste the entire HTML content into a Code Block')

    db.close()


if __name__ == '__main__':
    main()
