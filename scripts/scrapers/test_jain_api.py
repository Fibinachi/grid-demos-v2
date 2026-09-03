"""
Quick test: hit jainmandir SearchTempleByState API via Playwright.
Logs every response with status code and body preview.
"""
import json, time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent="Mozilla/5.0")
    page = context.new_page()
    
    results = []
    
    def handle_response(response):
        url = response.url
        parts = url.split("/")
        if "SearchTempleByState" in parts or "SearchTempleByDistrict" in parts:
            status = response.status
            try:
                body = response.text()[:300]
            except:
                body = "NO BODY"
            # Extract state name from URL
            try:
                idx = parts.index("SearchTempleByState")
                state_label = parts[idx+1] if idx+1 < len(parts) else "?"
            except ValueError:
                state_label = url
            results.append({"url": url, "status": status, "body": body})
            print(f"  >>> {status} {state_label}")
            if status == 200:
                try:
                    data = response.json()
                    print(f"      Temples: {len(data)}")
                    if data:
                        print(f"      First: {data[0].get('name','?')} @ {data[0].get('location','?')}")
                except:
                    print(f"      Body: {body[:150]}")
    
    page.on("response", handle_response)
    
    print("Loading page...")
    page.goto("https://www.jainmandir.org/MainPage/MandirListMenu.html",
              wait_until="networkidle", timeout=30000)
    print(f"Title: {page.title()}")
    
    # Try Gujarat
    print("\nSelecting Gujarat (id=13)...")
    page.locator("#statedata").select_option("13")
    time.sleep(1)
    
    print("Clicking View...")
    page.locator("button:has-text('View')").first.click()
    time.sleep(3)
    
    print(f"\n=== RESULTS ===")
    for r in results:
        print(f"  {r['status']} | {r['url'][:80]}")
    
    browser.close()
    
if not results:
    print("NO API CALLS DETECTED — the View button might not trigger loadLeaftLetData")
