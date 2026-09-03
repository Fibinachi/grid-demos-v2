#!/usr/bin/env python3
"""
Check unscraped denominational homepages for accessible church directories.
Tries common URL patterns and reports what's found.
"""
import urllib.request, urllib.error, re, sys, json
from datetime import datetime

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GrantWizard/1.0"

DENOM_CHECKLIST = [
    # (name, homepage, known_denoms_in_db)
    # High Priority
    ("AME Zion Church", "https://www.amezion.org", "African Methodist Episcopal Zion Church"),
    ("CME Church", "https://www.c-m-e.org", "Christian Methodist Episcopal Church"),
    ("Full Gospel Baptist", "https://www.fullgospelbaptist.org", "Full Gospel Baptist Church Fellowship"),
    # Medium Priority
    ("Christian Reformed Church", "https://www.crcna.org", "Christian Reformed Church in North America"),
    ("Evangelical Free (EFCA)", "https://www.efca.org", "Evangelical Free Church of America"),
    ("Evangelical Covenant", "https://www.covchurch.org", "Evangelical Covenant Church"),
    ("UPCI", "https://www.upci.org", "United Pentecostal Church International"),
    ("Church of God of Prophecy", "https://www.cogop.org", "Church of God of Prophecy"),
    ("IPHC", "https://www.iphc.org", "International Pentecostal Holiness Church"),
    ("Foursquare Church", "https://www.foursquare.org", "Foursquare Church"),
    ("Vineyard USA", "https://vineyardusa.org", "Vineyard Churches"),
    ("Calvary Chapel", "https://calvarychapel.com", "Calvary Chapel"),
    ("EPC", "https://www.epc.org", "Evangelical Presbyterian Church"),
    ("WELS", "https://www.wels.net", "Wisconsin Evangelical Lutheran Synod"),
    ("Cooperative Baptist Fellowship", "https://www.cbf.org", "Cooperative Baptist Fellowship"),
    ("Converge Worldwide", "https://converge.org", "Converge Worldwide"),
    ("Unitarian Universalist", "https://www.uua.org", "Unitarian Universalist"),
    ("Mennonite USA", "https://www.mennoniteusa.org", "Mennonite Church USA"),
    ("Church of the Brethren", "https://www.brethren.org", "Church of the Brethren"),
    # Orthodox
    ("Coptic Orthodox", "https://www.copticchurch.net", "Coptic Orthodox Church"),
    ("Orthodox Church in America", "https://www.oca.org", "Orthodox Church in America"),
    ("Ethiopian Orthodox", "https://www.eotc.us", "Ethiopian Orthodox Tewahedo Church"),
    ("Antiochian Orthodox", "https://www.antiochian.org", "Antiochian Orthodox Christian Archdiocese"),
    ("Armenian Apostolic", "https://www.armenianchurch.us", "Armenian Apostolic Church"),
]

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def try_url(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as f:
            html = f.read(100000).decode("utf-8", "replace")
            links = re.findall(r'href=[\'"]?([^\'" >]+)', html)
            return html, links
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return None, f"DNS/TCP {e.reason}"
    except Exception as e:
        return None, str(e)[:60]

def check_directory_paths(base_url, paths):
    """Try common directory URL paths on this domain."""
    found = []
    for path in paths:
        url = base_url.rstrip("/") + path
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=6) as f:
                html = f.read(50000).decode("utf-8", "replace")
                church_count = len(re.findall(r'(?:church|congregation|parish)', html, re.I))
                found.append((path, len(html), church_count))
        except:
            pass
    return found

def main():
    HOME_CHECK_PATHS = [
        "/find-a-church", "/churches", "/church-directory", "/find-a-church",
        "/congregations", "/our-churches", "/locator", "/church-locator",
        "/directory", "/find", "/locations", "/church-search",
        "/churchfinder", "/findachurch", "/about/churches",
    ]
    
    results = []
    
    for name, homepage, denom in DENOM_CHECKLIST:
        log(f"\n--- {name} ---")
        log(f"  Homepage: {homepage}")
        
        html, links = try_url(homepage)
        if html is None:
            log(f"  ❌ Homepage unreachable: {links}")
            results.append((name, homepage, "UNREACHABLE", links, 0, []))
            continue
        
        log(f"  ✅ Homepage OK ({len(html):,} bytes, {len(links):,} links)")
        
        # Check for directory-related links on homepage
        dir_keywords = ["find a church", "church directory", "church locator", 
                       "find a congregation", "our churches", "locations",
                       "find a parish", "church search", "church finder",
                       "congregation", "church near"]
        dir_links = []
        for l in links:
            text = l.lower()
            for kw in dir_keywords:
                if kw in text:
                    dir_links.append(l)
                    break
        
        if dir_links:
            log(f"  🔗 Directory links on homepage ({len(dir_links)}):")
            for l in dir_links[:10]:
                log(f"    {l[:90]}")
        
        # Try common directory paths
        found_dirs = check_directory_paths(homepage, HOME_CHECK_PATHS)
        working = [(p, s, c) for p, s, c in found_dirs if c > 0]
        if working:
            log(f"  📋 Working directory paths:")
            for p, s, c in working:
                log(f"    {p:30s} ({s:,} bytes, {c} church mentions)")
        else:
            log(f"  ❌ No directory paths found")
        
        results.append((name, homepage, "CHECKED", len(html), len(links), working))
    
    # Summary
    print("\n\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    reachable = sum(1 for r in results if r[3] != 0)
    with_dir = sum(1 for r in results if r[5])
    print(f"Reachable homepages: {reachable}/{len(results)}")
    print(f"With directory paths: {with_dir}/{len(results)}")
    print()
    for name, hp, status, size, links, dirs in results:
        if dirs:
            dir_paths = ", ".join(d[0] for d in dirs[:3])
            print(f"  ✅ {name:35s} | dirs: {dir_paths}")
        else:
            print(f"  {'⚠️' if 'CHECKED' in status else '❌'} {name:35s} | {status}")

if __name__ == "__main__":
    main()
