"""Quick test: query Overture for SC to check for Kingdom Halls."""
import overturemaps, time

bbox = [-83.4, 32.0, -78.5, 35.2]
print("Querying SC places from Overture...")
t0 = time.time()
reader = overturemaps.record_batch_reader(overture_type="place", bbox=bbox)
df = reader.read_pandas()
print(f"Got {len(df):,} SC places in {time.time()-t0:.1f}s")

names = df["names"].dropna()

kh = names.apply(lambda n: isinstance(n, dict) and "kingdom hall" in str(n.get("primary", "")).lower())
jw = names.apply(lambda n: isinstance(n, dict) and "jehovah" in str(n.get("primary", "")).lower())
wt = names.apply(lambda n: isinstance(n, dict) and "watchtower" in str(n.get("primary", "")).lower())

print(f"Kingdom Hall in SC: {kh.sum()}")
print(f"Jehovah in SC name: {jw.sum()}")
print(f"Watchtower in SC: {wt.sum()}")

combined = kh | jw | wt
print(f"Total JW-like in SC: {combined.sum()}")

if combined.sum() > 0:
    for _, r in df[combined].head(20).iterrows():
        n = r.get("names", {}) or {}
        cat = r.get("categories", {}) or {}
        addr = (r.get("addresses") or [{}])[0]
        print(f'  {str(n.get("primary",""))[:50]:50s} | {addr.get("locality",""):15s} | cat: {cat.get("primary","") if isinstance(cat,dict) else ""}')
else:
    # Show what categories DO exist for SC places of worship
    worship = df[df["categories"].apply(lambda c: isinstance(c, dict) and c.get("primary") == "place_of_worship")]
    print(f"\nTotal places_of_worship in SC: {len(worship):,}")
    
    # Check brands in SC worship places
    brands = worship["brand"].dropna().apply(lambda b: b.get("name") if isinstance(b, dict) else None).value_counts()
    print("Brands in SC worship places:")
    for brand, cnt in brands.head(20).items():
        print(f"  {brand or '(none)':40s}: {cnt}")
