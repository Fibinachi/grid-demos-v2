"""
BUILD: Insurance Data Department Pipeline
==========================================
Pitches GRID worship-site data (3.5M+ religious sites) to insurance companies
as property risk, crime, disaster, and emergency-response enrichment data.

Insurance data departments need granular, property-level risk data for:
  - Property & Casualty underwriting (fire risk, flood zones, crime areas)
  - Reinsurance catastrophe modeling (hurricane, earthquake, wildfire exposure)
  - Actuarial pricing (building characteristics, neighborhood demographics)
  - ISO Public Protection Classification (fire station distance → insurance rating)
  - InsurTech platforms (API-delivered risk scores, portfolio analysis)

Targets: P&C insurers, reinsurers, InsurTech, insurance data vendors, MGAs.

Contacts sourced from:
  - NAIC top 25 P&C insurers (publicly available)
  - InsurTech 100 lists
  - Insurance data ecosystem (ISO/Verisk, Zesty.ai, Cape Analytics, etc.)
  - LinkedIn/company research for data/analytics department contacts

Usage:
    python scripts/outreach/build_insurance_pipeline.py
    python scripts/outreach/build_insurance_pipeline.py --preview  # Just preview, don't write
"""

import json, os
from pathlib import Path
from datetime import datetime

OUT = Path("outputs/outreach")
OUT.mkdir(parents=True, exist_ok=True)
QUEUE_FILE = OUT / "unified_queue.jsonl"

NOW = datetime.now().strftime("%B %d, %Y")

# ══════════════════════════════════════════════════════════════════════════
# DATA ASSETS (what we're selling)
# ══════════════════════════════════════════════════════════════════════════

CRIME_DATA = """CRIME RISK DATA (FBI Uniform Crime Reporting):
• County-level violent & property crime rates linked to every US worship site
• Violent crime: murder, rape, robbery, aggravated assault (per 100K population)
• Property crime: burglary, larceny, motor vehicle theft (per 100K population)
• State-level trends 1979-2024 for long-tail risk modeling
• NIBRS agency-level offense data (2024) for hyperlocal granularity
• Perfect for: theft/vandalism risk on insured religious properties, neighborhood crime scoring"""

DISASTER_DATA = """DISASTER & CLIMATE RISK DATA (FEMA National Risk Index):
• 938,000 US worship sites linked to 16 FEMA hazard types at census-tract resolution
• Hurricane risk (HRCN), inland flood (IFLD), coastal flood (CFLD), river flood (RFLD)
• Wildfire (WFIR), tornado (TRND), earthquake (ERQK), hail (HAIL), strong wind (SWND)
• Lightning (LTNG), drought (DRGT), heat wave (HWAV), winter weather (WNTW)
• Landslide/avalanche (AVLN), volcano (VLCN), tsunami (TSUN)
• EAL (Expected Annual Loss) scores — dollarized risk per hazard
• Social Vulnerability Index (SOVI) and Community Resilience (RESL) scores
• Perfect for: catastrophe modeling, portfolio risk aggregation, climate resilience scoring"""

EMERGENCY_DATA = """EMERGENCY RESPONSE DISTANCE:
• Distance to nearest fire station (km) — direct proxy for ISO Public Protection Classification
• Distance to nearest police station (km) — response time proxy for crime/burglary risk
• US-wide coverage from OpenStreetMap (fire + police stations nationwide)
• Perfect for: ISO rating territories, response time modeling, first-responder proximity underwriting"""

BUILDING_DATA = """BUILDING & PROPERTY DATA:
• 934,000 worship sites with building square footage — key input for replacement cost estimation
• 85,000+ census tracts with FEMA building value estimates
• Zillow ZHVI home value index by ZIP code — neighborhood property value trends
• US Census ACS demographics: median income, poverty rate, education, population density
• CDC PLACES health data by tract — chronic disease prevalence, health outcomes
• Perfect for: replacement cost modeling, neighborhood risk scoring, actuarial pricing"""

