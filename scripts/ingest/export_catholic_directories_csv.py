"""
Export all unparsed Catholic Directory years to CSV.
Reads formatted text files, extracts parish/clergy data, outputs CSV.
Uses the same parsing logic as parse_catholic_directories.py but exports to CSV.
"""
import sqlite3
import re
import os
import csv
from pathlib import Path
from collections import defaultdict

DIRECTORIES = Path("E:/grid/data/directories")
OUTPUT_DIR = Path("E:/grid/data/denom/catholic_directories_csv")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RE_DIOCESE = re.compile(r'^(?:ARCHDIOCESE|DIOCESE)\s+OF\s+(.+?)\.?\s*$', re.IGNORECASE)
RE_CHURCH_LINE = re.compile(r'^(.+?)\s*[—\-]\s*(.+)$')

STRUCTURAL_PATS = [
    r'^Digitized by', r'^Google$', r'^={3,}',
    r'^CHURCHES\s+AND\s+CLERGY$', r'^CITY\s+OF\s+', r'^CTTT\s+',
    r'^DECEASED\s+PRELATES', r'^DSOSABED\s+',
    r'^Established\s+\d{4}', r'^Comprises\s+', r'^PROVINCE\s+OF\s+',
    r'^\d+\s+DIOCESE\s+OF', r'^INSTITUTIONS\.?$', r'^RECAPITULATION\.?$',
    r'^CONTENTS$', r'^CATALOGUE|^CATALOG', r'^NOTE:', r'^REMARKS?[\.:]',
    r'^SUMMARY', r'^OBITUARY', r'^ALPHABETICAL\s+LIST',
    r'^The\s+(?:Diocese|Archdiocese|Province)\s+of',
    r'^COUNCIL\s+OF', r'^TABLE\s+OF\s+CONTENTS',
    r'^HIERARCHY\s+OF',
    r'^Most\s+Rev\.?\s+\w.*?(?:Bishop|Archbishop|consecrated)',
    r'^Rt\.?\s+Rev\.?\s+\w.*?(?:Bishop|consecrated)',
    r'^Very\s+Rev\.?\s+\w.*?(?:V\.\s*G\.|Vic\.\s*Gen\.)',
    r'^\([^)]+\)$',
    r'^attended\s+from', r'^served\s+from', r'^who\s+also\s+attends',
    r'^also\s+attends', r'^High\s+Mass', r'^Vespers', r'^Mass\s+and',
    r'^Residence', r'^Office[,\.]', r'^Terms[\.:]', r'^Number\s+of',
    r'^For\s+further', r'^Communications?', r'^The\s+course\s+of',
    r'^There\s+are', r'^This\s+(?:institution|asylum|college|seminary|convent|academy|diocess|diocese|report)',
    r'^Young\s+(?:ladies|men)', r'^Report\s+(?:furnished|reprinted|arranged)',
    r'^Catholic\s+population', r'^Churches[,\.]\s', r'^Clergymen',
    r'^Ecclesiastical\s+(?:institutions|seminary)', r'^Colleges?[\.,]',
    r'^Schools?[\.,]', r'^Orphan', r'^Female\s+(?:religious|academ)',
    r'^Charitable', r'^Sunday\s+School', r'^Rosary', r'^Free\s+School',
    r'^Male\s+(?:Orphan|School)', r'^German\s+(?:Male|Female|School)',
    r'^English\s+Male', r'^Boys[\'’]?\s+(?:Free\s+)?School',
    r'^Girls[\'’]?\s+(?:Free\s+)?School', r'^Ladies[\'’]?\s+Catholic',
    r'^Catholic\s+Male\s+Benevolent', r'^Preparatory\s+(?:Seminary|School)',
    r'^The\s+(?:college|academy|institution|public|branches|members\s+of)',
    r'^Twelve\s+other', r'^About\s+(?:one\s+)?hundred', r'^Some\s+(?:twelve|four)',
    r'^SISTERS\s+OF', r'^CONVENT\s+OF', r'^COLLEGE\s+OF',
    r'^ACADEMY\s+OF', r'^SEMINARY', r'^ORPHAN\s+ASYLUM',
    r'^DIOCESAN\s+SEMINARY', r'^ECCLESIASTICAL\s+INSTITUTIONS',
    r'^INDIAN\s+MISSIONS', r'^DISTRICT\s+OF',
    r'^MOON[\'’]S\s+PHASES', r'^BOSTON;', r'^BALTIMORE;',
    r'^SADLIER[\'’]S\s+CATHOLIC', r'^THE\s+(?:OFFICIAL|METROPOLITAN)\s+CATHOLIC',
    r'^\[?Published\s+by', r'^Entered[,\.]\s+according',
    r'^PREFACE\.?$', r'^In\s+presenting', r'^We\s+(?:return|trust|do\s+not|thank)',
    r'^Baltimore[,\.]\s+Nov', r'^J\.?\s+MURPHY', r'^Printed\s+and\s+Published',
    r'^Marble\s+Building', r'^London:', r'^Sold\s+by',
    r'^BISHOP\.?\s*$', r'^ARCHBISHOP\.?\s*$',
    r'^PREDECESSORS\.?$', r'^CHANGE$', r'^ADDITIONS\s+AND\s+CHANGES',
    r'^The\s+following\s+additions',
]
STRUCTURAL = [re.compile(p, re.IGNORECASE) for p in STRUCTURAL_PATS]

