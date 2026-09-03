"""Quick cost estimate for DeepSeek per-entry cleanup."""
import sqlite3

db = sqlite3.connect("E:\\grid\\churches.db")

total = db.execute("SELECT COUNT(*) FROM churches").fetchone()[0]

null_faith = db.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith = ''").fetchone()[0]

null_name = db.execute("SELECT COUNT(*) FROM churches WHERE name IS NULL OR name = ''").fetchone()[0]

no_coords = db.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NULL OR longitude IS NULL").fetchone()[0]

# Potential junk names
junk = db.execute("""
    SELECT COUNT(*) FROM churches WHERE 
    name LIKE '%facebook%' OR name LIKE '%youtube%' OR name LIKE '%twitter%'
    OR name LIKE '%http%' OR name LIKE '%www.%' OR name LIKE '%instagram%'
""").fetchone()[0]

# Just name obviously not a church (URLs, social media, HTML pages)
page_artifact = db.execute("""
    SELECT COUNT(*) FROM churches WHERE 
    name LIKE '%.html%' OR name LIKE '%%.com%' OR name LIKE '%twitter%'
    OR name LIKE '%facebook%' OR name LIKE '%youtube%' OR name LIKE '%instagram%'
    OR name LIKE '%search%result%' OR name LIKE '%search_results%'
    OR name LIKE '%page not found%' OR name LIKE '%404%'
""").fetchone()[0]

# Print what we found
print(f"{'Total churches':30s} {total:>10,}")
print(f"{'Null/no faith':30s} {null_faith:>10,}")
print(f"{'Null/empty name':30s} {null_name:>10,}")
print(f"{'No coordinates':30s} {no_coords:>10,}")
print(f"{'Junk names (social/URL)':30s} {junk:>10,}")
print(f"{'Page artifacts':30s} {page_artifact:>10,}")
print()

# Cost estimates based on typical DeepSeek API pricing
# DeepSeek-V3: ~$0.27/M input tokens, ~$1.10/M output tokens (as of late 2025/early 2026)
# DeepSeek-R1: ~$0.55/M input, ~$2.19/M output
# Typical prompt: ~200 tokens input (name + metadata + instruction)
# Typical response: ~50 tokens output (classification/decision)
# Per-entry cost varies by what "cleanup" means

print("=== COST ESTIMATES ===")
print("Assumes DeepSeek-V3 pricing (~$0.27/M input, ~$1.10/M output)")
print("Prompt: ~250 tokens (instruction + church name + metadata + few-shot)")
print("Response: ~60 tokens (classification/reasoning)")
print()

per_entry_tokens_input = 250
per_entry_tokens_output = 60
cost_input_per_1m = 0.27
cost_output_per_1m = 1.10

def estimate(label, count, pct_of_total=100):
    input_tokens = count * per_entry_tokens_input
    output_tokens = count * per_entry_tokens_output
    cost = (input_tokens / 1_000_000 * cost_input_per_1m) + (output_tokens / 1_000_000 * cost_output_per_1m)
    pct = count / total * 100
    print(f"{label:30s} ${cost:>8.2f}  ({count:>10,} entries, {pct:.1f}%)")

# Scenarios
print("--- Scenario A: Just the obvious junk ---")
estimate("Junk name cleanup", junk, junk/total*100)

print()
print("--- Scenario B: All null-faith entries ---")
estimate("Null faith classification", null_faith, null_faith/total*100)

print()
print("--- Scenario C: All ungeocoded entries ---")
estimate("Reverse geocode", no_coords, no_coords/total*100)

print()
print("--- Scenario D: Full ML classification sweep (faith, tradition, denom) ---")
# This would be a larger prompt with more context
per_entry_full = 400  # more context for full classification
cost_input_full = (per_entry_full / 1_000_000) * cost_input_per_1m
cost_output_full = (80 / 1_000_000) * cost_output_per_1m
cost_full_per_entry = cost_input_full + cost_output_full
# Apply only to entries that don't already have faith
target = null_faith + total  # could do all entries
cost_all = total * cost_full_per_entry
cost_null = null_faith * cost_full_per_entry
print(f"Per-entry cost (full class): ${cost_full_per_entry:.5f}")
print(f"If applied to all {total:,} entries: ${cost_all:,.2f}")
print(f"If applied to {null_faith:,} null-faith entries: ${cost_null:,.2f}")

print()
print("--- Scenario E: Name+quality review on ALL entries (the big one) ---")
# Very compact prompt: just verify name + faith + coords make sense
per_entry_tiny_input = 150
per_entry_tiny_output = 30
cost_input_tiny = (per_entry_tiny_input / 1_000_000) * cost_input_per_1m
cost_output_tiny = (per_entry_tiny_output / 1_000_000) * cost_output_per_1m
cost_tiny_per_entry = cost_input_tiny + cost_output_tiny
cost_tiny_all = total * cost_tiny_per_entry
print(f"Per-entry cost: ${cost_tiny_per_entry:.5f}")
print(f"Total for all {total:,}: ${cost_tiny_all:,.2f}")
print(f"Total for all {total:,} (at R1 pricing): ${total * ((150/1e6)*0.55 + (30/1e6)*2.19):,.2f}")

# Time estimate
print()
print("=== TIME ESTIMATE ===")
print(f"At 1 req/sec: {total/3600:.1f} hours = {total/3600/24:.1f} days")
print(f"At 10 req/sec (batch): {total/36000:.1f} hours = {total/36000/24:.1f} days")
print(f"At 100 req/sec (aggressive): {total/360000:.1f} hours = {total/360000/24:.1f} days")

db.close()
