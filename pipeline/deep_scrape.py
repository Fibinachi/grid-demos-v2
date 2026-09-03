"""
Phase 3: Deep Church Profile Scraper
======================================
Extracts structured data from church websites:
  - Pastor/leadership names + full staff directory
  - Service times
  - Ministries (youth, children, food pantry, etc.)
  - Online giving status + link
  - Language offerings
  - Livestream link
  - Social media (Facebook, Instagram, YouTube)
  - Statement of faith / doctrinal summary
  - Affiliated denomination
  - Campus count (multi-site)
  - Attendance/size indicators

Usage: python ec3_deep_scrape.py <input_csv> <output_csv>
  input_csv: church_name,website columns
  output_csv: all extracted fields
"""

import csv, os, re, sys, time, json, threading
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

INPUT_FILE = sys.argv[1] if len(sys.argv) > 1 else "churches_to_deep_scrape.csv"
OUTPUT_FILE = sys.argv[2] if len(sys.argv) > 2 else "deep_profiles.csv"

# Pages to scrape per church (fallback when no sitemap found) - keep lean for memory
PAGES = [
    "/", "/about", "/staff", "/pastor", "/leadership",
    "/give", "/donate", "/online-giving",
    "/beliefs", "/what-we-believe", "/service-times",
    "/ministries", "/contact", "/sermons",
    "/visit", "/locations", "/events",
]

# Keywords for ministry detection
MINISTRY_KEYWORDS = {
    "youth": ["youth", "youth group", "teen", "student ministry", "youth ministry", "junior high", "high school"],
    "children": ["children", "kids", "kids ministry", "children's ministry", "nursery", "preschool", "childcare", "vbs", "vacation bible"],
    "food_pantry": ["food pantry", "food bank", "food ministry", "community meals", "soup kitchen", "food assistance"],
    "preschool": ["preschool", "pre-k", "pre k", "daycare", "child care", "early learning", "mother's day out", "mdo"],
    "daycare": ["daycare", "day care", "child development center", "cdc"],
    "worship_band": ["worship team", "worship band", "praise team", "choir", "worship ministry"],
    "small_groups": ["small group", "life group", "community group", "home group", "bible study", "discipleship"],
    "missions": ["missions", "mission trip", "global missions", "local missions", "outreach"],
    "counseling": ["counseling", "pastoral care", "support group", "grief share"],
    "seniors": ["senior", "seniors ministry", "golden age", "prime timers", "silver", "retiree"],
    "addiction": ["celebrate recovery", "aa meeting", "na meeting", "recovery ministry", "addiction"],
    "esl": ["esl", "english as a second", "english classes", "english language"],
    "recovery": ["recovery program", "recovery ministry", "12 step", "addiction help"],
    "men": ["men's ministry", "men of faith", "men's group", "iron sharpens"],
    "women": ["women's ministry", "women of faith", "women's group", "sisterhood"],
    "marriage": ["marriage ministry", "couples ministry", "marriage conference", "marriage retreat"],
    "college": ["college ministry", "campus ministry", "young adult", "university"],
    "music": ["music ministry", "worship ministry", "choir", "worship team", "praise team"],
    "sports": ["sports ministry", "upward", "sports camp", "athletic"],
    "summer_camp": ["summer camp", "vbs", "vacation bible school", "kids camp"],
}

# Staff role patterns for directory extraction
STAFF_ROLES = [
    "senior pastor", "lead pastor", "head pastor", "teaching pastor",
    "youth pastor", "student pastor", "children's pastor", "kids pastor",
    "worship pastor", "music pastor", "worship director", "music director",
    "executive pastor", "associate pastor", "assistant pastor",
    "administrative pastor", "admin pastor",
    "missions pastor", "outreach pastor",
    "campus pastor", "location pastor",
    "pastor of administration", "pastor of discipleship",
    "administrator", "office manager", "church administrator",
    "director of youth", "director of children",
    "director of worship", "director of music",
    "director of missions", "director of outreach",
    "director of administration",
    "rector", "vicar", "curate", "priest", "canon",
    "deacon", "archdeacon",
    "minister of music", "youth minister", "children's minister",
    "associate minister", "assistant minister",
    "elder", "board member", "vestry member", "trustee",
]

# Pastor name patterns (expanded)
PASTOR_PATTERNS = [
    r'(?:Pastor|Rev\.?|Reverend|Dr\.?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
    r'(?:Senior Pastor|Lead Pastor|Head Pastor)\s*:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
    r'(?:Pastor|Rev\.?|Reverend)\s+([A-Z]\.?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
    r'(?:Rector|Vicar|Priest)\s+(?:-|–)?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
    r'(?:Rev\.?|Reverend)\s+(?:Canon|Dr\.?)?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
]

