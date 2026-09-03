"""
Tag monasteries and religious orders with correct faith.
Also do a final pass on remaining ZZ records with name-based country assignment.
"""
import sqlite3, datetime

DB = 'churches.db'
TS = datetime.datetime.now().isoformat()
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()
total_fixes = 0

def tag_faith(label, target_faith, where_clause, excl=None):
    global total_fixes
    sql = f"UPDATE churches SET faith='{target_faith}', faith_tradition='{target_faith}' WHERE {where_clause} AND (faith IS NULL OR faith='')"
    if excl:
        sql += f" AND NOT ({excl})"
    c.execute(sql)
    if c.rowcount > 0:
        print(f"  {label}: {c.rowcount}")
        total_fixes += c.rowcount

# ═══════════════════════════════════════════════════════════════════════════════
# 1. Catholic religious orders — name-based
# ═══════════════════════════════════════════════════════════════════════════════
print("=== Catholic orders ===")

catholic_orders = [
    ("Benedictine", "LOWER(name) LIKE '%benedictine%' OR LOWER(name) LIKE '%benedict%monastery%' OR LOWER(name) LIKE '%st. benedict%monastery%'"),
    ("Franciscan", "LOWER(name) LIKE '%franciscan%'"),
    ("Dominican", "LOWER(name) LIKE '%dominican%' AND LOWER(name) NOT LIKE '%dominican republic%'"),
    ("Carmelite", "LOWER(name) LIKE '%carmelite%' OR LOWER(name) LIKE '%mt. carmel%monastery%' OR LOWER(name) LIKE '%mount carmel%monastery%'"),
    ("Cistercian/Trappist", "LOWER(name) LIKE '%cistercian%' OR LOWER(name) LIKE '%trappist%'"),
    ("Jesuit", "LOWER(name) LIKE '%jesuit%'"),
    ("Poor Clare", "LOWER(name) LIKE '%poor clare%' OR LOWER(name) LIKE '%st. clare%monastery%' OR LOWER(name) LIKE '%st clare%monastery%' OR LOWER(name) LIKE '%saint clare%monastery%'"),
    ("Capuchin", "LOWER(name) LIKE '%capuchin%'"),
    ("Augustinian", "LOWER(name) LIKE '%augustinian%'"),
    ("Carthusian", "LOWER(name) LIKE '%carthusian%'"),
    ("Basilian", "LOWER(name) LIKE '%basilian%'"),
    ("Norbertine/Premonstratensian", "LOWER(name) LIKE '%norbertine%' OR LOWER(name) LIKE '%premonstratensian%'"),
    ("Servite", "LOWER(name) LIKE '%servite%'"),
    ("Pauline", "LOWER(name) LIKE '%pauline father%' OR LOWER(name) LIKE '%pauline monk%' OR LOWER(name) LIKE '%order of st paul%'"),
]

for name, where_clause in catholic_orders:
    tag_faith(f"{name} → Catholic", "Christian", where_clause)

# ── Generic Catholic monastery signals ──────────────────────────────────────
tag_faith("Monastery + Catholic source → Christian", "Christian",
    "LOWER(name) LIKE '%monastery%' AND (source='catholic_diocese_scrape' OR denomination LIKE '%catholic%' OR denomination LIKE '%Roman Catholic%')")

tag_faith("Holy/Sacred Heart/Immaculate monastery → Christian", "Christian",
    "(LOWER(name) LIKE '%immaculate heart%' OR LOWER(name) LIKE '%sacred heart%' OR LOWER(name) LIKE '%holy cross%' OR LOWER(name) LIKE '%holy spirit%' OR LOWER(name) LIKE '%holy ghost%' OR LOWER(name) LIKE '%holy trinity%' OR LOWER(name) LIKE '%our lady%' OR LOWER(name) LIKE '%holy rosary%' OR LOWER(name) LIKE '%st. joseph%' OR LOWER(name) LIKE '%saint joseph%') AND LOWER(name) LIKE '%monastery%'")

tag_faith("Monastery + Theotokos/Orthodox → Christian", "Christian",
    "LOWER(name) LIKE '%theotokos%' OR LOWER(name) LIKE '%skete%' OR LOWER(name) LIKE '%lavra%'")

# ═══════════════════════════════════════════════════════════════════════════════
# 2. Orthodox / Eastern Christian
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Orthodox / Eastern ===")

