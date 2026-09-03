#!/usr/bin/env python3
"""
Generic Catholic Directory importer via DeepSeek.
Processes any year 1833-1955 by splitting the formatted OCR text
into diocese sections and sending each to DeepSeek for extraction.

Usage:
    python scripts/ingest/import_catholic_dir.py 1938              # Single year
    python scripts/ingest/import_catholic_dir.py 1938 --dry-run   # Preview only
    python scripts/ingest/import_catholic_dir.py 1938 --limit 3   # Test first 3 dioceses
    python scripts/ingest/import_catholic_dir.py --batch          # All target years
    python scripts/ingest/import_catholic_dir.py --batch --dry-run # Preview all
"""
import os, re, json, requests, time, sys, sqlite3, argparse
from pathlib import Path
from datetime import datetime

DB_PATH = Path("E:/grid/data/catholic_directory.db")
DIR_DIR = Path("E:/grid/data/directories")
CHECKPOINT_DIR = Path("E:/grid/data/directories/checkpoints")
CHECKPOINT_DIR.mkdir(exist_ok=True)

key = os.environ.get("DEEPSEEK_API_KEY", "")
if not key:
    print("DEEPSEEK_API_KEY not set!")
    sys.exit(1)

# ── Target years (already loaded in DB) ──
ALREADY_LOADED = {1865, 1868, 1938, 1944, 2021, 1948, 1949, 1951, 1952, 1953, 1954, 1955, 1956, 1957, 1958, 1960, 1961, 1962, 1963, 1964, 1965, 1966, 1967, 1968, 1971, 1972, 1974, 1975, 1976, 1978, 1979, 1980, 1981, 1982, 1983, 1984, 1985, 1986, 1988, 1989, 1990, 1991, 1992, 1993, 1994, 1995, 1996, 1997, 1998, 1999, 2000, 2005, 2006, 2007, 2008, 2009, 2010, 2012, 2013, 2014, 2015, 2016, 2018, 2019, 2020}
TARGET_YEARS = []
for y in range(1833, 1956, 3):
    fpath = DIR_DIR / f"catholic_dir_{y}_formatted.txt"
    if fpath.exists() and y not in ALREADY_LOADED:
        TARGET_YEARS.append(y)

# Process all target years (no half-split)
# Years already completed will be skipped via checkpoints

# ── Prompt ──
SYSTEM_PROMPT = """Extract ALL parish and institution entries from this Catholic directory section.
This is OCR'd historical text. Return JSON array of objects.

For each entry, classify entity_type as one of:
  "parish" - church with resident priest(s)
  "cathedral" - cathedral church
  "mission" - mission church ("attended from", "visited from")
  "chapel" - chapel (hospital, convent, institutional)
  "school" - school, academy, college, university
  "cemetery" - cemetery
  "hospital" - hospital, orphanage, asylum, sanitarium, home for aged
  "convent" - convent, monastery, religious house, friary
  "seminary" - seminary, scholasticate, novitiate
  "chancery" - diocesan offices
  "other" - anything else

JSON format per entry:
{
  "church_name": "name of church/institution",
  "entity_type": "parish|mission|chapel|school|cemetery|hospital|convent|seminary|cathedral|chancery|other",
  "city": "city or town",
  "state": "state abbreviation (2 letters if possible)",
  "address": "street address if listed",
  "clergy": [
    {"name": "full clergy name", "title": "PASTOR|ASSISTANT|RECTOR|SUPERIOR|CHAPLAIN|ADMINISTRATOR|other"}
  ],
  "year_founded": null,
  "notes": "any additional details (school enrollment, religious order, etc.)"
}

CRITICAL RULES:
- Extract EVERY entry, do not skip any.
- For entries with no clergy listed, use empty array.
- Default entity_type is "parish" for named churches with priests.
- Fix OCR abbreviations: "Jno."="John", "Thos."="Thomas", "Jas."="James", "Geo."="George", "Wm."="William", "Chas."="Charles", "Robt."="Robert", "Edw."="Edward", "Ricd."="Richard", "Michl."="Michael", "Patk."="Patrick", "Rt. Rev."="Right Reverend", "Very Rev."="Very Reverend"
- If text is garbled beyond recognition, skip that entry.
- Return ONLY a valid JSON array, no markdown fences."""


def canonicalize_diocese(name):
    """Normalize diocese name. Strip OCR junk."""
    n = name.strip().upper()
    n = re.sub(r'\s+', ' ', n)
    n = re.sub(r'[\.\:\;\|\}\~\{\*\(\)\[\]\#\@\!\$\^\&]+$', '', n)
    n = re.sub(r'\s+\d+[\-\s]*$', '', n)
    n = re.sub(r'\s+[A-Z]{1,2}$', '', n)
    n = n.strip().rstrip('.').rstrip(',').strip()

    fixes = {
        'NEW-YORK': 'NEW YORK', 'NEW-ORLEANS': 'NEW ORLEANS',
        'ST, LOUIS': 'ST. LOUIS', 'STI PAUL': 'ST. PAUL',
        'STI. PAUL': 'ST. PAUL', 'ST, PAUL': 'ST. PAUL',
        'FORTÂ€ WAYNE': 'FORT WAYNE', 'SAULT-SAINTE-MARIE': 'SAULT STE. MARIE',
    }
    return fixes.get(n, n)


