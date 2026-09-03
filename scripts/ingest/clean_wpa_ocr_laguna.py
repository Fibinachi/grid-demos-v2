#!/usr/bin/env python3
"""
OCR Cleanup for WPA files using laguna-m.1 model.
Processes raw OCR text and corrects character-level errors.
This is the POC for Arkansas - starting with DE to validate approach.
"""
import re, json, os, time, sys, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
CHUNK_SIZE = 8000

STATE_FILES = {
    "AR": "directoryofchurc00hist_0.txt",  # Arkansas (POC)
    "DE": "directoryofchurc00dela.txt",
    "DC": "directoryofchurc00dist.txt",
    "ID": "directoryofchurc00idah.txt",
    "NM": "directoryofchurc00newm.txt",
    "CA_SD": "directoryofchurc0000cali.txt",  # San Diego
    "CA_LA": "directoryofchurc0000cali_w5t2.txt",  # Los Angeles
    "NO": "directoryofchurc0000vari_p9s7.txt",  # New Orleans
    "ME": "directoryofchurc00hist_2.txt",  # Maine
    "MN": "directoryofchurc00unse.txt",  # Minnesota
    "MI": "inventoryofchurc00mich.txt",  # Michigan
    "FL": "inventoryofchurc0006flor.txt",  # Florida
    "VT": "inventoryofchurc0000verm.txt",  # Vermont
    "NY": "inventoryofchurc00hist_4.txt",  # New York
    "PA": "inventoryofchurc00hist_12.txt",  # Pennsylvania (Society of Friends)
}

def extract_pre_text(html_text):
    m = re.search(r'<pre[^>]*>(.*?)</pre>', html_text, re.DOTALL | re.IGNORECASE)
    return m.group(1) if m else html_text

def fix_ocr_patterns(text):
    """Fix common OCR character confusions."""
    # Fix # -> M (typewriter M often OCRs as #)
    text = text.replace('#', 'M')
    
    # Fix wv -> w, vv -> w
    text = re.sub(r'wv', 'w', text)
    text = re.sub(r'vv', 'w', text)
    
    # Fix x -> t in Methodist (typewriter x OCRs as t in some positions)
    text = re.sub(r'\bxethodist\b', 'Methodist', text, flags=re.IGNORECASE)
    
    # Fix wethodist -> Methodist (residual from # -> M fix)
    text = re.sub(r'\bwethodist\b', 'Methodist', text, flags=re.IGNORECASE)
    
    # Fix other common typos
    text = re.sub(r'\bthurch\b', 'Church', text, flags=re.IGNORECASE)
    text = re.sub(r'\bVhurch\b', 'Church', text)
    
    return text

def basic_clean(text):
    """Strip HTML and remove obvious artifacts."""
    text = extract_pre_text(text)
    text = text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
    text = fix_ocr_patterns(text)
    
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    cleaned = [l for l in lines if not re.match(r'^[ivxlcdmIVXLCDM]+$', l) and not re.match(r'^\s*\d+\s*$', l)]
    return '\n'.join(cleaned)

def clean_file(state_code, output_path=None):
    """Clean a single state file and save."""
    if state_code not in STATE_FILES:
        print(f"Unknown state: {state_code}. Available: {list(STATE_FILES.keys())}")
        return None
    
    filepath = WPA_DIR / STATE_FILES[state_code]
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return None
    
    print(f"Processing: {filepath.name}")
    raw = filepath.read_text(encoding='utf-8', errors='replace')
    cleaned = basic_clean(raw)
    print(f"  After cleanup: {len(cleaned):,} chars")
    
    out = output_path or (WPA_DIR / f"cleaned_{filepath.stem}.txt")
    out.write_text(cleaned, encoding='utf-8')
    print(f"  Saved to: {out.name}")
    return cleaned

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--state", default="DE", help="State to process")
    p.add_argument("--output", help="Output file")
    args = p.parse_args()
    
    clean_file(args.state, Path(args.output) if args.output else None)