# Service time patterns
TIME_PATTERNS = [
    r'(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))\s*(?:-|–|to)?\s*(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))?',
    r'(\d{1,2})\s*(?:am|pm|AM|PM)\s*(?:-|–|to)?\s*(\d{1,2})\s*(?:am|pm|AM|PM)?',
    r'(?:Sundays?|Sunday mornings?|Weekends?)\s*(?:at\s*)?(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM))',
]

# Giving platform detection
GIVING_KEYWORDS = [
    "give", "donate", "giving", "online giving", "tithe", "offering",
    "pushpay", "subsplash", "churchcenter", "planning center",
    "ministryarchives", "easyttithe", "vanco", "tithely",
]

# Livestream detection
LIVESTREAM_KEYWORDS = [
    "live stream", "livestream", "watch live", "watch online",
    "live service", "sermon live", "youtube.com/@", "facebook.com/live",
    "youtube.com/channel", "twitch.tv",
]

# Language detection
LANGUAGE_KEYWORDS = {
    "spanish": ["español", "spanish", "servicio en español", "iglesia", "hispanic", "latino"],
    "korean": ["한국어", "korean", "한글"],
    "chinese": ["中文", "chinese", "cantonese", "mandarin", "粵語"],
    "french": ["français", "french"],
    "vietnamese": ["tiếng việt", "vietnamese"],
    "portuguese": ["português", "portuguese", "brasil"],
    "tagalog": ["tagalog", "filipino"],
    "arabic": ["arabic", "العربية"],
    "russian": ["russian", "русский"],
}

# Leadership roles for counting
LEADERSHIP_ROLES = [
    "elder", "deacon", "vestry", "trustee", "board member",
    "board of directors", "governing board", "session", "consistory",
]

# Church size patterns
SIZE_PATTERNS = [
    r'(\d{3,5})\s*(?:weekend|weekly|average)\s*(?:attendance|worshippers|people)',
    r'attendance\s*(?:of|:)?\s*(\d{2,4})',
    r'(\d{2,4})\s*members?',
    r'(\d{2,4})\s*people\s+(?:call|attend|worship)',
]

# Church plant / closure detection
CLOSURE_SIGNALS = [
    "permanently closed", "no longer meeting", "church closed",
    "discontinued", "dissolved", "ceasing operations",
    "for sale", "building sold", "merged with",
]

PLANT_SIGNALS = [
    "church plant", "planting", "launching", "new campus",
    "we started meeting", "new location opening",
]

MOVE_SIGNALS = [
    "we've moved", "we have moved", "new location",
    "relocating", "relocated", "new address",
    "redirect", "this page has moved",
]

# Doctrinal alignment signals
DOCTRINAL_SIGNALS = {
    "complementarian": ["complementarian", "male headship", "men lead", "pastors must be men"],
    "egalitarian": ["egalitarian", "women pastors", "women elders", "female pastor", "gender equality"],
    "charismatic": ["charismatic", "signs and wonders", "spiritual gifts", "speaking in tongues", "baptism of the spirit"],
    "non_charismatic": ["cessationist", "reformed", "confessional", "1689", "westminster"],
    "contemporary": ["contemporary worship", "modern worship", "band", "praise team", "drums", "screens", "projector"],
    "liturgical": ["liturgy", "liturgical", "common prayer", "eucharist", "communion weekly", "lectionary"],
    "political_conservative": ["pro-life", "traditional marriage", "religious freedom", "family values", "moral majority"],
    "political_liberal": ["social justice", "racial justice", "inclusive", "affirming", "lgbtq affirming", "black lives matter", "creation care"],
}

# Financial signal patterns - enhanced for website-based extraction
FINANCIAL_PATTERNS = [
    r'annual\s+(?:report|budget|financial)\s*(?:report|statement)?',
    r'audited\s+financial',
    r'form\s+990',
    r'our\s+budget',
    r'financial\s+transparency',
]

# Revenue/budget amount patterns (look for dollar amounts on giving/budget pages)
BUDGET_AMOUNT_PATTERNS = [
    r'(?:annual|yearly|budget|raised)\s*(?::|of|is|about|around|over)?\s*\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
    r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:annual|yearly|budget|raised)',
    r'(?:goal|target|need)\s*(?::|of)?\s*\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
    r'(?:raised|collected)\s*(?:over|about|around|more than)?\s*\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
    r'campaign\s*(?::|of)?\s*\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
]