orthodox_kws = [
    ("Orthodox (general)", "LOWER(name) LIKE '%orthodox%' AND LOWER(name) NOT LIKE '%catholic orthodox%'"),
    ("Greek Orthodox", "LOWER(name) LIKE '%greek orthodox%'"),
    ("Russian Orthodox", "LOWER(name) LIKE '%russian orthodox%'"),
    ("Serbian Orthodox", "LOWER(name) LIKE '%serbian orthodox%'"),
    ("Romanian Orthodox", "LOWER(name) LIKE '%romanian orthodox%'"),
    ("Bulgarian Orthodox", "LOWER(name) LIKE '%bulgarian orthodox%'"),
    ("Coptic", "LOWER(name) LIKE '%coptic%'"),
    ("Armenian", "LOWER(name) LIKE '%armenian%' AND (LOWER(name) LIKE '%church%' OR LOWER(name) LIKE '%orthodox%' OR LOWER(name) LIKE '%apostolic%' OR LOWER(name) LIKE '%monastery%')"),
    ("Syriac", "LOWER(name) LIKE '%syriac%' AND (LOWER(name) LIKE '%orthodox%' OR LOWER(name) LIKE '%catholic%' OR LOWER(name) LIKE '%church%')"),
    ("Ethiopian Orthodox", "LOWER(name) LIKE '%ethiopian orthodox%' OR LOWER(name) LIKE '%ethiopian tewahedo%'"),
]

for name, where_clause in orthodox_kws:
    tag_faith(f"{name} → Christian", "Christian", where_clause)

# ═══════════════════════════════════════════════════════════════════════════════
# 3. Buddhist monasteries
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Buddhist ===")
tag_faith("Buddhist monastery → Buddhist", "Buddhist",
    "LOWER(name) LIKE '%buddhist%monastery%' OR LOWER(name) LIKE '%zen monastery%' OR LOWER(name) LIKE '%tibetan%monastery%' OR LOWER(name) LIKE '%tibetan buddhist%' OR LOWER(name) LIKE '%drepung%' OR LOWER(name) LIKE '%ganden%'")

tag_faith("Lin Yun / Tian Ren monastery → Buddhist", "Buddhist",
    "(LOWER(name) LIKE '%lin yun%' OR LOWER(name) LIKE '%tian ren%') AND LOWER(name) LIKE '%monastery%'")

# ═══════════════════════════════════════════════════════════════════════════════
# 4. Hindu monasteries (matha)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Hindu ===")
tag_faith("Matha/math monastery → Hindu", "Hindu",
    "LOWER(name) LIKE '%matha%' OR LOWER(name) LIKE '% math %' OR LOWER(name) LIKE '%mutts%' OR LOWER(name) LIKE '%mutt%'")

conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 5. Remaining ZZ records — name-based country assignment
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Remaining ZZ name-based country ===")

