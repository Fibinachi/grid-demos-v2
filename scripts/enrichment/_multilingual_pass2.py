"""Final multilingual pass on remaining NULL-faith overture_full records."""
import sqlite3, datetime

DB = 'churches.db'
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()
total = 0

def tag(label, faith, tradition, where_clause):
    global total
    c.execute(f"UPDATE churches SET faith=?, faith_tradition=? WHERE (faith IS NULL OR faith='') AND ({where_clause})", (faith, tradition))
    if c.rowcount > 0:
        print(f"  {label}: {c.rowcount:,}")
        total += c.rowcount

# ── Korean ──────────────────────────────────────────────────────────────────
print("=== Korean ===")
tag("교회 (church)", "Christian", "Christianity", "LOWER(name) LIKE '%교회%'")
tag("성당 (cathedral/parish)", "Christian", "Christianity", "LOWER(name) LIKE '%성당%'")
tag("예배 (worship)", "Christian", "Christianity", "LOWER(name) LIKE '%예배%'")
tag("선교 (mission)", "Christian", "Christianity", "LOWER(name) LIKE '%선교%'")
tag("하나님/예수님 (God/Jesus)", "Christian", "Christianity", "LOWER(name) LIKE '%하나님%' OR LOWER(name) LIKE '%예수%' OR LOWER(name) LIKE '%주님%'")
tag("장로 (Presbyterian)", "Christian", "Christianity", "LOWER(name) LIKE '%장로%'")
tag("침례/감리 (Baptist/Methodist)", "Christian", "Christianity", "LOWER(name) LIKE '%침례%' OR LOWER(name) LIKE '%감리%'")
tag("성결 (Holiness)", "Christian", "Christianity", "LOWER(name) LIKE '%성결%'")
tag("순복음 (Full Gospel)", "Christian", "Christianity", "LOWER(name) LIKE '%순복음%'")
tag("한인 (Korean ethnic church)", "Christian", "Christianity", "LOWER(name) LIKE '%한인%' OR LOWER(name) LIKE '%한국%'")

# ── Chinese ─────────────────────────────────────────────────────────────────
print("\n=== Chinese ===")
tag("教会/教堂 (church)", "Christian", "Christianity", "LOWER(name) LIKE '%教会%' OR LOWER(name) LIKE '%教堂%' OR LOWER(name) LIKE '%禮拜堂%'")
tag("基督 (Christ)", "Christian", "Christianity", "LOWER(name) LIKE '%基督%'")
tag("福音 (Gospel)", "Christian", "Christianity", "LOWER(name) LIKE '%福音%'")
tag("天主 (Catholic)", "Christian", "Christianity", "LOWER(name) LIKE '%天主%'")
tag("佛 (Buddha — Buddhist)", "Buddhist", "Buddhism", "LOWER(name) LIKE '%佛%' AND LOWER(name) NOT LIKE '%基督%' AND LOWER(name) NOT LIKE '%天主%'")
tag("寺/庙 (temple)", "Buddhist", "Buddhism", "LOWER(name) LIKE '%寺%' OR LOWER(name) LIKE '%廟%' OR LOWER(name) LIKE '%庙%'")
tag("道 (Taoist)", "Other", "Other", "LOWER(name) LIKE '%道觀%' OR LOWER(name) LIKE '%道观%' OR LOWER(name) LIKE '%道教%'")

# ── Japanese ────────────────────────────────────────────────────────────────
print("\n=== Japanese ===")
tag("教会 (church)", "Christian", "Christianity", "LOWER(name) LIKE '%教会%'")
tag("教会堂/聖堂", "Christian", "Christianity", "LOWER(name) LIKE '%教会堂%' OR LOWER(name) LIKE '%聖堂%'")
tag("神社 (Shinto shrine)", "Shinto", "Shinto", "LOWER(name) LIKE '%神社%' OR LOWER(name) LIKE '%神宮%'")
tag("寺 (Buddhist temple)", "Buddhist", "Buddhism", "LOWER(name) LIKE '%寺%' AND LOWER(name) NOT LIKE '%教会%' AND LOWER(name) NOT LIKE '%神社%'")

