"""
MASS CPPA BROKER CAMPAIGN — targets all 581 California-registered data brokers
with tailored pitches based on their business type.

Categories & Pitches:
  list_broker       → Church contact data (463K phone/email/website)
  adtech            → Worship site audience segments for ad targeting
  people_search     → Church location/leadership data enrichment
  real_estate       → Church property assessment & valuation data
  financial_credit  → Church PPP loan data (209K SBA loans)
  identity_fraud    → Religious org identity verification data
  healthcare        → Faith-based health demographic data
  political         → Voter enrichment (religious affiliation data)
  b2b_sales         → Religious organization B2B contacts
  automotive        → Church parking/demographic enrichment
  general           → Full GRID dataset overview

Automatically skips:
  - Already-queued emails
  - Bounced addresses
  - Government entities (FBI, etc.)
  - Major companies we already pitched (political tier)
"""

import csv, json, os, re
from pathlib import Path
from datetime import datetime
from collections import Counter

OUT = Path("outputs/outreach")
QUEUE_FILE = OUT / "unified_queue.jsonl"
CSV_PATH = Path("scripts/outreach/California Data Broker Registry 2026.csv")
NOW = datetime.now().strftime("%B %d, %Y")

# ── Already-pitched companies (from political campaign) ──
ALREADY_PITCHED = {
    "dpo@aristotle.com", "privacy@i-360.com", "lauren.pembo@l2political.com",
    "privacy@targetsmart.com", "askprivacy@acxiom.com", "privacy@epsilon.com",
    "CA_DROP_EMS@experian.com", "privacy@catalist.us",
    "dataprotectionmail@civisanalytics.com", "consumercare@liveramp.com",
    "shawn@accurateappend.com", "operations@grassrootsanalytics.com",
}

# ── Government / non-commercial entities to skip ──
SKIP_PATTERNS = [
    "fbi", "cia", "homeland security", "department of", "federal bureau",
    "government", "state of", "city of", "county of", "police", "sheriff",
    "district attorney", "public defender", "court", "judicial",
    "united nations", "world bank", "federal reserve",
]

# ── Signature ──
SIG = """--
Charles Prescott
Creator, GRID — Global Religious Infrastructure Database
JD, LLM (Taxation) | Trinity College, University of Toronto
charlesaprescottjr@gmail.com | 843-504-4542
https://buymeacoffee.com/CharlesPrescott"""

# ── GRID stats by category ──
STATS = {
    "list_broker": """GRID: 3.5M worship sites with 463K+ verified phone numbers, emails, and websites.
200+ Christian denominations classified, 17 Muslim traditions, 12 Jewish movements, plus Hindu, Sikh, Buddhist, Jain, Baháʼí. 614K US addresses normalized. Perfect for list enrichment.""",

    "adtech": """GRID: 3.5M geocoded worship sites worldwide — 1M+ in US. Every church, mosque, synagogue, temple mapped with GPS coordinates and faith classification. Build faith-based audience segments for ad targeting. Census tract, congressional district, and county-level mappings included.""",

    "people_search": """GRID: 3.5M worship sites with clergy names, addresses, phones, and denominational hierarchies. Catholic dioceses, Lutheran synods, Baptist conventions, LDS stakes — all mapped. Perfect for people search enrichment and identity resolution.""",

    "real_estate": """GRID: 3.5M worship sites with property data. Boston property assessments integrated (924 churches with valuations, year built, condition). PPP loan data (209K loans matched to churches). Addresses normalized against IRS + Overture/OSM. Property data enrichment opportunity.""",

    "financial_credit": """GRID: 3.5M worship sites. 209K SBA PPP loans matched to churches — financial behavior data. 2010 & 2020 ARDA county-denomination adherent counts (300+ denominations). RUCC county codes appended. Financial demographic enrichment for religious organizations.""",

    "identity_fraud": """GRID: 3.5M worship sites with verified addresses, phones, and denominational affiliations. 614K US addresses normalized. Catholic diocese hierarchy (33K rows), LDS hierarchy (19K rows), Anglican communion (77K rows). Identity verification for religious organizations.""",

    "healthcare": """GRID: 3.5M worship sites mapped with faith tradition and county-level demographics. Faith-based health demographic data. Religious affiliation as a determinant of health behaviors. County census data appended. Healthcare marketing and research enrichment.""",

    "political": """GRID: 3.5M worship sites. 1M+ US churches mapped to congressional districts, state legislative districts, and counties. Religious affiliation is one of the strongest predictors of voter behavior. 200+ Christian denominations classified — not just "Protestant" but ELCA vs LCMS vs SBC.""",

    "b2b_sales": """GRID: 3.5M worship sites — the most comprehensive database of religious organizations worldwide. 463K+ verified contacts (phone/email/website). 85+ faith traditions. Perfect for B2B sales targeting religious organizations, faith-based nonprofits, and denominational HQs.""",

    "automotive": """GRID: 3.5M worship sites with GPS coordinates, addresses, and county demographics. Church parking lots, congregation sizes, and faith demographics. Perfect for automotive marketing and location-based targeting enrichment.""",

    "general": """GRID: 3.5M worship sites across 200+ countries. 1M+ in the US. 85+ faith traditions classified. 463K+ contacts. Geocoded with GPS. Census/election district mapped. Denomination hierarchies built. The world's most comprehensive religious infrastructure database.""",
}

