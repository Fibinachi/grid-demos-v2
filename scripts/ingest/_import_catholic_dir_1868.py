#!/usr/bin/env python3
"""
Import ALL 1868 Catholic Directory entries via DeepSeek.
Stores results in memory, writes to DB after all API calls complete.

Adapted from _import_1865_v3.py with improved diocese detection
that handles ST. LOUIS, ST. PAUL, ST. HYACINTH, etc.

Usage:
    python scripts/ingest/_import_catholic_dir_1868.py              # Full import
    python scripts/ingest/_import_catholic_dir_1868.py --dry-run    # Preview only
    python scripts/ingest/_import_catholic_dir_1868.py --limit 5    # Test first 5 dioceses
"""

import os, re, json, requests, time, sys, sqlite3
from pathlib import Path

DB_PATH = Path("E:/grid/data/catholic_directory.db")
DIR_TEXT = Path("E:/grid/data/directories/catholic_dir_1868.txt")
DIR_YEAR = 1868
CHUNK_SIZE = 500

key = os.environ.get("DEEPSEEK_API_KEY", "")
if not key:
    print("DEEPSEEK_API_KEY not set!")
    sys.exit(1)

# ── Prompt ──
prompt = """Extract ALL parish and institution entries from this 1868 Catholic directory section.
This is OCR'd 19th-century text. Return JSON array of objects.

For each entry, classify the entity_type as one of:
  "parish" - a church with a pastor (most common)
  "cathedral" - cathedral church
  "mission" - mission church or station ("attended from", "visited from")
  "chapel" - chapel
  "school" - school, academy, college
  "cemetery" - cemetery
  "hospital" - hospital, orphanage, asylum
  "convent" - convent, monastery, religious house
  "seminary" - seminary
  "other" - anything else

JSON format per entry:
{
  "church_name": "name of church/institution",
  "entity_type": "parish|mission|chapel|school|cemetery|hospital|convent|seminary|cathedral|other",
  "city": "city or town",
  "state": "state abbreviation or name",
  "address": "street address if listed",
  "clergy": [
    {"name": "clergy name", "title": "PASTOR|ASSISTANT|RECTOR|SUPERIOR|CHAPLAIN|other"}
  ],
  "year_founded": null,
  "notes": "any additional details"
}

IMPORTANT:
- Extract EVERY entry, do not skip any.
- For entries with no clergy listed, use empty array for clergy.
- If a name like "St. Mary's" appears without a clear type, default to "parish".
- OCR CORRECTION: Fix "Jno."->"John", "Thos."->"Thomas", "Jas."->"James", "Geo."->"George", "Wm."->"William", "Chas."->"Charles", "Robt."->"Robert", "Edw."->"Edward", "Ricd."->"Richard", "Michl."->"Michael", "Patk."->"Patrick"
- Missions "attended from X" or "visited from" -> entity_type="mission"

Return ONLY a valid JSON array, no markdown fences."""

# ── Load & split text ──
print("Loading text...")
text = open(str(DIR_TEXT), errors="ignore").read()
print(f"  {len(text):,} chars, {len(text.splitlines()):,} lines")

# Improved regex that handles ST. LOUIS, ST. PAUL, etc.
# Capture everything after DIOCESE/ARCHDIOCESE OF until end of line
pattern = r'(?:ARCHDIOCESE|DIOCESE)\s+OF\s+(.+?)(?:\s*\.?\s*\n)'

raw_matches = []
for m in re.finditer(pattern, text):
    raw_name = m.group(1).strip().rstrip('.').strip()
    pos = m.start()
    # Filter noise
    if len(raw_name) < 3:
        continue
    low = raw_name.lower()
    if any(w in low for w in ['street', 'avenue', 'road', 'lane',
            'square', 'liberty', 'broadway', 'wall', 'park', 'place',
            'contents', 'recapitulation', 'established', 'present',
            'most', 'right', 'movable', 'days of', 'per 100',
            'with prayers', 'by rt.', 'cts.', 's0s']):
        continue
    if re.search(r'\.{3,}', raw_name):  # ellipsis noise
        continue
    if re.match(r'^[A-Z][a-z]+[,\.\s]+\d', raw_name):  # "Boston, per 100" style
        continue
    raw_matches.append((raw_name, pos))

