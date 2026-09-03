#!/usr/bin/env python3
"""
Import Canadian Federal Election results by riding (FED).

Downloads:
  1. Transposition_343_FED_Summary.csv — winner, turnout, electors per riding
  2. Transposition_343_FED_Vote_Count.csv — vote counts by party (wide format)

Source: Elections Canada via open.canada.ca
  https://open.canada.ca/data/en/dataset/ (Transposition of the Vote from the
  44th General Election to the 2023 Representation Orders)

Creates: election_canada_fed_results table
Join key: fed_num (matches church_fed.fed_num)

Usage:
    python scripts/enrichment/import_canada_election.py
"""
import csv
import io
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

DB = r'E:\grid\churches.db'
DATA_DIR = Path(r'E:\grid\data\election')
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Elections Canada transposition CSVs (2021 results → 2023 FED boundaries)
# From open.canada.ca dataset 08c4ffbc-c513-41a4-b741-d35b41b50c22
URLS = {
    'fed_long':         'https://open.canada.ca/data/dataset/08c4ffbc-c513-41a4-b741-d35b41b50c22/resource/0f8be6d9-d975-4022-b11f-8cd31e41c8f9/download/transposition_343_fed.csv',
    'fed_summary':      'https://open.canada.ca/data/dataset/08c4ffbc-c513-41a4-b741-d35b41b50c22/resource/7657696a-1dc4-44ed-a992-61c49ed76740/download/transposition_343_fed_summary.csv',
    'fed_vote_count':   'https://open.canada.ca/data/dataset/08c4ffbc-c513-41a4-b741-d35b41b50c22/resource/463aa010-d9c1-470e-b6e3-d18a1c7a6a4a/download/transposition_343_fed_vote_count.csv',
    'fed_percentage':   'https://open.canada.ca/data/dataset/08c4ffbc-c513-41a4-b741-d35b41b50c22/resource/61132423-7762-4d39-8adb-38cc007f7e35/download/transposition_343_fed_percentage.csv',
}


def download_csv(url, label):
    """Download CSV from URL, save locally, return as list of dicts."""
    fname = url.split('/')[-1]
    dest = DATA_DIR / fname

    if dest.exists():
        print(f'  Already downloaded: {fname}')
        with open(dest, 'r', encoding='utf-8-sig') as f:
            return list(csv.DictReader(f))

    print(f'  Downloading {label}...', end=' ', flush=True)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0'})
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode('utf-8-sig')
        # Save locally
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(raw)
        rows = list(csv.DictReader(io.StringIO(raw)))
        print(f'{len(rows):,} rows')
        return rows
    except Exception as e:
        print(f'FAILED: {e}')
        return None


