#!/usr/bin/env python3
"""
WPA Directory Parser via DeepSeek.
Parses WPA "Directory of Churches and Religious Organizations" volumes.
Format: 3-column tabular — Church Name + Address | Town | County
Organized by denomination sections.

Usage:
    python _parse_wpa_deepseek.py                        # Parse all directory volumes
    python _parse_wpa_deepseek.py --volume DE             # Single state
    python _parse_wpa_deepseek.py --volume DE --limit 1   # Test first chunk only
"""
import os, re, json, requests, time, sys, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
CHUNK_SIZE = 8000  # chars per API call
OVERLAP = 500      # char overlap between chunks

# Map filenames to states
STATE_FILES = {
    "DE": "directoryofchurc00dela.txt",
    "DC": "directoryofchurc00dist.txt",
    "ID": "directoryofchurc00idah.txt",
    "NM": "directoryofchurc00newm.txt",
    "CA": "directoryofchurc0000cali.txt",
    "AR": "directoryofchurc00hist.txt",
    "ME": "directoryofchurc00hist_0.txt",
    "MN": "directoryofchurc00hist_1.txt",
    "NEW_ORLEANS": "directoryofchurc00hist_2.txt",
    "LA_ALAMEDA": "directoryofchurc0000cali_w5t2.txt",
    "LA_CITY": "directoryofchurc0000vari_p9s7.txt",
    "SAN_DIEGO": "directoryofchurc00unse.txt",
}

PROMPT = """Extract ALL church/religious organization entries from this WPA Historical Records Survey directory (circa 1940).
This is OCR'd typewriter text with ~85-90% accuracy. The format varies by denomination section.

For EACH entry found, extract these fields (use null if not found):
{
  "church_name": "canonical name of church",
  "address": "street address",
  "city": "city or town",
  "county": "county name if listed",
  "state": "two-letter state abbreviation",
  "denomination": "Baptist, Methodist, Catholic, Presbyterian, Episcopal, Lutheran, Jewish, etc.",
  "pastor_name": "pastor or clergy name",
  "race_label": "White, Colored, Negro if explicitly noted",
  "notes": "any other details like year organized, membership, etc."
}

IMPORTANT:
- The text is organized by denomination (Baptist Churches, Methodist Churches, Catholic Churches, etc.)
- Each entry typically has: church name, street address, city/town, pastor name
- Some entries span multiple lines
- OCR errors are common (e.g., "Chur ch" for "Church", "Rev" for "Reverend")
- Extract EVERY church/synagogue/temple/mission listed
- Skip header lines, page numbers, and section introductions
- Return ONLY a valid JSON array, no markdown fences."""


def call_deepseek(text_chunk):
    """Send chunk to DeepSeek, return parsed JSON list."""
    try:
        r = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            json={
                'model': 'deepseek-chat',
                'messages': [
                    {'role': 'system', 'content': PROMPT},
                    {'role': 'user', 'content': text_chunk}
                ],
                'temperature': 0.05,
                'max_tokens': 8000
            },
            headers={'Authorization': f'Bearer {DEEPSEEK_KEY}', 'Content-Type': 'application/json'},
            timeout=120
        )
        if r.status_code != 200:
            print(f"    HTTP {r.status_code}")
            return None
        
        content = r.json()['choices'][0]['message']['content']
        c2 = content.strip()
        c2 = re.sub(r'^```(?:json)?\s*\n?', '', c2)
        c2 = re.sub(r'\n?```\s*$', '', c2)
        
        s = c2.find('[')
        if s < 0:
            return None
        
        depth = 0
        for j in range(s, len(c2)):
            if c2[j] == '[': depth += 1
            elif c2[j] == ']':
                depth -= 1
                if depth == 0:
                    return json.loads(c2[s:j+1])
        return None
    except Exception as e:
        print(f"    Err: {e}")
        return None


