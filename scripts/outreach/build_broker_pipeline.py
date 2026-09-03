"""
BUILD: Data Broker & Mailing List Reseller Pipeline
=====================================================
Pitches GRID as a wholesale data product to mailing list brokers,
data resellers, lead generation platforms, and church directory companies.

These companies BUY data, mark it up, and resell it. They care about:
  - Record counts and fill rates
  - Uniqueness (what makes GRID different from InfoUSA/Data Axle)
  - Margin potential
  - Ready-to-sell product formats

Usage:
    python scripts/outreach/build_broker_pipeline.py
    python scripts/outreach/build_broker_pipeline.py --preview
"""

import json, os
from pathlib import Path
from datetime import datetime

OUT = Path("outputs/outreach")
OUT.mkdir(parents=True, exist_ok=True)
QUEUE_FILE = OUT / "unified_queue.jsonl"

NOW = datetime.now().strftime("%B %d, %Y")

# ══════════════════════════════════════════════════════════════════════════
SUBJECT = "GRID: 1M US Churches — Wholesale Mailing List for Resale"

STATS = """WHOLESALE DATA PRODUCT — US RELIGIOUS INSTITUTIONS:

  1,031,854 worship sites (all 50 states + DC + territories)
  1,000,000+ with mailing addresses (city, state, ZIP)
    398,000 with website URLs
     48,000 with phone numbers
     17,000 with email addresses
    934,000 with building square footage
    697,000 with FBI crime risk scores (state-level)
    938,000 with FEMA disaster risk scores (16 hazard types)

  FAITH CLASSIFICATION (nobody else has this):
    200+ Christian denominations (SBC, UMC, ELCA, LCMS, Catholic, Orthodox, etc.)
    17 Muslim traditions (Sunni, Shia, Twelver, Ismaili, Salafi, etc.)
    12 Jewish movements (Orthodox, Chabad, Reform, Conservative, etc.)
    Hindu, Sikh, Buddhist, Jain, Bahai — all classified

  WHAT MAKES THIS DIFFERENT FROM DATAAXLE/INFOUSA:
    - Denomination-level taxonomy they can't match
    - Building square footage (934K records) — sell to roofers, HVAC, insurers
    - FEMA disaster risk per building — sell to insurance agents
    - FBI crime scores per neighborhood — sell to security companies
    - GPS coordinates, not ZIP centroids
    - Hierarchy data: what diocese/synod does each church belong to?

  FORMATS: CSV, Excel, API (JSON). Quarterly refresh available.
  SAMPLES: Free 100-record sample for qualified brokers."""

SIG = """--
Charles Prescott
Creator, GRID — Global Religious Infrastructure Database
JD, LLM (Taxation) | Trinity College, University of Toronto
charlesaprescottjr@gmail.com | 843-504-4542
https://buymeacoffee.com/CharlesPrescott"""