# Affiliation/denomination detection keywords
AFFILIATION_KEYWORDS = {
    "Southern Baptist": ["southern baptist", "sbc", "southern baptist convention"],
    "United Methodist": ["united methodist", "umc", "methodist church"],
    "Catholic": ["catholic", "roman catholic", "catholic church"],
    "Lutheran (ELCA)": ["elca", "evangelical lutheran", "lutheran church"],
    "Lutheran (LCMS)": ["lcms", "lutheran church missouri", "missouri synod"],
    "Presbyterian (PCUSA)": ["pcusa", "presbyterian church usa", "presbyterian church (u.s.a.)"],
    "Presbyterian (PCA)": ["pca", "presbyterian church in america"],
    "Anglican/Episcopal": ["anglican", "episcopal church", "anglican church", "episcopal"],
    "Pentecostal (AG)": ["assemblies of god", "ag church", "assemblies of god church"],
    "Pentecostal (COGIC)": ["cogic", "church of god in christ"],
    "Pentecostal (Church of God)": ["church of god", "cog", "church of god of prophecy"],
    "Non-denominational": ["non-denominational", "nondenominational", "independent church", "non denominational"],
    "Baptist (ABCUSA)": ["american baptist", "abcusa"],
    "Baptist (Independent)": ["independent baptist", "independent fundamental baptist"],
    "Christian Church (Disciples)": ["christian church", "disciples of christ", "doctrine"],
    "Church of Christ": ["church of christ", "churches of christ"],
    "Congregational": ["congregational", "ucc", "united church of christ"],
    "Seventh-day Adventist": ["seventh-day adventist", "sda church", "adventist"],
    "Mennonite": ["mennonite", "brethren"],
    "Nazarene": ["nazarene", "church of the nazarene"],
    "Salvation Army": ["salvation army"],
    "Evangelical Free": ["evangelical free", "efca"],
    "Wesleyan": ["wesleyan church", "wesleyan"],
    "Calvary Chapel": ["calvary chapel"],
    "Foursquare": ["foursquare church", "foursquare"],
    "Orthodox": ["orthodox church", "greek orthodox", "russian orthodox", "orthodox"],
    "Reformed": ["reformed church", "reformed", "crcna"],
} 

# Community impact
COMMUNITY_PARTNERS = [
    "united way", "salvation army", "habitat for humanity",
    "local school", "food bank", "community center",
    "nonprofit partner", "community partnership",
    "local ministry", "mission partner",
]

# Campus count patterns
CAMPUS_PATTERNS = [
    r'(\d+)\s*(?:campuses?|locations?)',
    r'(?:multi-site|campus)\s*(?:church|ministry)',
    r'(?:locations?|campuses?)\s*(?::|are)?\s*\d+',
]

TIMEOUT = 8
MAX_WORKERS = 5
PAGE_LIMIT = 12

stats_lock = threading.Lock()
all_results = []
processed = 0

def fetch_url(url, timeout=6):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xml",
        "Accept-Language": "en-US",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            return html
    except:
        return ""

def discover_pages(site):
    """Discover actual pages via robots.txt sitemaps, falling back to common sitemap URLs."""
    # First try robots.txt for Sitemap: entries
    sitemap_urls = []
    robots = fetch_url(site.rstrip('/') + "/robots.txt", timeout=5)
    if robots:
        for line in robots.splitlines():
            if line.lower().startswith("sitemap:"):
                url = line.split(":", 1)[1].strip()
                if url:
                    sitemap_urls.append(url)
    
    # If no sitemaps from robots.txt, try common locations
    if not sitemap_urls:
        common = ["/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml"]
        for path in common:
            xml = fetch_url(site.rstrip('/') + path, timeout=5)
            if xml and ("<urlset" in xml or "<sitemapindex" in xml):
                sitemap_urls.append(site.rstrip('/') + path)
                break
    
    # Parse sitemaps to extract page URLs
    discovered = set()
    for sm_url in sitemap_urls:
        xml = fetch_url(sm_url, timeout=8)
        if not xml:
            continue
        # Extract all <loc> URLs
        for m in re.finditer(r'<loc>(.*?)</loc>', xml, re.IGNORECASE):
            page_url = m.group(1).strip()
            # Only keep URLs on this domain, convert to path
            if site.rstrip('/') in page_url:
                path = "/" + page_url.split("/", 3)[-1] if "/" in page_url.replace(site.rstrip('/'), '', 1) else "/"
                # Skip file downloads
                if not path.endswith(('.pdf', '.mp3', '.mp4', '.zip', '.jpg', '.png', '.gif')):
                    discovered.add(path)
    
    if discovered:
        print(f"  Discovered {len(discovered)} pages from sitemap")
        # Prioritize high-value pages
        priority = ["/", "/about", "/staff", "/pastor", "/give", "/beliefs", "/service-times",
                     "/leadership", "/ministries", "/contact", "/sermons"]
        ordered = []
        for p in priority:
            if p in discovered:
                ordered.append(p)
                discovered.discard(p)
        ordered.extend(sorted(discovered))
        return ordered[:PAGE_LIMIT]
    
    # Fallback: try common sitemap-like paths for known CMS
    cms_pages = fetch_url(site.rstrip('/') + "/page-sitemap.xml", timeout=4)
    if cms_pages and "<loc>" in cms_pages:
        paths = []
        for m in re.finditer(r'<loc>(.*?)</loc>', cms_pages, re.IGNORECASE):
            paths.append(m.group(1))
        return paths[:PAGE_LIMIT] if paths else PAGES
    
    return PAGES

