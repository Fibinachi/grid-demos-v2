#!/usr/bin/env python3
"""
Common Crawl Church Enrichment v2 — DuckDB + S3 Parquet
========================================================
Queries Common Crawl's URL index (Parquet on S3) directly via DuckDB for:
  A) Church domain candidates — find websites by guessing domains and checking CC
  B) Denom directory domains — extract all church listings from known directory sites
  C) People extraction — pastors, rectors, secretaries from page titles + WAT

Speed design:
  - Batch 500 domains at once into a single DuckDB query
  - Each query is a single Parquet scan with predicate pushdown (fast!)
  - Parallel workers for WAT download and live HTTP checks
  - S3 requester-pays enabled (user's own key pays, ~$0.004/GB)

Usage:
    python scripts/enrichment/common_crawl_enrich.py --limit 5000
    python scripts/enrichment/common_crawl_enrich.py --csv chunk.csv --output results.csv

Requires: pip install duckdb
"""
import csv, gzip, html, io, json, os, re, sys, time, sqlite3, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urlparse

try:
    import duckdb
except ImportError:
    print("Install duckdb: pip install duckdb")
    sys.exit(1)

# ── Config ──
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
for _ in range(5):
    if os.path.exists(os.path.join(PROJECT_DIR, "churches.db")):
        if os.path.getsize(os.path.join(PROJECT_DIR, "churches.db")) > 1000000:
            break
    parent = os.path.dirname(PROJECT_DIR)
    if parent == PROJECT_DIR:
        break
    PROJECT_DIR = parent

DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) < 1000000:
    cwd_db = os.path.join(os.getcwd(), "churches.db")
    if os.path.exists(cwd_db) and os.path.getsize(cwd_db) > 1000000:
        DB_PATH = cwd_db

# CC Parquet path — latest crawl
CC_BASE = "s3://commoncrawl/cc-index/table/cc-main/warc"
CC_REGION = "us-east-1"

# Denom directory domains to extract ALL pages from
DENOM_DIRECTORIES = {
    "episcopalassetmap.org": "episcopal",
    "findachurch.umc.org": "umc",
    "elca.org": "elca",
    "locator.lds.org": "lds",
    "adventist.org": "sda",
    "sbc.net": "sbc",
    "ag.org": "ag",
    "episcopalchurch.org": "episcopal",
    "parishesonline.com": "catholic",
    "massfinder.com": "catholic",
    "churchesofchrist.org": "coc",
    "churchofgod.org": "cog",
}

MAX_WORKERS = 20

STOP_WORDS = {'THE', 'OF', 'A', 'AN', 'AND', 'IN', 'AT'}
ABBREVS = {
    'FIRST': 'f', 'BAPTIST': 'b', 'CHURCH': 'c', 'METHODIST': 'm',
    'LUTHERAN': 'l', 'PRESBYTERIAN': 'p', 'PENTECOSTAL': 'p',
    'CATHOLIC': 'c', 'EPISCOPAL': 'e', 'CHRISTIAN': 'c',
    'ASSEMBLIES': 'a', 'GOSPEL': 'g', 'CALVARY': 'c', 'CHAPEL': 'c',
    'NAZARENE': 'n', 'MISSIONARY': 'm', 'ALLIANCE': 'a',
    'INDEPENDENT': 'i', 'BIBLE': 'b', 'FELLOWSHIP': 'f',
}
SKIP_DOMAINS = {
    "wikipedia.org", "facebook.com", "yelp.com", "yellowpages.com",
    "google.com", "faithstreet.com", "usachurches.org",
    "nonprofitlocator.org", "charitynavigator.org", "guidestar.org",
    "linkedin.com", "twitter.com", "instagram.com", "youtube.com",
    "bbb.org", "manta.com", "whitepages.com", "chamberofcommerce.com",
    "opengovus.com", "duckduckgo.com", "bing.com",
}