# ══════════════════════════════════════════════════════════════════════════
CONTACTS = [
    # Tier 1: Major Data Brokers
    {"tier": "T1", "org": "Data Axle (formerly Infogroup)", "dept": "Data Acquisition",
     "email": "data.acquisition@data-axle.com",
     "pitch": "Data Axle is the #1 business data provider. GRID's 1M US churches with denomination-level taxonomy, building sqft, and FEMA risk scores is a unique vertical dataset your sales teams can't get from your own compiler."},

    {"tier": "T1", "org": "InfoUSA", "dept": "Data Licensing",
     "email": "datasales@infousa.com",
     "pitch": "InfoUSA's church list is generic 'church' tags. GRID adds 200+ denomination classifications, building sqft, disaster risk scores, and crime data — ready to resell at premium pricing to your existing customer base."},

    {"tier": "T1", "org": "Dun & Bradstreet", "dept": "Data Partnerships",
     "email": "dnbdata@dnb.com",
     "pitch": "D&B's Hoovers database has religious orgs but not at GRID's granularity. 1M US worship sites with GPS, building sqft, FEMA risk, and denominational taxonomy — complementary to your existing business data."},

    {"tier": "T1", "org": "Salesgenie", "dept": "Data Acquisition",
     "email": "data@salesgenie.com",
     "pitch": "Salesgenie's small business focus includes churches — but without GRID's taxonomy depth. Add 200+ denominations, building characteristics, and risk scores to your church category."},

    {"tier": "T1", "org": "Exact Data", "dept": "Data Partnerships",
     "email": "partners@exactdata.com",
     "pitch": "Exact Data specializes in custom mailing lists. GRID's 1M US churches with unique attributes (sqft, FEMA, crime, denomination taxonomy) is a high-margin product for your insurance, construction, and nonprofit clients."},

    # Tier 2: Lead Intelligence Platforms
    {"tier": "T2", "org": "ZoomInfo", "dept": "Data Partnerships",
     "email": "data@zoominfo.com",
     "pitch": "ZoomInfo's B2B database has companies and contacts. GRID adds 1M religious institutions — a vertical you're light on — with taxonomy depth no one else has."},

    {"tier": "T2", "org": "Apollo.io", "dept": "Data Partnerships",
     "email": "partnerships@apollo.io",
     "pitch": "Apollo's lead database is strong on tech and business. GRID fills a gap: 1M US worship sites with contacts, building data, and risk scores — sell to vendors targeting the faith market."},

    {"tier": "T2", "org": "Seamless.ai", "dept": "Data Acquisition",
     "email": "data@seamless.ai",
     "pitch": "Seamless.ai's contact database can add 48K church phone numbers and 17K church emails from GRID — plus 1M address-only records for direct mail campaigns targeting faith communities."},

    {"tier": "T2", "org": "Lusha", "dept": "Data Partnerships",
     "email": "partnerships@lusha.com",
     "pitch": "Lusha's contact intelligence platform + GRID's 1M US worship sites with taxonomy depth = new vertical for your sales team. Churches buy everything from insurance to software to roofing."},

    {"tier": "T2", "org": "UpLead", "dept": "Data Partnerships",
     "email": "partners@uplead.com",
     "pitch": "UpLead's B2B data platform can expand into the faith vertical with GRID: 1M US churches, 200+ denominations, 934K with building sqft, 398K with websites."},

    {"tier": "T2", "org": "Cognism", "dept": "Data Partnerships",
     "email": "partners@cognism.com",
     "pitch": "Cognism's B2B data + GRID's US worship site taxonomy = a new category for your platform. 1M records with GPS, building data, risk scores, and denominational classification."},

    # Tier 3: Church-Specific Directories & Platforms
    {"tier": "T3", "org": "US Church Directory (uschurchdirectory.com)", "dept": "Data",
     "email": "info@uschurchdirectory.com",
     "pitch": "Your directory could add 200+ denomination classifications, building sqft, and GPS coordinates from GRID. 1M US churches ready to enrich your existing listings — a partnership that makes you the most complete church directory online."},

    {"tier": "T3", "org": "Church Angel (churchangel.com)", "dept": "Partnerships",
     "email": "support@churchangel.com",
     "pitch": "Church Angel's directory + GRID's 1M-church taxonomy database = the definitive church finder. Add building data, risk scores, and denominational depth to every listing."},

    {"tier": "T3", "org": "FaithStreet", "dept": "Partnerships",
     "email": "hello@faithstreet.com",
     "pitch": "FaithStreet connects people to churches. GRID maps every US worship site with GPS, denomination, and contact data — power your church discovery platform with the most complete dataset available."},

    {"tier": "T3", "org": "Outreach, Inc. (church marketing lists)", "dept": "Data Acquisition",
     "email": "info@outreach.com",
     "pitch": "Outreach Inc. sells church marketing lists. GRID's 1M US churches with denomination taxonomy, building data, and risk scores is a premium upgrade to your existing church database."},

    # Tier 4: Specialized Resellers
    {"tier": "T4", "org": "Melissa Data", "dept": "Data Partnerships",
     "email": "partners@melissa.com",
     "pitch": "Melissa's address verification + GRID's religious institution data = powerful combination. 1M US worship sites with verified addresses, GPS, building data, and denominational taxonomy ready for your data marketplace."},

    {"tier": "T4", "org": "Lake B2B", "dept": "Data Acquisition",
     "email": "info@lakeb2b.com",
     "pitch": "Lake B2B's custom list building + GRID's 1M church records with unique attributes (sqft, FEMA risk, crime data) = high-value custom lists for insurance, construction, and nonprofit verticals."},

    {"tier": "T4", "org": "BookYourData", "dept": "Data Partnerships",
     "email": "partners@bookyourdata.com",
     "pitch": "BookYourData's pay-per-lead model + GRID's church taxonomy = instant new vertical. 1M US worship sites with contact data, building characteristics, and risk scores — ready for your platform."},

    {"tier": "T4", "org": "TargetNXT", "dept": "Data Acquisition",
     "email": "info@targetnxt.com",
     "pitch": "TargetNXT's B2B data services + GRID's 1M US churches with 200+ denomination classifications and building data = expand your faith-based offerings with the most comprehensive church list available."},

    # Tier 5: Direct Mail & Print
    {"tier": "T5", "org": "Modern Postcard (direct mail for churches)", "dept": "Data",
     "email": "data@modernpostcard.com",
     "pitch": "Modern Postcard's direct mail campaigns + GRID's 1M church addresses with denomination targeting = powerful combination. Help your clients target specific faith communities with precision."},

    {"tier": "T5", "org": "PostcardMania", "dept": "Data Partnerships",
     "email": "partners@postcardmania.com",
     "pitch": "PostcardMania's direct mail platform can offer church-specific targeting using GRID data: 1M US worship sites sorted by denomination, building size, and location."},

    {"tier": "T5", "org": "Vistaprint (Digital Marketing for Churches)", "dept": "Partnerships",
     "email": "partnerships@vista.com",
     "pitch": "Vistaprint's church customer base + GRID's 1M-church taxonomy = upsell opportunity. Help your church clients target other churches or understand their market with GRID data."},
]

