#!/usr/bin/env python3
"""
Import the 1865 Catholic Directory into catholic_directory.db.

Parses raw OCR text from Internet Archive via DeepSeek API. Extracts EVERY
diocese section — bishops, parishes, missions, schools, cemeteries, etc.

Strategy:
1. Split raw OCR text into diocese sections (regex on headers)
2. For each section, use DeepSeek to extract structured entries
3. Also parse the universal hierarchy/bishops section
4. Insert everything into catholic_directory.db

Usage:
    python scripts/ingest/_import_catholic_dir_1865.py              # Full import
    python scripts/ingest/_import_catholic_dir_1865.py --dry-run    # Preview only
    python scripts/ingest/_import_catholic_dir_1865.py --limit 3    # Test first 3 dioceses
    python scripts/ingest/_import_catholic_dir_1865.py --resume     # Resume from checkpoint
"""

import json
import sqlite3
import re
import os
import time
import sys
import requests
from pathlib import Path
from datetime import datetime

# ── Paths ──
DB_PATH = Path("E:/grid/data/catholic_directory.db")
DIR_TEXT = Path("E:/grid/data/directories/catholic_dir_1865.txt")
CHECKPOINT_FILE = Path("E:/grid/data/directories/checkpoint_1865.json")
DIR_YEAR = 1865
CHUNK_SIZE = 500

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

# ── DeepSeek prompts ──

BISHOP_HEADER_PROMPT = """Extract the diocesan administration from this 1865 Catholic directory section header.
Return JSON: {
  "diocese": "name of diocese",
  "bishop": {"name": "...", "title": "BISHOP|ARCHBISHOP", "appointed": 18..},
  "vicar_general": "name or null",
  "cathedral": "cathedral church name and address",
  "chancery_address": "address if listed",
  "notes": "any other administration details"
}
If the see is vacant, set bishop to null. Extract ALL named clergy with their titles.
Return ONLY valid JSON, no markdown fences."""

PARISH_PROMPT_1865 = """Extract ALL parish and institution entries from this 1865 Catholic directory section.
This is OCR'd 19th-century text. Return JSON array of objects.

For each entry, classify the entity_type as one of:
  "parish" - a church with a pastor (most common)
  "cathedral" - cathedral church
  "mission" - mission church or station
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
- Some entries may be religious orders, orphanages, or schools — those are NOT parishes, classify appropriately.
- If a name like "St. Mary's" appears without a clear type, default to "parish".
- 19th-century Catholic directories often list "Missions" and "Stations" under a parish — extract these as separate entries with entity_type "mission".

Return ONLY a valid JSON array, no markdown fences."""

HIERARCHY_PROMPT_1865 = """Extract ALL bishops, archbishops, and cardinals from this 1865 US Catholic hierarchy listing.
Return JSON array: [
  {
    "name": "bishop name",
    "title": "Bishop of X | Archbishop of X",
    "diocese": "diocese name",
    "bishop_type": "BISHOP|ARCHBISHOP|CARDINAL",
    "consecrated": 18..,
    "birth_year": 18..,
    "notes": "any additional details"
  }
]
Extract EVERY bishop listed. Return ONLY valid JSON array, no markdown fences."""


# ── Diocese boundary detection ──

def find_diocese_sections(text):
    """
    Split the 1865 directory text into per-diocese sections.

    The 1865 OCR text repeats "DIOCESE OF X" as page headers, so we
    take the FIRST occurrence of each diocese name and use the gap
    between first occurrences as section boundaries.
    """
    pattern = r'(?:ARCHDIOCESE|DIOCESE)\s+OF\s+([A-Z][A-Z\s\-\']+?)(?:\.|\s*\n)'

    # Collect ALL matches
    all_matches = []
    for m in re.finditer(pattern, text):
        name = m.group(1).strip().rstrip('.')
        pos = m.start()
        if len(name) < 3:
            continue
        # Skip OCR noise: street names, ads, etc.
        if any(w in name.lower() for w in ['street', 'avenue', 'road', 'lane',
                'square', 'liberty', 'broadway', 'wall', 'park', 'place']):
            continue
        # Skip if preceded by lowercase (embedded in sentence)
        if pos > 0 and text[pos-1:pos].strip() and text[pos-1].islower():
            continue
        all_matches.append((name, pos))

    # Canonicalize diocese names and take FIRST occurrence only
    canonical = {}
    for name, pos in all_matches:
        # Normalize: uppercase, fix OCR variants
        key = name.upper().strip()
        # Merge OCR variants
        if key == 'PHILADELPHTA':
            key = 'PHILADELPHIA'
        if key == 'SANTA FR':
            key = 'SANTA FE'
        if key == 'SAUT-SAINTE-MARIE':
            key = 'SAULT STE. MARIE'
        if key == 'NEW-YORK':
            key = 'NEW YORK'
        if key == 'NEW-ORLEANS':
            key = 'NEW ORLEANS'
        if key == 'NATICHITOCHES' or key == 'NATCHITOCHES':
            key = 'NATCHITOCHES'
        if key == 'HARBOR GRACE':
            key = 'HARBOUR GRACE'
        if key == 'ERI':
            key = 'ERIE'
        if key == 'KINGSTON' and pos > 700000:
            key = 'KINGSTON (CA)'
        if key == 'THREE RIVERS':
            key = 'TROIS-RIVIERES'

        if key not in canonical:
            canonical[key] = pos

    # Sort by position
    sorted_dioceses = sorted(canonical.items(), key=lambda x: x[1])

    # Build sections with proper boundaries
    sections = []
    for i, (name, start) in enumerate(sorted_dioceses):
        # Determine end: next diocese's start, or a reasonable max
        if i + 1 < len(sorted_dioceses):
            end = sorted_dioceses[i + 1][1]
        else:
            end = min(start + 60000, len(text))

        section_text = text[start:end]
        sections.append({
            "name": name,
            "start": start,
            "end": end,
            "text": section_text,
        })

    print(f"Found {len(sections)} diocese sections (from {len(all_matches)} raw matches)")
    return sections