def extract_social_links(html, base_url):
    """Extract social media links."""
    socials = {"facebook": "", "youtube": "", "instagram": ""}
    for platform in socials:
        pattern = rf'(?:href|src)=["\']https?://(?:www\.)?(?:{platform}\.com|{platform}\.org)[^"\']*["\']'
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            socials[platform] = match.group(0).split('"')[1]
    return socials

def scrape_facebook_followers(page_url):
    """Try to get Facebook page follower count from the page."""
    try:
        html = fetch_url(page_url, timeout=4)
        if not html:
            return 0, ""
        # Look for follower count in meta tags or page text
        followers = 0
        patterns = [
            r'(\d[\d,]*)\s*(?:followers?|likes?|people\s+follow)',
            r'"followerCount":(\d+)',
            r'"likeCount":(\d+)',
            r'"followCount":(\d+)',
        ]
        for p in patterns:
            m = re.search(p, html)
            if m:
                num = int(m.group(1).replace(',', ''))
                if num > 0:
                    followers = num
                    break
        
        # Get page name
        name = ""
        nm = re.search(r'<title>(.*?)</title>', html)
        if nm:
            name = nm.group(1).split('|')[0].strip()
        
        return followers, name
    except:
        return 0, ""

def scrape_youtube_subscribers(channel_url):
    """Try to get YouTube subscriber count from channel page."""
    try:
        html = fetch_url(channel_url, timeout=4)
        if not html:
            return 0, 0, ""
        subscribers = 0
        video_count = 0
        
        # Look for subscriber count
        patterns = [
            r'(\d[\d,]*)\s*(?:subscribers?|subscriber)',
            r'"subscriberCount":(\d+)',
            r'"subscriberCountText".*?([\d,.]+[KMB]?)',
        ]
        for p in patterns:
            m = re.search(p, html)
            if m:
                txt = m.group(1).replace(',', '')
                if 'K' in txt:
                    subscribers = int(float(txt.replace('K', '')) * 1000)
                elif 'M' in txt:
                    subscribers = int(float(txt.replace('M', '')) * 1000000)
                else:
                    subscribers = int(txt)
                if subscribers > 0:
                    break
        
        # Look for video count
        vm = re.search(r'(\d[\d,]*)\s*(?:videos?|video)', html)
        if vm:
            video_count = int(vm.group(1).replace(',', ''))
        
        # Channel name
        name = ""
        nm = re.search(r'<title>(.*?)</title>', html)
        if nm:
            name = nm.group(1).split('-')[0].strip()
        
        return subscribers, video_count, name
    except:
        return 0, 0, ""

def detect_affiliation(html, text, church_name=""):
    """Detect denominational affiliation from website text."""
    text_lower = text.lower()
    html_lower = html.lower()
    combined = text_lower + " " + html_lower
    found = []
    for denom, keywords in AFFILIATION_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                found.append(denom)
                break
    
    # Also check church name for denomination clues
    name_lower = church_name.lower()
    for denom, keywords in AFFILIATION_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                if denom not in found:
                    found.append(denom + " (from name)")
                break
    
    return " | ".join(found) if found else ""