# ── Subject lines by category ──
SUBJECTS = {
    "list_broker": "GRID: 463K Religious Org Contacts for List Enrichment",
    "adtech": "GRID: Faith-Based Audience Segments — 3.5M Worship Sites",
    "people_search": "GRID: 3.5M Worship Sites for People Search Enrichment",
    "real_estate": "GRID: Church Property Data — 3.5M Sites with Valuations",
    "financial_credit": "GRID: Religious Org Financial Data — 209K PPP Loans",
    "identity_fraud": "GRID: Religious Org Identity Data for Verification",
    "healthcare": "GRID: Faith-Based Health Demographics",
    "political": "GRID: Religious Affiliation Voter Enrichment Data",
    "b2b_sales": "GRID: 463K Religious Organization B2B Contacts",
    "automotive": "GRID: Worship Site Location Data for Automotive",
    "general": "GRID: 3.5M Worship Sites — Global Religious Infrastructure Database",
}

# ── Category classification ──
def classify_broker(name, website, collects_minors, collects_ids, collects_geo,
                     collects_biometric, collects_health, collects_gender,
                     collects_sexual, collects_citizen, collects_union,
                     collects_logins, sold_feds, sold_states, sold_leo,
                     sold_foreign, sold_genai, fcra, glba, hipaa, comments):
    """Classify broker into a category based on their profile."""
    combined = (name + " " + website).lower()
    comments_lower = (comments or "").lower()
    
    # Government check
    for p in SKIP_PATTERNS:
        if p in combined or p in comments_lower:
            return None
    
    # Website domain extraction
    domain = ""
    if website:
        domain = website.lower().replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
    
    # Already pitched political companies
    if any(kw in combined for kw in ["aristotle", "i360", "l2 political", "targetsmart",
                                       "catalist", "civis analytics", "liveramp",
                                       "accurate append", "grassroots analytics"]):
        return "already_pitched"
    
    # Explicit category signals from name/website
    name_web = name.lower() + " " + website.lower()
    
    # List / lead generation
    if any(kw in name_web for kw in [
        "list", "lead", "mailing", "email list", "phone list", "data list",
        "datadelivers", "dataline", "databroker", "mailinglists",
        "telemarketing", "direct mail", "directmail", "mailing list",
        "contact list", "lead generation", "leadgeneration", "leadgen",
        "saleslead", "sales lead", "prospecting", "prospect list",
        "mailing data", "targeting list", "listbroker", "list broker",
        "email marketing", "emailmarketing", "emaillist",
    ]):
        return "list_broker"
    
    # AdTech / MarTech
    if any(kw in name_web for kw in [
        "ad ", "ads ", "adtech", "ad tech", "advertising", "ad exchange",
        "dsp", "ssp", "programmatic", "audience", "targeting", "segment",
        "media buying", "mediabuying", "demand side", "supply side",
        "native ad", "video ad", "display ad", "connected tv", "ctv",
        "retargeting", "ad network", "adnetwork", "ad platform",
        "publisher", "monetization", "monetize",
    ]):
        return "adtech"
    if "marketing" in name_web and not any(kw in name_web for kw in ["list", "lead", "email"]):
        return "adtech"
    
    # People search
    if any(kw in name_web for kw in [
        "people search", "peoplesearch", "people find", "peoplefinder",
        "background check", "backgroundcheck", "public record",
        "publicrecord", "peoplelooker", "people look", "arrest",
        "mugshot", "criminal", "inmate", "checkpeople", "check people",
        "beenverified", "truthfinder", "instant check", "lookup",
        "people data", "peopledata", "people whiz",
    ]):
        return "people_search"
    
    # Real estate / property
    if any(kw in name_web for kw in [
        "real estate", "realestate", "property", "home", "house",
        "mortgage", "title ", "deed", "parcel", "land", "zoning",
        "propertyradar", "costar", "buxton", "remodeling",
        "foreclosure", "building permit",
    ]) or domain.endswith((".realestate", ".property", ".homes")):
        return "real_estate"
    
    # Financial / credit
    if any(kw in name_web for kw in [
        "credit", "finance", "financial", "loan", "lending", "bank",
        "insurance", "underwriting", "fico", "score", "risk",
        "equifax", "experian", "transunion", "credit bureau",
        "debt", "payment", "fico", "credit report",
    ]) or fcra.lower() == "yes" or glba.lower() == "yes":
        return "financial_credit"
    
    # Identity / fraud
    if any(kw in name_web for kw in [
        "identity", "fraud", "verification", "verify", "kyc", "aml",
        "authentication", "biometric", "fideo", "clearview",
        "face recognition", "telesign", "spycloud",
    ]) or collects_biometric.lower() == "yes":
        return "identity_fraud"
    
    # Healthcare
    if any(kw in name_web for kw in [
        "health", "medical", "patient", "pharma", "clinical",
        "hospital", "doctor", "physician", "drug", "prescription",
        "healthcare", "healthwise", "semantiq",
    ]) or hipaa.lower() == "yes" or collects_health.lower() == "yes":
        return "healthcare"
    
    # Automotive
    if any(kw in name_web for kw in [
        "auto", "car", "vehicle", "dealer", "dealership", "automotive",
        "driver", "traffic", "tire", "automobile",
    ]):
        return "automotive"
    
    # B2B / sales intelligence
    if any(kw in name_web for kw in [
        "b2b", "sales intelligence", "salesintel", "sales enablement",
        "account based", "abm", "crm", "contact ", "contactout",
        "leadiq", "zoominfo", "clearbit", "lusha", "apollo",
        "company data", "firmographic", "technographic",
        "business data", "business contact",
    ]):
        return "b2b_sales"
    
    # Political (catch remaining political)
    if any(kw in name_web for kw in [
        "political", "voter", "campaign", "election", "canvass",
        "gotv", "constituent", "congressional", "legislative",
        "advocacy", "grassroots", "polling", "poll ",
        "dspolitical", "blue action", "helix campaign", "tunnl",
        "deep root", "resonate",
    ]):
        return "political"
    
    # Geolocation data
    if collects_geo.lower() == "yes" and not any(kw in name_web for kw in ["ad ", "ads ", "adtech"]):
        if any(kw in name_web for kw in ["location", "geo", "map", "place", "foursquare"]):
            return "adtech"  # location-based advertising
    
    # General data broker signals
    if any(kw in name_web for kw in [
        "data", "analytics", "insight", "intelligence", "database",
        "information", "solution", "platform", "technology",
        "software", "digital", "cloud", "api",
    ]):
        return "general"
    
    return "general"

