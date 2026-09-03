#!/usr/bin/env python3
"""
WPA Directory Parser via DeepSeek — Batch Edition.
Processes WPA "Directory of Churches and Religious Organizations" volumes.
Skips introductory text and targets church listing sections only.

Usage:
    python _parse_wpa_batch.py --state DE              # Single state
    python _parse_wpa_batch.py --all                   # All 12 directory states
    python _parse_wpa_batch.py --state DE --limit 3    # Test first 3 chunks
"""
import os, re, json, requests, time, sys, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")
LOG_FILE = Path("E:/grid/data/wpa/_deepseek_log.txt")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
CHUNK_SIZE = 8000
INTRO_SKIP = 50000  # skip first 50K chars (title page, TOC, preface)

STATE_FILES = {
    "DE": "directoryofchurc00dela.txt",
    "DC": "directoryofchurc00dist.txt",
    "ID": "directoryofchurc00idah.txt",
    "NM": "directoryofchurc00newm.txt",
    "CA": "directoryofchurc0000cali.txt",
    "AR": "directoryofchurc00hist.txt",
    "ME": "directoryofchurc00hist_0.txt",
    "MN": "directoryofchurc00hist_1.txt",
    "NO": "directoryofchurc00hist_2.txt",       # New Orleans
    "CA_ALA": "directoryofchurc0000cali_w5t2.txt",  # Alameda County
    "CA_LA": "directoryofchurc0000vari_p9s7.txt",   # Los Angeles
    "CA_SD": "directoryofchurc00unse.txt",          # San Diego
}

PROMPT = """Extract ALL church/religious organization entries from this 1940 WPA directory section.
OCR quality is ~85%. Format: denomination sections with entries listing church name, address, pastor.

For EACH entry, extract:
{
  "church_name": "canonical church name",
  "address": "street address if listed",
  "city": "city or town",
  "county": "county if listed",
  "denomination": "Baptist, Methodist, Catholic, Presbyterian, Episcopal, Lutheran, Jewish, etc.",
  "pastor_name": "pastor/clergy name if listed",
  "race_label": "White/Colored/Negro if explicitly noted in section header"
}

Extract EVERY church/synagogue/temple/mission. Skip table-of-contents lines and section headers.
Return ONLY valid JSON array, no markdown fences."""


def log(msg):
    print(msg, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def call_api(chunk):
    try:
        r = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            json={'model': 'deepseek-chat', 'messages': [
                {'role': 'system', 'content': PROMPT},
                {'role': 'user', 'content': chunk}
            ], 'temperature': 0.05, 'max_tokens': 8000},
            headers={'Authorization': f'Bearer {DEEPSEEK_KEY}', 'Content-Type': 'application/json'},
            timeout=90)
        if r.status_code != 200:
            return None
        c2 = r.json()['choices'][0]['message']['content'].strip()
        c2 = re.sub(r'^```(?:json)?\s*\n?', '', c2)
        c2 = re.sub(r'\n?```\s*$', '', c2)
        s = c2.find('[')
        if s < 0: return None
        depth = 0
        for j in range(s, len(c2)):
            if c2[j] == '[': depth += 1
            elif c2[j] == ']':
                depth -= 1
                if depth == 0:
                    return json.loads(c2[s:j+1])
        return None
    except Exception as e:
        return None


def parse_state(state_code, limit=None):
    if state_code not in STATE_FILES:
        log(f"Unknown state: {state_code}")
        return 0
    
    fp = WPA_DIR / STATE_FILES[state_code]
    if not fp.exists():
        log(f"File not found: {fp}")
        return 0
    
    log(f"\n{'='*50}")
    log(f"Parsing: {state_code} — {fp.name}")
    
    text = fp.read_text(encoding="utf-8", errors="replace")
    clean = re.sub(r'<[^>]+>', ' ', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    log(f"  {len(clean):,} chars total")
    
    # Skip intro
    if len(clean) > INTRO_SKIP:
        clean = clean[INTRO_SKIP:]
        log(f"  {len(clean):,} chars after skipping intro")
    
    # Chunk
    chunks = []
    pos = 0
    while pos < len(clean):
        chunk = clean[pos:pos + CHUNK_SIZE]
        if len(chunk) < 200: break
        chunks.append(chunk)
        pos += CHUNK_SIZE - 200  # small overlap
    
    if limit:
        chunks = chunks[:limit]
    
    log(f"  {len(chunks)} chunks, ~${len(chunks)*0.015:.2f} est cost")
    
    # Connect to DB
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wpa_deepseek_parsed (
            id INTEGER PRIMARY KEY, state TEXT, church_name TEXT, address TEXT,
            city TEXT, county TEXT, denomination TEXT, pastor_name TEXT,
            race_label TEXT, notes TEXT, source_chunk INTEGER,
            confidence REAL DEFAULT 0.85, created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("DELETE FROM wpa_deepseek_parsed WHERE state=?", (state_code,))
    conn.commit()
    
    total = 0
    t0 = time.time()
    
    for i, chunk in enumerate(chunks):
        t1 = time.time()
        result = call_api(chunk)
        elapsed = time.time() - t1
        
        if result and isinstance(result, list):
            n = len(result)
            log(f"  [{i+1}/{len(chunks)}] {n:>4} entries ({elapsed:.1f}s)")
            for e in result:
                conn.execute("""INSERT INTO wpa_deepseek_parsed
                    (state, church_name, address, city, county, denomination, pastor_name, race_label, notes, source_chunk)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""", (
                    state_code,
                    (e.get("church_name") or "").strip(),
                    (e.get("address") or "").strip() or None,
                    (e.get("city") or "").strip() or None,
                    (e.get("county") or "").strip() or None,
                    (e.get("denomination") or "").strip() or None,
                    (e.get("pastor_name") or "").strip() or None,
                    (e.get("race_label") or "").strip() or None,
                    (e.get("notes") or "").strip() or None,
                    i,
                ))
            conn.commit()
            total += n
        else:
            log(f"  [{i+1}/{len(chunks)}] FAIL ({elapsed:.1f}s)")
        
        time.sleep(0.2)
    
    conn.close()
    elapsed_total = (time.time() - t0) / 60
    log(f"  Total: {total:,} entries in {elapsed_total:.1f} min")
    return total


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--state", default=None)
    p.add_argument("--all", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()
    
    if not DEEPSEEK_KEY:
        print("DEEPSEEK_API_KEY not set!")
        return
    
    if args.state:
        parse_state(args.state, limit=args.limit)
    elif args.all:
        for st in STATE_FILES:
            parse_state(st, limit=args.limit)
    else:
        print("Use --state DE or --all")
        print(f"States: {', '.join(STATE_FILES.keys())}")


if __name__ == "__main__":
    main()
