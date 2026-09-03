"""
Parser for The Official Catholic Directory formatted text files (1948-2021).
Extracts diocese headers and church entries with proper state/city extraction.

Output: CSVs to E:/grid/data/denom/catholic_parsed_laguna/
Format: year,diocese,state,name,city,source_line
"""
import re
from pathlib import Path

DIRECTORIES = Path("E:/grid/data/directories")
OUTPUT_DIR = Path("E:/grid/data/denom/catholic_parsed_laguna")

def clean_ocr(text):
    """Clean common OCR artifacts."""
    text = text.replace("Hoty", "Holy").replace("Grecory", "Gregory")
    text = text.replace("Jospu", "Joseph").replace("Joun", "John")
    text = text.replace("Josr", "John").replace("Josrr", "John")
    text = text.replace("Wrncesnaus", "Winchest").replace("pm", "'s")
    text = re.sub(r"StT?\.", "St.", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()

def get_state(diocese, context):
    """Get state from context for a diocese."""
    known = {
        "boston": "MA", "baltimore": "MD", "new york": "NY", "chicago": "IL",
        "philadelphia": "PA", "albany": "NY", "buffalo": "NY", "rochester": "NY",
        "syracuse": "NY", "mobile": "AL", "miami": "FL", "tampa": "FL",
        "los angeles": "CA", "san francisco": "CA", "san diego": "CA", "sacramento": "CA",
        "detroit": "MI", "grand rapids": "MI", "lansing": "MI",
        "duluth": "MN", "st paul": "MN", "st. paul": "MN", "springfield": "IL",
        "dallas": "TX", "houston": "TX", "austin": "TX", "fort worth": "TX",
    }
    
    dio_lower = diocese.lower().strip(" .,-")
    for k, v in known.items():
        if dio_lower.startswith(k) or dio_lower == k:
            return v
    
    patterns = [
        (r"Mass\.", "MA"), (r"N\.Y\.", "NY"), (r"Md\.", "MD"),
        (r"Pa\.", "PA"), (r"Cal\.", "CA"), (r"Tex\.", "TX"),
        (r"Ill\.", "IL"), (r"Ohio", "OH"), (r"Wis\.", "WI"),
        (r"Mich\.", "MI"), (r"Mo\.", "MO"), (r"N\.J\.", "NJ"),
        (r"R\.I\.", "RI"), (r"Conn\.", "CT"),
    ]
    
    for pat, st in patterns:
        if re.search(pat, context, re.IGNORECASE):
            return st
    return ""

def parse_directory(filepath, year):
    """Parse a single directory file."""
    results = []
    current_diocese = ""
    current_state = ""
    in_church_section = False
    
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = [l.rstrip() for l in f.readlines()]
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line or len(line) < 5:
            continue
        
        # Detect church section - the section header
        if re.search(r"CLERGY,\s*CHURCHES", line, re.IGNORECASE):
            in_church_section = True
            continue
        
        # Diocese header
        dio_m = re.match(r"^(?:ARCH)?DIOCESE\s+OF\s+(.+?)[.,]?\s*$", line, re.IGNORECASE)
        if dio_m and not re.match(r"^\d+[-\u2014]", line):
            context = " ".join(lines[i:min(i+25, len(lines))])
            current_diocese = clean_ocr(dio_m.group(1).strip())
            current_state = get_state(current_diocese, context)
            continue
        
        # Numbered church entry (within city)
        if in_church_section and current_diocese and re.match(r"^\d+[-\u2014]", line):
            # Extract church name and optional location
            m = re.match(r"^\d+[-\u2014]\s*(.+?)$", line)
            if m:
                full_text = clean_ocr(m.group(1).strip())
                
                # Split on comma
                parts = [p.strip() for p in full_text.split(",")]
                church_name = parts[0]
                
                # City is typically a neighborhood if present and simple
                city = ""
                if len(parts) > 1:
                    # Check second part for being a simple city/neighborhood
                    potential = parts[1]
                    if (re.match(r"^[A-Z][a-z]+$", potential) and 
                        not re.search(r"(street|ave|st\.|rd\.|ln\.|drive|way|place|sq\b)", potential, re.IGNORECASE)):
                        city = potential
                
                if re.search(r"(St\.|Sts\.|Cathedral|Holy|Church|Mission|Shrine|Sacred|Immaculate|Our\s+Lady)", church_name, re.IGNORECASE):
                    results.append({
                        "year": year, "diocese": current_diocese, "state": current_state,
                        "name": church_name, "city": city, "source_line": i + 1
                    })
    
    return results

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, help="Parse specific year")
    ap.add_argument("--all", action="store_true", help="Parse all years 1948-2021")
    args = ap.parse_args()
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    if args.year:
        years = [args.year]
    elif args.all:
        years = sorted(set(
            int(m.group(1)) for fp in DIRECTORIES.glob("catholic_dir_*_formatted.txt")
            if (m := re.match(r"catholic_dir_(\d+)_formatted\.txt", fp.name))
            and 1948 <= int(m.group(1)) <= 2021
        ))
    else:
        ap.print_help()
        return
    
    for year in years:
        print(f"\nParsing {year}...")
        fp = DIRECTORIES / f"catholic_dir_{year}_formatted.txt"
        if not fp.exists():
            print(f"  File not found")
            continue
        
        results = parse_directory(fp, year)
        if results:
            out_csv = OUTPUT_DIR / f"catholic_{year}.csv"
            with open(out_csv, "w", encoding="utf-8") as f:
                f.write("year,diocese,state,name,city,source_line\n")
                for r in results:
                    name = r["name"].replace(",", " ")
                    city = r["city"].replace(",", " ") if r["city"] else ""
                    dio = r["diocese"].replace(",", " ")
                    f.write(f'{r["year"]},{dio},{r["state"]},{name},{city},{r["source_line"]}\n')
            print(f"  Wrote {len(results)} entries to {out_csv.name}")
        else:
            print(f"  No entries extracted")

if __name__ == "__main__":
    main()
