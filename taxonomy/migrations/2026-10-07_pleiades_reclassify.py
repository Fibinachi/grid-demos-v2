"""
Pleiades reclassification 2026-10-07.

1,647 ancient Pleiades archaeological sites were misclassified on the
Scientology node (614), probably as a classifier fallback. Reclassify
by Pleiades' own place_types + title keywords:

  church/church-2 -> 15  Christian (unspecified)   (ancient churches)
  synagogue       -> 5   Judaism
  mosque          -> 4   Islam
  stupa           -> 1   Buddhist
  prasada/Hindu titles -> 3 Hindu
  Greek keywords  -> 619 Hellenism
  Egyptian keywords -> 620 Ancient Egyptian Religion
  Mesopotamian keywords -> 630 Mesopotamian Religion
  default         -> 618 Roman Religion

Manual: Santa Costanza -> 15, Cave of the Apocalypse -> 15,
Donon Temple -> 618. Selcikler (unknown) stays on 614, flagged.

Approved by Charles 2026-10-07 ("Go").
Rollback: UPDATE churches SET taxonomy_id=614 WHERE id IN (<moved ids>)
  (every moved row came from 614).
"""

import io
import re
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

GDB = r"E:\grid\churches.db"
PDB = r"E:\grid\data\pleiades\pleiades.db"

MANUAL = {
    5258824: 15,   # Santa Costanza, Rome (4th-c Christian mausoleum)
    5259105: 15,   # Cave of the Apocalypse, Patmos
    6726139: 618,  # Donon Temple, Vosges (Gallo-Roman sanctuary)
    # 5259045 Selcikler: unknown, stays on 614, flagged below
}

GREEK = ["athena", "apollo", "poseidon", "amorgos", "delos", "delphi",
         "akragas", "agrigentum", "tainaron", "hellen", "greek"]
EGYPT = ["isis", "osiris", "karnak", "luxor", "pyramid", "egypt", "pharaoh"]
MESO = ["ziggurat", "uruk", "babylon", "mesopotam"]


def target(pdb, pid):
    ts = set(r[0] for r in pdb.execute(
        "SELECT place_type FROM places_place_types WHERE place_id=?", (pid,)))
    t = (pdb.execute("SELECT title FROM places WHERE id=?", (pid,)).fetchone()
         or ("",))[0]
    tl = t.lower()
    if ts & {"church-2", "church"}:
        return 15
    if "synagogue" in ts:
        return 5
    if "mosque" in ts:
        return 4
    if "stupa" in ts:
        return 1
    if "prasada" in ts or "mahabalipuram" in tl:
        return 3
    if any(k in tl for k in GREEK):
        return 619
    if any(k in tl for k in EGYPT):
        return 620
    if any(k in tl for k in MESO):
        return 630
    return 618


def main():
    gdb = sqlite3.connect(GDB, timeout=120)
    pdb = sqlite3.connect("file:%s?mode=ro" % PDB, uri=True)
    rows = gdb.execute(
        "SELECT id, source, latitude, longitude FROM churches "
        "WHERE taxonomy_id=614").fetchall()
    print("rows on 614:", len(rows))

    urlmap = {}
    for rid, src, lat, lon in rows:
        m = re.search(r"/places/(\d+)", src or "")
        if m:
            urlmap[rid] = int(m.group(1))
    pcoords = {}
    for pid, lat, lon in pdb.execute(
            "SELECT id, representative_latitude, representative_longitude "
            "FROM places WHERE representative_latitude IS NOT NULL"):
        try:
            pcoords[(round(float(lat), 3), round(float(lon), 3))] = pid
        except (TypeError, ValueError):
            pass
    pmap = dict(urlmap)
    for rid, src, lat, lon in rows:
        if rid in pmap or lat is None:
            continue
        pid = pcoords.get((round(float(lat), 3), round(float(lon), 3)))
        if pid:
            pmap[rid] = pid

    moves = {}  # rid -> target taxonomy_id
    for rid, pid in pmap.items():
        moves[rid] = target(pdb, pid)
    for rid, tid in MANUAL.items():
        if any(r[0] == rid for r in rows):
            moves[rid] = tid
    # drop no-ops (already on target)
    moves = {rid: tid for rid, tid in moves.items() if tid != 614}
    left = [r[0] for r in rows if r[0] not in moves]
    print("to move:", len(moves), "| staying on 614:", len(left), left)

    groups = {}
    for rid, tid in moves.items():
        groups.setdefault(tid, []).append(rid)

    gdb.execute("BEGIN IMMEDIATE")
    try:
        for tid, rids in groups.items():
            gdb.execute(
                "UPDATE churches SET taxonomy_id=? WHERE id IN (%s)"
                % ",".join("?" * len(rids)), (tid, *rids))
            print("  -> %d: %s rows" % (tid, "{:,}".format(len(rids))))
        gdb.execute("COMMIT")
    except Exception:
        gdb.execute("ROLLBACK")
        raise
    print("verify 614 count:",
          gdb.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id=614")
          .fetchone()[0])
    print("--- ROLLBACK ---")
    print("UPDATE churches SET taxonomy_id=614 WHERE id IN (%s);"
          % ",".join(str(r) for r in moves))
    gdb.close()


if __name__ == "__main__":
    main()
