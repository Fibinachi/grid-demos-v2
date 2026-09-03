"""
ACADEMIC OUTREACH CAMPAIGN — targets researchers across 8 disciplines
with discipline-specific GRID maps and BQ access link.
"""

import json, os
from pathlib import Path
from datetime import datetime

OUT = Path("outputs/outreach")
QUEUE_FILE = OUT / "unified_queue.jsonl"
BQ_LINK = "https://console.cloud.google.com/bigquery?project=american-rel-infra&ws=!1m0"
NOW = datetime.now().strftime("%B %d, %Y")
SIG = """—
Charles Prescott
Creator, GRID — Global Religious Infrastructure Database
JD, LLM (Taxation) | Trinity College, University of Toronto
charlesaprescottjr@gmail.com | 843-504-4542"""

# ── Discipline-specific intros ──
DISCIPLINES = {
    "sociology_religion": {
        "label": "Sociology of Religion",
        "intro": "As a sociologist of religion, you know the US Religion Census and Pew Landscape Study are the gold standards — but they're surveys, not infrastructure. GRID maps every actual worship site: 3.5M churches, mosques, synagogues, and temples worldwide, with 200+ denominations classified. Imagine studying religious diversity not through survey samples but through the physical footprint of every congregation.",
        "map_desc": "Map: Christian denominational diversity across the United States — each dot is a church, color-coded by tradition (Catholic, Baptist, Methodist, Lutheran, Pentecostal, LDS, Orthodox, etc.)",
    },
    "political_science": {
        "label": "Political Science",
        "intro": "Religious affiliation is one of the strongest predictors of voting behavior — but most political scientists rely on survey data. GRID maps 1M+ US worship sites with their exact location, denomination, and congressional district. Every church is also a polling place, a community organizing hub, and a GOTV target. The dataset includes election district mappings for US, Canada, UK, Brazil, and India.",
        "map_desc": "Map: US churches color-coded by denomination overlaid with 2020 presidential election results by county — revealing the spatial correlation between religious tradition and voting patterns.",
    },
    "geography": {
        "label": "Geography & GIS",
        "intro": "GRID is the largest geocoded religious infrastructure dataset ever assembled: 3.5M points across 200+ countries, each with GPS coordinates, address, faith tradition, and denominational hierarchy. Perfect for spatial analysis of religious landscapes, accessibility studies, and urban/rural religious geography. Ready for QGIS, ArcGIS, or any spatial analysis pipeline.",
        "map_desc": "Map: Global density of worship sites — 3.5M points showing the geographic distribution of religious infrastructure across 200+ countries.",
    },
    "public_health": {
        "label": "Public Health",
        "intro": "Faith-based organizations are critical partners in health interventions — from vaccine clinics to mental health programs. GRID maps every church, mosque, and temple with county-level health demographics, enabling precise targeting of faith-based health outreach. Includes RUCC rural/urban codes and ACS demographic data appended to each site.",
        "map_desc": "Map: US worship sites overlaid with county-level health indicators — showing where faith communities and health needs intersect.",
    },
    "economics": {
        "label": "Economics of Religion",
        "intro": "GRID includes 209,000 SBA PPP loans matched to churches — revealing the financial behavior of religious organizations during COVID. Combined with 2010 & 2020 ARDA county-denomination adherent counts (300+ denominations), this dataset enables rigorous economic analysis of religious markets, charitable giving patterns, and institutional resilience.",
        "map_desc": "Map: SBA PPP loan distribution across US churches — showing where religious organizations accessed federal relief, color-coded by loan amount.",
    },
    "urban_planning": {
        "label": "Urban Planning",
        "intro": "Churches are among the largest landholders in many cities — and they're increasingly redeveloping into housing, community centers, or closing entirely. GRID includes property assessment data (Boston pilot: 924 churches with valuations), zoning context, and building age. Understand the religious land use landscape at scale.",
        "map_desc": "Map: Religious property footprint in major US metros — showing church density, property values, and land use patterns.",
    },
    "history_religion": {
        "label": "History & Religious Studies",
        "intro": "GRID isn't just contemporary — it includes historical sites from Pleiades (1,702 ancient temples, sanctuaries, and shrines from the Roman, Hellenistic, Egyptian, and Mesopotamian worlds), plus National Historic Landmark churches. For historians of American religion, denominational hierarchies trace institutional evolution across centuries.",
        "map_desc": "Map: Ancient religious sites from the Pleiades gazetteer integrated with GRID — Roman temples, Greek sanctuaries, Egyptian pyramids, Mesopotamian ziggurats.",
    },
    "data_science": {
        "label": "Data Science & Computational Social Science",
        "intro": "GRID is a dream dataset for computational social science: 3.5M classified entities across 85+ faith traditions, with rich metadata (contacts, hierarchies, census mappings, financial data). Perfect for network analysis of denominational structures, NLP on church names, spatial ML, or training models on religious infrastructure prediction.",
        "map_desc": "Map: Faith tradition classification tree — 85+ categories across 8 civilizational families, showing the taxonomic depth of GRID's classification system.",
    },
}