print(f"  {len(raw_matches)} raw DIOCESE/ARCHDIOCESE markers")

# Canonicalize: fix OCR variants and deduplicate
def canonicalize(name):
    """Normalize diocese name to canonical form. Aggressively strip OCR junk."""
    n = name.strip()
    
    # First pass: strip from first comma that's followed by junk (not part of name)
    # e.g. "BALTIMORE, 5B" -> "BALTIMORE", "OTTAWA, U. C" -> "OTTAWA"
    # But keep "ST. JOHN'S, N. F." -> "ST. JOHN'S, N. F."
    if ',' in n:
        after_comma = n.split(',', 1)[1].strip()
        # Keep if it looks like a geographic qualifier (N. F., N. B., C. W., U. C.)
        if re.match(r'^[NSEWUCLR]\s*\.\s*[A-Z]\s*\.?$', after_comma):
            pass  # keep it
        elif re.match(r'^[A-Z][a-z]+', after_comma):
            pass  # keep e.g. "SANDWICH, ONTARIO"
        else:
            n = n.split(',')[0].strip()
    
    # Second pass: strip trailing junk after the diocese name
    # Remove trailing: digits, single chars, punctuation-only
    n = re.sub(r'\s+[\.\:\;\|\}\~\{\*\(\)\[\]\#\@\!\$\^\&]+$', '', n)
    n = re.sub(r'\s+\d+[-\s]*$', '', n)
    n = re.sub(r'\s+\d+\s*$', '', n)
    n = re.sub(r'\s+[A-Z]{1,2}$', '', n)  # trailing 1-2 uppercase chars (page markers)
    n = re.sub(r'[\.\:\;\|\}\~\{\*\(\)\[\]\#\@\!\$\^\&]+$', '', n)
    
    n = n.strip().rstrip('.').rstrip(',').strip()
    
    # Uppercase for matching
    n = n.upper().strip()
    n = re.sub(r'\s+', ' ', n)  # collapse whitespace
    
    # Fix known OCR errors
    fixes = {
        'NEW-YORK': 'NEW YORK',
        'NEW-ORLEANS': 'NEW ORLEANS',
        'NEW YORKS': 'NEW YORK',
        'NEW YORE': 'NEW YORK',
        'CINCINNATL': 'CINCINNATI',
        'PHILADELPHTA': 'PHILADELPHIA',
        'PIITSBURGH': 'PITTSBURGH',
        'RIMOUSEI': 'RIMOUSKI',
        'SAUT-SAINTE-MARIE': 'SAULT STE. MARIE',
        'HARBOR GRACE': 'HARBOUR GRACE',
        'THREE RIVERS': 'TROIS-RIVIERES',
        'NATICHITOCHES': 'NATCHITOCHES',
        'SANTA FH': 'SANTA FE',
        'SANTA FF': 'SANTA FE',
        'VINOENNES': 'VINCENNES',
        'ST, LOUIS': 'ST. LOUIS',
        'STI PAUL': 'ST. PAUL',
        'STI. PAUL': 'ST. PAUL',
        'ST, PAUL': 'ST. PAUL',
        'ST, BONIFACE': 'ST. BONIFACE',
        'FORTÂ€ WAYNE': 'FORT WAYNE',
        'MONTEREY AND LOS ANGELES ANGELES': 'MONTEREY AND LOS ANGELES',
        'SAINT JOHN, N. B': "ST. JOHN, N. B.",
        "ST. JOHNÂ€™S, N. F": "ST. JOHN'S, N. F.",
        "VANCOUVERÂ€™S ISLAND": "VANCOUVER ISLAND",
        'ST. GERMAIN OF ENCOUSTS': 'ST. GERMAIN OF RIMOUSKI',
    }
    for old, new in fixes.items():
        if n == old:
            n = new
    
    # Remove any remaining non-alpha-starting sequences
    n = re.sub(r'\s+[^A-Za-z\s\-\'\.]+$', '', n)
    
    return n.strip()

