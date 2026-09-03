"""Check shapefile polygon types."""
import geopandas as gpd

gdf = gpd.read_file(r"E:\grid\data\shapefiles\mun22gw\mun22gw.shp")
print(f"Total polygons: {len(gdf)}")
print(f"Columns: {list(gdf.columns)}")
print(f"\nCVE_MUN value distribution:")
print(gdf["CVE_MUN"].value_counts().head(20).to_string())
print(f"\nCVE_ENT value distribution:")
print(gdf["CVE_ENT"].value_counts().head(10).to_string())

# Check for rows where CVE_MUN is 0 or NaN
zero_mun = gdf[gdf["CVE_MUN"].isin(["0", 0, "000", None]) | gdf["CVE_MUN"].isna()]
print(f"\nRows with CVE_MUN=0 or NaN: {len(zero_mun)}")
if len(zero_mun) > 0:
    print(zero_mun[["CVE_ENT", "CVE_MUN", "NOMGEO"]].head(10).to_string())

# Valid municipio rows
valid = gdf[gdf["CVE_MUN"].notna() & (gdf["CVE_MUN"] != "0") & (gdf["CVE_MUN"] != 0)]
print(f"\nValid municipio polygons: {len(valid)}")