def main():
    db = sqlite3.connect(DB, timeout=60)
    db.execute('PRAGMA journal_mode=WAL')

    # ═══ Download ═══════════════════════════════════════════════════════
    print('Downloading Elections Canada data...')
    long_rows    = download_csv(URLS['fed_long'], 'FED Long Form')
    summary_rows = download_csv(URLS['fed_summary'], 'FED Summary')
    vote_rows    = download_csv(URLS['fed_vote_count'], 'FED Vote Count')
    pct_rows     = download_csv(URLS['fed_percentage'], 'FED Percentage')

    # Use long form as primary (one row per party per FED = 8,600+ rows)
    primary_rows = long_rows or vote_rows
    if not primary_rows:
        print('FATAL: Could not download election data')
        db.close()
        return

    # ═══ Parse summary ══════════════════════════════════════════════════
    print(f'\nParsing summaries ({len(summary_rows)} rows)...')
    summary_cols = list(summary_rows[0].keys())
    print(f'  Summary columns: {summary_cols}')

    # Summary columns: PROV_ID, PROV_NAME, FED_NUM, FED_FR, FED_EN,
    #   Transposed_Population, Registered_Electors, Transposed_Votes,
    #   Rejected_Ballots, Estimated_Turnout, Estimated_First_Place_EN, Estimated_First_Place_FR

    summaries = {}
    for r in summary_rows:
        fn = r.get('FED_NUM', '').strip()
        if not fn:
            continue
        turnout_str = r.get('Estimated_Turnout', '').strip().replace('%', '')
        s = {
            'fed_num': fn,
            'fed_name_en': r.get('FED_EN', '').strip(),
            'fed_name_fr': r.get('FED_FR', '').strip(),
            'winner': r.get('Estimated_First_Place_EN', '').strip(),
            'winner_fr': r.get('Estimated_First_Place_FR', '').strip(),
        }
        try:
            s['turnout_pct'] = float(turnout_str) if turnout_str else None
        except ValueError:
            s['turnout_pct'] = None
        try:
            s['electors'] = int(float(r.get('Registered_Electors', 0)))
        except (ValueError, TypeError):
            s['electors'] = None
        summaries[fn] = s
    print(f'  Parsed {len(summaries)} ridings')

    # ═══ Parse vote counts ═════════════════════════════════════════════
    if vote_rows:
        print(f'\nParsing vote counts ({len(vote_rows)} rows)...')
        vote_cols = list(vote_rows[0].keys())
        # First 5 columns are identifiers, then party columns, then stats
        id_cols = ['PROV_ID', 'PROV_NAME', 'FED_NUM', 'FED_FR', 'FED_EN']
        stats_cols = ['Rejected_Ballots', 'Transposed_Votes', 'Registered_Electors', 'Estimated_Turnout']
        party_cols = [c for c in vote_cols if c not in id_cols and c not in stats_cols]

        # Map bilingual party names → simple keys
        def party_key(name):
            n = name.lower()
            if 'liberal' in n and 'marxist' not in n:
                return 'liberal_votes'
            if 'conservative' in n:
                return 'conservative_votes'
            if 'new democratic' in n or 'nouveau parti' in n:
                return 'ndp_votes'
            if 'bloc qu' in n:
                return 'bloc_votes'
            if 'green' in n:
                return 'green_votes'
            if "people's" in n or 'populaire' in n:
                return 'ppc_votes'
            return 'other_votes'

        for r in vote_rows:
            fn = r.get('FED_NUM', '').strip()
            if not fn or fn not in summaries:
                continue
            total = 0
            for pc in party_cols:
                try:
                    v = int(float(r.get(pc, 0)))
                    if v > 0:
                        pk = party_key(pc)
                        summaries[fn][pk] = summaries[fn].get(pk, 0) + v
                        total += v
                except (ValueError, TypeError):
                    continue
            summaries[fn]['total_valid_votes'] = total

        # Calculate vote shares
        for fn, s in summaries.items():
            total = s.get('total_valid_votes', 0) or 0
            if total > 0:
                for party in ['liberal_votes','conservative_votes','ndp_votes','bloc_votes','green_votes','ppc_votes','other_votes']:
                    v = s.get(party, 0) or 0
                    s[f'{party}_pct'] = round(v / total * 100, 1)
        print(f'  Parsed vote shares for {sum(len([k for k in s if k.endswith("_votes") and not k.endswith("_pct")]) for s in summaries.values())} parties across {len(summaries)} ridings')

    # ═══ Create table ════════════════════════════════════════════════════
    print('\nCreating election_canada_fed_results table...')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS election_canada_fed_results (
            fed_num             TEXT PRIMARY KEY,
            fed_name            TEXT,
            winner              TEXT,
            turnout_pct         REAL,
            electors            INTEGER,
            total_valid_votes   INTEGER,
            liberal_votes       INTEGER DEFAULT 0,
            liberal_votes_pct   REAL,
            conservative_votes  INTEGER DEFAULT 0,
            conservative_votes_pct REAL,
            ndp_votes           INTEGER DEFAULT 0,
            ndp_votes_pct       REAL,
            bloc_votes          INTEGER DEFAULT 0,
            bloc_votes_pct      REAL,
            green_votes         INTEGER DEFAULT 0,
            green_votes_pct     REAL,
            ppc_votes           INTEGER DEFAULT 0,
            ppc_votes_pct       REAL,
            other_votes         INTEGER DEFAULT 0,
            other_votes_pct     REAL,
            source              TEXT DEFAULT 'elections_canada_transposition_2023',
            import_date         TEXT DEFAULT (date('now'))
        );
    ''')

    # Add FED names from church_fed table if available
    fed_names = dict(db.execute(
        "SELECT fed_num, fed_name_en FROM church_fed GROUP BY fed_num"
    ).fetchall())

    # ═══ Insert ═════════════════════════════════════════════════════════
    print('  Inserting results...')
    # Default all numeric columns
    for fn, s in summaries.items():
        s.setdefault('fed_name', '')
        for k in ['turnout_pct','electors','total_valid_votes',
                  'liberal_votes','liberal_votes_pct','conservative_votes','conservative_votes_pct',
                  'ndp_votes','ndp_votes_pct','bloc_votes','bloc_votes_pct',
                  'green_votes','green_votes_pct','ppc_votes','ppc_votes_pct',
                  'other_votes','other_votes_pct']:
            s.setdefault(k, None)

    db.executemany('''
        INSERT OR REPLACE INTO election_canada_fed_results
            (fed_num, fed_name, winner, turnout_pct, electors, total_valid_votes,
             liberal_votes, liberal_votes_pct,
             conservative_votes, conservative_votes_pct,
             ndp_votes, ndp_votes_pct,
             bloc_votes, bloc_votes_pct,
             green_votes, green_votes_pct,
             ppc_votes, ppc_votes_pct,
             other_votes, other_votes_pct)
        VALUES (:fed_num, :fed_name, :winner, :turnout_pct, :electors, :total_valid_votes,
                :liberal_votes, :liberal_votes_pct,
                :conservative_votes, :conservative_votes_pct,
                :ndp_votes, :ndp_votes_pct,
                :bloc_votes, :bloc_votes_pct,
                :green_votes, :green_votes_pct,
                :ppc_votes, :ppc_votes_pct,
                :other_votes, :other_votes_pct)
    ''', list(summaries.values()))
    db.commit()
    inserted = db.execute('SELECT COUNT(*) FROM election_canada_fed_results').fetchone()[0]
    print(f'  Inserted {inserted} ridings')

    # ═══ Verify ══════════════════════════════════════════════════════════
    print('\n  Sample results:')
    for r in db.execute('''
        SELECT fed_num, winner, turnout_pct, total_valid_votes,
               liberal_votes_pct, conservative_votes_pct, ndp_votes_pct
        FROM election_canada_fed_results
        ORDER BY total_valid_votes DESC
        LIMIT 8
    ''').fetchall():
        w = (r[1] or '')[:35]
        t = f'{r[2]:.1f}' if r[2] else 'N/A'
        print(f'    {r[0]} | Winner: {w:35s} | Turnout: {t}% | '
              f'L:{r[4] or 0:.0f}% C:{r[5] or 0:.0f}% N:{r[6] or 0:.0f}% ({r[3] or 0:,} votes)')

    # ═══ Join coverage check ══════════════════════════════════════════
    church_count = db.execute('''
        SELECT COUNT(*) FROM church_fed cf
        JOIN election_canada_fed_results e ON cf.fed_num = e.fed_num
    ''').fetchone()[0]
    total_with_fed = db.execute('SELECT COUNT(*) FROM church_fed').fetchone()[0]
    print(f'\n  Churches with election data: {church_count:,} / {total_with_fed:,} '
          f'({100*church_count/total_with_fed:.1f}%)')

    # ═══ Provenance ═══════════════════════════════════════════════════
    now = datetime.now().isoformat()
    db.execute('''
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at,
             churches_updated, churches_inserted, fields_populated,
             records_attempted, records_matched, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'elections_canada_fed_results',
        'import_canada_election.py',
        now, now, 0, inserted,
        'winner,turnout,liberal_votes,conservative_votes,ndp_votes,bloc_votes,green_votes,ppc_votes',
        len(summaries), inserted,
        'completed',
        f'2021 election results transposed to 2023 FEDs: {inserted} ridings'
    ))
    db.commit()
    db.close()

    print(f'\n{"="*60}')
    print(f'DONE — Election results for {inserted} ridings')
    print(f'Join: church_fed.fed_num = election_canada_fed_results.fed_num')
    print(f'{"="*60}')

if __name__ == '__main__':
    main()
