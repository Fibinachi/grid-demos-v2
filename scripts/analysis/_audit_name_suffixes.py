"""Audit corporate suffixes in Islam names that could interfere with classification."""
import sqlite3, re
from collections import Counter

conn = sqlite3.connect(r'E:\grid\churches.db')
c = conn.cursor()

# Check what suffixes exist
suffix_patterns = [
    (r'\bINC\b\.?\s*$', 'INC'),
    (r'\bINCORPORATED\b\.?\s*$', 'INCORPORATED'),
    (r'\bLLC\b\.?\s*$', 'LLC'),
    (r'\bL\.?L\.?C\.?\s*$', 'LLC'),
    (r'\bCORP\b\.?\s*$', 'CORP'),
    (r'\bCORPORATION\b\.?\s*$', 'CORPORATION'),
    (r'\bLTD\b\.?\s*$', 'LTD'),
    (r'\bLIMITED\b\.?\s*$', 'LIMITED'),
    (r'\bCO\b\.?\s*$', 'CO'),
    (r'\bCOMPANY\b\.?\s*$', 'COMPANY'),
    (r'\bASSOC\b\.?\s*$', 'ASSOC'),
    (r'\bASSOCIATION\b\.?\s*$', 'ASSOCIATION'),
    (r'\bFOUNDATION\b\.?\s*$', 'FOUNDATION'),
    (r'\bFUND\b\.?\s*$', 'FUND'),
    (r'\bTRUST\b\.?\s*$', 'TRUST'),
    (r'\bMINISTRIES?\b\.?\s*$', 'MINISTRY'),
    (r'\bFELLOWSHIP\b\.?\s*$', 'FELLOWSHIP'),
    (r'\bSOCIETY\b\.?\s*$', 'SOCIETY'),
    (r'\bORGANIZATION\b\.?\s*$', 'ORGANIZATION'),
    (r'\bENTERPRISES?\b\.?\s*$', 'ENTERPRISE'),
    (r'\bSERVICES?\b\.?\s*$', 'SERVICE'),
    (r'\bGROUP\b\.?\s*$', 'GROUP'),
    (r'\bINTERNATIONAL\b\.?\s*$', 'INTERNATIONAL'),
    (r'\bWORLDWIDE\b\.?\s*$', 'WORLDWIDE'),
    (r'\bGLOBAL\b\.?\s*$', 'GLOBAL'),
]

print("Suffix prevalence in Islam entries:")
for pat, label in suffix_patterns:
    c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Islam' AND name GLOB '*{label[0]}*' AND LOWER(name) LIKE '%{label.lower().rstrip('.')}%'")
    cnt = c.fetchone()[0]
    if cnt:
        print(f"  '{label}': {cnt:,}")

# Show the most common ending words
print("\n=== Last word of Islam names (top 30) ===")
c.execute("""
    SELECT LOWER(TRIM(name, ' .')) FROM churches WHERE faith='Islam' AND name IS NOT NULL
""")
last_words = Counter()
for (name,) in c.fetchall():
    parts = name.strip(' .').split()
    if parts:
        last_words[parts[-1].rstrip('.,;:')] += 1
for word, cnt in last_words.most_common(30):
    print(f"  '{word}': {cnt:,}")

# How many Islam names end with corporate suffixes
print("\n=== Names ending with corporate patterns ===")
corp_endings = ['INC', 'LLC', 'LTD', 'CORP', 'CO', 'ASSOC', 'ASSOCIATION', 'FOUNDATION', 
                'INCORPORATED', 'CORPORATION', 'INC.', 'LLC.', 'LTD.', 'CORP.', 'CO.',
                'INCORPORATED.', 'CORPORATION.', 'MINISTRIES', 'MINISTRY']
for ending in corp_endings:
    c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Islam' AND name LIKE '% {ending}' ESCAPE '\\'")
    cnt = c.fetchone()[0]
    if cnt:
        print(f"  ends with '{ending}': {cnt:,}")

conn.close()