RE_CHURCH_SECTION = re.compile(r'^CHURCHES\s+AND\s+CLERGY', re.IGNORECASE)
RE_PRIEST_SPLIT = re.compile(r'((?:Most\s+|Rt\.?\s*|Very\s+)?Rev(?:erend)?\.?\s+)')
RE_NAME = re.compile(
    r'((?:Mc|Mac|O[\'’]|De\s+|Van\s+|Vander\s+)?[A-Z][a-z]+'
    r'(?:\s+[A-Z]\.)*'
    r'\s+(?:Mc|Mac|O[\'’]|De\s+|Van\s+|Vander\s+)?[A-Z][a-z]+'
    r'(?:\s+[A-Z][a-z]+)?)'
)

ORDERS = sorted([
    'C.SS.R.', 'C.SS.R', 'C.SS.C.', 'C.SS.C', 'O.S.B.', 'O.S.B', 'O.S.D.', 'O.S.D',
    'O.S.F.', 'O.S.F', 'O.S.M.', 'O.S.M', 'C.M.', 'C.M', 'C.S.P.', 'C.S.P',
    'O.M.I.', 'O.M.I', 'O.M.J.', 'O.M.J', 'O.P.', 'O.P', 'O.F.M.', 'O.F.M',
    'O.Carm.', 'O.Carm', 'O.C.D.', 'O.C.D', 'O.S.A.', 'O.S.A', 'O.Praem.',
    'S.J.', 'S.J', 'SJ.', 'SJ', 'P.S.M.', 'P.S.M', 'S.P.M.', 'S.P.M',
    'C.C.J.M.', 'C.C.J.M', 'P.D.N.', 'P.D.N',
], key=len, reverse=True)

ROLES = [
    'Pastor', 'P.P.', 'P. P.', 'Rector', 'Assistant', 'Curate',
    'Chaplain', 'Superior', 'Prefect', 'President',
    'V.G.', 'V. G.', 'Vic. Gen.', 'Vicar General', 'Vicar-General',
    'Chancellor', 'Chancellpr', 'Secretary', 'Sec.', 'Sec\'ry',
    'Administrator', 'Admin.', 'Coadjutor',
    'Archbishop', 'Bishop',
    'Prior', 'Subprior', 'Provincial',
    'Professors', 'Novice', 'Novices',
    'D.D.', 'D. D.',
    'P.P', 'P P',
]


def is_structural(line):
    line = line.strip()
    if not line or re.match(r'^\d+$', line):
        return True
    for pat in STRUCTURAL:
        if pat.match(line):
            return True
    return False


def is_clergy_continuation(line):
    line = line.strip()
    if not line:
        return False
    if re.match(r'Rev\.\s+', line, re.IGNORECASE):
        return True
    if re.match(r'(who\s+also|dwelling\s+at|dw\.?\s+at|attends?\s+(?:the\s+)?Calvary)', line, re.IGNORECASE):
        return True
    return False


def parse_clergy_text(text):
    priests = []
    parts = RE_PRIEST_SPLIT.split(text)
    i = 1
    while i < len(parts) - 1:
        title_part = parts[i].strip()
        name_part = parts[i + 1].strip()

        title = 'Rev.'
        if re.search(r'Most\s+Rev', title_part, re.IGNORECASE):
            title = 'Most Rev.'
        elif re.search(r'Rt\.?\s*Rev', title_part, re.IGNORECASE):
            title = 'Rt. Rev.'
        elif re.search(r'Very\s+Rev', title_part, re.IGNORECASE):
            title = 'Very Rev.'

        name_match = RE_NAME.search(name_part)
        if name_match:
            name = name_match.group(1)
            remainder = name_part[name_match.end():].strip()
            
            order = None
            for o in ORDERS:
                o_pat = re.escape(o).replace(r'\.', r'\.\s*')
                if re.search(o_pat, remainder, re.IGNORECASE):
                    order = o.rstrip('.')
                    remainder = re.sub(o_pat, '', remainder, flags=re.IGNORECASE).strip()
                    break
            
            role = None
            for r in ROLES:
                if r.lower() in remainder.lower():
                    role = r
                    break
            if not role and remainder:
                role = remainder.strip()
            elif not role:
                role = None
            
            priests.append({'title': title, 'name': name, 'order': order, 'role': role.strip() if role else None})
        i += 2
    return priests