# ── Academic contacts by discipline ──
CONTACTS = [
    # Sociology of Religion
    {"discipline": "sociology_religion", "univ": "University of Notre Dame", "dept": "Sociology", "name": "Center for the Study of Religion and Society", "email": "csrs@nd.edu"},
    {"discipline": "sociology_religion", "univ": "Baylor University", "dept": "Institute for Studies of Religion", "email": "isr@baylor.edu"},
    {"discipline": "sociology_religion", "univ": "Duke University", "dept": "Divinity School", "email": "divinity@duke.edu"},
    {"discipline": "sociology_religion", "univ": "Princeton University", "dept": "Center for the Study of Religion", "email": "csr@princeton.edu"},
    {"discipline": "sociology_religion", "univ": "Indiana University-Purdue University Indianapolis", "dept": "Center for the Study of Religion and American Culture", "email": "raac@iupui.edu"},
    {"discipline": "sociology_religion", "univ": "Pew Research Center", "dept": "Religion Research", "email": "info@pewresearch.org"},
    {"discipline": "sociology_religion", "univ": "Hartford Institute for Religion Research", "dept": "", "email": "hirr@hartsem.edu"},
    {"discipline": "sociology_religion", "univ": "ARDA — Association of Religion Data Archives", "dept": "Penn State University", "email": "arda@psu.edu"},
    # Political Science
    {"discipline": "political_science", "univ": "Harvard University", "dept": "Department of Government", "email": "government@fas.harvard.edu"},
    {"discipline": "political_science", "univ": "University of Michigan", "dept": "Center for Political Studies", "email": "cps@isr.umich.edu"},
    {"discipline": "political_science", "univ": "Stanford University", "dept": "Political Science", "email": "politicalscience@stanford.edu"},
    {"discipline": "political_science", "univ": "MIT", "dept": "Political Science", "email": "polisci-info@mit.edu"},
    {"discipline": "political_science", "univ": "UC Berkeley", "dept": "Institute of Governmental Studies", "email": "igs@berkeley.edu"},
    # Geography & GIS
    {"discipline": "geography", "univ": "Penn State University", "dept": "Department of Geography", "email": "geography@psu.edu"},
    {"discipline": "geography", "univ": "UC Santa Barbara", "dept": "Department of Geography", "email": "geog-web@geog.ucsb.edu"},
    {"discipline": "geography", "univ": "University of Wisconsin-Madison", "dept": "Department of Geography", "email": "geography@wisc.edu"},
    {"discipline": "geography", "univ": "University of Chicago", "dept": "Center for Spatial Data Science", "email": "spatial@uchicago.edu"},
    {"discipline": "geography", "univ": "Arizona State University", "dept": "School of Geographical Sciences", "email": "geography@asu.edu"},
    # Public Health
    {"discipline": "public_health", "univ": "Johns Hopkins University", "dept": "Bloomberg School of Public Health", "email": "bsph.admissions@jhu.edu"},
    {"discipline": "public_health", "univ": "Harvard University", "dept": "T.H. Chan School of Public Health", "email": "admissions@hsph.harvard.edu"},
    {"discipline": "public_health", "univ": "Emory University", "dept": "Rollins School of Public Health", "email": "sphadmissions@emory.edu"},
    {"discipline": "public_health", "univ": "Columbia University", "dept": "Mailman School of Public Health", "email": "msph-admissions@columbia.edu"},
    # Economics
    {"discipline": "economics", "univ": "George Mason University", "dept": "Department of Economics", "email": "economics@gmu.edu"},
    {"discipline": "economics", "univ": "University of Chicago", "dept": "Becker Friedman Institute", "email": "bfi@uchicago.edu"},
    {"discipline": "economics", "univ": "Harvard University", "dept": "Department of Economics", "email": "economics@harvard.edu"},
    {"discipline": "economics", "univ": "NBER", "dept": "Religion and Economics Program", "email": "info@nber.org"},
    # Urban Planning
    {"discipline": "urban_planning", "univ": "MIT", "dept": "Department of Urban Studies and Planning", "email": "duspinfo@mit.edu"},
    {"discipline": "urban_planning", "univ": "UC Berkeley", "dept": "College of Environmental Design", "email": "ced@berkeley.edu"},
    {"discipline": "urban_planning", "univ": "NYU", "dept": "Wagner School of Public Service", "email": "wagner.urban@nyu.edu"},
    {"discipline": "urban_planning", "univ": "University of Pennsylvania", "dept": "Weitzman School of Design", "email": "design@design.upenn.edu"},
    # History & Religious Studies
    {"discipline": "history_religion", "univ": "Yale University", "dept": "Department of Religious Studies", "email": "religious.studies@yale.edu"},
    {"discipline": "history_religion", "univ": "Harvard Divinity School", "dept": "", "email": "hdsinfo@hds.harvard.edu"},
    {"discipline": "history_religion", "univ": "University of Chicago", "dept": "Divinity School", "email": "divinity@uchicago.edu"},
    {"discipline": "history_religion", "univ": "Duke University", "dept": "Department of Religious Studies", "email": "religious.studies@duke.edu"},
    # Data Science
    {"discipline": "data_science", "univ": "Northeastern University", "dept": "Network Science Institute", "email": "networkscience@northeastern.edu"},
    {"discipline": "data_science", "univ": "NYU", "dept": "Center for Data Science", "email": "cds@nyu.edu"},
    {"discipline": "data_science", "univ": "Stanford University", "dept": "Data Science Institute", "email": "datascience@stanford.edu"},
    {"discipline": "data_science", "univ": "University of Michigan", "dept": "Michigan Institute for Data Science", "email": "midas-contact@umich.edu"},
]

