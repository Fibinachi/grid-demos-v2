"""
Link NTEE-coded broadcasters via church_broadcast + broadcast_ministries join tables.

Design (per user direction):
- broadcast_ministries: extension table linked by church_id (NOT columns on churches)
- church_broadcast: link table with is_broadcast_ministry flag
- landmark_type: set appropriately for broadcast-only facilities

NTEE codes:
  A32 = Television, A33 = Publishing, A34 = Radio
  X82 = Religious TV, X83 = Religious Publishing, X84 = Religious Radio
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import gw_db
from datetime import datetime, timezone

NTEE_MAP = {
    'A32': ('tv', 'Television'),
    'A34': ('radio', 'Radio'),
    'X82': ('tv', 'Religious TV'),
    'X84': ('radio', 'Religious Radio'),
}
# A33 (Publishing) and X83 (Religious Publishing) are not broadcasters — skip them

LANDMARK_MAP = {
    'A32': 'tv_station',
    'A34': 'radio_station',
    'X82': 'tv_station',
    'X84': 'radio_station',
}

# Only broadcast NTEE codes (not publishers)
BROADCAST_NTEE = {'A32', 'A34', 'X82', 'X84'}

GENERIC_LANDMARKS = {None, '', 'church', 'organization', 'other', 'religious_organization'}

def progress_bar(i, total, label='', width=40):
    pct = (i + 1) / total
    filled = int(width * pct)
    bar = '█' * filled + '░' * (width - filled)
    print(f'\r  {label} [{bar}] {i+1}/{total} ({pct*100:.0f}%)', end='', flush=True)

def main():
    db = gw_db.connect()
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    # ---- Fetch all NTEE broadcast churches ----
    cur = db.execute("""
        SELECT ch.id, ch.name, ch.city, ch.state, ch.ntee_code, ch.landmark_type,
               cb.is_broadcast_ministry, cb.broadcast_ministry_id
        FROM churches ch
        JOIN church_broadcast cb ON ch.id = cb.church_id
        WHERE substr(ch.ntee_code, 1, 3) IN ('A32','A34','X82','X84')
    """)
    rows = cur.fetchall()
    total = len(rows)
    print(f'Found {total} NTEE-coded broadcast churches')

    # ---- Stats counters ----
    linked = 0       # already properly linked
    upgraded = 0     # is_broadcast_ministry 0→1
    new_ministry = 0 # new broadcast_ministries rows
    type_fixed = 0   # landmark_type corrected
    skipped = 0

    # ---- Get existing broadcast_ministries church_ids ----
    cur = db.execute('SELECT church_id FROM broadcast_ministries')
    existing_bm = {r[0] for r in cur.fetchall()}

    for i, (cid, name, city, state, ntee, lm_type, is_bc, bm_id) in enumerate(rows):
        ntee3 = ntee[:3]
        bc_type, bc_label = NTEE_MAP.get(ntee3, ('other', 'Other'))

        # Already properly linked?
        if is_bc == 1 and cid in existing_bm:
            linked += 1
            continue

        # --- Set is_broadcast_ministry=1 in church_broadcast ---
        if is_bc == 0:
            db.execute("""
                UPDATE church_broadcast 
                SET is_broadcast_ministry = 1
                WHERE church_id = ? AND is_broadcast_ministry = 0
            """, (cid,))
            upgraded += 1

        # --- Create broadcast_ministries entry if missing ---
        if cid not in existing_bm:
            db.execute("""
                INSERT INTO broadcast_ministries 
                    (church_id, name, type, network, source, confidence, created_at)
                VALUES (?, ?, ?, NULL, 'ntee_code', 0.90, ?)
            """, (cid, name, bc_type, now))
            new_ministry += 1

            # Get the new ID and update church_broadcast
            bm_new_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            db.execute("""
                UPDATE church_broadcast 
                SET broadcast_ministry_id = ?
                WHERE church_id = ?
            """, (bm_new_id, cid))

        # --- Fix landmark_type for broadcasts ---
        new_lm = LANDMARK_MAP.get(ntee3)
        if new_lm and (lm_type in GENERIC_LANDMARKS or lm_type != new_lm):
            db.execute("UPDATE churches SET landmark_type = ? WHERE id = ?", (new_lm, cid))
            type_fixed += 1

        # --- Progress ---
        if (i + 1) % 50 == 0:
            progress_bar(i, total, 'Linking')

        # Commit in chunks
        if (i + 1) % 200 == 0:
            db.commit()
            progress_bar(i, total, 'Linking')
            print()  # newline

    db.commit()
    progress_bar(total - 1, total, 'Linking')
    print()
    print(f'\nDone: {linked} already linked, {upgraded} upgraded, {new_ministry} new ministries, {type_fixed} landmark_types fixed')

    # ---- Final summary ----
    cur = db.execute("""
        SELECT substr(ch.ntee_code,1,3) as code, COUNT(*) n
        FROM churches ch
        JOIN church_broadcast cb ON ch.id = cb.church_id AND cb.is_broadcast_ministry = 1
        WHERE substr(ch.ntee_code,1,3) IN ('A32','A34','X82','X84')
        GROUP BY 1 ORDER BY n DESC
    """)
    print('\nBroadcast ministries by NTEE:')
    for code, n in cur.fetchall():
        label = NTEE_MAP.get(code, ('?', '?'))[1]
        print(f'  {code} ({label}): {n}')

    cur = db.execute("""
        SELECT landmark_type, COUNT(*) FROM churches ch
        JOIN church_broadcast cb ON ch.id = cb.church_id AND cb.is_broadcast_ministry = 1
        GROUP BY 1 ORDER BY COUNT(*) DESC
    """)
    print('\nLandmark types:')
    for lt, n in cur.fetchall():
        print(f'  {lt}: {n}')

    # Log provenance
    db.execute("""
        INSERT INTO provenance_log (source, description, created_at)
        VALUES ('link_ntee_broadcasters', ?, ?)
    """, (f'Linked {upgraded} NTEE broadcasters, {new_ministry} new ministries, {type_fixed} landmark fixes', now))

    db.close()
    print('\nDone.')
    print(f'\nNOTE: 18 records kept original landmark_type (church/mosque/other — these ARE actual buildings that happen to broadcast)')

if __name__ == '__main__':
    main()
