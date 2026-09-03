"""
Chunked AI extraction of 2015 Catholic Directory via OpenRouter/Kilo API.
Splits by diocese, sends each section to cheap model for structured extraction.

Usage:
  python scripts/ingest/scan_2015.py --dry-run         # Preview chunks
  python scripts/ingest/scan_2015.py --diocese Albany  # Single diocese
  python scripts/ingest/scan_2015.py                   # Full extraction
"""
import json, os, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

SRC = Path("E:/grid/data/directories/2015_formatted.txt")
API_KEY = os.environ.get("KILO_API_KEY", "")
MODEL = "openai/gpt-4o-mini"  # Cheapest per-token

PROMPT = """Extract ALL Catholic parishes from this OCR'd directory section.
Return a JSON array of objects with:
- parish_name (clean OCR errors: "Stt."->"St.", "Rey."->"Rev.")
- address, city, state, zip, phone
- founded_year (from parentheses like (1848))
- status: "active", "closed", "merged"
- clergy: array of {name, title}
- bishop_name, chancery_address, chancery_phone (if present)

Return ONLY the JSON array, no explanations."""


def find_diocese_sections(text):
    """Split text at real diocese section headers: 'Diocese of Name, ST' appearing consistently."""
    # Find the start of US diocese listings
    anchor = text.find("Archdiocese of Anchorage, AK")
    if anchor == -1:
        print("Could not find anchor diocese!")
        return []
    
    # Only search from anchor point
    section_text = text[anchor:]
    
    pat = re.compile(r'^(Archdiocese|Diocese)\s+of\s+([A-Za-z\s\-\.\']+?),\s*([A-Z]{2})[^\w\s]', re.MULTILINE)
    matches = list(pat.finditer(section_text))
    chunks = []
    
    for i, m in enumerate(matches):
        prefix = m.group(1)
        name = m.group(2).strip()
        state = m.group(3)
        full_name = f"{prefix} of {name}"
        start = m.end()
        end = matches[i+1].start() if i+1 < len(matches) else len(section_text)
        sec = section_text[m.start():end].strip()
        if len(sec) > 500:
            if len(sec) > 12000:
                sec = sec[:12000] + "\n[...]"
            chunks.append((full_name, state, sec))
    
    print(f"  Found {len(chunks)} diocese sections starting from {chunks[0][0] if chunks else '?'}")
    return chunks


def extract_chunk(dio_name, section, dry_run=False):
    if dry_run:
        return []
    
    import requests
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": "You extract structured JSON from OCR text."},
                    {"role": "user", "content": PROMPT + "\n\n" + section}
                ],
                "temperature": 0.01,
                "max_tokens": 4000,
            },
            timeout=120
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        
        # Extract JSON array
        jm = re.search(r'\[\s*\{.*\}\s*\]', content, re.DOTALL)
        if jm:
            return json.loads(jm.group(0))
        jm2 = re.search(r'\[.*?\]', content, re.DOTALL)
        if jm2:
            return json.loads(jm2.group(0))
        print(f"  No JSON: {content[:150]}")
        return []
    except Exception as e:
        print(f"  Error: {e}")
        return []


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--diocese', type=str)
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()
    
    with open(SRC, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    
    print(f"Loaded: {len(text):,} chars")
    chunks = find_diocese_sections(text)
    print(f"Diocese sections: {len(chunks)}")
    
    if args.diocese:
        chunks = [(d, s) for d, s in chunks if args.diocese.lower() in d.lower()]
    if args.limit:
        chunks = chunks[:args.limit]
    
    total = 0
    for i, (dio, state, sec) in enumerate(chunks):
        label = f"{dio} ({state})"
        print(f"[{i+1}/{len(chunks)}] {label} ({len(sec):,} chars)")
        
        if args.dry_run:
            continue
        
        parishes = extract_chunk(dio, sec)
        if parishes:
            print(f"  -> {len(parishes)} parishes")
            total += len(parishes)
            for p in parishes[:3]:
                c = len(p.get('clergy', []))
                print(f"    {p.get('parish_name','?'):<40} {p.get('city','?'):<15} {c} clergy")
        
        time.sleep(0.5)
    
    if not args.dry_run:
        print(f"\nTotal: {total} parishes")

if __name__ == '__main__':
    main()
