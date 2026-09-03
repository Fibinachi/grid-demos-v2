"""
NFHL Bounding Box Pre-computation
Extracts min_lon, min_lat, max_lon, max_lat from WKB for fast spatial indexing.
Only deserializes lightweight envelope — skips polygons that hang shapely.
Phase 1 of 2. Phase 2: run_nfhl_spatial_join.py
"""
import sqlite3, time, struct
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent.parent
WORK_DB = PROJECT / "churches_nfhl_work.db"
CHUNK_SIZE = 1000
MAX_WKB = 50_000  # Skip polygons >50KB WKB (too complex, rarely helpful)

def progress_bar(i, total, start, label=""):
    if total == 0: return
    elapsed = max(time.time() - start, 0.001)
    rate = (i+1)/elapsed
    eta = (total-i-1)/rate/60 if rate>0 else 0
    pct = (i+1)/total*100
    f = int(30*(i+1)/total)
    print(f"\r    {'█'*f}{'░'*(30-f)} {i+1:,}/{total:,} ({pct:.0f}%) {rate:.0f}/s ETA={eta:.0f}m {label}", end="", flush=True)


def extract_bbox_fast(wkb):
    """
    Extract bounding box from WKB without full geometry deserialization.
    Uses struct to parse WKB header and point data directly.
    Handles: Polygon, MultiPolygon, GeometryCollection.
    Returns (min_x, min_y, max_x, max_y) or None.
    """
    if not wkb or len(wkb) < 9:
        return None

    # Read endianness
    endian = '<' if wkb[0] == 1 else '>'
    
    # Read geometry type
    geom_type = struct.unpack(f'{endian}I', wkb[1:5])[0]
    
    # WKB geometry types (ISO)
    # 1=Point, 2=LineString, 3=Polygon, 6=MultiPolygon, 7=GeometryCollection
    
    min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
    
    def parse_polygon(data, offset):
        """Parse a WKB polygon starting at offset, update global bbox. Returns new offset."""
        nonlocal min_x, min_y, max_x, max_y
        try:
            num_rings = struct.unpack(f'{endian}I', data[offset:offset+4])[0]
            offset += 4
            for _ in range(num_rings):
                num_points = struct.unpack(f'{endian}I', data[offset:offset+4])[0]
                offset += 4
                for _ in range(num_points):
                    x, y = struct.unpack(f'{endian}dd', data[offset:offset+16])
                    offset += 16
                    if x < min_x: min_x = x
                    if x > max_x: max_x = x
                    if y < min_y: min_y = y
                    if y > max_y: max_y = y
        except struct.error:
            pass
        return offset
    
    try:
        offset = 5  # After endian + type
        
        if geom_type == 3:  # Polygon
            offset = parse_polygon(wkb, offset)
        elif geom_type == 6:  # MultiPolygon
            num_polys = struct.unpack(f'{endian}I', wkb[offset:offset+4])[0]
            offset += 4
            for _ in range(num_polys):
                # Each polygon has endian+type header
                poly_endian = '<' if wkb[offset] == 1 else '>'
                poly_type = struct.unpack(f'{poly_endian}I', wkb[offset+1:offset+5])[0]
                if poly_type == 3:
                    offset = parse_polygon(wkb, offset + 5)
                else:
                    break  # Unexpected type, bail
        elif geom_type == 7:  # GeometryCollection
            num_geoms = struct.unpack(f'{endian}I', wkb[offset:offset+4])[0]
            offset += 4
            for _ in range(num_geoms):
                if offset >= len(wkb):
                    break
                g_endian = '<' if wkb[offset] == 1 else '>'
                g_type = struct.unpack(f'{g_endian}I', wkb[offset+1:offset+5])[0]
                if g_type == 3:  # Polygon
                    offset = parse_polygon(wkb, offset + 5)
                elif g_type == 6:  # MultiPolygon
                    offset += 5
                    num_polys = struct.unpack(f'{g_endian}I', wkb[offset:offset+4])[0]
                    offset += 4
                    for _ in range(num_polys):
                        if offset >= len(wkb):
                            break
                        p_endian = '<' if wkb[offset] == 1 else '>'
                        p_type = struct.unpack(f'{p_endian}I', wkb[offset+1:offset+5])[0]
                        if p_type == 3:
                            offset = parse_polygon(wkb, offset + 5)
                        else:
                            break
                else:
                    # Unknown sub-geometry, skip
                    break
        
        if min_x == float('inf'):
            return None
        return (min_x, min_y, max_x, max_y)
    except (struct.error, IndexError):
        return None


