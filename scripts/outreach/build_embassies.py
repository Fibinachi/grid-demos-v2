"""Embassy outreach — every embassy has diaspora/community officers who need this data."""
import json
from pathlib import Path
OUT = Path("outputs/outreach")

EMBASSIES = [
    # ═══ CHINA — biggest diaspora: 796 folk shrines in THA alone ═══
    {"org": "Chinese Embassy Bangkok - Cultural Section", "email": "culture@chinaembassy.or.th", "faith": "Chinese Folk", "target": "Bangkok"},
    {"org": "Chinese Embassy Bangkok - Consular Affairs", "email": "consul@chinaembassy.or.th", "faith": "Chinese Folk", "target": "Bangkok"},
    {"org": "Chinese Embassy Kuala Lumpur", "email": "chinaemb_my@mfa.gov.cn", "faith": "Chinese Folk", "target": "Kuala Lumpur"},
    {"org": "Chinese Embassy Vientiane (Laos)", "email": "chinaemb_la@mfa.gov.cn", "faith": "Chinese Folk", "target": "Vientiane"},
    {"org": "Chinese Embassy Phnom Penh (Cambodia)", "email": "chinaemb_kh@mfa.gov.cn", "faith": "Chinese Folk", "target": "Phnom Penh"},
    {"org": "Chinese Embassy Hanoi", "email": "chinaemb_vn@mfa.gov.cn", "faith": "Chinese Folk", "target": "Hanoi"},
    {"org": "Chinese Embassy Yangon (Myanmar)", "email": "chinaemb_mm@mfa.gov.cn", "faith": "Chinese Folk", "target": "Yangon"},

    # ═══ INDIA — 5,242 temples in US alone ═══
    {"org": "Indian Embassy Washington DC - Community Affairs", "email": "community@indianembassy.org", "faith": "Hindu", "target": "Washington DC"},
    {"org": "Indian Consulate New York", "email": "consul.newyork@mea.gov.in", "faith": "Hindu", "target": "New York"},
    {"org": "Indian Consulate San Francisco", "email": "consul.sanfrancisco@mea.gov.in", "faith": "Hindu", "target": "San Francisco"},
    {"org": "Indian Consulate Chicago", "email": "consul.chicago@mea.gov.in", "faith": "Hindu", "target": "Chicago"},
    {"org": "Indian Consulate Houston", "email": "consul.houston@mea.gov.in", "faith": "Hindu", "target": "Houston"},
    {"org": "Indian High Commission London", "email": "hccommunity@hcilondon.gov.in", "faith": "Hindu", "target": "London"},
    {"org": "Indian Embassy Ottawa", "email": "community@indianembassyottawa.gov.in", "faith": "Hindu", "target": "Ottawa"},
    {"org": "Indian Embassy Kuala Lumpur", "email": "community@hcikl.gov.in", "faith": "Hindu", "target": "Kuala Lumpur"},

    # ═══ TURKIYE — 2,869 mosques in DE ═══
    {"org": "Turkish Embassy Berlin - Religious Affairs", "email": "berlin@mfa.gov.tr", "faith": "Islam", "target": "Berlin"},
    {"org": "Turkish Consulate Frankfurt", "email": "frankfurt@mfa.gov.tr", "faith": "Islam", "target": "Frankfurt"},
    {"org": "Turkish Consulate Munich", "email": "munchen@mfa.gov.tr", "faith": "Islam", "target": "Munich"},
    {"org": "Turkish Consulate Stuttgart", "email": "stuttgart@mfa.gov.tr", "faith": "Islam", "target": "Stuttgart"},
    {"org": "Turkish Consulate Cologne", "email": "koln@mfa.gov.tr", "faith": "Islam", "target": "Cologne"},
    {"org": "Turkish Embassy London - Community", "email": "london@mfa.gov.tr", "faith": "Islam", "target": "London"},
    {"org": "Turkish Embassy Paris - Community", "email": "paris@mfa.gov.tr", "faith": "Islam", "target": "Paris"},
    {"org": "Turkish Embassy The Hague", "email": "thehague@mfa.gov.tr", "faith": "Islam", "target": "The Hague"},
    {"org": "Turkish Embassy Vienna - Community", "email": "vienna@mfa.gov.tr", "faith": "Islam", "target": "Vienna"},

    # ═══ THAILAND — 906 Buddhist temples in US ═══
    {"org": "Royal Thai Embassy Washington DC", "email": "thaidelawashington@thaiembdc.org", "faith": "Buddhist", "target": "Washington DC"},
    {"org": "Royal Thai Consulate Los Angeles", "email": "thaigenla@thaiemmbsyla.org", "faith": "Buddhist", "target": "Los Angeles"},
    {"org": "Royal Thai Consulate New York", "email": "thaigennewyork@thaiembassynyc.org", "faith": "Buddhist", "target": "New York"},
    {"org": "Royal Thai Embassy London", "email": "thaidelondon@thaiembassylondon.org.uk", "faith": "Buddhist", "target": "London"},

    # ═══ VIETNAM — 409 temples in US ═══
    {"org": "Vietnamese Embassy Washington DC", "email": "vnembassyus@mofa.gov.vn", "faith": "Buddhist", "target": "Washington DC"},
    {"org": "Vietnamese Consulate San Francisco", "email": "vnsanfran@mofa.gov.vn", "faith": "Buddhist", "target": "San Francisco"},
    {"org": "Vietnamese Consulate Houston", "email": "vnconsulatehouston@mofa.gov.vn", "faith": "Buddhist", "target": "Houston"},

    # ═══ PAKISTAN — global diaspora ═══
    {"org": "Pakistani Embassy Washington DC - Community", "email": "community@pakistanembassy.org", "faith": "Islam", "target": "Washington DC"},
    {"org": "Pakistani Consulate New York", "email": "consul.newyork@pakistanembassy.org", "faith": "Islam", "target": "New York"},
    {"org": "Pakistani Embassy London", "email": "phclondon@phclondon.org", "faith": "Islam", "target": "London"},

    # ═══ INDONESIA — 101K mosques, global diaspora ═══
    {"org": "Indonesian Embassy Washington DC - Community", "email": "community@kemlu.go.id", "faith": "Islam", "target": "Washington DC"},
    {"org": "Indonesian Consulate Los Angeles", "email": "consul.losangeles@kemlu.go.id", "faith": "Islam", "target": "Los Angeles"},

    # ═══ BANGLADESH — global diaspora ═══
    {"org": "Bangladesh Embassy Washington DC", "email": "consular@bdelasdc.org", "faith": "Islam", "target": "Washington DC"},
    {"org": "Bangladesh High Commission London", "email": "community@bhclondon.org.uk", "faith": "Islam", "target": "London"},

    # ═══ SRI LANKA — Buddhist diaspora ═══
    {"org": "Sri Lankan Embassy Washington DC", "email": "consular@embassyofsrilanka.org", "faith": "Buddhist", "target": "Washington DC"},
    {"org": "Sri Lankan Embassy London", "email": "consular@slhc-london.co.uk", "faith": "Buddhist", "target": "London"},

    # ═══ KOREA — Korean Christian diaspora ═══
    {"org": "Korean Embassy Washington DC - Community", "email": "community@koreaembassy.org", "faith": "Christian", "target": "Washington DC"},
    {"org": "Korean Consulate Los Angeles", "email": "consul.losangeles@mofa.go.kr", "faith": "Christian", "target": "Los Angeles"},
    {"org": "Korean Consulate New York", "email": "consul.newyork@mofa.go.kr", "faith": "Christian", "target": "New York"},

    # ═══ PHILIPPINES — OFW religious communities ═══
    {"org": "Philippine Embassy Washington DC - Migrant Affairs", "email": "migrant@philippineembassy.org", "faith": "Christian", "target": "Washington DC"},
    {"org": "Philippine Consulate Los Angeles", "email": "consul.losangeles@philippineconsulatela.org", "faith": "Christian", "target": "Los Angeles"},
    {"org": "Philippine Embassy London", "email": "consular@philemb.co.uk", "faith": "Christian", "target": "London"},

    # ═══ NIGERIA — African Christian diaspora ═══
    {"org": "Nigerian Embassy Washington DC", "email": "consular@nigeriaembassyusa.org", "faith": "Christian", "target": "Washington DC"},
    {"org": "Nigerian High Commission London", "email": "consular@nigeriahc.org.uk", "faith": "Christian", "target": "London"},

    # ═══ ETHIOPIA — Ethiopian Orthodox diaspora ═══
    {"org": "Ethiopian Embassy Washington DC", "email": "consular@ethiopianembassy.org", "faith": "Christian", "target": "Washington DC"},
    {"org": "Ethiopian Embassy London", "email": "consular@ethioembassy.org.uk", "faith": "Christian", "target": "London"},

    # ═══ MOROCCO — Moroccan mosques in Europe ═══
    {"org": "Moroccan Embassy Paris - Community", "email": "consulat@amb-maroc.fr", "faith": "Islam", "target": "Paris"},
    {"org": "Moroccan Consulate Brussels", "email": "consul@moroccanconsulate.be", "faith": "Islam", "target": "Brussels"},
    {"org": "Moroccan Embassy The Hague", "email": "consul@marokko.nl", "faith": "Islam", "target": "The Hague"},

    # ═══ EGYPT — Coptic + Muslim diaspora ═══
    {"org": "Egyptian Embassy Washington DC - Community", "email": "community@egyptembassy.net", "faith": "Islam", "target": "Washington DC"},
    {"org": "Egyptian Consulate New York", "email": "consul.newyork@egyptconsulate.com", "faith": "Islam", "target": "New York"},

    # ═══ IRAN — Shia diaspora mapping ═══
    {"org": "Iranian Interests Section Washington DC", "email": "consular@daftar.org", "faith": "Islam", "target": "Washington DC"},
    {"org": "Iranian Embassy London", "email": "consular@iranembassyuk.org", "faith": "Islam", "target": "London"},
]

json.dump(EMBASSIES, open(OUT/"embassy_leads.json","w"), indent=2)
from collections import Counter
print(f"Embassy leads: {len(EMBASSIES)}")
for c, n in Counter(e['target'].split(',')[0].strip() for e in EMBASSIES).most_common():
    print(f"  {c}: {n}")
for f, n in Counter(e['faith'] for e in EMBASSIES).most_common():
    print(f"  Faith {f}: {n}")
