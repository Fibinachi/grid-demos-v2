"""Audit what data is in DB vs what's still in CSVs."""
import sqlite3, os, csv, glob

d = r'E:\grid'
conn = sqlite3.connect(d + '/churches.db')
cur = conn.cursor()

# Check DB contents
cur.execute('SELECT COUNT(*) FROM churches')
total = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM churches WHERE email != ''")
email = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM churches WHERE pastor_name != ''")
pastor = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM churches WHERE phone != ''")
phone = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM churches WHERE ein != ''")
ein = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM churches WHERE has_website = 1')
web = cur.fetchone()[0]

print('=== What is in the DB ===')
print(f'Total churches: {total:,}')
print(f'With email: {email:,}')
print(f'With pastor name: {pastor:,}')
print(f'With phone: {phone:,}')
print(f'With EIN: {ein:,}')
print(f'Has website: {web:,}')

# Check which CSVs haven't been imported
conn.close()

print(f'\n=== Key data files NOT yet in DB ===')

# Check church_master_emails.csv (900 contacts)
path = d + '/church_master_emails.csv'
if os.path.exists(path):
    with open(path, encoding='utf-8-sig') as f:
        r = list(csv.DictReader(f))
    print(f'  church_master_emails.csv: {len(r)} rows - NOT imported')

# Check enriched_churches.csv (IRS cross-ref with addresses)
path = d + '/enriched_churches.csv'
if os.path.exists(path):
    with open(path, encoding='utf-8-sig') as f:
        r = list(csv.DictReader(f))
    print(f'  enriched_churches.csv: {len(r)} rows - NOT imported (has IRS addresses)')

# Check church_clean_send.csv
path = d + '/church_clean_send.csv'
if os.path.exists(path):
    with open(path, encoding='utf-8-sig') as f:
        r = list(csv.DictReader(f))
    print(f'  church_clean_send.csv: {len(r)} rows - NOT imported')

# Check found_chunk_1b_results.csv (Phase 1b)
path = d + '/found_chunk_1b_results.csv'
if os.path.exists(path):
    with open(path, encoding='utf-8-sig') as f:
        r = list(csv.DictReader(f))
    with_email = sum(1 for x in r if x.get('email','').strip())
    print(f'  found_chunk_1b_results.csv (Phase 1b): {len(r)} rows, {with_email} emails - NOT imported')

# Check final_send_list_10k.csv
path = d + '/final_send_list_10k.csv'
if os.path.exists(path):
    with open(path, encoding='utf-8-sig') as f:
        r = list(csv.DictReader(f))
    print(f'  final_send_list_10k.csv: {len(r)} rows - NOT imported')

# Check Phase 1 chunks still on EC2
print(f'\n  Phase 1 chunk 1 (18.188.95.190): Still running - ~825 emails pending')
print(f'  Phase 1 chunk 2 (18.191.145.108): Still running - ~825 emails pending')
print(f'  Pastor finder (3.138.187.55): Running - 14,993 pastor names being processed')
print(f'  IRS finder 0 (3.19.141.81): Running - 136,716 churches')
print(f'  IRS finder 1 (18.191.24.204): Running - 136,716 churches')
