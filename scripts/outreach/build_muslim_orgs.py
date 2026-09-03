"""Build Muslim organization outreach leads — relief, advocacy, media, finance, pilgrimage."""
import json, sqlite3
from pathlib import Path
OUT = Path("outputs/outreach")

LEADS = [
    # ═══ UMBRELLA / ADVOCACY ═══
    {"org": "Islamic Society of North America (ISNA)", "email": "info@isna.net", "sector": "Advocacy", "sub": "300+ affiliated mosques, largest US Muslim org"},
    {"org": "Islamic Circle of North America (ICNA)", "email": "info@icna.org", "sector": "Advocacy", "sub": "200+ chapters, community outreach"},
    {"org": "Council on American-Islamic Relations (CAIR)", "email": "info@cair.com", "sector": "Advocacy", "sub": "Civil rights, 35+ chapters"},
    {"org": "Muslim Public Affairs Council (MPAC)", "email": "info@mpac.org", "sector": "Advocacy", "sub": "Policy & media advocacy"},
    {"org": "Islamic Supreme Council of America", "email": "info@islamicsupremecouncil.org", "sector": "Advocacy", "sub": "Traditional Islam, interfaith"},
    {"org": "Federation of Islamic Associations (FIA)", "email": "info@fiaonline.org", "sector": "Umbrella", "sub": "US mosque federation"},
    {"org": "MAS (Muslim American Society)", "email": "info@muslimamericansociety.org", "sector": "Advocacy", "sub": "Community organizing, 50+ chapters"},
    {"org": "Islamic Networks Group (ING)", "email": "info@ing.org", "sector": "Education", "sub": "Interfaith education, speaker network"},
    {"org": "Zaytuna College", "email": "info@zaytuna.edu", "sector": "Education", "sub": "First US accredited Muslim liberal arts college"},
    {"org": "Bayyinah Institute", "email": "info@bayyinah.com", "sector": "Education", "sub": "Quranic Arabic education"},
    {"org": "Al-Maghrib Institute", "email": "info@almaghrib.org", "sector": "Education", "sub": "Islamic seminary-style classes, 80K+ students"},

    # ═══ RELIEF / HUMANITARIAN ═══
    {"org": "Islamic Relief USA", "email": "info@irusa.org", "sector": "Relief", "sub": "Largest Muslim relief org, 40+ countries"},
    {"org": "Muslim Aid USA", "email": "info@muslimaidusa.org", "sector": "Relief", "sub": "International relief & development"},
    {"org": "Zakat Foundation of America", "email": "info@zakat.org", "sector": "Relief", "sub": "Zakat-based relief, 50+ countries"},
    {"org": "Ummah Welfare Trust", "email": "info@uwt.org", "sector": "Relief", "sub": "Islamic relief, UK/US based"},
    {"org": "Baitulmaal", "email": "info@baitulmaal.org", "sector": "Relief", "sub": "Muslim relief & development"},
    {"org": "Penny Appeal USA", "email": "info@pennyappealusa.org", "sector": "Relief", "sub": "Mosque water projects, Ramadan food packs"},
    {"org": "Human Appeal USA", "email": "info@humanappealusa.org", "sector": "Relief", "sub": "International relief, mosque partnerships"},
    {"org": "Islamic Help USA", "email": "info@islamichelpusa.org", "sector": "Relief", "sub": "Water, food, education programs"},
    {"org": "MISF (Muslim International Student Fund)", "email": "info@misfusa.org", "sector": "Education", "sub": "Scholarship & community programs"},

    # ═══ MEDIA / PUBLISHING ═══
    {"org": "Bridges TV (Bridges Network)", "email": "info@bridgestv.com", "sector": "Media", "sub": "Muslim American TV network"},
    {"org": "Islam Channel", "email": "info@islamchannel.tv", "sector": "Media", "sub": "UK-based, global Muslim TV"},
    {"org": "AboutIslam.net", "email": "info@aboutislam.net", "sector": "Media", "sub": "Islamic content & outreach"},
    {"org": "MuslimMatters.org", "email": "info@muslimmatters.org", "sector": "Media", "sub": "Muslim community blog/magazine"},
    {"org": "Amana Publications", "email": "info@amana-publications.com", "sector": "Publishing", "sub": "Islamic book publisher"},
    {"org": "Kube Publishing / The Islamic Foundation", "email": "info@kubepublishing.com", "sector": "Publishing", "sub": "Islamic academic publisher"},
    {"org": "IIIT (International Institute of Islamic Thought)", "email": "info@iiit.org", "sector": "Research", "sub": "Islamic research & publishing"},

    # ═══ ISLAMIC FINANCE ═══
    {"org": "Amana Mutual Funds (Saturna Capital)", "email": "info@amanafunds.com", "sector": "Finance", "sub": "Largest Islamic mutual funds, $3B+ AUM"},
    {"org": "Guidance Residential", "email": "info@guidanceresidential.com", "sector": "Finance", "sub": "Islamic home financing, 50+ US states"},
    {"org": "Devon Bank (Islamic Banking Division)", "email": "info@devonbank.com", "sector": "Finance", "sub": "Shariah-compliant banking Chicago"},
    {"org": "University Islamic Financial", "email": "info@universityislamicfinancial.com", "sector": "Finance", "sub": "Islamic mortgage & finance, MI"},
    {"org": "Al Baraka Bank USA", "email": "info@albaraka.com", "sector": "Finance", "sub": "Islamic banking, 5 US branches"},

    # ═══ PILGRIMAGE / UMRAH ═══
    {"org": "SalamAir (Hajj packages)", "email": "info@salamair.com", "sector": "Travel", "sub": "Hajj & Umrah travel"},
    {"org": "Nusuk (Saudi Hajj Ministry platform)", "email": "info@nusuk.sa", "sector": "Travel", "sub": "Official Hajj booking platform"},
    {"org": "Al-Haramain Travel", "email": "info@alharamaintravel.com", "sector": "Travel", "sub": "Hajj/Umrah tour operator, 20+ years"},
    {"org": "Dar El Salam Travel", "email": "info@darelsalamtravel.com", "sector": "Travel", "sub": "Hajj/Umrah, 150+ US cities"},

    # ═══ HALAL CERTIFICATION ═══
    {"org": "Islamic Food and Nutrition Council of America (IFANCA)", "email": "info@ifanca.org", "sector": "Halal", "sub": "Largest US halal certifier"},
    {"org": "Halal Food Standards Alliance of America (HFSAA)", "email": "info@hfsaa.org", "sector": "Halal", "sub": "North American halal certification"},
    {"org": "Islamic Services of America (ISA)", "email": "info@isaiowa.org", "sector": "Halal", "sub": "Halal certification, Cedar Rapids IA"},
    {"org": "American Halal Association", "email": "info@americanhalalassociation.org", "sector": "Halal", "sub": "Halal business network"},
    {"org": "Shari'ah Association of North America (SANA)", "email": "info@sanahalal.com", "sector": "Halal", "sub": "Halal certifier, 15+ years"},

    # ═══ FUNERAL / BURIAL ═══
    {"org": "Islamic Funeral Services of America", "email": "info@islamicfuneral.com", "sector": "Funeral", "sub": "Muslim funeral services, 30+ states"},
    {"org": "Garden of Peace (Muslim cemetery)", "email": "info@gardenofpeace.org", "sector": "Funeral", "sub": "Largest US Muslim cemetery, MA"},
    {"org": "Janazah Services Network", "email": "info@janazahservices.com", "sector": "Funeral", "sub": "National Muslim burial network"},

    # ═══ MOSQUE DATABASES / DIRECTORY COMPETITORS (potential partners) ═══
    {"org": "Salatomatic / Zabihah", "email": "info@salatomatic.com", "sector": "Directory", "sub": "Mosque & halal restaurant directory"},
    {"org": "IslamicFinder", "email": "info@islamicfinder.org", "sector": "Directory", "sub": "Mosque finder, prayer times — 10M+ users"},
    {"org": "Mosalasala / Masjidway", "email": "info@mosqueway.com", "sector": "Directory", "sub": "Mosque directory platform"},
]

