"""
GRID SALES CAMPAIGN CONFIGURATION
==================================
Pricing tiers, product definitions, campaign templates, and buyer personas.
This is the single source of truth for all sales campaign logic.

Author: Charles Prescott — GRID (Global Religious Infrastructure Database)
Last updated: 2026-07-08
"""

from datetime import datetime
from typing import Dict, List, Optional
import json
from pathlib import Path

OUT = Path("outputs/outreach")
OUT.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════
# 1. PRODUCT TIERS & PRICING
# ══════════════════════════════════════════════════════════════════════════

PRODUCTS = {
    "community_report": {
        "name": "Community Intelligence Report",
        "price_usd": 250,
        "type": "one-time",
        "description": "Custom demographic & community analysis for a single worship site",
        "deliverables": [
            "3/5/10-mile radius demographic breakdown",
            "Competitive landscape (other houses of worship nearby)",
            "Community needs assessment",
            "Custom maps & visualizations (PDF + HTML)",
            "15-minute consultation call"
        ],
        "turnaround": "3-5 business days",
        "buy_link": "https://buymeacoffee.com/CharlesPrescott",
        "target_personas": ["church_admin", "pastor"],
        "email_list_price": None  # Not sold as list
    },

    "researcher_basic": {
        "name": "GRID Researcher Access",
        "price_usd": 500,
        "type": "annual",
        "description": "Full US dataset for academic & nonprofit research",
        "deliverables": [
            "Full US dataset (~1M records) in CSV format",
            "Annual data refresh",
            "Non-commercial use license",
            "Basic documentation & data dictionary",
            "Email support"
        ],
        "turnaround": "Same-day download after payment",
        "buy_link": "https://buymeacoffee.com/CharlesPrescott",
        "target_personas": ["academic", "researcher", "nonprofit"],
        "email_list_price": None
    },

    "professional": {
        "name": "GRID Professional Access",
        "price_usd": 2500,
        "type": "annual",
        "description": "Full global dataset with API access for commercial use",
        "deliverables": [
            "Full global dataset (~3.5M records) in CSV format",
            "REST API access (10M calls/month)",
            "Quarterly data refreshes",
            "Commercial use license (single organization)",
            "API documentation & SDK examples",
            "Priority email support"
        ],
        "turnaround": "Same-day setup after payment",
        "buy_link": "https://buymeacoffee.com/CharlesPrescott",
        "target_personas": ["startup", "consultant", "data_analyst", "nonprofit"],
        "email_list_price": None
    },

    "enterprise": {
        "name": "GRID Enterprise Access",
        "price_usd": 10000,
        "type": "annual",
        "description": "Unlimited access with white-label rights for large organizations",
        "deliverables": [
            "Everything in Professional",
            "Unlimited API calls",
            "Monthly data refreshes",
            "White-label / resale rights",
            "Custom data cuts & exports",
            "Dedicated account manager",
            "SLA with 99.5% uptime guarantee",
            "Phone + email support"
        ],
        "turnaround": "1-2 business days setup",
        "buy_link": "https://buymeacoffee.com/CharlesPrescott",
        "target_personas": ["data_broker", "mapping_company", "enterprise", "insurance"],
        "email_list_price": None
    },

    "data_license": {
        "name": "GRID Custom Data License",
        "price_usd": "Custom (typically $5K-$50K/year)",
        "type": "custom",
        "description": "Bulk data licensing for resale, integration, or redistribution",
        "deliverables": [
            "Full dataset in your preferred format",
            "Custom refresh schedule (weekly to annual)",
            "Tailored data cuts (by country, faith, denomination)",
            "Integration support",
            "Revenue-share or flat-fee options available"
        ],
        "turnaround": "Scoped per agreement",
        "buy_link": None,  # Requires direct negotiation
        "target_personas": ["data_broker", "mapping_company", "enterprise"],
        "email_list_price": None
    },

    "church_mailing_list": {
        "name": "US Church Mailing List",
        "price_usd": 0.05,  # per record
        "type": "one-time",
        "description": "Targeted mailing list of US worship sites for direct marketing",
        "deliverables": [
            "Filterable by denomination, geography, building size, risk scores",
            "CSV export with addresses, phones, emails where available",
            "100-record free sample for qualified buyers",
            "Minimum order: 1,000 records ($50)"
        ],
        "turnaround": "Same-day download",
        "buy_link": "https://buymeacoffee.com/CharlesPrescott",
        "target_personas": ["marketer", "roofing", "hvac", "insurance_agent"],
        "email_list_price": 0.05  # per-record pricing
    }
}

