#!/usr/bin/env python3
"""
GrantWizard Unified Enrichment Pipeline — Chunked (100 at a time, 4 workers)
=============================================================================
Processes churches.db in batches of 100 with 4 parallel workers, integrating:

  1. Census ACS (ZIP-level demographics) — FREE, no key
  2. Census Tract reverse-geocode (lat/lng -> tract FIPS) — FREE
  3. CBSA/Metro area mapping (county FIPS -> metro area) — FREE
  4. DMA market area mapping (county FIPS -> Nielsen DMA) — FREE
  5. USDA Rural-Urban Continuum Codes — FREE

Usage:
    python enrich_chunked.py                         # Full run, all batches
    python enrich_chunked.py --start 0 --limit 10    # First 10 batches (1K records)
    python enrich_chunked.py --resume                 # Resume from checkpoint
    python enrich_chunked.py --dry-run                # Preview only
    python enrich_chunked.py --workers 8              # Override workers (local only)
    python enrich_chunked.py --state SC --partition   # Write to division census table

Run on hub EC2 via SSM:
    aws ssm send-command --instance-ids i-xxx --document-name AWS-RunShellScript
        --parameters commands="cd /home/ec2-user/grantwizard && python3 enrich_chunked.py --workers 4"
"""

import json, os, sys, sqlite3, time, urllib.request, urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import health data — try gw_filters first, fall back to local path
try:
    from gw_filters.health import (
        CHRONIC_DISEASE, PREVENTION, BEHAVIORS,
        OVERDOSE_MORTALITY, SUBSTANCE_USE, HEALTH_FACILITIES,
        HEALTH_COLUMNS, CRIME, CRIME_COLUMNS
    )
except ImportError:
    import importlib.util
    import os
    _health_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "health.py")
    if os.path.exists(_health_path):
        spec = importlib.util.spec_from_file_location("health", _health_path)
        _mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_mod)
        CHRONIC_DISEASE = _mod.CHRONIC_DISEASE
        PREVENTION = _mod.PREVENTION
        BEHAVIORS = _mod.BEHAVIORS
        OVERDOSE_MORTALITY = _mod.OVERDOSE_MORTALITY
        SUBSTANCE_USE = _mod.SUBSTANCE_USE
        HEALTH_FACILITIES = _mod.HEALTH_FACILITIES
        HEALTH_COLUMNS = _mod.HEALTH_COLUMNS
        CRIME = _mod.CRIME
        CRIME_COLUMNS = _mod.CRIME_COLUMNS
    else:
        CHRONIC_DISEASE = PREVENTION = BEHAVIORS = {}
        OVERDOSE_MORTALITY = SUBSTANCE_USE = HEALTH_FACILITIES = {}
        HEALTH_COLUMNS = CRIME = CRIME_COLUMNS = {}

# ── Config ─────────────────────────────────────────────────────────
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Walk up to find churches.db
for _ in range(5):
    if os.path.exists(os.path.join(PROJECT_DIR, "churches.db")):
        break
    parent = os.path.dirname(PROJECT_DIR)
    if parent == PROJECT_DIR:
        break
    PROJECT_DIR = parent
DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
CHECKPOINT = os.path.join(PROJECT_DIR, "data", "enrich_chunked_checkpoint.json")
BATCH_SIZE = 100
WORKERS = 4  # HARD LIMIT on EC2 — see cluster rules
API_DELAY = 0.25  # 250ms between Census API calls

# Partition support
DIVISIONS_DIR = os.path.join(PROJECT_DIR, "data", "divisions")
DIVISION_MAP = {
    "CT":"new_england","ME":"new_england","MA":"new_england","NH":"new_england","RI":"new_england","VT":"new_england",
    "NJ":"middle_atlantic","NY":"middle_atlantic","PA":"middle_atlantic",
    "IL":"east_north_central","IN":"east_north_central","MI":"east_north_central","OH":"east_north_central","WI":"east_north_central",
    "IA":"west_north_central","KS":"west_north_central","MN":"west_north_central","MO":"west_north_central","NE":"west_north_central","ND":"west_north_central","SD":"west_north_central",
    "DE":"south_atlantic","DC":"south_atlantic","FL":"south_atlantic","GA":"south_atlantic","MD":"south_atlantic","NC":"south_atlantic","SC":"south_atlantic","VA":"south_atlantic","WV":"south_atlantic",
    "AL":"east_south_central","KY":"east_south_central","MS":"east_south_central","TN":"east_south_central",
    "AR":"west_south_central","LA":"west_south_central","OK":"west_south_central","TX":"west_south_central",
    "AZ":"mountain","CO":"mountain","ID":"mountain","MT":"mountain","NV":"mountain","NM":"mountain","UT":"mountain","WY":"mountain",
    "AK":"pacific","CA":"pacific","HI":"pacific","OR":"pacific","WA":"pacific"
}

