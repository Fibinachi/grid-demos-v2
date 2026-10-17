#!/usr/bin/env python3
"""
1926 Census of Religious Bodies - Cook County schedule scraper (STAGED, not run).

Acquires the 1,805 Cook County per-congregation schedules from the American
Religious Ecologies project (Roy Rosenzweig Center for History and New Media,
George Mason University; NEH-funded; co-directors Lincoln Mullen, John Turner)
as the 1926 layer for the GRID Cook County longitudinal benchmark.

Method established 2026-10-08 (research stage, verified live):
- No bulk download exists for schedule-level records. The project's /data/
  page offers only three aggregate datasets (denominations list, city-level
  membership, populated places), all on GitHub with DOIs.
- The Omeka S instance (omeka.religiousecologies.org) is retired: every path
  301-redirects to religiousecologies.org. No REST API.
- The only path is a polite scrape of the county browser + per-record pages,
  which carry clean structured transcription fields. Parser below was built
  against the live HTML (verified on record 7211, 2026-10-08).

Targets:
- Browser (canonical county URL, verified 1,805 records, 91 pages @20/page):
    https://religiousecologies.org/census/browser/IL/Cook/
- Record: https://religiousecologies.org/census/record/<id>/
  Fields: title, schedule_id, church_name (denomination), denomination_family,
  census_code, place, county, state, male/female/13+ members, Sunday school
  officers+scholars, clergy (name, college, serving), property & finances
  (edifices, edifice_value, pastors_residence, residence_value, expenses,
  benevolences, total_expenditures), archival schedule image URL.
  NOTE: street addresses appear in the schedule IMAGES where present, not in
  the transcription -- the centroid-bridge geocoding idea will need image
  review, not the text fields.

Run profile: 91 list pages + 1,805 record pages = ~1,896 requests.
At 1.5s politeness delay ~= 48 minutes. Writes to a JSONL staging file only;
nothing touches production. Resume-safe via --resume.

Run on garage (Charles's directive: background jobs on garage):
  python3 1926-cook-scraper.py --out staging/chicago_benchmark/1926_cook_raw.jsonl

After the pull: audit transcription completeness (share of "Unnamed Church"
and missing member counts), then cross-era linkage against 1951/1963/2026.
Cite the project (NEH, Mullen/Turner, RRCHNM) in the benchmark's
data-quality statement.
"""

import argparse, json, os, re, sys, time, html
import requests

BASE = "https://religiousecologies.org"
BROWSER = BASE + "/census/browser/IL/Cook/"
UA = {"User-Agent": "GRID-research-bot/1.0 (academic research; contact charles@gridataset.com)"}
DELAY = 1.5
_SES = requests.Session()
_SES.headers.update(UA)

def fetch(url, retries=4):
    for i in range(retries):
        try:
            r = _SES.get(url, timeout=30)
            if r.status_code == 429 and i < retries - 1:
                time.sleep(10 * (i + 1)); continue
            r.raise_for_status()
            return r.text
        except requests.HTTPError:
            raise
        except Exception:
            if i < retries - 1:
                time.sleep(5); continue
            raise

def clean(t):
    return html.unescape(re.sub(r"<[^>]+>", "", t or "")).strip()

def parse_list_page(page_html):
    ids = re.findall(r'href="/census/record/(\d+)/"', page_html)
    pages = [int(p) for p in re.findall(r"[?&]page=(\d+)", page_html)]
    return ids, max(pages) if pages else 1

def th_field(page_html, label):
    """Extract <td> value for a <th>LABEL</th> row (label may have nested markup)."""
    m = re.search(r"<th[^>]*>.*?" + re.escape(label) + r".*?</th>\s*<td[^>]*>(.*?)</td>",
                  page_html, re.S | re.I)
    return clean(m.group(1)) if m else None