CONTACT_DATA = """CONTACT & ENRICHMENT:
• 463,000+ phone numbers, emails, websites (verified contact data)
• 209,000+ SBA PPP loan records — financial health indicators
• 614,000 US addresses normalized (IRS + OpenStreetMap)
• GPS coordinates for all 1M+ US sites"""

COVERAGE = """COVERAGE SUMMARY:
• 1,031,854 worship sites in the United States (all 50 states + DC + territories)
• 1M+ with GPS coordinates, 938K linked to FEMA risk, 934K with building sqft
• County-level RUCC codes, ACS demographics, election results appended
• Denomination hierarchy: Catholic dioceses, Lutheran synods, SBC conventions, etc.
• Faith classification: 85+ traditions (Christian denominations, Muslim, Jewish, Hindu, Sikh, Buddhist)"""

# ══════════════════════════════════════════════════════════════════════════
# SIGNATURE
# ══════════════════════════════════════════════════════════════════════════

SIG = """--
Charles Prescott
Creator, GRID — Global Religious Infrastructure Database
JD, LLM (Taxation) | Trinity College, University of Toronto
charlesaprescottjr@gmail.com | 843-504-4542
https://buymeacoffee.com/CharlesPrescott"""

# ══════════════════════════════════════════════════════════════════════════
# INSURANCE CONTACTS
# ══════════════════════════════════════════════════════════════════════════

SUBJECT = "GRID: Property Risk, Crime & Disaster Data for Religious Infrastructure — 1M+ US Sites"