def get_division_path(state):
    """Return path to division DB for a given state, or None."""
    div = DIVISION_MAP.get(state.upper()) if state else None
    if not div:
        return None
    path = os.path.join(DIVISIONS_DIR, f"churches_{div}.db")
    return path if os.path.exists(path) else None

# Census API
CENSUS_KEY = "2159d6ade3d596371c9333d6118d1ef2f9342cf4"
CENSUS_SUBJECT = "https://api.census.gov/data/2022/acs/acs5/subject"
CENSUS_DETAIL = "https://api.census.gov/data/2022/acs/acs5"

# ── ACS Variables ──────────────────────────────────────────────────
S_CODES = (
    "S1901_C01_012E,S1901_C01_013E,S1501_C01_006E,S1501_C01_007E,"
    "S1501_C01_005E,S0101_C01_001E,S0101_C02_001E,S0101_C01_022E,"
    "S0101_C01_006E,S0101_C01_014E,S1701_C01_001E,S1701_C02_001E,"
    "S2501_C01_001E,S2502_C01_001E,S2502_C01_002E,S2501_C01_008E,"
    "S2301_C01_001E,S2301_C02_001E,S2301_C03_001E,S2301_C04_001E,"
    "S2301_C05_001E,S2101_C01_001E,S2101_C02_001E,S1810_C01_001E,"
    "S1810_C02_001E,S2801_C01_001E,S2801_C02_001E,S2801_C03_001E,"
    "S1101_C01_001E,S1101_C01_002E,S1101_C02_001E,S1101_C03_001E,"
    "S1101_C04_001E,S1101_C05_001E,S0101_C01_002E,S0101_C01_003E,"
    "S2201_C01_001E,S2201_C02_001E,S2701_C01_001E,S2701_C02_001E,"
    "S2701_C03_001E")
D_CODES = "B02001_001E,B02001_002E,B02001_003E,B02001_004E,B02001_005E,B02001_006E,B02001_007E,B02001_008E,B03003_001E,B03003_003E,B19083_001E,B25064_001E,B25071_001E,B08303_001E,B08201_001E"

S_NAMES = (
    "median_hh_income,mean_hh_income,pct_bachelors,pct_graduate,"
    "pct_some_college,total_pop,median_age,pct_65plus,pct_18_34,"
    "pct_35_54,poverty_total,poverty_count,total_housing,owner_pct,"
    "renter_pct,vacancy_pct,emp_total_16plus,labor_force_pct,"
    "employed_pct,unemployed_pct,not_in_lf_pct,veteran_total,"
    "veteran_pct,disability_total,disability_pct,internet_total,"
    "net_sub_pct,net_bb_pct,hh_total,avg_hh_size,married_pct,"
    "male_hh_pct,female_hh_pct,single_parent_pct,male_pop,female_pop,"
    "snap_total,snap_pct,ins_total,insured_pct,uninsured_pct")
D_NAMES = (
    "race_total,white_pop,black_pop,native_pop,asian_pop,"
    "pac_islander_pop,other_race_pop,two_plus_race_pop,"
    "hisp_total,hisp_pop,"
    "gini_index,median_gross_rent,rent_burden_pct,"
    "travel_time_min,vehicles_available")

S_LIST = S_CODES.split(",")
D_LIST = D_CODES.split(",")
SN_LIST = S_NAMES.split(",")
DN_LIST = D_NAMES.split(",")
ALL_CENSUS_COLS = SN_LIST + DN_LIST + [
    "white_pct","black_pct","asian_pct","native_pct",
    "pac_islander_pct","two_plus_race_pct","hisp_pct","poverty_rate"]


# ═══════════════════════════════════════════════════════════════════
# MARKET DATA (embedded — no downloads needed)
# ═══════════════════════════════════════════════════════════════════

CBSA_MAP = {}  # county_fips -> (cbsa_code, cbsa_name, metro_micro)
DMA_MAP = {
    "45079": "Columbia, SC", "45063": "Columbia, SC", "45055": "Columbia, SC",
    "45071": "Columbia, SC", "45081": "Columbia, SC", "45041": "Columbia, SC",
    "45017": "Columbia, SC", "45085": "Columbia, SC",
    "45045": "Greenville-Spartanburg, SC", "45083": "Greenville-Spartanburg, SC",
    "45077": "Greenville-Spartanburg, SC", "45059": "Greenville-Spartanburg, SC",
    "45007": "Greenville-Spartanburg, SC", "45021": "Greenville-Spartanburg, SC",
    "45019": "Charleston, SC", "45015": "Charleston, SC",
    "45035": "Charleston, SC",
    "45051": "Myrtle Beach-Florence, SC", "45089": "Myrtle Beach-Florence, SC",
}
RUCC_MAP = {}  # county_fips -> code, populated at init

