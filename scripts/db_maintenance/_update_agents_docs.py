"""Update AGENTS.md with 06-23 diocese validation results."""
import re

with open('AGENTS.md', 'r', encoding='utf-8') as f:
    text = f.read()

changes = 0

# ---- EDIT 1: Add to Medium Priority table (both occurrences) ----
old_medium = '| Afro-diasporic religion audit | name patterns | ~TBD |'
new_medium = (
    '| Afro-diasporic religion audit | name patterns | ~TBD |\n'
    '| Per-country diocese gap analysis | gcatholic / catholicdata.org | 2,278 missing circumscriptions |'
)
cnt = text.count(old_medium)
print(f'Edit 1 (Medium Priority row): found {cnt} occurrences')
assert cnt == 2, f'Expected 2, got {cnt}'
text = text.replace(old_medium, new_medium)
changes += 1

# ---- EDIT 2: Add cross-source validation note under Global Diocese Coverage ----
old_gdc = (
    '### Global Diocese Coverage\n'
    '| Country | Coverage | Source |\n'
    '|---|---|---|\n'
    '| France | 6,515/6,515 (100%) | gcatholic scraper |\n'
    '| United States | 26,845/38,742 (69%) | County propagation |\n'
    '| Rest of world | 0 | Pending gcatholic scraper completion |\n'
    '\n'
    '### Maps Generated'
)
new_gdc = (
    '### Global Diocese Coverage\n'
    '| Country | Coverage | Source |\n'
    '|---|---|---|\n'
    '| France | 6,515/6,515 (100%) | gcatholic scraper |\n'
    '| United States | 26,845/38,742 (69%) | County propagation |\n'
    '| Rest of world | 0 | Pending gcatholic scraper completion |\n'
    '\n'
    '**Cross-source validation** (2026-06-23): `_validate_dioceses.py` confirmed '
    '**763 distinct diocese values** (25.1% of Vatican\'s 3,041). '
    'See full section above for per-country breakdown.\n'
    '\n'
    '### Maps Generated'
)
cnt = text.count(old_gdc)
print(f'Edit 2 (Global Diocese Coverage): found {cnt} occurrences')
assert cnt == 2, f'Expected 2, got {cnt}'
text = text.replace(old_gdc, new_gdc)
changes += 1

# ---- EDIT 3: Add 06-23 diocese validation to Recent Fixes ----
old_last_row = (
    '| **06-22** | **Page artifact cleanup (Phase 2)** | '
    '`scripts/db_maintenance/cleanup_page_artifacts_phase2.py` | '
    '**179 + 10 NULL-id records deleted**: 177 missing from Phase 1\'s hardcoded ID list '
    '(same patterns, broader sweep) + 10 NULL-id garbage records '
    '(`holy_sites_import` URLs/maps links, social page titles). '
    'Deleted from 8 child tables. 179 provenance entries logged. '
    'Zero remaining matches across all patterns. |\n'
    '\n'
    '### Reconstructing past provenance'
)
new_last_row = (
    '| **06-22** | **Page artifact cleanup (Phase 2)** | '
    '`scripts/db_maintenance/cleanup_page_artifacts_phase2.py` | '
    '**179 + 10 NULL-id records deleted**: 177 missing from Phase 1\'s hardcoded ID list '
    '(same patterns, broader sweep) + 10 NULL-id garbage records '
    '(`holy_sites_import` URLs/maps links, social page titles). '
    'Deleted from 8 child tables. 179 provenance entries logged. '
    'Zero remaining matches across all patterns. |\n'
    '| **06-23** | **Diocese coverage validation** | '
    '`_validate_dioceses.py` | '
    '**763 distinct diocese values** (25.1% of Vatican 3,041). '
    'US 357 raw to 214 normalized (0 dupes), FR 85/98, IT 54/~225, CA 53/70, PH 48/86, GB 36/~35. '
    'Zero Africa/Asia/Oceania. 39,354 churches with diocese (38,323 US). '
    'GoodLands: 69 French polygons. Eastern/Orthodox: 17 entries. |\n'
    '\n'
    '### Reconstructing past provenance'
)
cnt = text.count(old_last_row)
print(f'Edit 3 (Recent Fixes last row): found {cnt} occurrences')
assert cnt == 2, f'Expected 2, got {cnt}'
text = text.replace(old_last_row, new_last_row)
changes += 1

with open('AGENTS.md', 'w', encoding='utf-8') as f:
    f.write(text)

print(f'\nAll {changes} edits applied successfully.')