# ── DeepSeek API ──

def call_deepseek(prompt, chunk, debug=False):
    """Call DeepSeek API and return parsed JSON."""
    if not DEEPSEEK_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY not set!")

    try:
        r = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            json={
                'model': 'deepseek-chat',
                'messages': [
                    {'role': 'system', 'content': prompt},
                    {'role': 'user', 'content': chunk}
                ],
                'temperature': 0.05,
                'max_tokens': 8000
            },
            headers={
                'Authorization': f'Bearer {DEEPSEEK_KEY}',
                'Content-Type': 'application/json'
            },
            timeout=120
        )

        if r.status_code == 200:
            content = r.json()['choices'][0]['message']['content']
            if debug:
                print(f"\n    [DEBUG] Raw response ({len(content)} chars): {content[:300]}...")
            # Strip markdown fences (handle both ```json and ```)
            cleaned = content.strip()
            cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
            cleaned = re.sub(r'\n?```\s*$', '', cleaned)
            if debug:
                print(f"    [DEBUG] Cleaned ({len(cleaned)} chars): {cleaned[:300]}...")

            # Find JSON array or object
            for start_char, end_char in [('[', ']'), ('{', '}')]:
                s = cleaned.find(start_char)
                if s >= 0:
                    depth = 0
                    for j in range(s, len(cleaned)):
                        if cleaned[j] == start_char:
                            depth += 1
                        elif cleaned[j] == end_char:
                            depth -= 1
                            if depth == 0:
                                result = json.loads(cleaned[s:j+1])
                                if debug:
                                    t = type(result).__name__
                                    n = len(result) if isinstance(result, list) else len(result.keys())
                                    print(f"    [DEBUG] Parsed {t} with {n} items")
                                return result
            if debug:
                print(f"    [DEBUG] No JSON structure found in cleaned response")
            return None
        else:
            print(f"  HTTP {r.status_code}: {r.text[:200]}")
            return None
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"  API error: {e}")
        return None


def progress_bar(current, total, width=50):
    pct = current / total if total > 0 else 1
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    return f"│{bar}│ {pct*100:5.1f}% ({current:,}/{total:,})"


# ── Main import ──

