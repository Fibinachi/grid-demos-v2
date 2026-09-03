"""Query PSS diocese data for Phase 2 planning."""
import sqlite3
c = sqlite3.connect('E:/grid/churches.db')
cur = c.cursor()

# 1. PSS diocese codes
cur.execute("SELECT diocese, COUNT(*) as cnt FROM pss_schools WHERE diocese IS NOT NULL AND diocese != '' GROUP BY diocese ORDER BY cnt DESC LIMIT 30")
print("=== PSS DIOCESE CODES ===")
for r in cur.fetchall():
    print(f"  {r[0]:15s} {r[1]}")

# 2. Merge target schools with diocese codes
cur.execute("SELECT COUNT(*) FROM pss_schools WHERE merge_target_id IS NOT NULL AND diocese IS NOT NULL AND diocese != ''")
cnt = cur.fetchone()[0]
print(f"\nMerged+diocese: {cnt}")

# 3. relig_label breakdown (these describe the congregation/order)
cur.execute("SELECT relig_label, COUNT(*) as cnt FROM pss_schools WHERE relig_label IS NOT NULL AND relig_label != '' GROUP BY relig_label ORDER BY cnt DESC LIMIT 40")
print("\n=== PSS RELIG LABELS (top 40) ===")
for r in cur.fetchall():
    print(f"  {str(r[0])[:65]:65s} {r[1]}")

# 4. orient_label breakdown
cur.execute("SELECT orient_label, COUNT(*) as cnt FROM pss_schools WHERE orient_label IS NOT NULL AND orient_label != '' GROUP BY orient_label ORDER BY cnt DESC LIMIT 20")
print("\n=== PSS ORIENT LABELS (top 20) ===")
for r in cur.fetchall():
    print(f"  {str(r[0])[:60]:60s} {r[1]}")

# 5. Sample PSS schools with diocese codes to see what we're working with
cur.execute("SELECT pinst, pcity, pstabb, diocese, relig_label, orient_label FROM pss_schools WHERE diocese IS NOT NULL AND diocese != '' LIMIT 20")
print("\n=== SAMPLE PSS SCHOOLS WITH DIOCESE ===")
for r in cur.fetchall():
    print(f"  {r[0][:50]:50s} | {r[1]:20s} {r[2]:5s} | code={r[3]:8s} | {str(r[4] or '')[:30]:30s} | {str(r[5] or '')[:20]:20s}")

# 6. How many schools (in churches table) already have enrichment rows?
cur.execute("SELECT COUNT(*) FROM churches c JOIN church_enrichment ce ON c.id = ce.church_id WHERE c.landmark_type = 'school'")
in_enrich = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM churches WHERE landmark_type = 'school'")
total_schools = cur.fetchone()[0]
print(f"\n=== SCHOOL ENRICHMENT STATUS ===")
print(f"  Schools in enrichment: {in_enrich} / {total_schools}")

# 7. Schools with existing diocese in enrichment
cur.execute("SELECT COUNT(*) FROM churches c JOIN church_enrichment ce ON c.id = ce.church_id WHERE c.landmark_type = 'school' AND ce.diocese IS NOT NULL AND ce.diocese != ''")
with_diocese = cur.fetchone()[0]
print(f"  Schools with diocese in enrichment: {with_diocese}")

# 8. What schools have county_fips in enrichment?
cur.execute("SELECT COUNT(*) FROM churches c JOIN church_enrichment ce ON c.id = ce.church_id WHERE c.landmark_type = 'school' AND ce.county_fips IS NOT NULL AND ce.county_fips != ''")
with_fips = cur.fetchone()[0]
print(f"  Schools with county_fips in enrichment: {with_fips}")

# 9. Schools without enrichment row
cur.execute("SELECT COUNT(*) FROM churches WHERE landmark_type = 'school' AND id NOT IN (SELECT church_id FROM church_enrichment)")
no_enrich = cur.fetchone()[0]
print(f"  Schools without enrichment row: {no_enrich}")

c.close()
