"""
Generate press releases for GRID dataset — tailored to different outlet types.
Each press release highlights different angles of the data.
"""
import json
from pathlib import Path
from datetime import datetime

OUT = Path("outputs/outreach/press_releases")
OUT.mkdir(parents=True, exist_ok=True)

DATE = datetime.now().strftime("%B %d, %Y")

press_releases = {}

# ====== 1. Religion News Service / General Religion Press ======
press_releases["religion_wire"] = {
    "target": "Religion News Service, The Conversation (Religion), wire services",
    "file": "press_release_religion_wire.md",
    "content": f"""# PRESS RELEASE — FOR IMMEDIATE RELEASE
# World's Largest Religious Infrastructure Database Reaches 3.5M Sites: Every Faith, Every Country, Geocoded

**Contact:** Charles Prescott, Creator — GRID (Global Religious Infrastructure Database)
**Email:** charlesaprescott@outlook.com
**Date:** {DATE}

**Boston, MA** — GRID, the Global Religious Infrastructure Database, today announced it has mapped **3.5 million religious sites worldwide** — spanning every faith tradition across every country — making it the most comprehensive open-geography dataset of religious infrastructure ever assembled.

## By the Numbers

| Metric | Count |
|---|---|
| Total worship sites | 3,500,000+ |
| Faiths covered | 20+ (Christian, Islam, Buddhist, Hindu, Jewish, Sikh, Jain, Shinto, Taoist, Baháʼí, Ancient/Historical, Indigenous) |
| Countries | 240+ |
| US churches | 1,070,000+ |
| Email-contacted sites | 16,000+ (US) |
| Ancient sites (Pleiades) | 1,700+ (temples, sanctuaries, theaters, tombs) |

## What Makes GRID Unique

Unlike survey-based datasets that provide county-level aggregates every 10 years, GRID is:
- **Site-level**: Every church, mosque, temple, gurdwara, and shrine as a discrete geocoded point
- **Multi-faith**: Islam (357K), Buddhism (203K), Hinduism (202K), Judaism (23K), Sikh (5.6K), Jain (7.5K), Shinto (65K), and more — all classified with sub-tradition granularity
- **Continuously updated**: New imports weekly from denominational directories, government registries, and open data portals
- **Enriched**: Census demographics (US), FEMA risk data, USDA rural-urban codes, PPP loan data

## Recent Milestones

- **Jain classification 100% complete**: 7,530 Jain facilities classified (Digambar/Shwetambar/Sthanakvasi) with landmark types (temple, gurdwara, prayer hall, dharamshala, school, hospital) via AI-assisted review
- **Ancient religious sites**: 1,700+ temples, sanctuaries, theaters, and tombs from the Pleiades gazetteer — Roman, Hellenistic, Egyptian, Mesopotamian, and more — classified under a 24-node Pagan/Ancient taxonomy
- **Anglican Communion mapped**: 77,522 churches across 156 countries

## Availability

GRID is available for academic research via BigQuery (project: `american-rel-infra`, dataset: `American_Religious_Infrastructure`) and for individual scholars at $497/yr.

**Website**: GRID (contact for access)
**BigQuery**: `SELECT * FROM american-rel-infra.American_Religious_Infrastructure.churches`
"""
}

# ====== 2. Academic / Research Press ======
press_releases["academic"] = {
    "target": "The Chronicle of Higher Education, Nature, Science, academic societies (SSSR, ASR, ARDA)",
    "file": "press_release_academic.md",
    "content": f"""# PRESS RELEASE — FOR IMMEDIATE RELEASE
# New Database Maps 3.5M Religious Sites Worldwide — A Game Changer for Quantitative Sociology of Religion

**Contact:** Charles Prescott, Creator — GRID
**Email:** charlesaprescott@outlook.com
**Date:** {DATE}

**Boston, MA** — Researchers studying the spatial dynamics of religion now have access to an unprecedented resource: GRID (Global Religious Infrastructure Database), a site-level geocoded dataset of **3.5 million religious facilities** across all faiths and countries.

## Beyond Survey Data

Traditional datasets like the US Religion Census provide county-level aggregates once a decade. GRID changes the paradigm:
- **Site-level granularity**: Analyze religious infrastructure at the address, census tract, county, or country level
- **Multi-faith taxonomy**: 1,066 tradition nodes across a 5-level FLTD hierarchy (Faith-Legacy-Tradition-Movement-Denomination)
- **Temporal depth**: Multiple import cycles showing organizational change (e.g., SBC declined 22% in adherents from 2010→2020)
- **Cross-sectional enrichment**: FEMA hazard risk, ACS demographics, USDA RUCC codes, SBA loan data — all JOINable at the site level

## Research Applications

- Spatial clustering of religious sites by denomination
- Religious infrastructure and community resilience (FEMA risk data joined)
- Faith diaspora mapping (every mosque in every country)
- Historical religious geography (1,700+ ancient sites from Pleiades)
- Congregation density vs. census demographics

## Data Access

Available via BigQuery for computational access. Scholar licenses at $497/yr.

**BigQuery dataset**: `american-rel-infra.American_Religious_Infrastructure`
**Demo view**: `demo_vt_churches` — Vermont churches with census + FEMA data
"""
}