def extract_church_parts(text):
    text = re.sub(r'\^', '', text.strip())
    text = re.sub(r'\s{2,}', ' ', text)

    church_name = None
    city = None

    church_pats = [
        r'(St\.?\s+\w+(?:[\'’]s)?(?:\s+\w+)*)',
        r'(Cathedral(?:\s+of\s+\w+(?:\s+\w+)*)?)',
        r'(Immaculate\s+Conception(?:\s+\w+)*)',
        r'(Holy\s+\w+(?:\s+\w+)*)',
        r'(Our\s+Lady\s+\w+(?:\s+\w+)*)',
        r'(Sacred\s+Heart(?:\s+\w+)*)',
        r'(Church\s+of\s+\w+(?:\s+\w+)*)',
        r'(Chapel\s+of\s+\w+(?:\s+\w+)*)',
        r'(SS\.\s+\w+(?:\s+\w+)*)',
        r'(Sts?\.\s+\w+(?:\s+\w+)*)',
        r'(Mount\s+(?:St\.?\s+)?\w+(?:[\'’]s)?(?:\s+\w+)*)',
        r'(Nativity\s+of\s+\w+(?:\s+\w+)*)',
        r'(Annunciation(?:\s+\w+)*)',
        r'(Transfiguration(?:\s+\w+)*)',
        r'(Assumption(?:\s+\w+)*)',
        r'(Nuestra\s+Se[ñn]ora\s+\w+(?:\s+\w+)*)',
        r'(San\s+\w+(?:\s+\w+)*)',
        r'(Santa\s+\w+(?:\s+\w+)*)',
    ]

    for pat in church_pats:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            church_name = m.group(1)
            break

    if not church_name:
        clean = re.sub(r'corner\s+of\s+.+', '', text, flags=re.IGNORECASE)
        clean = re.sub(r'(?:Front|East|West|North|South)\s+near\s+.+', '', clean, flags=re.IGNORECASE)
        clean = re.sub(r'between\s+.+', '', clean, flags=re.IGNORECASE)
        church_name = clean.strip().rstrip(',').strip()

    parts = text.split(',')
    if parts:
        first = parts[0].strip()
        is_church = any(re.match(pat, first, re.IGNORECASE) for pat in church_pats)
        if not is_church:
            if not re.match(r'^(?:corner|between|near|Front|East|West|North|South|attended|served|who|also|High|Vespers|Residence|Office|Terms|Number|For|The|We|Young|Male|German|English|Boys|Girls|Ladies|Catholic|Report|There|This|Twelve|About|Some)', first, re.IGNORECASE):
                city = re.sub(r'\s+(?:Co\.?|County)$', '', first, flags=re.IGNORECASE).strip()

    return city, church_name


GARBAGE_PARISH = re.compile(
    r'^$'
    r'|^(Most|Rt\.?|Very|V\.|Mt\.?)$'
    r'|^(?:Rev|Reverend|Very Rev|Most Rev|Rt Rev)\b'
    r'|,\s*(?:S\.\s*J\.|C\.\s*S\.\s*S\.\s*R\.|O\.\s*S\.\s*[BFD]\.|C\.\s*M\.|D\.\s*D\.|V\.\s*G\.)'
    r'|\d+\s*(?:a\.\s*m\.|p\.\s*m\.|o\'clock)'
    r'|\bstreet[s\.]?\s*$'
    r'|^[A-Z]\.$'
    r'|^[•\-\*]'
    r'|^\d+$'
    r'|^.{1,3}$'
    r'|^.{0,40},\s*(?:S\.\s*J\.|C\.\s*S\.\s*S\.|O\.\s*S\.|C\.\s*M\.|D\.\s*D\.|Sup|V\.\s*G\.|Pastor|Rector|Chaplain)', re.IGNORECASE
)


def filter_garbage(records):
    return [r for r in records if r['parish'] and not GARBAGE_PARISH.search(r['parish'])]