def main():
    print("=== NFHL BBOX PRE-COMPUTATION ===\n")
    
    db = sqlite3.connect(str(WORK_DB), timeout=120)
    db.execute("PRAGMA journal_mode=WAL")
    
    # Check if bbox columns exist
    cols = [c[1] for c in db.execute("PRAGMA table_info(nfhl_flood_zones)").fetchall()]
    for col in ['min_lon', 'min_lat', 'max_lon', 'max_lat']:
        if col not in cols:
            db.execute(f"ALTER TABLE nfhl_flood_zones ADD COLUMN {col} REAL")
    db.commit()
    
    # Count unprocessed
    remaining = db.execute(
        "SELECT COUNT(*) FROM nfhl_flood_zones WHERE min_lon IS NULL"
    ).fetchone()[0]
    total = db.execute("SELECT COUNT(*) FROM nfhl_flood_zones").fetchone()[0]
    print(f"  {remaining:,} / {total:,} need bbox computation\n")
    
    if remaining == 0:
        print("All bboxes already computed!")
        db.close()
        return
    
    print("Step 1: Computing bounding boxes from WKB...")
    t0 = time.time()
    processed, skipped_size, skipped_error = 0, 0, 0
    
    rows = list(db.execute(
        "SELECT rowid, geom_wkb, fld_zone FROM nfhl_flood_zones WHERE min_lon IS NULL"
    ).fetchall())
    
    for i in range(0, len(rows), CHUNK_SIZE):
        batch = rows[i:i+CHUNK_SIZE]
        updates = []
        
        for rowid, wkb, zone in batch:
            if wkb is None or len(wkb) < 9:
                skipped_error += 1
                updates.append((None, None, None, None, rowid))
                continue
            if len(wkb) > MAX_WKB:
                skipped_size += 1
                # Still try fast extraction for large WKB
                bbox = extract_bbox_fast(wkb)
                if bbox:
                    updates.append((*bbox, rowid))
                else:
                    updates.append((None, None, None, None, rowid))
                continue
            
            # Fast native WKB parsing
            bbox = extract_bbox_fast(wkb)
            if bbox:
                updates.append((*bbox, rowid))
            else:
                skipped_error += 1
                updates.append((None, None, None, None, rowid))
        
        # Batch update
        db.execute("BEGIN")
        for min_x, min_y, max_x, max_y, rowid in updates:
            db.execute(
                "UPDATE nfhl_flood_zones SET min_lon=?, min_lat=?, max_lon=?, max_lat=? WHERE rowid=?",
                (min_x, min_y, max_x, max_y, rowid)
            )
        db.commit()
        
        processed += len(batch)
        progress_bar(processed, len(rows), t0,
                     f"ok={processed-skipped_size-skipped_error:,} skip_sz={skipped_size:,} err={skipped_error:,}")
    
    print()
    elapsed = time.time() - t0
    print(f"\n  {processed:,} processed in {elapsed:.0f}s ({processed/elapsed:.0f} rec/s)")
    print(f"  Skipped: {skipped_size:,} too large, {skipped_error:,} parse errors")
    
    # Create spatial index
    print("\nStep 2: Creating spatial index on bboxes...")
    db.execute("DROP INDEX IF EXISTS idx_nfhl_bbox")
    db.execute("""
        CREATE INDEX idx_nfhl_bbox ON nfhl_flood_zones(min_lon, min_lat, max_lon, max_lat)
    """)
    db.commit()
    
    # Summary
    valid = db.execute("SELECT COUNT(*) FROM nfhl_flood_zones WHERE min_lon IS NOT NULL").fetchone()[0]
    nulls = db.execute("SELECT COUNT(*) FROM nfhl_flood_zones WHERE min_lon IS NULL").fetchone()[0]
    print(f"  Valid bboxes: {valid:,}")
    print(f"  NULL bboxes:  {nulls:,}")
    
    db.close()
    print("\nDone. Ready for spatial join.")


if __name__ == "__main__":
    main()