db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

# Stats for pitch
muslim_total = db.execute("SELECT COUNT(*) as n FROM churches WHERE faith='Islam'").fetchone()['n']
muslim_trads = db.execute("SELECT COUNT(DISTINCT tradition) as n FROM churches WHERE faith='Islam' AND tradition IS NOT NULL").fetchone()['n']
muslim_us = db.execute("SELECT COUNT(*) as n FROM churches WHERE faith='Islam' AND country='US'").fetchone()['n']
with_contact = db.execute("SELECT COUNT(DISTINCT cv.church_id) as n FROM church_contact_values cv JOIN churches c ON c.id=cv.church_id WHERE c.faith='Islam' AND cv.contact_type IN ('email','phone','website')").fetchone()['n']
top_countries = db.execute("SELECT country, COUNT(*) as n FROM churches WHERE faith='Islam' GROUP BY country ORDER BY n DESC LIMIT 10").fetchall()
db.close()

print(f"Muslim worship sites: {muslim_total:,} global ({muslim_us:,} US)")
print(f"  Traditions: {muslim_trads} classified (Sunni/Shia/Ibadi/Sufi/etc.)")
print(f"  With contact info: {with_contact:,}")
for c in top_countries:
    print(f"  {c['country']}: {c['n']:,}")

json.dump(LEADS, open(OUT/"muslim_org_leads.json","w"), indent=2)
from collections import Counter
for sector, count in Counter(l['sector'] for l in LEADS).most_common():
    print(f"  {sector}: {count}")
print(f"Total: {len(LEADS)}")
