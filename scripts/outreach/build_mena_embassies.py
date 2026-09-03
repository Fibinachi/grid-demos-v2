"""
Build MENA embassy/MOIA outreach leads — country-specific pitches.
PRIMARY ASK: their government mosque registry/list.
SECONDARY: licensing/partnership on our global dataset.
"""
import json
from pathlib import Path
OUT = Path("outputs/outreach")

LEADS = [
    # ═══ TIER 1: LARGEST MOSQUE COUNTRIES ═══

    {
        "org": "Indonesian Embassy Washington DC — Religious Affairs",
        "email": "consular@embassyofindonesia.org",
        "sector": "Government", "country": "ID", "mosques_in_grid": 98314,
        "pitch_angle": "worlds_largest",
        "subject": "GRID: 100K Indonesian mosques mapped — seeking Kemenag mosque registry",
        "body": (
            "Dear Religious Affairs Attaché,\n\n"
            "I direct the Global Religious Infrastructure Database (GRID). We have mapped "
            "100,499 mosques in Indonesia — the largest single-country mosque dataset in the "
            "world — alongside 378,573 mosques across 80+ countries.\n\n"
            "Indonesia's Ministry of Religious Affairs (Kemenag) reportedly tracks over 800,000 "
            "mosques nationwide. I am writing to request access to Kemenag's mosque registry — "
            "even at the kabupaten level, a simple list of names and locations would allow us "
            "to dramatically improve our coverage, which currently stands at about 12%.\n\n"
            "I am also open to discussing whether our global dataset — with 17 Islamic traditions "
            "classified, GPS coordinates, and diaspora mosque mapping across the US (6,185 "
            "mosques), Europe, and Australia — would be useful to Kemenag's work.\n\n"
            "I can be reached at charlesaprescott@outlook.com.\n\n"
            "With respect,\nCharles Prescott\nCreator, GRID\nJD/LLM (Taxation) · Trinity College\ncharlesaprescottjr@gmail.com"
        ),
    },

    {
        "org": "Turkish Embassy Washington DC — Religious Affairs (Diyanet)",
        "email": "embassy.washingtondc@mfa.gov.tr",
        "sector": "Government", "country": "TR", "mosques_in_grid": 36613,
        "pitch_angle": "diyanet_diaspora",
        "subject": "GRID: 38K Turkish mosques mapped — seeking Diyanet mosque registry",
        "body": (
            "To the Religious Affairs Counselor,\n\n"
            "I direct the Global Religious Infrastructure Database (GRID). We have mapped "
            "37,917 mosques in Turkey and 378,573 globally across 80+ countries.\n\n"
            "Diyanet reportedly oversees 85,000+ mosques domestically. I am writing to request "
            "access to Diyanet's mosque registry — even a simple list of names and il/ilçe "
            "locations would allow us to close the gap between our 38K and your 85K+. "
            "We are happy to sign any data-use agreement required.\n\n"
            "I would also be glad to discuss whether our global dataset — with tradition-level "
            "classification and diaspora mosque mapping across Germany (2,806 mosques), France, "
            "the Netherlands, Belgium, Austria, the UK, and the US — is useful to Diyanet's "
            "international work.\n\n"
            "I can be reached at charlesaprescott@outlook.com. English preferred — my Turkish "
            "is unfortunately nonexistent.\n\n"
            "Saygılarımla,\nCharles Prescott\nCreator, GRID\nJD/LLM (Taxation) · Trinity College\ncharlesaprescottjr@gmail.com"
        ),
    },

    {
        "org": "Embassy of Yemen Washington DC",
        "email": "consular@yemenembassy.org",
        "sector": "Government", "country": "YE", "mosques_in_grid": 33193,
        "pitch_angle": "reconstruction",
        "subject": "GRID: 33K Yemeni mosques mapped — seeking Awqaf mosque registry",
        "body": (
            "To the Embassy of Yemen,\n\n"
            "I direct the Global Religious Infrastructure Database (GRID). We have mapped "
            "33,311 mosques in Yemen — the third-largest country dataset globally, behind "
            "only Indonesia and Saudi Arabia.\n\n"
            "The Yemeni Ministry of Awqaf and Religious Guidance maintains the country's "
            "official mosque registry. I am writing to request access to this list — even at "
            "the governorate level, a simple count or name list would help us reconcile and "
            "improve our data. This is also a matter of cultural heritage: many of these sites "
            "have been damaged by conflict, and an accurate baseline supports preservation "
            "and eventual reconstruction planning.\n\n"
            "I would also welcome a discussion about whether our global dataset has value "
            "for the Ministry's work with Yemeni diaspora communities.\n\n"
            "I can be reached at charlesaprescott@outlook.com.\n\n"
            "With respect,\nCharles Prescott\nCreator, GRID\nJD/LLM (Taxation) · Trinity College\ncharlesaprescottjr@gmail.com"
        ),
    },

    {
        "org": "Embassy of Malaysia Washington DC — Religious Affairs",
        "email": "consular@malaysiaembassy.org",
        "sector": "Government", "country": "MY", "mosques_in_grid": 15962,
        "pitch_angle": "jakim_halal",
        "subject": "GRID: 16K Malaysian mosques mapped — seeking JAKIM mosque registry",
        "body": (
            "To the Religious Affairs Attaché,\n\n"
            "I direct the Global Religious Infrastructure Database (GRID). We have mapped "
            "16,623 mosques in Malaysia and 378,573 globally across 80+ countries.\n\n"
            "JAKIM reportedly registers 6,000+ mosques and 15,000+ suraus nationwide. "
            "I am writing to request access to this registry — even a summary-level list "
            "by state would allow us to substantially improve our Malaysian coverage.\n\n"
            "I would also be glad to discuss whether our global dataset — mapping Malaysian "
            "diaspora communities from Australian university suraus to mosques in the UK, US, "
            "and Middle East — supports JAKIM's halal economy and diaspora engagement work.\n\n"
            "I can be reached at charlesaprescott@outlook.com.\n\n"
            "With respect,\nCharles Prescott\nCreator, GRID\nJD/LLM (Taxation) · Trinity College\ncharlesaprescottjr@gmail.com"
        ),
    },

    {
        "org": "Bangladesh Embassy Washington DC",
        "email": "consular@bdelasdc.org",
        "sector": "Government", "country": "BD", "mosques_in_grid": 13640,
        "pitch_angle": "diaspora",
        "subject": "GRID: 14K Bangladeshi mosques mapped — seeking Islamic Foundation registry",
        "body": (
            "To the Embassy of Bangladesh,\n\n"
            "I direct the Global Religious Infrastructure Database (GRID). We have mapped "
            "14,305 mosques in Bangladesh and 378,573 globally.\n\n"
            "The Islamic Foundation Bangladesh reportedly oversees 300,000+ mosques. I am "
            "writing to request access to this registry — even a summary by division or "
            "district would dramatically improve our coverage and help us better represent "
            "Bangladesh's mosque infrastructure globally.\n\n"
            "I would also welcome a conversation about whether our global dataset — which "
            "maps Bangladeshi diaspora mosque communities in the UK (Tower Hamlets, "
            "Birmingham), US (New York, Detroit), the Gulf, and Southeast Asia — is useful "
            "to the Islamic Foundation's work.\n\n"
            "I can be reached at charlesaprescott@outlook.com.\n\n"
            "With respect,\nCharles Prescott\nCreator, GRID\nJD/LLM (Taxation) · Trinity College\ncharlesaprescottjr@gmail.com"
        ),
    },

    {
        "org": "Pakistani Embassy Washington DC — Community Affairs",
        "email": "community@pakistanembassy.org",
        "sector": "Government", "country": "PK", "mosques_in_grid": 9643,
        "pitch_angle": "diaspora",
        "subject": "GRID: 10K Pakistani mosques mapped — seeking Religious Affairs registry",
        "body": (
            "Dear Community Affairs Officer,\n\n"
            "I direct the Global Religious Infrastructure Database (GRID). We have mapped "
            "10,751 mosques in Pakistan and 378,573 globally across 80+ countries.\n\n"
            "Pakistan's Ministry of Religious Affairs and Interfaith Harmony maintains the "
            "country's mosque registry. I am writing to request access to this list — even "
            "province-level summaries would allow us to significantly improve our coverage.\n\n"
            "I would also welcome a conversation about whether our global dataset — which maps "
            "Pakistani diaspora mosque networks in the UK (Birmingham, Bradford, Manchester), "
            "US (New York, Chicago, Houston), Canada, and the Gulf — is useful to the Ministry's "
            "diaspora outreach and interfaith coordination work.\n\n"
            "I can be reached at charlesaprescott@outlook.com.\n\n"
            "With respect,\nCharles Prescott\nCreator, GRID\nJD/LLM (Taxation) · Trinity College\ncharlesaprescottjr@gmail.com"
        ),
    },

    {
        "org": "Embassy of Algeria Washington DC",
        "email": "consular@algerianembassy.org",
        "sector": "Government", "country": "DZ", "mosques_in_grid": 10058,
        "pitch_angle": "maghreb",
        "subject": "GRID: 10K Algerian mosques mapped — seeking Religious Affairs registry",
        "body": (
            "To the Embassy of Algeria,\n\n"
            "I direct the Global Religious Infrastructure Database (GRID). We have mapped "
            "10,369 mosques in Algeria — the largest mosque dataset in the Maghreb — and "
            "378,573 globally.\n\n"
            "Algeria's Ministry of Religious Affairs and Endowments reportedly oversees "
            "20,000+ mosques across all 58 wilayas. I am writing to request access to this "
            "registry — even a wilaya-level summary would allow us to substantially improve "
            "our coverage, which currently stands at roughly 50%.\n\n"
            "I would also be glad to discuss whether our global dataset — which maps Algerian "
            "diaspora mosques across France (Paris, Lyon, Marseille), Belgium, and Canada — "
            "is useful to the Ministry.\n\n"
            "I can be reached at charlesaprescott@outlook.com.\n\n"
            "With respect,\nCharles Prescott\nCreator, GRID\nJD/LLM (Taxation) · Trinity College\ncharlesaprescottjr@gmail.com"
        ),
    },

    {
        "org": "Interests Section of Iran Washington DC",
        "email": "consular@daftar.org",
        "sector": "Government", "country": "IR", "mosques_in_grid": 7906,
        "pitch_angle": "shia_global",
        "subject": "GRID: 9K Iranian mosques mapped — seeking Owqaf mosque registry",
        "body": (
            "To the Iranian Interests Section,\n\n"
            "I direct the Global Religious Infrastructure Database (GRID). We have mapped "
            "9,434 mosques in Iran — the largest classified Shia mosque dataset in the world — "
            "and 378,573 globally across 80+ countries.\n\n"
            "Iran's Organization of Endowments and Charitable Affairs (Owqaf) reportedly "
            "registers 80,000+ mosques. I am writing to request access to this registry — "
            "even a province-level (ostan) summary would allow us to dramatically improve "
            "our coverage, currently at about 12%.\n\n"
            "I would also welcome a discussion about whether our global dataset — which maps "
            "Shia mosque networks across Iraq (4,682), Lebanon, Bahrain (155 Shia from "
            "government data), Pakistan, and diaspora communities in the US, UK, and Canada — "
            "is useful to Owqaf's international work.\n\n"
            "I can be reached at charlesaprescott@outlook.com.\n\n"
            "With respect,\nCharles Prescott\nCreator, GRID\nJD/LLM (Taxation) · Trinity College\ncharlesaprescottjr@gmail.com"
        ),
    },

    # ═══ TIER 2: GULF STATES (global mosque funders) ═══

    {
        "org": "UAE Embassy Washington DC — Religious Affairs",
        "email": "consular@uaeembassy-usa.org",
        "sector": "Government", "country": "AE", "mosques_in_grid": 755,
        "pitch_angle": "awqaf_global",
        "subject": "GRID: Global mosque map — seeking AWQAF mosque registry + partnership",
        "body": (
            "To the Religious Affairs Section,\n\n"
            "I direct the Global Religious Infrastructure Database (GRID). We have mapped "
            "378,573 mosques worldwide across 80+ countries — the most comprehensive independent "
            "mosque infrastructure dataset available.\n\n"
            "The UAE's General Authority of Islamic Affairs and Endowments (AWQAF) maintains "
            "the country's official mosque registry and operates mosque-building programs "
            "globally. I am writing with two requests:\n\n"
            "First, I am writing to request access to AWQAF's mosque list for the UAE — even "
            "a simple name-and-emirate breakdown would help us improve our current coverage "
            "of 760 mosques.\n\n"
            "Second, I would welcome a conversation about whether our global dataset — with "
            "GPS coordinates, 17 tradition classifications, and gap analysis identifying "
            "underserved areas — is useful for AWQAF's international mosque-building planning.\n\n"
            "I can be reached at charlesaprescott@outlook.com.\n\n"
            "With respect,\nCharles Prescott\nCreator, GRID\nJD/LLM (Taxation) · Trinity College\ncharlesaprescottjr@gmail.com"
        ),
    },

    {
        "org": "Embassy of Qatar Washington DC",
        "email": "consular@qatarembassy.org",
        "sector": "Government", "country": "QA", "mosques_in_grid": 156,
        "pitch_angle": "qatar_charity",
        "subject": "GRID: 379K mosques mapped — seeking AWQAF Qatar registry + partnership",
        "body": (
            "To the Embassy of Qatar,\n\n"
            "I direct the Global Religious Infrastructure Database (GRID). We have mapped "
            "378,573 mosques worldwide across 80+ countries.\n\n"
            "Qatar's Ministry of Endowments and Islamic Affairs (AWQAF) maintains the national "
            "mosque registry, and Qatar Charity is one of the world's largest mosque funders. "
            "I am writing with two requests:\n\n"
            "First, I would like access to AWQAF's mosque list for Qatar — our current coverage "
            "of 157 mosques likely undercounts, and even a simple name list would help.\n\n"
            "Second, I would welcome a discussion about whether our global dataset — with GPS "
            "coordinates, tradition-level classification, and gap analysis — supports Qatar "
            "Charity's mosque-building site selection and monitoring worldwide.\n\n"
            "I can be reached at charlesaprescott@outlook.com.\n\n"
            "With respect,\nCharles Prescott\nCreator, GRID\nJD/LLM (Taxation) · Trinity College\ncharlesaprescottjr@gmail.com"
        ),
    },

    {
        "org": "Embassy of Kuwait Washington DC — Cultural Office",
        "email": "consular@kuwaitembassy.us",
        "sector": "Government", "country": "KW", "mosques_in_grid": 352,
        "pitch_angle": "awqaf_funder",
        "subject": "GRID: Global mosque map — seeking Kuwait Awqaf registry + partnership",
        "body": (
            "To the Cultural Affairs Section,\n\n"
            "I direct the Global Religious Infrastructure Database (GRID). We have mapped "
            "378,573 mosques worldwide — the most comprehensive independent mosque "
            "infrastructure dataset available.\n\n"
            "Kuwait's Ministry of Awqaf and Islamic Affairs maintains the national mosque "
            "registry and funds mosque construction across Africa, Asia, and Europe. "
            "I am writing with two requests:\n\n"
            "First, I would like access to Kuwait's mosque list — our current coverage of "
            "367 mosques is limited, and even a simple list would help us improve.\n\n"
            "Second, I would welcome a discussion about whether our global dataset — with "
            "GPS coordinates, tradition classification, and gap analysis for underserved "
            "areas — supports the Ministry's international mosque-building programs.\n\n"
            "I can be reached at charlesaprescott@outlook.com.\n\n"
            "With respect,\nCharles Prescott\nCreator, GRID\nJD/LLM (Taxation) · Trinity College\ncharlesaprescottjr@gmail.com"
        ),
    },

    {
        "org": "Embassy of Bahrain Washington DC",
        "email": "consular@bahrainembassy.org",
        "sector": "Government", "country": "BH", "mosques_in_grid": 1168,
        "pitch_angle": "data_partner",
        "subject": "GRID: 1,170 Bahraini mosques from your open data — seeking more",
        "body": (
            "To the Embassy of Bahrain,\n\n"
            "I direct the Global Religious Infrastructure Database (GRID). We have mapped "
            "1,170 mosques in Bahrain — and I want to acknowledge that 974 of these came "
            "directly from data.gov.bh, Bahrain's excellent open data portal. We classified "
            "all entries by tradition (Sunni Maliki 760, Shia Twelver 155, Salafi 7) with "
            "95% confidence via AI review.\n\n"
            "I am writing because our coverage is still incomplete. Bahrain's Ministry of "
            "Justice, Islamic Affairs and Endowments likely has a more comprehensive list "
            "that includes smaller musallas and community prayer halls. I would very much "
            "appreciate access to any additional mosque data the Ministry can share.\n\n"
            "I would also welcome a conversation about whether our global dataset — 378,573 "
            "mosques in 80+ countries — is useful to the Ministry for diaspora mapping or "
            "comparative research.\n\n"
            "I can be reached at charlesaprescott@outlook.com.\n\n"
            "With respect,\nCharles Prescott\nCreator, GRID\nJD/LLM (Taxation) · Trinity College\ncharlesaprescottjr@gmail.com"
        ),
    },

    {
        "org": "Embassy of Oman Washington DC — Cultural Affairs",
        "email": "consular@omaniembassy.org",
        "sector": "Government", "country": "OM", "mosques_in_grid": 873,
        "pitch_angle": "ibadi_unique",
        "subject": "GRID: 966 Omani mosques mapped — seeking MERA mosque registry",
        "body": (
            "To the Cultural Affairs Section,\n\n"
            "I direct the Global Religious Infrastructure Database (GRID). We have mapped "
            "966 mosques in Oman — the only systematically classified Ibadi mosque dataset "
            "in the world — alongside 378,573 globally.\n\n"
            "Oman's Ministry of Endowments and Religious Affairs (MERA) maintains the "
            "national mosque registry. I am writing to request access to this list — even "
            "a governorate-level summary would help us better represent Oman's unique Ibadi "
            "tradition in our global database.\n\n"
            "I would also be glad to discuss whether our dataset is useful to MERA's "
            "international outreach — particularly our mapping of Ibadi communities in "
            "East Africa (Zanzibar, Kenya, Tanzania).\n\n"
            "I can be reached at charlesaprescott@outlook.com.\n\n"
            "With respect,\nCharles Prescott\nCreator, GRID\nJD/LLM (Taxation) · Trinity College\ncharlesaprescottjr@gmail.com"
        ),
    },

    # ═══ TIER 3: HISTORIC ISLAMIC CENTERS ═══

    {
        "org": "Egyptian Embassy Washington DC — Religious Affairs",
        "email": "community@egyptembassy.net",
        "sector": "Government", "country": "EG", "mosques_in_grid": 2408,
        "pitch_angle": "al_azhar",
        "subject": "GRID: 2,600 Egyptian mosques mapped — seeking Awqaf mosque registry",
        "body": (
            "To the Religious Affairs Section,\n\n"
            "I direct the Global Religious Infrastructure Database (GRID). We have mapped "
            "2,648 mosques in Egypt and 378,573 globally across 80+ countries.\n\n"
            "Egypt's Ministry of Awqaf reportedly manages 130,000+ mosques and zawiyas — "
            "our 2,648 from open sources is a fraction of this. I am writing to request "
            "access to the Awqaf mosque registry. Even a governorate-level summary would "
            "dramatically improve our coverage and help us better represent Egypt's position "
            "as the historic center of Sunni Islam.\n\n"
            "I would also welcome a conversation about whether our global dataset — which "
            "maps Al-Azhar-affiliated mosques and Egyptian diaspora communities across "
            "Europe, North America, and the Gulf — is useful to the Ministry's work.\n\n"
            "I can be reached at charlesaprescott@outlook.com.\n\n"
            "With respect,\nCharles Prescott\nCreator, GRID\nJD/LLM (Taxation) · Trinity College\ncharlesaprescottjr@gmail.com"
        ),
    },

    {
        "org": "Embassy of Morocco Washington DC — Religious Affairs",
        "email": "consular@moroccanembassy.us",
        "sector": "Government", "country": "MA", "mosques_in_grid": 2472,
        "pitch_angle": "sufi_europe",
        "subject": "GRID: 2,700 Moroccan mosques mapped — seeking Habous registry",
        "body": (
            "To the Religious Affairs Section,\n\n"
            "I direct the Global Religious Infrastructure Database (GRID). We have mapped "
            "2,742 mosques in Morocco — the only country where Sufi is the dominant "
            "classified tradition — and 378,573 globally.\n\n"
            "Morocco's Ministry of Endowments and Islamic Affairs (Habous) reportedly "
            "oversees 50,000+ mosques. I am writing to request access to this registry — "
            "even a provincial summary would allow us to dramatically improve our coverage.\n\n"
            "I would also welcome a conversation about whether our global dataset — which "
            "uniquely traces the geographic distribution of Maliki fiqh and Sufi tariqas "
            "(Tijaniyya, Qadiriyya) across the Maghreb and into Moroccan diaspora communities "
            "in France, Belgium, the Netherlands, and Spain — is useful to the Ministry.\n\n"
            "I can be reached at charlesaprescott@outlook.com.\n\n"
            "With respect,\nCharles Prescott\nCreator, GRID\nJD/LLM (Taxation) · Trinity College\ncharlesaprescottjr@gmail.com"
        ),
    },

    {
        "org": "Embassy of Jordan Washington DC",
        "email": "consular@jordanembassyus.org",
        "sector": "Government", "country": "JO", "mosques_in_grid": 1190,
        "pitch_angle": "data_partner",
        "subject": "GRID: 1,290 Jordanian mosques from your open data — seeking more",
        "body": (
            "To the Embassy of Jordan,\n\n"
            "I direct the Global Religious Infrastructure Database (GRID). We have mapped "
            "1,288 mosques in Jordan — including 1,075 matched from Jordan's open data "
            "portal (opendata.gov.jo) via the Ministry of Awqaf and Islamic Affairs, "
            "complete with imam contact phone numbers where available.\n\n"
            "I am writing because our import covered 10 of 12 governorates. I would very "
            "much appreciate access to the remaining governorates' mosque data, as well "
            "as any registry of smaller musallas and zawiyas the Ministry maintains.\n\n"
            "I would also welcome a conversation about whether our global dataset — 378,573 "
            "mosques in 80+ countries — is useful to the Ministry for comparative research "
            "or diaspora engagement.\n\n"
            "I can be reached at charlesaprescott@outlook.com.\n\n"
            "With respect,\nCharles Prescott\nCreator, GRID\nJD/LLM (Taxation) · Trinity College\ncharlesaprescottjr@gmail.com"
        ),
    },

    {
        "org": "Embassy of Iraq Washington DC — Cultural Affairs",
        "email": "consular@iraqiembassy.us",
        "sector": "Government", "country": "IQ", "mosques_in_grid": 3335,
        "pitch_angle": "shia_sunni",
        "subject": "GRID: 4,700 Iraqi mosques mapped — seeking Sunni + Shia Endowment registries",
        "body": (
            "To the Cultural Affairs Section,\n\n"
            "I direct the Global Religious Infrastructure Database (GRID). We have mapped "
            "4,682 mosques in Iraq — with tradition-level classification distinguishing "
            "Twelver Shia shrines (Najaf, Karbala, Kadhimiya, Samarra) from Sunni mosques "
            "across all 18 governorates.\n\n"
            "Iraq's Sunni Endowment Diwan and Shia Endowment Diwan each maintain registries "
            "of the mosques under their authority. I am writing to request access to either "
            "or both lists — even governorate-level summaries would substantially improve "
            "our coverage and help us accurately represent Iraq's religious infrastructure.\n\n"
            "I would also welcome a discussion about whether our global dataset is useful "
            "for reconstruction planning, cultural heritage preservation, or Iraqi diaspora "
            "engagement.\n\n"
            "I can be reached at charlesaprescott@outlook.com.\n\n"
            "With respect,\nCharles Prescott\nCreator, GRID\nJD/LLM (Taxation) · Trinity College\ncharlesaprescottjr@gmail.com"
        ),
    },

    # ═══ TIER 4: SMALLER BUT IMPORTANT ═══

    {
        "org": "Embassy of Tunisia Washington DC",
        "email": "consular@tunisianembassy.org",
        "sector": "Government", "country": "TN", "mosques_in_grid": 1959,
        "pitch_angle": "maghreb",
        "subject": "GRID: 2,100 Tunisian mosques mapped — seeking Religious Affairs registry",
        "body": (
            "To the Embassy of Tunisia,\n\n"
            "I direct the Global Religious Infrastructure Database (GRID). We have mapped "
            "2,113 mosques in Tunisia and 378,573 globally across 80+ countries.\n\n"
            "Tunisia's Ministry of Religious Affairs oversees approximately 5,000 mosques. "
            "I am writing to request access to this registry — even a governorate-level "
            "summary would allow us to substantially improve our current 42% coverage.\n\n"
            "I would also welcome a conversation about whether our global dataset — which "
            "maps Tunisian diaspora mosque communities in France, Italy, and Canada — is "
            "useful to the Ministry.\n\n"
            "I can be reached at charlesaprescott@outlook.com.\n\n"
            "With respect,\nCharles Prescott\nCreator, GRID\nJD/LLM (Taxation) · Trinity College\ncharlesaprescottjr@gmail.com"
        ),
    },

    {
        "org": "Embassy of Libya Washington DC",
        "email": "consular@libyanembassy.org",
        "sector": "Government", "country": "LY", "mosques_in_grid": 2838,
        "pitch_angle": "reconstruction",
        "subject": "GRID: 3,100 Libyan mosques mapped — seeking Awqaf mosque registry",
        "body": (
            "To the Embassy of Libya,\n\n"
            "I direct the Global Religious Infrastructure Database (GRID). We have mapped "
            "3,118 mosques in Libya — with GPS coordinates and Maliki tradition classification "
            "across all regions.\n\n"
            "Libya's Awqaf authority maintains the national mosque registry. I am writing to "
            "request access to this list — even a regional summary would help us improve our "
            "coverage and support cultural heritage documentation.\n\n"
            "I would also welcome a discussion about whether our global dataset is useful for "
            "Libyan diaspora engagement or reconstruction planning.\n\n"
            "I can be reached at charlesaprescott@outlook.com.\n\n"
            "With respect,\nCharles Prescott\nCreator, GRID\nJD/LLM (Taxation) · Trinity College\ncharlesaprescottjr@gmail.com"
        ),
    },

    {
        "org": "Embassy of Sudan Washington DC",
        "email": "consular@sudanembassy.org",
        "sector": "Government", "country": "SD", "mosques_in_grid": 1312,
        "pitch_angle": "africa",
        "subject": "GRID: 1,700 Sudanese mosques mapped — seeking Religious Affairs registry",
        "body": (
            "To the Embassy of Sudan,\n\n"
            "I direct the Global Religious Infrastructure Database (GRID). We have mapped "
            "1,734 mosques in Sudan and 378,573 globally.\n\n"
            "Sudan's Ministry of Religious Affairs and Endowments maintains the national "
            "mosque registry. I am writing to request access to this list — even a state-level "
            "(wilayah) summary would improve our coverage and help document Sudan's unique "
            "Sufi mosque heritage (Qadiriyya, Shadhiliyya tariqas).\n\n"
            "I would also welcome a conversation about whether our global dataset is useful "
            "to the Ministry for diaspora engagement or interfaith work.\n\n"
            "I can be reached at charlesaprescott@outlook.com.\n\n"
            "With respect,\nCharles Prescott\nCreator, GRID\nJD/LLM (Taxation) · Trinity College\ncharlesaprescottjr@gmail.com"
        ),
    },

    {
        "org": "Nigerian Embassy Washington DC",
        "email": "consular@nigeriaembassyusa.org",
        "sector": "Government", "country": "NG", "mosques_in_grid": 2126,
        "pitch_angle": "africa_largest",
        "subject": "GRID: 2,600 Nigerian mosques mapped — seeking NSCIA mosque registry",
        "body": (
            "To the Embassy of Nigeria,\n\n"
            "I direct the Global Religious Infrastructure Database (GRID). We have mapped "
            "2,658 mosques in Nigeria — the largest mosque dataset in Sub-Saharan Africa — "
            "alongside 378,573 globally.\n\n"
            "Nigeria's Supreme Council for Islamic Affairs (NSCIA) and state-level Sharia "
            "commissions maintain mosque registries. I am writing to request access to any "
            "such list — even state-level summaries would allow us to significantly improve "
            "our coverage across all 36 states + FCT.\n\n"
            "I would also welcome a conversation about whether our global dataset — which "
            "maps Nigerian diaspora mosque communities in the UK (London, Manchester) and "
            "US (Houston, New York, Atlanta) — is useful to NSCIA's work.\n\n"
            "I can be reached at charlesaprescott@outlook.com.\n\n"
            "With respect,\nCharles Prescott\nCreator, GRID\nJD/LLM (Taxation) · Trinity College\ncharlesaprescottjr@gmail.com"
        ),
    },
]

json.dump(LEADS, open(OUT / "mena_embassy_leads.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

print(f"\n=== {len(LEADS)} MENA embassy leads (data-first pitch) ===")
for l in LEADS:
    has_data_ask = "request access" in l["body"] or "would like access" in l["body"] or "appreciate access" in l["body"]
    print(f"  {'✅' if has_data_ask else '❌'} {l['country']} | {l['mosques_in_grid']:,} mosques | {l['pitch_angle']} | {l['org'][:55]}")
print(f"\nSaved to {OUT / 'mena_embassy_leads.json'}")
