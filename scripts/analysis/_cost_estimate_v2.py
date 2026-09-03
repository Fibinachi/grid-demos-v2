"""Enhanced cost estimate with web-sourced pricing + pragmatic scenarios."""
import sqlite3

db = sqlite3.connect("E:\\grid\\churches.db")
total = db.execute("SELECT COUNT(*) FROM churches").fetchone()[0]

# --- Scope queries ---
null_faith = db.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith = ''").fetchone()[0]
no_coords = db.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NULL OR longitude IS NULL").fetchone()[0]

# All Islamic entries for doctrinal classification
islam_count = db.execute("SELECT COUNT(*) FROM churches WHERE faith = 'Islam'").fetchone()[0]

# All Shinto entries for classification
shinto_count = db.execute("SELECT COUNT(*) FROM churches WHERE faith = 'Shinto'").fetchone()[0]

# Jewish entries for tradition/denom classification
jewish_count = db.execute("SELECT COUNT(*) FROM churches WHERE faith = 'Jewish'").fetchone()[0]

# Buddhist for tradition classification
buddhist_count = db.execute("SELECT COUNT(*) FROM churches WHERE faith = 'Buddhist'").fetchone()[0]

# Hindu for tradition classification  
hindu_count = db.execute("SELECT COUNT(*) FROM churches WHERE faith = 'Hindu'").fetchone()[0]

# Entries with potential garbage names beyond simple URL match
garbage = db.execute("""
    SELECT COUNT(*) FROM churches WHERE 
    LENGTH(name) > 200 
    OR (name LIKE '%MAINTENANCE%' AND name NOT LIKE '%church%' AND name NOT LIKE '%temple%')
    OR (name LIKE '%BINGO%' AND name NOT LIKE '%church%')
    OR (name REGEXP '^[A-Z\s\.]{3,30}$' COLLATE NOCASE AND name NOT LIKE '%ST%' AND name NOT LIKE '%SAINT%')
""" if False else """ -- SQLite doesn't support REGEXP by default, use LIKE
    SELECT COUNT(*) FROM churches WHERE 
    LENGTH(name) > 200 
""").fetchone()[0]

garbage = db.execute("SELECT COUNT(*) FROM churches WHERE LENGTH(name) > 200").fetchone()[0]

# Duplicate churches (by name+lat+long)
name_coord_dupes = db.execute("""
    SELECT COUNT(*) FROM (
        SELECT name, ROUND(latitude, 4), ROUND(longitude, 4), COUNT(*) as cnt
        FROM churches WHERE name IS NOT NULL AND latitude IS NOT NULL
        GROUP BY name, ROUND(latitude, 4), ROUND(longitude, 4)
        HAVING cnt > 1
    )
""").fetchone()[0]

# Ungeocoded
ungeocoded = no_coords

# Count of entries in "Other" faith
other_faith = db.execute("SELECT COUNT(*) FROM churches WHERE faith = 'Other'").fetchone()[0]

# Null faith_tradition
null_tradition = db.execute("SELECT COUNT(*) FROM churches WHERE faith_tradition IS NULL OR faith_tradition = ''").fetchone()[0]

print(f"{'Total churches':30s} {total:>10,}")
print(f"{'Null faith':30s} {null_faith:>10,}")
print(f"{'Null faith_tradition':30s} {null_tradition:>10,}")
print(f"{'No coordinates':30s} {no_coords:>10,}")
print(f"{'Long names (>200 chars)':30s} {garbage:>10,}")
print(f"{'Name+coord duplicates':30s} {name_coord_dupes:>10,}")
print(f"{'Other faith':30s} {other_faith:>10,}")
print(f"{'Islam (doctrinal class.)':30s} {islam_count:>10,}")
print(f"{'Shinto (classification)':30s} {shinto_count:>10,}")
print(f"{'Jewish (classification)':30s} {jewish_count:>10,}")
print(f"{'Buddhist (classification)':30s} {buddhist_count:>10,}")
print(f"{'Hindu (classification)':30s} {hindu_count:>10,}")
print()

# === PRICING (DeepSeek API as of early 2026) ===
# DeepSeek-V3: $0.27/M input tokens, $1.10/M output tokens
# DeepSeek-R1: $0.55/M input, $2.19/M output
# Batch API (50% discount): $0.135/M input, $0.55/M output
# Cache hit (automatic for repeated prefix): ~$0.072/M input

pricing = {
    "v3":     {"input": 0.27, "output": 1.10, "label": "DeepSeek-V3 (on-demand)"},
    "r1":     {"input": 0.55, "output": 2.19, "label": "DeepSeek-R1 (on-demand)"},
    "v3_batch": {"input": 0.135, "output": 0.55, "label": "DeepSeek-V3 (batch, 50% off)"},
}