def find_dioceses(text):
    """Find diocese section headers: DIOCESE/ARCHDIOCESE OF X followed by Latin name."""
    pattern = r'(?:ARCHDIOCESE|DIOCESE)\s+OF\s+(.+?)\s*\n'
    matches = []
    for m in re.finditer(pattern, text):
        raw = m.group(1).strip().rstrip('.').strip()
        if len(raw) < 3:
            continue
        # Must be followed by Latin diocesan name within 300 chars
        after = text[m.end():m.end()+300]
        if not re.search(r'\(Archidioecesis|\(Dioecesis', after):
            continue
        # Filter "PRIESTS OF THE ARCHDIOCESE OF..." style headers
        before = text[max(0,m.start()-80):m.start()]
        if 'PRIESTS OF THE' in before.upper():
            continue
        matches.append((raw, m.start()))

    # Deduplicate by stem
    deduped = {}
    for name, pos in matches:
        stem = re.sub(r'[^A-Z\s]', '', name.upper()).strip()[:20]
        if stem not in deduped:
            deduped[stem] = (name, pos)
        elif len(name) < len(deduped[stem][0]):
            deduped[stem] = (name, deduped[stem][1])

    sorted_dioceses = sorted(deduped.values(), key=lambda x: x[1])
    
    sections = []
    for i, (name, start) in enumerate(sorted_dioceses):
        # End at next diocese or reasonable chunk
        end = sorted_dioceses[i+1][1] if i+1 < len(sorted_dioceses) else min(start + 120000, len(text))
        sections.append({"name": name, "text": text[start:end]})
    
    return sections


