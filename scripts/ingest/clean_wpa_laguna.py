#!/usr/bin/env python3
"""
WPA OCR Cleanup for laguna processing.
Cleans and joins fragmented OCR text.
"""
import re
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")

def join_fragments(text):
    """Join fragmented OCR lines (each word on its own line)."""
    lines = text.split('\n')
    joined = []
    buf = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if buf:
                joined.append(' '.join(buf))
                buf = []
            continue
        buf.append(stripped)
    
    if buf:
        joined.append(' '.join(buf))
    
    return '\n'.join(joined)

def extract_and_clean(filepath):
    text = filepath.read_text(encoding='utf-8', errors='replace')
    m = re.search(r'<pre[^>]*>(.*?)</pre>', text, re.DOTALL | re.IGNORECASE)
    if not m or not m.group(1).strip():
        return ""
    
    # Fix HTML entities
    content = m.group(1)
    content = content.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
    
    # Remove HTML tags
    content = re.sub(r'<[^>]+>', ' ', content)
    
    # Join fragmented lines
    content = join_fragments(content)
    
    # Remove standalone page numbers/Roman numerals
    lines = [l for l in content.split('\n') if l.strip()]
    lines = [l for l in lines if not re.match(r'^[ivxlcdmIVXLCDM]+$', l, re.IGNORECASE)]
    lines = [l for l in lines if not re.match(r'^\s*\d+\s*$', l)]
    
    return '\n'.join(lines)

def main():
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
        cleaned = extract_and_clean(filepath)
        if cleaned:
            (WPA_DIR / f"cleaned_{state}.txt").write_text(cleaned, encoding='utf-8')
            print(f"{state}: {len(cleaned):,} chars -> cleaned_{state}.txt")

if __name__ == "__main__":
    main()