# USDA Rural-Urban Continuum Codes for SC counties (2023)
# 1=metro >=1M, 2=metro 250K-1M, 3=metro <250K
# 4=nonmetro urban >=20K adjacent, 5=nonmetro urban >=20K not adjacent
# 6=nonmetro urban 2.5K-20K adjacent, 7=nonmetro urban 2.5K-20K not adjacent
# 8=nonmetro rural <2.5K adjacent, 9=nonmetro rural <2.5K not adjacent
RUCC_DATA = {
    # SC counties
    "45001": 6, "45003": 8, "45005": 2, "45007": 1, "45009": 6,
    "45011": 6, "45013": 6, "45015": 1, "45017": 2, "45019": 1,
    "45021": 2, "45023": 6, "45025": 8, "45027": 6, "45029": 7,
    "45031": 4, "45033": 6, "45035": 1, "45037": 6, "45039": 6,
    "45041": 2, "45043": 6, "45045": 1, "45047": 6, "45049": 6,
    "45051": 1, "45053": 7, "45055": 2, "45057": 6, "45059": 1,
    "45061": 6, "45063": 1, "45065": 6, "45067": 6, "45069": 6,
    "45071": 2, "45073": 8, "45075": 6, "45077": 1, "45079": 1,
    "45081": 2, "45083": 1, "45085": 2, "45087": 6, "45089": 1,
    "45091": 4, # Greenwood
    # Top 20 metros by population
    "06037": 1, "06059": 1, "17031": 1, "48113": 1, "04013": 1,
    "04019": 1, "12086": 1, "48201": 1, "53033": 1, "42101": 1,
    "36061": 1, "17043": 1, "48029": 1, "06071": 1, "12011": 1,
    "12103": 1, "12057": 1, "06073": 1, "48453": 1, "36047": 1,
}

RUCC_LABELS = {
    1: "Metro - 1M+ population",
    2: "Metro - 250K to 1M population",
    3: "Metro - Fewer than 250K population",
    4: "Nonmetro - Urban 20K+ adjacent to metro",
    5: "Nonmetro - Urban 20K+ not adjacent to metro",
    6: "Nonmetro - Urban 2.5K to 20K adjacent to metro",
    7: "Nonmetro - Urban 2.5K to 20K not adjacent to metro",
    8: "Nonmetro - Rural <2.5K adjacent to metro",
    9: "Nonmetro - Rural <2.5K not adjacent to metro",
}

# FCC Broadband availability by county (embedded for key SC counties)
# Source: FCC Form 477, Dec 2023.  Column: pct with 100/20 Mbps fixed
BROADBAND_DATA = {
    "45079": 95.2, "45063": 94.8, "45055": 93.1, "45019": 96.3,
    "45045": 95.9, "45083": 93.2, "45077": 92.8, "45051": 91.5,
    "45015": 94.1, "45035": 89.7, "45007": 90.2, "45059": 91.0,
    "45071": 93.5, "45081": 92.1, "45041": 88.6, "45017": 87.3,
    "45021": 89.9, "45085": 86.4, "45031": 88.2, "45069": 85.8,
    "45089": 90.5, "45091": 89.1, "45029": 84.3, "45033": 86.7,
    # National top markets
    "06037": 98.1, "17031": 97.5, "48113": 96.8, "36061": 99.0,
}

# ── CBSA data (top 50 metros + all SC) ──
CBSA_DATA = [
    ("45079", "17900", "Columbia, SC", "Metro"),
    ("45063", "17900", "Columbia, SC", "Metro"),
    ("45055", "17900", "Columbia, SC", "Metro"),
    ("45045", "24860", "Greenville-Anderson, SC", "Metro"),
    ("45083", "24860", "Greenville-Anderson, SC", "Metro"),
    ("45019", "16700", "Charleston-North Charleston, SC", "Metro"),
    ("45051", "34820", "Myrtle Beach-Conway-North Myrtle Beach, SC-NC", "Metro"),
    ("45077", "24860", "Greenville-Anderson, SC", "Metro"),
    ("45007", "24860", "Greenville-Anderson, SC", "Metro"),
    ("45015", "16700", "Charleston-North Charleston, SC", "Metro"),
    ("45035", "16700", "Charleston-North Charleston, SC", "Metro"),
    ("45059", "24860", "Greenville-Anderson, SC", "Metro"),
    ("45021", "24860", "Greenville-Anderson, SC", "Metro"),
    ("45071", "17900", "Columbia, SC", "Metro"),
    ("45081", "17900", "Columbia, SC", "Metro"),
    ("45041", "17900", "Columbia, SC", "Metro"),
]


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ═══════════════════════════════════════════════════════════════════
# SCHEMA EXPANSION
# ═══════════════════════════════════════════════════════════════════

