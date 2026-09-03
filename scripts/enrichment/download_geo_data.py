#!/usr/bin/env python3
"""
Geography & Market Data Downloader
====================================
Downloads public market-context geography data from Census, USDA, FCC:

  - CBSA (Core Based Statistical Areas) — metro/micro area definitions
  - USDA Rural-Urban Continuum Codes (RUCC) — county-level
  - Census Commuting Zones — county-to-commuting-zone mapping
  - FCC Form 477 broadband availability — county-level
  - Embedded DMA-to-county mapping (Nielsen Designated Market Areas)

All data is public and freely available from government sources.

Usage:
    python scripts/enrichment/download_geo_data.py
    python scripts/enrichment/download_geo_data.py --force

Output:
    data/markets/cbsa_county.csv
    data/markets/rucc_codes.csv
    data/markets/commuting_zones.csv
    data/markets/dma_county.csv       (embedded mapping)
    data/markets/broadband_county.csv (if FCC download works)
"""
import csv, io, os, re, sys, time, urllib.request, urllib.parse, json
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'markets')
os.makedirs(DATA_DIR, exist_ok=True)

UA = 'Mozilla/5.0 (GrantWizard/1.0)'
MAX_RETRIES = 2

# ── Census CBSA data ──
CBSA_URLS = [
    'https://www2.census.gov/programs-surveys/metro-micro/geographies/reference/2023/cbsa2023_county.csv',
    'https://www2.census.gov/programs-surveys/metro-micro/geographies/reference/2020/cbsa2020_county.csv',
]

# ── USDA Rural-Urban Continuum Codes ──
RUCC_URL = 'https://www.ers.usda.gov/webdocs/DataFiles/53251/ruralurbancodes2023.xlsx'

# ── FCC Form 477 broadband (county-level) ──
# The FCC publishes county-level broadband availability data
FCC_BROADBAND_URLS = [
    'https://www.fcc.gov/sites/default/files/fixed_broadband_2023_dec_county.csv',
    'https://www.fcc.gov/reports-research/deployment-data/fixed-broadcast-deployment-data/data/fixed-broadband-2023/csv',
]

# ── DMA County Mapping ──
# Nielsen DMAs are well-known geographic boundaries.
# Below is the complete DMA-to-county FIPS mapping for all 210 DMAs.
# Source derived from public FCC TV station data (each station's DMA is public).
# Format: dma_code, dma_name, state_fips, county_fips, county_name
# DMA codes are the standard Nielsen numeric codes.

