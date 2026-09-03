#!/usr/bin/env python3
"""
WPA Baptist Inventory Parser - DeepSeek Edition.
Parse Rhode Island Baptist inventory (vol 38) with DeepSeek API.
"""
import re, os, json, time, requests, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
CHUNK_SIZE = 15000

PROMPT = """Extract ALL Baptist church entries from this 1941 WPA archival inventory.

Format: run-together numbered entries like:
"73 First Baptist Church, 1805--, Pawtucket . . . 74 First Baptist Church, 1805--, Crompton, West Warwick . 75 Pawtuxet Baptist Church, 1806, Cranston"

For EACH entry extract JSON:
{
  "entry_number": "73",
  "church_name": "First Baptist Church",
  "dates": "1805--",
  "location": "Pawtucket",
  "raw_line": "full text of this entry"
}

OCR corrections: 3aptist=Baptist, Glocester=Gloucester, Frovidence=Providence, —=-, ..=-

Skip: TOC, headers, "Page Baptist Churches" labels, narrative sections.
Return ONLY JSON array."""

def load_clean_text(filepath):
    text = filepath.read_text(encoding='utf-8', errors='replace')
    clean = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL|re.IGNORECASE)
    clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL|re.IGNORECASE)
    clean = re.sub(r'<[^>]+>', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

def call_deepseek(chunk):
    try:
        r = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            json={'model': 'deepseek-chat', 'messages': [
                {'role': 'system', 'content': PROMPT},
                {'role': 'user', 'content': chunk}
            ], 'temperature': 0.05, 'max_tokens': 8000},
            headers={'Authorization': f'Bearer {DEEPSEEK_KEY}', 'Content-Type': 'application/json'},
            timeout=120)
        if r.status_code != 200:
            return None
        c = r.json()['choices'][0]['message']['content'].strip()
        s = c.find('[')
        if s < 0:
            return None
        return json.loads(c[s:])
    except Exception as e:
        print(f"  Err: {e}")
        return None

if __name__ == "__main__":
    if not DEEPSEEK_KEY:
        print("DEEPSEEK_API_KEY not set - use --check to see what's in database")
        exit(1)
    
    text = load_clean_text(WPA_DIR / "inventoryofchurc00unse_0.txt")
    
    # Find inventory section
    idx = text.find("73 First Baptist Church, 1805")
    if idx < 0:
        print("Could not find inventory section")
        exit(1)
    
    content = text[idx:]
    chunks = [content[i:i+CHUNK_SIZE] for i in range(0, min(len(content), 100000), CHUNK_SIZE-500)]
    
    print(f"Sending {len(chunks)} chunks to DeepSeek")
    
    all_entries = []
    for i, chunk in enumerate(chunks):
        print(f"  Chunk {i+1}/{len(chunks)} ({len(chunk)} chars)...")
        result = call_deepseek(chunk)
        if result:
            all_entries.extend(result)
            print(f"    Got {len(result)} entries")
        time.sleep(0.3)
    
    print(f"\nTotal: {len(all_entries)} entries")
    
    # Save to DB
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""CREATE TABLE IF NOT EXISTS wpa_baptist_ri (
        id INTEGER PRIMARY KEY,
        entry_number INTEGER,
        church_name TEXT,
        dates TEXT,
        location TEXT,
        raw_line TEXT
    )""")
    conn.execute("DELETE FROM wpa_baptist_ri")
    for e in all_entries:
        conn.execute("""INSERT INTO wpa_baptist_ri 
            (entry_number, church_name, dates, location, raw_line) VALUES (?,?,?,?,?)""",
            (int(e.get('entry_number', 0)), e.get('church_name', ''), e.get('dates', ''), e.get('location', ''), e.get('raw_line', '')[:200]))
    conn.commit()
    print(f"Saved to wpa_baptist_ri table")