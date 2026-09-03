#!/usr/bin/env python3
"""Scrape Church of the Nazarene directory from findachurch.nazarene.org.

The site is a Laravel/Inertia SPA. We use Playwright to render it,
find the search/filter API, and extract all church listings.

Re-run the ssm-run-nazarene.json on EC2 to execute.
"""
import asyncio, csv, json, os, re, sys, time
from playwright.async_api import async_playwright

PROJECT_DIR = r"E:\grid"
OUTPUT_CSV = os.path.join(PROJECT_DIR, "data", "nazarene_churches.csv")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

async def main():
    churches = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=UA)
        page = await context.new_page()
        
        print("Loading findachurch.nazarene.org...")
        await page.goto("https://findachurch.nazarene.org/", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)
        
        # Check if there's a search/zip box
        search_input = await page.query_selector("input[type='text'], input[placeholder*='zip' i], input[placeholder*='city' i], input[placeholder*='search' i]")
        
        if search_input:
            print("Found search input - trying to get all churches")
            # Try empty search or all states
            # First check if there's a state/region dropdown
            selects = await page.query_selector_all("select")
            if selects:
                for sel in selects:
                    label = await sel.get_attribute("aria-label") or await sel.get_attribute("name") or ""
                    print(f"  Select found: {label}")
                    options = await sel.query_selector_all("option")
                    print(f"  Options: {len(options)}")
                    
                    # Try each state
                    for opt in options:
                        val = await opt.get_attribute("value")
                        txt = await opt.inner_text()
                        if val and val.strip():
                            print(f"  Selecting: {txt} ({val})")
                            await sel.select_option(val)
                            await page.wait_for_timeout(2000)
                            
                            # Read results
                            results = await extract_listing(page)
                            churches.extend(results)
                            print(f"  Found {len(results)} churches so far")
        else:
            print("No search input found - checking page structure")
            print(await page.content()[:3000])
        
        # If we have a search box, try by state
        if search_input:
            us_states = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
                        "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
                        "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
                        "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
                        "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"]
            for state in us_states[:5]:  # Test with 5 first
                print(f"Searching {state}...")
                await search_input.fill(state)
                await page.wait_for_timeout(1500)
                results = await extract_listing(page)
                churches.extend(results)
        
        await browser.close()
    
    # Save
    seen = set()
    unique = []
    for c in churches:
        key = (c.get("name",""), c.get("city",""), c.get("state",""))
        if key not in seen:
            seen.add(key)
            unique.append(c)
    
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name","address","city","state","zip","phone","website","source"])
        w.writeheader()
        w.writerows(unique)
    
    print(f"\nSaved {len(unique)} churches to {OUTPUT_CSV}")

async def extract_listing(page):
    """Extract church listings from current page."""
    churches = []
    
    # Check for church cards/items
    items = await page.query_selector_all("[class*='church'], [class*='result'], [class*='card'], li, [class*='item'], tr")
    
    for item in items:
        try:
            text = await item.inner_text()
            html = await item.inner_html()
            
            name_el = await item.query_selector("h2, h3, h4, [class*='name'], [class*='title'], strong")
            name = await name_el.inner_text() if name_el else ""
            
            link_el = await item.query_selector("a[href]")
            link = await link_el.get_attribute("href") if link_el else ""
            
            if name and len(name) > 5:
                churches.append({
                    "name": name.strip(),
                    "address": "",
                    "website": link or "",
                    "source": "nazarene_findachurch"
                })
        except:
            pass
    
    return churches

if __name__ == "__main__":
    asyncio.run(main())
