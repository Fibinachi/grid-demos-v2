"""
DeepSeek-powered extraction of parish data from the 2000 Catholic Directory.
Sends diocese-section chunks to DeepSeek API, requesting structured JSON output.

Usage:
  python scripts/ingest/deepseek_2000.py --dry-run    # Test on first 2 dioceses
  python scripts/ingest/deepseek_2000.py               # Full extraction
  python scripts/ingest/deepseek_2000.py --diocese "Albany"  # Single diocese
"""
import json, re, os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

SRC = Path("E:/grid/data/directories/2000_formatted.txt")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

PROMPT = """Extract all Catholic parishes from this OCR'd directory section.
For each parish, return a JSON object with these fields:
- parish_name: clean name (fix OCR errors like "Stt." -> "St.", "Rey." -> "Rev.")
- address: street address if present
- city: city name
- state: 2-letter state code
- zip: 5-digit ZIP if present
- phone: phone number if present (format: XXX-XXX-XXXX)
- founded_year: founding year in parentheses if present, e.g. (1848)
- status: "active" if normal, "closed" if marked closed, "merged" if merged
- clergy: array of {name, title} objects (title: "Pastor", "Parochial Vicar", "Deacon", etc.)

Return ONLY a JSON array, no other text. Example:
[{"parish_name": "St. Mary", "address": "10 Lodge St.", "city": "Albany", "state": "NY", "zip": "12207", "phone": "518-462-5000", "founded_year": 1797, "status": "active", "clergy": [{"name": "John Smith", "title": "Pastor"}]}]

Directory section:
"""


def split_into_dioceses(text):
    """Split the 2000 directory text into diocese sections."""
    sections = []
    pattern = re.compile(r'^(?:Archdiocese|Diocese)\s+of\s+([A-Za-z\s\-\']+?)\s*$', re.MULTILINE)
    
    matches = list(pattern.finditer(text))
    for i, m in enumerate(matches):
        dio_name = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section_text = text[start:end]
        # Only include if it has parish content (contains "Rev." or "Church")
        if 'Rev.' in section_text or 'Church' in section_text:
            # Trim to ~8000 chars max (API limit friendly)
            if len(section_text) > 12000:
                section_text = section_text[:12000] + "\n[TRUNCATED]"
            sections.append((dio_name, section_text))
    
    return sections


def call_deepseek(diocese_name, section_text, dry_run=False):
    """Send section to DeepSeek API, return parsed JSON."""
    if dry_run:
        print(f"  [DRY RUN] Would send {len(section_text):,} chars for '{diocese_name}'")
        return []
    
    if not DEEPSEEK_KEY:
        print("  No DEEPSEEK_API_KEY set. Set environment variable or pass key.")
        return []
    
    import requests
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": PROMPT + section_text}
        ],
        "temperature": 0.1,
        "max_tokens": 4000,
    }
    
    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers, json=payload, timeout=120
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        
        # Extract JSON array
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        else:
            print(f"  No JSON in response: {content[:200]}")
            return []
    except Exception as e:
        print(f"  API error: {e}")
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

    print(f"Loaded 2000 directory: {len(text):,} chars")
    
    sections = split_into_dioceses(text)
    print(f"Found {len(sections)} diocese sections")

    if args.diocese:
        sections = [(d, t) for d, t in sections if d.lower() == args.diocese.lower()]
    
    if args.limit:
        sections = sections[:args.limit]

    total_parishes = 0
    for i, (dio_name, section) in enumerate(sections):
        print(f"\n[{i+1}/{len(sections)}] {dio_name} ({len(section):,} chars)")
        
        parishes = call_deepseek(dio_name, section, args.dry_run)
        
        if parishes:
            print(f"  Extracted {len(parishes)} parishes")
            total_parishes += len(parishes)
            for p in parishes[:3]:
                print(f"    {p.get('parish_name', '?')} | {p.get('city', '?')}, {p.get('state', '?')} | clergy: {len(p.get('clergy', []))}")
        
        # Rate limit: 1 request per 2 seconds
        if not args.dry_run and i < len(sections) - 1:
            time.sleep(2)

    print(f"\n{'='*60}")
    print(f"Total: {total_parishes} parishes from {len(sections)} dioceses")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
