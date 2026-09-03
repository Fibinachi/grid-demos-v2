"""
Market & Demographic Geography Data
=====================================
Consolidates: download_geo_data.py

Downloads and caches public geography data: CBSA, RUCC, Commuting Zones,
DMA-to-county mapping, and FCC broadband availability.
"""

import csv, io, os, sys, time, urllib.request
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data", "markets")
CACHE_MAX_AGE = 86400 * 7  # 7 days

os.makedirs(DATA_DIR, exist_ok=True)

UA = "Mozilla/5.0 (GrantWizard/1.0)"
MAX_RETRIES = 2

# ── Data Sources ───────────────────────────────────────────────────

CBSA_URLS = [
    "https://www2.census.gov/programs-surveys/metro-micro/geographies/reference/2023/cbsa2023_county.csv",
    "https://www2.census.gov/programs-surveys/metro-micro/geographies/reference/2020/cbsa2020_county.csv",
]
RUCC_URL = "https://www.ers.usda.gov/webdocs/DataFiles/53251/ruralurbancodes2023.xlsx?sv=usr"
FCC_BROADBAND_URLS = [
    "https://www.fcc.gov/sites/default/files/fixed_broadband_2023_dec_county.csv",
]

# ── Food Access Research Atlas (USDA) ──────────────────────────────

FARA_URL = (
    "https://www.ers.usda.gov/media/5627/"
    "food-access-research-atlas-data-download-2019.zip?v=21058"
)

FARA_COLUMNS_CORE = {
    "CensusTract": "TEXT",
    "Urban": "INTEGER",
    "LILATracts_1And10": "INTEGER",
    "LILATracts_halfAnd10": "INTEGER",
    "LILATracts_1And20": "INTEGER",
    "LILATracts_Vehicle": "INTEGER",
    "HUNVFlag": "INTEGER",
    "LowIncomeTracts": "INTEGER",
    "PovertyRate": "REAL",
    "MedianFamilyIncome": "INTEGER",
    "LA1and10": "INTEGER",
    "LAhalfand10": "INTEGER",
    "LATracts_half": "INTEGER",
    "LATracts1": "INTEGER",
    "LATracts10": "INTEGER",
    "LATracts20": "INTEGER",
    "LATractsVehicle_20": "INTEGER",
    "GroupQuartersFlag": "INTEGER",
    "NUMGQTRS": "INTEGER",
    "PCTGQTRS": "REAL",
    "TractHUNV": "INTEGER",
    "TractSNAP": "INTEGER",
    "TractKids": "INTEGER",
    "TractSeniors": "INTEGER",
    "Pop2010": "INTEGER",
    "OHU2010": "INTEGER",
}


def load_food_desert(force=False):
    """
    Download/cache USDA Food Access Research Atlas.
    Returns list of dicts keyed by CensusTract (11-digit FIPS).
    """
    cache_file = "food_access_research_atlas.csv"
    if _is_cached(cache_file) and not force:
        return _read_csv(cache_file)

    # Download zip as raw bytes
    import urllib.request
    req = urllib.request.Request(FARA_URL, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw_bytes = resp.read()
    except Exception:
        if os.path.exists(_cache_path(cache_file)):
            return _read_csv(cache_file)
        return []

    import io, zipfile
    z = zipfile.ZipFile(io.BytesIO(raw_bytes))
    csv_name = [n for n in z.namelist() if n.endswith(".csv") and "Food" in n][0]
    raw = z.read(csv_name).decode("utf-8", errors="replace")

    path = _cache_path(cache_file)
    with open(path, "w", encoding="utf-8") as f:
        f.write(raw)
    return _read_csv(cache_file)


def _fetch(url, timeout=30):
    """Fetch a URL with retries."""
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception:
            if attempt == MAX_RETRIES - 1:
                return None
            time.sleep(2)
    return None


def _cache_path(name):
    return os.path.join(DATA_DIR, name)


def _is_cached(name):
    path = _cache_path(name)
    if not os.path.exists(path):
        return False
    age = time.time() - os.path.getmtime(path)
    return age < CACHE_MAX_AGE


# ═══════════════════════════════════════════════════════════════════
# CBSA (Core Based Statistical Areas)
# ═══════════════════════════════════════════════════════════════════

def load_cbsa(force=False):
    """
    Load CBSA-to-county mapping. Returns list of dicts.
    Each dict: county_fips, cbsa_code, cbsa_name, metro_micro
    """
    cache_file = "cbsa_county.csv"
    if _is_cached(cache_file) and not force:
        return _read_csv(cache_file)

    for url in CBSA_URLS:
        content = _fetch(url)
        if content:
            path = _cache_path(cache_file)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return _read_csv(cache_file)

    # Fall back to cache
    if os.path.exists(_cache_path(cache_file)):
        return _read_csv(cache_file)
    return []


# ═══════════════════════════════════════════════════════════════════
# DMA (Designated Market Area) — embedded mapping
# ═══════════════════════════════════════════════════════════════════

# DMA-to-county mapping (key DMA codes for major markets)
# Source: Nielsen, embedded for reliability
DMA_COUNTY_MAP = {
    "501": "New York, NY", "803": "Los Angeles, CA", "602": "Chicago, IL",
    "504": "Philadelphia, PA", "511": "Washington, DC", "506": "Boston, MA",
    "623": "Dallas-Ft. Worth, TX", "505": "Detroit, MI", "507": "Atlanta, GA",
    "618": "Houston, TX", "819": "Seattle-Tacoma, WA", "828": "Phoenix, AZ",
    "766": "Denver, CO", "613": "Minneapolis-St. Paul, MN", "539": "Tampa-St. Pete, FL",
    "534": "Miami-Ft. Lauderdale, FL", "527": "Charlotte, SC",
    "592": "Columbia, SC", "546": "Greenville-Spartanburg, SC",
    "577": "Charleston, SC", "567": "Myrtle Beach-Florence, SC",
}

# DMA-to-county FIPS (partial — major SC + national markets)
DMA_COUNTY_FIPS = {
    "Columbia, SC": [
        "45079",  # Richland
        "45063",  # Lexington
        "45055",  # Kershaw
        "45071",  # Newberry
        "45081",  # Sumter
        "45041",  # Fairfield
        "45017",  # Calhoun
        "45085",  # Union (partial)
    ],
    "Greenville-Spartanburg, SC": [
        "45045",  # Greenville
        "45083",  # Spartanburg
        "45077",  # Pickens
        "45059",  # Laurens
        "45007",  # Anderson
        "45021",  # Cherokee
        "45091",  # Greenwood (partial)
    ],
    "Charleston, SC": [
        "45019",  # Charleston
        "45015",  # Berkeley
        "45035",  # Dorchester
        "45029",  # Colleton (partial)
    ],
    "Myrtle Beach-Florence, SC": [
        "45051",  # Horry
        "45041",  # Marion
        "45033",  # Dillon
        "45089",  # Williamsburg
        "45061",  # Lee
        "45069",  # Marlboro
        "45031",  # Darlington
        "45041",  # Florence
    ],
}


def county_to_dma(county_fips):
    """Look up DMA name from 5-digit county FIPS code."""
    for dma_name, counties in DMA_COUNTY_FIPS.items():
        if county_fips in counties:
            return dma_name
    return None


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _read_csv(name):
    path = _cache_path(name)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))
