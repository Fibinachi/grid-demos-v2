#!/usr/bin/env python3
"""
Website Denomination Detector
==============================
Fetches homepage HTML of unlabeled churches and detects denomination
from JSON-LD schema markup, body text keywords, and page metadata.

Usage:
    python scripts/enrichment/classify_denom_from_web.py                # Full run
    python scripts/enrichment/classify_denom_from_web.py --dry-run      # Preview
    python scripts/enrichment/classify_denom_from_web.py --limit 100    # Quick test
"""
import sqlite3, os, sys, re, json, urllib.request, time
from datetime import datetime
from collections import Counter
from urllib.parse import urlparse

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
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 GrantWizard/1.0"
DELAY = 0.1  # 100ms between requests (10/sec)

# Denomination keywords to scan body text for
# Ordered by specificity — first match wins
DENOM_RULES = [
    (["ROMAN CATHOLIC", "ROMAN CATHOLIC CHURCH"], "Roman Catholic Church"),
    ([" CATHOLIC CHURCH", " CATHOLIC PARISH", " CATHOLIC "], "Roman Catholic Church"),
    (["MALANKARA CATHOLIC"], "Syro-Malabar Catholic Church"),
    (["COPTIC ORTHODOX"], "Coptic Orthodox Church"),
    (["ETHIOPIAN ORTHODOX"], "Ethiopian Orthodox Tewahedo Church"),
    (["GREEK ORTHODOX"], "Greek Orthodox Archdiocese of America"),
    (["ORTHODOX CHURCH IN AMERICA", "OCA CHURCH", "RUSSIAN ORTHODOX"], "Orthodox Church in America"),
    (["ANTIOCHIAN ORTHODOX", "SYRIAN ORTHODOX"], "Antiochian Orthodox Christian Archdiocese"),
    (["ROMANIAN ORTHODOX"], "Romanian Orthodox Church"),
    (["UKRAINIAN ORTHODOX"], "Ukrainian Orthodox Church"),
    (["SERBIAN ORTHODOX"], "Serbian Orthodox Church"),
    (["BULGARIAN ORTHODOX"], "Bulgarian Orthodox Church"),
    (["ARMENIAN APOSTOLIC", "ARMENIAN ORTHODOX"], "Armenian Apostolic Church"),
    (["MALANKARA ORTHODOX SYRIAN", "MALANKARA ORTHODOX"], "Malankara Orthodox Syrian Church"),
    ([" ORTHODOX "], "Eastern Orthodox"),
    (["SOUTHERN BAPTIST"], "Southern Baptist Convention"),
    (["MISSIONARY BAPTIST"], "Missionary Baptist"),
    (["INDEPENDENT BAPTIST", "INDEPENDENT BAPTIST"], "Independent Baptist"),
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
    (["VINEYARD CHURCH", "VINEYARD CHRISTIAN"], "Vineyard Churches"),
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

def extract_denom_from_jsonld(html):
    """Check JSON-LD for denomination/religiousDenomination fields."""
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
    """Check visible body text for denomination keywords."""
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

def fetch_url(url, timeout=3):
    """Fetch a URL and return HTML content. Fast timeout, small buffer."""
    import socket
    socket.setdefaulttimeout(timeout)
    try:
        r = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.5",
        })
        with urllib.request.urlopen(r, timeout=timeout) as f:
            return f.read(30000).decode("utf-8", "replace")
    except Exception:
        return None

def classify_website(url):
    """Fetch and classify a church website."""
    html = fetch_url(url)
    if not html:
        return None, "fetch_failed"
    
    # Strategy 1: JSON-LD schema markup (highest confidence)
    ld_denoms = extract_denom_from_jsonld(html)
    if ld_denoms:
        return ld_denoms[0], "jsonld"
    
    # Strategy 2: Body text keywords
    body_denom = extract_denom_from_body(html)
    if body_denom:
        return body_denom, "body_keyword"
    
    # Strategy 3: Page title
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
    # Also handle --limit N (space-separated)
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith("--"):
            limit = int(sys.argv[idx + 1])
    
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    
    # Get unlabeled churches with websites
    c.execute("""
        SELECT id, name, website FROM churches 
        WHERE (denomination IS NULL OR denomination = '')
        AND website IS NOT NULL AND website != ''
        AND website NOT LIKE '%sbc.net%'
        AND website LIKE '%.%'
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
                c.execute("""
                    UPDATE churches SET denomination=?, classification_source='website_detection'
                    WHERE id=?
                """, (denom, cid))
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
