"""Hindu + Muslim US outreach leads."""
LEADS = [
    # ═══ HINDU ORGS ═══
    {"org": "Hindu American Foundation", "email": "info@hafsite.org", "faith": "Hindu", "sector": "Advocacy"},
    {"org": "ISKCON (International Society for Krishna Consciousness)", "email": "info@iskcon.org", "faith": "Hindu", "sector": "Umbrella"},
    {"org": "Bochasanwasi Akshar Purushottam Swaminarayan Sanstha (BAPS)", "email": "info@baps.org", "faith": "Hindu", "sector": "Umbrella"},
    {"org": "Vishwa Hindu Parishad of America", "email": "info@vhp-america.org", "faith": "Hindu", "sector": "Umbrella"},
    {"org": "Hindu Temple Executives Conference", "email": "info@hteconference.org", "faith": "Hindu", "sector": "Umbrella"},
    {"org": "Hindu Students Council", "email": "info@hindustudentscouncil.org", "faith": "Hindu", "sector": "Education"},
    {"org": "Hindu University of America", "email": "info@hua.edu", "faith": "Hindu", "sector": "Education"},
    {"org": "The Pluralism Project (Harvard)", "email": "pluralism@harvard.edu", "faith": "Hindu/Islam", "sector": "Research"},
    {"org": "Hindu Mandir Executives Conference", "email": "info@hmec.org", "faith": "Hindu", "sector": "Umbrella"},
    {"org": "Encyclopedia of Hinduism", "email": "info@encyclopediaofhinduism.org", "faith": "Hindu", "sector": "Research"},
    {"org": "Oxford Centre for Hindu Studies", "email": "info@ochs.org.uk", "faith": "Hindu", "sector": "Academic"},
    {"org": "Sri Venkateswara Temple (Bridgewater)", "email": "info@venkateswara.org", "faith": "Hindu", "sector": "Temple"},
    {"org": "Shirdi Sai Baba Temple", "email": "info@shirdisai.org", "faith": "Hindu", "sector": "Temple"},
    {"org": "Art of Living Foundation", "email": "info@artofliving.org", "faith": "Hindu", "sector": "Organization"},

    # ═══ MUSLIM ORGS ═══
    {"org": "Islamic Society of North America (ISNA)", "email": "info@isna.net", "faith": "Islam", "sector": "Umbrella"},
    {"org": "Council on American-Islamic Relations (CAIR)", "email": "info@cair.com", "faith": "Islam", "sector": "Advocacy"},
    {"org": "Muslim Public Affairs Council (MPAC)", "email": "info@mpac.org", "faith": "Islam", "sector": "Advocacy"},
    {"org": "Islamic Relief USA", "email": "info@irusa.org", "faith": "Islam", "sector": "Nonprofit"},
    {"org": "Zakat Foundation of America", "email": "info@zakat.org", "faith": "Islam", "sector": "Nonprofit"},
    {"org": "International Institute of Islamic Thought (IIIT)", "email": "info@iiit.org", "faith": "Islam", "sector": "Research"},
    {"org": "Fiqh Council of North America", "email": "info@fiqhcouncil.org", "faith": "Islam", "sector": "Religious"},
    {"org": "Islamic Circle of North America (ICNA)", "email": "info@icna.org", "faith": "Islam", "sector": "Umbrella"},
    {"org": "Muslim Students Association (MSA) National", "email": "info@msanational.org", "faith": "Islam", "sector": "Education"},
    {"org": "American Muslims for Palestine", "email": "info@ampalestine.org", "faith": "Islam", "sector": "Advocacy"},
    {"org": "Islamic Networks Group (ING)", "email": "info@ing.org", "faith": "Islam", "sector": "Education"},
    {"org": "The Institute for Social Policy & Understanding (ISPU)", "email": "info@ispu.org", "faith": "Islam", "sector": "Research"},
    {"org": "DinarStandard — Muslim Market Research", "email": "info@dinarstandard.com", "faith": "Islam", "sector": "Research"},
    {"org": "Muslim Pro / IslamicFinder", "email": "info@islamicfinder.org", "faith": "Islam", "sector": "Tech"},
    {"org": "Al-Mustafa Institute", "email": "info@almustafa.org", "faith": "Islam", "sector": "Education"},
    {"org": "Inner-City Muslim Action Network (IMAN)", "email": "info@iman.org", "faith": "Islam", "sector": "Nonprofit"},
    {"org": "Islamic Development Bank (IsDB)", "email": "info@isdb.org", "faith": "Islam", "sector": "International"},
    {"org": "Organization of Islamic Cooperation (OIC)", "email": "info@oic-oci.org", "faith": "Islam", "sector": "International"},
    {"org": "Diyanet Center of America", "email": "info@diyanetamerica.org", "faith": "Islam", "sector": "Religious"},
    {"org": "Oxford Islamic Studies Online", "email": "info@oxfordislamicstudies.com", "faith": "Islam", "sector": "Academic"},
    {"org": "Royal Aal al-Bayt Institute for Islamic Thought", "email": "info@aalalbayt.org", "faith": "Islam", "sector": "Academic"},

    # ═══ INTERFAITH ═══
    {"org": "Interfaith Youth Core (IFYC)", "email": "info@ifyc.org", "faith": "Interfaith", "sector": "Nonprofit"},
    {"org": "Shoulder to Shoulder Campaign", "email": "info@shouldertoshouldercampaign.org", "faith": "Interfaith", "sector": "Advocacy"},
]

import json
from pathlib import Path
OUT = Path("outputs/outreach")
OUT.mkdir(parents=True, exist_ok=True)
json.dump(LEADS, open(OUT/"hindu_muslim_leads.json","w"), indent=2)
print(f"Saved {len(LEADS)} leads ({sum(1 for l in LEADS if 'Hindu' in l['faith']) or '?'} Hindu, {sum(1 for l in LEADS if 'Islam' in l['faith'])} Muslim)")
for faith, count in __import__('collections').Counter(l['faith'] for l in LEADS).most_common():
    print(f"  {faith}: {count}")
