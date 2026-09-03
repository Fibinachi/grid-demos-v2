"""Try reading WI GDB with geopandas."""
import sys
sys.path.insert(0, r"E:\grid\.venv\Lib\site-packages")

try:
    import geopandas as gpd
    print(f"geopandas {gpd.__version__}")
    
    gdb = r"E:\grid\data\wi_parcels\v12_gdb\V12.0.0_Wisconsin_Parcels_2026_10.3_Compressed\V12.0.0_Wisconsin_Parcels_2026_10.3_Compressed.gdb"
    
    # Try reading
    print("Reading GDB...")
    gdf = gpd.read_file(gdb, rows=1000)
    print(f"Read {len(gdf)} rows")
    print(f"Columns: {list(gdf.columns)[:20]}")
    
    # Check AUXCLASS values
    if "AUXCLASS" in gdf.columns:
        print(f"\nAUXCLASS unique values: {gdf['AUXCLASS'].unique()[:20]}")
        print(f"AUXCLASS value counts: {gdf['AUXCLASS'].value_counts()}")
    else:
        print("\nAUXCLASS not in columns")
    
    # Check PROPCLASS
    if "PROPCLASS" in gdf.columns:
        print(f"\nPROPCLASS sample: {gdf['PROPCLASS'].value_counts().head(10)}")
    
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
