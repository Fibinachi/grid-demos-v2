"""
Replace old census table names with new names across all project scripts.
Run AFTER _rename_census_tables.py.
"""
import os
import re

BASE = r'E:\grid'
REPLACEMENTS = [
    ('church_census_us',            'church_census_us'),
    ('church_census_ca',  'church_census_ca'),
    ('church_census_mx',  'church_census_mx'),
    ('county_census_us',            'county_census_us'),
    ('municipio_census_mx',   'municipio_census_mx'),
    ('tract_lookup_us',     'tract_lookup_us'),
]

# Files to skip (already updated or generated)
SKIP = [
    '_rename_census_tables.py',
    '__pycache__',
    '.git',
    '.venv',
]

def replace_in_file(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    original = content
    for old, new in REPLACEMENTS:
        content = content.replace(old, new)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    # Process root directory .py files
    for f in os.listdir(BASE):
        if f.endswith('.py'):
            fp = os.path.join(BASE, f)
            if replace_in_file(fp):
                print(f'  OK {f}')
    
    # Process scripts directory
    scripts_dir = os.path.join(BASE, 'scripts')
    for root, dirs, files in os.walk(scripts_dir):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for f in files:
            if f.endswith('.py') and f not in SKIP:
                fp = os.path.join(root, f)
                if replace_in_file(fp):
                    rel = os.path.relpath(fp, BASE)
                    print(f'  OK {rel}')
    
    # Process AGENTS.md
    agents_md = os.path.join(BASE, 'AGENTS.md')
    if os.path.exists(agents_md):
        if replace_in_file(agents_md):
            print('  OK AGENTS.md')
    
    # Also check E:\grid root for .md, .txt
    for f in os.listdir(BASE):
        if f.endswith(('.md', '.txt')) and f != 'AGENTS.md':
            fp = os.path.join(BASE, f)
            try:
                if replace_in_file(fp):
                    print(f'  OK {f}')
            except:
                pass

    print('\nDone.')

if __name__ == '__main__':
    main()
