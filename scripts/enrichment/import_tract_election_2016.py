"""
Download and import tract-level 2016 presidential election results from
Harvard Dataverse (doi:10.7910/DVN/VOQCHQ).
This is the authoritative source for US election data at census tract level.

The dataset provides estimated 2016 Democratic and Republican vote shares
for every census tract in the US using precinct-to-tract crosswalks.
"""
import urllib.request
import zipfile
import os
import sqlite3
import pandas as pd
import sys

DATA_DIR = "data/tract_election_2016"
TRACT_FILE = os.path.join(DATA_DIR, "tract_election_2016.csv")
DB_PATH = "E:/grid/churches.db"

# ── Step 1: Download ──
if not os.path.exists(TRACT_FILE):
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # The Harvard Dataverse tract-level dataset (2016)
    # Direct download URL for the CSV version
    url = "https://dataverse.harvard.edu/api/access/datafile/4204036"
    
    print("Downloading tract-level 2016 election data from Harvard Dataverse...")
    print("  (This is ~15 MB, may take a moment...)")
    
    try:
        urllib.request.urlretrieve(url, os.path.join(DATA_DIR, "tract_election_2016_raw.tab"))
        print("  Downloaded successfully")
    except Exception as e:
        print(f"  Download failed: {e}")
        print("\nTrying alternative: direct CSV from Harvard Dataverse...")
        
        # Alternative: try the Harvard Dataverse direct download
        url2 = "https://dataverse.harvard.edu/api/access/datafile/:persistentId?persistentId=doi:10.7910/DVN/VOQCHQ/YFBHYU"
        try:
            urllib.request.urlretrieve(url2, os.path.join(DATA_DIR, "tract_election_2016_raw.tab"))
            print("  Downloaded via alternative URL")
        except Exception as e2:
            print(f"  Both downloads failed. Manual download needed.")
            print(f"  Go to: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/VOQCHQ")
            print(f"  Download the .tab file and save to: {DATA_DIR}/tract_election_2016_raw.tab")
            sys.exit(1)
    
    # Convert .tab to CSV (it's tab-separated)
    print("Converting to CSV...")
    df = pd.read_csv(os.path.join(DATA_DIR, "tract_election_2016_raw.tab"), sep='\t')
    df.to_csv(TRACT_FILE, index=False)
    print(f"  Saved {len(df):,} rows to {TRACT_FILE}")
else:
    print(f"File already exists: {TRACT_FILE}")

# ── Step 2: Explore columns ──
print("\n=== Dataset columns ===")
df = pd.read_csv(TRACT_FILE, nrows=0)
for c in df.columns:
    print(f"  {c}")

# Read first few rows to understand structure
df = pd.read_csv(TRACT_FILE, nrows=5)
print("\n=== Sample rows ===")
print(df.head().to_string())

print("\nImport ready. Run --import to load into SQLite.")
