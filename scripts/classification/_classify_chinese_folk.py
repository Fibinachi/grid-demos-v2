"""
_classify_chinese_folk.py — Classify Chinese folk religion, Taoist, and Buddhist entries.

Targets: OSM osm_import entries with null faith, focusing on TW, CN, HK, and other
Chinese diaspora communities. Uses Chinese characters + landmark_type patterns.

Classification tiers:
  Tier 1 — Buddhist temple (寺,  Buddhist temple landmark)
  Tier 2 — Chinese folk / Taoist (宮, 廟, 祠, 壇, 庵, 觀)
  Tier 3 — Ancestral hall (祠堂, 宗祠, 祖祠)
  Tier 4 — Christian (教堂, 教會, 福音)
  Tier 5 — Muslim (清真, 伊斯兰)
  Tier 6 — Vietnamese patterns (đình, chùa, miếu, thánh thất)
  Tier 7 — Korean patterns (절, 사찰)
"""
import sqlite3

DB = 'churches.db'
conn = sqlite3.connect(DB, timeout=60)
c = conn.cursor()

def log(label, count):
    if count:
        print(f"  {label}: {count:,}")

def apply(condition, faith, label):
    c.execute(f"UPDATE churches SET faith=? WHERE (faith IS NULL OR faith='') AND ({condition})", (faith,))
    log(label, c.rowcount)

start = sqlite3.connect(DB).execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith=''").fetchone()[0]
print(f"Starting null faith: {start:,}\n")

# ═══════════════════════════════════════════════════════════════
# Tier 1: Buddhist temples (寺)
# ═══════════════════════════════════════════════════════════════
print("--- Tier 1: Buddhist (寺 temple pattern) ---")
# 寺 (sì) = Buddhist temple. Very reliable signal.
apply("country IN ('TW','CN','HK','MO') AND name LIKE '%寺%' AND landmark_type IN ('temple','pagoda','','shrine')",
      "Buddhist", "TW/CN/HK 寺 Buddhist temple")
apply("name LIKE '%寺%' AND (landmark_type='temple' OR landmark_type='') AND country IN ('KR','JP')",
      "Buddhist", "KR/JP 寺 Buddhist temple")
# 庵 (ān) = Buddhist nunnery / small temple
apply("country IN ('TW','CN','HK') AND name LIKE '%庵%'",
      "Buddhist", "TW/CN/HK 庵 Buddhist nunnery")
conn.commit()

# ═══════════════════════════════════════════════════════════════
# Tier 2: Chinese folk / Taoist (宮, 廟, 祠, 壇)
# ═══════════════════════════════════════════════════════════════
print("\n--- Tier 2: Chinese folk / Taoist ---")
# 宮 (gōng) = palace/temple — Taoist or Chinese folk
apply("country IN ('TW','CN','HK','MO') AND name LIKE '%宮%' AND landmark_type IN ('temple','shrine','','shrine')",
      "Taoist", "TW/CN/HK 宮 Taoist temple")
# 廟 (miào) = temple — usually Chinese folk / Taoist
apply("country IN ('TW','CN','HK','MO') AND name LIKE '%廟%'",
      "Taoist", "TW/CN/HK 廟 Chinese folk temple")
# 壇 (tán) = altar — Taoist / Chinese folk
apply("country IN ('TW','CN','HK','MO') AND name LIKE '%壇%'",
      "Taoist", "TW/CN/HK 壇 Taoist altar")
# 觀 / 观 (guàn) = Taoist temple
apply("country IN ('TW','CN','HK','MO') AND (name LIKE '%觀%' OR name LIKE '%观%')",
      "Taoist", "TW/CN/HK 觀/观 Taoist observatory")
# 府 (fǔ) = palace — Taoist / Chinese folk
apply("country IN ('TW','CN','HK') AND name LIKE '%府%' AND (landmark_type='temple' OR landmark_type='shrine' OR landmark_type='')",
      "Taoist", "TW/CN/HK 府 temple")
# 王爺 / 王爷 (wángyé) = Chinese folk deity temples
apply("country IN ('TW','CN','HK') AND (name LIKE '%王爺%' OR name LIKE '%王爷%')",
      "Taoist", "TW/CN/HK 王爺 Chinese folk")
conn.commit()

