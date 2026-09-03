#!/usr/bin/env python3
"""
WPA Baptist Inventory Parser - Rhode Island Test.
"""
import os, re, json, time, requests, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
CHUNK_SIZE = 12000

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
    print("Parsing Rhode Island Baptist Inventory (vol 38)")
    
    text = load_clean_text(WPA_DIR / "inventoryofchurc00unse_0.txt")
    
    # Find inventory section
    idx = text.find("73 First Baptist Church, 1805")
    if idx < 0:
        idx = text.find("First Baptist Church")
    
    content = text[idx:idx+200000]  # First ~200K chars
    
    chunks = [content[i:i+CHUNK_SIZE] for i in range(0, len(content), CHUNK_SIZE-500)]
    print(f"{len(chunks)} chunks")
    
    all_entries = []
    for i, chunk in enumerate(chunks):
        print(f"[{i+1}/{len(chunks)}] ", end='', flush=True)
        result = call_deepseek(chunk)
        if result:
            all_entries.extend(result)
            print(f"got {len(result)}")
        else:
            print("fail")
        time.sleep(0.3)
    
    print(f"\nTotal: {len(all_entries)} entries")
    
    if all_entries:
        # Sample output
        print("\nFirst 10 entries:")
        for e in all_entries[:10]:
            print(f"  {e}")
        
        # Save
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("DROP TABLE IF EXISTS wpa_baptist_ri")
        conn.execute("""CREATE TABLE wpa_baptist_ri (
            id INTEGER PRIMARY KEY, entry_number INTEGER, church_name TEXT, dates TEXT, 
            location TEXT, founding_year INTEGER, closing_year INTEGER, pastor_names TEXT
        )""")
        for e in all_entries:
            years = re.findall(r'(\d{4})', e.get('dates', '') or '')
            founding = int(years[0]) if years else None
            closing = int(years[-1]) if len(years) > 1 else None
            conn.execute("INSERT INTO wpa_baptist_ri (entry_number, church_name, dates, location, founding_year, closing_year, pastor_names) VALUES (?,?,?,?,?,?,?)",
                (e.get('entry_number'), e.get('church_name'), e.get('dates'), e.get('location'), founding, closing, json.dumps(e.get('pastor_names', []))))
        conn.commit()
        conn.close()
        print("\nSaved to wpa_baptist_ri")