
"""Church vacancy detection pipeline.
Identifies churches with open staff positions via multiple sources.
Vacancy = high-value outreach: verified contacts, active decision-makers.

Sources:
  1. Denominational job boards — scraped listings
  2. ChurchStaffing.com — public API
  3. Church website signals — "We're Hiring", "Pastoral Search", "Transition"
  4. Staff change detection — pastor_left vs church_staff history

Usage:
    python scripts/enrichment/detect_vacancies.py           # full scan
    python scripts/enrichment/detect_vacancies.py --source pcusa  # single source
    python scripts/enrichment/detect_vacancies.py --dry-run
"""
import json, os, re, sqlite3, sys, time, urllib.request
from datetime import datetime, timedelta

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT, 'churches.db')

DRY_RUN = '--dry-run' in sys.argv
SOURCE = None
for a in sys.argv:
    if a.startswith('--source='):
        SOURCE = a.split('=')[1]

def log(msg):
    print(f"  {msg}", flush=True)

# ═══════════════════════════════════════════════════════════════════
# SOURCE 1: Denominational Job Boards
# ═══════════════════════════════════════════════════════════════════

DENOM_JOB_BOARDS = {
    'PCUSA': {
        'url': 'https://www.pcusa.org/job-board/',
        'feed': 'https://jobs.pcusa.org/api/v1/jobs',
        'type': 'api',
    },
    'UMC': {
        'url': 'https://www.umc.org/en/content/church-careers',
        'feed': 'https://www.resourceumc.org/api/jobs',
        'type': 'api',
    },
    'SBC': {
        'url': 'https://www.sbc.net/jobs/',
        'feed': 'https://jobs.sbc.net/wp-json/wp/v2/jobs',
        'type': 'api',
    },
    'ELCA': {
        'url': 'https://www.elca.org/Resources/ELCA-Careers',
        'type': 'page',
    },
    'Episcopal': {
        'url': 'https://www.episcopalchurch.org/job-postings/',
        'type': 'page',
    },
    'ACNA': {
        'url': 'https://anglicanchurch.net/jobs/',
        'type': 'page',
    },
    'ChurchStaffing': {
        'url': 'https://www.churchstaffing.com/',
        'feed': 'https://www.churchstaffing.com/api/jobs/search',
        'type': 'api',
    },
    'JustChurchJobs': {
        'url': 'https://www.justchurchjobs.com/',
        'feed': 'https://www.justchurchjobs.com/api/jobs',
        'type': 'api',
        'notes': '50+ job board integrations, seminary/college feeds, strong SBC/nondenom presence',
    },
    'MinistryJobs': {
        'url': 'https://www.ministryjobs.com/',
        'feed': 'https://www.ministryjobs.com/api/listings',
        'type': 'api',
        'notes': 'Froot Group network, worship/youth/senior pastor focus, mid-size churches',
    },
    'ChristianCareerCenter': {
        'url': 'https://www.christiancareercenter.com/',
        'feed': 'https://www.christiancareercenter.com/api/jobs',
        'type': 'api',
    },
    'MinistryList': {
        'url': 'https://www.ministrylist.com/',
        'type': 'page',
        'notes': 'Free job board, all denominations',
    },
    'ChurchJobsOnline': {
        'url': 'https://www.churchjobsonline.com/',
        'type': 'page',
    },
}

