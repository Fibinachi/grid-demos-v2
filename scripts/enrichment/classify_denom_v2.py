#!/usr/bin/env python3
"""
Website Denomination Detector — Subprocess fetch version
=========================================================
Same as classify_denom_from_web.py but uses subprocess for each
URL fetch with a hard timeout that actually kills hung processes.
"""
import sqlite3, os, sys, re, json, subprocess, time
from datetime import datetime
from collections import Counter

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
for _ in range(5):
    dbpath = os.path.join(PROJECT_DIR, "churches.db")
    if os.path.exists(dbpath) and os.path.getsize(dbpath) > 1024:
        break
    parent = os.path.dirname(PROJECT_DIR)
    if parent == PROJECT_DIR:
        break
    PROJECT_DIR = parent

DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GrantWizard/1.0"
DELAY = 0.05

# Denomination rules copied from main classifier
DENOM_RULES = [
    (["ROMAN CATHOLIC", "ROMAN CATHOLIC CHURCH"], "Roman Catholic Church"),
    ([" CATHOLIC CHURCH", " CATHOLIC PARISH", " CATHOLIC "], "Roman Catholic Church"),
    (["SOUTHERN BAPTIST"], "Southern Baptist Convention"),
    (["MISSIONARY BAPTIST"], "Missionary Baptist"),
    (["INDEPENDENT BAPTIST"], "Independent Baptist"),
    (["FREE WILL BAPTIST"], "Free Will Baptist"),
    (["PRIMITIVE BAPTIST"], "Primitive Baptist"),
    (["NATIONAL BAPTIST CONVENTION"], "National Baptist Convention USA"),
    (["AMERICAN BAPTIST CHURCH"], "American Baptist Churches USA"),
    (["PROGRESSIVE BAPTIST"], "Progressive National Baptist Convention"),
    (["FULL GOSPEL BAPTIST"], "Full Gospel Baptist Church Fellowship"),
    ([" BAPTIST "], "Baptist (unspecified)"),
    (["UNITED METHODIST"], "United Methodist Church"),
    (["FREE METHODIST"], "Free Methodist Church"),
    (["AFRICAN METHODIST EPISCOPAL ZION", "AME ZION"], "African Methodist Episcopal Zion Church"),
    (["AFRICAN METHODIST EPISCOPAL", "AME CHURCH"], "African Methodist Episcopal Church"),
    (["CHRISTIAN METHODIST EPISCOPAL", "CME CHURCH"], "Christian Methodist Episcopal Church"),
    (["WESLEYAN CHURCH"], "Wesleyan Church"),
    ([" METHODIST "], "United Methodist Church"),
    (["LUTHERAN CHURCH MISSOURI SYNOD", "MISSOURI SYNOD", "LCMS"], "Lutheran Church--Missouri Synod"),
    (["EVANGELICAL LUTHERAN CHURCH", "ELCA"], "Evangelical Lutheran Church in America"),
    (["WISCONSIN EVANGELICAL LUTHERAN", "WELS"], "Wisconsin Evangelical Lutheran Synod"),
    (["LUTHERAN CHURCH"], "Lutheran (unspecified)"),
    (["PRESBYTERIAN CHURCH IN AMERICA", "PCA CHURCH"], "Presbyterian Church in America"),
    (["PRESBYTERIAN CHURCH USA", "PRESBYTERIAN CHURCH U.S.A.", "PCUSA"], "Presbyterian Church (U.S.A.)"),
    (["CUMBERLAND PRESBYTERIAN"], "Cumberland Presbyterian"),
    (["ORTHODOX PRESBYTERIAN", "OPC"], "Orthodox Presbyterian Church"),
    (["ASSOCIATE REFORMED PRESBYTERIAN", "ARPC"], "Associate Reformed Presbyterian Church"),
    (["EVANGELICAL PRESBYTERIAN", "EPC"], "Evangelical Presbyterian Church"),
    (["REFORMED PRESBYTERIAN"], "Reformed Presbyterian Church"),
    ([" PRESBYTERIAN "], "Presbyterian Church (U.S.A.)"),
    (["EPISCOPAL CHURCH", " EPISCOPAL "], "Episcopal Church"),
    (["ANGLICAN CHURCH", "ANGLICAN"], "Anglican Church"),
    (["ASSEMBLIES OF GOD"], "Assemblies of God"),
    (["CHURCH OF GOD IN CHRIST", "COGIC"], "Church of God in Christ"),
    ([" PENTECOSTAL "], "Pentecostal (unspecified)"),
    (["FOURSQUARE CHURCH", "FOURSQUARE GOSPEL"], "Foursquare Church"),
    (["CHURCH OF GOD OF PROPHECY", "COGOP"], "Church of God of Prophecy"),
    (["CHURCH OF GOD"], "Church of God (Cleveland, TN)"),
    (["CHURCHES OF CHRIST"], "Churches of Christ"),
    (["CHURCH OF CHRIST"], "Churches of Christ"),
    (["SEVENTH-DAY ADVENTIST", "SEVENTH DAY ADVENTIST"], "Seventh-day Adventist"),
    (["ADVENTIST CHURCH"], "Seventh-day Adventist"),
    (["CHURCH OF THE NAZARENE", " NAZARENE "], "Church of the Nazarene"),
    (["UNITED CHURCH OF CHRIST", "UCC CHURCH"], "United Church of Christ"),
    (["CHRISTIAN CHURCH DISCIPLES", "DISCIPLES OF CHRIST"], "Christian Church (Disciples of Christ)"),
    (["CHRISTIAN CHURCH"], "Christian Church (Disciples of Christ)"),
    (["REFORMED CHURCH IN AMERICA", "RCA CHURCH"], "Reformed Church in America"),
    (["CHRISTIAN REFORMED CHURCH", "CRC CHURCH"], "Christian Reformed Church"),
    (["EVANGELICAL FREE CHURCH", "EFCA"], "Evangelical Free Church of America"),
    (["EVANGELICAL COVENANT CHURCH"], "Evangelical Covenant Church"),
    (["SALVATION ARMY"], "Salvation Army"),
    (["CALVARY CHAPEL"], "Calvary Chapel"),
    (["MENNONITE CHURCH", " MENNONITE "], "Mennonite (unspecified)"),
    (["CHURCH OF THE BRETHREN"], "Church of the Brethren"),
    (["CHURCH OF JESUS CHRIST OF LATTER", "LDS CHURCH", "MORMON"], "The Church of Jesus Christ of Latter-day Saints"),
    (["JEHOVAH WITNESS"], "Jehovah's Witnesses"),
    (["UNITARIAN UNIVERSALIST", " UNITARIAN "], "Unitarian Universalist"),
    (["CHRISTIAN SCIENCE"], "Christian Science"),
    (["RELIGIOUS SOCIETY OF FRIENDS", "QUAKER"], "Religious Society of Friends (Quakers)"),
    ([" BIBLE CHURCH"], "Bible Church (unspecified)"),
    (["NON-DENOMINATIONAL", "NONDENOMINATIONAL"], "Non-Denominational"),
    (["COMMUNITY CHURCH"], "Community Church (unspecified)"),
]

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def fetch_url_subprocess(url, timeout=6):
    """Fetch a URL via subprocess so we can hard-kill if it hangs."""
    script = f"""
import urllib.request, sys
try:
    r = urllib.request.Request({repr(url)}, headers={{"User-Agent": {repr(UA)}, "Accept": "text/html"}})
    with urllib.request.urlopen(r, timeout={timeout}) as f:
        sys.stdout.buffer.write(f.read(100000))
except Exception:
    pass
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, timeout=timeout + 2,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout.decode("utf-8", "replace")
        return None
    except subprocess.TimeoutExpired:
        return None

def extract_denom_from_jsonld(html):
    found = []
    for ld_text in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE):
        try:
            data = json.loads(ld_text)
            def crawl(obj, depth=0):
                if depth > 5:
                    return
                if isinstance(obj, dict):
                    for key in ['denomination', 'religiousDenomination', 'affiliation', 'parentOrganization']:
                        if key in obj and isinstance(obj[key], str) and len(obj[key]) > 3:
                            found.append(obj[key].strip())
                    for v in obj.values():
                        crawl(v, depth + 1)
                elif isinstance(obj, list):
                    for item in obj[:10]:
                        crawl(item, depth + 1)
            crawl(data)
        except:
            pass
    return found

def extract_denom_from_body(html):
    body_start = html.lower().find("<body")
    body_end = html.lower().find("</body>")
    if body_start >= 0 and body_end > body_start:
        body = html[body_start:body_end].upper()
    else:
        body = html.upper()
    for keywords, label in DENOM_RULES:
        for kw in keywords:
            if f" {kw} " in body or body.startswith(kw + " ") or body.endswith(" " + kw):
                return label
    return None

def classify_website(url):
    html = fetch_url_subprocess(url)
    if not html:
        return None, "fetch_failed"
    ld_denoms = extract_denom_from_jsonld(html)
    if ld_denoms:
        return ld_denoms[0], "jsonld"
    body_denom = extract_denom_from_body(html)
    if body_denom:
        return body_denom, "body_keyword"
    title = re.search(r'<title>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
    if title:
        title_upper = title.group(1).upper()
        for keywords, label in DENOM_RULES:
            for kw in keywords:
                if kw in title_upper:
                    return label, "title_keyword"
    return None, "no_signal"

def main():
    dry_run = "--dry-run" in sys.argv
    limit = 0
    for a in sys.argv:
        if a.startswith("--limit="):
            limit = int(a.split("=")[1])
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith("--"):
            limit = int(sys.argv[idx + 1])

    db = sqlite3.connect(DB_PATH)
    c = db.cursor()

    c.execute("""
        SELECT id, name, website FROM churches 
        WHERE (denomination IS NULL OR denomination = '')
        AND website IS NOT NULL AND website != ''
        AND website NOT LIKE '%sbc.net%'
        ORDER BY RANDOM()
    """)
    rows = c.fetchall()
    total = len(rows)
    if limit:
        rows = rows[:limit]

    log(f"Processing {len(rows):,} unlabeled churches with websites ({total:,} total)")

    tagged = 0
    failed = 0
    results = Counter()
    source_counts = Counter()

    for i, (cid, name, website) in enumerate(rows):
        denom, source = classify_website(website)
        if denom:
            tagged += 1
            results[denom] += 1
            source_counts[source] += 1
            if not dry_run:
                c.execute("UPDATE churches SET denomination=?, classification_source='website_detection' WHERE id=?", (denom, cid))
        else:
            failed += 1
            source_counts[source] += 1
        if (i + 1) % 50 == 0:
            db.commit()
            log(f"  {i+1:,}/{len(rows):,}... ({tagged} tagged, {failed} no signal)")
        time.sleep(DELAY)

    db.commit()
    log(f"\n{'='*60}")
    log(f"Total checked: {len(rows):,}")
    log(f"Tagged: {tagged:,}")
    log(f"No signal: {failed:,}")
    log(f"\nBy source:")
    for src, cnt in source_counts.most_common():
        log(f"  {src:20s}: {cnt}")
    log(f"\nBy denomination (top 30):")
    for denom, cnt in results.most_common(30):
        log(f"  {denom:45s}: {cnt}")
    if not dry_run:
        c.execute("SELECT COUNT(*) FROM churches WHERE denomination IS NULL OR denomination = ''")
        remaining = c.fetchone()[0]
        log(f"\nRemaining unlabeled: {remaining:,}")
    db.close()

if __name__ == "__main__":
    main()
