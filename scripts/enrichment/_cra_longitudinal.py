"""
Longitudinal analysis: Find CRA charities in 2011 that are NOT in 2018 → potentially CLOSED.
"""
import pandas as pd, sqlite3, os

PROJECT_DIR = "E:/grid"
DATA_DIR = os.path.join(PROJECT_DIR, "data", "cra")
DB_PATH = os.path.join(PROJECT_DIR, "churches.db")

# Load BNs from both CSVs
print("Loading 2011 BNs...")
df2011 = pd.read_csv(os.path.join(DATA_DIR, "cra_2011_identification.csv"), 
                     encoding="utf-8", usecols=["BN", "Legal Name", "Category", "City", "Province"])
print(f"  2011 total: {len(df2011):,}")

print("Loading 2018 BNs...")
df2018 = pd.read_csv(os.path.join(DATA_DIR, "cra_2018_identification.csv"),
                     encoding="utf-8", usecols=["BN"])
print(f"  2018 total: {len(df2018):,}")

# Religious categories for 2011
RELIGIOUS_2011 = set(range(30, 40)) | {35, 42, 43, 44, 45, 47, 48, 49, 59, 60, 61, 62}
religious2011 = df2011[df2011["Category"].isin(RELIGIOUS_2011)]
print(f"  2011 religious: {len(religious2011):,}")

bns_2011 = set(religious2011["BN"].dropna())
bns_2018 = set(df2018["BN"].dropna())

# Find closed = in 2011 but not 2018
closed_bns = bns_2011 - bns_2018
still_open_bns = bns_2011 & bns_2018

print(f"\n{'='*50}")
print(f"Religious in 2011: {len(bns_2011):,} (unique BNs)")
print(f"Religious in 2018: {len(bns_2018):,} (unique BNs)")
print(f"Still open (both years): {len(still_open_bns):,}")
print(f"CLOSED (2011 only): {len(closed_bns):,} ({100*len(closed_bns)/len(bns_2011):.1f}%)")

# Sample closed
closed_df = religious2011[religious2011["BN"].isin(closed_bns)]
print(f"\n--- Sample of closed churches ---")
by_cat = closed_df.groupby("Category").agg(
    count=("BN", "count"),
    samples=("Legal Name", lambda x: list(x.head(3)))
).sort_values("count", ascending=False)

for cat, row in by_cat.iterrows():
    print(f"  Cat {cat}: {row['count']:,} — {row['samples'][:2]}")

# By province
print(f"\n--- Closed by province ---")
by_prov = closed_df.groupby("Province").size().sort_values(ascending=False)
for prov, cnt in by_prov.items():
    print(f"  {prov}: {cnt:,}")

# Update DB: tag closed churches
db = sqlite3.connect(DB_PATH)
tagged = db.execute("""
    UPDATE churches SET notes = COALESCE(notes || '; ', '') || 'likely_closed_cra_2011_only'
    WHERE source = 'cra_2011' 
      AND cra_bn NOT IN (SELECT cra_bn FROM churches WHERE source = 'cra_2018' AND cra_bn IS NOT NULL)
      AND cra_bn IS NOT NULL
""").rowcount
print(f"\nTagged {tagged:,} churches as likely_closed in DB")
db.commit()
db.close()

# Top 20 closed cities
print(f"\n--- Top 20 cities with most closures ---")
by_city = closed_df.groupby("City").size().sort_values(ascending=False).head(20)
for city, cnt in by_city.items():
    print(f"  {city}: {cnt:,}")
