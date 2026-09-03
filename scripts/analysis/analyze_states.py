"""Analyze state distribution for Wyoming Rule chunking"""
import csv, math
from collections import Counter

# Read IRS data
with open('irs_churches.csv', encoding='utf-8-sig') as f:
    churches = list(csv.DictReader(f))

# Count by state
state_counts = Counter()
for r in churches:
    state = r.get('STATE', '').strip()
    if state:
        state_counts[state] += 1

total = sum(state_counts.values())
print(f"Total churches: {total:,}")
print(f"Number of states/territories: {len(state_counts)}")
print()

# Find the "Wyoming" - state with fewest churches
min_state = min(state_counts, key=state_counts.get)
min_count = state_counts[min_state]
print(f"Smallest state: {min_state} ({min_count:,} churches)")
print()

# Wyoming Rule: each chunk = ~min_count churches
chunk_size = min_count
num_chunks = math.ceil(total / chunk_size)
print(f"Wyoming Rule chunk size: {chunk_size:,} (={min_state}'s count)")
print(f"Number of chunks needed: {num_chunks}")
print()

# Sort states by count descending
sorted_states = sorted(state_counts.items(), key=lambda x: -x[1])
print(f"\n{'State':<6} {'Count':>8} {'Chunks':>6}")
print("-" * 22)
for state, count in sorted_states:
    num = math.ceil(count / chunk_size)
    print(f"{state:<6} {count:>8,} {num:>6}")

# Show how we'd group them
print(f"\n\n=== Proposed {num_chunks} Chunks ===")
chunks = [[] for _ in range(num_chunks)]
chunk_sizes = [0] * num_chunks

# Greedy: assign largest states first to chunks with most room
for state, count in sorted_states:
    # Find chunk with most remaining capacity
    best_chunk = min(range(num_chunks), key=lambda i: chunk_sizes[i])
    chunks[best_chunk].append((state, count))
    chunk_sizes[best_chunk] += count

for i, (chunk, size) in enumerate(zip(chunks, chunk_sizes)):
    states_str = ", ".join(f"{s}({c:,})" for s, c in chunk)
    print(f"\nChunk {i}: {size:,} churches")
    print(f"  States: {states_str}")