# ═══════════════════════════════════════════════════════════════
# Tier 3: Ancestral halls (祠堂, 宗祠, 祖祠)
# ═══════════════════════════════════════════════════════════════
print("\n--- Tier 3: Ancestral halls → Taoist ---")
apply("name LIKE '%祠%' AND country IN ('TW','CN','HK')",
      "Taoist", "TW/CN/HK 祠 ancestral hall")
# 宗祠, 祖祠, 祠堂
apply("name LIKE '%宗祠%' OR name LIKE '%祖祠%' OR name LIKE '%祠堂%' OR name LIKE '%家祠%'",
      "Taoist", "Chinese ancestral hall")
conn.commit()

# ═══════════════════════════════════════════════════════════════
# Tier 4: Christian (教堂, 教會, 福音)
# ═══════════════════════════════════════════════════════════════
print("\n--- Tier 4: Christian Chinese patterns ---")
apply("name LIKE '%教堂%' OR name LIKE '%教會%' OR name LIKE '%教会%' OR name LIKE '%福音%'",
      "Christian", "Chinese Christian patterns")
# 天主堂 = Catholic church
apply("name LIKE '%天主堂%' OR name LIKE '%天主%'",
      "Christian", "Chinese Catholic")
# 基督 = Christ
apply("name LIKE '%基督%'",
      "Christian", "Chinese基督 Christian")
conn.commit()

# ═══════════════════════════════════════════════════════════════
# Tier 5: Muslim (清真, 伊斯兰)
# ═══════════════════════════════════════════════════════════════
print("\n--- Tier 5: Muslim Chinese patterns ---")
apply("name LIKE '%清真%' OR name LIKE '%伊斯兰%' OR name LIKE '%回教%' OR name LIKE '%礼拜寺%'",
      "Islam", "Chinese Muslim patterns")
conn.commit()

# ═══════════════════════════════════════════════════════════════
# Tier 6: Vietnamese patterns
# ═══════════════════════════════════════════════════════════════
print("\n--- Tier 6: Vietnamese patterns ---")
# đình = communal house / temple, chùa = Buddhist pagoda
apply("country='VN' AND (name LIKE '%Chùa%' OR name LIKE '%chùa%')",
      "Buddhist", "VN Chùa (Buddhist)")
# Thánh thất = Holy See (Cao Dai)
apply("country='VN' AND (name LIKE '%Thánh thất%' OR name LIKE '%thánh thất%')",
      "Other", "VN Cao Dai Holy See")
# Đình / đền = temple/shrine
apply("country='VN' AND (name LIKE '%Đình%' OR name LIKE '%đền%' OR name LIKE '%đền%') AND landmark_type IN ('temple','shrine','')",
      "Taoist", "VN Đình/đền Chinese folk")
# Miếu = temple/shrine (Vietnamese)
apply("country='VN' AND (name LIKE '%Miếu%' OR name LIKE '%miếu%')",
      "Taoist", "VN Miếu temple")
# Nhà thờ = church (Vietnamese)
apply("country='VN' AND (name LIKE '%Nhà thờ%' OR name LIKE '%nhà thờ%')",
      "Christian", "VN Nhà thờ church")
conn.commit()

# ═══════════════════════════════════════════════════════════════
# Tier 7: Korean patterns
# ═══════════════════════════════════════════════════════════════
print("\n--- Tier 7: Korean patterns ---")
# 절 (jeol) = Buddhist temple (Korean)
apply("country='KR' AND name LIKE '%절%'",
      "Buddhist", "KR 절 Buddhist temple")
# 사찰 (sachal) = Buddhist temple
apply("country='KR' AND name LIKE '%사찰%'",
      "Buddhist", "KR 사찰 Buddhist temple")
conn.commit()

# ═══════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════
final = sqlite3.connect(DB).execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith=''").fetchone()[0]
classified = start - final
print(f"\n{'=' * 60}")
print(f"Total classified: {classified:,}")
print(f"Remaining null faith: {final:,}")

c.execute("INSERT INTO provenance_log (script_name, churches_updated, churches_inserted, notes, completed_at, status, fields_populated) VALUES ('_classify_chinese_folk', ?, 0, ?, datetime('now'), 'completed', 'faith')", (classified, f"Classified {classified} Chinese folk/Taoist/Buddhist entries"))
conn.commit()
conn.close()
print("Done!")