def scrape_denom_jobs(conn):
    """Scrape denominational job boards for vacancy listings."""
    c = conn.cursor()
    total = 0
    
    for name, config in DENOM_JOB_BOARDS.items():
        if SOURCE and SOURCE not in name.lower():
            continue
        if config.get('type') != 'api':
            log(f"  {name}: requires page scraping (skipping for now)")
            continue
        
        log(f"  {name}: {config['feed']}")
        try:
            req = urllib.request.Request(config['feed'],
                headers={'User-Agent': 'GrantWizard/1.0', 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            
            # Try common JSON job listing formats
            jobs = data if isinstance(data, list) else data.get('jobs', data.get('results', data.get('data', [])))
            log(f"    Found {len(jobs)} listings")
            
            for job in jobs[:10]:  # Limit per source for now
                title = job.get('title', job.get('job_title', job.get('name', '')))
                church = job.get('organization', job.get('company', job.get('church_name', '')))
                city = job.get('city', job.get('location', ''))
                url = job.get('url', job.get('apply_url', job.get('link', '')))
                
                if not church:
                    continue
                
                if DRY_RUN:
                    print(f"    {title[:60]} @ {church[:40]} ({city[:20]})")
                    continue
                
                c.execute("""
                    INSERT OR IGNORE INTO church_vacancies 
                    (source, source_url, job_title, church_name, city, detected_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (name, url, title, church, city, datetime.utcnow().isoformat()))
                total += 1
                
        except Exception as e:
            log(f"    Failed: {e}")
    
    conn.commit()
    return total


# ═══════════════════════════════════════════════════════════════════
# SOURCE 2: Church Website Signals
# ═══════════════════════════════════════════════════════════════════

VACANCY_SIGNALS = [
    (r'pastoral\s+search\s+committee', 0.9, 'pastoral_search'),
    (r'we\s+are\s+hiring', 0.7, 'hiring'),
    (r'job\s+opening', 0.6, 'job_opening'),
    (r'now\s+accepting\s+applications', 0.7, 'accepting_applications'),
    (r'position\s+available', 0.6, 'position_available'),
    (r'search\s+for\s+a\s+(new\s+)?pastor', 0.9, 'pastor_search'),
    (r'interim\s+(pastor|rector|minister)', 0.95, 'interim_pastor'),
    (r'pulpit\s+(vacancy|committee|search)', 0.95, 'pulpit_vacancy'),
    (r'transitional\s+(pastor|ministry)', 0.8, 'transitional'),
    (r'seeking\s+(pastor|rector|minister|youth\s+director|worship\s+leader)', 0.9, 'seeking_staff'),
]

# Denomination self-identification patterns from job postings
# These are the exact phrases churches use to describe themselves
DENOM_SELF_ID = [
    (r'(?:we\s+are|a(?:n)?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,5})\s+(?:church|congregation|parish|fellowship|community)', 0.95),
    (r'affiliated\s+with\s+(?:the\s+)?([A-Z][A-Za-z\s.]+?)(?:,|\.|\s+and)', 0.9),
    (r'member\s+(?:church\s+)?of\s+(?:the\s+)?([A-Z][A-Za-z\s.]+?)(?:,|\.)', 0.9),
    (r'part\s+of\s+(?:the\s+)?([A-Z][A-Za-z\s.]+?)(?:denomination|convention|diocese|synod|presbytery|association)', 0.85),
    (r'(SBC|PCUSA|UMC|ELCA|LCMS|ACNA|AME|COGIC|AG|ABCUSA|UCC|RCA|CRC|PCA|EPC|ECO)', 0.95),
    (r'(Southern Baptist|United Methodist|Presbyterian\s+Church\s+USA|Episcopal|Lutheran|Anglican|Baptist|Methodist|Pentecostal|Reformed|Orthodox|Catholic|Mennonite|Wesleyan|Nazarene|Covenant|Evangelical\s+Free|Assemblies\s+of\s+God)', 0.9),
]

def scan_website_signals(conn):
    """Scan church websites for vacancy signals in scraped text."""
    c = conn.cursor()
    
    # These columns may contain scraped website text
    text_cols = ['statement_of_faith', 'notes', 'community_impact']
    
    total = 0
    for col in text_cols:
        for pattern, confidence, signal_type in VACANCY_SIGNALS:
            c.execute(f"""
                SELECT id, name, city, state, website, {col}
                FROM churches 
                WHERE {col} LIKE '%' || ? || '%'
            """, (pattern,))
            
            for row in c.fetchall():
                church_id, name, city, state, website, text = row
                
                if DRY_RUN:
                    if total < 10:
                        print(f"    [{signal_type}] {name[:50]} ({city}, {state})")
                    total += 1
                    continue
                
                c.execute("""
                    INSERT OR IGNORE INTO church_vacancies 
                    (church_id, source, source_url, job_title, church_name, city, 
                     state, confidence, signal_type, detected_at)
                    VALUES (?, 'website_signal', ?, ?, ?, ?, ?, ?, ?, ?)
                """, (church_id, website, signal_type.replace('_', ' ').title(),
                      name, city, state, confidence, signal_type,
                      datetime.utcnow().isoformat()))
                total += 1
    
    conn.commit()
    return total


# ═══════════════════════════════════════════════════════════════════
# SOURCE 3: Staff Change Detection
# ═══════════════════════════════════════════════════════════════════

def detect_staff_changes(conn):
    """Compare church_staff history to detect pastor turnover (potential vacancy)."""
    c = conn.cursor()
    
    c.execute("""
        SELECT c.id, c.name, c.city, c.state, c.website, c.pastor_name,
               cs.pastor_name as historical_pastor
        FROM churches c
        LEFT JOIN church_staff cs ON c.id = cs.church_id
        WHERE c.pastor_name IS NULL OR c.pastor_name = ''
          AND cs.pastor_name IS NOT NULL AND cs.pastor_name != ''
        LIMIT 1000
    """)
    
    total = 0
    for row in c.fetchall():
        church_id, name, city, state, website, current, historical = row
        
        if DRY_RUN:
            if total < 10:
                print(f"    Staff change: {name[:50]} ({city}, {state}) — was: {historical[:30]}")
            total += 1
            continue
        
        c.execute("""
            INSERT OR IGNORE INTO church_vacancies
            (church_id, source, source_url, job_title, church_name, city, state,
             confidence, signal_type, details, detected_at)
            VALUES (?, 'staff_change', ?, 'Pastor (Staff Change Detected)', ?, ?, ?,
             0.8, 'staff_change', ?, ?)
        """, (church_id, website, name, city, state,
              f"Previous pastor: {historical}; Current: {current or 'unknown'}",
              datetime.utcnow().isoformat()))
        total += 1
    
    conn.commit()
    return total


# ═══════════════════════════════════════════════════════════════════
# SOURCE 4: Denomination Self-Identification from Vacancy Text
# ═══════════════════════════════════════════════════════════════════

def extract_denom_from_vacancy(text):
    """Extract denomination from job posting / website text.
    Returns (denom_name, confidence) or (None, 0)."""
    if not text:
        return None, 0
    
    for pattern, confidence in DENOM_SELF_ID:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            denom = match.group(1) if match.lastindex else match.group(0)
            denom = denom.strip().strip('.,;:')
            if len(denom) > 3:
                return denom, confidence
    
    return None, 0


def enrich_denom_from_vacancies(conn):
    """Update church denomination from self-identification in vacancy listings."""
    c = conn.cursor()
    
    # Get all vacancy listings with text
    c.execute("""
        SELECT v.id, v.church_id, v.job_title, v.details, 
               c.name as church_name, c.denomination, c.website
        FROM church_vacancies v
        LEFT JOIN churches c ON v.church_id = c.id
        WHERE (v.job_title IS NOT NULL OR v.details IS NOT NULL)
          AND (c.denomination IS NULL OR c.denomination = '')
        LIMIT 5000
    """)
    
    updated = 0
    for row in c.fetchall():
        vac_id, church_id, job_title, details, church_name, current_denom, website = row
        text = f"{job_title or ''} {details or ''} {church_name or ''}"
        
        denom, confidence = extract_denom_from_vacancy(text)
        if denom and confidence >= 0.85:
            if DRY_RUN:
                if updated < 10:
                    print(f"    [{confidence}] #{church_id}: '{current_denom or '?'}' -> '{denom}' ({church_name[:40]})")
                updated += 1
                continue
            
            c.execute("""
                UPDATE churches SET 
                    denomination = ?,
                    classification_source = 'vacancy_self_id',
                    last_updated = ?
                WHERE id = ? AND (denomination IS NULL OR denomination = '')
            """, (denom, datetime.utcnow().isoformat(), church_id))
            
            if c.rowcount > 0:
                updated += 1
                log(f"    Classified #{church_id}: {church_name[:50]} -> {denom}")
    
    conn.commit()
    return updated

ADDRESS_PATTERNS = [
    (r'(\d+\s+\w+(?:\s+\w+)*)\s+(?:Road|Rd|Street|St|Avenue|Ave|Blvd|Drive|Dr|Lane|Ln|Way|Ct|Circle|Cir|Pl|Hwy|Pkwy)\b', 0.8),
    (r'located\s+(?:at|in)\s+([^,.]+(?:Road|Rd|Street|St|Avenue|Ave|Blvd|Drive|Dr|Lane|Ln|Way|Ct))', 0.7),
]

def extract_address_from_vacancy(text):
    for pattern, confidence in ADDRESS_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            addr = match.group(0).strip()
            if len(addr) > 10: return addr, confidence
    return None, 0

def discover_new_churches(conn):
    """Find vacancies for churches not in DB, extract addresses, insert new records."""
    c = conn.cursor()
    c.execute("""
        SELECT v.id, v.church_name, v.city, v.state, v.job_title,
               v.source, v.source_url, v.details, v.detected_at
        FROM church_vacancies v WHERE v.church_id IS NULL
          AND v.church_name IS NOT NULL AND v.church_name != ''
        ORDER BY v.detected_at DESC
    """)
    new_churches, enriched = 0, 0
    for row in c.fetchall():
        vac_id, name, city, state, job_title, source, url, details, detected = row
        c.execute("""SELECT id, name, address FROM churches
            WHERE city=? AND state=? AND (name LIKE '%'||?||'%' OR ? LIKE '%'||name||'%') LIMIT 1""",
            (city, state, name, name))
        match = c.fetchone()
        if match:
            church_id, matched_name, existing_addr = match
            text = f"{job_title or ''} {details or ''}"
            addr, _ = extract_address_from_vacancy(text)
            if addr and (not existing_addr or existing_addr == ''):
                if not DRY_RUN: c.execute("UPDATE churches SET address=?, address_source='vacancy_listing', last_updated=? WHERE id=?", (addr, datetime.utcnow().isoformat(), church_id))
                enriched += 1
            if not DRY_RUN: c.execute("UPDATE church_vacancies SET church_id=? WHERE id=?", (church_id, vac_id))
        else:
            if DRY_RUN:
                if new_churches < 5: print(f"    NEW: {name[:50]} ({city}, {state})")
                new_churches += 1; continue
            text = f"{job_title or ''} {details or ''} {name}"
            denom, _ = extract_denom_from_vacancy(text)
            addr, _ = extract_address_from_vacancy(text)
            c.execute("""INSERT INTO churches (name, city, state, address, denomination, website,
                source, classification_source, org_type, website_source, last_updated)
                VALUES (?,?,?,?,?,?,'vacancy_discovery',?,'church','vacancy_listing',?)""",
                (name, city, state, addr, denom, url, 'vacancy_self_id' if denom else None, datetime.utcnow().isoformat()))
            new_id = c.lastrowid
            c.execute("UPDATE church_vacancies SET church_id=? WHERE id=?", (new_id, vac_id))
            new_churches += 1
            if new_churches <= 5: log(f"    NEW #{new_id}: {name[:50]} denom={denom or '?'}")
    conn.commit()
    return new_churches, enriched

JOB_TO_CAPABILITY = {
    r'youth pastor|youth minister|youth director|student pastor|student minister': ('has_youth', 1),
    r'children.*(?:pastor|minister|director)|kids.*(?:pastor|minister|director)': ('has_children', 1),
    r'preschool.*(?:director|teacher|minister)|nursery.*(?:director|coordinator)': ('has_preschool', 1),
    r'daycare.*(?:director|manager|supervisor)': ('has_daycare', 1),
    r'senior.*(?:pastor|minister|adult)|older adult.*(?:pastor|minister)': ('has_seniors', 1),
    r'worship.*(?:pastor|leader|director)|music.*(?:pastor|minister|director)': ('worship_style', 'contemporary'),
    r'traditional.*worship|organist|choir.*director|music.*traditional': ('worship_style', 'traditional'),
    r'missions.*(?:pastor|director|coordinator)|outreach.*(?:pastor|director)': ('has_missions', 1),
    r'counseling.*(?:pastor|minister)|pastoral.*care|counselor': ('has_counseling', 1),
    r'recovery.*(?:pastor|minister|director)|addiction.*(?:minister|counselor)': ('has_recovery', 1),
    r'esl.*(?:teacher|director|coordinator)|english.*second.*language': ('has_esl', 1),
    r'food.*pantry.*(?:director|coordinator|manager)|community.*meals': ('has_food_pantry', 1),
    r'sports.*(?:minister|director|coordinator)|recreation.*(?:minister|director)': ('has_sports', 1),
    r'campus.*pastor|multi.?site.*(?:pastor|director)|satellite.*(?:pastor|campus)': ('campus_count', 2),
    r'executive.*pastor|admin.*pastor|operations.*(?:pastor|director)|business.*admin': ('staff_count', 5),
    r'associate.*pastor|assistant.*pastor': ('staff_count', 3),
}

# Salary → budget estimation
# Pastor salary is typically 20-35% of total church budget
POSITION_BUDGET_MULTIPLIER = {
    'senior pastor': 3.5,    # salary ~28% of budget
    'lead pastor': 3.5,
    'executive pastor': 3.0,
    'associate pastor': 4.0,
    'youth pastor': 5.0,     # youth pastor ~20% of budget
    'children': 6.0,
    'worship pastor': 4.5,
    'worship leader': 5.0,
    'admin': 5.0,
    'default': 4.0,
}

SALARY_PATTERN = re.compile(
    r'(?:salary|compensation|pay|stipend)[:\s]*\$?([\d,]+(?:\.\d{2})?)\s*-?\s*\$?([\d,]+(?:\.\d{2})?)?'
    r'|\$([\d,]+(?:\.\d{2})?)\s*-?\s*\$?([\d,]+(?:\.\d{2})?)?\s*(?:per\s+year|/yr|annually|annual)',
    re.IGNORECASE
)

def extract_salary(text):
    """Extract salary range from job listing text. Returns (low, high, budget_estimate)."""
    match = SALARY_PATTERN.search(text) if text else None
    if not match:
        return None, None, None
    
    def parse(s):
        try: return float(s.replace(',', ''))
        except: return None
    
    vals = [parse(g) for g in match.groups() if g]
    if not vals:
        return None, None, None
    
    low = min(vals)
    high = max(vals) if len(vals) > 1 else low
    
    # Estimate budget from salary and position
    text_lower = text.lower()
    multiplier = POSITION_BUDGET_MULTIPLIER.get('default', 4.0)
    for role, mult in POSITION_BUDGET_MULTIPLIER.items():
        if role in text_lower:
            multiplier = mult
            break
    
    budget_est = int(low * multiplier)
    return low, high, budget_est

def infer_church_capabilities(conn):
    """Infer church attributes from vacancy job titles."""
    c = conn.cursor()
    updated = 0
    c.execute("""
        SELECT v.id, v.church_id, v.job_title, v.details, c.name
        FROM church_vacancies v JOIN churches c ON v.church_id = c.id
        WHERE v.job_title IS NOT NULL AND v.job_title != ''
    """)
    for vac_id, church_id, job_title, details, name in c.fetchall():
        text = f"{job_title} {details or ''}"
        for pattern, (field, value) in JOB_TO_CAPABILITY.items():
            if re.search(pattern, text, re.IGNORECASE):
                c.execute(f"SELECT {field} FROM churches WHERE id=?", (church_id,))
                current = c.fetchone()[0]
                if current is None or current == 0 or current == '':
                    if not DRY_RUN:
                        c.execute(f"UPDATE churches SET {field}=?, last_updated=? WHERE id=?",
                                 (value, datetime.utcnow().isoformat(), church_id))
                    updated += 1
                    break
    conn.commit()
    return updated

def estimate_church_budgets(conn):
    """Extract salary data from job listings and estimate church budgets."""
    c = conn.cursor()
    enriched = 0
    
    c.execute("""
        SELECT v.id, v.church_id, v.job_title, v.details, c.name, c.attendance_est
        FROM church_vacancies v JOIN churches c ON v.church_id = c.id
        WHERE (v.job_title LIKE '%$%' OR v.details LIKE '%$%'
               OR v.job_title LIKE '%salary%' OR v.details LIKE '%salary%'
               OR v.job_title LIKE '%compensation%' OR v.details LIKE '%compensation%')
    """)
    
    for vac_id, church_id, job_title, details, name, attendance in c.fetchall():
        text = f"{job_title} {details or ''}"
        low, high, budget = extract_salary(text)
        
        if budget and budget > 10000:  # Sanity check
            if not DRY_RUN:
                c.execute("""
                    UPDATE church_vacancies SET 
                        contact_email = CASE WHEN contact_email IS NULL THEN ? END,
                        details = ?,
                        confidence = MAX(confidence, 0.85)
                    WHERE id = ?
                """, (f"Salary: ${low:,.0f} - ${high:,.0f}, Budget est: ${budget:,}", 
                      f"{details or ''} [Salary: ${low:,.0f}-${high:,.0f}]", vac_id))
            
            enriched += 1
            if enriched <= 10:
                # Cross-check with attendance
                att_check = f" (attendance: {attendance:,})" if attendance else ""
                log(f"    ${low:,.0f}-${high:,.0f} → budget ~${budget:,} "
                    f"| {name[:40]}{att_check}")
    
    conn.commit()
    return enriched

THEOLOGY_KEYWORDS = {
    'reformed': ['reformed', 'calvinist', 'tulip', 'westminster', 'dordt', 'sovereign grace',
                 'doctrines of grace', 'confessional', 'covenant theology'],
    'charismatic': ['charismatic', 'pentecostal', 'speaking in tongues', 'gifts of the spirit',
                    'holy spirit', 'prophetic', 'healing ministry', 'signs and wonders'],
    'cessationist': ['cessationist', 'sign gifts have ceased'],
    'complementarian': ['complementarian', 'male headship', 'male leadership', 'biblical manhood'],
    'egalitarian': ['egalitarian', 'women in ministry', 'female pastor', 'gender equality'],
    'dispensational': ['dispensational', 'premillennial', 'pre-trib', 'rapture', 'end times'],
    'covenant': ['covenant theology', 'infant baptism', 'paedobaptism', 'covenant child'],
    'creedal': ['creedal', 'nicene', 'apostles creed', 'athanasian', 'historic creeds'],
    'missional': ['missional', 'church planting', 'gospel-centered', 'incarnational'],
    'liturgical': ['liturgical', 'liturgy', 'eucharist', 'lectionary', 'book of common prayer'],
    'contemporary': ['contemporary worship', 'modern worship', 'praise band', 'relevant'],
    'traditional': ['traditional', 'hymns', 'organ', 'choir', 'robed'],
    'social_justice': ['social justice', 'racial reconciliation', 'justice', 'advocacy',
                       'oppressed', 'marginalized', 'anti-racism'],
    'family_integrated': ['family integrated', 'family worship', 'no youth group'],
    'house_church': ['house church', 'simple church', 'organic church'],
    'multiethnic': ['multiethnic', 'multi-ethnic', 'multicultural', 'diverse congregation'],
    'baptist_distinctive': ['believers baptism', 'credobaptism', 'regenerate membership',
                            'soul liberty', 'priesthood of all believers'],
}

def extract_theology_keywords(conn):
    """Extract theological distinctives from full vacancy text."""
    c = conn.cursor()
    tagged = 0
    
    c.execute("""
        SELECT v.id, v.church_id, v.job_title, v.details, c.name, c.doctrinal_alignment
        FROM church_vacancies v JOIN churches c ON v.church_id = c.id
        WHERE v.details IS NOT NULL AND v.details != ''
    """)
    
    for vac_id, church_id, job_title, details, name, current_doctrine in c.fetchall():
        text = f"{job_title or ''} {details or ''}".lower()
        found = []
        
        for category, keywords in THEOLOGY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                found.append(category)
        
        if found:
            new_tags = ', '.join(found)
            existing = current_doctrine or ''
            
            if not DRY_RUN:
                # Update vacancy with keywords
                c.execute("UPDATE church_vacancies SET details = ?, signal_type = ? WHERE id = ?",
                         (f"{details or ''}\n[Theology: {new_tags}]", 
                          f"theology:{new_tags}", vac_id))
                
                # Update church doctrinal alignment if not already set
                if not existing:
                    c.execute("""
                        UPDATE churches SET doctrinal_alignment = ?, last_updated = ? WHERE id = ?
                    """, (new_tags, datetime.utcnow().isoformat(), church_id))
            
            tagged += 1
            if tagged <= 15:
                log(f"    [{new_tags}] {name[:50]}")
    
    conn.commit()
    return tagged

def create_tables(conn):
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS church_vacancies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            church_id INTEGER REFERENCES churches(id),
            source TEXT NOT NULL,
            listing_url TEXT,                  -- URL of the job listing itself
            source_url TEXT,                   -- Church website or source homepage
            job_title TEXT,
            church_name TEXT NOT NULL,
            city TEXT,
            state TEXT,
            confidence REAL DEFAULT 0.5,
            signal_type TEXT,
            details TEXT,
            contact_name TEXT,
            contact_email TEXT,
            contact_phone TEXT,
            application_deadline TEXT,
            is_new_church INTEGER DEFAULT 0,   -- 1 if discovered via job listing
            detected_at TEXT NOT NULL,
            verified_at TEXT,
            UNIQUE(source, church_name, city, job_title)
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_vacancy_church ON church_vacancies(church_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_vacancy_source ON church_vacancies(source)")
    conn.commit()
    log("Table church_vacancies ready")

def main():
    log("=== Church Vacancy Detection Pipeline ===")
    
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA journal_mode=DELETE")
    
    create_tables(conn)
    
    results = {}
    
    # Source 1: Denom job boards
    log("\n1. Denominational Job Boards")
    n = scrape_denom_jobs(conn)
    results['job_boards'] = n
    log(f"  Total: {n} vacancies found")
    
    # Source 2: Website signals
    log("\n2. Church Website Vacancy Signals")
    n = scan_website_signals(conn)
    results['website_signals'] = n
    log(f"  Total: {n} churches with vacancy signals")
    
    # Source 4: Denom classification from vacancy text
    log("\n4. Denomination Self-Identification from Vacancies")
    n = enrich_denom_from_vacancies(conn)
    results['denom_classification'] = n
    log(f"  Total: {n} churches classified by self-identification")
    
    # Source 5: New church discovery + address enrichment
    log("\n5. New Church Discovery & Address Enrichment")
    new_ch, addr_enriched = discover_new_churches(conn)
    results['new_churches'] = new_ch
    results['addresses_enriched'] = addr_enriched
    log(f"  New churches discovered: {new_ch}")
    log(f"  Addresses enriched: {addr_enriched}")
    
    # Source 6: Infer church capabilities from job titles
    log("\n6. Church Capability Inference from Job Titles")
    n = infer_church_capabilities(conn)
    results['capabilities_inferred'] = n
    log(f"  Capabilities inferred: {n}")
    
    # Source 7: Budget estimation from salary data
    log("\n7. Budget Estimation from Salary Data")
    n = estimate_church_budgets(conn)
    results['budgets_estimated'] = n
    log(f"  Budgets estimated: {n}")
    
    # Source 8: Theology keyword extraction from full listing text
    log("\n8. Theology Keyword Extraction")
    n = extract_theology_keywords(conn)
    results['theology_tagged'] = n
    log(f"  Listings tagged: {n}")
    
    # Summary
    log(f"\n=== Summary ===")
    for source, count in results.items():
        log(f"  {source}: {count:,}")
    
    c = conn.cursor()
    c.execute("SELECT COUNT(1), COUNT(DISTINCT church_id) FROM church_vacancies WHERE church_id IS NOT NULL")
    total, unique = c.fetchone()
    log(f"\n  Total vacancies: {total:,} ({unique:,} unique churches)")
    
    # High-confidence matches worth outreach
    c.execute("""
        SELECT COUNT(1) FROM church_vacancies 
        WHERE confidence >= 0.8 AND church_id IS NOT NULL
    """)
    high_conf = c.fetchone()[0]
    log(f"  High confidence (>=0.8): {high_conf:,} — ready for outreach")
    
    conn.close()
    log("\nDone.")

if __name__ == '__main__':
    main()