# Each scenario has a prompt template cost
scenarios = [
    # (label, count, input_tokens, output_tokens, description)
    ("Faith classification (null faith)", null_faith, 250, 60, "Classify ~82K entries with missing faith using name+country+denom"),
    ("Tradition classification (null trad)", null_tradition, 200, 50, "Assign faith_tradition to ~1.1M entries missing it"),
    ("Muslim doctrinal (342K Islam)", islam_count, 300, 80, "Shia/Sunni/Sufi/Salafi/Deobandi/etc. — 342K entries"),
    ("Dedup (name+coord clusters)", name_coord_dupes, 350, 100, "Resolve ~197K duplicate clusters — mark keep/merge/delete"),
    ("Reverse geocode (ungeocoded)", ungeocoded, 180, 40, "Place name→lat/lon for ~44K entries"),
    ("Full sweep (null traditions)", null_tradition, 200, 50, "Largest-bucket tradition classification"),
]

# Also: what if you did EVERY entry with a simple quality check?
# Prompt: name + faith + country → "OK" or flag issue
quality_check_input = 120  # Very compact: just name + metadata + "is this valid?"
quality_check_output = 20  # Just "OK" or "FLAG: reason"

print("=" * 72)
print("DEEPSEEK CREDIT COST ESTIMATE — GRID Database Cleanup")
print("=" * 72)
print()

for label, count, inp, out, desc in scenarios:
    print(f"--- {label} ---")
    print(f"  {desc}")
    print(f"  Entries: {count:>10,}")
    for pkey, p in pricing.items():
        cost = (count * inp / 1_000_000 * p["input"]) + (count * out / 1_000_000 * p["output"])
        input_cost = (count * inp / 1_000_000 * p["input"])
        output_cost = (count * out / 1_000_000 * p["output"])
        print(f"  {p['label']:35s}  ${cost:>8.2f}  (${input_cost:.2f} in + ${output_cost:.2f} out)")
    print()

print("--- QUALITY CHECK ON ALL ENTRIES (entry-by-entry validation) ---")
print(f"  ALL {total:,} entries, very compact prompt (120 in / 20 out)")
for pkey, p in pricing.items():
    cost = (total * quality_check_input / 1_000_000 * p["input"]) + (total * quality_check_output / 1_000_000 * p["output"])
    input_cost = (total * quality_check_input / 1_000_000 * p["input"])
    output_cost = (total * quality_check_output / 1_000_000 * p["output"])
    print(f"  {p['label']:35s}  ${cost:>8.2f}  (${input_cost:.2f} in + ${output_cost:.2f} out)")

print()
print("--- COMPARISON: Rule-based (SQL + regex) vs LLM ---")
print("  Most cleanup tasks are CHEAPER and FASTER with SQL/regex:")
print(f"  - Faith classification: already written (_classify_muslim_fast.py, etc.)")
print(f"  - Muslim doctrinal: 45 regex patterns ready, 0 \$ inference cost")
print(f"  - Shinto: country=JP + shrine name patterns, 0 \$")
print("  - Null faith: name-based patterns handle most, LLM only for edge cases")
print()
print(f"  If you use LLM ONLY for the 'hard' cases that regex can't handle")
print(f"  (~10% of each bucket):")
for pkey, p in pricing.items():
    hard_faith = null_faith * 0.10
    hard_islam = islam_count * 0.05  # Muslim doctrinal is harder, more remain
    hard_trad = null_tradition * 0.05
    hard_total = hard_faith + hard_islam + hard_trad
    cost = (hard_total * 300 / 1_000_000 * p["input"]) + (hard_total * 80 / 1_000_000 * p["output"])
    print(f"  {p['label']:35s}  ${cost:>8.2f}")

print()
print("--- BOTTOM LINE (batch pricing, the cheapest option) ---")
# Most pragmatic: batch DeepSeek-V3
v3_batch = pricing["v3_batch"]
# Scenario: run the already-written regex classifiers for bulk, use LLM for hard cases only
total_llm_entries = int(null_faith * 0.10 + null_tradition * 0.05 + islam_count * 0.05 + ungeocoded * 0.10)
total_llm_cost = (total_llm_entries * 300 / 1_000_000 * v3_batch["input"]) + (total_llm_entries * 80 / 1_000_000 * v3_batch["output"])
print(f"  Hybrid approach (regex + batch V3 LLM for edge cases):")
print(f"  ~{total_llm_entries:,} hard cases → \${total_llm_cost:.2f}")
print()
print(f"  FULLLLM approach (entry-by-entry for ALL 3.64M):")
print(f"  Quality check only: \${(total * 120 / 1_000_000 * v3_batch['input']) + (total * 20 / 1_000_000 * v3_batch['output']):.2f}")
full_class_cost = (total * 400 / 1_000_000 * v3_batch["input"]) + (total * 80 / 1_000_000 * v3_batch["output"])
print(f"  Full classification: \${full_class_cost:.2f}")
print(f"  Full classification (V3 on-demand): \${(total * 400 / 1_000_000 * pricing['v3']['input']) + (total * 80 / 1_000_000 * pricing['v3']['output']):.2f}")

db.close()