can = {}
for raw_name, pos in raw_matches:
    kn = canonicalize(raw_name)
    if not kn or len(kn) < 3:
        continue
    if kn not in can:
        can[kn] = pos

# ── Fuzzy dedup: merge OCR variants ──
# Strategy: keep earliest occurrence, use normalized prefix as grouping key
def stem(name):
    """Extract a short grouping stem from diocese name."""
    # Strip periods, commas, collapse whitespace
    s = re.sub(r'[.,;:()\[\]{}|~*#@!$%^&+=<>\\/\'\"`]', '', name)
    s = re.sub(r'\s+', ' ', s).strip().upper()
    # Take first ~15 chars
    return s[:15]

deduped = {}  # stem -> (best_name, position)
for name, pos in sorted(can.items(), key=lambda x: x[1]):
    sk = stem(name)
    if sk not in deduped:
        deduped[sk] = (name, pos)
    else:
        # Keep the name with fewer trailing junk chars (shorter is usually cleaner)
        existing_name, existing_pos = deduped[sk]
        if len(name) < len(existing_name):
            deduped[sk] = (name, existing_pos)  # keep earliest position

print(f"  {len(deduped)} unique dioceses after fuzzy dedup")

# Rebuild sorted list
sd = sorted(deduped.values(), key=lambda x: x[1])
print(f"  {len(sd)} unique dioceses after dedup")

# Build sections
sections = []
for i, (name, start) in enumerate(sd):
    end = sd[i+1][1] if i+1 < len(sd) else min(start + 60000, len(text))
    sections.append({"name": name, "text": text[start:end]})

# ── Args ──
import argparse
p = argparse.ArgumentParser(description="Import 1868 Catholic Directory via DeepSeek")
p.add_argument("--dry-run", action="store_true", help="Preview only, no API calls")
p.add_argument("--limit", type=int, default=None, help="Limit to first N dioceses")
p.add_argument("--resume", action="store_true", help="Resume from checkpoint")
args = p.parse_args()

if args.limit:
    sections = sections[:args.limit]
    print(f"  Limited to first {args.limit} dioceses")

if args.dry_run:
    print(f"\n-- DRY RUN -- {len(sections)} dioceses to process")
    for i, s in enumerate(sections):
        size_kb = len(s["text"]) // 1024
        print(f"  {i+1:3d}. {s['name']:45s} ({size_kb:,} KB)")
    est_cost = len(sections) * 0.015
    print(f"\n  Estimated DeepSeek cost: ~${est_cost:.2f} ({len(sections)} calls)")
    sys.exit(0)

CHECKPOINT_FILE = Path("E:/grid/data/directories/checkpoint_1868.json")

# ── Process all dioceses via DeepSeek ──
all_entries = []  # list of tuples for DB insert
entry_idx = 0
type_counts = {}
failures = []

# ── Load checkpoint ──
completed_dioceses = set()
if args.resume and CHECKPOINT_FILE.exists():
    try:
        completed_dioceses = set(json.loads(CHECKPOINT_FILE.read_text()))
        print(f"  Resuming — {len(completed_dioceses)} dioceses already completed")
    except:
        pass

# ── Open DB connection for incremental writes ──
conn = sqlite3.connect(str(DB_PATH))
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA foreign_keys=OFF")
conn.execute("PRAGMA synchronous=OFF")

# If not resuming, clear old 1868 data
if not completed_dioceses:
    print("Clearing old 1868 data...")
    conn.execute("DELETE FROM dir_contacts WHERE entry_id IN (SELECT id FROM dir_entries WHERE directory_year=?)", (DIR_YEAR,))
    conn.execute("DELETE FROM dir_clergy WHERE directory_year=?", (DIR_YEAR,))
    conn.execute("DELETE FROM dir_bishops WHERE directory_year=?", (DIR_YEAR,))
    conn.execute("DELETE FROM dir_entries WHERE directory_year=?", (DIR_YEAR,))
    conn.execute("DELETE FROM dir_provenance WHERE source LIKE 'catholic_dir_1868%'", ())
    conn.commit()

print(f"\nProcessing {len(sections)} dioceses via DeepSeek...")
print(f"(Estimated cost: ~${len(sections)*0.015:.2f})\n")

