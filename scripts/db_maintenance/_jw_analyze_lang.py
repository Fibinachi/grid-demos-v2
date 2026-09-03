"""Analyze language patterns in JW entries."""
import sqlite3, re
from collections import Counter

conn = sqlite3.connect(r'E:\grid\churches.db')
c = conn.cursor()

# Get all unique names with counts - filter to the ones that are actually JW
# (exclude Jehovah Jireh, Jehovah Baptist, etc.)
rows = c.execute("""
    SELECT name, COUNT(*) as cnt
    FROM churches 
    WHERE (name LIKE '%Kingdom%Hall%' OR name LIKE '%Jehovah%' OR name LIKE '%Jehova%'
       OR name LIKE '%Salon%Reino%' OR name LIKE '%Salon%Reino%' OR name LIKE '%Salao%Reino%'
       OR name LIKE '%Salao%Reino%' OR name LIKE '%Assembly%Hall%Jehov%'
       OR name LIKE '%Testigos%Jehova%' OR name LIKE '%Testemunha%Jeova%'
       OR name LIKE '%Witnesses%' OR name LIKE '%Witness%Kingdom%')
    AND name NOT LIKE '%Universal%' AND name NOT LIKE '%IURD%'
    AND name NOT LIKE '%JIREH%' AND name NOT LIKE '%Jireh%' AND name NOT LIKE '%jireh%'
    AND name NOT LIKE '%BAPTIST%' AND name NOT LIKE '%Baptist%' AND name NOT LIKE '%baptist%'
    AND name NOT LIKE '%LUTHERAN%' AND name NOT LIKE '%Lutheran%'
    AND name NOT LIKE '%SHAMMAH%' AND name NOT LIKE '%Shammah%'
    AND name NOT LIKE '%SHALOM%' AND name NOT LIKE '%Shalom%'
    AND name NOT LIKE '%RAPHA%' AND name NOT LIKE '%Rapha%'
    AND name NOT LIKE '%MISSIONARY%' AND name NOT LIKE '%Missionary%'
    AND name NOT LIKE '%PENTECOSTAL%' AND name NOT LIKE '%Pentecostal%'
    AND name NOT LIKE '%METHODIST%' AND name NOT LIKE '%Methodist%'
    AND name NOT LIKE '%MINISTRIES%' AND name NOT LIKE '%Ministries%' AND name NOT LIKE '%ministries%'
    AND name NOT LIKE '%NISSI%' AND name NOT LIKE '%Nissi%'
    AND name NOT LIKE '%ROI%' AND name NOT LIKE '%Rohi%'
    AND name NOT LIKE '%SAMA%'
    AND name NOT LIKE '%DELIVERANCE%' AND name NOT LIKE '%Deliverance%'
    AND name NOT LIKE '%CHURCH OF%' AND name NOT LIKE '%Church of%'
    AND name NOT LIKE '%CHRISTIAN%' AND name NOT LIKE '%Christian%'
    AND name NOT LIKE '%FELLOWSHIP%' AND name NOT LIKE '%Fellowship%'
    AND name NOT LIKE '%COMMUNITY%' AND name NOT LIKE '%Community%'
    AND name NOT LIKE '%GOSPEL%' AND name NOT LIKE '%Gospel%'
    AND name NOT LIKE '%PRAISE%' AND name NOT LIKE '%Praise%'
    AND name NOT LIKE '%WORSHIP%' AND name NOT LIKE '%Worship%'
    GROUP BY name
    ORDER BY cnt DESC
""").fetchall()

total_entries = sum(r[1] for r in rows)
print(f'JW entries (filtered): {total_entries:,} across {len(rows)} unique names')
print()

