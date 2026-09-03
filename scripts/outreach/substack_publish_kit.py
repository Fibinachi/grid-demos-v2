"""
Substack Publishing Kit — Instructions
=======================================
Generated files are ready for Substack. Two options to publish:
"""

import json
from pathlib import Path

KITS = {
    "tx-hill-flood": {
        "title": "Texas Hill Country Flash Floods — GRID Flood Alert",
        "map": "docs/tx-hill-flood/tx-hill-flood-elev_map.html",
        "analysis": "docs/tx-hill-flood/tx-hill-flood-elev_analysis.md",
    },
    "ky-flood": {
        "title": "Kentucky Ohio River Flooding — GRID Flood Alert",
        "map": "docs/flood_alert_ky.html",
        "analysis": None,
    },
    "tx-flood-risk": {
        "title": "Texas Hill Country — Risk-Based Analysis",
        "map": "docs/flood_alert_tx_hill.html",
        "analysis": None,
    },
}

for slug, kit in KITS.items():
    print(f"\n{'='*60}")
    print(f"  {kit['title']}")
    print(f"{'='*60}")
    
    map_path = Path(kit['map'])
    if map_path.exists():
        map_size = map_path.stat().st_size / 1024
        print(f"\n  📍 Map: {kit['map']} ({map_size:.0f} KB)")
        print(f"\n  To embed in Substack:")
        print(f"  1. Open Substack editor")
        print(f"  2. Click </> (Embed) button")
        print(f"  3. Paste this HTML:")
        print(f"\n     <iframe src=\"YOUR_HOSTED_URL/{map_path.name}\" width=\"100%\" height=\"650px\"></iframe>")
        print(f"\n  4. Or open {map_path} in browser, copy all HTML, paste into Substack Code Block")
    
    analysis_path = Path(kit['analysis']) if kit['analysis'] else None
    if analysis_path and analysis_path.exists():
        md = analysis_path.read_text(encoding='utf-8')
        print(f"\n  📄 Analysis: {kit['analysis']} ({len(md)/1024:.0f} KB)")
        print(f"\n  To publish:")
        print(f"  1. Open Substack editor")
        print(f"  2. Paste the markdown content")
        print(f"  3. Substack will render headers, tables, lists")
    elif not analysis_path:
        print(f"\n  📄 Analysis: not generated for this kit")
    
    print(f"\n  📧 To email as draft:")
    print(f"     Substack supports \"post via email\" — email the map embed +")
    print(f"     analysis text to your Substack's private email address.")

print(f"\n{'='*60}")
print(f"  Files ready at:")
print(f"    docs/tx-hill-flood/tx-hill-flood-elev_map.html")
print(f"    docs/tx-hill-flood/tx-hill-flood-elev_analysis.md")
print(f"    docs/flood_alert_ky.html")
print(f"    docs/flood_alert_tx_hill.html")
print(f"{'='*60}")