CONTACTS = [
    # ── Tier 1: Top P&C Insurers (Data/Analytics/Innovation Departments) ──
    {"tier": "T1", "sector": "P&C", "org": "State Farm", "dept": "Research & Data Analytics",
     "email": "b2b@statefarm.com",
     "pitch": "Largest P&C insurer in the US — 87M policies, #1 in auto and home. GRID data enriches your property risk models with hyperlocal crime rates, FEMA hazard scores, fire-station proximity, and building characteristics for 1M+ religious properties nationwide. MAGNet analytics internship program shows your commitment to data science — GRID is ready for your models."},

    {"tier": "T1", "sector": "P&C", "org": "Berkshire Hathaway (GEICO/Gen Re/NICO)",
     "email": "geicodata@geico.com",
     "pitch": "Berkshire's insurance empire spans auto, property, and reinsurance. GRID provides granular, geocoded risk data for every US worship site — the kind of alternative data that gives underwriters an edge."},

    {"tier": "T1", "sector": "P&C", "org": "Progressive", "dept": "Data Science",
     "email": "data@progressive.com",
     "pitch": "Progressive's data-driven culture is legendary. GRID adds a new dimension: 1M+ religious properties with crime, disaster, building, and emergency-response data — ready for your models."},

    {"tier": "T1", "sector": "P&C", "org": "Liberty Mutual", "dept": "Solaria Labs (Innovation)",
     "email": "solarialabs@libertymutual.com",
     "pitch": "Liberty Mutual's Solaria Labs drives data innovation — their Enterprise Data & AI team (led by Monica Caldas) embeds AI into underwriting, claims, and customer service. GRID adds a new asset class: 1M+ religious properties with building sqft, FEMA 16-hazard scores, FBI crime rates, and fire-station proximity.",
     "fallback": "https://www.libertymutual.com/about-liberty-mutual/corporate-information/enterprise-strategy-innovation"},

    {"tier": "T1", "sector": "P&C", "org": "Allstate", "dept": "Research & Analytics",
     "email": "data.analytics@allstate.com",
     "pitch": "Allstate's property book spans the US. GRID gives you granular, property-level risk scores (crime, disaster, emergency response) for 1M+ religious sites — orthogonal data your competitors don't have."},

    {"tier": "T1", "sector": "P&C", "org": "USAA", "dept": "Data & Analytics",
     "email": "dataoffice@usaa.com",
     "pitch": "USAA serves military families — many active in faith communities. GRID maps military chapel infrastructure plus 1M+ civilian worship sites with crime, disaster, and emergency-response data."},

    {"tier": "T1", "sector": "P&C", "org": "Travelers", "dept": "Innovation & Data Culture",
     "email": "innovation@travelers.com",
     "pitch": "Travelers' Data Culture program and innovation ecosystem make them a natural fit. GRID's building sqft, FEMA risk scores, and crime rates for 934K+ worship sites are ready to enrich your commercial property underwriting models."},

    {"tier": "T1", "sector": "P&C", "org": "Chubb", "dept": "Data & Analytics",
     "email": "globaldata@chubb.com",
     "pitch": "Chubb insures many high-value religious properties (cathedrals, megachurches, historic sites). GRID provides building characteristics, disaster risk, and crime data for precise risk assessment."},

    {"tier": "T1", "sector": "P&C", "org": "Farmers Insurance", "dept": "Data Science",
     "email": "corporate.communications@farmersinsurance.com",
     "pitch": "Farmers' agent network covers every county. GRID gives your underwriters crime rates, FEMA hazard scores, and fire-station proximity for every church in their territory. Please forward to your Data & Analytics leadership."},

    {"tier": "T1", "sector": "P&C", "org": "Nationwide", "dept": "Data & Analytics",
     "email": "datascience@nationwide.com",
     "pitch": "Nationwide's Church & Ministry insurance program is a natural fit. GRID enriches every religious property with risk data your competitors can't access."},

    # ── Tier 2: Reinsurers & Catastrophe Modelers ──
    {"tier": "T2", "sector": "Reinsurance", "org": "Swiss Re", "dept": "Tech & Innovation Partnerships",
     "email": "innovation@swissre.com",
     "pitch": "Swiss Re actively seeks partners leveraging real-time data for risk prediction (swissre.com/about-us/tech-innovation). GRID maps 938K US worship sites with 16 FEMA hazard types at tract resolution — a unique exposure dataset for religious infrastructure cat modeling."},

    {"tier": "T2", "sector": "Reinsurance", "org": "Munich Re", "dept": "Data & Analytics",
     "email": "innovation@munichre.com",
     "pitch": "Munich Re's risk intelligence platform would benefit from GRID's proprietary dataset: 1M+ religious properties with building sqft, FEMA multi-hazard scores, and emergency-response proximity."},

    {"tier": "T2", "sector": "Reinsurance", "org": "Aon (Reinsurance Solutions)", "dept": "Impact Forecasting",
     "email": "data.analytics@aon.com",
     "pitch": "Aon's Impact Forecasting team models catastrophe risk globally. GRID provides granular US exposure data for religious infrastructure — 938K sites with 16 FEMA hazard types."},

    {"tier": "T2", "sector": "Reinsurance", "org": "Guy Carpenter (Marsh McLennan)",
     "email": "guy.carpenter@marsh.com",
     "pitch": "Guy Carpenter's brokerage and analytics platform can differentiate with GRID data: 1M+ US worship sites with property characteristics, crime risk, and disaster exposure."},

    {"tier": "T2", "sector": "Reinsurance", "org": "Gallagher Re", "dept": "Gallagher Research Centre",
     "email": "GRC@ajg.com",
     "pitch": "Gallagher Research Centre connects academic research with (re)insurance needs — and Gallagher has a dedicated Religious practice group. GRID is a perfect fit: 1M+ US worship sites with FEMA risk, FBI crime, and building data. Plus: Gallagher Blueprint analytics integration potential."},

    {"tier": "T2", "sector": "Reinsurance", "org": "RenaissanceRe", "dept": "Data & Analytics",
     "email": "investorrelations@renre.com",
     "pitch": "RenRe's property cat focus makes GRID's granular exposure data invaluable — 938K worship sites with FEMA multi-hazard scores and building characteristics for portfolio risk aggregation."},

    # ── Tier 3: Insurance Data Vendors & Platforms ──
    {"tier": "T3", "sector": "Data Vendor", "org": "Verisk Analytics (ISO)", "dept": "Data Partnerships",
     "email": "datapartnerships@verisk.com",
     "pitch": "Verisk's ISO unit sets the standard for property risk data. GRID is a unique, orthogonal dataset — 1M+ worship sites with crime, FEMA hazard, building sqft, and fire-station proximity — that would strengthen your commercial property analytics."},

    {"tier": "T3", "sector": "Data Vendor", "org": "CoreLogic", "dept": "Data Partnerships",
     "email": "datapartner@corelogic.com",
     "pitch": "CoreLogic's property data is the gold standard. GRID adds religious infrastructure mapping with multi-hazard risk scores, crime rates, and emergency-response data — complementary data for your insurance clients."},

    {"tier": "T3", "sector": "Data Vendor", "org": "LexisNexis Risk Solutions", "dept": "Insurance",
     "email": "insurance.data@lexisnexisrisk.com",
     "pitch": "LexisNexis Risk Solutions powers insurance underwriting across the industry. GRID is a new alternative data source — 1M+ religious properties with crime, disaster, and building risk attributes."},

    {"tier": "T3", "sector": "Data Vendor", "org": "ISO (Insurance Services Office)", "dept": "Data",
     "email": "isodata@verisk.com",
     "pitch": "ISO's PPC (Public Protection Classification) rates fire protection. GRID maps fire-station distance for every US worship site — ground-truth validation for your PPC data plus FEMA multi-hazard enrichment."},

    {"tier": "T3", "sector": "Data Vendor", "org": "Zesty.ai", "dept": "Data Partnerships",
     "email": "partnerships@zesty.ai",
     "pitch": "Zesty.ai uses AI for property risk assessment. GRID adds a new vertical — 1M+ religious properties — with building sqft, FEMA hazard scores, and neighborhood crime data for your models."},

    {"tier": "T3", "sector": "Data Vendor", "org": "Cape Analytics", "dept": "Partnerships",
     "email": "partners@capeanalytics.com",
     "pitch": "Cape Analytics does computer vision for property intelligence. GRID maps every church, mosque, synagogue, and temple in America with building characteristics and risk scores — training data for your models."},

    {"tier": "T3", "sector": "Data Vendor", "org": "Arturo (AI Property Intelligence)",
     "email": "partnerships@arturo.ai",
     "pitch": "Arturo's AI property analytics plus GRID's religious infrastructure mapping = powerful combination. 934K worship sites with building sqft, FEMA risk, and crime data."},

    # ── Tier 4: InsurTech & Innovation Labs ──
    {"tier": "T4", "sector": "InsurTech", "org": "Lemonade", "dept": "Business Development",
     "email": "partnerships@lemonade.com",
     "pitch": "Lemonade's AI-driven underwriting (Maya Prosor, CBO) would benefit from GRID's alternative data: crime rates, disaster risk scores, and emergency-response proximity for every US worship site — unique signals for your models."},

    {"tier": "T4", "sector": "InsurTech", "org": "Hippo Insurance", "dept": "Data & Analytics",
     "email": "data@hippo.com",
     "pitch": "Hippo's proactive home insurance platform could use GRID data to assess neighborhood risk: crime rates, FEMA hazard scores, and fire-station proximity around every worship site (and by extension, surrounding properties)."},

    {"tier": "T4", "sector": "InsurTech", "org": "Root Insurance", "dept": "Data Science",
     "email": "data@rootinsurance.com",
     "pitch": "Root's data science approach to insurance is a perfect fit for GRID's alternative data: 1M+ geocoded worship sites with crime, disaster, and building characteristics — unique variables for risk modeling."},

    {"tier": "T4", "sector": "InsurTech", "org": "Kin Insurance", "dept": "Data & Analytics",
     "email": "partnerships@kin.com",
     "pitch": "Kin's focus on climate-resilient home insurance aligns perfectly with GRID's FEMA multi-hazard data: 938K worship sites scored for hurricane, flood, wildfire, tornado, and 12 other hazard types."},

    {"tier": "T4", "sector": "InsurTech", "org": "Slide Insurance", "dept": "Data & Analytics",
     "email": "data@slideinsurance.com",
     "pitch": "Slide's Florida-focused property insurance needs granular hurricane and flood risk data. GRID maps every FL worship site with FEMA hazard scores and building characteristics."},

    # ── Tier 5: Specialty Religious Insurers & MGAs ──
    {"tier": "T5", "sector": "Specialty", "org": "Church Mutual Insurance Company",
     "email": "innovation@churchmutual.com",
     "pitch": "Church Mutual is the #1 insurer of religious institutions. GRID maps your entire addressable market — 1M+ US worship sites with building sqft, FEMA risk scores, crime rates, and denominational data."},

    {"tier": "T5", "sector": "Specialty", "org": "GuideOne Insurance", "dept": "Data & Analytics",
     "email": "datascience@guideone.com",
     "pitch": "GuideOne specializes in religious organization insurance. GRID provides the most comprehensive map of your market ever assembled — 934K+ worship sites with building and risk data."},

    {"tier": "T5", "sector": "Specialty", "org": "Brotherhood Mutual Insurance Company",
     "email": "analytics@brotherhoodmutual.com",
     "pitch": "Brotherhood Mutual insures thousands of churches and ministries. GRID gives you market intelligence on every religious property in America — FEMA risk, crime rates, building sqft, and more."},

    {"tier": "T5", "sector": "Specialty", "org": "Philadelphia Insurance (PHLY)", "dept": "Data & Analytics",
     "email": "data@phly.com",
     "pitch": "PHLY's niche includes religious organizations. GRID maps every one with crime risk, disaster exposure, building characteristics, and emergency-response data for smarter underwriting."},

    {"tier": "T5", "sector": "Specialty", "org": "Glatfelter Insurance Group (Religious Practice)",
     "email": "info@glatfelter.com",
     "pitch": "Glatfelter's Religious Practice program insures faith-based organizations. GRID provides a complete map of US religious infrastructure with risk data to power your underwriting and marketing."},

    # ── Tier 6: Consulting & Advisory ──
    {"tier": "T6", "sector": "Consulting", "org": "McKinsey (Insurance Practice)", "dept": "Data & Analytics",
     "email": "insurance_data@mckinsey.com",
     "pitch": "McKinsey's insurance practice advises the world's largest carriers. GRID is a unique alternative dataset — 1M+ worship sites with multi-peril risk scores — that your clients would value for portfolio analysis."},

    {"tier": "T6", "sector": "Consulting", "org": "Deloitte (Insurance Data & Analytics)",
     "email": "insurancedata@deloitte.com",
     "pitch": "Deloitte's insurance analytics team can leverage GRID as a differentiated data source for client engagements — 1M+ religious properties with crime, disaster, and building risk attributes."},

    {"tier": "T6", "sector": "Consulting", "org": "Milliman", "dept": "Data & Analytics",
     "email": "data.solutions@milliman.com",
     "pitch": "Milliman's actuarial expertise combined with GRID's granular risk data (FEMA 16-hazard, FBI crime, fire-station proximity) creates powerful portfolio analysis for your insurance clients."},
]

