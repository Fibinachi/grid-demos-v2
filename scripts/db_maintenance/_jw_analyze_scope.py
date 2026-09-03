"""Analyze full scope of JW entries for standardization."""
import sqlite3

conn = sqlite3.connect(r'E:\grid\churches.db')
c = conn.cursor()

# Total JW entries denominator - broader net
total = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE name LIKE '%Kingdom%Hall%' OR name LIKE '%Jehovah%' 
       OR name LIKE '%Jehova%' OR name LIKE '%Salon%Reino%' 
       OR name LIKE '%Salón%Reino%' OR name LIKE '%Salão%Reino%'
       OR name LIKE '%Salao%Reino%' OR name LIKE '%Assembly%Hall%Jehov%'
       OR name LIKE '%Testigos%Jehova%' OR name LIKE '%Testemunha%Jeova%'
       OR name LIKE '%Witnesses%' OR name LIKE '%Witness%Kingdom%'
""").fetchone()[0]
print(f'Total JW-identifiable entries: {total:,}')

# English KH patterns
eng = c.execute("""SELECT COUNT(*) FROM churches 
    WHERE (name LIKE '%Kingdom%Hall%' OR name LIKE '%Kingdom%Hall%') 
    AND name NOT LIKE '%Salon%' AND name NOT LIKE '%Salao%' 
    AND name NOT LIKE '%Salao%' AND name NOT LIKE '%Reino%'""").fetchone()[0]
print(f'English Kingdom Hall entries: {eng:,}')

# Spanish
span = c.execute("""SELECT COUNT(*) FROM churches 
    WHERE (name LIKE '%Salon%Reino%' OR name LIKE '%Salon%Reino%') 
    AND name NOT LIKE '%Universal%'""").fetchone()[0]
print(f'Spanish Salon del Reino entries: {span:,}')

# Portuguese
port = c.execute("""SELECT COUNT(*) FROM churches 
    WHERE (name LIKE '%Salao%Reino%' OR name LIKE '%Salao%Reino%') 
    AND name NOT LIKE '%Universal%'""").fetchone()[0]
print(f'Portuguese Salao do Reino entries: {port:,}')

# Igreja Universal (NOT JW, but similar pattern)
iurd = c.execute("""SELECT COUNT(*) FROM churches 
    WHERE name LIKE '%Universal%Reino%' OR name LIKE '%IURD%'""").fetchone()[0]
print(f'\nIgreja Universal do Reino de Deus (NOT JW): {iurd:,}')

# Assembly Halls
ah = c.execute("""SELECT COUNT(*) FROM churches 
    WHERE name LIKE '%Assembly%Hall%' AND (name LIKE '%Jehov%' OR name LIKE '%Witness%')""").fetchone()[0]
print(f'Assembly Halls of JWs: {ah:,}')

# Other JW patterns (Jehovah's Witnesses, Testigos de Jehova, etc.)
other = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE (name LIKE '%Jehovah%' OR name LIKE '%Jehova%' 
       OR name LIKE '%Testigos%Jehova%' OR name LIKE '%Testemunha%Jeova%')
    AND name NOT LIKE '%Kingdom%Hall%' AND name NOT LIKE '%Kingdom%Hall%'
    AND name NOT LIKE '%Salon%Reino%' AND name NOT LIKE '%Salon%Reino%'
    AND name NOT LIKE '%Salao%Reino%' AND name NOT LIKE '%Salao%Reino%'
    AND name NOT LIKE '%Assembly%Hall%'
    AND name NOT LIKE '%Universal%'
""").fetchone()[0]
print(f'Other JW name patterns: {other:,}')

# JW-related entries with city populated
no_uni = """AND name NOT LIKE '%Universal%'"""
has_city = c.execute(f"""
    SELECT COUNT(*) FROM churches 
    WHERE (name LIKE '%Kingdom%Hall%' OR name LIKE '%Jehovah%' OR name LIKE '%Jehova%'
       OR name LIKE '%Salon%Reino%' OR name LIKE '%Salon%Reino%' OR name LIKE '%Salao%Reino%'
       OR name LIKE '%Salao%Reino%' OR name LIKE '%Assembly%Hall%Jehov%'
       OR name LIKE '%Testigos%Jehova%' OR name LIKE '%Testemunha%Jeova%'
       OR name LIKE '%Witnesses%')
    AND name NOT LIKE '%Universal%'
    AND city IS NOT NULL AND city != '' AND city != 'None'
""").fetchone()[0]
print(f'\nJW entries WITH city populated: {has_city:,}')

no_city = c.execute(f"""
    SELECT COUNT(*) FROM churches 
    WHERE (name LIKE '%Kingdom%Hall%' OR name LIKE '%Jehovah%' OR name LIKE '%Jehova%'
       OR name LIKE '%Salon%Reino%' OR name LIKE '%Salon%Reino%' OR name LIKE '%Salao%Reino%'
       OR name LIKE '%Salao%Reino%' OR name LIKE '%Assembly%Hall%Jehov%'
       OR name LIKE '%Testigos%Jehova%' OR name LIKE '%Testemunha%Jeova%'
       OR name LIKE '%Witnesses%')
    AND name NOT LIKE '%Universal%'
    AND (city IS NULL OR city = '' OR city = 'None')
""").fetchone()[0]
print(f'JW entries WITHOUT city: {no_city:,}')

# Check what languages are present - sample names in non-English scripts
print('\n=== Language detection needed ===')
samples = c.execute("""
    SELECT name, city, state, country FROM churches 
    WHERE (name LIKE '%Kingdom%Hall%' OR name LIKE '%Jehovah%' OR name LIKE '%Jehova%')
    AND name GLOB '*[^a-zA-Z0-9 .,;:!?()_/-]*'
    LIMIT 30
""").fetchall()
for n, ci, st, co in samples:
    print(f'  [{co}] {n[:80]} | city={str(ci)[:20]}')

conn.close()
print(f'\nDone.')