def parse_record(rid, page_html):
    rec = {"record_id": rid, "url": f"{BASE}/census/record/{rid}/"}
    m = re.search(r"<h1[^>]*>(.*?)</h1>", page_html, re.S)
    rec["title"] = clean(m.group(1)) if m else None
    m = re.search(r"Record ID:\s*(\d+)\s*[•·]\s*Schedule ID:\s*(\d+)", page_html)
    if m:
        rec["schedule_id"] = m.group(2)
    for label, key in [("Name", "church_name"),
                       ("Denomination Family", "denomination_family"),
                       ("Census Code", "census_code"),
                       ("Populated Place", "place"),
                       ("County", "county"),
                       ("State", "state"),
                       ("Number of Edifices", "edifices"),
                       ("Edifice Value", "edifice_value"),
                       ("Pastor's Residence", "pastors_residence"),
                       ("Residence Value", "residence_value"),
                       ("Expenses", "expenses"),
                       ("Benevolences", "benevolences"),
                       ("Total Expenditures", "total_expenditures")]:
        rec[key] = th_field(page_html, label)
    # Membership stat boxes
    for num, lab in re.findall(
            r'<span class="stat-number">([\d,]+)</span>\s*<div class="stat-label">([^<]+)</div>',
            page_html):
        lab = lab.strip().lower()
        if lab == "male members": rec["male_members"] = num
        elif lab == "female members": rec["female_members"] = num
        elif "13" in lab: rec["members_13plus"] = num
    # Sunday school row
    m = re.search(r"<td[^>]*>\s*Sunday School\s*</td>\s*<td[^>]*>([\d,]*)</td>\s*<td[^>]*>([\d,]*)</td>",
                  page_html, re.I)
    if m:
        rec["ss_officers"], rec["ss_scholars"] = m.group(1), m.group(2)
    # Clergy blocks
    clergy = []
    for cm in re.finditer(
            r'<h3 class="text-lg font-semibold text-content-primary">([^<]+)</h3>(.*?)</div>\s*</div>\s*</div>',
            page_html, re.S):
        block = cm.group(2)
        college = re.search(r"College:</span>\s*<span[^>]*>([^<]*)</span>", block)
        serving = re.search(r"Currently Serving:</span>\s*<span[^>]*>([^<]*)</span>", block)
        clergy.append({"name": clean(cm.group(1)),
                       "college": clean(college.group(1)) if college else None,
                       "serving": clean(serving.group(1)) if serving else None})
    rec["clergy"] = clergy
    m = re.search(r'href="(https://religiousecologies\.org/media/census_images/originals/[^"]+?\.jpg)"',
                  page_html)
    rec["schedule_image"] = m.group(1) if m else None
    return rec

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    done = set()
    if args.resume and os.path.exists(args.out):
        with open(args.out) as f:
            for line in f:
                try: done.add(str(json.loads(line)["record_id"]))
                except Exception: pass
    print(f"resuming with {len(done)} records already pulled", flush=True)

    first = fetch(BROWSER)
    ids, last_page = parse_list_page(first)
    m = re.search(r"([\d,]+) religious census records found", first)
    print(f"browser reports {m.group(1) if m else '?'} records, {last_page} pages", flush=True)

    all_ids = []
    for p in range(1, last_page + 1):
        page_html = first if p == 1 else fetch(f"{BROWSER}?page={p}")
        ids, _ = parse_list_page(page_html)
        all_ids.extend(i for i in ids if i not in all_ids)
        if p > 1: time.sleep(DELAY)
    print(f"{len(all_ids)} record ids collected", flush=True)

    todo = [i for i in all_ids if i not in done]
    print(f"{len(todo)} records to pull (~{len(todo)*DELAY/60:.0f} min)", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "a") as f:
        for n, rid in enumerate(todo, 1):
            try:
                f.write(json.dumps(parse_record(rid, fetch(f"{BASE}/census/record/{rid}/"))) + "\n")
                f.flush()
            except Exception as e:
                print(f"FAILED {rid}: {e}", file=sys.stderr, flush=True)
            if n % 100 == 0: print(f"{n}/{len(todo)}", flush=True)
            time.sleep(DELAY)
    print("done", flush=True)

if __name__ == "__main__":
    main()