# ── Hindi/Sanskrit ──────────────────────────────────────────────────────────
print("\n=== Hindi/Sanskrit/Indian ===")
tag("मंदिर (mandir/temple)", "Hindu", "Hinduism", "LOWER(name) LIKE '%मंदिर%' OR LOWER(name) LIKE '%मन्दिर%'")
tag("गुरुद्वारा (gurudwara)", "Sikh", "Sikhism", "LOWER(name) LIKE '%गुरुद्वारा%'")
tag("मस्जिद (masjid)", "Islam", "Islam", "LOWER(name) LIKE '%मस्जिद%'")

# ── Arabic ──────────────────────────────────────────────────────────────────
print("\n=== Arabic ===")
tag("مسجد (masjid/mosque)", "Islam", "Islam", "LOWER(name) LIKE '%مسجد%' OR LOWER(name) LIKE '%جامع%'")
tag("كنيسة (kanisa/church)", "Christian", "Christianity", "LOWER(name) LIKE '%كنيسة%'")
tag("معبد (temple)", "Hindu", "Hinduism", "LOWER(name) LIKE '%معبد%' AND LOWER(name) NOT LIKE '%كنيسة%' AND LOWER(name) NOT LIKE '%مسجد%'")

# ── Hebrew ──────────────────────────────────────────────────────────────────
print("\n=== Hebrew ===")
tag("בית כנסת (synagogue)", "Jewish", "Judaism", "LOWER(name) LIKE '%בית כנסת%' OR LOWER(name) LIKE '%בית הכנסת%'")
tag("חב״ד (Chabad)", "Jewish", "Judaism", "LOWER(name) LIKE '%חב%ד%' OR LOWER(name) LIKE '%חבד%'")

# ── Thai ────────────────────────────────────────────────────────────────────
print("\n=== Thai ===")
tag("วัด (wat/temple)", "Buddhist", "Buddhism", "LOWER(name) LIKE '%วัด%'")
tag("โบสถ์ (church)", "Christian", "Christianity", "LOWER(name) LIKE '%โบสถ์%'")
tag("มัสยิด (masjid)", "Islam", "Islam", "LOWER(name) LIKE '%มัสยิด%'")

# ── Catch remaining by word patterns ────────────────────────────────────────
print("\n=== Remaining catch-all ===")
tag("mission/misión/missão", "Christian", "Christianity", "LOWER(name) LIKE '%mission%' OR LOWER(name) LIKE '%misión%' OR LOWER(name) LIKE '%missão%'")
tag("congregation/congregación", "Christian", "Christianity", "LOWER(name) LIKE '%congregation%' OR LOWER(name) LIKE '%congregación%' OR LOWER(name) LIKE '%congregação%'")
tag("pastor/pasteur", "Christian", "Christianity", "LOWER(name) LIKE '%pastor%' OR LOWER(name) LIKE '%pasteur%'")
tag("diocese/diócesis/diocèse", "Christian", "Christianity", "LOWER(name) LIKE '%diocese%' OR LOWER(name) LIKE '%diócesis%' OR LOWER(name) LIKE '%diocèse%'")
tag("christian/crestin/cristão", "Christian", "Christianity", "LOWER(name) LIKE '%cristã%' OR LOWER(name) LIKE '%cristian%' OR LOWER(name) LIKE '%crestin%'")
tag("presbytery/presbitério", "Christian", "Christianity", "LOWER(name) LIKE '%presbiter%'")
tag("spiritual", "Christian", "Christianity", "LOWER(name) LIKE '%spiritual%' AND LOWER(name) NOT LIKE '%bahai%' AND LOWER(name) NOT LIKE '%spiritual assembly%'")
tag("baha'i/bahai", "Bahai", "Bahai", "LOWER(name) LIKE '%bahai%' OR LOWER(name) LIKE '%baha i%'")

conn.commit()
print(f"\nTotal tagged: {total:,}")
c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith=''")
print(f"Remaining NULL-faith: {c.fetchone()[0]:,}")

c.execute("""INSERT INTO provenance_log (source, script_name, started_at, completed_at,
    churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES ('manual','_multilingual_pass2.py',?,?,?,0,'faith,faith_tradition','completed',?)""",
    (datetime.datetime.now().isoformat(), datetime.datetime.now().isoformat(), total,
     f'Multilingual pass 2: {total} tagged (Korean, Chinese, Japanese, Arabic, Hebrew, Thai, etc.)'))
conn.commit()
conn.close()