def import_1865(dry_run=False, limit=None, resume=False):
    if not DEEPSEEK_KEY:
        print("❌ DEEPSEEK_API_KEY not set! Set it in environment variables.")
        return

    if not DIR_TEXT.exists():
        print(f"❌ Missing: {DIR_TEXT}")
        return
    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        print("   Run: python scripts/ingest/_build_catholic_dir_db.py")
        return

    # ── Load text ──
    print(f"Loading 1865 directory text...")
    text = DIR_TEXT.read_text(encoding="utf-8", errors="ignore")
    print(f"  {len(text):,} chars, {len(text.splitlines()):,} lines")

    # ── Find diocese sections ──
    sections = find_diocese_sections(text)

    # Filter unique diocese names (canonicalize)
    seen_names = set()
    unique_sections = []
    for s in sections:
        canonical = s["name"].strip().upper().rstrip('.')
        if canonical not in seen_names:
            seen_names.add(canonical)
            unique_sections.append(s)
    sections = unique_sections
    print(f"  {len(sections)} unique dioceses after dedup")

    if limit:
        sections = sections[:limit]
        print(f"  Limited to first {limit} dioceses")

    # ── Load/resume checkpoint ──
    completed = set()
    if resume and CHECKPOINT_FILE.exists():
        completed = set(json.loads(CHECKPOINT_FILE.read_text()))
        print(f"  Resuming — {len(completed)} already completed")

    if dry_run:
        print(f"\n── DRY RUN ── {len(sections)} dioceses to process")
        for i, s in enumerate(sections):
            size_kb = len(s["text"]) // 1024
            print(f"  {i+1:3d}. {s['name']:35s} ({size_kb:,} KB)")
        est_cost = len(sections) * 0.015
        print(f"\n  Estimated DeepSeek cost: ~${est_cost:.2f} ({len(sections)} calls)")
        return

    # ── Connect to DB ──
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA foreign_keys=OFF")

    # Clear existing 1865 data
    print("Clearing existing 1865 data...")
    conn.execute("DELETE FROM dir_contacts WHERE entry_id IN (SELECT id FROM dir_entries WHERE directory_year=?)", (DIR_YEAR,))
    conn.execute("DELETE FROM dir_clergy WHERE directory_year=?", (DIR_YEAR,))
    conn.execute("DELETE FROM dir_bishops WHERE directory_year=?", (DIR_YEAR,))
    conn.execute("DELETE FROM dir_entries WHERE directory_year=?", (DIR_YEAR,))
    conn.execute("DELETE FROM dir_provenance WHERE source LIKE 'catholic_dir_1865%'", ())
    conn.commit()

    # ── Process each diocese ──
    all_entries = []
    all_clergy = []
    all_bishops = []
    total_entries = 0
    total_clergy = 0
    total_bishops = 0
    type_counts = {}

    print(f"\nParsing {len(sections)} dioceses via DeepSeek...")
    print(f"(This will take a few minutes. Cost: ~${len(sections)*0.015:.2f})\n")

    for i, section in enumerate(sections):
        name = section["name"]
        if name in completed:
            print(f"  [{i+1}/{len(sections)}] {name:30s} ⏭️  (cached)")
            continue

        sec_text = section["text"]
        sec_clean = re.sub(r'\s+', ' ', sec_text).strip()

        # Truncate to reasonable size (max 8000 chars to keep API responsive)
        max_chars = 8000
        if len(sec_clean) > max_chars:
            sec_clean = sec_clean[:max_chars]

        if len(sec_clean) < 200:
            print(f"  [{i+1}/{len(sections)}] {name:30s} ⚠️  too short ({len(sec_clean)} chars)")
            continue

        print(f"  [{i+1}/{len(sections)}] {name:30s} ({len(sec_clean):,} chars) ...", end=" ", flush=True)

        # Parse via DeepSeek
        result = call_deepseek(PARISH_PROMPT_1865, sec_clean)

        if result and isinstance(result, list):
            for entry in result:
                ename = (entry.get("church_name") or "").strip()
                if not ename:
                    continue

                etype = entry.get("entity_type", "parish")
                city = (entry.get("city") or "").strip()
                state = (entry.get("state") or "").strip()
                address = (entry.get("address") or "").strip()
                clergy_list = entry.get("clergy", [])
                year_founded = entry.get("year_founded")
                notes = entry.get("notes") or ""

                type_counts[etype] = type_counts.get(etype, 0) + 1

                all_entries.append((
                    DIR_YEAR,
                    f"{name}_{len(all_entries)}",
                    ename,
                    city if city else None,
                    state if state else None,
                    name,  # diocese
                    etype,
                    address if address else None,
                    None,  # zip
                    None,  # phone
                    None,  # website
                    None,  # email
                    year_founded,
                    None,  # landmark_type
                    None,  # grid_church_id
                    (notes + f" [OCR source: 1865 Sadlier's Catholic Directory]").strip(),
                    json.dumps(entry, ensure_ascii=False),
                ))

                for c in clergy_list:
                    cname = (c.get("name") or "").strip()
                    ctitle = (c.get("title") or "").strip()
                    if cname:
                        all_clergy.append((len(all_entries)-1, DIR_YEAR, cname, ctitle, None, None, None))
                        total_clergy += 1

                total_entries += 1

            print(f"OK {len(result)} entries")
        else:
            print(f"FAIL - no parseable result")

        # Mark complete
        completed.add(name)

        # Save checkpoint every 5 dioceses
        if (i+1) % 5 == 0:
            CHECKPOINT_FILE.write_text(json.dumps(sorted(completed)), encoding="utf-8")
            conn.commit()  # periodic commit

        # Rate limit
        time.sleep(0.5)

    # ── Also try to parse hierarchy section ──
    print(f"\nLooking for hierarchy section...")
    hier_patterns = [
        "CARDINALS, ARCHBISHOPS, BISHOPS",
        "HIERARCHY OF THE CATHOLIC CHURCH",
        "THE HIERARCHY",
    ]
    for pat in hier_patterns:
        idx = text.find(pat)
        if idx > 0 and idx < len(text) * 0.4:
            hier_text = text[idx:idx+30000]
            hier_clean = re.sub(r'\s+', ' ', hier_text).strip()
            print(f"  Found '{pat}' at pos {idx:,}, parsing...", end=" ", flush=True)
            bishops_result = call_deepseek(HIERARCHY_PROMPT_1865, hier_clean[:12000])
            if bishops_result and isinstance(bishops_result, list):
                for b in bishops_result:
                    all_bishops.append((
                        DIR_YEAR,
                        b.get("name", "").strip(),
                        b.get("title", "").strip() or None,
                        b.get("diocese", "").strip() or None,
                        b.get("bishop_type", "").strip() or None,
                        "historical",
                        None,
                        b.get("consecrated"),
                        b.get("birth_year"),
                        None,
                        b.get("notes", "").strip() or None,
                        json.dumps(b, ensure_ascii=False),
                    ))
                    total_bishops += 1
                print(f"✅ {len(bishops_result)} bishops")
            else:
                print(f"❌ no result")
            break

    # ── Flush all to DB ──
    print(f"\nWriting {total_entries:,} entries + {total_clergy:,} clergy + {total_bishops:,} bishops to DB...")

    # Bulk insert entries
    for chunk_start in range(0, len(all_entries), CHUNK_SIZE):
        chunk = all_entries[chunk_start:chunk_start + CHUNK_SIZE]
        conn.executemany("""
            INSERT INTO dir_entries (directory_year, source_entry_id, name, city,
                state, diocese, entity_type, address, zip, phone, website, email,
                year_founded, landmark_type, grid_church_id, notes, source_raw)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, chunk)

    conn.commit()

    # Get entry IDs for clergy linking
    entry_map = {}
    for row in conn.execute("SELECT source_entry_id, id FROM dir_entries WHERE directory_year=?", (DIR_YEAR,)):
        entry_map[row[0]] = row[1]

    # Bulk insert clergy with real entry_ids
    clergy_with_ids = []
    for temp_eid, year, cname, crole, prefix, suffix, cnotes in all_clergy:
        source_key = f"{sections[min(temp_eid, len(sections)-1)]['name']}_{temp_eid}"
        real_eid = entry_map.get(source_key)
        if real_eid:
            clergy_with_ids.append((real_eid, year, cname, crole, prefix, suffix, cnotes))

    for chunk_start in range(0, len(clergy_with_ids), CHUNK_SIZE):
        chunk = clergy_with_ids[chunk_start:chunk_start + CHUNK_SIZE]
        conn.executemany("""
            INSERT INTO dir_clergy (entry_id, directory_year, name, role, prefix, suffix, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, chunk)

    # Bulk insert bishops
    conn.executemany("""
        INSERT INTO dir_bishops (directory_year, name, title, diocese, bishop_type,
            status, appointed_year, consecrated_year, birth_year, cathedral, notes, source_raw)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, all_bishops)

    # ── Log provenance ──
    conn.execute("""
        INSERT INTO dir_provenance (source, description, entry_count, clergy_count, bishop_count)
        VALUES (?, ?, ?, ?, ?)
    """, (
        "catholic_dir_1865",
        f"Full DeepSeek-parsed import of 1865 Sadlier's Catholic Directory — "
        f"{total_entries:,} entries across {len(sections)} dioceses",
        total_entries,
        total_clergy,
        total_bishops,
    ))
    conn.commit()

    # ── Cleanup checkpoint ──
    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()

    # ── Summary ──
    print(f"\n{'='*60}")
    print(f"✅ 1865 Import Complete")
    print(f"{'='*60}")
    print(f"  Dioceses processed: {len(completed)}")
    print(f"  Entries:    {total_entries:>10,}")
    print(f"  Clergy:     {total_clergy:>10,}")
    print(f"  Bishops:    {total_bishops:>10,}")
    print(f"\nEntity types:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t:25s} {c:>8,}")

    verified = conn.execute("SELECT COUNT(*) FROM dir_entries WHERE directory_year=?", (DIR_YEAR,)).fetchone()[0]
    print(f"\n  Verified in DB: {verified:,} entries")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Import 1865 Catholic Directory via DeepSeek")
    p.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    p.add_argument("--limit", type=int, default=None, help="Limit to first N dioceses")
    p.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    args = p.parse_args()
    import_1865(dry_run=args.dry_run, limit=args.limit, resume=args.resume)