# ══════════════════════════════════════════════════════════════════════════

def build_body(c):
    tier_angle = {
        "T1": "You already sell church lists — GRID makes yours the best on the market with taxonomy depth and risk data nobody else has.",
        "T2": "Your platform is light on religious institutions. GRID fills that vertical with 1M classified, enriched records ready for your users.",
        "T3": "Your church directory or platform + GRID's complete taxonomy = the definitive resource. Let's talk partnership.",
        "T4": "GRID data can differentiate your offerings in the faith vertical. 1M records with unique attributes your competitors can't source.",
        "T5": "Your direct mail clients targeting churches need GRID's precision: mail to ELCA churches, not just 'churches.'",
    }

    return f"""Subject: {SUBJECT}

Hi {c['org']},

I've built GRID — the most comprehensive database of US religious institutions ever assembled — and I'm looking for data brokers and resellers to bring it to market.

{STATS}

WHY {c['org'].upper()}:
{c['pitch']}

{tier_angle.get(c['tier'], '')}

I'm offering wholesale pricing for bulk licensing or revenue-share partnerships. Free 100-record sample available for qualified brokers — just reply and tell me what slice you'd like to see.

{SIG}"""

# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    preview_only = "--preview" in sys.argv

    print("=" * 70)
    print("DATA BROKER & MAILING LIST RESELLER PIPELINE")
    print("=" * 70)
    print(f"  Target: {len(CONTACTS)} data brokers & resellers")
    print()

    queue = []
    for c in CONTACTS:
        body = build_body(c)
        entry = {
            "to": c["email"],
            "subject": SUBJECT,
            "body": body,
            "source": "broker",
            "org": c["org"],
            "tier": c["tier"],
            "queued": NOW,
        }
        queue.append(entry)
        print(f"  ✅ {c['tier']} | {c['org'][:50]:50s} -> {c['email']}")

    if preview_only:
        print(f"\n{'='*70}")
        print(f"PREVIEW — {len(queue)} contacts. Remove --preview to write to queue.")
        sys.exit(0)

    # Read existing queue
    existing = []
    if QUEUE_FILE.exists():
        existing = [json.loads(l) for l in QUEUE_FILE.read_text(encoding="utf-8").strip().split("\n") if l.strip()]

    existing_emails = {e.get("to", "").lower() for e in existing}
    new_entries = [q for q in queue if q["to"].lower() not in existing_emails]
    dupes = [q for q in queue if q["to"].lower() in existing_emails]

    all_entries = existing + new_entries
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        for item in all_entries:
            f.write(json.dumps(item) + "\n")

    print(f"\n{'='*70}")
    print(f"QUEUE: {len(new_entries)} new brokers added | {len(dupes)} duplicates | {len(all_entries)} total")
    print(f"  Est. send time: {len(all_entries)*3/60:.1f} hours")
