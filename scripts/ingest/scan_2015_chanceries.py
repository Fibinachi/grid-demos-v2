"""
Extract chancery data from 2015 Catholic Directory via Kilo API.
173 diocese chunks → structured JSON → catholic_chanceries table.
"""
import json, os, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

SRC = Path("E:/grid/data/directories_clean/2015_cleaned.txt")
API_KEY = os.environ.get("KILO_API_KEY", "")
BASE_URL = "https://api.kilo.ai/api/gateway"
MODEL = "openai/gpt-4o-mini"

PROMPT = """Extract the chancery/diocesan office information from this OCR'd Catholic directory section.
Return a JSON object with:
- diocese_name: full name (e.g. "Archdiocese of Baltimore")
- state: 2-letter state code
- bishop_name: full name of the current bishop
- bishop_email: if listed
- chancery_address: street address of the chancery office
- chancery_phone: phone number (format XXX-XXX-XXXX)
- chancery_fax: fax number
- chancery_email: email
- chancery_website: website
- vicar_general: name
- chancellor: name
- catholic_population: number (demographic statistic)
- total_parishes: number
- total_priests: number
- square_miles: number

Also extract each parish with:
- parish_name, address, city, state, zip, phone
- founded_year (year in parentheses), status (active/closed/merged)
- clergy: array of {name, title}

Return ONLY a JSON array with exactly ONE element (the diocese object with all fields filled, parishes in a "parishes" array)."""


def find_sections(text):
    """Split at diocese abbreviation markers that precede CLERGY, PARISHES."""
    # Find all CLERGY markers, then find the diocese abbreviation before each
    clergy_positions = [m.start() for m in re.finditer('CLERGY, PARISHES, MISSIONS AND PAROCHIAL SCHOOLS', text)]
    
    pat = re.compile(r'^([A-Z][A-Z\s\-\.\']+?)\s+\(([A-Z]{3})\)\s*$', re.MULTILINE)
    all_markers = list(pat.finditer(text))
    
    sections = []
    for cp in clergy_positions:
        # Find the last marker before this CLERGY section (within 5000 chars)
        best = None
        for m in all_markers:
            if cp - 6000 < m.start() < cp - 50:
                best = m
            elif m.start() >= cp:
                break
        if best:
            name = best.group(1).strip()
            abbr = best.group(2)
            # Check if we already have this section
            if sections and sections[-1][0] == name and abs(sections[-1][3] - best.start()) < 5000:
                continue  # Duplicate
            sections.append((name, abbr, best.start(), cp))
    
    # Build chunks
    chunks = []
    for i, (name, abbr, start, cp_end) in enumerate(sections):
        end = sections[i+1][2] if i+1 < len(sections) else len(text)
        sec = text[start:end].strip()
        if len(sec) > 500:
            if len(sec) > 12000:
                sec = sec[:12000] + "\n[...]"
            chunks.append((name, abbr, sec))
    
    print(f"  {len(chunks)} diocese content sections")
    return chunks


def extract(dio_name, state, section):
    import requests
    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": "You extract structured JSON from OCR Catholic directory text."},
                    {"role": "user", "content": PROMPT + "\n\n" + section}
                ],
                "temperature": 0.01,
                "max_tokens": 4000,
            },
            timeout=120
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        # Extract JSON
        jm = re.search(r'\[.*?\]', content, re.DOTALL)
        if jm:
            data = json.loads(jm.group(0))
            if data and isinstance(data, list):
                return data[0]
        return None
    except Exception as e:
        print(f"    API error: {e}")
        return None


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    with open(SRC, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    print(f"Loaded: {len(text):,} chars")

    sections = find_sections(text)
    if args.limit:
        sections = sections[:args.limit]

    total_parishes = 0
    for i, (dio, abbr, sec) in enumerate(sections):
        print(f"[{i+1}/{len(sections)}] {dio} ({abbr}) {len(sec):,} chars")
        if args.dry_run:
            continue

        result = extract(dio, abbr, sec)
        if result:
            parishes = result.get('parishes', [])
            print(f"  Bishop: {result.get('bishop_name','?')}")
            print(f"  Chancery: {result.get('chancery_address','')[:60]}")
            print(f"  Parishes: {len(parishes)}")
            total_parishes += len(parishes)

        time.sleep(0.5)

    print(f"\nTotal parishes extracted: {total_parishes}")

if __name__ == '__main__':
    main()
