"""
BUILD: Political Data Voter Enrichment Campaign
================================================
Pitches GRID worship-site data (3.5M+ religious sites) to political data companies
as voter enrichment & activation data. Religious affiliation predicts voting behavior,
churches are polling locations & GOTV hubs.

Contacts sourced from CPPA California Data Broker Registry (2026).
Privacy emails route through legal → forwarded to BD teams.
"""

import json, os
from pathlib import Path
from datetime import datetime

OUT = Path("outputs/outreach")
OUT.mkdir(parents=True, exist_ok=True)
QUEUE_FILE = OUT / "unified_queue.jsonl"

NOW = datetime.now().strftime("%B %d, %Y")

# ── Shared data points ──────────────────────────────────
GRID_STATS = """GRID STATS:
• 3,537,585 worship sites across 200+ countries
• 1,074,000+ in the United States (all 50 states + DC)
• 85+ faith traditions classified (Christian denominations, Muslim, Jewish, Hindu, etc.)
• Geocoded with GPS coordinates, addresses, phone numbers, websites
• Census tract / congressional district / state legislative district mapped
• Denomination hierarchy data (Catholic dioceses, Lutheran synods, SBC conventions, etc.)
• 614,000 US addresses normalized (IRS + Overture/OSM)
• County-level RUCC codes, ACS demographics, election results appended"""

CONTACT_ENRICHMENT = """CONTACT & ENRICHMENT:
• 463,000+ phone numbers, emails, websites (church_contact_values)
• 209,000+ SBA PPP loan records linked to churches
• 2010 & 2020 ARDA county-denomination adherent counts (300+ denominations)"""

ELECTION_DATA = """ELECTION & CENSUS MAPPING:
• 1,074K US churches → congressional districts, state legislative districts, counties
• Canada: 66K churches → 343 federal electoral districts
• UK: 100K churches → 650 Westminster constituencies
• Brazil: 205K churches → 5,120 municipalities + 2022 presidential election results
• India: 220K churches → 543 Lok Sabha constituencies"""

# ── Signature ────────────────────────────────────────────
SIG = """--
Charles Prescott
Creator, GRID — Global Religious Infrastructure Database
JD, LLM (Taxation) | Trinity College, University of Toronto
charlesaprescottjr@gmail.com | 843-504-4542
https://buymeacoffee.com/CharlesPrescott"""

# ── Subject line ─────────────────────────────────────────
SUBJECT = "GRID: 3.5M Worship Sites as Voter Enrichment & Activation Data"

# ── Contacts from CPPA Registry ──────────────────────────
CONTACTS = [
    # Tier 1: Core Political Data Ecosystem
    {"tier": "T1", "org": "Aristotle International, Inc.", "email": "dpo@aristotle.com",
     "pitch": "non-partisan, 40-year track record, compliance + data + software suite"},
    {"tier": "T1", "org": "i360, LLC", "email": "privacy@i-360.com",
     "pitch": "290M voter/consumer database, GOP-aligned, predictive analytics for GOTV"},
    {"tier": "T1", "org": "L2 Political (Labels & Lists, Inc.)", "email": "lauren.pembo@l2political.com",
     "pitch": "200M registered voters, 2.3B voting history records, clean national voter file"},
    {"tier": "T1", "org": "TargetSmart Communications LLC", "email": "privacy@targetsmart.com",
     "pitch": "Democratic/progressive leader, accurate cell phone data, media buying platform"},

    # Tier 2: Major Consumer Data Brokers with Political Offerings
    {"tier": "T2", "org": "Acxiom LLC", "email": "askprivacy@acxiom.com",
     "pitch": "12,000+ global data attributes, Personicx segmentation, Real Identity matching"},
    {"tier": "T2", "org": "Epsilon Data Management, LLC", "email": "privacy@epsilon.com",
     "pitch": "single consumer view across channels, ethically sourced data, Omnicom-backed"},
    {"tier": "T2", "org": "Experian (Experian Marketing Solutions, LLC)", "email": "CA_DROP_EMS@experian.com",
     "pitch": "Political Personas, financial/demographic data, donor targeting, 85% FCRA-regulated"},

    # Tier 3: Technology, Analytics, and Specialized Firms
    {"tier": "T3", "org": "Catalist LLC", "email": "privacy@catalist.us",
     "pitch": "central progressive data hub, interactive dashboards, historic election modeling"},
    {"tier": "T3", "org": "Civis Analytics, Inc.", "email": "dataprotectionmail@civisanalytics.com",
     "pitch": "data science firm, precision targeting, Obama 2012 roots, predictive modeling"},
    {"tier": "T3", "org": "LiveRamp Holdings, Inc.", "email": "consumercare@liveramp.com",
     "pitch": "data collaboration network, privacy-safe identity resolution, post-cookie future"},

    # Tier 4: Niche or Regionally Focused
    {"tier": "T4", "org": "Accurate Append Inc.", "email": "shawn@accurateappend.com",
     "pitch": "voter data enrichment, donor profiling, Donor Score product, phone/email append"},
    {"tier": "T4", "org": "Grassroots Analytics", "email": "operations@grassrootsanalytics.com",
     "pitch": "hyper-targeted donor prospecting, fundraising tools, all campaign levels"},
]