def parse_volume(state_code, limit=None):
    """Parse a single state's directory volume."""
    if state_code not in STATE_FILES:
        print(f"Unknown state: {state_code}")
        return []
    
    filepath = WPA_DIR / STATE_FILES[state_code]
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return []
    
    print(f"\n{'='*60}")
    print(f"Parsing: {state_code} — {filepath.name}")
    print(f"{'='*60}")
    
    # Load and clean text
    text = filepath.read_text(encoding="utf-8", errors="replace")
    clean = re.sub(r'<[^>]+>', ' ', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    print(f"  {len(clean):,} chars")
    
    # Chunk it
    chunks = []
    pos = 0
    while pos < len(clean):
        chunk = clean[pos:pos + CHUNK_SIZE]
        if len(chunk) < 200:
            break
        chunks.append(chunk)
        pos += CHUNK_SIZE - OVERLAP
    
    if limit:
        chunks = chunks[:limit]
    
    print(f"  {len(chunks)} chunks, ~${len(chunks)*0.015:.2f} estimated cost")
    
    all_entries = []
    for i, chunk in enumerate(chunks):
        sys.stdout.write(f"  Chunk {i+1}/{len(chunks)} ({len(chunk):,} chars) ... ")
        sys.stdout.flush()
        
        t0 = time.time()
        result = call_deepseek(chunk)
        elapsed = time.time() - t0
        
        if result and isinstance(result, list):
            print(f"OK {len(result)} entries ({elapsed:.1f}s)")
            for entry in result:
                entry['_source_state'] = state_code
                entry['_chunk'] = i
            all_entries.extend(result)
        else:
            print(f"FAIL ({elapsed:.1f}s)")
        
        time.sleep(0.3)
    
    print(f"  Total: {len(all_entries):,} entries")
    return all_entries


def save_to_db(entries, state_code):
    """Save parsed entries to wpa.db."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    
    # Ensure table exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wpa_deepseek_parsed (
            id INTEGER PRIMARY KEY,
            state TEXT,
            church_name TEXT,
            address TEXT,
            city TEXT,
            county TEXT,
            denomination TEXT,
            pastor_name TEXT,
            race_label TEXT,
            notes TEXT,
            source_chunk INTEGER,
            confidence REAL DEFAULT 0.85,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    
    # Clear old data for this state
    conn.execute("DELETE FROM wpa_deepseek_parsed WHERE state=?", (state_code,))
    
    count = 0
    for e in entries:
        conn.execute("""
            INSERT INTO wpa_deepseek_parsed (state, church_name, address, city, county,
                denomination, pastor_name, race_label, notes, source_chunk)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            state_code,
            (e.get("church_name") or "").strip(),
            (e.get("address") or "").strip() or None,
            (e.get("city") or "").strip() or None,
            (e.get("county") or "").strip() or None,
            (e.get("denomination") or "").strip() or None,
            (e.get("pastor_name") or "").strip() or None,
            (e.get("race_label") or "").strip() or None,
            (e.get("notes") or "").strip() or None,
            e.get("_chunk", 0),
        ))
        count += 1
    
    conn.commit()
    conn.close()
    print(f"  Saved {count:,} entries to wpa_deepseek_parsed")


def main():
    import argparse
    p = argparse.ArgumentParser(description="WPA Directory Parser via DeepSeek")
    p.add_argument("--volume", default=None, help="State code (DE, DC, ID, NM, CA, AR, ME, MN)")
    p.add_argument("--limit", type=int, default=None, help="Limit to N chunks per volume")
    p.add_argument("--all", action="store_true", help="Parse all directory volumes")
    args = p.parse_args()
    
    if not DEEPSEEK_KEY:
        print("DEEPSEEK_API_KEY not set!")
        return
    
    if args.volume:
        entries = parse_volume(args.volume, limit=args.limit)
        if entries:
            save_to_db(entries, args.volume)
    elif args.all:
        for state in STATE_FILES:
            entries = parse_volume(state, limit=args.limit)
            if entries:
                save_to_db(entries, state)
    else:
        print("Specify --volume DE or --all")
        print(f"Available volumes: {', '.join(STATE_FILES.keys())}")


if __name__ == "__main__":
    main()
