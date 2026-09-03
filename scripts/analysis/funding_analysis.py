goal = 30000  # CAD target

# Sent (12) - conservative midpoint estimates in USD
sent = {
    'Anglican Foundation': 3000,
    'Global Ministries (UMC)': 10000,
    'GBHEM GRASP': 5000,
    'UCC Foundation': 3000,
    'Methodist Foundation': 3000,
    'Rotary Columbia': 15000,
    'Autism Speaks': 7500,
    'Lime Connect': 5000,
    'ADDA': 2000,
    'AL Auxiliary': 3500,
    'DAV': 3500,
}

queued_midpoints = {
    'Batch 3 (30 targeted)': 3500,
    'Lineage (13)': 1500,
    'Mensa/High-IQ (4)': 3000,
    'Autism Parent (14)': 2000,
    'Film Industry (8)': 2500,
    'Arts/Nonprofit (22)': 2000,
    'Foundation Mass (800)': 1500,
}

total_sent = sum(sent.values())
total_queued = sum(v * int(k.split('(')[1].split(')')[0]) for k, v in queued_midpoints.items())
total_all = total_sent + total_queued
total_ask_cad = total_all * 1.30  # rough USD to CAD

print(f'=== TOTAL ASK ===')
print(f'Goal:                    ${goal:>8,} CAD')
print(f'Already sent (11 tracked): ${total_sent:>8,} USD')
print(f'Queued (105):              ${total_queued:>8,} USD')
print(f'Grand total (116):         ${total_all:>8,} USD')
print(f'In CAD:                    ${total_ask_cad:>8,.0f} CAD')
print()

print('=== RESPONSE RATE ESTIMATES ===')
print()
print('Cold email to foundations (800 mass batch):')
print('  Reply rate:          1-3%  (~8-24 replies)')
print('  With actual funding: very low - most fund orgs, not individuals')
print()
print('Targeted personalized (70 targeted):')
print('  Reply rate:          10-20% (~7-14 replies)')
print('  With actual funding: 5-10% (~4-7 may have programs)')
print()
print('Already sent (12):')
print('  Reply rate:          25-40% (~3-5 replies)')
print('  With actual funding: 10-20% (~1-3 may lead to money)')
print()

print('=== REALISTIC FUNDING OUTCOME ===')
print(f'Conservative:        $2,000 - $8,000 USD  (${2000*1.3:,.0f}-${8000*1.3:,.0f} CAD)')
print(f'Moderate:            $8,000 - $20,000 USD (${8000*1.3:,.0f}-${20000*1.3:,.0f} CAD)')
print(f'Optimistic:          $20,000 - $50,000+ USD')
print(f'Goal:                ${goal:,} CAD')
print()

print('=== BEST SINGLE BETS ===')
print('1. Mensa Foundation - $200K+ annual pool (essay ready)')
print('2. Union Plus Scholarship - $1K-$4K (grandfather USW, opens late Jun)')
print('3. Rotary Columbia - $10K-$30K (already sent)')
print('4. Anglican Foundation - $1K-$5K (already sent)')
print('5. Lime Connect - $2.5K-$10K (already sent)')