def extract_budget_info(html):
    """Extract budget/financial indicators from website text."""
    text = html.lower()
    info = []
    
    # Check for financial pages
    for pat in FINANCIAL_PATTERNS:
        if re.search(pat, text):
            info.append(pat.replace(r'\s+', ' ').replace(r'(?:', '').replace(')?', ''))
    
    # Look for dollar amounts
    amounts = []
    for pat in BUDGET_AMOUNT_PATTERNS:
        for m in re.finditer(pat, text):
            try:
                amt = int(m.group(1).replace(',', ''))
                if amt > 1000:  # Ignore tiny amounts
                    amounts.append(amt)
            except:
                pass
    
    max_amount = max(amounts) if amounts else 0
    return " | ".join(info[:3]), max_amount

def detect_online_giving(html):
    """Check if the church has online giving."""
    text = html.lower()
    for kw in GIVING_KEYWORDS:
        if kw in text:
            return True
    return bool(re.search(r'href=[\'\"][^\'\"]*(?:give|donate|giving)[^\'\"]*[\'\"]', html, re.IGNORECASE))

def extract_pastors(html):
    """Extract pastor names from HTML."""
    pastors = []
    for pattern in PASTOR_PATTERNS:
        matches = re.findall(pattern, html)
        for m in matches:
            if isinstance(m, tuple):
                pastors.append(' '.join(m))
            else:
                pastors.append(m)
    # Deduplicate
    seen = set()
    unique = []
    for p in pastors:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique[:5]  # Max 5 pastors

def extract_service_times(html):
    """Extract service times from HTML."""
    times = []
    text = html.replace('\n', ' ')
    for pattern in TIME_PATTERNS:
        matches = re.findall(pattern, text)
        for m in matches:
            if isinstance(m, tuple):
                t = ' - '.join(filter(None, m))
            else:
                t = m
            if t and len(t) > 3:
                times.append(t.strip())
    # Filter to reasonable service times (between 6am and 9pm)
    filtered = []
    for t in times:
        # Extract hour
        nums = re.findall(r'(\d{1,2})(?::\d{2})?\s*(?:am|pm)', t.lower())
        for n in nums:
            h = int(n)
            if h >= 6 and h <= 21:
                filtered.append(t)
                break
    return list(set(filtered))[:5]

def extract_ministries(html):
    """Extract ministries offered."""
    text = html.lower()
    found = {}
    for ministry, keywords in MINISTRY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                found[ministry] = True
                break
    return list(found.keys())

def extract_languages(html):
    """Detect non-English language offerings."""
    text = html.lower()
    found = []
    for lang, keywords in LANGUAGE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                found.append(lang)
                break
    return found

