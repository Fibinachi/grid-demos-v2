#!/usr/bin/env python3
import json
import re
from pathlib import Path

CHUNKS_DIR = Path("E:/grid/data/directories/chunks")
OUTPUT_DIR = CHUNKS_DIR / "fixed"
OUTPUT_DIR.mkdir(exist_ok=True)

# OCR fix patterns - word breaks at line ends with hyphens
OCR_REPAIR_PATTERNS = [
    # Generic patterns for any hyphenated line break
    (r"(\w+)-\s*(\r?\n|\r)?\s*(\w+)", r"\1\2"),  # Merge word split at line break with hyphen
    
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
    # This merges words separated by hyphen+linebreak
    text = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", text)
    
    return text

def process_chunk_file(chunk_path):
    """Process a single chunk file"""
    try:
        with open(chunk_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Process each entry
        fixed_data = []
        for entry in data:
            # Each entry is [year, text]
            if len(entry) >= 2 and isinstance(entry[1], str):
                fixed_text = apply_ocr_fixes(entry[1])
                fixed_entry = entry.copy()
                fixed_entry[1] = fixed_text
                fixed_data.append(fixed_entry)
            else:
                fixed_data.append(entry)
        
        # Save to output file
        output_path = OUTPUT_DIR / chunk_path.name
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(fixed_data, f, ensure_ascii=False, indent=None)
        
        print(f"Fixed {len(fixed_data)} entries in {chunk_path.name}")
        return True
        
    except Exception as e:
        print(f"Error processing {chunk_path.name}: {str(e)}")
        return False

def main():
    # Process all chunk files
    chunk_files = sorted(CHUNKS_DIR.glob("chunk_*.json"))
    processed_count = 0
    
    for chunk_file in chunk_files:
        if process_chunk_file(chunk_file):
            processed_count += 1
    
    print(f"\nProcessing complete. Fixed {processed_count} chunk files.")
    print(f"Output saved to: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()