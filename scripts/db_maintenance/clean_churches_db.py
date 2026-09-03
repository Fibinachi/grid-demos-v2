import sqlite3
import re
from pathlib import Path

# Connect to the database
db_path = Path('churches.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Step 1: Clean up extra spaces in names and other text fields
def normalize_spaces(text):
    if text:
        return re.sub(r'\s+', ' ', text.strip())
    return text

# Get all records
cursor.execute('SELECT * FROM churches WHERE religion_type = 'christian' AND denomination_affiliation NOT LIKE '%buddhist%' AND denomination_affiliation NOT LIKE '%hindu%' AND landmark_type NOT IN ('embassy', 'university')')
all_records = cursor.fetchall()
num_records = len(all_records)
print(f'Total records: {num_records}')

# Identify columns by name from schema
cursor.execute('PRAGMA table_info(churches)')
schema = cursor.fetchall()
col_names = [row[1] for row in schema]
print(f'Columns: {col_names}')

# Map column indices
name_idx = col_names.index('name')
denomination_idx = col_names.index('denomination_affiliation')
religion_type_idx = col_names.index('religion_type')
landmark_type_idx = col_names.index('landmark_type')
source_idx = col_names.index('source')
city_idx = col_names.index('city')

# Keywords to filter out as non-church artifacts
artifact_keywords = {
    'news', 'article', 'press', 'release', 'ministry', 'outreach',
    'center', 'centre', 'prophetic', 'christian center',
    'fellowship', 'evangelistic', 'evangelical', 'evangelist',
    'good news', 'goodnews', 'good news', 'goodnews'
}

def is_artifact_record(record):
    # Check name for artifact keywords
    name = record[name_idx]
    if name:
        name_lower = name.lower()
        for kw in artifact_keywords:
            if kw in name_lower:
                return True
    # Check denomination for artifact keywords
    denomination = record[denomination_idx] or ''
    denomination_lower = denomination.lower()
    for kw in artifact_keywords:
        if kw in denomination_lower:
            return True
    # Check religion_type for artifact keywords
    religion_type = record[religion_type_idx] or ''
    religion_type_lower = religion_type.lower()
    for kw in artifact_keywords:
        if kw in religion_type_lower:
            return True
    # Check landmark_type for artifact keywords
    landmark_type = record[landmark_type_idx] or ''
    landmark_type_lower = landmark_type.lower()
    for kw in artifact_keywords:
        if kw in landmark_type_lower:
            return True
    return False

# Count artifacts to remove
artifact_count = 0
cleaned_records = []
for record in all_records:
    if is_artifact_record(record):
        artifact_count += 1
        # Skip these records
        continue
    # Normalize spaces in relevant fields
    normalized_record = list(record)
    for i, value in enumerate(record):
        if isinstance(value, str):
            normalized_record[i] = normalize_spaces(value)
    cleaned_records.append(tuple(normalized_record))

# Update the database with cleaned records
# First, delete all existing records
cursor.execute('DELETE FROM churches')
print(f'Deleted {artifact_count} artifact records')

# Insert cleaned records in batches
batch_size = 500
for i in range(0, len(cleaned_records), batch_size):
    batch = cleaned_records[i:i+batch_size]
    cursor.executemany('INSERT INTO churches VALUES (' + ','.join(['?']*len(col_names)) + ')', batch)
    conn.commit()
    print(f'Processed batch {i//batch_size + 1} ({len(batch)} records)')

# Final count
cursor.execute('SELECT COUNT(*) FROM churches')
final_count = cursor.fetchone()[0]
print(f'Final record count: {final_count}')

# Commit and close
conn.commit()
conn.close()
print('Database cleaning completed successfully!')