# Language classification
lang_patterns = {
    'English': [r'Kingdom\s*Hall', r"Jehovah'?s?\s*Witness", r'Kingdom\s*Hall\s*of', r'Assembly\s*Hall'],
    'German': [r'Königreichssaal', r'K÷nigreichssaal', r'Zeugen\s+Jehovas', r'K÷nigreichsaal', r'Kongress-Saal'],
    'Spanish': [r'Sal[óo]n\s+del\s+Reino', r'Testigos?\s*de\s*Jehov[áa]'],
    'Portuguese': [r'Sal[ãa]o\s+do\s+Reino', r'Testemunha', r'Salao\s+do\s+Reino'],
    'Dutch': [r'Koninkrijkszaal', r'Getuigen'],
    'French': [r'Salle\s+du\s+Royaume', r'T[ée]moins?\s*de\s*J[ée]hovah'],
    'Swedish': [r'Rikets\s+sal', r'vittnen', r'Vittnen'],
    'Danish': [r'Rigssal', r'Vidners?\s*Rigssal', r'Vidner'],
    'Norwegian': [r'vitners?\s*Rikets\s*sal', r'vitners'],
    'Finnish': [r'valtakunnansali', r'todistajien'],
    'Hungarian': [r'királyságterme', r'Tanúinak', r'kirßlysßgterme'],
    'Malagasy': [r'Vavolombelon', r'Fanjakan'],
    'Icelandic': [r'Ríkissalur', r'vitnum'],
    'Greenlandic': [r'Nalunaajaasuisa\s*Naalagaaffilersaarfii'],
    'Polish': [r'Królestwa'],
    'Italian': [r'Regno\s*de[il]\s*Testim', r'Sala\s+del\s+Regno'],
    'Swahili': [r'Ufalme', r'Mashahidi'],
    'Romanian': [r'Sala\s+Regatului'],
    'Chinese': [r'[\u4e00-\u9fff]'],
    'Russian': [r'[\u0400-\u04ff]'],
    'Arabic': [r'[\u0600-\u06ff]'],
    'Greek': [r'[\u0370-\u03ff]'],
    'Korean': [r'[\uac00-\ud7af]'],
    'Japanese': [r'[\u3040-\u309f\u30a0-\u30ff]'],
    'Hebrew': [r'[\u0590-\u05ff]'],
}

lang_counts = Counter()
lang_names = {}  # lang -> [(name, cnt)]
lang_other = 0

for name, cnt in rows:
    detected = False
    for lang, patterns in lang_patterns.items():
        for pat in patterns:
            if re.search(pat, name, re.IGNORECASE):
                lang_counts[lang] += cnt
                if lang not in lang_names:
                    lang_names[lang] = []
                lang_names[lang].append((name, cnt))
                detected = True
                break
        if detected:
            break
    if not detected:
        lang_other += cnt
        if 'Other' not in lang_names:
            lang_names['Other'] = []
        lang_names['Other'].append((name, cnt))

print('Language breakdown:')
for lang, cnt in sorted(lang_counts.items(), key=lambda x: -x[1]):
    examples = lang_names[lang][:3]
    ex_str = ' | '.join(f'[{e[1]}]{e[0][:50]}' for e in examples)
    print(f'  {lang:15s} {cnt:>6,}  ({ex_str})')
print(f'  {"Other":15s} {lang_other:>6,}'  + (f'  ({lang_names.get("Other", [["",0]])[0][0][:60]})' if lang_other > 0 else ''))

# Also count non-JW "Jehovah" entries that we excluded
non_jw = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE name LIKE '%Jehovah%' OR name LIKE '%Jehova%'
    AND (name LIKE '%JIREH%' OR name LIKE '%Jireh%' OR name LIKE '%BAPTIST%' 
         OR name LIKE '%LUTHERAN%' OR name LIKE '%SHAMMAH%' OR name LIKE '%SHALOM%'
         OR name LIKE '%RAPHA%' OR name LIKE '%MISSIONARY%' OR name LIKE '%PENTECOSTAL%'
         OR name LIKE '%METHODIST%' OR name LIKE '%MINISTRIES%' OR name LIKE '%NISSI%'
         OR name LIKE '%SAMA%' OR name LIKE '%CHRISTIAN%' OR name LIKE '%PRAISE%'
         OR name LIKE '%WORSHIP%')
    AND name NOT LIKE '%Kingdom%Hall%'
    AND name NOT LIKE '%Witness%'
""").fetchone()[0]
print(f'\nNon-JW Jehovah entries (excluded from scope): {non_jw:,}')

conn.close()
