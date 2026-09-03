"""Check religious categories in Overture."""
import overturemaps

bbox = [-83.4, 32.0, -78.5, 35.2]
print("Querying Overture for SC...")
reader = overturemaps.record_batch_reader(overture_type="place", bbox=bbox)
df = reader.read_pandas()

# Extract primary category for all rows, keep as column in df
df["prim_cat"] = df["categories"].apply(
    lambda c: c.get("primary") if isinstance(c, dict) else None
)
df["sub_cat"] = df["categories"].apply(
    lambda c: c.get("subcategory") if isinstance(c, dict) else None
)

cat_counts = df["prim_cat"].value_counts()

keywords = [
    "church", "worship", "temple", "mosque", "synagogue", "chapel",
    "monastery", "convent", "shrine", "mission", "parish", "diocese",
    "religious", "faith", "kingdom", "jehovah", "cathedral", "basilica",
    "seminary", "minister", "evangelical", "ward", "stake", "congregation",
    "abbey", "gurdwara", "mandir", "spiritual", "prayer", "meditation",
    "ashram", "hermitage", "anglican", "baptist", "methodist", "lutheran",
    "presbyterian", "orthodox", "catholic", "pentecostal", "buddhist",
    "hindu", "islamic", "muslim", "jewish", "salvation", "gospel",
    "pagan", "wiccan"
]

religious = [c for c in cat_counts.index if c and any(k in c for k in keywords)]
print(f"=== RELIGIOUS CATEGORIES ({len(religious)}) ===")
for c in sorted(religious):
    cnt = cat_counts[c]
    subset = df[df["prim_cat"] == c]
    subcats = subset["sub_cat"].value_counts()
    print(f"\n{c} ({cnt:,})")
    for sc, scnt in subcats.items():
        label = sc if sc else "(none)"
        print(f"  sub: {label}: {scnt}")
