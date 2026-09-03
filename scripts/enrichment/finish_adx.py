"""Create data dictionary and finish ADX listing setup."""
import json, subprocess, time
from pathlib import Path
from datetime import datetime

OUT = Path("outputs/marketplace")

# Data dictionary
dict_md = OUT / "data_dictionary.md"
dict_md.write_text(f"""# GRID -- Global Religious Infrastructure Database

**3,481,509 worship sites | 291 countries | 1,073,812 US | 85,154 FEMA-scored tracts | 980,403 churches with risk scores**
Updated quarterly or more often -- new data pushed as sources are ingested.

---

## FTLM Taxonomy: Civilization > Faith > Legacy > Tradition > Movement
Every worship site is classified across five taxonomic levels. 100% faith-classified.

| Level | Count | Examples |
|---|---|---|
| **Civilization** | 6 | Abrahamic, Dharmic, East Asian, Indigenous, Pagan, Ancient |
| **Faith** | 12 | Christian (2.58M), Islam (361K), Hindu (202K), Buddhist (199K), Shinto (68K), Judaism (27K), Sikh (7K), Taoist (15K), Jain (979), Bahai, Confucian, Other |
| **Legacy** | 20+ | Sunni / Shia / Ibadi; Catholic / Protestant / Orthodox; Mahayana / Theravada / Vajrayana |
| **Tradition** | 1,066 | Roman Catholic, Sunni/Hanafi, Baptist, Vaishnavism, Orthodox/Chabad, Pentecostal |
| **Movement** | 300+ | ELCA / LCMS / WELS; SBC / National Baptist; Hasidic / Yeshiva; Khalsa / Singh Sabha |

---

## Core Data (US: 1,073,812 records)

| Dimension | Coverage |
|---|---|
| GPS coordinates | 982,994 (91%) |
| County FIPS (5-digit) | 959,059 (89%) |
| ZIP5 | 234,267 |
| Websites | 336,848 |
| Phone numbers | 45,936 |
| Email addresses | 16,325 |
| Street addresses | 614K address-normalized |

---

## Enrichment Layers

### FEMA National Risk Index (v1.20, Dec 2025)
- **980,403 US churches** joined to 85,154 census tracts
- 18 natural hazard risk scores + ratings: hurricane, tornado, inland flood, wildfire, earthquake, winter weather, heat wave, drought, coastal flood, avalanche, cold wave, hail, ice storm, landslide, lightning, strong wind, tsunami, volcano
- Composite scores: RISK_SCORE, EAL_SCORE (Expected Annual Loss), SOVI_SCORE (Social Vulnerability), RESL_SCORE (Community Resilience)
- Population and building/agriculture value per tract

### FBI Crime Data
- **State-level** (SRS): 2,233 rows, 1979-2024, all 50 states -- violent crime, homicide, property crime, burglary, larceny, motor vehicle theft
- **Agency-level** (NIBRS 2024): 12,435 law enforcement agencies -- 69 offense categories, population served

### Geographic Layers (via church_districts: 9.3M assignments)
10 Census geographic layers joined to every US church: Census Tract, Block Group, County Subdivision, Place, ZIP/ZCTA, Congressional District, State House, State Senate, CBSA (metro area), Urban/Rural

### Denomination Hierarchies (9 denominations, 163K relationships)
| Denomination | Records | Structure |
|---|---|---|
| Lutheran | 57,322 | HQ > Synod/District > Congregation (ELCA/LCMS/WELS) |
| Catholic | 33,087 | Diocese > Parish |
| Baptist (SBC) | 35,655 | Convention > Association > Church |
| LDS/Mormon | 19,440 | Area Office > Temple > Stake > Meetinghouse |
| Jehovah's Witnesses | 10,664 | Bethel > Assembly Hall > Kingdom Hall |
| Chabad | 2,885 | Headquarters > Center |
| Salvation Army | 2,869 | Territory > Division > Corps |
| Bahai | 1,192 | World Centre > NSA > LSA > Center |
| Moravian | 608 | Province > Congregation |

### Additional Enrichment
- **RUCC Codes**: 3,233 counties with USDA Rural-Urban Continuum Codes
- **SBA PPP Loans**: 209,736 loans matched to churches (COVID-era financial data)
- **Census ACS**: County-level demographics (income, poverty, education, housing)
- **CDC PLACES**: 3M+ tract-level health records (obesity, diabetes, smoking, insurance, etc.)
- **1.8M enrichment changes** tracked with provenance logging

---

## Data Sources
Overture Maps, OpenStreetMap, IRS Form 990, Catholic diocese directories, SBA PPP, SBC/ELCA/LCMS/PCUSA/AG/UMC directories, FEMA NRI v1.20, FBI UCR, Census ACS/TIGER, CDC PLACES, USDA RUCC, Wikipedia NHL landmarks, Wikidata, Pleiades (ancient sites), and 20+ denominational scrapers.

## Pricing Tiers

| Tier | Price | Contents |
|---|---|---|
| Free Sample | $0 | Vermont 500 rows with FEMA scores (included with listing) |
| US Monthly | $997/mo | Full US (~1M records), updated quarterly+ |
| US One-Time | $4,997 | Full US, one-time + 1 year of updates |
| Global Enterprise | Contact | 3.4M records, 200+ countries, all enrichment layers |
| Private Offers | Custom | API access, site license, custom extracts |

## AWS Data Exchange Listing
https://us-east-1.console.aws.amazon.com/dataexchange/home?region=us-east-1#/data-sets/993cef8f87cacadaee6e20e52d939084

Contact: charlesaprescottjr@gmail.com
""", encoding='utf-8')

# Upload
print("Uploading data dictionary...")
subprocess.run(["aws", "s3", "cp", str(dict_md), "s3://grid-marketplace-data/data/data_dictionary.md"], check=True)
print("Done!")

# Check ADX status
result = subprocess.run(["aws", "dataexchange", "list-data-sets", "--output", "json"], capture_output=True, text=True)
ds_list = json.loads(result.stdout)
for ds in ds_list.get("DataSets", []):
    ds_id = ds["Id"]
    revs = subprocess.run(["aws", "dataexchange", "list-data-set-revisions", "--data-set-id", ds_id, "--output", "json"], capture_output=True, text=True)
    rev_data = json.loads(revs.stdout)
    print(f"\nDataset: {ds['Name']} ({ds_id})")
    print(f"  Revisions: {len(rev_data.get('Revisions', []))}")
    for rev in rev_data.get("Revisions", []):
        print(f"  Rev: {rev['Id']} (finalized: {rev.get('Finalized', False)})")