def process_year(year, dry_run=False, limit=None):
    """Process a single directory year."""
    fpath = DIR_DIR / f"catholic_dir_{year}_formatted.txt"
    if not fpath.exists():
        print(f"  File not found: {fpath}")
        return False

    checkpoint_file = CHECKPOINT_DIR / f"checkpoint_{year}.json"
    
    print(f"\n{'='*60}")
    print(f"YEAR {year}")
    print(f"{'='*60}")

    text = open(str(fpath), errors='ignore').read()
    size_kb = len(text) // 1024
    print(f"  File: {size_kb:,} KB, {len(text.splitlines()):,} lines")

    sections = find_dioceses(text)
    print(f"  Dioceses found: {len(sections)}")

    if limit:
        sections = sections[:limit]
        print(f"  Limited to {limit}")

    if dry_run:
        est_cost = len(sections) * 0.015
        print(f"\n  -- DRY RUN -- {len(sections)} dioceses, ~${est_cost:.2f}")
        for i, s in enumerate(sections):
            kb = len(s["text"]) // 1024
            print(f"    {i+1:3d}. {s['name']:40s} ({kb:,} KB)")
        return True

    # ── DB Setup ──
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("PRAGMA synchronous=OFF")

    # Load checkpoint
    completed = set()
    if checkpoint_file.exists():
        try:
            completed = set(json.loads(checkpoint_file.read_text()))
            print(f"  Resuming — {len(completed)} dioceses already done")
        except:
            pass

    # Clear old data if starting fresh
    if not completed:
        print("  Clearing old data...")
        conn.execute("DELETE FROM dir_contacts WHERE entry_id IN (SELECT id FROM dir_entries WHERE directory_year=?)", (year,))
        conn.execute("DELETE FROM dir_clergy WHERE directory_year=?", (year,))
        conn.execute("DELETE FROM dir_bishops WHERE directory_year=?", (year,))
        conn.execute("DELETE FROM dir_entries WHERE directory_year=?", (year,))
        conn.commit()

    # ── Process each diocese ──
    entry_idx = 0
    type_counts = {}
    failures = []
    total_entries = 0
    total_clergy = 0

    total = len(sections)
    for i, sec in enumerate(sections):
        name = sec["name"]
        if name in completed:
            continue

        clean = re.sub(r'\s+', ' ', sec["text"]).strip()[:30000]
        if len(clean) < 200:
            completed.add(name)
            continue

        bar_len = 25
        filled = int(bar_len * (i+1) / total)
        bar = "#" * filled + "-" * (bar_len - filled)
        pct = (i+1)/total*100
        print(f"  [{bar}] {pct:5.1f}% {i+1}/{total} {name:40s} ...", end=" ", flush=True)

        t0 = time.time()
        batch_entries = []
        try:
            r = requests.post(
                'https://api.deepseek.com/v1/chat/completions',
                json={
                    'model': 'deepseek-chat',
                    'messages': [
                        {'role': 'system', 'content': SYSTEM_PROMPT},
                        {'role': 'user', 'content': clean}
                    ],
                    'temperature': 0.05,
                    'max_tokens': 16000
                },
                headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                timeout=120
            )
            elapsed = time.time() - t0

            if r.status_code != 200:
                print(f"HTTP {r.status_code} ({elapsed:.1f}s)")
                failures.append((name, f"HTTP {r.status_code}"))
                continue

            content = r.json()['choices'][0]['message']['content']
            c2 = content.strip()
            c2 = re.sub(r'^```(?:json)?\s*\n?', '', c2)
            c2 = re.sub(r'\n?```\s*$', '', c2)

            s_idx = c2.find('[')
            if s_idx < 0:
                print(f"No JSON ({elapsed:.1f}s)")
                failures.append((name, "No JSON"))
                continue

            depth = 0
            parsed = None
            for j in range(s_idx, len(c2)):
                if c2[j] == '[':
                    depth += 1
                elif c2[j] == ']':
                    depth -= 1
                    if depth == 0:
                        parsed = json.loads(c2[s_idx:j+1])
                        break

            if not parsed:
                print(f"Incomplete JSON ({elapsed:.1f}s)")
                failures.append((name, "Incomplete JSON"))
                continue

            n_entries = len(parsed)
            n_clergy = sum(len(e.get("clergy", [])) for e in parsed)
            print(f"OK {n_entries}e/{n_clergy}c ({elapsed:.1f}s)")

            for entry in parsed:
                ename = (entry.get("church_name") or "").strip()
                if not ename:
                    continue
                etype = entry.get("entity_type", "parish")
                city = (entry.get("city") or "").strip()
                state = (entry.get("state") or "").strip()
                address = (entry.get("address") or "").strip()
                notes_val = (entry.get("notes") or "").strip()
                clergy_list = entry.get("clergy", [])
                yf = entry.get("year_founded")

                type_counts[etype] = type_counts.get(etype, 0) + 1

                source_key = f"{name}_{entry_idx}"
                batch_entries.append((
                    year, source_key, ename,
                    city or None, state or None, name, etype,
                    address or None, None, None, None, None,
                    yf, None, None,
                    notes_val + f" [{year} Catholic Directory]",
                    json.dumps(entry, ensure_ascii=False),
                    json.dumps(clergy_list, ensure_ascii=False),
                ))
                entry_idx += 1

            # Write to DB
            if batch_entries:
                entry_data = [e[:-1] for e in batch_entries]
                conn.executemany("""INSERT INTO dir_entries (directory_year, source_entry_id, name, city,
                    state, diocese, entity_type, address, zip, phone, website, email,
                    year_founded, landmark_type, grid_church_id, notes, source_raw)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", entry_data)

                for e in batch_entries:
                    source_key = e[1]
                    clergy_json = e[17]
                    if clergy_json:
                        clergy_list = json.loads(clergy_json)
                        real_eid = conn.execute(
                            "SELECT id FROM dir_entries WHERE source_entry_id=? AND directory_year=?",
                            (source_key, year)
                        ).fetchone()
                        if real_eid:
                            for c in clergy_list:
                                cname = (c.get("name") or "").strip()
                                ctitle = (c.get("title") or "").strip()
                                if cname:
                                    conn.execute(
                                        "INSERT INTO dir_clergy (entry_id, directory_year, name, role) VALUES (?,?,?,?)",
                                        (real_eid[0], year, cname, ctitle)
                                    )
                                    total_clergy += 1
                conn.commit()
                total_entries += len(batch_entries)

            completed.add(name)

        except Exception as e:
            elapsed = time.time() - t0
            print(f"Err: {e} ({elapsed:.1f}s)")
            failures.append((name, str(e)))

        checkpoint_file.write_text(json.dumps(sorted(completed)), encoding="utf-8")
        time.sleep(0.3)

    # ── Summary ──
    print(f"\n  COMPLETE: {total_entries:,} entries, {total_clergy:,} clergy")
    print(f"  Types: {dict(type_counts)}")
    if failures:
        print(f"  Failed: {len(failures)} dioceses")
        for fname, reason in failures[:5]:
            print(f"    - {fname}: {reason}")

    conn.close()
    return total_entries > 0


def main():
    p = argparse.ArgumentParser(description="Import Catholic Directory via DeepSeek")
    p.add_argument("year", nargs="?", type=int, help="Single year to process")
    p.add_argument("--batch", action="store_true", help="Process all target years")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=None, help="Limit dioceses per year")
    args = p.parse_args()

    if args.batch:
        years = TARGET_YEARS
        print(f"BATCH MODE: {len(years)} years")
        print(f"Estimated cost: ~${len(years) * 50 * 0.015:.2f} (assuming ~50 dioceses/year)")
        if args.dry_run:
            for y in years:
                process_year(y, dry_run=True, limit=args.limit)
            return
        for y in years:
            process_year(y, dry_run=False, limit=args.limit)
    elif args.year:
        process_year(args.year, dry_run=args.dry_run, limit=args.limit)
    else:
        p.print_help()

if __name__ == "__main__":
    main()
