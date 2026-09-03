#!/usr/bin/env python3
"""ABCUSA NetSuite Directory Scraper — top 10 municipalities per state.

Searches abc-usa.org/find-a-church NetSuite form using Playwright.
Each search gets a fresh browser context to avoid stale session state.
"""
import argparse, csv, json, os, re, sys
from playwright.sync_api import sync_playwright

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PARENT_URL = "https://www.abc-usa.org/find-a-church"

TOP10 = {
    "AK":["Anchorage","Fairbanks","Juneau","Wasilla","Palmer","Kenai","Kodiak","Bethel","Sitka","Soldotna"],
    "AL":["Birmingham","Montgomery","Mobile","Huntsville","Tuscaloosa","Hoover","Dothan","Auburn","Decatur","Madison"],
    "AR":["Little Rock","Fort Smith","Fayetteville","Springdale","Jonesboro","Rogers","North Little Rock","Conway","Bentonville","Pine Bluff"],
    "AZ":["Phoenix","Tucson","Mesa","Chandler","Glendale","Scottsdale","Gilbert","Tempe","Peoria","Flagstaff"],
    "CA":["Los Angeles","San Diego","San Jose","San Francisco","Fresno","Sacramento","Long Beach","Oakland","Bakersfield","Anaheim"],
    "CO":["Denver","Colorado Springs","Aurora","Fort Collins","Lakewood","Boulder","Pueblo","Arvada","Centennial","Thornton"],
    "CT":["Bridgeport","New Haven","Hartford","Stamford","Waterbury","Norwalk","Danbury","New Britain","Bristol","Meriden"],
    "DE":["Wilmington","Dover","Newark","Middletown","Smyrna","Milford","Seaford","Georgetown","Elsmere","New Castle"],
    "FL":["Jacksonville","Miami","Tampa","Orlando","St. Petersburg","Hialeah","Tallahassee","Fort Lauderdale","Port St. Lucie","Cape Coral"],
    "GA":["Atlanta","Augusta","Columbus","Savannah","Athens","Macon","Roswell","Albany","Marietta","Valdosta"],
    "HI":["Honolulu","Hilo","Kailua","Kapolei","Kaneohe","Waipahu","Pearl City","Mililani","Kahului","Kihei"],
    "IA":["Des Moines","Cedar Rapids","Davenport","Sioux City","Iowa City","Waterloo","Council Bluffs","Dubuque","Ames","West Des Moines"],
    "ID":["Boise","Meridian","Nampa","Idaho Falls","Pocatello","Caldwell","Coeur d'Alene","Twin Falls","Rexburg","Moscow"],
    "IL":["Chicago","Aurora","Rockford","Joliet","Naperville","Springfield","Peoria","Elgin","Waukegan","Champaign"],
    "IN":["Indianapolis","Fort Wayne","Evansville","South Bend","Carmel","Bloomington","Fishers","Hammond","Gary","Muncie"],
    "KS":["Wichita","Overland Park","Kansas City","Olathe","Topeka","Lawrence","Shawnee","Manhattan","Lenexa","Salina"],
    "KY":["Louisville","Lexington","Bowling Green","Owensboro","Covington","Richmond","Georgetown","Florence","Hopkinsville","Nicholasville"],
    "LA":["New Orleans","Baton Rouge","Shreveport","Lafayette","Lake Charles","Kenner","Bossier City","Monroe","Alexandria","Houma"],
    "MA":["Boston","Worcester","Springfield","Cambridge","Lowell","Lawrence","New Bedford","Brockton","Quincy","Fall River"],
    "MD":["Baltimore","Frederick","Rockville","Gaithersburg","Bowie","Hagerstown","Annapolis","College Park","Salisbury","Laurel"],
    "ME":["Portland","Lewiston","Bangor","South Portland","Auburn","Brunswick","Biddeford","Augusta","Saco","Waterville"],
    "MI":["Detroit","Grand Rapids","Warren","Sterling Heights","Lansing","Ann Arbor","Flint","Dearborn","Livonia","Troy"],
    "MN":["Minneapolis","Saint Paul","Rochester","Duluth","Bloomington","Brooklyn Park","Plymouth","Maple Grove","Woodbury","Eagan"],
    "MO":["Kansas City","St. Louis","Springfield","Independence","Columbia","Lee's Summit","O'Fallon","St. Joseph","St. Charles","St. Peters"],
    "MS":["Jackson","Gulfport","Southaven","Hattiesburg","Biloxi","Meridian","Tupelo","Greenville","Olive Branch","Horn Lake"],
    "MT":["Billings","Missoula","Great Falls","Bozeman","Butte","Helena","Kalispell","Havre","Anaconda","Miles City"],
    "NC":["Charlotte","Raleigh","Greensboro","Durham","Winston-Salem","Fayetteville","Cary","Wilmington","High Point","Asheville"],
    "ND":["Fargo","Bismarck","Grand Forks","Minot","West Fargo","Williston","Dickinson","Mandan","Jamestown","Wahpeton"],
    "NE":["Omaha","Lincoln","Bellevue","Grand Island","Kearney","Fremont","Norfolk","North Platte","Hastings","Columbus"],
    "NH":["Manchester","Nashua","Concord","Derry","Rochester","Salem","Dover","Londonderry","Merrimack","Hudson"],
    "NJ":["Newark","Jersey City","Paterson","Elizabeth","Edison","Woodbridge","Toms River","Hamilton","Trenton","Camden"],
    "NM":["Albuquerque","Las Cruces","Rio Rancho","Santa Fe","Roswell","Farmington","Hobbs","Clovis","Carlsbad","Alamogordo"],
    "NV":["Las Vegas","Henderson","Reno","North Las Vegas","Sparks","Carson City","Elko","Mesquite","Boulder City","Fallon"],
    "NY":["New York","Buffalo","Rochester","Yonkers","Syracuse","Albany","New Rochelle","Mount Vernon","Schenectady","Utica"],
    "OH":["Columbus","Cleveland","Cincinnati","Toledo","Akron","Dayton","Youngstown","Canton","Lorain","Springfield"],
    "OK":["Oklahoma City","Tulsa","Norman","Broken Arrow","Edmond","Lawton","Enid","Stillwater","Muskogee","Bartlesville"],
    "OR":["Portland","Salem","Eugene","Gresham","Hillsboro","Beaverton","Bend","Medford","Springfield","Corvallis"],
    "PA":["Philadelphia","Pittsburgh","Allentown","Erie","Reading","Scranton","Bethlehem","Lancaster","Harrisburg","Altoona"],
    "RI":["Providence","Warwick","Cranston","Pawtucket","East Providence","Woonsocket","Newport","Central Falls","Westerly","Barrington"],
    "SC":["Columbia","Charleston","North Charleston","Mount Pleasant","Rock Hill","Greenville","Summerville","Spartanburg","Hilton Head Island","Florence"],
    "SD":["Sioux Falls","Rapid City","Aberdeen","Brookings","Watertown","Mitchell","Yankton","Pierre","Huron","Spearfish"],
    "TN":["Nashville","Memphis","Knoxville","Chattanooga","Clarksville","Murfreesboro","Franklin","Johnson City","Jackson","Bartlett"],
    "TX":["Houston","San Antonio","Dallas","Austin","Fort Worth","El Paso","Arlington","Corpus Christi","Plano","Lubbock"],
    "UT":["Salt Lake City","West Valley City","Provo","West Jordan","St. George","Ogden","Sandy","Orem","Layton","South Jordan"],
    "VA":["Virginia Beach","Norfolk","Chesapeake","Richmond","Newport News","Alexandria","Hampton","Roanoke","Portsmouth","Suffolk"],
    "VT":["Burlington","South Burlington","Rutland","Barre","Montpelier","Winooski","St. Albans","Newport","Vergennes","Bristol"],
    "WA":["Seattle","Spokane","Tacoma","Vancouver","Bellevue","Everett","Kent","Yakima","Spokane Valley","Renton"],
    "WI":["Milwaukee","Madison","Green Bay","Kenosha","Racine","Appleton","Waukesha","Eau Claire","Oshkosh","Janesville"],
    "WV":["Charleston","Huntington","Morgantown","Parkersburg","Wheeling","Weirton","Fairmont","Beckley","Clarksburg","Martinsburg"],
    "WY":["Cheyenne","Casper","Laramie","Gillette","Rock Springs","Sheridan","Evanston","Green River","Riverton","Cody"],
}