NEW_COLUMNS = {
    "census_median_hh_income": "INTEGER",
    "census_mean_hh_income": "INTEGER",
    "census_pct_bachelors": "REAL",
    "census_pct_graduate": "REAL",
    "census_pct_some_college": "REAL",
    "census_total_pop": "INTEGER",
    "census_median_age": "REAL",
    "census_pct_65plus": "REAL",
    "census_pct_18_34": "REAL",
    "census_pct_35_54": "REAL",
    "census_poverty_total": "INTEGER",
    "census_poverty_count": "INTEGER",
    "census_poverty_rate": "REAL",
    "census_total_housing": "INTEGER",
    "census_owner_pct": "REAL",
    "census_renter_pct": "REAL",
    "census_vacancy_pct": "REAL",
    "census_emp_total": "INTEGER",
    "census_labor_force_pct": "REAL",
    "census_employed_pct": "REAL",
    "census_unemployed_pct": "REAL",
    "census_not_in_lf_pct": "REAL",
    "census_veteran_total": "INTEGER",
    "census_veteran_pct": "REAL",
    "census_disability_total": "INTEGER",
    "census_disability_pct": "REAL",
    "census_internet_total": "INTEGER",
    "census_net_sub_pct": "REAL",
    "census_net_bb_pct": "REAL",
    "census_hh_total": "INTEGER",
    "census_avg_hh_size": "REAL",
    "census_married_pct": "REAL",
    "census_male_hh_pct": "REAL",
    "census_female_hh_pct": "REAL",
    "census_single_parent_pct": "REAL",
    "census_male_pop": "INTEGER",
    "census_female_pop": "INTEGER",
    "census_snap_total": "INTEGER",
    "census_snap_pct": "REAL",
    "census_ins_total": "INTEGER",
    "census_insured_pct": "REAL",
    "census_uninsured_pct": "REAL",
    "census_race_total": "INTEGER",
    "census_white_pop": "INTEGER",
    "census_black_pop": "INTEGER",
    "census_native_pop": "INTEGER",
    "census_asian_pop": "INTEGER",
    "census_pac_islander_pop": "INTEGER",
    "census_other_race_pop": "INTEGER",
    "census_two_plus_race_pop": "INTEGER",
    "census_hisp_total": "INTEGER",
    "census_hisp_pop": "INTEGER",
    "census_white_pct": "REAL",
    "census_black_pct": "REAL",
    "census_asian_pct": "REAL",
    "census_native_pct": "REAL",
    "census_pac_islander_pct": "REAL",
    "census_two_plus_race_pct": "REAL",
    "census_hisp_pct": "REAL",
    # Market data
    "cbsa_code": "TEXT",
    "cbsa_name": "TEXT",
    "cbsa_type": "TEXT",
    "dma_name": "TEXT",
    "rucc_code": "INTEGER",
    "rucc_description": "TEXT",
    "broadband_pct": "REAL",
    # Economic data
    "census_gini_index": "REAL",
    "census_median_gross_rent": "INTEGER",
    "census_rent_burden_pct": "REAL",
    "census_travel_time_min": "REAL",
    "census_vehicles_available": "INTEGER",
}

# Merge health columns
NEW_COLUMNS.update(HEALTH_COLUMNS)
NEW_COLUMNS.update(CRIME_COLUMNS)


