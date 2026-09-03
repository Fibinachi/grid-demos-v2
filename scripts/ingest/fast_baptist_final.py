#!/usr/bin/env python3
"""
WPA Baptist Inventory - Fast Final Processing.
Skip slow Nominatim, use existing GRID city data and build relationships.
"""
import sqlite3, re
from pathlib import Path

WPA_DB = Path("E:/grid/wpa.db")
CHURCHES_DB = Path("E:/grid/churches.db")

def link_to_grid():
    """Link all Baptist churches to GRID by name+state+city."""
    wpa = sqlite3.connect(str(WPA_DB))
    grid = sqlite3.connect(str(CHURCHES_DB))
    
    wpa.row_factory = sqlite3.Row
    grid.row_factory = sqlite3.Row
    
    churches = wpa.execute("SELECT id, church_name, location, state FROM wpa_baptist_churches").fetchall()
    
    grid_churches = grid.execute("SELECT id, name, city, state FROM churches WHERE state IS NOT NULL").fetchall()
    
    state_index = {}
    for c in grid_churches:
        state = c['state'].upper()
        state_index.setdefault(state, []).append(c)
    
    print(f"Linking {len(churches)} Baptist churches to GRID...")
    
    wpa.execute("DELETE FROM wpa_baptist_grid_links")
    
    matches = 0
    for ch in churches:
        wpa_id = ch['id']
        name = (ch['church_name'] or '').lower()
        location = (ch['location'] or '').lower()
        state = (ch['state'] or '').upper()
        
        if not state or state not in state_index:
            continue
        
        best_match = None
        best_score = 0
        
        for grid_ch in state_index[state]:
            grid_name = grid_ch['name'].lower()
            grid_city = (grid_ch['city'] or '').lower()
            
            name_words = set(name.split())
            grid_words = set(grid_name.split())
            overlap = len(name_words & grid_words)
            score = overlap
            
            if location and grid_city and location in grid_city:
                score += 2
            
            if score > best_score and score >= 3:
                best_score = score
                best_match = grid_ch
        
        if best_match:
            wpa.execute("""
                INSERT INTO wpa_baptist_grid_links (wpa_id, grid_church_id, match_method, match_score, notes)
                VALUES (?, ?, 'name_city', ?, ?)
            """, (wpa_id, best_match['id'], best_score, f"Score: {best_score}"))
            matches += 1
    
    wpa.commit()
    print(f"Linked {matches} churches to GRID")
    wpa.close()
    grid.close()

def build_pastor_relationships():
    """Build pastor-to-church relationships."""
    wpa = sqlite3.connect(str(WPA_DB))
    wpa.row_factory = sqlite3.Row
    
    rows = wpa.execute("""
        SELECT church_name, raw_text, notes 
        FROM wpa_records 
        WHERE volume_id IN (38, 13, 14, 15, 21, 22, 24, 25, 35, 36, 42, 43, 44)
    """).fetchall()
    
    print(f"Extracting pastor relationships from {len(rows)} records...")
    
    wpa.execute("CREATE TABLE IF NOT EXISTS wpa_baptist_pastor_church (pastor_id INTEGER, church_id INTEGER, role TEXT, years TEXT)")
    wpa.execute("DELETE FROM wpa_baptist_pastor_church")
    
    relationships = []
    
    for row in rows:
        text = f"{row['church_name'] or ''} {row['raw_text'] or ''} {row['notes'] or ''}"
        
        for m in re.finditer(r'(?:Pastor|Rev\.?|Elder)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', text):
            pastor_name = m.group(1).strip()
            
            church_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Baptist\s+)?Church', text)
            if church_match:
                church_name = church_match.group(1).strip()
                relationships.append((pastor_name, church_name))
    
    for pastor, church in relationships:
        wpa.execute("""
            INSERT INTO wpa_baptist_pastor_church (pastor_id, church_id, role)
            SELECT p.id, c.id, 'pastor'
            FROM wpa_baptist_pastors p, wpa_baptist_churches c
            WHERE p.pastor_name = ? AND c.church_name LIKE ?
            LIMIT 1
        """, (pastor, f"%{church}%"))
    
    wpa.commit()
    c = wpa.execute("SELECT COUNT(*) FROM wpa_baptist_pastor_church").fetchone()[0]
    print(f"Built {c} pastor-church relationships")
    wpa.close()

def build_association_relationships():
    """Build association-to-church relationships."""
    wpa = sqlite3.connect(str(WPA_DB))
    wpa.row_factory = sqlite3.Row
    
    rows = wpa.execute("SELECT church_name, raw_text, notes FROM wpa_records WHERE volume_id IN (38, 13, 14, 15, 21, 22, 24, 25, 35, 36, 42, 43, 44)").fetchall()
    
    print(f"Extracting association relationships from {len(rows)} records...")
    
    wpa.execute("CREATE TABLE IF NOT EXISTS wpa_baptist_church_association (church_id INTEGER, association_id INTEGER)")
    wpa.execute("DELETE FROM wpa_baptist_church_association")
    
    relationships = []
    
    for row in rows:
        text = f"{row['church_name'] or ''} {row['raw_text'] or ''} {row['notes'] or ''}"
        
        for m in re.finditer(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Association', text):
            assoc_name = m.group(1).strip() + " Association"
            
            church_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Baptist\s+)?Church', text)
            if church_match:
                church_name = church_match.group(1).strip()
                relationships.append((church_name, assoc_name))
    
    for church, assoc in relationships:
        wpa.execute("""
            INSERT INTO wpa_baptist_church_association (church_id, association_id)
            SELECT c.id, a.id
            FROM wpa_baptist_churches c, wpa_baptist_associations a
            WHERE c.church_name LIKE ? AND a.association_name = ?
            LIMIT 1
        """, (f"%{church}%", assoc))
    
    wpa.commit()
    c = wpa.execute("SELECT COUNT(*) FROM wpa_baptist_church_association").fetchone()[0]
    print(f"Built {c} church-association relationships")
    wpa.close()

def create_unified_table():
    """Create final unified table."""
    wpa = sqlite3.connect(str(WPA_DB))
    
    print("Creating unified table...")
    
    wpa.execute("DROP TABLE IF EXISTS wpa_baptist_unified")
    wpa.execute("""
        CREATE TABLE wpa_baptist_unified AS
        SELECT 
            c.id,
            c.church_name,
            c.dates,
            c.founding_year,
            c.closing_year,
            c.location,
            c.state,
            gl.grid_church_id,
            gl.match_score
        FROM wpa_baptist_churches c
        LEFT JOIN wpa_baptist_grid_links gl ON c.id = gl.wpa_id
    """)
    
    wpa.commit()
    
    c = wpa.execute("SELECT COUNT(*) FROM wpa_baptist_unified").fetchone()[0]
    linked = wpa.execute("SELECT COUNT(*) FROM wpa_baptist_unified WHERE grid_church_id IS NOT NULL").fetchone()[0]
    
    print(f"Unified: {c} churches, {linked} linked to GRID")
    wpa.close()

if __name__ == "__main__":
    link_to_grid()
    build_pastor_relationships()
    build_association_relationships()
    create_unified_table()
    print("\nDone.")