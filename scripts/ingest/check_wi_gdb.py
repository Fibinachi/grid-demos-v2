"""Inspect WI V12 parcel GDB schema."""
import fiona, sys

gdb = r"E:\grid\data\wi_parcels\v12_gdb\V12.0.0_Wisconsin_Parcels_2026_10.3_Compressed\V12.0.0_Wisconsin_Parcels_2026_10.3_Compressed.gdb"

print("Layers:")
layers = fiona.listlayers(gdb)
for layer in layers:
    print(f"  {layer}")

print()
for layer in layers[:2]:
    with fiona.open(gdb, layer=layer) as src:
        print(f"=== {layer}: {len(src)} features ===")
        props = src.schema["properties"]
        for name, dtype in props.items():
            print(f"  {name:40s} {dtype}")
        print(f"  ... ({len(props)} fields total)")
        print()
        
        # Show first feature
        if len(src) > 0:
            f = next(iter(src))
            print("  Sample first feature:")
            for k, v in list(f["properties"].items())[:15]:
                print(f"    {k}: {v}")