# ── Build body ──
def build_body(name, email, category, website):
    stats = STATS.get(category, STATS["general"])
    subject = SUBJECTS.get(category, SUBJECTS["general"])
    
    cat_intro = {
        "list_broker": "I noticed you're in the list brokerage space. GRID's contact data for 463K+ religious organizations could be a powerful addition to your inventory.",
        "adtech": "I noticed you're in the ad tech / audience targeting space. GRID's faith-based audience segments could help your clients reach religious communities with precision.",
        "people_search": "I noticed you're in the people search space. GRID's worship site data — with clergy names, addresses, phones, and hierarchies — could enrich your search results.",
        "real_estate": "I noticed you're in the property data space. GRID's church property data — including valuations, year built, and PPP loans — could add a new vertical to your offerings.",
        "financial_credit": "I noticed you're in the financial data space. GRID's church PPP loan data (209K loans) and denominational financials could enrich your datasets.",
        "identity_fraud": "I noticed you're in the identity/fraud space. GRID's verified worship site data could provide ground-truth religious organization identity data.",
        "healthcare": "I noticed you're in the healthcare data space. GRID's faith-based demographic data could enhance your health behavior and community health analytics.",
        "political": "I noticed you're in the political data space. GRID's religious affiliation data is a powerful predictor of voter behavior.",
        "b2b_sales": "I noticed you're in the B2B data space. GRID's 463K+ religious organization contacts could expand your B2B coverage.",
        "automotive": "I noticed you're in the automotive data space. GRID's worship site location data could enrich your location-based targeting.",
        "general": "I noticed you're in the data business. GRID's 3.5M worship site database could complement your existing data offerings.",
    }
    
    return f"""Subject: {subject}

Dear {name} Data Team,

{cats.get(category, cat_intro.get(category, cat_intro['general']))}

{stats}

The data includes:
• 3,537,585 worship sites (1M+ US, rest across 200+ countries)
• GPS coordinates, address, city, state, ZIP for each site
• Faith/tradition classification (200+ Christian denominations, 17 Muslim traditions, etc.)
• 463K+ phone numbers, emails, websites
• Census tract, congressional district, county mappings
• Denomination hierarchy data (Catholic, LDS, Anglican, Lutheran, Baptist, etc.)
• 209K SBA PPP loans matched to churches
• County-level ACS demographics and RUCC codes appended

I'd be happy to send sample data, discuss bulk licensing, or set up an API. This could be a straight data purchase, a revenue-share partnership, or a custom integration — whatever works for your model.

{SIG}"""

