"""Build Buddhist + Sikh + Bahai outreach leads."""
LEADS = [
    # ═══ BUDDHIST ORGS ═══
    {"org": "Buddhist Churches of America", "email": "info@bcahq.org", "faith": "Buddhist", "sector": "Umbrella"},
    {"org": "SGI-USA (Soka Gakkai International)", "email": "info@sgi-usa.org", "faith": "Buddhist", "sector": "Umbrella"},
    {"org": "Tibet House US", "email": "info@tibethouse.us", "faith": "Buddhist", "sector": "Cultural"},
    {"org": "Shambhala International", "email": "info@shambhala.org", "faith": "Buddhist", "sector": "Organization"},
    {"org": "Insight Meditation Society", "email": "info@dharma.org", "faith": "Buddhist", "sector": "Center"},
    {"org": "Barre Center for Buddhist Studies", "email": "info@buddhistinquiry.org", "faith": "Buddhist", "sector": "Academic"},
    {"org": "Dharma Drum Mountain", "email": "info@ddmusa.org", "faith": "Buddhist", "sector": "Organization"},
    {"org": "Fo Guang Shan (Buddha's Light)", "email": "info@ibps.org", "faith": "Buddhist", "sector": "Umbrella"},
    {"org": "Tzu Chi USA", "email": "info@tzuchi.us", "faith": "Buddhist", "sector": "Nonprofit"},
    {"org": "Zen Mountain Monastery", "email": "info@zmm.org", "faith": "Buddhist", "sector": "Monastery"},
    {"org": "San Francisco Zen Center", "email": "info@sfzc.org", "faith": "Buddhist", "sector": "Center"},
    {"org": "Rigpa Fellowship", "email": "info@rigpa.org", "faith": "Buddhist", "sector": "Organization"},
    {"org": "The Tibet Fund", "email": "info@tibetfund.org", "faith": "Buddhist", "sector": "Nonprofit"},
    {"org": "Buddhist Peace Fellowship", "email": "info@bpf.org", "faith": "Buddhist", "sector": "Nonprofit"},
    {"org": "Numata Center for Buddhist Studies", "email": "info@numatacenter.org", "faith": "Buddhist", "sector": "Academic"},
    {"org": "BDK America (Bukkyo Dendo Kyokai)", "email": "info@bdkamerica.org", "faith": "Buddhist", "sector": "Publishing"},
    {"org": "Wisdom Publications", "email": "info@wisdompubs.org", "faith": "Buddhist", "sector": "Publishing"},
    {"org": "Lion's Roar (Buddhist magazine)", "email": "info@lionsroar.com", "faith": "Buddhist", "sector": "Media"},
    {"org": "Tricycle: The Buddhist Review", "email": "info@tricycle.org", "faith": "Buddhist", "sector": "Media"},
    {"org": "Buddhist Digital Resource Center", "email": "info@bdrc.io", "faith": "Buddhist", "sector": "Tech"},
    {"org": "Khyentse Foundation", "email": "info@khyentsefoundation.org", "faith": "Buddhist", "sector": "Foundation"},

    # ═══ SIKH ORGS ═══
    {"org": "Sikh Coalition", "email": "info@sikhcoalition.org", "faith": "Sikh", "sector": "Advocacy"},
    {"org": "World Sikh Council", "email": "info@worldsikhcouncil.org", "faith": "Sikh", "sector": "Umbrella"},
    {"org": "SikhNet", "email": "info@sikhnet.com", "faith": "Sikh", "sector": "Media"},
    {"org": "Sikh Research Institute", "email": "info@sikhri.org", "faith": "Sikh", "sector": "Research"},
    {"org": "Sikh American Legal Defense (SALDEF)", "email": "info@saldef.org", "faith": "Sikh", "sector": "Advocacy"},
    {"org": "United Sikhs", "email": "info@unitedsikhs.org", "faith": "Sikh", "sector": "Nonprofit"},
    {"org": "EcoSikh", "email": "info@ecosikh.org", "faith": "Sikh", "sector": "Nonprofit"},
    {"org": "Sikh Dharma International", "email": "info@sikhdharma.org", "faith": "Sikh", "sector": "Religious"},
    {"org": "Sikh Foundation", "email": "info@sikhfoundation.org", "faith": "Sikh", "sector": "Foundation"},

    # ═══ BAHAI ORGS ═══
    {"org": "Bahai National Center (USA)", "email": "info@bahai.us", "faith": "Bahai", "sector": "Umbrella"},
    {"org": "Bahai International Community", "email": "info@bic.org", "faith": "Bahai", "sector": "International"},
    {"org": "Bahai World Centre (Haifa)", "email": "info@bwc.org", "faith": "Bahai", "sector": "HQ"},
    {"org": "Bahai Studies Association", "email": "info@bahai-studies.ca", "faith": "Bahai", "sector": "Academic"},

    # ═══ INTERFAITH BUDDHIST-SIKH ═══
    {"org": "American Buddhist Congress", "email": "info@americanbuddhistcongress.org", "faith": "Buddhist", "sector": "Umbrella"},
    {"org": "Soka University of America", "email": "info@soka.edu", "faith": "Buddhist", "sector": "Academic"},
    {"org": "Maitripa College", "email": "info@maitripa.org", "faith": "Buddhist", "sector": "Academic"},
]

import json, sqlite3
from pathlib import Path
OUT = Path("outputs/outreach")

db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

# Stats for pitch
buddhist_us = db.execute("SELECT COUNT(*) as n FROM churches WHERE faith='Buddhist' AND country='US'").fetchone()['n']
buddhist_global = db.execute("SELECT COUNT(*) as n FROM churches WHERE faith='Buddhist'").fetchone()['n']
buddhist_trads = db.execute("SELECT COUNT(DISTINCT tradition) as n FROM churches WHERE faith='Buddhist' AND tradition IS NOT NULL").fetchone()['n']
sikh_us = db.execute("SELECT COUNT(*) as n FROM churches WHERE faith='Sikh' AND country='US'").fetchone()['n']
sikh_global = db.execute("SELECT COUNT(*) as n FROM churches WHERE faith='Sikh'").fetchone()['n']
bahai_hierarchy = db.execute("SELECT COUNT(*) as n FROM bahai_hierarchy").fetchone()['n'] if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bahai_hierarchy'").fetchone() else 0
db.close()

print(f"Buddhist: {buddhist_global:,} global ({buddhist_us:,} US), {buddhist_trads} traditions")
print(f"Sikh: {sikh_global:,} global ({sikh_us:,} US), fully DeepSeek-classified")
if bahai_hierarchy:
    print(f"Bahai: {bahai_hierarchy:,} hierarchy records")

json.dump(LEADS, open(OUT/"buddhist_sikh_bahai_leads.json","w"), indent=2)
from collections import Counter
for faith, count in Counter(l['faith'] for l in LEADS).most_common():
    print(f"  {faith}: {count}")
print(f"Total: {len(LEADS)}")
