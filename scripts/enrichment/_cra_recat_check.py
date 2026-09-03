"""Verify: How many 2011 religious BNs appear in 2018 under a DIFFERENT (non-religious) category?"""
import pandas as pd

# Load full 2018 with categories
df2018 = pd.read_csv('E:/grid/data/cra/cra_2018_identification.csv', 
                     encoding='utf-8', usecols=['BN', 'Category', 'Legal Name'])
df2011 = pd.read_csv('E:/grid/data/cra/cra_2011_identification.csv',
                     encoding='utf-8', usecols=['BN', 'Category', 'Legal Name'])

# Religious categories
REL_2011 = set(range(30, 40)) | {35, 42, 43, 44, 45, 47, 48, 49, 59, 60, 61, 62}
REL_2018 = {30, 40, 50, 60, 90}

# 2011 religious → their BNs
rel2011 = df2011[df2011['Category'].isin(REL_2011)]
bns_rel2011 = set(rel2011['BN'].dropna())
print(f"2011 religious BNs: {len(bns_rel2011):,}")

# All 2018 BNs (categorized)
bns_2018_all = set(df2018['BN'].dropna())
bns_2018_religious = set(df2018[df2018['Category'].isin(REL_2018)]['BN'].dropna())

# Scenario 1: Still religious in 2018
still_religious = bns_rel2011 & bns_2018_religious
print(f"\nStill religious in 2018: {len(still_religious):,}")

# Scenario 2: Reclassified to non-religious in 2018
reclassified = bns_rel2011 & (bns_2018_all - bns_2018_religious)
print(f"Reclassified to non-religious in 2018: {len(reclassified):,}")

if len(reclassified) > 0:
    # Show examples
    recat = df2018[df2018['BN'].isin(reclassified)]
    print(f"\n  Examples of reclassified charities:")
    for _, row in recat.head(10).iterrows():
        old = rel2011[rel2011['BN'] == row['BN']]
        old_name = old['Legal Name'].values[0] if len(old) > 0 else '?'
        old_cat = old['Category'].values[0] if len(old) > 0 else '?'
        print(f"    {old_name[:60]} → Cat {row['Category']} ({row['Legal Name'][:40]})")

# Scenario 3: Truly gone (not in 2018 at all)
truly_gone = bns_rel2011 - bns_2018_all
print(f"\nTruly gone (no 2018 record): {len(truly_gone):,}")

# Summary
total = len(bns_rel2011)
print(f"\n{'='*50}")
print(f"Total 2011 religious: {total:,}")
print(f"  Still religious:    {len(still_religious):,} ({100*len(still_religious)/total:.1f}%)")
print(f"  Reclassified:       {len(reclassified):,} ({100*len(reclassified)/total:.1f}%)")
print(f"  Truly gone:         {len(truly_gone):,} ({100*len(truly_gone)/total:.1f}%)")
print(f"\nBottom line: Of {total:,} religious charities in 2011,")
print(f"  {len(truly_gone):,} ({100*len(truly_gone)/total:.1f}%) have NO 2018 CRA record at all → likely closed")
print(f"  {len(reclassified):,} ({100*len(reclassified)/total:.1f}%) are still registered but under a non-religious category")