# ====== 3. Data Journalism / Media Press ======
press_releases["data_journalism"] = {
    "target": "Nieman Lab, GIJN, Reuters Institute, data journalism desks at BBC/Guardian/NYT",
    "file": "press_release_data_journalism.md",
    "content": f"""# PRESS RELEASE — FOR IMMEDIATE RELEASE
# The World's Religious Infrastructure, Now Queryable: 3.5M Sites for Data Journalists

**Contact:** Charles Prescott, Creator — GRID
**Email:** charlesaprescott@outlook.com
**Date:** {DATE}

**Boston, MA** — Data journalists covering religion now have a resource that until recently didn't exist: a complete, geocoded map of the world's religious infrastructure.

GRID (Global Religious Infrastructure Database) lets any journalist with basic SQL answer questions like:
- *Which US counties have the most churches per capita?*
- *How does mosque density correlate with Muslim population in European cities?*
- *Where are the last functioning ancient temples in the Mediterranean?*
- *What's the religious infrastructure of any country — in a single query?*

## Query Examples

**Every mosque in Germany** (6,707):
```sql
SELECT COUNT(*) FROM churches WHERE faith='Islam' AND country='DE'
```

**Buddhist temples by country** (top 5: Japan 60K, Thailand 39K, China 27K, Myanmar 10K, Sri Lanka 10K):
```sql
SELECT country, COUNT(*) FROM churches WHERE faith='Buddhist' GROUP BY country ORDER BY COUNT(*) DESC
```

**The dataset includes**: 3.5M sites, 240+ countries, 1,066 traditions, census demographics, FEMA risk data, and ancient/historical sites.

**Access**: BigQuery public dataset. Scholar/journalist licenses at $497/yr.
"""
}

# ====== 4. Faith Media / Denominational Press ======
press_releases["faith_media"] = {
    "target": "Christianity Today, Sojourners, Religion Unplugged, faith news desks",
    "file": "press_release_faith_media.md",
    "content": f"""# PRESS RELEASE — FOR IMMEDIATE RELEASE
# Global Religious Infrastructure Database Reaches 3.5M Sites — Including 1M+ US Churches

**Contact:** Charles Prescott, Creator — GRID
**Email:** charlesaprescott@outlook.com
**Date:** {DATE}

**Boston, MA** — GRID, a project to map every religious facility on Earth, now catalogs **3.5 million sites** including every Christian denomination across 240+ countries.

## US Church Coverage

| Denomination | Sites |
|---|---|
| Catholic | 148,000+ |
| Baptist (all conventions) | 101,000+ |
| Methodist | 49,000+ |
| Lutheran (ELCA/LCMS/WELS) | 57,000+ |
| Pentecostal | 42,000+ |
| Anglican/Episcopal | 77,000+ (worldwide) |
| LDS/Mormon | 19,400+ (meetinghouses + temples) |
| Jehovah's Witnesses | 10,600+ (Kingdom Halls) |
| Orthodox | 99,000+ (worldwide) |

## Beyond Christianity

GRID covers all faiths equally: Islam (357K), Buddhism (203K), Hinduism (202K), Judaism (23K), Sikh (5.6K), Jain (7.5K), Shinto (65K), Baháʼí (1.7K), and indigenous/traditional religions.

All sites are geocoded with enrichment data including census demographics and FEMA risk profiles.
"""
}

# Write all press releases
for key, pr in press_releases.items():
    path = OUT / pr["file"]
    path.write_text(pr["content"], encoding="utf-8")
    print(f"✅ {pr['file']} — for {pr['target']}")

print(f"\n{'='*60}")
print(f"4 press releases generated in {OUT}")
print(f"{'='*60}")
