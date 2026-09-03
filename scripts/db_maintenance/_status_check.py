# -*- coding: utf-8 -*-
with open('AGENTS.md', 'r', encoding='utf-8') as f:
    t = f.read()
print(f'Size: {len(t)} bytes, Lines: {t.count(chr(10))+1}')
print(f'06-23 bold rows (**06-23**): {t.count("**06-23**")}')
print(f'Cross-source validation: {t.count("Cross-source validation")}')
print(f'Agent Instructions headers: {t.count("# Agent Instructions")}')
# Check both copies of Medium Priority for the Per-country row
print(f'Per-country diocese gap row: {t.count("Per-country diocese gap")}')
# Count 06-22 and 06-23 date refs
print(f'06-22 references: {t.count("06-22")}')
print(f'06-23 references: {t.count("06-23")}')
print(f'Recent Fixes headers: {t.count("### Recent Fixes")}')
print(f'Maps Generated headers: {t.count("### Maps Generated")}')
print(f'Medium Priority headers: {t.count("### Medium Priority")}')
print(f'Global Diocese Coverage headers: {t.count("### Global Diocese Coverage")}')
print(f'First 5 chars: {repr(t[:5])}')
print(f'Last 100 chars: {repr(t[-100:])}')
