#!/usr/bin/env python3
"""
WPA Baptist Inventory Parser - DeepSeek Edition.

Parses Baptist archival inventory format (narrative, run-together entries).
Creates tables for churches, associations, and potential pastor links.

Format: "73 First Baptist Church, 1805--, Pawtucket . . . 74..."
"""
import os, re, json, time, requests, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
CHUNK_SIZE = 12000

# Baptist inventory volumes
INVENTORIES = {
    "RI": "inventoryofchurc00unse_0.txt",  # Rhode Island
}

PROMPT = """Extract ALL Baptist church entries from this 1941 WPA archival inventory.

Format: run-together numbered entries like:
"73 First Baptist Church, 1805--, Pawtucket . . . 74 First Baptist Church, 1805--, Crompton, West Warwick . 75..."

For EACH entry extract JSON:
{
  "entry_number": "73",
  "church_name": "full canonical name",
  "dates": "year range like 1805-- or 1700-1873",
  "location": "town/city name",
  "pastor_names": ["any person names in clergy context"],
  "archival_notes": "what records exist (minutes, membership)",
  "association": "parent association if mentioned"
}

OCR corrections: 3aptist=Baptist, Glocester=Gloucester, Frovidence=Providence, -=hyphen

Skip: TOC, page headers, narrative sections. Return ONLY valid JSON array."""

def call_deepseek(text):
    try:
        r = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            json={'model': 'deepseek-chat', 'messages': [
                {'role': 'system', 'content': PROMPT},
                {'role': 'user', 'content': text}
            ], 'temperature': 0.05, 'max_tokens': 8000},
            headers={'Authorization': f'Bearer {DEEPSEEK_KEY}', 'Content-Type': 'application/json'},
            timeout=120)
        if r.status_code != 200:
            return None
        c = r.json()['choices'][0]['message']['content'].strip()
        c = re.sub(r'^```json?\s*\n?', '', c)
        c = re.sub(r'\n?```\s*$', '', c)
        s = c.find('[')
        if s < 0:
            return None
        return json.loads(c[s:])
    except Exception as e:
        print(f"  Err: {e}")
        return None

def load_clean_text(filepath):
    text = filepath.read_text(encoding='utf-8', errors='replace')
    clean = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL|re.IGNORECASE)
    clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL|re.IGNORECASE)
    clean = re.sub(r'<[^>]+>', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

if __name__ == "__main__":
    if not DEEPSEEK_KEY:
        print("Set DEEPSEEK_API_KEY")
        exit(1)
    
    for state, fname in INVENTORIES.items():
        print(f"\n{'='*50}")
        print(f"Parsing {state}: {fname}")
        
        text = load_clean_text(WPA_DIR / fname)
        
        # Find inventory section start (first numbered entry)
        idx = text.find("73 First Baptist Church")
        if idx < 0:
            idx = text.find("First Baptist Church")
        if idx < 0:
            print("Could not find inventory section")
            continue
        
        content = text[idx:]
        
        # Chunk
        chunks = [content[i:i+CHUNK_SIZE] for i in range(0, min(len(content), 200000), CHUNK_SIZE-500)]
        
        print(f"{len(chunks)} chunks to process")
        
        all_entries = []
        for i, chunk in enumerate(chunks[:10]):  # Limit 10 chunks for test
            print(f"  [{i+1}/{len(chunks)}] Processing {len(chunk)} chars...")
            result = call_deepseek(chunk)
            if result:
                all_entries.extend(result)
                print(f"    Got {len(result)} entries")
            time.sleep(0.3)
        
        if not all_entries:
            print("No entries extracted - check format")
            continue
        
        # Save to DB
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(f"""CREATE TABLE IF NOT EXISTS wpa_baptist_{state.lower()} (
            id INTEGER PRIMARY KEY,
            entry_number INTEGER,
            church_name TEXT,
            dates TEXT,
            location TEXT,
            founding_year INTEGER,
            closing_year INTEGER,
            pastor_names TEXT,
            archival_notes TEXT,
            association TEXT
        )""")
        conn.execute(f"DELETE FROM wpa_baptist_{state.lower()}")
        
        for e in all_entries:
            years = re.findall(r'(\d{4})', e.get('dates', '') or '')
            founding = int(years[0]) if years else None
            closing = int(years[-1]) if len(years) > 1 else None
            
            conn.execute(f"""INSERT INTO wpa_baptist_{state.lower()} 
                (entry_number, church_name, dates, location, founding_year, closing_year, 
                 pastor_names, archival_notes, association)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (e.get('entry_number'), e.get('church_name'), e.get('dates'), 
                 e.get('location'), founding, closing,
                 json.dumps(e.get('pastor_names', [])), e.get('archival_notes'), e.get('association')))
        conn.commit()
        
        print(f"Saved {len(all_entries)} to wpa_baptist_{state.lower()}")
        
        # Stats
        c = conn.execute(f"SELECT COUNT(*) FROM wpa_baptist_{state.lower()} WHERE founding_year IS NOT NULL")
        print(f"With founding years: {c.fetchone()[0]}")
        conn.close()