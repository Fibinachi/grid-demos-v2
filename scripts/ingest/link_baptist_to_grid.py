#!/usr/bin/env python3
"""Link Baptist entries to GRID churches."""
import re, sqlite3
from pathlib import Path

DB_PATH = Path("E:/grid/wpa.db")
CHURCHES_DB = Path("E:/grid/churches.db")

wpa = sqlite3.connect(str(DB_PATH))
grid = sqlite3.connect(str(CHURCHES_DB))

# Get grid churches with valid state
grid_churches = [c for c in grid.execute(
    "SELECT id, name, city, state, latitude, longitude FROM churches WHERE faith='Christian' AND tradition LIKE '%Baptist%' AND state IS NOT NULL LIMIT 50000"
).fetchall() if c[3]]

print(f"GRID Baptist churches with state: {len(grid_churches)}")

tables = [
    ('wpa_baptist_ri', 'RI'),
    ('wpa_baptist_nc_yancey', 'NC'), ('wpa_baptist_nc_brunswick', 'NC'),
    ('wpa_baptist_nc_central', 'NC'), ('wpa_baptist_nc_flatriver', 'NC'),
    ('wpa_baptist_nc_stanly', 'NC'), ('wpa_baptist_nc_alleghany', 'NC'),
    ('wpa_baptist_nc_state', 'NC'),
    ('wpa_baptist_nj_baptist', 'NJ'),
    ('wpa_baptist_ms_baptist', 'MS'),
    ('wpa_baptist_va_baptist_3', 'VA'),
]

wpa.execute("DELETE FROM wpa_baptist_grid_links")
matches = 0

for tbl, state in tables:
    rows = wpa.execute(f"SELECT id, church_name, location, founding_year FROM {tbl}").fetchall()
    
    for wpa_row in rows:
        wpa_id = wpa_row[0]
        name = (wpa_row[1] or '').strip().lower()
        location = wpa_row[2] or ''
        year = wpa_row[3]
        
        if not name or len(name) < 5:
            continue
        
        best_match = None
        best_score = 0
        
        for c in grid_churches:
            if c[3].lower() != state.lower():
                continue
            
            wpa_words = set(name.replace('-', ' ').split()[:3])
            grid_words = set(c[1].lower().replace('-', ' ').split()[:3])
            overlap = len(wpa_words & grid_words)
            
            if overlap >= 2 or name[:20] in c[1].lower():
                if overlap > best_score:
                    best_match = c
                    best_score = overlap
        
        if best_match:
            matches += 1
            wpa.execute("INSERT INTO wpa_baptist_grid_links (wpa_id, grid_church_id, match_method, match_score, notes) VALUES (?,?,?,?,?)",
                (wpa_id, best_match[0], 'name_overlap', float(best_score), f"Matched to {best_match[1]}"))

wpa.commit()
print(f"Matched {matches} entries to GRID churches")

grid.close()
wpa.close()