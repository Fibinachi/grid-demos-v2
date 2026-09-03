#!/usr/bin/env python3
"""
Comprehensive WPA OCR cleanup for laguna processing.
Handles both directory and inventory file formats.
"""
import re
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")

def extract_text(filepath):
    """Extract OCR text from various IA formats."""
    text = filepath.read_text(encoding='utf-8', errors='replace')
    
    # Try pre block first
    m = re.search(r'<pre[^>]*>(.*?)</pre>', text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1)
    
    # Try generic content div
    m = re.search(r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>', text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1)
    
    return text

def clean_text(text):
    """Clean HTML and basic artifacts."""
    text = text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
    text = text.replace('#', 'M')  # Fix # -> M
    text = re.sub(r'<[^>]+>', ' ', text)
    
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    lines = [l for l in lines if not re.match(r'^[ivxlcdmIVXLCDM]+$', l)]
    lines = [l for l in lines if not re.match(r'^\s*\d+\s*$', l)]
    
    return '\n'.join(lines)

def main():
    files = {
        "AR": "directoryofchurc00hist_0.txt",  # Arkansas - POC
        "DE": "directoryofchurc00dela.txt",
        "DC": "directoryofchurc00dist.txt",
        "ID": "directoryofchurc00idah.txt",
        "NM": "directoryofchurc00newm.txt",
        "CA_SD": "directoryofchurc0000cali.txt",
        "CA_LA": "directoryofchurc0000cali_w5t2.txt",
        "NO": "directoryofchurc0000vari_p9s7.txt",
        "ME": "directoryofchurc00hist_2.txt",
        "MN": "directoryofchurc00unse.txt",
        "MI": "inventoryofchurc00mich.txt",
        "FL": "inventoryofchurc0006flor.txt",
        "VT": "inventoryofchurc0000verm.txt",
        "NY": "inventoryofchurc00hist_4.txt",
        "PA": "inventoryofchurc00hist_12.txt",
    }
    
    for state, fname in files.items():
        filepath = WPA_DIR / fname
        if not filepath.exists():
            print(f"SKIP {fname}: not found")
            continue
        
        raw = extract_text(filepath)
        cleaned = clean_text(raw)
        
        out_path = WPA_DIR / f"cleaned_{state}.txt"
        out_path.write_text(cleaned, encoding='utf-8')
        print(f"{state}: {len(cleaned):,} chars from {fname}")

if __name__ == "__main__":
    main()