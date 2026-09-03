"""
HUMANITARIAN / DISASTER RELIEF OUTREACH CAMPAIGN
Pitches GRID as pre-positioned shelter data for every disaster zone.
"""
import json
from pathlib import Path
from datetime import datetime

OUT = Path("outputs/outreach")
QUEUE_FILE = OUT / "unified_queue.jsonl"
MAP_FILE = OUT / "map_us_disaster_risk.png"
BQ_LINK = "https://console.cloud.google.com/bigquery?project=american-rel-infra&ws=!1m0"
NOW = datetime.now().strftime("%B %d, %Y")

SIG = """--
Charles Prescott
Creator, GRID - Global Religious Infrastructure Database
JD, LLM (Taxation) | Trinity College, University of Toronto
charlesaprescottjr@gmail.com | 843-504-4542"""

leads = json.loads(Path("outputs/outreach/humanitarian_leads.json").read_text())

SUBJECT = "GRID: Pre-Positioned Shelter Data - 3.5M Worship Sites for Disaster Response"

BODY_TEMPLATE = """Subject: {subject}

Dear {org} Team,

During every disaster - hurricane, earthquake, flood, conflict - the first shelters to open are churches, mosques, and temples. But emergency planners have never had a complete map of where they are. Until now.

GRID (Global Religious Infrastructure Database) maps 3,537,585 worship sites worldwide:

WHAT THIS MEANS FOR DISASTER RESPONSE:
- Pre-positioned shelter inventory: Every church, mosque, and temple is a potential shelter. GRID gives you the full map before the disaster hits.
- Contact data: 463K+ phone numbers and emails for immediate coordination with faith leaders
- GPS coordinates: Exact locations for supply drops, evacuation routing, and needs assessment
- Capacity estimation: Building data (where available) to estimate shelter capacity
- Faith classification: 200+ Christian denominations, 17 Muslim traditions - know which community you're serving
- Already mapped: US sites cross-referenced with FEMA National Risk Index, census tracts, and county demographics

{tailored_pitch}

THE DATA:
- 3,537,585 worship sites across 200+ countries
- Every site has GPS, address, faith tradition, denomination hierarchy
- 463K+ verified phone numbers, emails, websites
- 614K US addresses normalized
- US sites mapped to FEMA NRI risk scores, census tracts, counties
- Catholic parish networks (33K rows), Anglican communion (77K), LDS stakes (19K) mapped

You can query the full dataset now in BigQuery:
{BQ_LINK}

I'm reaching out because GRID can save hours - sometimes days - in the critical first 72 hours of a response. Knowing exactly where every house of worship is located means faster shelter openings, more efficient supply distribution, and better coordination with community leaders.

Happy to discuss how GRID could integrate into your GIS and emergency planning workflows. I can provide custom extracts by country, region, or disaster type.

{SIG}"""

# Sector-specific tailored pitches
SECTOR_PITCHES = {
    "UN Coordination": "UN OCHA's HDX platform and Humanitarian Data Exchange are the backbone of coordinated response. GRID could be the religious infrastructure layer that every cluster - Shelter, Health, WASH, Food Security - uses to preposition aid. I'd love to explore publishing GRID as an HDX dataset.",
    "UN Agency": "Your agency's field operations depend on knowing where communities gather. GRID maps every worship site in your countries of operation - with faith classification that helps you engage the right community leaders. Whether it's WFP food distribution through mosque networks or UNHCR camp planning near churches, GRID provides the infrastructure layer.",
    "Government": "Your disaster response operations need pre-positioned community asset data. GRID cross-references every US worship site with FEMA National Risk Index scores - so you know exactly which shelters are in flood zones, earthquake zones, or hurricane paths before the disaster. Combined with county demographics and RUCC codes for rural/urban classification.",
    "INGO": "Your field teams already partner with local faith communities. GRID gives you the complete map of every church, mosque, and temple in your operating areas - with phone numbers to reach faith leaders immediately. Catholic Relief Services: GRID has 33K Catholic parish hierarchy rows. World Vision: church-based networks mapped across 90+ countries. This is your community infrastructure layer.",
    "Emergency Response": "In the first 72 hours of a disaster, knowing where every house of worship is located means the difference between chaos and coordination. GRID maps worship sites with GPS coordinates, contact data, and FEMA risk scores - so your teams know exactly where to go before they deploy. Pre-position your supply chains around faith infrastructure.",
    "Faith-Based": "Your organization's entire model is built on faith community networks. GRID maps every church, mosque, synagogue, and temple in your operating areas - with denominational classification so you know the difference between a Catholic parish, an SBC church, and an independent Pentecostal congregation. This is your own network, mapped and enriched.",
}

def build_body(lead):
    org = lead["org"]
    sector = lead.get("sector", "INGO")
    tailored = SECTOR_PITCHES.get(sector, SECTOR_PITCHES["INGO"])
    return BODY_TEMPLATE.format(
        subject=SUBJECT, org=org, tailored_pitch=tailored, BQ_LINK=BQ_LINK, SIG=SIG
    )

# Build queue
queue = []
for lead in leads:
    body = build_body(lead)
    entry = {
        "to": lead["email"],
        "subject": SUBJECT,
        "body": body,
        "source": "humanitarian",
        "org": lead["org"],
        "sector": lead.get("sector", ""),
        "tier": lead.get("tier", 0),
        "queued": NOW,
    }
    queue.append(entry)
    print(f"  T{lead.get('tier','?')} | {lead['org'][:48]:48s} -> {lead['email']}")

# Write
existing = []
if QUEUE_FILE.exists():
    existing = [json.loads(l) for l in QUEUE_FILE.read_text(encoding="utf-8").strip().split("\n") if l.strip()]

existing_emails = {e.get("to", "").lower() for e in existing}
new_entries = [q for q in queue if q["to"].lower() not in existing_emails]
dupes = len(queue) - len(new_entries)

all_entries = existing + new_entries
with open(QUEUE_FILE, "w", encoding="utf-8") as f:
    for item in all_entries:
        f.write(json.dumps(item) + "\n")

print(f"\n{'='*60}")
print(f"HUMANITARIAN CAMPAIGN QUEUED")
print(f"{'='*60}")
print(f"  Leads: {len(queue)}")
print(f"  New queued: {len(new_entries)}")
print(f"  Duplicates skipped: {dupes}")
print(f"  Existing queue: {len(existing)}")
print(f"  Total queue: {len(all_entries)}")
if MAP_FILE.exists():
    print(f"  Disaster map: {MAP_FILE} ({MAP_FILE.stat().st_size/1024:.0f} KB)")
print(f"  BigQuery: {BQ_LINK}")