# ── People extraction patterns ──
PEOPLE_RE = re.compile(
    r'(?:^|\||[-u2013u2014u2022])\s*(?:Rev\.?\s*|Reverend\s+|Pastor\s+|Rector\s+|'
    r'Fr\.?\s+|Father\s+|Dr\.?\s+|Brother\s+|Br\.?\s+|'
    r'Minister\s+|Deacon\s+|Deaconess\s+|Elder\s+|Bishop\s+|'
    r'Canon\s+|Vicar\s+|Archdeacon\s+|Chaplain\s+|'
    r'Administrator\s+|Secretary\s+|Clerk\s+|Treasurer\s+|'
    r'Director\s+|Coordinator\s+|'
    r'Lead Pastor\s+|Senior Pastor\s+|Youth Pastor\s+|Executive Pastor\s+|'
    r'Worship Pastor\s+|Children.s Pastor\s+|Music Director\s+|'
    r'Office Manager\s+|Business Manager\s+|'
    r'Associate Pastor\s+|Assistant Pastor\s+)'
    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
    re.IGNORECASE
)


# ── Domain generation ──

def generate_guesses(name, city, state):
    if not name:
        return []
    n = name.strip().upper()
    city_clean = (city or "").strip().lower().replace(" ", "").replace(".", "").replace("'", "")
    name_clean = re.sub(r'[^A-Z0-9 ]', '', n).strip()
    words = name_clean.split()
    sig_words = [w for w in words if w not in STOP_WORDS and len(w) > 1]
    if not sig_words:
        return []
    guesses = set()
    full = '-'.join(w.lower() for w in sig_words[:4])
    if full:
        for tld in ['.org', '.com', '.church']:
            guesses.add(full + tld)
            if city_clean:
                guesses.add(full + city_clean + tld)
    abbr = ''.join(ABBREVS.get(w, w[0].lower()) for w in sig_words[:3])
    if abbr and len(abbr) <= 6 and city_clean:
        guesses.add(abbr + city_clean + '.org')
        guesses.add(abbr + city_clean + '.com')
    if city_clean and full:
        guesses.add(city_clean + full + '.org')
        guesses.add(city_clean + full + '.com')
    return list(guesses)[:8]


def extract_people(text):
    if not text:
        return []
    found = []
    for m in PEOPLE_RE.finditer(text):
        name = m.group(1).strip()
        full = m.group(0).strip()
        role = full.split(name)[0].strip()
        if name and 5 < len(name) < 60:
            found.append(f"{name} ({role})")
    return found


def page_title_score(title, church_name):
    """Score how well a page title matches a church name (via gw_filters.web)."""
    from gw_filters.web import title_score
    return int(title_score(title, church_name) * 100)
    if r >= 0.8: return 85
    if r >= 0.5: return 60
    if matches >= 2: return 40
    if matches >= 1: return 15
    return 0


