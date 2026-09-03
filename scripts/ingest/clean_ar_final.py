#!/usr/bin/env python3
"""
Clean Arkansas entries properly - split concatenated names.
"""
import re, json, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")

def split_concatenated(text):
    """Split concatenated church entries."""
    # Pattern: "ChurchA (Rt. X) ChurchB (Rt. Y)" should be separate
    # Split on patterns like "(Rt." followed by church name
    
    # Split on common church prefixes followed by routes
    parts = re.split(r'\s+(?:Assembly|First|Second|Third|Mt\.|Bethel|Bethany|Bethlehem|Pleasant|Oak|Rock|New|Old|Union)\s+(?:Church|Chapel|Congregation)', text, flags=re.IGNORECASE)
    
    # Also split on standalone route markers
    result = []
    for p in parts:
        # Extract individual churches
        churches = re.findall(r'([A-Z][A-Za-z][A-Za-z\s\-\']{3,})\s*\((?:Rt\.|R\. F\. D\.)\s*([\d\-–]+[^)]*)\)', p)
        result.extend(churches)
    
    return result

def extract_clean(text):
    """Extract clean individual church entries."""
    entries = []
    
    for match in re.finditer(r'([A-Z][A-Za-z][A-Za-z\s\-\']{3,})\s*\((?:Rt\.|R\. F\. D\.)\s*([\d\-–]+[^)]*)\)', text):
        name = match.group(1).strip('. ,;-')
        # Skip concatenated entries (check if contains multiple route markers)
        if text.count('(Rt.') > 1 or text.count('R. F. D.') > 1:
            # Split it
            parts = split_concatenated(text)
            for p_name, p_route in parts:
                p_name = p_name.strip('. ,;-')
                if len(p_name) > 5:
                    entries.append(p_name)
            break
        else:
            entries.append(name)
    
    return entries

# Load and process Arkansas
text = (WPA_DIR / "final_AR.txt").read_text(encoding='utf-8', errors='replace')
entries = extract_clean(text)

print(f"Extracted {len(entries)} entries")

# Now let's try a simpler approach - each line that matches route pattern
lines = text.split('\n')
simple_entries = []
for line in lines:
    matches = re.findall(r'([A-Z][A-Za-z][A-Za-z\s\-\']{3,})\s*\((?:Rt\.|R\. F\. D\.)\s*([\d\-–]+[^)]*)\)', line)
    for name, route in matches:
        name = name.strip('. ,;-')
        if len(name) > 5:
            simple_entries.append(name)

# Dedup
unique = list(dict.fromkeys(simple_entries))
print(f"Simple extraction: {len(unique)} unique entries")

# Save
(WPA_DIR / "clean_ar_final.json").write_text(json.dumps(unique, indent=2), encoding='utf-8')

# Import
conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()
cur.execute("DELETE FROM wpa_churches")
for name in unique[:3000]:
    cur.execute("INSERT INTO wpa_churches (state, church_name) VALUES ('AR', ?)", (name,))
conn.commit()
conn.close()
print("Imported to wpa.db")