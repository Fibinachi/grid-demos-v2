#!/usr/bin/env python3
"""
Prepare RI Baptist inventory for DeepSeek parsing.
The format is complex - numbered entries run together on lines.
Send larger chunks to DeepSeek with clear instructions.
"""
import re, os, json, time, requests, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
CHUNK_SIZE = 12000

def load_clean_text(filepath):
    text = filepath.read_text(encoding='utf-8', errors='replace')
    clean = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL|re.IGNORECASE)
    clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL|re.IGNORECASE)
    clean = re.sub(r'<[^>]+>', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

PROMPT = """Extract ALL Baptist church entries from this WPA archival inventory.

Format: numbered entries separated by page numbers, like:
"73 First Baptist Church, 1805--, Pawtucket . . . 74 First Baptist Church, 1805--, Crompton, West Warwick . 75 Pawtuxet Baptist Church, 1806, Cranston"

Each entry has: entry_number, church_name, dates, location.

For EACH entry extract as JSON:
{
  "entry_number": "73",
  "church_name": "First Baptist Church",
  "dates": "1805--",
  "location": "Pawtucket"
}

OCR corrections needed:
- '3aptist' → 'Baptist', 'Glocester' → 'Gloucester'
- '~' → '-', '—' → '-', '?' is literal uncertainty marker
- Page numbers like '73 74 75' at end of lines are NOT entry numbers

Skip: Table of Contents lines, page headers, "Page Baptist Churches..." labels.
Return ONLY a valid JSON array, no markdown."""

def call_deepseek(text_chunk):
    try:
        r = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            json={'model': 'deepseek-chat', 'messages': [
                {'role': 'system', 'content': PROMPT},
                {'role': 'user', 'content': text_chunk}
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
        print("DEEPSEEK_API_KEY not set - skipping API call")
        exit(1)
    
    text = load_clean_text(WPA_DIR / "inventoryofchurc00unse_0.txt")
    
    # Find inventory section
    idx = text.find("73 First Baptist Church, 1805")
    if idx < 0:
        idx = text.find("Page Baptist Churches")
    
    content = text[idx:] if idx > 0 else text[60000:]
    
    # Take first chunk
    chunk = content[:CHUNK_SIZE]
    print(f"First chunk: {len(chunk)} chars")
    print(f"Sample: {chunk[:500]}...")
    
    print("\nCalling DeepSeek API...")
    result = call_deepseek(chunk)
    
    if result:
        print(f"Got {len(result)} entries")
        for e in result[:10]:
            print(f"  {e}")