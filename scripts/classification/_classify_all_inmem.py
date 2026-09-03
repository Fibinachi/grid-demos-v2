"""
One-pass in-memory classifier sweep — ZERO row iteration.

Loads ALL churches into pandas, runs every classifier via vectorized
boolean masks, then writes results to DB in bulk grouped by value.
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timezone

DB = "E:\\grid\\churches.db"

print("=== IN-MEMORY CLASSIFIER SWEEP (vectorized) ===")
print("Loading all churches into memory...")

conn = sqlite3.connect(DB)
df = pd.read_sql(
    "SELECT rowid, id, name, country, faith, faith_tradition "
    "FROM churches", conn
)
conn.close()

print(f"Loaded {len(df):,} rows  ({(df.memory_usage(deep=True).sum() / 1e9):.2f} GB)")
print()

now = datetime.now(timezone.utc).isoformat()

# ──────────────────────────────────────────
# 1. SHINTO CLASSIFIER
# ──────────────────────────────────────────
print("--- Shinto classifier ---")
mask_null = df['faith'].isna() | (df['faith'] == '')
p = '神社|神宮|大社|jinja|jingu|taisha|shrine|shinto|kami|神道|靖国|明治神宮|伊勢神宮'
m = mask_null & (df['country'] == 'JP') & df['name'].str.contains(p, na=False, case=False)
n1 = m.sum()
print(f"  {n1:,} entries → Shinto")
df.loc[m, 'faith'] = 'Shinto'
df.loc[m, 'faith_tradition'] = 'Shinto'

# ──────────────────────────────────────────
# 2. CHINESE FOLK CLASSIFIER
# ──────────────────────────────────────────
print("--- Chinese folk classifier ---")
mask_null = df['faith'].isna() | (df['faith'] == '')
p2 = '宮|廟|寺|祠|庵|壇|堂|觀|庙|妈祖|天后|福德|城隍'
c2 = ['TW', 'CN', 'HK', 'SG', 'MY', 'MO']
m2 = mask_null & df['country'].isin(c2) & df['name'].str.contains(p2, na=False)
n2 = m2.sum()
print(f"  {n2:,} entries → Chinese Folk")
df.loc[m2, 'faith'] = 'Chinese Folk'
df.loc[m2, 'faith_tradition'] = 'Chinese Folk'

# ──────────────────────────────────────────
# 3. NULL FAITH → ISLAMIC NAME PATTERNS
# ──────────────────────────────────────────
print("--- Arabic/Islamic name → Islam ---")
mask_null = df['faith'].isna() | (df['faith'] == '')
p3 = (r'\b(masjid|مسجد|mosque|jami|jama|jamiya|islamic\s+center|'
      r'islamic\s+centre|islamic\s+society|musallah|musalla|musola|'
      r'madrasa|madrassah|madrasah|quran|qur\'an|qur’an|koran|'
      r'allah|khutbah|minbar|mihrab|minaret|'
      r'jamaat|anjuman|jamia|dargah|masjeed|masjith|'
      r'idgah|eidgah|cami|camii|mescit|camisi|'
      r'djamaa|djami|da\'wa|dawa|ibadah|ibadat|taqwa)\b')
m3 = mask_null & df['name'].str.contains(p3, na=False, case=False)
n3 = m3.sum()
print(f"  {n3:,} entries → Islam (Sunni)")
df.loc[m3, 'faith'] = 'Islam'
df.loc[m3, 'faith_tradition'] = 'Sunni'

# ──────────────────────────────────────────
# 4. NULL FAITH → BUDDHIST NAME PATTERNS
# ──────────────────────────────────────────
print("--- Buddhist name patterns → Buddhist ---")
mask_null = df['faith'].isna() | (df['faith'] == '')
p4 = (r'\b(wat|vihara|vihar|vihear|bot|stupa|chedi|'
      r'phra|buddha|buddhist|dharma|dhamma|'
      r'sangha|pagoda|boeddhistische|bouddhiste|budista|'
      r'kyaung|chùa|tự|phật|'
      r'bhikkhu|bhikshu|arhat|bodhisattva)\b')
m4 = mask_null & df['name'].str.contains(p4, na=False, case=False)
n4 = m4.sum()
print(f"  {n4:,} entries → Buddhist")
df.loc[m4, 'faith'] = 'Buddhist'
df.loc[m4, 'faith_tradition'] = 'Buddhist'

# ──────────────────────────────────────────
# 5. MUSLIM DOCTRINAL CLASSIFIER
# ──────────────────────────────────────────
print("--- Muslim doctrinal classifier ---")
mask_islam = df['faith'] == 'Islam'
n5_tot = mask_islam.sum()
print(f"  {n5_tot:,} Islam entries to classify")

# Reset empty faith_tradition for Islam entries to allow pattern matching
mi_unset = mask_islam & (df['faith_tradition'].isna() | (df['faith_tradition'] == ''))
df.loc[mi_unset, 'faith_tradition'] = ''  # mark as pending

patterns = [
    # Shia
    (r'\b(imam\w*\s+bargah|imambargah|imamzadeh|husayniyya|husseiniye|'
     r'azakhana|ashurkhana|ashoora|majlis|tazia|'
     r'rawdha|rawza|qom|qum|karbala|najaf|kufa|'
     r'khomeini|ayatollah|velayat|taqiyya|'
     r'jafari|ithna\s*ashari|twelver|'
     r'al-mustafa|al-ghadeer|ziyarat)\b', 'Shia'),
    (r'\bimam\w*\s+(hussain|hussein|ali|rida|reza|baqir|sadiq|kazim|jafar)\b', 'Shia'),
    # Sufi
    (r'\b(sufi|tasawwuf|tariqa|tariqah|zikr|dhikr|muraqaba|'
     r'qadiriyya|qadiriyah|chishti|naqshbandi|shadhili|'
     r'tijani|mouride|murid|pir|murshid|silsila|khanqah|tekke|dergah|'
     r'whirling|mevlevi|rifai|sama|ghawth|'
     r'niass|tijaniyya|layene|thierno)\b', 'Sunni/Sufi'),
    # Salafi
    (r'\b(salafi|salafiyya|wahhabi|ahl\s*(al\s*)?hadeeth|'
     r'ahl\s*(us\s*)?sunnah|muwahhid|dawah\s*salafiyya|'
     r'ibn\s*(baz|uthaymin)|albani)\b', 'Sunni/Salafi'),
    # Deobandi
    (r'\b(deobandi|darul\s*uloom|dar\s*ul\s*uloom|'
     r'jamia\s*deoband|tablighi|tabligh|ijtima|'
     r'fazail|bishwa\s*ijtema|khatme\s*nubuwwat)\b', 'Sunni/Deobandi'),
    # Ahmadiyya
    (r'\b(ahmadiyya|ahmadi|lahore\s*ahmadiyya|ahmadiyya\s*mujaddid|'
     r'mirza\s*ghulam|basharat|baitul|fazl\s*mosque|'
     r'mubarak\s*mosque|nusrat\s*jahan)\b', 'Ahmadiyya'),
    # Nation of Islam
    (r'\b(nation\s+of\s+islam|fi\.sha\.llaah|'
     r'mosque\s*(maryam|no\.?\s*(7|27|15))|'
     r'muhammad\s*temple|farrakhan|elijah\s*muhammad)\b', 'Nation of Islam'),
    # Quranist
    (r'\b(quranist|quraniyoon|quran\s*only|ahl\s*al\s*quran|'
     r'godislam|islami\s*quran)\b', 'Quranist'),
    # Ismaili
    (r'\b(ismaili|aga\s*khan|jamatkhana|dawoodi\s*bohra|'
     r'sulaymani|nazari|mohammed\s*shah)\b', 'Ismaili'),
]

trad_counts = []
n_classified = 0
for pat, trad in patterns:
    mp = mask_islam & (df['faith_tradition'] == '') & df['name'].str.contains(pat, na=False, case=False)
    np_ = mp.sum()
    if np_:
        trad_counts.append((trad, np_))
    df.loc[mp, 'faith_tradition'] = trad
    n_classified += np_

for trad, cnt in trad_counts:
    print(f"  {trad:20s} {cnt:>7,}")

# Default Sunni
m_def = mask_islam & (df['faith_tradition'] == '')
n_def = m_def.sum()
print(f"  {'Sunni (default)':20s} {n_def:>7,}")
df.loc[m_def, 'faith_tradition'] = 'Sunni'
n_classified += n_def

# ──────────────────────────────────────────
# WRITE TO DB — grouped by value, no row iteration
# ──────────────────────────────────────────
print(f"\n--- Writing to DB ({n_classified} doctrinal + null-faith changes) ---")
conn2 = sqlite3.connect(DB)
conn2.execute("PRAGMA journal_mode=WAL")
conn2.execute("BEGIN")

# Faith updates: group rowids by new faith value
faith_updates = {}
for faith_val, mask in [('Shinto', m), ('Chinese Folk', m2), ('Islam', m3), ('Buddhist', m4)]:
    rids = df.loc[mask, 'rowid']
    if len(rids):
        faith_updates[faith_val] = rids.values.tolist()

print("  Updating faith...")
for val, rids in faith_updates.items():
    for i in range(0, len(rids), 10000):
        chunk = rids[i:i+10000]
        ph = ",".join("?" * len(chunk))
        conn2.execute(f"UPDATE churches SET faith = ? WHERE rowid IN ({ph})", [val] + chunk)

# faith_tradition updates: group by new value
trad_updates = {}
for trad_val, mask in [
    ('Shinto', m), ('Chinese Folk', m2), ('Buddhist', m4),
    ('Sunni', m3),
]:
    rids = df.loc[mask, 'rowid']
    if len(rids):
        trad_updates[trad_val] = trad_updates.get(trad_val, []) + rids.values.tolist()

# Muslim doctrinal traditions
for trad in set(t for _, t in patterns):
    trad_updates.setdefault(trad, [])
for _, t in patterns:
    rids = df.loc[df['faith_tradition'] == t, 'rowid'].values.tolist()
    trad_updates[t] = list(set(trad_updates.get(t, []) + rids))
# Sunni default
sunni_rids = df.loc[mask_islam & (df['faith_tradition'] == 'Sunni'), 'rowid'].values.tolist()
trad_updates['Sunni'] = list(set(trad_updates.get('Sunni', []) + sunni_rids))

print("  Updating faith_tradition...")
for val, rids in trad_updates.items():
    if not rids:
        continue
    for i in range(0, len(rids), 10000):
        chunk = rids[i:i+10000]
        ph = ",".join("?" * len(chunk))
        conn2.execute(f"UPDATE churches SET faith_tradition = ? WHERE rowid IN ({ph})", [val] + chunk)

# Provenance log
print("  Logging provenance...")
conn2.execute(
    "INSERT INTO provenance_log (source, fields_populated, notes, status) VALUES (?, ?, ?, ?)",
    ('inmem_classifier', 'faith, faith_tradition',
     f'{n1} Shinto, {n2} Chinese Folk, {n3} Islam-name, {n4} Buddhist, '
     f'{n_classified} doctrinal ({n_def} default Sunni)',
     'completed')
)

conn2.execute("COMMIT")
conn2.close()

# ──────────────────────────────────────────
print("\n=== RESULTS ===")
print(f"  Shinto (JP shrine names):           {n1:>8,}")
print(f"  Chinese Folk (TW/CN/HK names):      {n2:>8,}")
print(f"  Islam (Arabic name patterns):       {n3:>8,}")
print(f"  Buddhist (name patterns):           {n4:>8,}")
print(f"  Muslim doctrinal classified:        {n_classified:>8,}")
print(f"  ──────────────────────────────────")
print(f"  TOTAL changes:                      {(n1+n2+n3+n4+n_classified):>8,}")

# Quick verification
conn3 = sqlite3.connect(DB)
still_null = conn3.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith = ''").fetchone()[0]
missing_trad = conn3.execute("SELECT COUNT(*) FROM churches WHERE faith_tradition IS NULL OR faith_tradition = ''").fetchone()[0]
print(f"\n  Remaining null faith: {still_null:,}")
print(f"  Remaining null faith_tradition: {missing_trad:,}")
print(f"  Remaining Islam without tradition: {conn3.execute('SELECT COUNT(*) FROM churches WHERE faith = ? AND (faith_tradition IS NULL OR faith_tradition = ?)', ['Islam', '']).fetchone()[0]:,}")
conn3.close()
print("DONE ✅")