for i, sec in enumerate(sections):
    name = sec["name"]
    
    # Skip already-completed dioceses
    if name in completed_dioceses:
        continue
    
    clean = re.sub(r'\s+', ' ', sec["text"]).strip()[:8000]

    if len(clean) < 200:
        print(f"  [{i+1}/{len(sections)}] {name:40s} SKIP ({len(clean)} chars)")
        completed_dioceses.add(name)
        continue

    pct = (i+1)/len(sections)*100
    bar_len = 30
    filled = int(bar_len * (i+1) / len(sections))
    bar = "#" * filled + "-" * (bar_len - filled)
    print(f"  [{bar}] {pct:5.1f}% [{i+1}/{len(sections)}] {name:40s} ({len(clean):,} chars) ...", end=" ", flush=True)

    t0 = time.time()
    batch_entries = []
    try:
        r = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            json={
                'model': 'deepseek-chat',
                'messages': [
                    {'role': 'system', 'content': prompt},
                    {'role': 'user', 'content': clean}
                ],
                'temperature': 0.05,
                'max_tokens': 8000
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
            print(f"No JSON found ({elapsed:.1f}s)")
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
        print(f"OK {n_entries} entries ({elapsed:.1f}s)")

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

            batch_entries.append((
                DIR_YEAR, f"{name}_{entry_idx}", ename,
                city or None, state or None, name, etype,
                address or None, None, None, None, None,
                yf, None, None,
                notes_val + " [1868 Sadlier's]",
                json.dumps(entry, ensure_ascii=False),
                json.dumps(clergy_list, ensure_ascii=False),
            ))
            entry_idx += 1
        
        # Write this diocese's entries to DB immediately
        if batch_entries:
            entry_data = [e[:-1] for e in batch_entries]
            conn.executemany("""INSERT INTO dir_entries (directory_year, source_entry_id, name, city,
                state, diocese, entity_type, address, zip, phone, website, email,
                year_founded, landmark_type, grid_church_id, notes, source_raw)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", entry_data)
            
            # Insert clergy for these entries
            for e in batch_entries:
                source_key = e[1]
                clergy_json = e[17]
                if clergy_json:
                    clergy_list = json.loads(clergy_json)
                    real_eid = conn.execute(
                        "SELECT id FROM dir_entries WHERE source_entry_id=? AND directory_year=?",
                        (source_key, DIR_YEAR)
                    ).fetchone()
                    if real_eid:
                        for c in clergy_list:
                            cname = (c.get("name") or "").strip()
                            ctitle = (c.get("title") or "").strip()
                            if cname:
                                conn.execute(
                                    "INSERT INTO dir_clergy (entry_id, directory_year, name, role) VALUES (?,?,?,?)",
                                    (real_eid[0], DIR_YEAR, cname, ctitle)
                                )
            conn.commit()
            all_entries.extend(batch_entries)
        
        # Mark this diocese complete
        completed_dioceses.add(name)

    except Exception as e:
        elapsed = time.time() - t0
        print(f"Err: {e} ({elapsed:.1f}s)")
        failures.append((name, str(e)))

    # Save checkpoint
    CHECKPOINT_FILE.write_text(json.dumps(sorted(completed_dioceses)), encoding="utf-8")
    time.sleep(0.3)

print(f"\n{'='*60}")
print(f"Parsing complete: {len(all_entries):,} entries collected")
print(f"  Failed dioceses: {len(failures)}")
if failures:
    for fname, reason in failures[:10]:
        print(f"    WARN {fname}: {reason}")
print(f"{'='*60}")

# ── Flush remaining to DB ──
if not all_entries:
    print("\nWARNING: No entries to import!")
    conn.close()
    sys.exit(1)

print("\nAll entries already written incrementally.")

# ── Hierarchy section ──
print("Looking for hierarchy section...")
total_bishops = 0
for pat in ["CARDINALS, ARCHBISHOPS, BISHOPS", "THE HIERARCHY", "HIERARCHY OF THE CATHOLIC CHURCH"]:
    idx = text.find(pat)
    if idx > 0 and idx < len(text) * 0.5:
        hier = re.sub(r'\s+', ' ', text[idx:idx+30000]).strip()[:12000]
        print(f"  Found '{pat}' at pos {idx:,}, parsing...")
        try:
            r = requests.post(
                'https://api.deepseek.com/v1/chat/completions',
                json={
                    'model': 'deepseek-chat',
                    'messages': [
                        {'role': 'system', 'content': "Extract ALL bishops from this 1868 hierarchy listing. Return JSON array with: name, title, diocese, bishop_type, consecrated, birth_year, notes. Return ONLY valid JSON array."},
                        {'role': 'user', 'content': hier}
                    ],
                    'temperature': 0.05, 'max_tokens': 8000
                },
                headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                timeout=60
            )
            if r.status_code == 200:
                c2 = r.json()['choices'][0]['message']['content'].strip()
                c2 = re.sub(r'^```(?:json)?\s*\n?', '', c2)
                c2 = re.sub(r'\n?```\s*$', '', c2)
                s_idx = c2.find('[')
                if s_idx >= 0:
                    depth = 0
                    for j in range(s_idx, len(c2)):
                        if c2[j] == '[': depth += 1
                        elif c2[j] == ']':
                            depth -= 1
                            if depth == 0:
                                bishops = json.loads(c2[s_idx:j+1])
                                for b in bishops:
                                    conn.execute("""INSERT INTO dir_bishops (directory_year, name, title, diocese,
                                        bishop_type, status, consecrated_year, birth_year, notes, source_raw)
                                        VALUES (?,?,?,?,?,?,?,?,?,?)""", (
                                        DIR_YEAR, b.get("name",""), b.get("title","") or None,
                                        b.get("diocese","") or None, b.get("bishop_type","") or None,
                                        "historical", b.get("consecrated"), b.get("birth_year"),
                                        b.get("notes","") or None, json.dumps(b, ensure_ascii=False)))
                                total_bishops = len(bishops)
                                print(f"  OK {total_bishops} bishops imported")
                                break
        except Exception as e:
            print(f"  Hierarchy error: {e}")
        break
else:
    print("  Hierarchy section not found")

# ── Provenance ──
entry_count = conn.execute("SELECT COUNT(*) FROM dir_entries WHERE directory_year=?", (DIR_YEAR,)).fetchone()[0]
clergy_count = conn.execute("SELECT COUNT(*) FROM dir_clergy WHERE directory_year=?", (DIR_YEAR,)).fetchone()[0]
bishop_count = conn.execute("SELECT COUNT(*) FROM dir_bishops WHERE directory_year=?", (DIR_YEAR,)).fetchone()[0]

conn.execute("""INSERT INTO dir_provenance (source, description, entry_count, clergy_count, bishop_count)
    VALUES (?,?,?,?,?)""", (
    "catholic_dir_1868",
    f"1868 Sadlier's Catholic Directory -- {entry_count:,} entries across {len(sections)} dioceses",
    entry_count, clergy_count, bishop_count
))

conn.execute("INSERT OR REPLACE INTO directory_metadata (year, title, source_file, total_entries, total_clergy, total_bishops, notes) VALUES (?,?,?,?,?,?,?)", (
    DIR_YEAR,
    "Sadlier's Catholic Directory, Almanac and Ordo 1868",
    str(DIR_TEXT),
    entry_count,
    clergy_count,
    bishop_count,
    f"DeepSeek-parsed from OCR text. {len(sections)} dioceses processed, {len(failures)} failures."
))

conn.execute("PRAGMA foreign_keys=ON")
conn.commit()

# ── Summary ──
print(f"\n{'='*60}")
print(f"1868 Import Complete")
print(f"{'='*60}")
print(f"  Dioceses processed: {len(sections)}")
print(f"  Failures:           {len(failures)}")
print(f"  Entries:    {entry_count:>10,}")
print(f"  Clergy:     {clergy_count:>10,}")
print(f"  Bishops:    {bishop_count:>10,}")
print(f"\n  Entity types:")
for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f"    {t:25s} {c:>8,}")

conn.close()
print("\nDone.")