# ── Load existing queue & bounces ──
existing_emails = set()
if QUEUE_FILE.exists():
    for line in QUEUE_FILE.read_text(encoding="utf-8").strip().split("\n"):
        if line.strip():
            try:
                e = json.loads(line)
                existing_emails.add(e.get("to", "").lower())
            except:
                pass

bounce_file = OUT / "gmail_bounced.txt"
bounced = set()
if bounce_file.exists():
    bounced = {l.strip().lower() for l in bounce_file.read_text().splitlines() if l.strip()}

# ── Parse CSV ──
print(f"Loading CPPA registry...")
with open(CSV_PATH, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    brokers = list(reader)
print(f"  {len(brokers)} brokers in registry")

# ── Classify & build ──
queue = []
cats = Counter()
skipped = {"already_pitched": 0, "government": 0, "existing": 0, "bounced": 0, "no_email": 0, "queued": 0}

for row in brokers:
    name = row.get(reader.fieldnames[0], "").strip().strip('"')
    email = row.get(reader.fieldnames[3], "").strip().lower()
    website = row.get(reader.fieldnames[2], "").strip()
    phone = row.get(reader.fieldnames[4], "").strip()
    city = row.get(reader.fieldnames[6], "").strip()
    state = row.get(reader.fieldnames[7], "").strip()
    
    collects_ids = row.get(reader.fieldnames[13], "")
    collects_geo = row.get(reader.fieldnames[19], "")
    collects_biometric = row.get(reader.fieldnames[18], "")
    collects_health = row.get(reader.fieldnames[20], "")
    collects_gender = row.get(reader.fieldnames[17], "")
    collects_sexual = row.get(reader.fieldnames[16], "")
    collects_citizen = row.get(reader.fieldnames[14], "")
    collects_union = row.get(reader.fieldnames[15], "")
    collects_logins = row.get(reader.fieldnames[12], "")
    collects_minors = row.get(reader.fieldnames[11], "")
    
    sold_feds = row.get(reader.fieldnames[22], "")
    sold_states = row.get(reader.fieldnames[23], "")
    sold_leo = row.get(reader.fieldnames[24], "")
    sold_foreign = row.get(reader.fieldnames[21], "")
    sold_genai = row.get(reader.fieldnames[25], "")
    
    fcra = row.get(reader.fieldnames[26], "")
    glba = row.get(reader.fieldnames[30], "")
    hipaa = row.get(reader.fieldnames[42], "")
    comments = row.get(reader.fieldnames[76], "")
    
    # Skip empty emails
    if not email or "@" not in email:
        skipped["no_email"] += 1
        continue
    
    # Skip already pitched
    if email in ALREADY_PITCHED:
        skipped["already_pitched"] += 1
        continue
    
    # Skip existing in queue
    if email in existing_emails:
        skipped["existing"] += 1
        continue
    
    # Skip bounced
    if email in bounced:
        skipped["bounced"] += 1
        continue
    
    # Classify
    category = classify_broker(name, website, collects_minors, collects_ids,
                                collects_geo, collects_biometric, collects_health,
                                collects_gender, collects_sexual, collects_citizen,
                                collects_union, collects_logins, sold_feds, sold_states,
                                sold_leo, sold_foreign, sold_genai, fcra, glba, hipaa, comments)
    
    if category is None:
        skipped["government"] += 1
        continue
    if category == "already_pitched":
        skipped["already_pitched"] += 1
        continue
    
    cats[category] += 1
    
    body = build_body(name, email, category, website)
    queue.append({
        "to": email,
        "subject": SUBJECTS.get(category, SUBJECTS["general"]),
        "body": body,
        "source": "cppa_mass",
        "org": name,
        "category": category,
        "website": website,
        "city": city,
        "state": state,
        "queued": NOW,
    })

# ── Write queue ──
existing = []
if QUEUE_FILE.exists():
    existing = [json.loads(l) for l in QUEUE_FILE.read_text(encoding="utf-8").strip().split("\n") if l.strip()]

all_entries = existing + queue
with open(QUEUE_FILE, "w", encoding="utf-8") as f:
    for item in all_entries:
        f.write(json.dumps(item) + "\n")

# ── Summary ──
print(f"\n{'='*60}")
print(f"MASS CPPA CAMPAIGN — COMPLETE")
print(f"{'='*60}")
print(f"  Total brokers in registry: {len(brokers)}")
print(f"  Already pitched (political): {skipped['already_pitched']}")
print(f"  Government/skipped: {skipped['government']}")
print(f"  No email: {skipped['no_email']}")
print(f"  Already in queue: {skipped['existing']}")
print(f"  Bounced: {skipped['bounced']}")
print(f"  NEW QUEUED: {len(queue)}")
print(f"\n  Category breakdown:")
for cat, count in cats.most_common():
    print(f"    {cat:25s}: {count:>4}")
print(f"\n  Existing queue entries: {len(existing)}")
print(f"  Total queue now: {len(all_entries)}")
print(f"  Estimated send time: {len(all_entries)*3/60:.1f} hours ({len(all_entries)*3/3600:.1f} days)")

if queue:
    print(f"\n  Sample entries:")
    for q in queue[:5]:
        print(f"    {q['category']:15s} | {q['org'][:45]:45s} → {q['to']}")
else:
    print("\n  ⚠️ No new entries queued — all already processed.")
