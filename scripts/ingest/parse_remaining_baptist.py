#!/usr/bin/env python3
"""
WPA Baptist Inventory Parser - Remaining Volumes.
"""
import os, re, json, time, requests, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
CHUNK_SIZE = 12000

# Remaining Baptist inventory volumes
INVENTORIES = [
    ("nj_baptist", 36, "inventoryofchurc00newj.txt"),
    ("va_baptist_1", 42, "inventoryofchurc01hist.txt"),
    ("va_baptist_2", 43, "inventoryofchurc21hist.txt"),
    ("va_baptist_3", 44, "inventoryofchurc22hist.txt"),
]

PROMPT = """Extract ALL Baptist church entries from this 1941 WPA archival inventory.

Format: run-together numbered entries like:
"73 First Baptist Church, 1805--, Pawtucket . . . 74 First Baptist Church, 1805--, Crompton, West Warwick . 75..."

For EACH entry extract JSON:
{
  "entry_number": "73",
  "church_name": "full canonical name",
  "dates": "year range like 1805-- or 1700-1873 or about 1820",
  "location": "town/city name",
  "pastor_names": ["any person names in clergy context"],
  "archival_notes": "what records exist (minutes, membership)",
  "association": "parent association if mentioned"
}

OCR corrections: 3aptist=Baptist, Glocester=Gloucester, Frovidence=Providence, -=hyphen

Skip: TOC, page headers, narrative sections. Return ONLY valid JSON array."""

def call_deepseek(text):
    r = requests.post(
        'https://api.deepseek.com/v1/chat/completions',
        json={'model': 'deepseek-chat', 'messages': [
            {'role': 'system', 'content': PROMPT},
            {'role': 'user', 'content': text}
        ], 'temperature': 0.05, 'max_tokens': 8000},
        headers={'Authorization': f'Bearer {DEEPSEEK_KEY}', 'Content-Type': 'application/json'},
        timeout=120)
    if r.status_code != 200:
        print(f"  HTTP {r.status_code}")
        return None
    c = r.json()['choices'][0]['message']['content'].strip()
    c = re.sub(r'^```json?\s*\n?', '', c)
    c = re.sub(r'\n?```\s*$', '', c)
    s = c.find('[')
    if s < 0:
        return None
    return json.loads(c[s:])

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
    
    total_entries = 0
    
    for table_name, volume_id, fname in INVENTORIES:
        print(f"\n{'='*50}")
        print(f"Parsing vol {volume_id}: {fname}")
        
        filepath = WPA_DIR / fname
        if not filepath.exists():
            print(f"  File not found - skipping")
            continue
        
        text = load_clean_text(filepath)
        print(f"  Clean text: {len(text)} chars")
        
        # Find inventory section
        idx = -1
        for pattern in ["First Baptist Church", "First Six Principle", "Baptist Church, ", "Page Baptist Churches"]:
            i = text.find(pattern)
            if i > 0 and i < 100000:
                idx = i
                break
        
        if idx < 0:
            print("  Could not find inventory section - skipping")
            continue
        
        content = text[idx:idx+200000]
        
        chunks = [content[i:i+CHUNK_SIZE] for i in range(0, len(content), CHUNK_SIZE-500)]
        print(f"  {len(chunks)} chunks")
        
        all_entries = []
        for i, chunk in enumerate(chunks):
            print(f"  [{i+1}/{len(chunks)}] ", end='', flush=True)
            result = call_deepseek(chunk)
            if result:
                all_entries.extend(result)
                print(f"got {len(result)}")
            else:
                print("fail")
            time.sleep(0.3)
        
        if not all_entries:
            continue
        
        # Save
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(f"""CREATE TABLE IF NOT EXISTS wpa_baptist_{table_name} (
            id INTEGER PRIMARY KEY, entry_number INTEGER, church_name TEXT, dates TEXT, 
            location TEXT, founding_year INTEGER, closing_year INTEGER, pastor_names TEXT
        )""")
        conn.execute(f"DELETE FROM wpa_baptist_{table_name}")
        
        for e in all_entries:
            years = re.findall(r'(\d{4})', e.get('dates', '') or '')
            founding = int(years[0]) if years else None
            closing = int(years[-1]) if len(years) > 1 else None
            conn.execute(f"INSERT INTO wpa_baptist_{table_name} (entry_number, church_name, dates, location, founding_year, closing_year, pastor_names) VALUES (?,?,?,?,?,?,?)",
                (e.get('entry_number'), e.get('church_name'), e.get('dates'), e.get('location'), founding, closing, json.dumps(e.get('pastor_names', []))))
        conn.commit()
        
        saved = len(all_entries)
        total_entries += saved
        print(f"Saved {saved} to wpa_baptist_{table_name}")
        conn.close()
    
    print(f"\n{'='*50}")
    print(f"TOTAL: {total_entries} entries across {len(INVENTORIES)} volumes")