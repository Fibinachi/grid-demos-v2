"""Clean the Catholic directory CSV files - remove OCR artifacts and normalize data."""
import csv
import re
from pathlib import Path

INPUT = Path('E:/grid/data/denom/catholic_directories_1948_2021.csv')
OUTPUT = Path('E:/grid/data/denom/catholic_directories_1948_2021_clean.csv')

def clean_city(city):
    """Clean city field - remove garbage and normalize."""
    if not city:
        return ''
    
    city = city.strip()
    
    # Remove OCR artifacts
    city = re.sub(r'^\W+|\W+$', '', city)
    
    # Skip if it looks like garbage (contains special patterns)
    if re.match(r'^(?:Tr|Pastor|Pupils|St|Holy|Sacred|Our|Mothers|Missions)\W*$', city, re.IGNORECASE):
        return ''
    
    # Skip if just numbers
    if re.match(r'^\d+$', city):
        return ''
    
    return city

def clean_name(name):
    """Clean institution name."""
    if not name:
        return ''
    
    name = name.strip()
    
    # Remove trailing garbage
    name = re.sub(r'\s*[\uFFFD\u0000-\u001F\u007F-\u009F].*$', '', name)
    name = re.sub(r'\s*;.*$', '', name)  # Remove semicolons and after
    
    return name

def clean_diocese(diocese):
    """Clean diocese name."""
    if not diocese:
        return ''
    
    diocese = diocese.strip()
    diocese = re.sub(r'^\W+|\W+$', '', diocese)
    
    return diocese

def main():
    total = 0
    clean = 0
    
    with open(INPUT, 'r', encoding='utf-8') as f_in:
        reader = csv.DictReader(f_in)
        records = []
        
        for row in reader:
            total += 1
            cleaned = {
                'year': row['year'],
                'diocese': clean_diocese(row.get('diocese', '')),
                'state': row.get('state', '').strip(),
                'city': clean_city(row.get('city', '')),
                'name': clean_name(row.get('name', '')),
            }
            
            # Only keep rows with valid name and diocese
            if cleaned['name'] and cleaned['diocese'] and len(cleaned['name']) > 5:
                records.append(cleaned)
                clean += 1
    
    with open(OUTPUT, 'w', newline='', encoding='utf-8') as f_out:
        writer = csv.DictWriter(f_out, fieldnames=['year', 'diocese', 'state', 'city', 'name'])
        writer.writeheader()
        writer.writerows(records)
    
    print(f"Cleaned: {clean:,} / {total:,} records kept")
    print(f"Saved to: {OUTPUT}")

if __name__ == '__main__':
    main()