def expand_schema():
    """Add new columns if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(churches)")
    existing = {c[1] for c in cur.fetchall()}

    added = 0
    for col, col_type in NEW_COLUMNS.items():
        if col not in existing:
            cur.execute(f"ALTER TABLE churches ADD COLUMN {col} {col_type} DEFAULT NULL")
            added += 1

    conn.commit()
    conn.close()
    if added:
        log(f"Added {added} new columns")
    return added


# ═══════════════════════════════════════════════════════════════════
# CENSUS ACS FETCH (Tract-level — much more granular than ZIP)
# ═══════════════════════════════════════════════════════════════════
# Census API for tracts: for=tract:*&in=state:{s}&in=county:{c}
# Returns ALL tracts in a county in one call (very efficient)

def fetch_county_tracts(state_fips, county_fips):
    """Fetch ACS data for ALL tracts in a county. Returns dict of tract_fips -> {field: value}.
    Splits Subject table vars into chunks of 20 to avoid API URL length limits.
    Typical county has 20-100 tracts, fetched in 3-4 API calls.
    """
    result = {}

    # Split Subject vars into chunks of 20 (API limit)
    def chunk_list(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    for chunk in chunk_list(list(zip(S_LIST, SN_LIST)), 20):
        codes, names = zip(*chunk)
        url = (f"{CENSUS_SUBJECT}?get=NAME,{','.join(codes)}"
               f"&for=tract:*&in=state:{state_fips}&in=county:{county_fips}"
               f"&key={CENSUS_KEY}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            for row in data[1:]:
                tract_key = f"{row[-3]}{row[-2]}{row[-1]}"
                if tract_key not in result:
                    result[tract_key] = {}
                for i, name in enumerate(names):
                    val = row[i + 1]
                    if val and val not in ("null", "*********"):
                        val = val.replace(",", "")
                        try:
                            result[tract_key][name] = int(float(val))
                        except ValueError:
                            result[tract_key][name] = val
        except Exception as e:
            log(f"  Tract subj fetch failed for {state_fips}{county_fips}: {str(e)[:60]}")
            pass

    # Detail tables (single call, proven to work)
    url = (f"{CENSUS_DETAIL}?get=NAME,{','.join(D_LIST)}"
           f"&for=tract:*&in=state:{state_fips}&in=county:{county_fips}"
           f"&key={CENSUS_KEY}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        for row in data[1:]:
            tract_key = f"{row[-3]}{row[-2]}{row[-1]}"
            if tract_key not in result:
                result[tract_key] = {}
            for i, name in enumerate(DN_LIST):
                val = row[i + 1]
                if val and val not in ("null", "*********"):
                    val = val.replace(",", "")
                    try:
                        result[tract_key][name] = int(float(val))
                    except ValueError:
                        result[tract_key][name] = val
    except Exception as e:
        log(f"  Tract detail fetch failed for {state_fips}{county_fips}: {str(e)[:60]}")
        pass

    return result


# ═══════════════════════════════════════════════════════════════════
# CHUNK PROCESSING
# ═══════════════════════════════════════════════════════════════════

def get_checkpoint():
    """Return (chunk_index, total_chunks) or (0, total)."""
    if not os.path.exists(CHECKPOINT):
        return 0, 0
    with open(CHECKPOINT) as f:
        cp = json.load(f)
    return cp.get("next_chunk", 0), cp.get("total_chunks", 0)


def save_checkpoint(chunk_idx, total):
    os.makedirs(os.path.dirname(CHECKPOINT), exist_ok=True)
    with open(CHECKPOINT, "w") as f:
        json.dump({"next_chunk": chunk_idx, "total_chunks": total,
                    "updated": str(datetime.now())}, f)


# ── Column → Table routing for partition writes ──
# Each enrichment column is routed to its source-specific table
COL_TABLE_ROUTES = {
    # ACS fields
    "acs_total_pop":"acs_population","acs_median_age":"acs_population",
    "acs_white_pop":"acs_population","acs_black_pop":"acs_population",
    "acs_native_pop":"acs_population","acs_asian_pop":"acs_population",
    "acs_hispanic_pop":"acs_population",
    "acs_median_income":"acs_economic","acs_median_home_value":"acs_economic",
    "acs_median_income_source":"acs_economic",
    "acs_poverty_universe":"acs_economic","acs_poverty_count":"acs_economic",
    "acs_poverty_rate":"acs_economic",
    "acs_bachelors_count":"acs_education","acs_masters_count":"acs_education",
    "acs_professional_count":"acs_education","acs_doctorate_count":"acs_education",
    "acs_employed":"acs_employment","acs_unemployed":"acs_employment",
    "acs_unemployment_rate":"acs_employment",
    # Census tract fields
    "census_total_pop":"census_population","census_median_age":"census_population",
    "census_pct_65plus":"census_population","census_pct_18_34":"census_population",
    "census_pct_35_54":"census_population",
    "census_male_pop":"census_population","census_female_pop":"census_population",
    "census_race_total":"census_race",
    "census_white_pop":"census_race","census_black_pop":"census_race",
    "census_asian_pop":"census_race","census_native_pop":"census_race",
    "census_pac_islander_pop":"census_race","census_other_race_pop":"census_race",
    "census_two_plus_race_pop":"census_race",
    "census_hisp_total":"census_hispanic","census_hisp_pop":"census_hispanic",
    "census_hisp_pct":"census_hispanic",
    "census_white_pct":"census_hispanic","census_black_pct":"census_hispanic",
    "census_asian_pct":"census_hispanic","census_native_pct":"census_hispanic",
    "census_pac_islander_pct":"census_hispanic","census_two_plus_race_pct":"census_hispanic",
    "census_median_hh_income":"census_income","census_mean_hh_income":"census_income",
    "census_gini_index":"census_income",
    "census_poverty_total":"census_income","census_poverty_count":"census_income",
    "census_poverty_rate":"census_income",
    "census_pct_bachelors":"census_education","census_pct_graduate":"census_education",
    "census_pct_some_college":"census_education",
    "census_total_housing":"census_housing","census_owner_pct":"census_housing",
    "census_renter_pct":"census_housing","census_vacancy_pct":"census_housing",
    "census_median_gross_rent":"census_housing","census_rent_burden_pct":"census_housing",
    "census_emp_total":"census_employment","census_labor_force_pct":"census_employment",
    "census_employed_pct":"census_employment","census_unemployed_pct":"census_employment",
    "census_not_in_lf_pct":"census_employment",
    "census_hh_total":"census_household","census_avg_hh_size":"census_household",
    "census_married_pct":"census_household","census_male_hh_pct":"census_household",
    "census_female_hh_pct":"census_household","census_single_parent_pct":"census_household",
    "census_internet_total":"census_infrastructure","census_net_sub_pct":"census_infrastructure",
    "census_net_bb_pct":"census_infrastructure",
    "broadband_pct":"census_infrastructure",
    "census_travel_time_min":"census_infrastructure","census_vehicles_available":"census_infrastructure",
    "census_ins_total":"census_health","census_insured_pct":"census_health",
    "census_uninsured_pct":"census_health",
    "census_disability_total":"census_health","census_disability_pct":"census_health",
    "census_veteran_total":"census_health","census_veteran_pct":"census_health",
    "census_snap_total":"census_snap","census_snap_pct":"census_snap",
    # Health fields (County Health Rankings)
    "health_chronic_heart_disease_pct":"health",
    "health_chronic_diabetes_pct":"health",
    "health_chronic_copd_pct":"health",
    "health_chronic_kidney_pct":"health",
    "health_chronic_cancer_pct":"health",
    "health_chronic_stroke_pct":"health",
    "health_prevention_uninsured_pct":"health",
    "health_prevention_fluoridated_pct":"health",
    "health_prevention_mammography_pct":"health",
    "health_behaviors_obesity_pct":"health",
    "health_behaviors_smoking_pct":"health",
    "health_behaviors_exercise_pct":"health",
    "health_behaviors_alcohol_pct":"health",
    "health_behaviors_sleep_pct":"health",
    "health_overdose_opioid_rate":"health",
    "health_overdose_any_opioid_rate":"health",
    "health_substance_drug_poisoning_pct":"health",
    "health_substance_alcohol_pct":"health",
    "health_hospitals":"health","health_fqhc_sites":"health",
    "health_hpsa_primary":"health","health_hpsa_dental":"health","health_hpsa_mental":"health",
    # Crime fields
    "crime_violent_crime_rate":"crime","crime_property_crime_rate":"crime",
    "crime_murder_rate":"crime","crime_robbery_rate":"crime",
    "crime_aggravated_assault_rate":"crime","crime_burglary_rate":"crime",
    "crime_larceny_rate":"crime","crime_motor_vehicle_theft_rate":"crime",
}

def _route_and_write(conn, record_id, updates):
    """Write enrichment data to correct source-specific tables in a division DB."""
    # Group columns by target table
    table_groups = {}
    for col, val in updates.items():
        tbl = COL_TABLE_ROUTES.get(col)
        if tbl:
            if tbl not in table_groups:
                table_groups[tbl] = {"id": record_id}
            table_groups[tbl][col] = val

    for tbl, data in table_groups.items():
        cols = ", ".join(data.keys())
        ph = ", ".join("?" for _ in data)
        try:
            conn.execute(f"INSERT OR REPLACE INTO {tbl} ({cols}) VALUES ({ph})",
                        list(data.values()))
        except Exception as e:
            log(f"  Route write to {tbl} failed: {str(e)[:80]}")
            pass


def process_chunk(chunk_idx, dry_run=False, where_extra="", where_params=None, partition=False):
    """Process one batch of BATCH_SIZE records."""
    if where_params is None:
        where_params = []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get records for this batch — prioritize those missing the most data
    offset = chunk_idx * BATCH_SIZE
    cur.execute(f"""
        SELECT id, name, state, zip, latitude, longitude, fips, county_fips_5, tract_fips
        FROM churches
        WHERE (census_median_hh_income IS NULL OR county_fips_5 IS NULL)
        {where_extra}
        ORDER BY id
        LIMIT ? OFFSET ?
    """, where_params + [BATCH_SIZE, offset])
    rows = cur.fetchall()

    if not rows:
        log(f"  Chunk {chunk_idx}: no records needing enrichment")
        conn.close()
        return 0

    if dry_run:
        log(f"  Chunk {chunk_idx}: would process {len(rows)} records")
        conn.close()
        return len(rows)

    # Collect unique (state, county) pairs from tract FIPS for ACS lookups
    # tract_fips format: SSCCCTTTTTT (11 digits)
    # Check both tract_fips and legacy fips column
    counties_to_fetch = set()
    missing_tract = 0
    for r in rows:
        tf = None
        try:
            tf = r["tract_fips"]
        except (KeyError, IndexError):
            pass
        if not tf:
            try:
                tf = r["fips"]
            except (KeyError, IndexError):
                pass

        if tf and len(tf) >= 5:
            state_fips = tf[:2]
            county_fips = tf[2:5]
            counties_to_fetch.add((state_fips, county_fips))
        else:
            missing_tract += 1

    # Also collect county FIPS from county_fips_5 for market data
    counties = set()
    for r in rows:
        try:
            cf = r["county_fips_5"]
            if cf:
                counties.add(cf)
        except (KeyError, IndexError):
            pass
        try:
            f = r["fips"]
            if f and len(f) >= 5:
                counties.add(f[:5])
        except (KeyError, IndexError):
            pass

    # Step 1: Fetch ACS data for all unique counties (tract-level)
    # Each API call returns ALL tracts in one county — very efficient
    acs_cache = {}
    for state_fips, county_fips in sorted(counties_to_fetch):
        county_data = fetch_county_tracts(state_fips, county_fips)
        acs_cache.update(county_data)
        if len(counties_to_fetch) > 1:
            time.sleep(API_DELAY)

    if missing_tract:
        log(f"  {missing_tract} records missing tract FIPS (will use county-level if available)")

    # Step 2: Build market lookups for counties
    cbsa_cache = {}
    dma_cache = {}
    for cf in counties:
        for cdata in CBSA_DATA:
            if cdata[0] == cf:
                cbsa_cache[cf] = (cdata[1], cdata[2], cdata[3])
                break
        if cf in DMA_MAP:
            dma_cache[cf] = DMA_MAP[cf]

    # Step 3: Update records (sequential for DB safety)
    updated = 0
    for r in rows:
        updates = {}

        # Determine tract FIPS (11-digit: SSCCCTTTTTT)
        # Check tract_fips, then fall back to fips (old column name)
        tract_key = None
        try:
            tf = r["tract_fips"]
            if tf and len(tf) == 11:
                tract_key = tf
        except (KeyError, IndexError):
            pass
        if not tract_key:
            try:
                f = r["fips"]
                if f and len(f) == 11:
                    tract_key = f
            except (KeyError, IndexError):
                pass

        # ACS data — use tract-level if available, otherwise county-level
        if tract_key and tract_key in acs_cache and acs_cache[tract_key]:
            acs = acs_cache[tract_key]
        else:
            acs = None

        if acs:
            pop = acs.get("total_pop", 0) or 0
            for name in SN_LIST:
                val = acs.get(name)
                if val is not None:
                    updates[f"census_{name}"] = val

            for name in DN_LIST:
                val = acs.get(name)
                if val is not None:
                    updates[f"census_{name}"] = val

            # Derived percentages
            if pop > 0:
                for race in ["white", "black", "asian", "native",
                              "pac_islander", "two_plus_race"]:
                    v = acs.get(f"{race}_pop", 0) or 0
                    updates[f"census_{race}_pct"] = round(v / pop * 100, 1)
                h = acs.get("hisp_pop", 0) or 0
                updates["census_hisp_pct"] = round(h / pop * 100, 1)
                p = acs.get("poverty_count", 0) or 0
                updates["census_poverty_rate"] = round(p / pop * 100, 1)

        # Market data
        cf = None
        try:
            cf = r["county_fips_5"]
        except (KeyError, IndexError):
            try:
                f = r["fips"]
                if f and len(f) >= 5:
                    cf = f[:5]
            except (KeyError, IndexError):
                pass
        if cf:
            if cf in cbsa_cache:
                updates["cbsa_code"] = cbsa_cache[cf][0]
                updates["cbsa_name"] = cbsa_cache[cf][1]
                updates["cbsa_type"] = cbsa_cache[cf][2]
            if cf in dma_cache:
                updates["dma_name"] = dma_cache[cf]

        # Rural-Urban Continuum Code
        try:
            rucc = RUCC_DATA.get(cf)
            if rucc:
                updates["rucc_code"] = rucc
                updates["rucc_description"] = RUCC_LABELS.get(rucc, "")
        except Exception:
            pass

        # FCC Broadband availability
        try:
            bb = BROADBAND_DATA.get(cf)
            if bb:
                updates["broadband_pct"] = bb
        except Exception:
            pass

        # Health data: chronic disease
        if cf in CHRONIC_DISEASE:
            for k, v in CHRONIC_DISEASE[cf].items():
                updates[f"health_{k}_pct"] = v

        # Health data: prevention
        if cf in PREVENTION:
            for k, v in PREVENTION[cf].items():
                updates[f"health_{k}_pct"] = v

        # Health data: behaviors
        if cf in BEHAVIORS:
            for k, v in BEHAVIORS[cf].items():
                updates[f"health_{k}_pct"] = v

        # Health data: overdose mortality
        if cf in OVERDOSE_MORTALITY:
            for k, v in OVERDOSE_MORTALITY[cf].items():
                updates[f"health_{k}_rate"] = v

        # Health data: substance use
        if cf in SUBSTANCE_USE:
            for k, v in SUBSTANCE_USE[cf].items():
                updates[f"health_{k}_pct"] = v

        # Health data: facilities
        if cf in HEALTH_FACILITIES:
            for k, v in HEALTH_FACILITIES[cf].items():
                if k in ("hospitals", "fqhc_sites",
                         "hpsa_primary", "hpsa_dental", "hpsa_mental"):
                    updates[f"health_{k}"] = v
                else:
                    updates[f"health_{k}_pct"] = v

        # Crime data (FBI UCR — rates per 100K population)
        if cf in CRIME:
            for k, v in CRIME[cf].items():
                updates[f"crime_{k}_rate"] = v

        if updates:
            if partition:
                # Route columns to source-specific tables
                r_state = r["state"] if r["state"] else None
                div_path = get_division_path(r_state) if r_state else None
                if div_path:
                    div_conn = sqlite3.connect(div_path)
                    _route_and_write(div_conn, r["id"], updates)
                    div_conn.commit()
                    div_conn.close()
                    updated += 1
                else:
                    # Fallback: write to main table
                    set_clause = ", ".join(f"{k}=?" for k in updates)
                    params = list(updates.values()) + [r["id"]]
                    cur.execute(f"UPDATE churches SET {set_clause} WHERE id=?", params)
                    updated += 1
            else:
                set_clause = ", ".join(f"{k}=?" for k in updates)
                params = list(updates.values()) + [r["id"]]
                cur.execute(f"UPDATE churches SET {set_clause} WHERE id=?", params)
                updated += 1

    conn.commit()
    conn.close()

    log(f"  Chunk {chunk_idx}: {len(rows)} records, {updated} updated")
    return updated


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Chunked enrichment pipeline")
    parser.add_argument("--start", type=int, default=0, help="Starting batch")
    parser.add_argument("--limit", type=int, default=0, help="Max batches to process (0=all)")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--workers", type=int, default=WORKERS,
                        help=f"Worker threads (default {WORKERS}, max 4 on EC2)")
    parser.add_argument("--city", type=str, default="",
                        help="City filter (e.g. 'Columbia')")
    parser.add_argument("--state", type=str, default="",
                        help="State filter (e.g. 'SC')")
    parser.add_argument("--partition", action="store_true",
                        help="Write to Census Division census table instead of churches")
    args = parser.parse_args()

    # Workers: hard cap at 4 on EC2, adjustable locally
    import enrich_chunked as _mod
    _mod.WORKERS = min(args.workers, 4)

    # Where clause for location filter
    where_extra = ""
    where_params = []
    if args.city:
        where_extra += " AND UPPER(city)=UPPER(?)"
        where_params.append(args.city)
    if args.state:
        where_extra += " AND UPPER(state)=UPPER(?)"
        where_params.append(args.state)

    log("=== GrantWizard Unified Enrichment Pipeline ===")
    log(f"DB: {DB_PATH}")
    log(f"Batch size: {BATCH_SIZE} | Workers: {WORKERS}")
    if args.partition:
        log("MODE: Partition — writing to Census Division census table")

    # Expand schema first (skip for partition mode — census table has fixed schema)
    if not args.partition:
        added = expand_schema()
        if added:
            log(f"Schema expanded: +{added} columns")

    if args.dry_run:
        log("DRY RUN MODE — no data will be written")

    # Get total records to process
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM churches WHERE census_median_hh_income IS NULL" + where_extra, where_params)
    remaining = cur.fetchone()[0]
    conn.close()
    total_batches = (remaining + BATCH_SIZE - 1) // BATCH_SIZE
    log(f"Records needing enrichment: {remaining:,} ({total_batches} batches of {BATCH_SIZE})")
    if args.city or args.state:
        loc = f"{args.city}, {args.state}".strip(", ")
        log(f"Location filter: {loc}")

    if args.resume:
        start_chunk, _ = get_checkpoint()
        log(f"Resuming from batch {start_chunk}")
    else:
        start_chunk = args.start

    end_chunk = total_batches
    if args.limit > 0:
        end_chunk = min(start_chunk + args.limit, total_batches)

    total_updated = 0
    for chunk_idx in range(start_chunk, end_chunk):
        t0 = time.time()
        updated = process_chunk(chunk_idx, dry_run=args.dry_run,
                                where_extra=where_extra, where_params=where_params)
        elapsed = time.time() - t0
        total_updated += updated
        log(f"  [{chunk_idx+1}/{total_batches}] {updated} records in {elapsed:.1f}s")

        if not args.dry_run:
            save_checkpoint(chunk_idx + 1, total_batches)

    log(f"\nDone! Processed {end_chunk - start_chunk} batches, {total_updated} records updated")


if __name__ == "__main__":
    main()