# ══════════════════════════════════════════════════════════════════════════
# 2. BUYER PERSONAS
# ══════════════════════════════════════════════════════════════════════════

PERSONAS = {
    "data_broker": {
        "name": "Data Broker / Reseller",
        "primary_product": "data_license",
        "secondary_products": ["enterprise", "church_mailing_list"],
        "pain_points": [
            "Church lists are generic — no denomination taxonomy",
            "Can't differentiate from InfoUSA/Data Axle",
            "Missing building data and risk scores",
            "No refresh schedule for church data"
        ],
        "value_props": [
            "200+ denomination classifications (nobody else has this)",
            "934K buildings with square footage",
            "FEMA disaster risk + FBI crime scores per location",
            "Quarterly refresh keeps data current"
        ],
        "subject_templates": [
            "GRID: {count} US Churches — Wholesale Data for Resale",
            "Differentiate your church data with GRID's taxonomy",
            "Partnership: GRID worship site data for {company}"
        ]
    },
    "mapping_company": {
        "name": "Mapping / GIS Company",
        "primary_product": "data_license",
        "secondary_products": ["enterprise"],
        "pain_points": [
            "Missing religious POI coverage in international markets",
            "No faith/tradition classification for POIs",
            "GPS accuracy issues with existing religious POI data"
        ],
        "value_props": [
            "3.5M worship sites across 240+ countries",
            "GPS-verified locations (not ZIP centroids)",
            "Faith, tradition, and landmark type for every record"
        ],
        "subject_templates": [
            "GRID: 3.5M Religious POIs for {company} Maps",
            "Fill your religious POI gaps with GRID — 240 countries"
        ]
    },
    "academic": {
        "name": "Academic Researcher",
        "primary_product": "researcher_basic",
        "secondary_products": ["professional"],
        "pain_points": [
            "No comprehensive cross-faith dataset exists",
            "ARDA data is county-level only, not point-level",
            "Hard to study religious infrastructure at scale"
        ],
        "value_props": [
            "3.5M point-level records across all major faiths",
            "Census-tract and electoral district enrichment built in",
            "Cited in academic research — peer-review ready"
        ],
        "subject_templates": [
            "GRID: Point-Level Global Religious Data for Research",
            "Research dataset: 3.5M worship sites, 240 countries"
        ]
    },
    "church_admin": {
        "name": "Church Administrator / Pastor",
        "primary_product": "community_report",
        "secondary_products": [],
        "pain_points": [
            "Don't know their community demographics",
            "Need data for grant applications",
            "Want to understand their competitive landscape",
            "Planning outreach or expansion"
        ],
        "value_props": [
            "Data-driven community insights for $250",
            "Professional maps and reports for grant applications",
            "Understand who you're serving (and not serving)"
        ],
        "subject_templates": [
            "Community Intelligence Report for {church_name} — $250",
            "Understand your community: GRID Report for {church_name}"
        ]
    },
    "insurance": {
        "name": "Insurance Company / Agent",
        "primary_product": "professional",
        "secondary_products": ["enterprise", "church_mailing_list"],
        "pain_points": [
            "Need to assess risk for church properties",
            "Churches are a distinct insurance vertical",
            "Building sqft and location data is scattered"
        ],
        "value_props": [
            "934K buildings with square footage",
            "FEMA disaster risk scores (16 hazard types)",
            "FBI crime risk scores by location",
            "Distance to nearest fire/police station for every US church"
        ],
        "subject_templates": [
            "GRID: Risk-Scored Church Property Database for Insurance",
            "1M US churches with disaster + crime risk scores"
        ]
    },
    "nonprofit": {
        "name": "Nonprofit / Foundation",
        "primary_product": "researcher_basic",
        "secondary_products": ["professional"],
        "pain_points": [
            "Need data for grant-making decisions",
            "Want to identify underserved communities",
            "Track religious infrastructure for program planning"
        ],
        "value_props": [
            "Identify faith deserts and underserved areas",
            "Cross-reference with census demographics",
            "300+ denominational families classified"
        ],
        "subject_templates": [
            "GRID: Religious Infrastructure Data for Grant-Making",
            "Map faith communities for better program targeting"
        ]
    },
    "marketer": {
        "name": "Direct Marketer / Agency",
        "primary_product": "church_mailing_list",
        "secondary_products": ["professional"],
        "pain_points": [
            "Generic church lists don't let you target by denomination",
            "Need to reach specific faith communities",
            "Church data gets stale quickly"
        ],
        "value_props": [
            "Target by specific denomination (ELCA vs LCMS vs SBC)",
            "Filter by building size, location, risk profile",
            "Updated regularly — not a recycled 2010 list"
        ],
        "subject_templates": [
            "Target churches by denomination — GRID Mailing Lists",
            "Precision church marketing: 200+ denominations"
        ]
    },
    "roofing": {
        "name": "Roofing / Construction / HVAC",
        "primary_product": "church_mailing_list",
        "secondary_products": [],
        "pain_points": [
            "Churches are great customers (large buildings, steady budgets)",
            "Hard to find ALL churches in a territory",
            "No building size data to qualify leads"
        ],
        "value_props": [
            "934K churches with building square footage",
            "Filter by building size to find your ideal prospects",
            "GPS coordinates for territory planning"
        ],
        "subject_templates": [
            "Find every church in your territory — GRID Building Data",
            "Churches by square footage: qualify your leads instantly"
        ]
    }
}

