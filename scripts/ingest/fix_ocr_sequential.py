#!/usr/bin/env python3
import json
import re
from pathlib import Path
import time

CHUNKS_DIR = Path("E:/grid/data/directories/chunks")
OUTPUT_DIR = CHUNKS_DIR / "fixed"
OUTPUT_DIR.mkdir(exist_ok=True)

# OCR fix patterns - word breaks at line ends with hyphens
OCR_REPAIR_PATTERNS = [
    # Generic patterns for any hyphenated line break
    (r"(\w+)-\s*(\r?\n|\r)?\s*(\w+)", r"\1\3"),  # Merge word split at line break with hyphen
    
    # Specific known patterns from the data
    (r"consec-", "consecrated"),      # consec- -> consecrated
    (r"translat-", "translating"),   # translat- -> translating  
    (r"attend-", "attend"),           # attend- -> attend
    (r"Gait-", "gate"),               # Gait- -> gate
    (r"arche-", "archive"),           # arche- -> archive
    (r"scholar-", "scholars"),        # scholar- -> scholars
    (r"contempl-", "contemplate"),   # contempl- -> contemplate
    (r"valide-", "validate"),         # valide- -> validate
    (r"cath-", "catholic"),           # cath- -> catholic
    (r"christ-", "christ"),           # christ- -> christ
    (r"liturg-", "liturgy"),         # liturg- -> liturgy
]

def apply_ocr_fixes(text):
    """Apply OCR fixes to normalize text"""
    if not isinstance(text, str):
        return text
    
    # Apply specific patterns first
    for pattern, replacement in OCR_REPAIR_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # Handle remaining hyphenated line breaks generally
    # Fix: use \1 for first group, no \2 since there's only one capture group
    text = re.sub(r"(\w+)-\s*\n\s*\w+", r"\1", text)
    
    return text

def process_chunk(chunk_file):
    """Process a single chunk file sequentially"""
    try:
        with open(chunk_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Process each entry sequentially with progress tracking
        fixed_data = []
        total_entries = len(data)
        print(f"Processing {chunk_file.name}...")
        
        for i, entry in enumerate(data, 1):
            # Extract year and text
            if len(entry) >= 2 and isinstance(entry[1], str):
                original_text = entry[1]
                fixed_text = apply_ocr_fixes(original_text)
                
                # Create fixed entry
                fixed_entry = [entry[0], fixed_text]  # [year, corrected_text]
                fixed_data.append(fixed_entry)
            else:
                fixed_data.append(entry)  # Keep entries with missing text
            
            # Progress update every 1% or every 1000 entries
            if i % max(1, total_entries // 100) == 0:
                progress = i / total_entries * 100
                print(f"\rProgress: {progress:.1f}% ({i}/{total_entries} entries)", end="")
        
        # Save to output file
        output_path = OUTPUT_DIR / chunk_file.name
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(fixed_data, f, ensure_ascii=False)
        
        print(f"\nFixed {chunk_file.name}: {len(fixed_data)} entries")
        return True
        
    except Exception as e:
        print(f"Error processing {chunk_file.name}: {str(e)}")
        return False

def main():
    # Process all chunk files sequentially
    chunk_files = sorted(CHUNKS_DIR.glob("chunk_*.json"))
    processed_count = 0
    
    for chunk_file in chunk_files:
        # Skip if already processed (unless output is older than input)
        output_path = OUTPUT_DIR / chunk_file.name
        if output_path.exists() and output_path.stat().st_mtime >= chunk_file.stat().st_mtime:
            continue
        
        if process_chunk(chunk_file):
            processed_count += 1
    
    print(f"\nProcessing complete. Fixed {processed_count} new chunk files.")
    print(f"Total fixed files: {len(list(OUTPUT_DIR.glob('chunk_*.json')))}")
    print(f"Output saved to: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()