def parse_file(filepath, year):
    records = []
    current_diocese = None
    in_church_section = False

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        raw = f.read()

    raw = re.sub(r'([a-z])-\s*\n\s*([a-z])', r'\1\2', raw)
    lines = [l.rstrip() for l in raw.splitlines()]

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        line_num = i + 1

        dio_match = RE_DIOCESE.match(line)
        if dio_match:
            current_diocese = dio_match.group(1).strip().rstrip('.')
            in_church_section = False
            i += 1
            continue

        if RE_CHURCH_SECTION.match(line):
            in_church_section = True
            i += 1
            continue

        if is_structural(line):
            i += 1
            continue

        if not in_church_section:
            i += 1
            continue

        church_match = RE_CHURCH_LINE.match(line)
        if church_match:
            church_part = church_match.group(1).strip()
            clergy_part = church_match.group(2).strip()

            j = i + 1
            while j < len(lines):
                cont = lines[j].strip()
                if is_clergy_continuation(cont):
                    clergy_part += '; ' + cont
                    j += 1
                elif cont and not is_structural(cont) and not RE_CHURCH_LINE.match(cont) and not RE_DIOCESE.match(cont):
                    if re.search(r'Rev\.\s+', cont) or 'attends' in cont.lower() or 'dwelling' in cont.lower():
                        clergy_part += ' ' + cont
                        j += 1
                    else:
                        break
                else:
                    break

            city, church_name = extract_church_parts(church_part)
            priests = parse_clergy_text(clergy_part)

            for p in priests:
                records.append({
                    'year': year, 'diocese': current_diocese, 'city': city,
                    'parish': church_name, 'priest_name': p['name'],
                    'title': p['title'], 'order': p['order'], 'role': p['role'],
                    'source_file': os.path.basename(filepath),
                    'source_line': line_num,
                })
            i = j
            continue

        if re.search(r'Rev\.\s+', line) and len(line) > 30:
            m = re.search(r'(?:,\s*)?(Rev\.\s+)', line)
            if m:
                church_part = line[:m.start()].strip().rstrip(',').strip()
                clergy_part = line[m.start():].strip()

                j = i + 1
                while j < len(lines):
                    cont = lines[j].strip()
                    if is_clergy_continuation(cont):
                        clergy_part += '; ' + cont
                        j += 1
                    else:
                        break

                city, church_name = extract_church_parts(church_part)
                priests = parse_clergy_text(clergy_part)
                for p in priests:
                    records.append({
                        'year': year, 'diocese': current_diocese, 'city': city,
                        'parish': church_name, 'priest_name': p['name'],
                        'title': p['title'], 'order': p['order'], 'role': p['role'],
                        'source_file': os.path.basename(filepath),
                        'source_line': line_num,
                    })
                i = j
                continue

        i += 1

    return filter_garbage(records)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--year', type=int, help='Parse specific year')
    ap.add_argument('--years', type=int, nargs='+', help='Parse specific years')
    ap.add_argument('--all', action='store_true', help='Parse all unparsed years')
    ap.add_argument('--list', action='store_true', help='List years needing parsing')
    args = ap.parse_args()

    db = sqlite3.connect('E:/grid/churches.db')
    years_parsed = set(r[0] for r in db.execute("SELECT year FROM catholic_clergy GROUP BY year").fetchall())
    db.close()

    all_files = sorted(DIRECTORIES.glob('catholic_dir_*_formatted.txt'))
    available_years = set()
    for fp in all_files:
        m = re.search(r'catholic_dir_(\d{4})_formatted\.txt', fp.name)
        if m:
            available_years.add(int(m.group(1)))

    missing_years = sorted(available_years - years_parsed)

    if args.list:
        print(f"Years already parsed in catholic_clergy: {sorted(years_parsed)}")
        print(f"Years available in files: {sorted(available_years)}")
        print(f"\nMissing years ({len(missing_years)}): {missing_years}")
        return

    years_to_process = []
    if args.year:
        years_to_process = [args.year]
    elif args.years:
        years_to_process = args.years
    elif args.all:
        years_to_process = missing_years
    else:
        years_to_process = missing_years[:5]
        print(f"Processing first 5 years: {years_to_process}")

    total = 0
    for year in years_to_process:
        fp = DIRECTORIES / f"catholic_dir_{year}_formatted.txt"
        if not fp.exists():
            print(f"Not found: {fp}")
            continue
        print(f"\n{year} - parsing...")
        recs = parse_file(fp, year)
        print(f"  {len(recs)} assignments")

        csv_path = OUTPUT_DIR / f"catholic_directory_{year}.csv"
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['year', 'diocese', 'city', 'parish', 'priest_name', 'title', 'order', 'role', 'source_file', 'source_line'])
            w.writeheader()
            w.writerows(recs)
        print(f"  Saved to {csv_path}")
        total += len(recs)

    print(f"\nTotal: {total} records exported")


if __name__ == '__main__':
    main()