# ══════════════════════════════════════════════════════════════════════════
# 3. CAMPAIGN SEQUENCES
# ══════════════════════════════════════════════════════════════════════════

# Multi-touch campaign sequences per persona
CAMPAIGN_SEQUENCES = {
    "data_broker": {
        "name": "Data Broker 4-Touch Sequence",
        "touches": [
            {
                "day": 0,
                "type": "cold_email",
                "template": "broker_touch1",
                "goal": "Introduction + value proposition"
            },
            {
                "day": 5,
                "type": "follow_up",
                "template": "broker_touch2",
                "goal": "Sample offer + social proof"
            },
            {
                "day": 12,
                "type": "linkedin_or_web_form",
                "template": None,
                "goal": "Multi-channel touch — connect on LinkedIn or submit web form"
            },
            {
                "day": 21,
                "type": "breakup",
                "template": "broker_touch3",
                "goal": "Last attempt — free sample + calendar link"
            }
        ]
    },
    "mapping_company": {
        "name": "Mapping Company 3-Touch Sequence",
        "touches": [
            {"day": 0, "type": "cold_email", "template": "mapping_touch1", "goal": "POI gap analysis"},
            {"day": 7, "type": "follow_up", "template": "mapping_touch2", "goal": "Country-specific sample"},
            {"day": 18, "type": "breakup", "template": "mapping_touch3", "goal": "Final offer + data spec sheet"}
        ]
    },
    "academic": {
        "name": "Academic 2-Touch Sequence",
        "touches": [
            {"day": 0, "type": "cold_email", "template": "academic_touch1", "goal": "Research collaboration pitch"},
            {"day": 14, "type": "follow_up", "template": "academic_touch2", "goal": "Sample dataset + pricing"}
        ]
    },
    "church_admin": {
        "name": "Church Admin 3-Touch Sequence",
        "touches": [
            {"day": 0, "type": "cold_email", "template": "church_touch1", "goal": "Community report offer"},
            {"day": 10, "type": "follow_up", "template": "church_touch2", "goal": "Neighborhood-specific teaser"},
            {"day": 24, "type": "breakup", "template": "church_touch3", "goal": "Last chance + discount"}
        ]
    },
    "insurance": {
        "name": "Insurance 3-Touch Sequence",
        "touches": [
            {"day": 0, "type": "cold_email", "template": "insurance_touch1", "goal": "Risk-scored church database"},
            {"day": 7, "type": "follow_up", "template": "insurance_touch2", "goal": "FEMA risk map attachment"},
            {"day": 16, "type": "breakup", "template": "insurance_touch3", "goal": "Sample risk report for their territory"}
        ]
    },
    "nonprofit": {
        "name": "Nonprofit 2-Touch Sequence",
        "touches": [
            {"day": 0, "type": "cold_email", "template": "nonprofit_touch1", "goal": "Grant-making data pitch"},
            {"day": 14, "type": "follow_up", "template": "nonprofit_touch2", "goal": "Faith desert analysis sample"}
        ]
    }
}

