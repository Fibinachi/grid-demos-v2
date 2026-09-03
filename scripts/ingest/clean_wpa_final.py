#!/usr/bin/env python3
"""
WPA OCR Cleanup Summary - Ready for laguna processing

Files cleaned:
- AR (Arkansas POC): 231,958 chars - format: 3-column (church+address | town | county)
- DE (Delaware): 233,346 chars
- DC (District of Columbia): 175,912 chars  
- ID (Idaho): 152,249 chars
- NM (New Mexico): 203,353 chars
- ME (Maine): 261,507 chars
- MN (Minnesota): 459,215 chars
- MI (Michigan): 105,243 chars
- NY (New York): 195,586 chars
- PA_Friends (Pennsylvania): 510,177 chars

Files needing different extraction (empty pre blocks):
- CA_SD, CA_LA, FL, VT
"""
import re
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")

def extract_text(filepath):
    text = filepath.read_text(encoding='utf-8', errors='replace')
    m = re.search(r'<pre[^>]*>(.*?)</pre>', text, re.DOTALL | re.IGNORECASE)
    return m.group(1) if m and m.group(1) else ""

def clean_text(text):
    text = text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
    text = text.replace('#', 'M')
    # Remove HTML tags but keep newlines
    text = re.sub(r'<[^>]+>', '', text)
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    lines = [l for l in lines if not re.match(r'^[ivxlcdmIVXLCDM]+$', l)]
    lines = [l for l in lines if not re.match(r'^\s*\d+\s*$', l)]
    return '\n'.join(lines)

if __name__ == "__main__":
    working_files = {
        "AR": "directoryofchurc00hist_0.txt",
        "DE": "directoryofchurc00dela.txt",
        "DC": "directoryofchurc00dist.txt",
        "ID": "directoryofchurc00idah.txt",
        "NM": "directoryofchurc00newm.txt",
        "ME": "directoryofchurc00hist_2.txt",
        "MN": "directoryofchurc00unse.txt",
        "MI_Rc": "inventoryofchurc00mich.txt",
        "NY": "inventoryofchurc00hist_4.txt",
        "PA_Friends": "inventoryofchurc00hist_12.txt",
    }
    
    for state, fname in working_files.items():
        filepath = WPA_DIR / fname
        raw = extract_text(filepath)
        if raw:
            cleaned = clean_text(raw)
            (WPA_DIR / f"cleaned_{state}.txt").write_text(cleaned, encoding='utf-8')
            print(f"{state}: {len(cleaned):,} chars cleaned")