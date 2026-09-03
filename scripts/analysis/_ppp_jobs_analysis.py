"""Analyze PPP jobs_reported as a measure of church employment."""
import sqlite3
db = sqlite3.connect('e:/grid/churches.db')

# Jobs distribution
print('=== Jobs Reported Distribution (PPP-matched churches) ===')
for r in db.execute('''
    SELECT 
        CASE 
            WHEN jobs_reported = 0 THEN '0 (volunteer only?)'
            WHEN jobs_reported = 1 THEN '1'
            WHEN jobs_reported BETWEEN 2 AND 3 THEN '2-3'
            WHEN jobs_reported BETWEEN 4 AND 5 THEN '4-5'
            WHEN jobs_reported BETWEEN 6 AND 10 THEN '6-10'
            WHEN jobs_reported BETWEEN 11 AND 20 THEN '11-20'
            WHEN jobs_reported BETWEEN 21 AND 50 THEN '21-50'
            WHEN jobs_reported BETWEEN 51 AND 100 THEN '51-100'
            WHEN jobs_reported > 100 THEN '100+'
        END as bucket,
        COUNT(*) as n,
        ROUND(COUNT(*)*100.0 / (SELECT COUNT(*) FROM sba_ppp_loans WHERE church_id IS NOT NULL), 1) as pct
    FROM sba_ppp_loans
    WHERE church_id IS NOT NULL
    GROUP BY bucket
    ORDER BY MIN(jobs_reported)
'''):
    print(f'  {r[0]:<25} {r[1]:>8,}  ({r[2]:.1f}%)')

# Compute stats in Python (SQLite lacks MEDIAN/PERCENTILE_CONT)
import numpy as np
jobs = [r[0] for r in db.execute(
    'SELECT jobs_reported FROM sba_ppp_loans WHERE church_id IS NOT NULL AND jobs_reported > 0'
)]
jobs_arr = np.array(jobs)

print()
print('=== Top-line stats ===')
print(f'  Churches with PPP (jobs>0): {len(jobs_arr):,}')
print(f'  Mean jobs: {jobs_arr.mean():.1f}')
print(f'  Median jobs: {np.median(jobs_arr):.0f}')
print(f'  StDev: {jobs_arr.std():.1f}')

print()
print('=== Percentiles ===')
for p in [10, 25, 50, 75, 90, 95, 99]:
    print(f'  P{p:>2}: {np.percentile(jobs_arr, p):>6.0f} jobs')

# By faith tradition
print()
print('=== Avg Jobs by Faith Tradition (top 15) ===')
for r in db.execute('''
    SELECT COALESCE(c.tradition, '(none)'), COUNT(*) as n, ROUND(AVG(p.jobs_reported),1) as avg_jobs,
           ROUND(AVG(p.loan_amount),0) as avg_loan
    FROM sba_ppp_loans p
    JOIN churches c ON p.church_id = c.id
    WHERE p.jobs_reported > 0
    GROUP BY c.tradition
    ORDER BY n DESC
    LIMIT 15
'''):
    print(f'  {r[0]:<35} {r[1]:>6,} churches  avg {r[2]:>5.1f} jobs  ${r[3]:>9,.0f} loan')

# PPP formula: loan = 2.5 * monthly payroll. So monthly payroll = loan / 2.5
# Per employee: monthly payroll / jobs_reported
print()
print('=== Estimated monthly payroll per employee (loan / 2.5 / jobs) ===')
print('(PPP allowed max loan = 2.5 x average monthly payroll)')
for r in db.execute('''
    SELECT 
        ROUND(AVG(p.loan_amount / 2.5 / NULLIF(p.jobs_reported, 0)), 0) as monthly_per_emp,
        ROUND(AVG(p.loan_amount / NULLIF(p.jobs_reported, 0)), 0) as annual_per_emp
    FROM sba_ppp_loans p
    JOIN churches c ON p.church_id = c.id
    WHERE p.jobs_reported > 0 AND p.loan_amount > 0
'''):
    print(f'  Monthly payroll per employee: ${r[0]:,}')
    print(f'  Annual implied per employee:  ${r[1]:,}')

# By RUCC
print()
print('=== Jobs by RUCC ===')
for r in db.execute('''
    SELECT r.rucc_code, r.description, COUNT(*) as n,
           ROUND(AVG(p.jobs_reported),1) as avg_jobs,
           ROUND(AVG(p.loan_amount),0) as avg_loan
    FROM sba_ppp_loans p
    JOIN churches c ON p.church_id = c.id
    JOIN rucc_codes r ON c.county_fips_5 = r.fips
    WHERE p.jobs_reported > 0
    GROUP BY r.rucc_code
    ORDER BY r.rucc_code
'''):
    print(f'  RUCC {r[0]}: {r[1]:<55} {r[2]:>5,} churches  avg {r[3]:>5.1f} jobs  ${r[4]:>9,.0f}')

# Caveats
print()
print('=== CAVEATS ===')
print('jobs_reported = number of employees on payroll at time of PPP application.')
print('This includes: pastor(s), staff, custodians, musicians, admin, etc.')
print('This EXCLUDES: volunteers, contractors (1099), unpaid clergy.')
print()
print('For small churches (median ~5 jobs), this likely captures:')
print('  1 pastor + 1-2 part-time staff + 1-2 support = ~5 people')
print('For larger churches (P90=45 jobs), this is the full paid staff.')

# Churches with 0 jobs - what are they?
print()
print('=== Churches reporting 0 jobs ===')
for r in db.execute('''
    SELECT c.name, c.tradition, c.city, p.loan_amount, p.business_type
    FROM sba_ppp_loans p
    JOIN churches c ON p.church_id = c.id
    WHERE p.jobs_reported = 0
    LIMIT 10
'''):
    print(f'  {r[0]:<50} {r[1]:<20} ${r[3]:>10,.0f}  type={r[4]}')

db.close()