# ── Build body ──
def build_body(c):
    disc = DISCIPLINES[c["discipline"]]
    name = c.get("name", c["dept"])
    recipient = name if name else c["dept"]

    return f"""Subject: GRID: 3.5M Worship Sites — Early Access for {disc['label']} Research

Dear {recipient} at {c['univ']},

I'm reaching out because whatever you study in {disc['label']}, you've probably wished for better data on religious infrastructure. I've built it.

{disc['intro']}

WHAT GRID IS:
— 3,537,585 worship sites worldwide (churches, mosques, synagogues, temples, gurdwaras)
— 200+ Christian denominations classified, 17 Muslim traditions, 12 Jewish movements
— Each site has: GPS coordinates, address, phone, website, faith classification, denomination hierarchy
— US sites mapped to census tract, congressional district, county
— 614K US addresses normalized, 463K+ verified contacts
— 209K SBA PPP loans matched to churches for economic analysis
— 1,702 ancient religious sites from the Pleiades gazetteer
— Election district mappings for US, Canada, UK, Brazil, India

{disc['map_desc']}

CURRENT STATUS:
GRID is currently under review by ARDA (Association of Religion Data Archives) and being prepared for academic release. I'm offering early access to researchers who want to explore the dataset before publication.

YOU CAN QUERY IT NOW:
The full dataset (3.5M rows) is already available in BigQuery:
{BQ_LINK}

Run SQL directly against the database — filter by country, faith, denomination, census tract, or any field.

I'd love to discuss how GRID could support your research. Happy to provide custom extracts, answer questions about methodology, or jump on a call.

{SIG}"""

# ── Build queue ──
queue = []
for c in CONTACTS:
    body = build_body(c)
    entry = {
        "to": c["email"],
        "subject": f"GRID: 3.5M Worship Sites — Early Access for {DISCIPLINES[c['discipline']]['label']} Research",
        "body": body,
        "source": "academic",
        "org": f"{c['univ']} - {c['dept']}",
        "discipline": c["discipline"],
        "queued": NOW,
    }
    queue.append(entry)
    disc_label = DISCIPLINES[c["discipline"]]["label"]
    print(f"  ✅ {disc_label[:28]:28s} | {c['univ'][:35]:35s} → {c['email']}")

# ── Write to queue ──
existing = []
if QUEUE_FILE.exists():
    existing = [json.loads(l) for l in QUEUE_FILE.read_text(encoding="utf-8").strip().split("\n") if l.strip()]

existing_emails = {e.get("to", "").lower() for e in existing}
new = [q for q in queue if q["to"].lower() not in existing_emails]
dupes = len(queue) - len(new)

all_entries = existing + new
with open(QUEUE_FILE, "w", encoding="utf-8") as f:
    for item in all_entries:
        f.write(json.dumps(item) + "\n")

print(f"\n{'='*60}")
print(f"ACADEMIC CAMPAIGN")
print(f"{'='*60}")
print(f"  Disciplines: {len(DISCIPLINES)}")
print(f"  Contacts: {len(queue)}")
print(f"  New queued: {len(new)}")
print(f"  Duplicates: {dupes}")
print(f"  Existing queue: {len(existing)}")
print(f"  Total queue: {len(all_entries)}")
print(f"  BigQuery link: {BQ_LINK}")