def check_live(domain):
    for proto in ['https', 'http']:
        try:
            req = urllib.request.Request(f"{proto}://{domain}", method='HEAD',
                headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                return f"{proto}://{domain}"
        except Exception:
            continue
    return None


# ── CC DuckDB Query Engine ──

class CCEngine:
    def __init__(self):
        self.con = duckdb.connect()
        self.con.execute("INSTALL httpfs; LOAD httpfs;")
        self.con.execute(f"SET s3_region='{CC_REGION}';")
        self.con.execute("SET s3_requester_pays=true;")
        self.con.execute("SET s3_use_ssl=true;")

        # Read AWS creds: env vars first, then ~/.aws/credentials
        creds = {}
        for env_key, duck_key in [
            ("AWS_ACCESS_KEY_ID", "s3_access_key_id"),
            ("AWS_SECRET_ACCESS_KEY", "s3_secret_access_key"),
            ("AWS_SESSION_TOKEN", "s3_session_token"),
        ]:
            val = os.environ.get(env_key)
            if val:
                creds[duck_key] = val

        if "s3_access_key_id" not in creds:
            aws_creds = os.path.expanduser("~/.aws/credentials")
            if os.path.exists(aws_creds):
                import configparser
                cfg = configparser.ConfigParser()
                cfg.read(aws_creds)
                profile = os.environ.get("AWS_PROFILE", "default")
                if profile in cfg:
                    creds["s3_access_key_id"] = cfg[profile].get("aws_access_key_id", "")
                    creds["s3_secret_access_key"] = cfg[profile].get("aws_secret_access_key", "")
                    if cfg[profile].get("aws_session_token"):
                        creds["s3_session_token"] = cfg[profile]["aws_session_token"]

        for duck_key, val in creds.items():
            if val:
                safe_val = val.replace("'", "''")
                self.con.execute(f"SET {duck_key}='{safe_val}';")

        # Auto-detect latest crawl
        self.cc_path = self._detect_latest_crawl()
        self._warm = False

    def _detect_latest_crawl(self):
        """Find the latest crawl directory with Parlamat files."""
        try:
            import boto3
            s3 = boto3.client('s3', region_name=CC_REGION)
            paginator = s3.get_paginator('list_objects_v2')
            crawls = []
            for page in paginator.paginate(Bucket='commoncrawl', Prefix='cc-index/table/cc-main/warc/crawl=', Delimiter='/'):
                for p in page.get('CommonPrefixes', []):
                    crawl = p['Prefix'].split('crawl=')[1].rstrip('/')
                    crawls.append(crawl)
            # Sort by crawl name (CC-MAIN-YYYY-NN format)
            crawls.sort()
            latest = crawls[-1]
            path = f"{CC_BASE}/crawl={latest}/subset=warc/*.parquet"
            print(f"  Latest crawl: {latest}")
            return path
        except Exception as e:
            # Fallback to hardcoded latest
            print(f"  WARN: Crawl detection failed: {e}, using fallback")
            return f"{CC_BASE}/crawl=CC-MAIN-2026-21/subset=warc/*.parquet"

    def warm_cache(self):
        if not self._warm:
            try:
                self.con.execute(f"""
                    SELECT COUNT(*) FROM read_parquet('{self.cc_path}', filename=true)
                    LIMIT 1
                """).fetchone()
                self._warm = True
                return True
            except Exception as e:
                print(f"  WARN: CC Parquet warm failed: {e}")
                return False
        return True

    def query_domains_batch(self, domains, batch_size=500):
        if not domains:
            return []
        results = []
        ccp = self.cc_path
        for i in range(0, len(domains), batch_size):
            batch = domains[i:i+batch_size]
            vals_list = []
            for d in batch:
                safe = d.replace("'", "''")
                vals_list.append(f"('{safe}')")
            vals = ", ".join(vals_list)

            try:
                rows = self.con.execute(f"""
                    SELECT url, url_host_registered_domain,
                           content_languages, fetch_status,
                           warc_filename, warc_record_offset, warc_record_length
                    FROM read_parquet('{ccp}', filename=true)
                    WHERE url_host_registered_domain IN (
                        SELECT col0 FROM (VALUES {vals}) t
                    )
                    AND fetch_status = 200
                    AND content_languages LIKE '%eng%'
                    LIMIT 50000
                """).fetchall()

                for r in rows:
                    results.append({
                        "url": r[0] or "",
                        "domain": r[1] or "",
                        "lang": r[2] or "",
                        "status": r[3],
                        "warc_file": r[4] or "",
                        "warc_offset": r[5] or 0,
                        "warc_length": r[6] or 0,
                    })
            except Exception as e:
                print(f"  DBG: batch error at offset {i}: {e}")

            if (i // batch_size) % 10 == 0 and i > 0:
                print(f"    scanned {i+batch_size:,} domains, {len(results)} matches")

        return results

    def query_denom_directory(self, domain, label):
        try:
            safe = domain.replace("'", "''")
            ccp = self.cc_path
            rows = self.con.execute(f"""
                SELECT url, url_host_registered_domain,
                       content_languages, fetch_status,
                       warc_filename, warc_record_offset, warc_record_length
                FROM read_parquet('{ccp}', filename=true)
                WHERE url_host_registered_domain = '{safe}'
                AND fetch_status = 200
                AND content_languages LIKE '%eng%'
                AND content_mime_type LIKE '%html%'
                LIMIT 100000
            """).fetchall()

            results = []
            for r in rows:
                results.append({
                    "url": r[0] or "",
                    "domain": r[1] or "",
                    "lang": r[2] or "",
                    "status": r[3],
                    "warc_file": r[4] or "",
                    "warc_offset": r[5] or 0,
                    "warc_length": r[6] or 0,
                    "denom_label": label,
                })
            return results
        except Exception as e:
            print(f"  DBG: denom error {domain}: {e}")
            return []

    def close(self):
        self.con.close()


# ── WAT download (for deeper metadata) ──

CC_WAT_HOST = "https://data.commoncrawl.org"

def fetch_wat_metadata(warc_file, offset, length):
    if not warc_file or not offset or not length:
        return None
    try:
        wat_path = (warc_file
                    .replace("crawl-data/", "crawl-data/", 1)
                    .replace("/warc/", "/wat/")
                    .replace(".warc.gz", ".wat.gz"))
        url = f"{CC_WAT_HOST}/{wat_path}"
        import requests
        headers = {"Range": f"bytes={int(offset)}-{int(offset)+int(length)-1}"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 206:
            data = gzip.decompress(resp.content)
            return json.loads(data.decode('utf-8', errors='replace'))
    except:
        pass
    return None


def parse_wat(wat):
    result = {"emails": [], "phones": [], "social": [], "people": []}
    if not wat:
        return result
    try:
        pl = wat.get("Envelope", {}).get("Payload-Metadata", {})
        hr = pl.get("HTTP-Response-Metadata", {})
        hh = hr.get("HTML-Metadata", {})

        for k, v in hh.get("Meta", {}).items():
            if k.lower() in ("description", "keywords", "dc.description"):
                for p in extract_people(v):
                    if p not in result["people"]:
                        result["people"].append(p)

        for link in hh.get("Links", []):
            href = link.get("url", "") or ""
            text = link.get("text", "") or ""
            dom = urlparse(href).netloc.lower()

            if href.startswith("mailto:"):
                e = href[7:].split("?")[0].strip()
                if "@" in e and e not in result["emails"]:
                    result["emails"].append(e)

            if any(s in dom for s in ["facebook", "fb.com"]):
                result["social"].append(f"facebook:{href}")
            elif "instagram" in dom:
                result["social"].append(f"instagram:{href}")
            elif "youtube" in dom or "youtu.be" in dom:
                result["social"].append(f"youtube:{href}")
            elif "twitter" in dom or "x.com" in dom:
                result["social"].append(f"twitter:{href}")

            if text:
                for p in extract_people(text):
                    if p not in result["people"]:
                        result["people"].append(p)

        desc = hh.get("Meta", {}).get("description", "") + " " + hh.get("Meta", {}).get("keywords", "")
        for ph in re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', desc):
            c = re.sub(r'[^\d]', '', ph)
            if len(c) == 10 and c not in result["phones"]:
                result["phones"].append(c)
    except:
        pass
    return result


# ── MAIN ──

CSV_FIELDS = [
    "id", "name", "city", "state",
    "source_type", "denom_label",
    "cc_domain", "cc_url", "cc_page_title",
    "cc_verified", "cc_confidence",
    "cc_emails", "cc_phones", "cc_social",
    "cc_people_names",
    "live_url",
]


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", help="Input CSV (id,name,city,state)")
    parser.add_argument("--output", default="data/cc_results.csv")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--cc-only", action="store_true", help="Skip denom directories")
    parser.add_argument("--denom-only", action="store_true", help="Only denom directories")
    parser.add_argument("--db", default=DB_PATH)
    args = parser.parse_args()

    print("=" * 60)
    print("Common Crawl v2 - DuckDB + S3 Parquet")
    print("=" * 60)

    workers = args.workers

    print("\n[1] Initializing DuckDB + S3 CC connection...")
    cc = CCEngine()
    if not cc.warm_cache():
        print("  FAILED: Cannot access CC Parquet. Check AWS credentials.")
        cc.close()
        return

    print("  CC Parquet ready: " + cc.cc_path[:80] + "...")

    print("\n[2] Loading churches...")
    churches = []

    if args.csv:
        with open(args.csv, 'r', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                churches.append({
                    "id": r.get("id", r.get("church_id", "")),
                    "name": r.get("name", ""),
                    "city": r.get("city", ""),
                    "state": r.get("state", ""),
                })
    else:
        db = sqlite3.connect(args.db)
        q = "SELECT id, name, city, state FROM churches WHERE (website IS NULL OR website = '') ORDER BY id"
        if args.limit:
            q += f" LIMIT {args.limit}"
        churches = [{"id": str(r[0]), "name": r[1], "city": r[2], "state": r[3]} for r in db.execute(q).fetchall()]
        db.close()

    print(f"  Loaded {len(churches):,} churches needing websites")
    if not churches:
        cc.close()
        return

    all_results = []

    # Step A: Denom directory extraction
    if not args.cc_only:
        print(f"\n[3A] Querying {len(DENOM_DIRECTORIES)} denom directory domains...")
        for domain, label in sorted(DENOM_DIRECTORIES.items()):
            pages = cc.query_denom_directory(domain, label)
            if pages:
                print(f"  {label:12s} {domain:35s} -> {len(pages):,} pages")
                for p in pages[:2]:
                    print(f"       {p.get('url', '')[:80]}")
                if len(pages) > 2:
                    print(f"       ... +{len(pages)-2} more")

                for p in pages:
                    all_results.append({
                        "id": "", "name": "", "city": "", "state": "",
                        "source_type": "denom_directory",
                        "denom_label": label,
                        "cc_domain": p.get("domain", ""),
                        "cc_url": p.get("url", ""),
                        "cc_page_title": "",
                        "cc_verified": 1,
                        "cc_confidence": 80,
                        "cc_emails": "", "cc_phones": "", "cc_social": "",
                        "cc_people_names": "",
                        "live_url": "",
                    })
            else:
                print(f"  {label:12s} {domain:35s} -> 0 pages")

    # Step B: Domain candidate matching
    if not args.denom_only:
        print(f"\n[3B] Generating domain candidates for {len(churches):,} churches...")
        all_domains = []
        church_domains = {}

        for c in churches:
            guesses = generate_guesses(c["name"], c["city"], c["state"])
            for d in guesses:
                if any(s in d for s in SKIP_DOMAINS):
                    continue
                dl = d.lower()
                if dl not in church_domains:
                    church_domains[dl] = []
                    all_domains.append(dl)
                church_domains[dl].append(c["id"])

        print(f"  {len(all_domains):,} unique domain candidates")

        print(f"  Querying CC index (batch=500)...")
        cc_matches = cc.query_domains_batch(all_domains, batch_size=500)
        print(f"  Found {len(cc_matches):,} CC matches")

        print(f"  Matching results to churches...")
        domain_to_records = {}
        for m in cc_matches:
            dom = m["domain"].lower()
            if dom not in domain_to_records:
                domain_to_records[dom] = []
            domain_to_records[dom].append(m)

        matched_ids = set()
        for c in churches:
            guesses = generate_guesses(c["name"], c["city"], c["state"])
            if not guesses:
                continue

            best = None
            for d in guesses:
                dl = d.lower()
                if dl in domain_to_records:
                    best = (dl, domain_to_records[dl][0])
                    break

            if best:
                matched_ids.add(c["id"])
                domain_name, rec = best
                # Try WAT to get title/people/emails for verified match
                wat_title = ""
                wat_people = ""
                wat_emails = ""
                wat_social = ""
                wat_phones = ""

                if rec.get("warc_file") and rec.get("warc_offset") and rec.get("warc_length"):
                    wat = fetch_wat_metadata(
                        rec["warc_file"], rec["warc_offset"], rec["warc_length"]
                    )
                    if wat:
                        meta = parse_wat(wat)
                        # Extract title from WAT
                        try:
                            hr = wat.get("Envelope", {}).get("Payload-Metadata", {}).get("HTTP-Response-Metadata", {})
                            wat_title = hr.get("HTML-Metadata", {}).get("Meta", {}).get("title", "")
                            if not wat_title:
                                wat_title = hr.get("HTML-Metadata", {}).get("Meta", {}).get("Title", "")
                        except:
                            pass
                        if meta["emails"]:
                            wat_emails = "; ".join(meta["emails"][:5])
                        if meta["phones"]:
                            wat_phones = "; ".join(meta["phones"][:3])
                        if meta["social"]:
                            wat_social = "; ".join(meta["social"][:5])
                        if meta["people"]:
                            wat_people = "; ".join(meta["people"][:5])

                all_results.append({
                    "id": c["id"],
                    "name": c["name"],
                    "city": c["city"],
                    "state": c["state"],
                    "source_type": "domain_match",
                    "denom_label": "",
                    "cc_domain": domain_name,
                    "cc_url": rec.get("url", ""),
                    "cc_page_title": wat_title,
                    "cc_verified": 1 if wat_title else 0,
                    "cc_confidence": 70 if wat_title else 50,
                    "cc_emails": wat_emails,
                    "cc_phones": wat_phones,
                    "cc_social": wat_social,
                    "cc_people_names": wat_people,
                    "live_url": "",
                })

        print(f"  Matched {len(matched_ids):,} churches via CC")

        # Step C: Live HTTP check for ALL unmatched + also verify CC-matched with live
        all_to_check = [c for c in churches]
        print(f"\n[3C] Live HTTP check + title verification for {len(all_to_check):,} churches...")
        live_found = 0
        live_verified = 0

        def check_one(c):
            for d in generate_guesses(c["name"], c["city"], c["state"]):
                if any(s in d for s in SKIP_DOMAINS):
                    continue
                live = check_live(d)
                if live:
                    # Try to get page title
                    title = ""
                    try:
                        req = urllib.request.Request(live, headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                            "Accept": "text/html",
                        })
                        with urllib.request.urlopen(req, timeout=5) as resp:
                            raw = resp.read(100 * 1024)
                            text = raw.decode("utf-8", errors="replace")
                            m = re.search(r'<title[^>]*>(.*?)</title>', text, re.IGNORECASE | re.DOTALL)
                            if m:
                                title = html.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()
                    except:
                        pass
                    score = page_title_score(title, c["name"])
                    return {
                        "id": c["id"], "name": c["name"], "city": c["city"],
                        "state": c["state"], "live_url": live, "domain": d,
                        "title": title, "score": score,
                    }
            return None

        with ThreadPoolExecutor(max_workers=min(workers, 100)) as pool:
            futures = {pool.submit(check_one, c): c for c in all_to_check}
            done = 0
            for f in as_completed(futures):
                done += 1
                r = f.result()
                if r:
                    live_found += 1
                    if r["score"] >= 60:
                        live_verified += 1
                    # Add/update result
                    existing = None
                    for i, existing_r in enumerate(all_results):
                        if existing_r.get("id") == r["id"]:
                            existing = i
                            break
                    row = {
                        "id": r["id"], "name": r["name"], "city": r["city"],
                        "state": r["state"],
                        "source_type": "live_check",
                        "denom_label": "",
                        "cc_domain": r["domain"],
                        "cc_url": r["live_url"],
                        "cc_page_title": r["title"],
                        "cc_verified": 1 if r["score"] >= 60 else 0,
                        "cc_confidence": r["score"],
                        "cc_emails": "", "cc_phones": "", "cc_social": "",
                        "cc_people_names": "",
                        "live_url": r["live_url"],
                    }
                    if existing is not None:
                        # Update existing with live data
                        all_results[existing]["live_url"] = r["live_url"]
                        all_results[existing]["cc_url"] = r["live_url"]
                        all_results[existing]["cc_page_title"] = r["title"]
                        all_results[existing]["cc_verified"] = 1 if r["score"] >= 60 else all_results[existing]["cc_verified"]
                        all_results[existing]["cc_confidence"] = max(r["score"], all_results[existing].get("cc_confidence", 0))
                    else:
                        all_results.append(row)
                if done % 5000 == 0:
                    print(f"    live: {done:,}/{len(all_to_check):,}, found {live_found:,}, verified {live_verified:,}")

        print(f"  Live check: {live_found:,} domains found, {live_verified:,} title-verified")

    # Write output
    print(f"\n[4] Writing {len(all_results):,} results to {args.output}...")
    with open(args.output, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction='ignore')
        w.writeheader()
        w.writerows(all_results)

    denom_count = sum(1 for r in all_results if r["source_type"] == "denom_directory")
    domain_count = sum(1 for r in all_results if r["source_type"] == "domain_match")
    live_count = sum(1 for r in all_results if r["source_type"] == "live_check")
    people_count = sum(1 for r in all_results if r["cc_people_names"])

    print(f"\n{'='*50}")
    print(f"RESULTS SUMMARY")
    print(f"{'='*50}")
    print(f"  Denom directory pages: {denom_count:,}")
    print(f"  Domain matches:        {domain_count:,}")
    print(f"  Live-only matches:     {live_count:,}")
    print(f"  With people names:     {people_count:,}")
    print(f"  Total records:         {len(all_results):,}")

    cc.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
