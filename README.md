# GRID — Global Religious Infrastructure Database

> **Canada & India Public Release — A geocoded census of 292,785 religious sites across two of the world's most religiously diverse democracies. Fully FAIR-compliant (Findable, Accessible, Interoperable, Reusable) under CC BY 4.0.**

[![Records](https://img.shields.io/badge/published%20records-292%2C785-green)](#) [![Countries](https://img.shields.io/badge/countries-2-orange)](#) [![Coordinates](https://img.shields.io/badge/coordinates-98.3%25-blue)](#) [![License](https://img.shields.io/badge/license-CC%20BY%204.0-lightgrey)](#license)

---

## Overview

GRID is an open census of religious infrastructure, assembled from Wikidata, OpenStreetMap, Overture Maps, government databases, and web scraping. **This public release covers Canada and India** — two nations chosen for their exceptional religious diversity and complementary geographic coverage. The full database (~3.29M records across 290 countries) remains in development; the Canada and India subsets are published under CC BY 4.0 with full provenance tracking.

### ⚠️ Important Coverage Caveat

**Canada's 66,912 records are a near-complete census**, benefiting from the authoritative Canada Revenue Agency charity register (31,833 records), comprehensive OSM coverage, and HERE-geocoded addresses. Coverage is estimated at >90% of all religious buildings.

**India's 225,873 records are a substantial undercount.** We estimate India's true total at approximately **4.8 million** worship sites based on a clergy-ratio model grounded in the economics of religious labor:

> A full-time religious professional (priest, imam, pastor, granthi, pujari) requires financial support from approximately three families with sufficient disposable wealth. Sustaining three such families requires a broader community of roughly **300 people**. This yields a **1:300 clergy-to-population ratio**. Applied to India's ~1.45 billion population: **~4.8 million worship sites**.

Our 225,873 records represent approximately **4.7%** of this total. The current data derive from:

- Wikidata SPARQL (163,525 records) — biased toward listed/notable sites with Wikipedia articles
- OpenStreetMap (57,392 records) — sparse in rural areas, community-mapped in urban centers
- Tamil Nadu heritage register (4,915 records) — one state only

The India dataset is best understood as a **4.7% sampling frame of digitally documented, mapped religious infrastructure** — not a complete census.

#### Planned: Tract-Level Gap Analysis

To move from aggregate estimates to spatially precise undercount identification, we plan to overlay the existing sites onto India census tracts and compute actual sites-per-capita per tract. Tracts where the ratio falls substantially below 1:300 will be flagged as "cold spots" — regions where undocumented worship sites are most likely to be found. This transforms the completeness estimate into a **spatially falsifiable hypothesis** and enables prioritized data collection in the highest-gap regions.

**Key metrics for this release (June 2026):**

| Metric | Canada | India | **Combined** |
|--------|--------|-------|-------------|
| Religious sites | **66,912** | **225,873** | **292,785** |
| Estimated completeness | >90% | ~4.7% | — |
| Estimated true total | ~75K | ~4.8M | — |
| Coordinate coverage | 100.0% | 97.8% | **98.3%** |
| Faith traditions | 10 | 9 | **12** |
| Primary sources | CRA charities, OSM, Overture | Wikidata, OSM, Tamil Heritage | Multi-source |
## The CFTLM Taxonomy

GRID uses a hierarchical **Civilization → Faith → Tradition → Legacy → Movement (CFTLM)** taxonomy with 604 nodes. Every record is classified to a specific leaf node. While the taxonomy spans all world religions, the Canada & India public release focuses on faiths with significant presence in those countries.

### Faith Traditions Represented in Canada & India

| Faith | Canada Presence | India Presence | Key Traditions Classified |
|-------|----------------|----------------|--------------------------|
| **Christian** | ✅ Majority (~75%) | ✅ Minority (~3%) | Catholic, Anglican, United Church, Baptist, Orthodox, Pentecostal, Lutheran, Presbyterian |
| **Hindu** | ✅ Growing (~3%) | ✅ Majority (~80%) | Vaishnavism, Shaivism, Shaktism, Smartism, Swaminarayan, ISKCON |
| **Islam** | ✅ Significant (~5%) | ✅ Major minority (~14%) | Sunni (Hanafi, Shafii, Salafi, Sufi, Deobandi), Shia (Twelver, Ismaili, Bohra), Ahmadiyya |
| **Sikh** | ✅ Significant (~5%) | ✅ Minority (~2%) | Khalsa, Singh Sabha, Nanaksar, Ravidassia, Ramgarhia |
| **Buddhist** | ✅ Present (~4%) | ✅ Minority (~0.7%) | Mahayana (Zen, Pure Land, Tibetan), Theravada (Thai Forest, Vipassana), Vajrayana |
| **Jewish** | ✅ Present (~2%) | ✅ Historical | Orthodox (Chabad, Yeshiva, Hasidic), Conservative, Reform, Sephardic |
| **Jain** | ✅ Present | ✅ Minority (~0.3%) | Digambara, Svetambara |
| **Indigenous/Traditional** | ✅ First Nations | ✅ | Traditional African, Australian Aboriginal |
| **Baháʼí** | ✅ Present | ✅ Present | Baháʼí, Local Spiritual Assembly |
| **Zoroastrian** | ✅ Parsi diaspora | ✅ Parsi community | Zoroastrian |
| **Other** | ✅ | ✅ | Chinese Folk, Caodaism, New Age, Spiritualist |

### Classification Quality (Canada & India)

| Faith | Classification Method | Confidence |
|-------|----------------------|------------|
| **Christian** — Canada | CRA charity data + name heuristics + IRS NTEE cross-reference | 0.85–0.95 |
| **Christian** — India | Name heuristics + country priors + DeepSeek AI verification | 0.70–0.85 |
| **Muslim** — both | Country-based geo-priors + name heuristics (17 traditions) | 0.85–0.95 |
| **Hindu** — India | Country priors (India default) + name heuristics | 0.80–0.90 |
| **Sikh** — both | Name heuristics + DeepSeek AI scan (global, 5,619 entries) | 0.85–0.95 |
| **Buddhist** — both | Name heuristics + country priors | 0.70–0.85 |
| **Jewish** — both | Worldwide DeepSeek audit (23,451 entries, 6 regions) | 0.95 |

See `taxonomy_completeness.txt` for the full 604-node CFTLM tree with completeness statistics.
## Database Schema

The canonical database is `E:\grid\churches.db` (~14.4 GB, SQLite 3.49+, WAL mode, integrity verified). For the public release, filter by `country IN ('CA', 'IN')`. See `docs/SCHEMA.md` for the complete schema documentation.

### Core Tables (Public-Relevant)

| Table | Rows | Description |
|-------|------|-------------|
| `churches` | 3.29M | Main table — filter `WHERE country IN ('CA','IN')` for public subset (292,785) |
| `taxonomy` | 604 | CFTLM tree nodes with `id`, `parent_id`, `name`, `level` |
| `provenance_log` | 720+ | Every data operation timestamped with source, script, counts, status |
| `enrichment_change_log` | 211K+ | Per-field change tracking (old→new values, church_id, source) |
| `church_contact_values` | 463K | Normalized contact storage (phone/email/website/social) by type |

### Key `churches` Columns (Public Subset)

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `name` | TEXT | Canonical name |
| `taxonomy_id` | INTEGER | FK → `taxonomy.id` (CFTLM classification) |
| `faith` | TEXT | Top-level faith (Christian, Islam, Hindu, Buddhist, etc.) |
| `tradition` | TEXT | Sub-faith tradition (Catholic, Sunni, Zen, Vaishnavism, etc.) |
| `denomination` | TEXT | Specific body (United Church of Canada, Catholic, ISKCON, etc.) |
| `landmark_type` | TEXT | Building type (church, cathedral, mosque, temple, gurdwara, etc.) |
| `latitude`, `longitude` | REAL | WGS84 decimal coordinates |
| `city`, `state`, `country` | TEXT | Geographic hierarchy (state = province/state code) |
| `website`, `phone`, `email` | TEXT | Contact information |
| `confidence_score` | REAL | 0.0–1.0 overall data quality confidence |
| `source` | TEXT | Data provenance (cra_2018, osm_import, holy_sites_import, etc.) |
| `wikidata_qid` | TEXT | Wikidata entity ID for cross-validation |
| `diocese` | TEXT | Ecclesiastical jurisdiction |
| `tradition_confidence` | REAL | Faith-specific confidence score |
| `tradition_source` | TEXT | How the tradition was classified (deepseek, heuristic, etc.) |

### Canada Sources

| Source | Records | Description |
|--------|---------|-------------|
| `cra_2018` | 26,592 | Canada Revenue Agency registered charities (2018) |
| `osm_import` | 15,506 | OpenStreetMap religious building import |
| `overture_full` | 13,727 | Overture Maps global places with religious categories |
| `cra_2011` | 5,241 | Canada Revenue Agency registered charities (2011) |
| `holy_sites_import` | 4,038 | Wikidata SPARQL + cross-referencing |
| Other | 1,808 | GCatholic, Masstimes, denominational scrapers |

### India Sources

| Source | Records | Description |
|--------|---------|-------------|
| `holy_sites_import` | 163,525 | Wikidata SPARQL (28 building types, all faiths) |
| `osm_import` | 37,944 | OpenStreetMap religious building import |
| `csv_import_india_osm` | 19,448 | Additional OSM religious feature extraction |
| `tamil_nadu_heritage_pdf` | 4,915 | Tamil Nadu heritage temple import |

## Quick Queries

```sql
-- All Canada religious sites
SELECT id, name, faith, tradition, landmark_type, latitude, longitude, city, state
FROM churches WHERE country = 'CA';

-- All India religious sites
SELECT id, name, faith, tradition, landmark_type, latitude, longitude, city, state
FROM churches WHERE country = 'IN';

-- Canada: faith breakdown
SELECT faith, COUNT(*) FROM churches WHERE country = 'CA' GROUP BY faith ORDER BY COUNT(*) DESC;

-- India: top 10 states by religious sites
SELECT state, COUNT(*) FROM churches WHERE country = 'IN' GROUP BY state ORDER BY COUNT(*) DESC LIMIT 10;

-- Sikh gurdwaras in Canada
SELECT * FROM churches WHERE country = 'CA' AND faith = 'Sikh' AND landmark_type = 'gurdwara';

-- Hindu temples in India with coordinates
SELECT name, city, state, latitude, longitude FROM churches
WHERE country = 'IN' AND faith = 'Hindu' AND latitude IS NOT NULL;

-- Canada CRA-enriched records with charity numbers
SELECT name, city, source FROM churches WHERE country = 'CA' AND source LIKE 'cra_%';
```
## Project Architecture

```raw
grid/
├── gw_db/                 # Provenance-aware database access layer
│   └── __init__.py        # connect(), Provenance context manager, log_change()
├── gw_filters/             # Centralized filtering & classification
│   ├── faith.py           # Name-based + NTEE faith classification
│   └── clean.py           # Text/phone/domain/ZIP normalization
├── gw_geo/                 # Centralized geocoding & spatial analysis
│   ├── census.py          # US Census geocoder (3 tiers, free)
│   └── here.py            # HERE.com geocoding
├── scripts/
│   ├── classification/    # Faith/denomination classification (DeepSeek, heuristics, priors)
│   ├── enrichment/         # CRA charities, geocoding, contacts, property imports
│   ├── import/             # Bulk data ingestion (Wikidata, OSM, Overture, CKAN)
│   ├── scrapers/           # Denomination-specific web scrapers
│   └── db_maintenance/     # Schema migration, hierarchy building, cleanup
├── data/                   # Reference data, shapefiles, scraped CSVs
├── docs/                   # Documentation & paper drafts
└── outputs/                # Generated maps, reports, visualizations
```

### Core Module: `gw_db` — Provenance-Aware Database Access

Every script that touches `churches.db` imports from here. Provides automatic provenance logging.

```python
from gw_db import connect, Provenance, log_change

db = connect()  # WAL mode, 30s timeout, auto-finds churches.db

# Automatic provenance logging
with Provenance(db, "my_script.py", source="cra_charities",
                action="enriched", fields="cra_bn,charity_status"):
    # ... batch operations ...
    pass  # provenance_log INSERT on exit

# Per-change tracking
log_change(db, church_id=12345, field="tradition",
           old_value="Other", new_value="Catholic", source="cra_classification")
```

### Core Module: `gw_filters` — Classification & Filtering

```python
from gw_filters import faith, clean

faith.from_name("Gurdwara Sahib Ottawa")        # → "sikh"
faith.from_name("ISKCON Temple Toronto")         # → "hindu"
faith.from_name("Basilica of Our Lady of Montreal") # → "christian"
clean.clean_church_name("St. Mary's Parish (Inc.)") # → "St. Mary's Parish"
```

### Core Module: `gw_geo` — Geocoding

```python
from gw_geo import census, here

# For Canada: HERE geocoding (30K/month)
lat, lng, addr, score = here.geocode("Notre-Dame Basilica, Montréal, QC")

# For India: Nominatim (self-hosted Docker)
# See scripts/start_nominatim.sh
```

### Canada Data Pipeline

```raw
CRA Charities DB → scrape/download → classify via DeepSeek + name heuristics
    → geocode via HERE → match to existing churches by name+city
    → merge into churches table with cra_bn enrichment
```

### India Data Pipeline

```raw
Wikidata SPARQL (28 building types) + Overture Maps (16 religious categories)
    → country filter IN → classify by name heuristics + country priors
    → Hindu temple subtype detection → Muslim tradition classification
    → merge into churches table
```
## Data Sources — Canada

| Source | Records | Description | License |
|--------|---------|-------------|---------|
| Canada Revenue Agency | ~10K | Registered charities with BN, address, charitable purpose | Open Government Licence |
| Wikidata SPARQL | ~30K | All 28 religious building types with P140 (religion) | CC0 |
| Overture Maps | ~50K | 16 religious categories with coordinates | CDLA Permissive v2.0 |
| Wikipedia lists | ~1K | Cathedrals, basilicas, heritage churches | CC BY-SA |
| Denominational scrapers | ~2K | United Church, Anglican, Catholic directories | Various |
| HERE geocoding | — | Street-level geocoding for CRA addresses | Proprietary (enrichment only) |

## Data Sources — India

| Source | Records | Description | License |
|--------|---------|-------------|---------|
| Wikidata SPARQL | ~50K | Hindu temples, mosques, churches, gurdwaras | CC0 |
| Overture Maps | ~150K | 16 religious categories | CDLA Permissive v2.0 |
| Wikipedia lists | ~5K | Largest Hindu temples, cathedrals, mosques | CC BY-SA |
| Tamil Heritage Sites | ~1K | Imported historical temples | Various |
| Geofabrik/OSM extracts | — | Nominatim reverse geocoding (planned) | ODbL |

## Classification Pipeline — Canada

### Faith Classification
1. **CRA charity data**: Religious designation from charity registration
2. **Name-based heuristics**: Pattern matching on church/mosque/synagogue/temple/gurdwara keywords
3. **Wikidata P140**: Religion property when available
4. **DeepSeek AI**: Ireland-style classification for ambiguous entries (planned)

### Tradition & Denomination
- **Christian**: United Church of Canada, Anglican Church of Canada, Catholic (Latin Rite + Ukrainian Catholic), Presbyterian, Lutheran, Baptist, Orthodox (Greek, Russian, Ukrainian, Serbian)
- **Muslim**: Sunni majority with Shia (Twelver, Ismaili) and Ahmadiyya minorities
- **Sikh**: 100% DeepSeek-verified globally, gurdwara classification
- **Jewish**: Orthodox (Chabad), Conservative, Reform — worldwide DeepSeek audit applied

## Classification Pipeline — India

### Faith Classification
1. **Country-based priors**: India default = Hindu (with strong Muslim/Christian/Sikh/Jain/Buddhist minorities)
2. **Name-based heuristics**: mandir/mosque/masjid/church/gurdwara/jain keywords
3. **Wikidata P140**: Religion property when available
4. **Language detection**: Hindi, Tamil, Telugu, Malayalam, Bengali, Marathi, Gujarati name patterns

### Tradition & Denomination
- **Hindu**: Vaishnavism (incl. ISKCON, Swaminarayan), Shaivism, Shaktism, Smartism — 188K total records
- **Muslim**: 17 traditions (Sunni: Hanafi/Shafii/Salafi/Deobandi/Sufi; Shia: Twelver/Ismaili/Bohra)
- **Christian**: Catholic (Latin Rite + Syro-Malabar/Syro-Malankara), Church of South India, Church of North India, Orthodox (Malankara, Syriac)
- **Sikh**: Khalsa, Singh Sabha, Nanaksar, Ravidassia, Ramgarhia — DeepSeek-verified
- **Jain**: Digambara, Svetambara
- **Buddhist**: Theravada (Sri Lankan lineage), Mahayana (Tibetan, Zen), Vajrayana

## FAIR Compliance

GRID Canada & India is published under **CC BY 4.0** and designed for FAIR principles:

| Principle | Implementation |
|-----------|---------------|
| **Findable** | DOI (pending), GitHub repository, Google BigQuery public dataset (planned), Zenodo archive (planned) |
| **Accessible** | SQLite download, CSV/GeoJSON export scripts, BigQuery SQL interface, no authentication required |
| **Interoperable** | WGS84 coordinates, ISO 3166-1 country codes, Wikidata QID cross-references, CFTLM taxonomy with persistent IDs, SQLite (universal format) |
| **Reusable** | CC BY 4.0 license, full provenance tracking (720+ operations logged), field-level change history (211K+ entries), confidence scores per record, data dictionary documentation |

### Data Access Methods

```bash
# Method 1: Full SQLite download (recommended for research)
# ~150 MB filtered to CA+IN only
python scripts/db_maintenance/export_public_subset.py --countries CA,IN --format sqlite

# Method 2: CSV/GeoJSON export
python scripts/db_maintenance/export_public_subset.py --countries CA,IN --format csv
python scripts/db_maintenance/export_public_subset.py --countries CA,IN --format geojson

# Method 3: BigQuery (planned)
# SELECT * FROM `project.dataset.churches` WHERE country IN ('CA', 'IN')
```

### Provenance & Reproducibility

Every record in the public subset carries full provenance:
- `source`: Original data source (wikidata, overture, cra_charities, scraper, etc.)
- `wikidata_qid`: Wikidata entity ID for cross-validation
- `confidence_score`: 0.0–1.0 overall quality indicator
- `tradition_confidence`: Faith-specific classification confidence
- `tradition_source`: How tradition was determined

All enrichment scripts are in `scripts/enrichment/` and are idempotent. The `provenance_log` table records every operation with timestamps and outcome status.

```bash
# Environment
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Verify database integrity
python scripts/db_maintenance/enrichment_status.py

# Export public subset
python scripts/db_maintenance/export_public_subset.py --countries CA,IN --format sqlite
```

## Key Achievements (Relevant to Public Release)

- **Canada CRA charities**: ~10K registered religious charities classified and linked
- **100% Sikh DeepSeek-reviewed**: 5,619 global entries — Canadian and Indian gurdwaras verified
- **Worldwide Jewish audit**: 23,451 entries across 6 regions — Canadian synagogues verified
- **17 Muslim doctrinal traditions**: Canadian and Indian mosques classified to specific schools
- **Hindu taxonomy**: 188K global entries with Vaishnavism/Shaivism/Shaktism/Smartism classification
- **Multi-language name handling**: Hindi, Tamil, Telugu, French, Punjabi, Gujarati scripts supported
- **720+ provenance log entries**: Complete operational history
- **211,153+ enrichment change log entries**: Full field-level change tracking

## License

This dataset (Canada & India subset) is published under the [Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/) (CC BY 4.0).

Individual source datasets carry their own licenses:
- Canada Revenue Agency data: Open Government Licence — Canada
- Wikidata: CC0
- Overture Maps: CDLA Permissive v2.0
- OpenStreetMap: ODbL
- Wikipedia: CC BY-SA 3.0

## Citation

If you use GRID Canada & India in your research, please cite:

> Prescott, C. (2026). *GRID: Global Religious Infrastructure Database — Canada & India Public Release* (Version 2.0) [Dataset]. Available at: https://github.com/[repo-url]

## Related Documentation

| Document | Description |
|----------|-------------|
| `docs/NATURE_DATA_DESCRIPTOR.md` | Data descriptor paper for *Scientific Data* (Nature) |
| `docs/SCHEMA.md` | Complete database schema with SQL references |
| `docs/REPRODUCIBILITY.md` | Step-by-step reproducibility guide |
| `docs/TAXONOMY.md` | CFTLM taxonomy design and classification methodology |
| `taxonomy_completeness.txt` | 604-node CFTLM tree with per-node completeness statistics |
| `AGENTS.md` | Developer onboarding — current state, recent fixes, project conventions |

## Public Release Notes

**Scope**: This public release covers **Canada (CA)** and **India (IN)** only. Filter queries by `WHERE country IN ('CA', 'IN')`. The full database of ~3.29M records across 290 countries remains under active development and is not included in this publication.

**Excluded**: United States (~1M records), Brazil (~205K), Japan (~158K), Indonesia (~152K), Germany (~106K), United Kingdom (~101K), and all other countries.

---

*Built with Python 3.11, SQLite 3.49+, and a commitment to open, reproducible, FAIR-compliant data science.*