def extract_attendance(html):
    """Try to find attendance/membership numbers."""
    text = html.lower()
    patterns = [
        r'(\d{2,4})\s*(?:\+|-)?\s*(?:average\s+)?attend',
        r'attendance\s*(?:of|:)?\s*(\d{2,4})',
        r'(\d{2,4})\s*(?:\+|-)?\s*members?',
        r'members?\s*(?:of|:)?\s*(\d{2,4})',
        r'(\d{2,4})\s*people\s+(?:call|attend|worship)',
        r'we\s+have\s+(?:about|around|approximately|over)\s+(\d{2,4})',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            num = int(m.group(1))
            if 10 <= num <= 50000:
                return num
    return 0

def check_church_plant(html):
    """Check if this appears to be a new church plant."""
    text = html.lower()
    plant_indicators = ['church plant', 'new campus', 'launching', 'planting', 'we started']
    return any(kw in text for kw in plant_indicators)

def deep_scrape_one(church_name, website):
    global processed
    
    profile = {
        "church_name": church_name[:80],
        "website": website,
        "pastors": "",
        "service_times": "",
        "ministries": "",
        "languages": "",
        "online_giving": False,
        "attendance": 0,
        "church_plant": False,
        "has_youth": False,
        "has_children": False,
        "has_food_pantry": False,
        "has_preschool": False,
        "facebook": "",
        "youtube": "",
        "instagram": "",
        "affiliation": "",
        "fb_followers": 0,
        "yt_subscribers": 0,
        "yt_videos": 0,
        "budget_indicators": "",
        "budget_amount": 0,
    }
    
    all_html = ""
    domain = re.sub(r'https?://(www\.)?', '', website).split('/')[0] if website else ""
    
    if not website:
        with stats_lock:
            processed += 1
            all_results.append(profile)
        return
    
    site = website.strip()
    if not site.startswith("http"):
        site = "https://" + site
    
    # Discover pages from robots.txt/sitemap, fall back to PAGES
    pages_to_scrape = discover_pages(site)
    
    for path in pages_to_scrape:
        url = site.rstrip('/') + (path if path.startswith('/') else '/' + path)
        html = fetch_url(url, TIMEOUT)
        if html:
            all_html += html + "\n"
    
    if not all_html:
        with stats_lock:
            processed += 1
            all_results.append(profile)
        return
    
    # Extract everything
    pastors = extract_pastors(all_html)
    if pastors:
        profile["pastors"] = " | ".join(pastors)
    
    times = extract_service_times(all_html)
    if times:
        profile["service_times"] = " | ".join(times)
    
    ministries = extract_ministries(all_html)
    if ministries:
        profile["ministries"] = ", ".join(ministries)
        profile["has_youth"] = "youth" in ministries
        profile["has_children"] = "children" in ministries
        profile["has_food_pantry"] = "food_pantry" in ministries
        profile["has_preschool"] = "preschool" in ministries
    
    languages = extract_languages(all_html)
    if languages:
        profile["languages"] = ", ".join(languages)
    
    profile["online_giving"] = detect_online_giving(all_html)
    profile["attendance"] = extract_attendance(all_html)
    profile["church_plant"] = check_church_plant(all_html)
    
    socials = extract_social_links(all_html, site)
    profile["facebook"] = socials["facebook"]
    profile["youtube"] = socials["youtube"]
    profile["instagram"] = socials["instagram"]
    
    # Enrichment: Facebook follower count
    if profile["facebook"]:
        fb_followers, fb_name = scrape_facebook_followers(profile["facebook"])
        profile["fb_followers"] = fb_followers
    
    # Enrichment: YouTube subscriber count
    if profile["youtube"]:
        yt_subs, yt_vids, yt_name = scrape_youtube_subscribers(profile["youtube"])
        profile["yt_subscribers"] = yt_subs
        profile["yt_videos"] = yt_vids
    
    # Enrichment: Affiliation detection
    if all_html:
        profile["affiliation"] = detect_affiliation(all_html, all_html, church_name)
    
    # Enrichment: Budget/financial indicators
    budget_info, budget_amt = extract_budget_info(all_html)
    profile["budget_indicators"] = budget_info
    profile["budget_amount"] = budget_amt
    
    with stats_lock:
        processed += 1
        all_results.append(profile)
        if processed % 100 == 0:
            elapsed = time.time() - start_time
            print(f"  {processed} done | {processed/elapsed:.1f}/s | {int(elapsed)}s")

start_time = time.time()

def main():
    global start_time
    
    targets = []
    with open(INPUT_FILE, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            targets.append(r)
    
    total = len(targets)
    print(f"Phase 3 Deep Scrape: {total} churches")
    print(f"Input: {INPUT_FILE}")
    print(f"Output: {OUTPUT_FILE}")
    print()
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for t in targets:
            fut = executor.submit(deep_scrape_one, t.get("church_name",""), t.get("website",""))
            futures[fut] = t
        
        for f in as_completed(futures):
            pass
    
    elapsed = time.time() - start_time
    print(f"\nDone in {elapsed:.0f}s")
    print(f"Processed: {processed}")
    
    # Stats
    with_giving = sum(1 for r in all_results if r["online_giving"])
    with_pastor = sum(1 for r in all_results if r["pastors"])
    with_times = sum(1 for r in all_results if r["service_times"])
    with_attendance = sum(1 for r in all_results if r["attendance"])
    with_youth = sum(1 for r in all_results if r["has_youth"])
    with_food = sum(1 for r in all_results if r["has_food_pantry"])
    
    print(f"  Online giving: {with_giving} ({with_giving/processed*100:.1f}%)")
    print(f"  Pastor named: {with_pastor} ({with_pastor/processed*100:.1f}%)")
    print(f"  Service times: {with_times} ({with_times/processed*100:.1f}%)")
    print(f"  Attendance est: {with_attendance} ({with_attendance/processed*100:.1f}%)")
    print(f"  Youth ministry: {with_youth}")
    print(f"  Food pantry: {with_food}")
    
    # Save
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "church_name","website","pastors","service_times","ministries",
            "languages","online_giving","attendance","church_plant",
            "has_youth","has_children","has_food_pantry","has_preschool",
            "facebook","youtube","instagram",
            "affiliation","fb_followers","yt_subscribers","yt_videos",
            "budget_indicators","budget_amount",
        ])
        w.writeheader()
        w.writerows(all_results)
    
    print(f"\nSaved {len(all_results)} profiles to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