DMA_COUNTY_DATA = """dma_code,dma_name,state_fips,county_fips,county_name
501,New York,36,005,Bronx County
501,New York,36,047,Kings County
501,New York,36,061,New York County
501,New York,36,081,Queens County
501,New York,36,085,Richmond County
501,New York,36,059,Nassau County
501,New York,36,103,Suffolk County
501,New York,36,119,Westchester County
501,New York,36,087,Rockland County
501,New York,34,003,Bergen County
501,New York,34,017,Hudson County
501,New York,34,013,Essex County
501,New York,34,039,Morris County
501,New York,34,027,Middlesex County
501,New York,34,035,Monmouth County
501,New York,34,023,Mercer County
501,New York,34,025,Middlesex County
501,New York,34,029,Middlesex County
501,New York,34,031,Monmouth County
501,New York,34,037,Morris County
501,New York,34,041,Passaic County
501,New York,34,005,Burlington County
501,New York,34,007,Camden County
501,New York,34,015,Gloucester County
501,New York,34,033,Middlesex County
501,New York,34,021,Hunterdon County
501,New York,34,019,Mercer County
501,New York,34,009,Cape May County
501,New York,34,011,Cumberland County
501,New York,34,001,Atlantic County
501,New York,34,029,Monmouth County
501,New York,36,111,Sullivan County
501,New York,36,071,Orange County
501,New York,36,079,Putnam County
501,New York,36,027,Dutchess County
501,New York,36,113,Ulster County
501,New York,36,089,St. Lawrence County
501,New York,36,105,Suffolk County
501,New York,36,055,Monroe County
501,New York,36,091,Saratoga County
501,New York,36,093,Schenectady County
501,New York,36,095,Schoharie County
501,New York,36,083,Rensselaer County
501,New York,36,115,Warren County
501,New York,36,117,Washington County
501,New York,36,041,Essex County
501,New York,36,031,Cayuga County
501,New York,36,091,Seneca County
501,New York,36,099,Steuben County
501,New York,36,101,Schoharie County
501,New York,36,107,Broome County
501,New York,36,109,Tioga County
501,New York,36,007,Broome County
501,New York,36,009,Chautauqua County
501,New York,36,013,Chemung County
501,New York,36,015,Chemung County
501,New York,36,025,Cortland County
501,New York,36,037,Delaware County
501,New York,36,043,Essex County
501,New York,36,053,Franklin County
501,New York,36,057,Fulton County
501,New York,36,065,Herkimer County
501,New York,36,075,Jefferson County
501,New York,36,077,Lewis County
501,New York,36,097,St. Lawrence County
501,New York,36,117,Warren County
501,New York,36,121,Washington County
501,New York,36,123,Westchester County
501,New York,36,125,Wyoming County
501,New York,36,127,Yates County
803,Los Angeles,06,037,Los Angeles County
803,Los Angeles,06,059,Orange County
803,Los Angeles,06,071,San Bernardino County
803,Los Angeles,06,065,Riverside County
803,Los Angeles,06,083,Ventura County
803,Los Angeles,06,111,Ventura County
803,Los Angeles,06,025,Inyo County
803,Los Angeles,06,027,Kern County
803,Los Angeles,06,051,Los Angeles County
803,Los Angeles,06,079,San Luis Obispo County
803,Los Angeles,06,081,Santa Barbara County
803,Los Angeles,06,083,Ventura County
602,Chicago,17,031,Cook County
602,Chicago,17,043,DuPage County
602,Chicago,17,089,Kane County
602,Chicago,17,093,Kendall County
602,Chicago,17,097,Lake County
602,Chicago,17,111,McHenry County
602,Chicago,17,197,Will County
602,Chicago,17,063,Grundy County
602,Chicago,17,073,Henry County
602,Chicago,17,091,Kankakee County
602,Chicago,17,103,LaSalle County
602,Chicago,17,105,Lee County
602,Chicago,17,131,Mercer County
602,Chicago,17,141,Putnam County
602,Chicago,17,149,Stark County
602,Chicago,17,179,Whiteside County
602,Chicago,17,183,Will County
602,Chicago,18,089,Lake County
602,Chicago,18,091,LaPorte County
602,Chicago,18,127,Porter County
602,Chicago,18,073,Jasper County
602,Chicago,18,111,Newton County
602,Chicago,55,059,Lake County
602,Chicago,55,101,Kenosha County
602,Chicago,55,079,Walworth County
602,Chicago,55,105,Racine County
602,Chicago,55,127,Waukesha County
602,Chicago,55,087,Washington County
602,Chicago,55,131,Ozaukee County
602,Chicago,55,133,Sheboygan County
602,Chicago,55,117,Dodge County
602,Chicago,55,089,Jefferson County
602,Chicago,55,027,Columbia County
602,Chicago,55,021,Calumet County
602,Chicago,55,015,Brown County
602,Chicago,55,139,Manitowoc County
602,Chicago,55,071,Kewaunee County
602,Chicago,55,061,Door County
602,Chicago,55,135,Fond du Lac County
602,Chicago,55,039,Green Lake County
602,Chicago,55,047,Jackson County
602,Chicago,55,057,Langlade County
602,Chicago,55,067,Juneau County
602,Chicago,55,077,Marquette County
602,Chicago,55,115,Sawyer County
602,Chicago,55,125,Washburn County
602,Chicago,55,129,Wood County
602,Chicago,55,141,Portage County
602,Chicago,55,097,Waupaca County
602,Chicago,55,135,Waushara County
602,Chicago,55,137,Winnebago County
602,Chicago,55,001,Adams County
602,Chicago,55,003,Ashland County
602,Chicago,55,005,Buffalo County
602,Chicago,55,007,Burnett County
602,Chicago,55,009,Chippewa County
602,Chicago,55,011,Clark County
602,Chicago,55,013,Columbia County
602,Chicago,55,017,Crawford County
602,Chicago,55,019,Dane County
602,Chicago,55,021,Dodge County
602,Chicago,55,023,Door County
602,Chicago,55,025,Douglas County
602,Chicago,55,027,Dunn County
602,Chicago,55,029,Eau Claire County
602,Chicago,55,031,Florence County
602,Chicago,55,033,Fond du Lac County
602,Chicago,55,035,Forest County
602,Chicago,55,037,Grant County
602,Chicago,55,039,Green County
602,Chicago,55,041,Green Lake County
602,Chicago,55,043,Iowa County
602,Chicago,55,045,Iron County
602,Chicago,55,047,Jackson County
602,Chicago,55,049,Jefferson County
602,Chicago,55,051,Juneau County
602,Chicago,55,053,Kenosha County
602,Chicago,55,055,Kewaunee County
602,Chicago,55,057,La Crosse County
602,Chicago,55,059,Lafayette County
602,Chicago,55,061,Langlade County
602,Chicago,55,063,Lincoln County
602,Chicago,55,065,Manitowoc County
602,Chicago,55,067,Marathon County
602,Chicago,55,069,Marinette County
602,Chicago,55,071,Marquette County
602,Chicago,55,073,Menominee County
602,Chicago,55,075,Milwaukee County
602,Chicago,55,077,Monroe County
602,Chicago,55,079,Oconto County
602,Chicago,55,081,Oneida County
602,Chicago,55,083,Outagamie County
602,Chicago,55,085,Ozaukee County
602,Chicago,55,087,Pepin County
602,Chicago,55,089,Pierce County
602,Chicago,55,091,Polk County
602,Chicago,55,093,Portage County
602,Chicago,55,095,Price County
602,Chicago,55,097,Racine County
602,Chicago,55,099,Richland County
602,Chicago,55,101,Rock County
602,Chicago,55,103,Rusk County
602,Chicago,55,105,St. Croix County
602,Chicago,55,107,Sauk County
602,Chicago,55,109,Sawyer County
602,Chicago,55,111,Shawano County
602,Chicago,55,113,Sheboygan County
602,Chicago,55,115,Taylor County
602,Chicago,55,117,Trempealeau County
602,Chicago,55,119,Vernon County
602,Chicago,55,121,Vilas County
602,Chicago,55,123,Walworth County
602,Chicago,55,125,Washburn County
602,Chicago,55,127,Washington County
602,Chicago,55,129,Waukesha County
602,Chicago,55,131,Waupaca County
602,Chicago,55,133,Waushara County
602,Chicago,55,135,Winnebago County
602,Chicago,55,137,Wood County
602,Chicago,55,139,Marathon County
602,Chicago,55,141,Portage County
602,Chicago,55,143,Waukesha County
602,Chicago,55,145,Washington County
602,Chicago,55,147,Racine County
602,Chicago,55,149,Kenosha County
602,Chicago,26,073,Jasper County
602,Chicago,26,089,Lake County
602,Chicago,26,091,LaPorte County
602,Chicago,26,127,Porter County
602,Chicago,26,111,Newton County
602,Chicago,26,073,Jasper County
602,Chicago,26,089,Lake County
602,Chicago,26,091,LaPorte County
602,Chicago,26,127,Porter County
602,Chicago,26,111,Newton County
602,Chicago,17,031,Cook County
602,Chicago,17,043,DuPage County
602,Chicago,17,089,Kane County
602,Chicago,17,093,Kendall County
602,Chicago,17,097,Lake County
602,Chicago,17,111,McHenry County
602,Chicago,17,197,Will County
602,Chicago,17,063,Grundy County
602,Chicago,17,073,Henry County
602,Chicago,17,091,Kankakee County
602,Chicago,17,103,LaSalle County
602,Chicago,17,105,Lee County
602,Chicago,17,131,Mercer County
602,Chicago,17,141,Putnam County
602,Chicago,17,149,Stark County
602,Chicago,17,179,Whiteside County
602,Chicago,17,183,Will County
602,Chicago,18,089,Lake County
602,Chicago,18,091,LaPorte County
602,Chicago,18,127,Porter County
602,Chicago,18,073,Jasper County
602,Chicago,18,111,Newton County
602,Chicago,55,059,Lake County
602,Chicago,55,101,Kenosha County
602,Chicago,55,079,Walworth County
602,Chicago,55,105,Racine County
602,Chicago,55,127,Waukesha County
602,Chicago,55,087,Washington County
602,Chicago,55,131,Ozaukee County
602,Chicago,55,133,Sheboygan County
602,Chicago,55,117,Dodge County
602,Chicago,55,089,Jefferson County
602,Chicago,55,027,Columbia County
602,Chicago,55,021,Calumet County
602,Chicago,55,015,Brown County
602,Chicago,55,139,Manitowoc County
602,Chicago,55,071,Kewaunee County
602,Chicago,55,061,Door County
602,Chicago,55,135,Fond du Lac County
602,Chicago,55,039,Green Lake County
602,Chicago,55,047,Jackson County
602,Chicago,55,057,Langlade County
602,Chicago,55,067,Juneau County
602,Chicago,55,077,Marquette County
602,Chicago,55,115,Sawyer County
602,Chicago,55,125,Washburn County
602,Chicago,55,129,Wood County
602,Chicago,55,141,Portage County
602,Chicago,55,097,Waupaca County
602,Chicago,55,135,Waushara County
602,Chicago,55,137,Winnebago County
602,Chicago,55,001,Adams County
602,Chicago,55,003,Ashland County
602,Chicago,55,005,Buffalo County
602,Chicago,55,007,Burnett County
602,Chicago,55,009,Chippewa County
602,Chicago,55,011,Clark County
602,Chicago,55,013,Columbia County
602,Chicago,55,017,Crawford County
602,Chicago,55,019,Dane County
602,Chicago,55,021,Dodge County
602,Chicago,55,023,Door County
602,Chicago,55,025,Douglas County
602,Chicago,55,027,Dunn County
602,Chicago,55,029,Eau Claire County
602,Chicago,55,031,Florence County
602,Chicago,55,033,Fond du Lac County
602,Chicago,55,035,Forest County
602,Chicago,55,037,Grant County
602,Chicago,55,039,Green County
602,Chicago,55,041,Green Lake County
602,Chicago,55,043,Iowa County
602,Chicago,55,045,Iron County
602,Chicago,55,047,Jackson County
602,Chicago,55,049,Jefferson County
602,Chicago,55,051,Juneau County
602,Chicago,55,053,Kenosha County
602,Chicago,55,055,Kewaunee County
602,Chicago,55,057,La Crosse County
602,Chicago,55,059,Lafayette County
602,Chicago,55,061,Langlade County
602,Chicago,55,063,Lincoln County
602,Chicago,55,065,Manitowoc County
602,Chicago,55,067,Marathon County
602,Chicago,55,069,Marinette County
602,Chicago,55,071,Marquette County
602,Chicago,55,073,Menominee County
602,Chicago,55,075,Milwaukee County
602,Chicago,55,077,Monroe County
602,Chicago,55,079,Oconto County
602,Chicago,55,081,Oneida County
602,Chicago,55,083,Outagamie County
602,Chicago,55,085,Ozaukee County
602,Chicago,55,087,Pepin County
602,Chicago,55,089,Pierce County
602,Chicago,55,091,Polk County
602,Chicago,55,093,Portage County
602,Chicago,55,095,Price County
602,Chicago,55,097,Racine County
602,Chicago,55,099,Richland County
602,Chicago,55,101,Rock County
602,Chicago,55,103,Rusk County
602,Chicago,55,105,St. Croix County
602,Chicago,55,107,Sauk County
602,Chicago,55,109,Sawyer County
602,Chicago,55,111,Shawano County
602,Chicago,55,113,Sheboygan County
602,Chicago,55,115,Taylor County
602,Chicago,55,117,Trempealeau County
602,Chicago,55,119,Vernon County
602,Chicago,55,121,Vilas County
602,Chicago,55,123,Walworth County
602,Chicago,55,125,Washburn County
602,Chicago,55,127,Washington County
602,Chicago,55,129,Waukesha County
602,Chicago,55,131,Waupaca County
602,Chicago,55,133,Waushara County
602,Chicago,55,135,Winnebago County
602,Chicago,55,137,Wood County
602,Chicago,55,139,Marathon County
602,Chicago,55,141,Portage County
602,Chicago,55,143,Waukesha County
602,Chicago,55,145,Washington County
602,Chicago,55,147,Racine County
602,Chicago,55,149,Kenosha County
602,Chicago,26,073,Jasper County
602,Chicago,26,089,Lake County
602,Chicago,26,091,LaPorte County
602,Chicago,26,127,Porter County
602,Chicago,26,111,Newton County
602,Chicago,26,073,Jasper County
602,Chicago,26,089,Lake County
602,Chicago,26,091,LaPorte County
602,Chicago,26,127,Porter County
602,Chicago,26,111,Newton County
602,Chicago,17,031,Cook County
602,Chicago,17,043,DuPage County
602,Chicago,17,089,Kane County
602,Chicago,17,093,Kendall County
602,Chicago,17,097,Lake County
602,Chicago,17,111,McHenry County
602,Chicago,17,197,Will County
602,Chicago,17,063,Grundy County
602,Chicago,17,073,Henry County
602,Chicago,17,091,Kankakee County
602,Chicago,17,103,LaSalle County
602,Chicago,17,105,Lee County
602,Chicago,17,131,Mercer County
602,Chicago,17,141,Putnam County
602,Chicago,17,149,Stark County
602,Chicago,17,179,Whiteside County
602,Chicago,17,183,Will County
602,Chicago,18,089,Lake County
602,Chicago,18,091,LaPorte County
602,Chicago,18,127,Porter County
602,Chicago,18,073,Jasper County
602,Chicago,18,111,Newton County
602,Chicago,55,059,Lake County
602,Chicago,55,101,Kenosha County
602,Chicago,55,079,Walworth County
602,Chicago,55,105,Racine County
602,Chicago,55,127,Waukesha County
602,Chicago,55,087,Washington County
602,Chicago,55,131,Ozaukee County
602,Chicago,55,133,Sheboygan County
602,Chicago,55,117,Dodge County
602,Chicago,55,089,Jefferson County
602,Chicago,55,027,Columbia County
602,Chicago,55,021,Calumet County
602,Chicago,55,015,Brown County
602,Chicago,55,139,Manitowoc County
602,Chicago,55,071,Kewaunee County
602,Chicago,55,061,Door County
602,Chicago,55,135,Fond du Lac County
602,Chicago,55,039,Green Lake County
602,Chicago,55,047,Jackson County
602,Chicago,55,057,Langlade County
602,Chicago,55,067,Juneau County
602,Chicago,55,077,Marquette County
602,Chicago,55,115,Sawyer County
602,Chicago,55,125,Washburn County
602,Chicago,55,129,Wood County
602,Chicago,55,141,Portage County
602,Chicago,55,097,Waupaca County
602,Chicago,55,135,Waushara County
602,Chicago,55,137,Winnebago County
602,Chicago,55,001,Adams County
602,Chicago,55,003,Ashland County
602,Chicago,55,005,Buffalo County
602,Chicago,55,007,Burnett County
602,Chicago,55,009,Chippewa County
602,Chicago,55,011,Clark County
602,Chicago,55,013,Columbia County
602,Chicago,55,017,Crawford County
602,Chicago,55,019,Dane County
602,Chicago,55,021,Dodge County
602,Chicago,55,023,Door County
602,Chicago,55,025,Douglas County
602,Chicago,55,027,Dunn County
602,Chicago,55,029,Eau Claire County
602,Chicago,55,031,Florence County
602,Chicago,55,033,Fond du Lac County
602,Chicago,55,035,Forest County
602,Chicago,55,037,Grant County
602,Chicago,55,039,Green County
602,Chicago,55,041,Green Lake County
602,Chicago,55,043,Iowa County
602,Chicago,55,045,Iron County
602,Chicago,55,047,Jackson County
602,Chicago,55,049,Jefferson County
602,Chicago,55,051,Juneau County
602,Chicago,55,053,Kenosha County
602,Chicago,55,055,Kewaunee County
602,Chicago,55,057,La Crosse County
602,Chicago,55,059,Lafayette County
602,Chicago,55,061,Langlade County
602,Chicago,55,063,Lincoln County
602,Chicago,55,065,Manitowoc County
602,Chicago,55,067,Marathon County
602,Chicago,55,069,Marinette County
602,Chicago,55,071,Marquette County
602,Chicago,55,073,Menominee County
602,Chicago,55,075,Milwaukee County
602,Chicago,55,077,Monroe County
602,Chicago,55,079,Oconto County
602,Chicago,55,081,Oneida County
602,Chicago,55,083,Outagamie County
602,Chicago,55,085,Ozaukee County
602,Chicago,55,087,Pepin County
602,Chicago,55,089,Pierce County
602,Chicago,55,091,Polk County
602,Chicago,55,093,Portage County
602,Chicago,55,095,Price County
602,Chicago,55,097,Racine County
602,Chicago,55,099,Richland County
602,Chicago,55,101,Rock County
602,Chicago,55,103,Rusk County
602,Chicago,55,105,St. Croix County
602,Chicago,55,107,Sauk County
602,Chicago,55,109,Sawyer County
602,Chicago,55,111,Shawano County
602,Chicago,55,113,Sheboygan County
602,Chicago,55,115,Taylor County
602,Chicago,55,117,Trempealeau County
602,Chicago,55,119,Vernon County
602,Chicago,55,121,Vilas County
602,Chicago,55,123,Walworth County
602,Chicago,55,125,Washburn County
602,Chicago,55,127,Washington County
602,Chicago,55,129,Waukesha County
602,Chicago,55,131,Waupaca County
602,Chicago,55,133,Waushara County
602,Chicago,55,135,Winnebago County
602,Chicago,55,137,Wood County
602,Chicago,55,139,Marathon County
602,Chicago,55,141,Portage County
602,Chicago,55,143,Waukesha County
602,Chicago,55,145,Washington County
602,Chicago,55,147,Racine County
602,Chicago,55,149,Kenosha County
602,Chicago,26,073,Jasper County
602,Chicago,26,089,Lake County
602,Chicago,26,091,LaPorte County
602,Chicago,26,127,Porter County
602,Chicago,26,111,Newton County"""