SKIP_LABELS = {'CHURCH ID','CHURCH NAME','ADDRESS 1','CITY','STATE','ZIPCODE','PHONE','WEB ADDRESS'}


def search_one(browser, state_abbr, city):
    """Run one search using a shared browser. Returns list of dicts."""
    ctx = browser.new_context(viewport={'width': 1280, 'height': 900})
    page = ctx.new_page()
    page.goto(PARENT_URL, wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(5000)

    frame = next((f for f in page.frames if 'scriptlet' in f.url), None)
    if not frame:
        ctx.close()
        return []

    t = frame.evaluate('()=>document.body.innerText')
    m = re.search(r'(\d+)\s*\+\s*(\d+)\s*=', t)
    if not m:
        ctx.close()
        return []

    ans = str(int(m.group(1)) + int(m.group(2)))
    frame.fill('#custpage_math_challenge', ans)
    frame.fill('#custpage_f_city', city)

    arrow = frame.locator('.uir-field-dropdown-arrow').first
    arrow.click()
    frame.wait_for_timeout(500)
    for i in range(frame.locator('.dropdownNotSelected').count()):
        if frame.locator('.dropdownNotSelected').nth(i).inner_text().strip() == state_abbr:
            frame.locator('.dropdownNotSelected').nth(i).click()
            break

    frame.locator('.acs-btn-search').click()
    frame.wait_for_timeout(6000)

    t = frame.evaluate('()=>document.body.innerText')
    ctx.close()

    # Parse results — header labels are on separate lines
    recs = []
    if 'Total results: 0' in t or 'No records' in t:
        return recs

    in_header = False
    header_done = False

    for line in t.split('\n'):
        line = line.strip()
        if not line:
            continue
        if line == 'CHURCH ID':
            in_header = True
            continue
        if in_header:
            if line in SKIP_LABELS:
                continue
            in_header = False
            header_done = True
        if not header_done:
            continue
        if line in SKIP_LABELS or 'No records' in line or 'Churches' in line or 'RESULT INDEX' in line:
            continue
        if line.startswith('CHALLENGE:') or line == 'Search' or line == 'Clear All':
            continue

        m2 = re.match(r'^\s*(\d+)\s+(.*)', line)
        if m2:
            cid = m2.group(1)
            rest = m2.group(2).strip()
            # Skip ZIP+phone+website lines (rest starts with phone pattern)
            if re.match(r'\d{3}[-.\s)]\d{3}[-.\s]\d{4}', rest):
                continue
            # Skip if rest has no letters at all (pure numbers)
            if not re.search(r'[a-zA-Z]', rest):
                continue
            recs.append({'id': cid, 'name': rest, 'city': city, 'state': state_abbr})

    return recs


def main():
    parser = argparse.ArgumentParser(description='ABCUSA NetSuite Directory Scraper')
    parser.add_argument('--state', default='', help='State abbrev to scrape (e.g. CA)')
    parser.add_argument('--limit', type=int, default=0, help='Limit to first N states')
    parser.add_argument('--dry-run', action='store_true', help='No DB import')
    parser.add_argument('-o', '--output', default='', help='Output CSV path')
    args = parser.parse_args()

    states = sorted(TOP10.keys())
    if args.state:
        states = [s for s in states if s == args.state.upper()]
    if args.limit:
        states = states[:args.limit]

    n_searches = sum(len(TOP10[s]) for s in states)
    print(f'=== ABCUSA NetSuite Directory Scraper ===')
    print(f'{len(states)} states, {n_searches} searches')
    if args.dry_run:
        print('*** DRY RUN ***')
    print()

    all_recs, seen = [], set()
    errors = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=['--window-size=1280,900'])
        try:
            for si, st in enumerate(states):
                for ci, city in enumerate(TOP10[st]):
                    label = f'[{si+1:2d}/{len(states)}] {st} [{ci+1:2d}/10]'
                    print(f'  {label} {city:25s}...', end=' ', flush=True)
                    try:
                        recs = search_one(browser, st, city)
                        new = [r for r in recs if r['id'] not in seen]
                        for r in new:
                            seen.add(r['id'])
                        all_recs.extend(new)
                        print(f'{len(recs)} found, {len(new)} new')
                    except Exception as e:
                        errors += 1
                        print(f'ERR: {e}')
        finally:
            browser.close()

    print(f'\n=== RESULTS ===')
    print(f'Total unique churches: {len(all_recs):,}')
    print(f'Errors: {errors}')
    by_st = {}
    for r in all_recs:
        s = r.get('state', '?')
        by_st[s] = by_st.get(s, 0) + 1
    if by_st:
        print('By state:', ', '.join(f'{s}:{c:,}' for s, c in sorted(by_st.items(), key=lambda x: -x[1])))

    if all_recs:
        print(f'\nSamples:')
        for r in all_recs[:10]:
            print(f'  #{r["id"]:>6s} | {r["name"][:55]:55s} | {r.get("city",""):20s} {r.get("state","")}')

    if args.output and all_recs:
        with open(args.output, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['id', 'name', 'city', 'state'])
            w.writeheader()
            w.writerows(all_recs)
        print(f'\nExported to {args.output}')

    print('\nDone!')


if __name__ == '__main__':
    main()
