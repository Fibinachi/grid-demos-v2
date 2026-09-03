"""Render 'A Million Points of Light' — cover-quality heat maps at multiple resolutions."""
import sqlite3, time, numpy as np
from PIL import Image, ImageFilter, ImageDraw, ImageFont

DB = "E:/grid/churches.db"

# Render at multiple resolutions
SIZES = {
    "hd": (1920, 1080),
    "4k": (3840, 2160),
}

db = sqlite3.connect(DB)
print("Loading coordinates...", flush=True)
t0 = time.time()
rows = db.execute("""
    SELECT lon, lat,
           CASE WHEN faith = 'Christian' THEN 0
                WHEN faith = 'Islam' THEN 1
                WHEN faith = 'Hindu' THEN 2
                WHEN faith = 'Buddhist' THEN 3
                WHEN faith = 'Jewish' THEN 4
                WHEN faith = 'Sikh' THEN 5
                WHEN faith = 'Shinto' THEN 6
                ELSE 7 END as faith_idx
    FROM holy_sites
    WHERE lat IS NOT NULL AND lat != 0
""").fetchall()
load_t = time.time() - t0
print(f"  {len(rows):,} points in {load_t:.1f}s", flush=True)

COLORS = np.array([
    [0.39, 0.59, 1.00],  # Christian - blue
    [0.20, 0.78, 0.39],  # Islam - green
    [1.0, 0.39, 0.78],   # Hindu - pink
    [0.78, 0.39, 0.20],  # Buddhist - brown
    [0.59, 0.39, 0.98],  # Jewish - purple
    [1.0, 0.78, 0.20],   # Sikh - gold
    [1.0, 0.39, 0.20],   # Shinto - orange
    [0.70, 0.70, 0.70],  # Other - grey
], dtype=np.float32)

for label, (W, H) in SIZES.items():
    print(f"\nRendering {label} ({W}x{H})...", flush=True)
    t1 = time.time()
    
    # Bin points
    density = np.zeros((H, W), dtype=np.float32)
    color_acc = np.zeros((H, W, 3), dtype=np.float32)
    
    for lon, lat, trad in rows:
        if lon is None or lat is None: continue
        x = int((float(lon) + 180) / 360 * W)
        y = int((90 - float(lat)) / 180 * H)
        if 0 <= x < W and 0 <= y < H:
            density[y, x] += 1.0
            color_acc[y, x] += COLORS[min(int(trad or 6), 6)]
    
    # Log-scale raw density per pixel FIRST (compresses US vs rest of world)
    blur_radius = 3 if "4k" in label else 2
    log_raw = np.log1p(density)  # pixel with 10000 churches → 9.2, pixel with 10 → 2.4
    density_u8 = np.clip(log_raw * 255 / max(log_raw.max(), 1), 0, 255).astype(np.uint8)
    density_blur = np.array(
        Image.fromarray(density_u8, 'L').filter(ImageFilter.GaussianBlur(radius=blur_radius))
    ).astype(np.float32) / 255.0
    
    # Same log scaling for color accumulation
    color_log = np.log1p(color_acc)
    color_u8 = np.clip(color_log * 255 / max(color_log.max(), 1), 0, 255).astype(np.uint8)
    color_blur = np.array(
        Image.fromarray(color_u8, 'RGB').filter(ImageFilter.GaussianBlur(radius=blur_radius))
    ).astype(np.float32) / 255.0
    
    # Apply gamma for contrast
    log_density = np.power(density_blur, 0.6)
    
    # ---- Grayscale cover ----
    gs = (log_density * 255).astype(np.uint8)
    gs = 255 - gs
    Image.fromarray(gs, 'L').save(f"E:/grid/cover_light_{label}.png")
    print(f"  -> cover_light_{label}.png", flush=True)
    
    # ---- Color cover ----
    norm_colors = np.zeros((H, W, 3), dtype=np.float32)
    nonzero = density_blur > 0.001
    for ch in range(3):
        norm_colors[nonzero, ch] = color_blur[nonzero, ch] / np.clip(density_blur[nonzero], 0.001, None)
    
    result = np.zeros((H, W, 3), dtype=np.float32)
    for ch in range(3):
        result[:, :, ch] = norm_colors[:, :, ch] * log_density
    
    result = np.power(np.clip(result, 0, 1), 1.0/1.3)  # Gamma for saturation
    result = (result * 255).astype(np.uint8)
    Image.fromarray(result, 'RGB').save(f"E:/grid/cover_color_{label}.png")
    print(f"  -> cover_color_{label}.png", flush=True)
    
    dt = time.time() - t1
    print(f"  {dt:.1f}s", flush=True)

db.close()
print(f"\nDone. Files: cover_light_*.png, cover_color_*.png")
print("Legend: Blue=Christian, Green=Islam, Pink=Hindu, Brown=Buddhist, Purple=Jewish, Gold=Sikh, Orange=Shinto, Grey=Other")