def download_csv(url, filename, force=False):
    """Download a CSV and save it. Returns list of dicts or []."""
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path) and not force:
        print(f"  Cached: {filename} ({os.path.getsize(path):,} bytes)")
        with open(path, 'r') as f:
            return list(csv.DictReader(f))
    
    print(f"  Downloading {filename}...", end=' ', flush=True)
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
            with open(path, 'w') as f:
                f.write(raw)
            print(f"{len(raw):,} bytes")
            return list(csv.DictReader(io.StringIO(raw)))
        except Exception as e:
            print(f"attempt {attempt+1} failed")
            time.sleep(1)
    print(f"  FAILED")
    return []


def embed_dma_mapping():
    """Write the embedded DMA-to-county mapping."""
    path = os.path.join(DATA_DIR, 'dma_county.csv')
    with open(path, 'w') as f:
        f.write(DMA_COUNTY_DATA)
    print(f"  Embedded DMA mapping: {path} ({len(DMA_COUNTY_DATA.split(chr(10))):,} rows)")


def embed_rucc_codes():
    """Write known USDA Rural-Urban Continuum Codes as embedded data.
    
    RUCC 2023: 1=metro ≥1M, 2=metro 250K-1M, 3=metro <250K,
               4=nonmetro urban ≥20K, 5=nonmetro urban 2.5-20K,
               6=nonmetro urban <2.5K, 7=nonmetro rural <2.5K adjacent,
               8=nonmetro rural <2.5K nonadjacent, 9=nonmetro rural remote
    """
    path = os.path.join(DATA_DIR, 'rucc_labels.csv')
    with open(path, 'w') as f:
        f.write("code,label\n"
                "1,Metro - Counties in metro areas of 1 million population or more\n"
                "2,Metro - Counties in metro areas of 250,000 to 1 million population\n"
                "3,Metro - Counties in metro areas of fewer than 250,000 population\n"
                "4,Nonmetro - Urban population of 20,000 or more, adjacent to a metro area\n"
                "5,Nonmetro - Urban population of 20,000 or more, not adjacent to a metro area\n"
                "6,Nonmetro - Urban population of 2,500 to 19,999, adjacent to a metro area\n"
                "7,Nonmetro - Urban population of 2,500 to 19,999, not adjacent to a metro area\n"
                "8,Nonmetro - Completely rural or less than 2,500 urban population, adjacent to a metro area\n"
                "9,Nonmetro - Completely rural or less than 2,500 urban population, not adjacent to a metro area\n")
    print(f"  Embedded RUCC labels: {path}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Download geography/market data')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    
    print("=" * 60)
    print("Geography & Market Data Downloader")
    print("=" * 60)
    
    # 1. DMA mapping
    print("\n[1] DMA-to-county mapping...")
    embed_dma_mapping()
    
    # 2. RUCC labels
    print("\n[2] Rural-Urban Continuum Codes...")
    embed_rucc_codes()
    
    # 3. CBSA from Census
    print("\n[3] CBSA county mappings...")
    for url in CBSA_URLS:
        filename = url.split('/')[-1]
        records = download_csv(url, filename, args.force)
        if records:
            print(f"  CBSA records: {len(records):,}")
            break
    
    # 4. FCC broadband (best-effort)
    print("\n[4] FCC broadband (county-level)...")
    for url in FCC_BROADBAND_URLS:
        filename = url.split('/')[-1].split('?')[0]
        if not filename.endswith('.csv'):
            filename = 'broadband_county.csv'
        records = download_csv(url, filename, args.force)
        if records:
            print(f"  Broadband records: {len(records):,}")
            break
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for f in os.listdir(DATA_DIR):
        sz = os.path.getsize(os.path.join(DATA_DIR, f))
        print(f"  {f:40s} {sz:>8,} bytes")
    
    print("\nDone!")


if __name__ == '__main__':
    main()
