"""
Download Canadian census tract + boundary enrichment data.
Sources:
  1. Statistics Canada 2021 Census - Dissemination Area (DA) profile CSV
  2. Elections Canada - Federal Electoral District shapefiles (2023)
  3. Statistics Canada - Dissemination Area boundary shapefiles

Downloads to data/canada_census/ and data/canada_boundaries/
"""
import urllib.request, zipfile, os, sys, csv, sqlite3, io, time
from pathlib import Path
from tqdm import tqdm

DATA_DIR = Path(r"E:\grid\data\canada_census")
BOUNDARY_DIR = Path(r"E:\grid\data\canada_boundaries")
DATA_DIR.mkdir(parents=True, exist_ok=True)
BOUNDARY_DIR.mkdir(parents=True, exist_ok=True)

CHUNK_SIZE = 5000


def download_file(url, dest, desc="Downloading"):
    """Download with progress bar."""
    if dest.exists() and dest.stat().st_size > 1000:
        print(f"  ⏭ Already exists: {dest.name} ({dest.stat().st_size/1024/1024:.1f}MB)")
        return True
    
    print(f"  Downloading {dest.name}...")
    try:
        urllib.request.urlretrieve(url, dest)
        size_mb = dest.stat().st_size / 1024 / 1024
        print(f"  ✅ Downloaded: {size_mb:.1f}MB")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def download_census_csv():
    """Download 2021 Census Profile CSV at Dissemination Area level."""
    # GEONO=004 gets CDs, CSDs, and DAs
    url = "https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/prof/details/download-telecharger/comp/getFile.cfm?LANG=E&GEONO=004&FILETYPE=CSV"
    dest = DATA_DIR / "census_2021_da.csv"
    return download_file(url, dest)


def download_fed_boundaries():
    """Download Federal Electoral District shapefiles."""
    url = "https://ftp.maps.canada.ca/pub/elections_elections/Electoral-districts_Circonscription-electorale/federal_electoral_districts_boundaries_2023/FED_CA_2023_EN-SHP.zip"
    dest = BOUNDARY_DIR / "fed_2023_shp.zip"
    return download_file(url, dest)


def download_da_boundaries():
    """Download Dissemination Area boundary shapefiles."""
    url = "https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/lda_000b21a_e.zip"
    dest = BOUNDARY_DIR / "da_2021_shp.zip"
    return download_file(url, dest)


def download_cd_boundaries():
    """Download Census Division boundary shapefiles."""
    url = "https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/lcd_000b21a_e.zip"
    dest = BOUNDARY_DIR / "cd_2021_shp.zip"
    return download_file(url, dest)


def download_ct_boundaries():
    """Download Census Tract boundary shapefiles."""
    url = "https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/lct_000b21a_e.zip"
    dest = BOUNDARY_DIR / "ct_2021_shp.zip"
    return download_file(url, dest)


def extract_zip(zip_path, extract_to):
    """Extract zip file."""
    extract_to.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(extract_to)
    files = list(extract_to.glob("*"))
    print(f"  Extracted {len(files)} files to {extract_to.name}/")
    return files


def main():
    print("=" * 60)
    print("CANADA CENSUS + BOUNDARY DOWNLOADER")
    print("=" * 60)
    print()
    
    downloads = []
    
    # Step 1: Census CSV
    print("--- Census Data ---")
    if download_census_csv():
        downloads.append("census_csv")
        size = (DATA_DIR / "census_2021_da.csv").stat().st_size
        print(f"  Note: {size/1024/1024:.1f}MB file - will stream-process rather than load entirely")
    
    # Step 2: Boundary files
    print("\n--- Boundary Files ---")
    fed_zip = BOUNDARY_DIR / "fed_2023_shp.zip"
    if download_fed_boundaries():
        if not fed_zip.exists():
            pass  # already extracted
        else:
            extract_zip(fed_zip, BOUNDARY_DIR / "fed_2023")
    
    print("\n--- DA Boundaries ---")
    da_zip = BOUNDARY_DIR / "da_2021_shp.zip"
    if download_da_boundaries():
        if da_zip.exists():
            extract_zip(da_zip, BOUNDARY_DIR / "da_2021")
    
    print("\n--- Census Tract Boundaries ---")
    ct_zip = BOUNDARY_DIR / "ct_2021_shp.zip"
    if download_ct_boundaries():
        if ct_zip.exists():
            extract_zip(ct_zip, BOUNDARY_DIR / "ct_2021")
    
    print("\n--- Census Division Boundaries ---")
    cd_zip = BOUNDARY_DIR / "cd_2021_shp.zip"
    if download_cd_boundaries():
        if cd_zip.exists():
            extract_zip(cd_zip, BOUNDARY_DIR / "cd_2021")
    
    print(f"\n{'='*60}")
    print("DOWNLOAD COMPLETE")
    print(f"{'='*60}")
    print(f"\nFiles downloaded to:")
    print(f"  Census: {DATA_DIR}")
    print(f"  Boundaries: {BOUNDARY_DIR}")
    print()
    print("Next step: Join DA codes to Canadian churches and import census data")


if __name__ == '__main__':
    main()