# ══════════════════════════════════════════════════════════════════════════
# 4. EMAIL TEMPLATES
# ══════════════════════════════════════════════════════════════════════════

SIGNATURE = """--
Charles Prescott
Creator, GRID — Global Religious Infrastructure Database
JD, LLM (Taxation) | Trinity College, University of Toronto
charlesaprescottjr@gmail.com | 843-504-4542
https://buymeacoffee.com/CharlesPrescott"""

GRID_STATS_SHORT = """GRID by the numbers:
  • 3.5M worship sites across 240+ countries
  • 7 major faiths fully classified (200+ Christian denominations)
  • 1M+ US churches with GPS coordinates, not ZIP centroids
  • 934K buildings with square footage
  • FEMA disaster risk + FBI crime scores for US locations
  • Electoral district, census tract, and ADM1 enrichment built in"""

GRID_STATS_FULL = """GRID (Global Religious Infrastructure Database):
  • 3,537,585 worship sites across 240+ countries
  • 1,074,302 US churches (all 50 states + DC + territories)
  • 200+ Christian denominational families classified
  • 17 distinct Muslim traditions (Sunni, Shia, Twelver, Ismaili, etc.)
  • 12 Jewish movements (Orthodox, Chabad, Reform, Conservative, etc.)
  • Hindu, Buddhist, Sikh, Jain, Baháʼí, Shinto, Taoist — all classified
  • 1,000,000+ US records with full mailing addresses
  • 934,000 with building square footage
  • 398,000 with website URLs
  • 48,000 with phone numbers
  • 17,000 with email addresses
  • GPS coordinates for all records (not ZIP centroids)
  • FEMA disaster risk scores (16 hazard types) for 938K US churches
  • FBI crime risk scores for 697K US churches
  • Distance to nearest fire/police station for 940K US churches"""

