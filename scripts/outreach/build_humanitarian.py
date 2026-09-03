"""
HUMANITARIAN OUTREACH LEADS — Disaster preparedness & aid distribution orgs.
GRID maps 3.5M worship sites as pre-positioned community hubs for disaster response.

Tiers:
  Tier 1 — UN/Govt/Global coordinating bodies (OCHA, WFP, USAID, FEMA)
  Tier 2 — Major INGOs with GIS capacity (IFRC, CRS, World Vision, IRC)
  Tier 3 — Specialized emergency response (Team Rubicon, Direct Relief, MSF)
  Tier 4 — Faith-based relief orgs (Islamic Relief, Samaritan's Purse, etc.)
  Tier 5 — Think tanks / Research (ODI, ALNAP, Humanitarian Data Exchange)
"""

LEADS = [
    # ═══════════════════════════════════════════
    # TIER 1 — UN COORDINATING BODIES & GOVT
    # ═══════════════════════════════════════════
    {"org": "UN OCHA — Centre for Humanitarian Data", "email": "centrehumdata@un.org", "tier": 1, "sector": "UN Coordination", "notes": "Manages HDX platform. Esri enterprise partner. GIS-forward."},
    {"org": "UN OCHA — Field Information Services", "email": "ocha-fis@un.org", "tier": 1, "sector": "UN Coordination", "notes": "Geospatial data strategy lead. ArcGIS enterprise."},
    {"org": "UN World Food Programme (WFP)", "email": "wfpinfo@wfp.org", "tier": 1, "sector": "UN Agency", "notes": "Food distribution logistics. Needs community hub mapping."},
    {"org": "UNHCR — Innovation Service", "email": "innovation@unhcr.org", "tier": 1, "sector": "UN Agency", "notes": "Refugee camp planning. GIS + community infrastructure."},
    {"org": "UNICEF — Emergency Programmes", "email": "emergency@unicef.org", "tier": 1, "sector": "UN Agency", "notes": "Child-focused emergency response. Supply distribution."},
    {"org": "UNDP — Crisis Bureau", "email": "crisis.bureau@undp.org", "tier": 1, "sector": "UN Agency", "notes": "Early recovery + resilience. Community infrastructure."},
    {"org": "USAID — Bureau for Humanitarian Assistance (BHA)", "email": "bha.info@usaid.gov", "tier": 1, "sector": "Government", "notes": "Lead US disaster response agency. OFDA successor."},
    {"org": "FEMA — National Preparedness Directorate", "email": "fema-npd@fema.dhs.gov", "tier": 1, "sector": "Government", "notes": "We already have FEMA NRI data. Natural partner."},
    {"org": "EU — Humanitarian Aid & Civil Protection (ECHO)", "email": "echo-info@ec.europa.eu", "tier": 1, "sector": "Government", "notes": "EU disaster response coordination. DG ECHO."},
    {"org": "UK Foreign, Commonwealth & Development Office (FCDO)", "email": "fcdo.correspondence@fcdo.gov.uk", "tier": 1, "sector": "Government", "notes": "UK humanitarian lead. CHASE team."},

    # ═══════════════════════════════════════════
    # TIER 2 — MAJOR INGOs (GIS CAPACITY)
    # ═══════════════════════════════════════════
    {"org": "IFRC — GIS & Information Management", "email": "im@ifrc.org", "tier": 2, "sector": "INGO", "notes": "IFRC GO platform. GIS training network. 191 national societies. Missing Maps partner."},
    {"org": "American Red Cross — International Services", "email": "international@redcross.org", "tier": 2, "sector": "INGO", "notes": "Missing Maps co-founder. GIS for disaster response. Heat risk mapping."},
    {"org": "British Red Cross — GIS Team", "email": "gis@redcross.org.uk", "tier": 2, "sector": "INGO", "notes": "Co-developed IFRC GIS training platform. HeiGIT partner."},
    {"org": "Netherlands Red Cross — 510 Data & Digital", "email": "510@redcross.nl", "tier": 2, "sector": "INGO", "notes": "Data innovation hub. GIS + predictive analytics for disasters."},
    {"org": "Catholic Relief Services (CRS)", "email": "info@crs.org", "tier": 2, "sector": "INGO", "notes": "100+ countries. Uses Catholic parish networks for aid distribution. GRID has 33K Catholic hierarchy rows."},
    {"org": "World Vision International", "email": "info@wvi.org", "tier": 2, "sector": "INGO", "notes": "90+ countries. Church-based community networks. Largest child-focused relief org."},
    {"org": "International Rescue Committee (IRC)", "email": "donations@rescue.org", "tier": 2, "sector": "INGO", "notes": "40+ countries. GIS services for OFDA. Camp planning + community mapping."},
    {"org": "Mercy Corps", "email": "info@mercycorps.org", "tier": 2, "sector": "INGO", "notes": "40+ countries. Cash aid + market-based response. Community infrastructure data needed."},
    {"org": "Oxfam International", "email": "information@oxfaminternational.org", "tier": 2, "sector": "INGO", "notes": "90+ countries. WASH + food security. Local partner networks."},
    {"org": "Save the Children International", "email": "info@savethechildren.org", "tier": 2, "sector": "INGO", "notes": "120 countries. Child protection in emergencies. Supply chain mapping."},
    {"org": "CARE International", "email": "info@careinternational.org", "tier": 2, "sector": "INGO", "notes": "100+ countries. Women-focused emergency response. Community-based distribution."},

    # ═══════════════════════════════════════════
    # TIER 3 — SPECIALIZED EMERGENCY RESPONSE
    # ═══════════════════════════════════════════
    {"org": "Team Rubicon", "email": "partnerships@teamrubiconusa.org", "tier": 3, "sector": "Emergency Response", "notes": "Veteran-led disaster response. Needs pre-disaster community asset mapping."},
    {"org": "Direct Relief", "email": "info@directrelief.org", "tier": 3, "sector": "Emergency Response", "notes": "Medical aid logistics. 514 shipments/week to 46 states + 22 countries. Needs facility mapping."},
    {"org": "Americares", "email": "DMaguire@Americares.org", "tier": 3, "sector": "Emergency Response", "notes": "Diana Maguire — emergency response partnerships. Health-focused. 1-800-486-HELP."},
    {"org": "Médecins Sans Frontières (MSF) International", "email": "office@msf.org", "tier": 3, "sector": "Emergency Response", "notes": "70+ countries. Medical emergency response. Needs community health facility mapping."},
    {"org": "International Medical Corps", "email": "info@internationalmedicalcorps.org", "tier": 3, "sector": "Emergency Response", "notes": "30+ countries. Health + training in emergencies. Community health network data."},
    {"org": "All Hands and Hearts", "email": "info@allhandsandhearts.org", "tier": 3, "sector": "Emergency Response", "notes": "School/community building reconstruction. Needs pre-disaster facility inventory."},
    {"org": "Humanity & Inclusion (HI)", "email": "info@hi.org", "tier": 3, "sector": "Emergency Response", "notes": "Disability-inclusive emergency response. 60 countries. Accessibility mapping."},

    # ═══════════════════════════════════════════
    # TIER 4 — FAITH-BASED RELIEF ORGS
    # ═══════════════════════════════════════════
    {"org": "Islamic Relief Worldwide", "email": "info@islamic-relief.org", "tier": 4, "sector": "Faith-Based Relief", "notes": "40+ countries. GRID has 361K mosques — instant distribution network map."},
    {"org": "Islamic Relief USA", "email": "info@irusa.org", "tier": 4, "sector": "Faith-Based Relief", "notes": "US affiliate. Emergency response + disaster prep. Mosque network mapping."},
    {"org": "Samaritan's Purse", "email": "info@samaritan.org", "tier": 4, "sector": "Faith-Based Relief", "notes": "100+ countries. Emergency field hospitals. Church-based distribution. Boone, NC."},
    {"org": "World Relief", "email": "info@worldrelief.org", "tier": 4, "sector": "Faith-Based Relief", "notes": "Evangelical relief org. Church-based refugee resettlement. 20+ countries."},
    {"org": "ADRA (Adventist Development & Relief Agency)", "email": "info@adra.org", "tier": 4, "sector": "Faith-Based Relief", "notes": "120 countries. SDA church network. GRID has SDA classification."},
    {"org": "Caritas Internationalis", "email": "info@caritas.org", "tier": 4, "sector": "Faith-Based Relief", "notes": "200+ country network. Catholic parish-based aid. Vatican City HQ. GRID has Catholic hierarchy."},
    {"org": "Tearfund", "email": "info@tearfund.org", "tier": 4, "sector": "Faith-Based Relief", "notes": "50+ countries. Evangelical relief + development. Church-based community networks."},
    {"org": "Lutheran World Relief", "email": "info@lwr.org", "tier": 4, "sector": "Faith-Based Relief", "notes": "30+ countries. Lutheran church networks. GRID has 57K Lutheran hierarchy rows."},
    {"org": "Church World Service (CWS)", "email": "info@cwsglobal.org", "tier": 4, "sector": "Faith-Based Relief", "notes": "30+ countries. Interfaith. Refugee resettlement + disaster response."},
    {"org": "American Jewish World Service (AJWS)", "email": "info@ajws.org", "tier": 4, "sector": "Faith-Based Relief", "notes": "19 countries. Human rights + disaster response. Jewish community networks."},

    # ═══════════════════════════════════════════
    # TIER 5 — THINK TANKS / RESEARCH / PLATFORMS
    # ═══════════════════════════════════════════
    {"org": "Humanitarian Data Exchange (HDX)", "email": "hdx@un.org", "tier": 5, "sector": "Data Platform", "notes": "Would host GRID as a public dataset. Managed by OCHA Centre."},
    {"org": "ALNAP (Active Learning Network for Accountability & Performance)", "email": "alnap@alnap.org", "tier": 5, "sector": "Research", "notes": "Humanitarian evaluation network. Evidence + data for better response."},
    {"org": "ODI — Humanitarian Policy Group (HPG)", "email": "hpg@odi.org.uk", "tier": 5, "sector": "Research", "notes": "Humanitarian policy research. Evidence-based practice."},
    {"org": "ACAPS", "email": "info@acaps.org", "tier": 5, "sector": "Research", "notes": "Needs assessment + crisis analysis. Data-driven humanitarian decision making."},
    {"org": "MapAction", "email": "info@mapaction.org", "tier": 5, "sector": "GIS/Data", "notes": "Emergency mapping charity. Deploys GIS teams to disasters. Natural GRID consumer."},
    {"org": "Humanitarian OpenStreetMap Team (HOT)", "email": "info@hotosm.org", "tier": 5, "sector": "GIS/Data", "notes": "Open mapping for humanitarian response. Missing Maps co-founder. GRID complements OSM."},
    {"org": "Esri — Disaster Response Program", "email": "disasterresponse@esri.com", "tier": 5, "sector": "GIS/Data", "notes": "Provides ArcGIS to disaster ops. OCHA's enterprise GIS partner already. Potential reseller."},
    {"org": "REACH Initiative", "email": "geneva@reach-initiative.org", "tier": 5, "sector": "Research", "notes": "Humanitarian data collection + analysis. 30+ crisis contexts."},
    {"org": "Ground Truth Solutions", "email": "info@groundtruthsolutions.org", "tier": 5, "sector": "Research", "notes": "Humanitarian feedback data. Perceptions of aid recipients. Community engagement."},
]

import json
from pathlib import Path

OUT = Path("outputs/outreach")
OUT.mkdir(parents=True, exist_ok=True)

# Export leads
json.dump(LEADS, open(OUT / "humanitarian_leads.json", "w"), indent=2)

# Summary
from collections import Counter
print(f"=== HUMANITARIAN LEADS: {len(LEADS)} total ===\n")
for tier in sorted(Counter(l['tier'] for l in LEADS)):
    tier_leads = [l for l in LEADS if l['tier'] == tier]
    print(f"Tier {tier} ({len(tier_leads)}):")
    for l in tier_leads:
        print(f"  {l['org']:<55s} | {l['email']}")
    print()

print("Saved to outputs/outreach/humanitarian_leads.json")