# ══════════════════════════════════════════════════════════════════════════
# PITCH BUILDER
# ══════════════════════════════════════════════════════════════════════════

def build_body(c):
    """Build personalized email body for an insurance contact."""

    dept_str = f" ({c.get('dept', '')})" if c.get('dept') else ""

    tier_section = {
        "T1": "As one of the largest P&C carriers, your underwriting models would benefit from this unique, orthogonal dataset.",
        "T2": "Your catastrophe and portfolio risk models need granular exposure data — GRID provides it for an entire asset class.",
        "T3": "Your data platform powers insurance decisions across the industry. GRID is a new, unique dataset your clients don't have.",
        "T4": "Your technology-first approach to insurance is a perfect fit for GRID's geocoded, API-ready risk data.",
        "T5": "As a specialist in religious organization insurance, GRID maps your entire addressable US market with risk data.",
        "T6": "Your advisory work for insurance clients can leverage GRID as a proprietary, differentiated data source.",
    }

    return f"""Subject: {SUBJECT}

Dear {c['org']}{dept_str} Team,

I've built GRID — the Global Religious Infrastructure Database — and I believe it can strengthen your risk assessment and underwriting capabilities.

{COVERAGE}

WHY THIS MATTERS FOR INSURANCE:
Religious properties represent a massive, under-modeled asset class. GRID provides granular, property-level risk data that traditional insurance data sources don't capture:

{CRIME_DATA}

{DISASTER_DATA}

{EMERGENCY_DATA}

{BUILDING_DATA}

{CONTACT_DATA}

{'-'*50}
WHY {c['org'].upper()}:
{c['pitch']}

{tier_section.get(c['tier'], '')}

I'd love to discuss how GRID data could integrate with your risk models — whether as a bulk data license, API access, or a custom partnership. Happy to send sample data for your analysts to evaluate, or schedule a call at your convenience.

{SIG}"""

# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    preview_only = "--preview" in sys.argv

    print("=" * 70)
    print("INSURANCE DATA DEPARTMENT OUTREACH PIPELINE")
    print("=" * 70)
    print(f"  Target: {len(CONTACTS)} insurance companies")
    print(f"  Sectors: P&C, Reinsurance, Data Vendors, InsurTech, Specialty, Consulting")
    print()

    # Build queue entries
    queue = []
    sector_counts = {}
    tier_counts = {}

    for c in CONTACTS:
        body = build_body(c)
        entry = {
            "to": c["email"],
            "subject": SUBJECT,
            "body": body,
            "source": "insurance",
            "org": c["org"],
            "sector": c["sector"],
            "tier": c["tier"],
            "dept": c.get("dept", ""),
            "queued": NOW,
        }
        queue.append(entry)

        sector_counts[c["sector"]] = sector_counts.get(c["sector"], 0) + 1
        tier_counts[c["tier"]] = tier_counts.get(c["tier"], 0) + 1

        print(f"  ✅ {c['tier']} | {c['sector']:15s} | {c['org'][:40]:40s} → {c['email']}")

    if preview_only:
        print(f"\n{'='*70}")
        print("PREVIEW ONLY — not writing to queue. Remove --preview to commit.")
        print(f"{'='*70}")
        print(f"\n  Sector breakdown:")
        for s, n in sorted(sector_counts.items()):
            print(f"    {s:20s}: {n}")
        print(f"\n  Tier breakdown:")
        for t, n in sorted(tier_counts.items()):
            print(f"    {t:5s}: {n}")
        print(f"\n  Total: {len(queue)} contacts")
        sys.exit(0)

    # Read existing queue
    existing = []
    if QUEUE_FILE.exists():
        existing = [json.loads(l) for l in QUEUE_FILE.read_text(encoding="utf-8").strip().split("\n") if l.strip()]

    # Dedup by email
    existing_emails = {e.get("to", "").lower() for e in existing}
    new_entries = [q for q in queue if q["to"].lower() not in existing_emails]
    dupes = [q for q in queue if q["to"].lower() in existing_emails]

    # Append new entries
    all_entries = existing + new_entries
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        for item in all_entries:
            f.write(json.dumps(item) + "\n")

    print(f"\n{'='*70}")
    print("QUEUE SUMMARY")
    print(f"{'='*70}")
    print(f"  Existing entries: {len(existing)}")
    print(f"  New insurance:    {len(new_entries)}")
    print(f"  Duplicates:       {len(dupes)}")
    print(f"  Total queue:      {len(all_entries)}")
    print(f"  Est. send time:   {len(all_entries)*3/60:.1f} hours at 1/3min")
    print(f"\n  Sector breakdown:")
    for s, n in sorted(sector_counts.items()):
        print(f"    {s:20s}: {n}")
    print(f"\n  Tier breakdown:")
    for t, n in sorted(tier_counts.items()):
        print(f"    {t:5s}: {n}")
    print(f"\n  Queue file: {QUEUE_FILE}")