EMAIL_TEMPLATES = {
    # ── DATA BROKER TOUCHES ──
    "broker_touch1": {
        "subject": "GRID: 1M US Churches — Wholesale Data with Taxonomy Nobody Else Has",
        "body": """Hi {dept} at {org},

I've built GRID — the most comprehensive religious institution database in existence — and I'm looking for data partners to bring it to market.

{stats}

WHAT MAKES GRID DIFFERENT FROM YOUR CURRENT CHURCH DATA:
  • 200+ denomination classifications (your current list just says "church")
  • Building square footage for 934K locations
  • FEMA disaster risk + FBI crime scores per building
  • GPS coordinates, not generic ZIP centroids
  • Hierarchy data: what diocese/synod/presbytery does each church belong to?

I'm offering wholesale licensing for resale, with flexible terms — flat-fee or revenue-share.

Free 100-record sample available. Just reply and tell me what slice you'd like to see.

{signature}"""
    },

    "broker_touch2": {
        "subject": "Re: GRID Church Data — Free Sample + What Your Competitors Are Missing",
        "body": """Hi {dept},

Following up — I wanted to share a quick comparison:

YOUR CURRENT CHURCH LIST:
  → "First Baptist Church" — generic tag, no building data, no risk scores

GRID CHURCH LIST:
  → "First Baptist Church" — Southern Baptist Convention, 12,500 sqft, 
    FEMA Flood Zone AE, FBI crime score 320/1000, GPS 34.0522°N,
    part of Birmingham Baptist Association, 3 phone numbers, website URL

The difference is data you can sell at a premium — building contractors, insurance agents, and direct marketers all pay more for qualified, enriched leads.

Want a free 100-record sample to see the difference? Just reply with your preferred state or denomination.

{signature}"""
    },

    "broker_touch3": {
        "subject": "Re: GRID Church Data — Final Offer with Free Sample",
        "body": """Hi {dept},

I know you're busy — just wanted to leave this with you.

GRID church data is available for wholesale licensing starting at $5K/year for full US dataset access with resale rights. Quarterly refreshes included.

No commitment needed — I'd be happy to send you a free 100-record sample so you can evaluate the data quality yourself. Just reply "send sample" and I'll get it to you same day.

If not the right fit, no worries at all.

{signature}"""
    },

    # ── CHURCH ADMIN TOUCHES ──
    "church_touch1": {
        "subject": "Community Intelligence Report for {church_name} — $250",
        "body": """Hi {church_name},

I run GRID, the Global Religious Infrastructure Database — we've mapped over 3.5 million places of worship worldwide. Your church at {address}, {city}, {state} {zip5} is in our database.

I wanted to let you know about our Community Intelligence Report. For $250, you get:

  • Demographic analysis of your 3, 5, and 10-mile radius
  • Competitive landscape — other houses of worship nearby
  • Community needs assessment
  • Custom maps and visualizations (PDF + interactive HTML)
  • 15-minute consultation call to walk through findings

This is the kind of data that helps with:
  • Outreach planning — who are you not reaching?
  • Grant applications — professional data backing your case
  • Strategic planning — where is the community growing?

Ready to order? Visit https://buymeacoffee.com/CharlesPrescott or just reply to this email.

{signature}"""
    },

    "church_touch2": {
        "subject": "Re: {church_name} Community Report — Your Neighborhood Snapshot",
        "body": """Hi {church_name},

Following up — I pulled a quick snapshot of your area around {address}, {city}, {state}.

Within 5 miles of your location, there are approximately {nearby_count} other houses of worship. The closest are:
  {nearby_list}

Your community's demographics, faith landscape, and growth patterns are all in the full Community Intelligence Report. It's $250 and includes a consultation call to walk through everything.

Order at https://buymeacoffee.com/CharlesPrescott or reply with any questions.

{signature}"""
    },

    "church_touch3": {
        "subject": "Re: {church_name} — Last Chance for Community Report ($50 off)",
        "body": """Hi {church_name},

I know you're busy running a church — I'll keep this brief.

I'm offering $50 off the Community Intelligence Report this month — $200 instead of $250. Same deliverables: demographic analysis, competitive landscape, custom maps, and a consultation call.

Use code CHURCH50 at https://buymeacoffee.com/CharlesPrescott

If this isn't the right time, no worries. The offer stands whenever you're ready.

{signature}"""
    },

    # ── ACADEMIC TOUCHES ──
    "academic_touch1": {
        "subject": "GRID: Point-Level Global Religious Data for Research",
        "body": """Hi {dept} at {org},

I'm reaching out because {org}'s research on religion is exactly the kind of work GRID was built to support.

GRID (Global Religious Infrastructure Database) contains 3.5M point-level worship site records across 240+ countries — all faiths, all denominations, with GPS coordinates, addresses, and taxonomy depth that doesn't exist anywhere else.

For researchers, GRID enables:
  • Hyperlocal religious landscape analysis (census-tract level)
  • Cross-faith comparative infrastructure studies
  • Longitudinal tracking of church/mosque/temple openings and closures
  • Denominational market share mapping
  • Electoral district and census tract cross-referencing (built in)

GRID Researcher Access is $500/year for the full US dataset with annual refresh. Global dataset available at the Professional tier ($2,500/year).

Would you be open to a 15-minute call to discuss how GRID could support your research program?

{signature}"""
    },

    "academic_touch2": {
        "subject": "Re: GRID Research Data — Sample Dataset + Pricing",
        "body": """Hi {dept},

Following up on GRID — I'd be happy to send a sample dataset (1,000 records with full taxonomy) so you can evaluate the data quality.

Quick pricing recap:
  • Researcher Access: $500/year — full US dataset (~1M records), CSV, annual refresh
  • Professional Access: $2,500/year — full global (~3.5M records), CSV + API, quarterly refresh
  • Both include non-commercial use license for academic work

Would a sample dataset be helpful? Just reply and I'll send it over.

{signature}"""
    },

    # ── INSURANCE TOUCHES ──
    "insurance_touch1": {
        "subject": "GRID: 1M US Churches with Risk Scores — Insurance Vertical Data",
        "body": """Hi {dept} at {org},

Churches are a massive, underserved insurance vertical — and GRID has the data to help you underwrite them better.

{stats}

EVERY US CHURCH IN GRID INCLUDES:
  • Building square footage (934K records)
  • FEMA disaster risk scores — 16 hazard types (938K records)
  • FBI crime risk scores by location (697K records)
  • Distance to nearest fire station + police station (940K records)
  • GPS coordinates for precise location-based risk assessment
  • Denomination classification (building type, occupancy patterns)

This is data you can use for:
  • Risk scoring and underwriting models
  • Territory planning for agents
  • Identifying high-value church prospects
  • Portfolio risk analysis

Professional access starts at $2,500/year. Enterprise licensing with API integration available.

Would you be interested in seeing a sample risk report for churches in your target territory?

{signature}"""
    },

    "insurance_touch2": {
        "subject": "Re: GRID Church Risk Data — Sample FEMA Risk Map",
        "body": """Hi {dept},

Following up — I've attached a FEMA disaster risk map showing every US church color-coded by composite risk score. 

Key stats from the data:
  • Median fire station distance: 1.80 km
  • Median police station distance: 3.43 km
  • 938K churches scored across 16 FEMA hazard types
  • Building sqft available for premium calculation

Want a sample of churches in your target states? Just reply with the states or ZIP codes you cover and I'll send a CSV sample same day.

{signature}"""
    },

    "insurance_touch3": {
        "subject": "Re: GRID Church Risk Data — Final Offer",
        "body": """Hi {dept},

One last follow-up — if church property insurance is a vertical you're interested in, GRID has the most complete risk-scored church database available anywhere.

$2,500/year for Professional access, or enterprise licensing for team-wide use. Free sample available — just reply with your territory.

No pressure — the data is here whenever you're ready.

{signature}"""
    },

    # ── MAPPING COMPANY TOUCHES ──
    "mapping_touch1": {
        "subject": "GRID: 3.5M Religious POIs — Fill Your Map Gaps",
        "body": """Hi {dept} at {org},

I've built GRID, the most comprehensive global religious POI database — 3.5 million worship sites across 240+ countries, GPS-verified and faith-classified.

For {org}'s maps, GRID fills a critical gap: comprehensive, accurately-classified religious points of interest. Most map providers have spotty religious POI coverage, especially outside the US and Europe.

WHAT GRID ADDS TO YOUR MAPS:
  • 3.5M worship sites — GPS coordinates, not address approximations
  • Faith + tradition + landmark type for every POI
  • 240+ countries with meaningful coverage
  • Building-level precision (not block-level)
  • Regular refreshes keep data current

Available for bulk licensing. I'd love to discuss how GRID could enhance {org}'s POI layer.

{signature}"""
    },

    "mapping_touch2": {
        "subject": "Re: GRID Religious POIs — Country-Specific Coverage",
        "body": """Hi {dept},

Following up — here's a quick snapshot of GRID's country coverage so you can see where we'd fill gaps in your religious POI layer:

  US: 1,074,302 | India: 226,252 | Brazil: 204,773
  Japan: 158,139 | Indonesia: 151,603 | Germany: 105,113
  UK: 100,684 | Canada: 94,620 | France: 92,663
  Italy: 85,808 | Thailand: 66,149 | Saudi Arabia: 60,221
  Mexico: 55,637 | Philippines: 54,831 | Spain: 49,953
  Turkey: 43,635 | Poland: 34,867 | Yemen: 32,667

Happy to provide a sample export for any country or region. Just let me know what would be most useful.

{signature}"""
    },

    "mapping_touch3": {
        "subject": "Re: GRID Religious POIs — Data Spec Sheet + Final Offer",
        "body": """Hi {dept},

Last follow-up — I've attached a data specification sheet with field definitions, coverage stats, and refresh cadence.

GRID data is available for enterprise licensing starting at $10K/year with full integration rights. Bulk one-time licenses also available.

If religious POIs are a priority for your maps team, I'd love to set up a 15-minute call. If not, no worries — the data will be here when it becomes one.

{signature}"""
    },

    # ── NONPROFIT TOUCHES ──
    "nonprofit_touch1": {
        "subject": "GRID: Religious Infrastructure Data for Smarter Grant-Making",
        "body": """Hi {dept} at {org},

I've built GRID — a database of 3.5 million worship sites worldwide — because I believe data should drive better decisions about where resources go.

For {org}, GRID can help answer questions like:
  • Where are the faith deserts — communities with no nearby worship sites?
  • Which underserved areas have growing religious populations?
  • How does religious infrastructure correlate with poverty, education, health outcomes?
  • Where would a new community center or interfaith initiative have the most impact?

GRID Researcher Access is $500/year — full US dataset with annual refresh for nonprofit use. Global dataset available at $2,500/year.

I'd love to discuss how GRID could support your grant-making or program planning.

{signature}"""
    },

    "nonprofit_touch2": {
        "subject": "Re: GRID for Grant-Making — Faith Desert Analysis Sample",
        "body": """Hi {dept},

Following up — I wanted to share a concrete example of how GRID data can drive decisions.

We can identify "faith deserts" — census tracts with above-average religious population but below-average worship site density. These are the communities most in need of religious infrastructure investment.

I'd be happy to generate a faith desert analysis for any county or state you're focused on — no cost, just to show you what the data can do.

{signature}"""
    }
}

