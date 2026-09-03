"""
Greek Orthodox Archdiocese of America (GOARCH) Parish Scraper.
Uses Wayback Machine to bypass Cloudflare, extracts parish listing data.
"""
import urllib.request, json, csv, re, sys, os, time
from datetime import datetime

# ─── Configuration ─────────────────────────────────────────────────
OUTPUT = "data/goarch_parishes.csv"
DB = "churches.db"

def fetch(url, timeout=20):
    try:
        import gzip
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Encoding": "gzip, deflate"
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                data = gzip.decompress(data)
            return data.decode(errors="ignore")
    except Exception as e:
        return None

def fetch_bytes(url, timeout=20):
    """Fetch raw bytes."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except:
        return None

def try_wayback_parishes():
    """
    GOARCH /parishes page on Liferay lists parishes via journal articles.
    We need to extract from Wayback Machine captures.
    """
    # Get CDX summary for the parishes page to find good snapshots
    cdx_url = "https://web.archive.org/cdx/search/cdx?url=www.goarch.org/parishes&output=json&limit=20&fl=timestamp,statuscode,original"
    data = fetch(cdx_url)
    if data:
        try:
            pages = json.loads(data)
            print(f"Wayback CDX: {len(pages)-1} captures")
            for p in pages[1:6]:
                print(f"  {p[0]} status={p[1]}")
        except:
            pass
    
    # Get the most recent complete capture
    html = fetch("https://web.archive.org/web/20250301000000id_/https://www.goarch.org/parishes")
    if html and "Just a moment" not in html[:200]:
        print(f"Wayback 2025-03: {len(html)} bytes")
        return html
    
    # Try older captures
    for date in ["20250101", "20241001", "20240601", "20240301", "20231001"]:
        html = fetch(f"https://web.archive.org/web/{date}000000id_/https://www.goarch.org/parishes")
        if html and "Just a moment" not in html[:200]:
            print(f"Wayback {date}: {len(html)} bytes")
            return html
    
    return None

def extract_parishes_from_liferay(html):
    """
    GOARCH uses Liferay. The parishes page lists journal articles.
    Extract parish info from the HTML structure.
    """
    parishes = []
    
    # Remove HTML tags for text extraction
    text = re.sub(r'<[^>]+>', '\n', html)
    text = re.sub(r'\n+', '\n', text)
    
    # Look for Liferay portlet data
    # GOARCH stores parish data in JSON objects within the page
    json_blocks = re.findall(r'\{[^}]*"title"[^}]*"address"[^}]*\}', html, re.DOTALL)
    
    # Also try to find structured data
    # Common Liferay patterns
    patterns = [
        # JSON-LD
        (r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', False),
        # Liferay data attributes
        (r'data-parish-id="([^"]*)"[^>]*data-parish-name="([^"]*)"', True),
        # Article entries with class
        (r'class="[^"]*journal-content-article[^"]*"[^>]*>', False),
        # Look for specific GOARCH parish listing pattern
        (r'(?:parish|church)-item[^>]*>', False),
    ]
    
    # Search for "parish" entries in the text
    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 5]
    
    # Find parish names (Greek Orthodox churches typically end with "Greek Orthodox Church")
    church_names = []
    for line in lines:
        if re.search(r'Greek\s+Orthodox', line, re.IGNORECASE):
            church_names.append(line[:200])
    
    if church_names:
        print(f"Found {len(church_names)} lines mentioning 'Greek Orthodox'")
        for name in church_names[:20]:
            print(f"  {name}")
    
    # Look for address patterns
    addresses = re.findall(r'\d+\s+[A-Z][A-Za-z\s,]+(?:Street|Avenue|Road|Drive|Lane|Way|Blvd|Dr|Ave|St|Rd|Ln|Cir|Ct)[^<,]*', html)
    
    return church_names, addresses

def try_direct_api():
    """Try Liferay API with different authentication."""
    for url in [
        "https://www.goarch.org/api/jsonws/parish/get-parishes?count=1000",
        "https://www.goarch.org/api/jsonws/parish/get-parishes-by-metropolis",
        "https://www.goarch.org/api/jsonws/assetentry/get-entries?groupId=10192&count=500",
        "https://www.goarch.org/api/jsonws/dlfileentry/get-file-entries?groupId=10192&count=500",
    ]:
        d = fetch(url, timeout=15)
        if d:
            try:
                j = json.loads(d)
                if isinstance(j, list):
                    print(f"\nAPI found: {url} -> {len(j)} items")
                    return j
                elif isinstance(j, dict):
                    print(f"\nAPI found: {url} -> {len(j)} keys")
                    return j
            except:
                if "[" in d[:100]:
                    print(f"\nAPI possible: {url} -> {d[:200]}")
    return None

def main():
    print("="*60)
    print("GOARCH Parish Scraper")
    print("="*60)
    
    # 1. Try Wayback Machine
    print("\n[1] Wayback Machine capture...")
    html = try_wayback_parishes()
    
    # 2. Try direct API
    print("\n[2] Direct API...")
    api_data = try_direct_api()
    
    # 3. Extract parish info
    print("\n[3] Extracting parish data...")
    if html:
        names, addresses = extract_parishes_from_liferay(html)
        print(f"\n  Found {len(names)} parish name matches")
        print(f"  Found {len(addresses)} address matches")
        
        # Save raw HTML for inspection
        with open("data/goarch_raw.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("  Saved raw HTML to data/goarch_raw.html")
    
    if api_data:
        with open("data/goarch_api.json", "w", encoding="utf-8") as f:
            json.dump(api_data, f, indent=2)
        print(f"Saved API data to data/goarch_api.json")
    
    # 4. If we got data, save as CSV
    print("\nDone.")

if __name__ == "__main__":
    main()