# ── Build body for each contact ──────────────────────────
def build_body(c):
    tier_intro = {
        "T1": "As a core player in the political data ecosystem, your voter file is the backbone of campaign targeting.",
        "T2": "Your consumer data scale and political offerings make you a natural partner for faith-based voter enrichment.",
        "T3": "Your analytics and technology platform would benefit from religious affiliation as a behavioral predictor.",
        "T4": "Your specialized voter data services are a perfect fit for faith-based enrichment and activation.",
    }

    return f"""Subject: {SUBJECT}

Dear {c['org']} Data Team,

I'm reaching out because I've built GRID — the Global Religious Infrastructure Database — and I believe it can strengthen your voter data products.

{GRID_STATS}

WHY RELIGIOUS DATA MATTERS FOR VOTER TARGETING:
Religious affiliation is one of the strongest predictors of voter turnout and party preference. GRID maps every church, mosque, synagogue, temple, and gurdwara in America — with classification granularity that no voter file has:

• 200+ Christian denominations (not just "Protestant" — but ELCA vs. LCMS vs. SBC vs. AME, etc.)
• 17 Muslim traditions (Sunni/Shia/Twelver/Ismaili/Salafi/etc.)
• 12 Jewish movements (Orthodox/Chabad/Reform/Conservative/Reconstructionist/etc.)
• Hindu, Sikh, Buddhist, Jain, Baháʼí, and more — all classified

{CONTACT_ENRICHMENT}

{ELECTION_DATA}

{'-'*50}
WHY {c['org'].upper()}:
{c['pitch']}. {tier_intro.get(c['tier'], '')}

I'd love to explore how GRID data could integrate with your platform — whether as bulk enrichment, API access, or a custom data partnership. Happy to schedule a call or send sample data for your analysts to evaluate.

{SIG}"""

# ── Build queue ──────────────────────────────────────────
queue = []
for c in CONTACTS:
    body = build_body(c)
    entry = {
        "to": c["email"],
        "subject": SUBJECT,
        "body": body,
        "source": "political_data",
        "org": c["org"],
        "tier": c["tier"],
        "queued": NOW,
    }
    queue.append(entry)
    print(f"  ✅ {c['tier']} | {c['org'][:45]:45s} → {c['email']}")

# ── Write to unified queue ───────────────────────────────
existing = []
if QUEUE_FILE.exists():
    existing = [json.loads(l) for l in QUEUE_FILE.read_text(encoding="utf-8").strip().split("\n") if l.strip()]

# Filter out any duplicates by email
existing_emails = {e.get("to", "").lower() for e in existing}
new_entries = [q for q in queue if q["to"].lower() not in existing_emails]
dupes = [q for q in queue if q["to"].lower() in existing_emails]

# Append new entries
all_entries = existing + new_entries
with open(QUEUE_FILE, "w", encoding="utf-8") as f:
    for item in all_entries:
        f.write(json.dumps(item) + "\n")

print(f"\n{'='*60}")
print(f"QUEUE SUMMARY")
print(f"{'='*60}")
print(f"  Existing entries: {len(existing)}")
print(f"  New political data: {len(new_entries)}")
print(f"  Duplicates skipped: {len(dupes)}")
print(f"  Total queue: {len(all_entries)}")
print(f"  Estimated send time: {len(all_entries)*3/60:.1f} hours")
print(f"\n  Queue file: {QUEUE_FILE}")

if new_entries:
    print(f"\n  Preview of first entry body:")
    preview = new_entries[0]["body"][:500]
    print(f"  {preview}...")
else:
    print("\n  ⚠️ All entries already in queue — nothing new added.")