# ══════════════════════════════════════════════════════════════════════════
# 5. LEAD SOURCE DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════

LEAD_SOURCES = {
    "data_brokers": {
        "name": "Data Brokers & Mailing List Resellers",
        "priority": 1,
        "avg_deal_size": 15000,
        "close_rate_estimate": 0.05,
        "total_addressable": 30,
        "persona": "data_broker"
    },
    "mapping_companies": {
        "name": "Mapping & GIS Companies",
        "priority": 2,
        "avg_deal_size": 25000,
        "close_rate_estimate": 0.03,
        "total_addressable": 10,
        "persona": "mapping_company"
    },
    "insurance_companies": {
        "name": "Insurance Companies & Agents",
        "priority": 3,
        "avg_deal_size": 3500,
        "close_rate_estimate": 0.08,
        "total_addressable": 200,
        "persona": "insurance"
    },
    "academic_institutions": {
        "name": "Universities & Research Centers",
        "priority": 4,
        "avg_deal_size": 750,
        "close_rate_estimate": 0.10,
        "total_addressable": 500,
        "persona": "academic"
    },
    "foundations_nonprofits": {
        "name": "Foundations & Nonprofits",
        "priority": 5,
        "avg_deal_size": 1500,
        "close_rate_estimate": 0.07,
        "total_addressable": 300,
        "persona": "nonprofit"
    },
    "church_admins": {
        "name": "Church Administrators & Pastors",
        "priority": 6,
        "avg_deal_size": 250,
        "close_rate_estimate": 0.02,
        "total_addressable": 17000,
        "persona": "church_admin"
    },
    "direct_marketers": {
        "name": "Direct Marketers & Agencies",
        "priority": 7,
        "avg_deal_size": 500,
        "close_rate_estimate": 0.06,
        "total_addressable": 1000,
        "persona": "marketer"
    },
    "construction_hvac": {
        "name": "Roofing, Construction & HVAC",
        "priority": 8,
        "avg_deal_size": 200,
        "close_rate_estimate": 0.04,
        "total_addressable": 5000,
        "persona": "roofing"
    }
}

# ══════════════════════════════════════════════════════════════════════════
# 6. PIPELINE STAGES
# ══════════════════════════════════════════════════════════════════════════

PIPELINE_STAGES = [
    "queued",           # In queue, not yet sent
    "sent",             # First email sent
    "opened",           # Email opened (if tracking available)
    "replied",          # Prospect replied
    "engaged",          # Active conversation
    "sample_sent",      # Free sample/data provided
    "proposal_sent",    # Formal proposal/pricing sent
    "negotiating",      # In negotiation
    "won",              # Closed won
    "lost",             # Closed lost
    "bounced",          # Email bounced
    "unsubscribed",     # Asked to be removed
    "no_response"       # No response after full sequence
]

# ══════════════════════════════════════════════════════════════════════════
# 7. SALES METRICS TARGETS
# ══════════════════════════════════════════════════════════════════════════

MONTHLY_TARGETS = {
    "emails_sent": 480 * 30,  # ~14,400/month at 20/hr
    "response_rate_target": 0.03,  # 3% response rate
    "meetings_booked": 20,
    "deals_closed": 5,
    "revenue_target": 5000,  # $5K/month starting target
    "avg_deal_size_target": 1000
}