# City/country name → ISO lookup
name_lookup = {
    'istanbul': 'TR', 'turkey': 'TR', 'türkiye': 'TR',
    'paris': 'FR', 'france': 'FR', 'lyon': 'FR', 'marseille': 'FR',
    'rome': 'IT', 'roma': 'IT', 'italy': 'IT', 'milano': 'IT', 'firenze': 'IT',
    'nesebar': 'BG', 'bulgaria': 'BG', 'sofia': 'BG',
    'patmos': 'GR', 'greece': 'GR', 'athens': 'GR', 'thessaloniki': 'GR',
    'liepaja': 'LV', 'latvia': 'LV', 'riga': 'LV',
    'vienna': 'AT', 'wien': 'AT', 'austria': 'AT',
    'berlin': 'DE', 'germany': 'DE', 'munich': 'DE', 'köln': 'DE',
    'london': 'GB', 'england': 'GB', 'britain': 'GB',
    'madrid': 'ES', 'spain': 'ES', 'barcelona': 'ES',
    'lisbon': 'PT', 'portugal': 'PT',
    'warsaw': 'PL', 'poland': 'PL', 'krakow': 'PL', 'kraków': 'PL',
    'budapest': 'HU', 'hungary': 'HU',
    'prague': 'CZ', 'praha': 'CZ', 'czech': 'CZ',
    'kiev': 'UA', 'kyiv': 'UA', 'ukraine': 'UA',
    'moscow': 'RU', 'russia': 'RU', 'moskva': 'RU',
    'tokyo': 'JP', 'japan': 'JP',
    'seoul': 'KR', 'korea': 'KR',
    'beijing': 'CN', 'china': 'CN',
    'delhi': 'IN', 'mumbai': 'IN', 'india': 'IN',
    'cairo': 'EG', 'egypt': 'EG',
    'copenhagen': 'DK', 'denmark': 'DK',
    'stockholm': 'SE', 'sweden': 'SE',
    'oslo': 'NO', 'norway': 'NO',
    'helsinki': 'FI', 'finland': 'FI',
    'brussels': 'BE', 'belgium': 'BE',
    'amsterdam': 'NL', 'netherlands': 'NL',
    'zurich': 'CH', 'bern': 'CH', 'switzerland': 'CH',
    'toronto': 'CA', 'montreal': 'CA', 'vancouver': 'CA',
    'sydney': 'AU', 'melbourne': 'AU', 'australia': 'AU',
    'dublin': 'IE', 'ireland': 'IE',
    'jerusalem': 'IL', 'tel aviv': 'IL',
    'beirut': 'LB', 'lebanon': 'LB',
    'damascus': 'SY', 'syria': 'SY',
    'amman': 'JO', 'jordan': 'JO',
    'baghdad': 'IQ', 'iraq': 'IQ',
    'tehran': 'IR', 'iran': 'IR',
    'riyadh': 'SA', 'saudi': 'SA',
    'dubai': 'AE', 'abu dhabi': 'AE', 'uae': 'AE',
    'doha': 'QA', 'qatar': 'QA',
    'kuwait': 'KW',
    'muscat': 'OM', 'oman': 'OM',
    'manila': 'PH', 'philippines': 'PH',
    'bangkok': 'TH', 'thailand': 'TH',
    'hanoi': 'VN', 'ho chi minh': 'VN', 'vietnam': 'VN',
    'jakarta': 'ID', 'indonesia': 'ID',
    'singapore': 'SG',
    'kuala lumpur': 'MY', 'malaysia': 'MY',
    'yangon': 'MM', 'myanmar': 'MM', 'burma': 'MM',
    'nairobi': 'KE', 'kenya': 'KE',
    'lagos': 'NG', 'abuja': 'NG', 'nigeria': 'NG',
    'accra': 'GH', 'ghana': 'GH',
    'addis ababa': 'ET', 'ethiopia': 'ET',
    'cape town': 'ZA', 'johannesburg': 'ZA', 'south africa': 'ZA',
    'santiago': 'CL', 'chile': 'CL',
    'lima': 'PE', 'peru': 'PE',
    'bogota': 'CO', 'colombia': 'CO',
    'caracas': 'VE', 'venezuela': 'VE',
    'quito': 'EC', 'ecuador': 'EC',
    'la paz': 'BO', 'bolivia': 'BO',
    'asuncion': 'PY', 'paraguay': 'PY',
    'montevideo': 'UY', 'uruguay': 'UY',
    'havana': 'CU', 'cuba': 'CU',
    'kingston': 'JM', 'jamaica': 'JM',
    'nassau': 'BS', 'bahamas': 'BS',
    'port of spain': 'TT', 'trinidad': 'TT',
    'wellington': 'NZ', 'new zealand': 'NZ', 'auckland': 'NZ',
    'suva': 'FJ', 'fiji': 'FJ',
}

zz_fixes = 0
c.execute("SELECT id, name FROM churches WHERE country='ZZ' AND latitude IS NOT NULL")
for rid, name in c.fetchall():
    if name is None:
        continue
    name_lower = name.lower()
    for location, iso in name_lookup.items():
        if location in name_lower:
            if rid is not None:
                c.execute("UPDATE churches SET country=? WHERE id=?", (iso, rid))
            else:
                c.execute("""
                    UPDATE churches SET country=?
                    WHERE country='ZZ' AND id IS NULL AND name=? LIMIT 1
                """, (iso, name))
            if c.rowcount > 0:
                zz_fixes += 1
            break

print(f"ZZ name-based fixes: {zz_fixes}")
total_fixes += zz_fixes
conn.commit()

# ── Final count ─────────────────────────────────────────────────────────────
c.execute("SELECT COUNT(*) FROM churches WHERE country='ZZ'")
remaining = c.fetchone()[0]
print(f"\nFinal ZZ: {remaining:,}")

# Log
c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
        churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('manual', '_tag_monasteries_zz.py', TS, TS,
      total_fixes, 0, 'faith,faith_tradition,country', 'completed',
      f'Tagged monasteries/orders + {zz_fixes} ZZ name-based country fixes. Total: {total_fixes}'))

conn.commit()

print(f"\nTotal fixes: {total_fixes}")
conn.close()
print("Done!")
