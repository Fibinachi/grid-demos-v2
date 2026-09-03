"""Query Overture Maps for Kingdom Halls / Jehovah's Witnesses specifically."""
import csv, os, sys
from datetime import datetime
import overturemaps

# Overture bounding box for CONUS (contiguous US)
USA_BBOX = [-124.8, 24.4, -66.9, 49.0]

def main():
    out_dir = r"E:\grid\data"
    os.makedirs(out_dir, exist_ok=True)
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Querying Overture places for CONUS...")
    print("  (this downloads the full US places dataset - may take a while)")
    
    reader = overturemaps.record_batch_reader(overture_type="place", bbox=USA_BBOX)
    df = reader.read_pandas()
    
    total = len(df)
    print(f"  Total places in US: {total:,}")
    
    # Check what categories exist
    cats = df["categories"].dropna().apply(lambda c: c.get("primary") if isinstance(c, dict) else None).value_counts()
    print(f"\n  Top categories:")
    for cat, cnt in cats.head(20).items():
        print(f"    {cat:40s}: {cnt:,}")
    
    # Search for Kingdom Halls and JW patterns
    names = df["names"].dropna()
    
    # Check names for JW patterns
    def name_contains(series, pattern):
        return series.apply(lambda n: isinstance(n, dict) and pattern.lower() in n.get("primary", "").lower())
    
    kh_mask = name_contains(names, "kingdom hall")
    jw_mask = name_contains(names, "jehovah") 
    witness_mask = name_contains(names, "witness")
    watchtower_mask = name_contains(names, "watchtower")
    
    print(f"\n  Kingdom Hall in name: {kh_mask.sum():,}")
    print(f"  Jehovah in name: {jw_mask.sum():,}")
    print(f"  Witness in name: {witness_mask.sum():,}")
    print(f"  Watchtower in name: {watchtower_mask.sum():,}")
    
    # Combined JW filter
    all_jw = kh_mask | jw_mask | witness_mask | watchtower_mask
    jw_df = df[all_jw]
    print(f"\n  Total JW-like records: {len(jw_df):,}")
    
    # Check what categories JW places have
    if len(jw_df) > 0:
        jw_cats = jw_df["categories"].dropna().apply(lambda c: c.get("primary") if isinstance(c, dict) else None).value_counts()
        print(f"\n  JW place categories:")
        for cat, cnt in jw_cats.items():
            print(f"    {cat or '(none)':40s}: {cnt}")
    
    # Save all JW results
    if len(jw_df) > 0:
        out_path = os.path.join(out_dir, "overture_jw.csv")
        records = []
        for _, row in jw_df.iterrows():
            n = row.get("names", {}) or {}
            pname = n.get("primary", "") if isinstance(n, dict) else ""
            ws = row.get("websites") or []
            ph = row.get("phones") or []
            addrs = row.get("addresses") or []
            addr = addrs[0] if len(addrs) > 0 else {}
            cat = row.get("categories", {}) or {}
            brand = row.get("brand", {}) or {}
            brand_name = brand.get("name", "") if isinstance(brand, dict) else ""
            
            records.append({
                "name": pname,
                "brand": brand_name,
                "category": cat.get("primary", "") if isinstance(cat, dict) else "",
                "website": ";".join(ws) if ws else "",
                "phone": ";".join(ph) if ph else "",
                "address": addr.get("freeform", ""),
                "city": addr.get("locality", ""),
                "state": addr.get("region", ""),
                "zip": addr.get("postcode", ""),
                "lat": row.get("bbox", {}).get("min_latitude", "") if isinstance(row.get("bbox"), dict) else "",
                "lon": row.get("bbox", {}).get("min_longitude", "") if isinstance(row.get("bbox"), dict) else "",
            })
        
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=records[0].keys())
            w.writeheader()
            w.writerows(records)
        
        print(f"\n  Saved {len(records)} records to {out_path}")
        
        # Show samples
        print(f"\n  Sample records:")
        for r in records[:10]:
            print(f"    {r['name'][:55]:55s} {r['city']:20s} {r['state']:2s}")
    else:
        print("\n  No JW records found in Overture dataset.")

if __name__ == "__main__":
    main()
