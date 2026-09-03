#!/usr/bin/env python3
"""
Complete 2021 Catholic Directory import — link clergy, import bishops, log provenance.
Run after _import_catholic_dir_2021.py has inserted entries + clergy.
"""
import sqlite3
import json
from pathlib import Path

DB_PATH = Path("E:/grid/data/catholic_directory.db")
DATA_DIR = Path("E:/grid/data/directories/2021")
DIR_YEAR = 2021


def complete_2021():
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")

    # ── Build entry_id mapping from source_entry_id ──
    print("Building entry ID mapping...")
    entry_map = {}
    for row in conn.execute(
        "SELECT source_entry_id, id FROM dir_entries WHERE directory_year=?",
        (DIR_YEAR,)
    ):
        entry_map[row[0]] = row[1]
    print(f"  {len(entry_map):,} entries mapped")

    # ── Link clergy in batches ──
    print("Linking clergy to entry IDs...")
    total_linked = 0
    total_orphan = 0
    batch = []
    
    for row in conn.execute(
        "SELECT id, entry_id FROM dir_clergy WHERE directory_year=?",
        (DIR_YEAR,)
    ):
        clergy_id = row[0]
        source_eid = str(row[1])  # temp entry_id holds source_entry_id
        real_eid = entry_map.get(source_eid)
        if real_eid:
            batch.append((real_eid, clergy_id))
        else:
            batch.append((-1, clergy_id))
            total_orphan += 1
        
        if len(batch) >= 500:
            conn.executemany(
                "UPDATE dir_clergy SET entry_id=? WHERE id=?",
                batch
            )
            total_linked += len(batch)
            batch.clear()
    
    if batch:
        conn.executemany(
            "UPDATE dir_clergy SET entry_id=? WHERE id=?",
            batch
        )
        total_linked += len(batch)
    
    print(f"  Linked {total_linked:,} clergy, {total_orphan} orphans")

    # Delete orphans
    if total_orphan > 0:
        conn.execute("DELETE FROM dir_clergy WHERE entry_id = -1")
        print(f"  Deleted {total_orphan} orphan clergy")

    # ── Import bishops ──
    bishops_file = DATA_DIR / "bishops_2021.json"
    if bishops_file.exists():
        print("Importing bishops...")
        with open(bishops_file, encoding="utf-8") as f:
            bishops = json.load(f)
        for b in bishops:
            conn.execute("""
                INSERT INTO dir_bishops (directory_year, name, title, diocese,
                    bishop_type, status, source_raw)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                DIR_YEAR,
                (b.get("name") or "").strip(),
                (b.get("title") or "").strip() or None,
                (b.get("diocese") or "").strip() or None,
                (b.get("type") or "").strip() or None,
                (b.get("status") or "").strip() or None,
                json.dumps(b, ensure_ascii=False),
            ))
        print(f"  Imported {len(bishops)} bishops")
    else:
        print("No bishops file found.")

    # ── Log provenance ──
    entry_count = conn.execute(
        "SELECT COUNT(*) FROM dir_entries WHERE directory_year=?", (DIR_YEAR,)
    ).fetchone()[0]
    clergy_count = conn.execute(
        "SELECT COUNT(*) FROM dir_clergy WHERE directory_year=?", (DIR_YEAR,)
    ).fetchone()[0]
    bishop_count = conn.execute(
        "SELECT COUNT(*) FROM dir_bishops WHERE directory_year=?", (DIR_YEAR,)
    ).fetchone()[0]

    conn.execute("""
        INSERT INTO dir_provenance (source, description, entry_count, clergy_count, bishop_count)
        VALUES (?, ?, ?, ?, ?)
    """, (
        "catholic_dir_2021",
        f"Full import of 2021 Catholic Directory — {entry_count:,} entries",
        entry_count,
        clergy_count,
        bishop_count,
    ))

    conn.execute("PRAGMA foreign_keys=ON")
    conn.commit()

    # ── Summary ──
    print(f"\n{'='*50}")
    print(f"✅ 2021 Import Complete")
    print(f"{'='*50}")
    print(f"  Entries:  {entry_count:>10,}")
    print(f"  Clergy:   {clergy_count:>10,}")
    print(f"  Bishops:  {bishop_count:>10,}")
    print(f"  Orphans:  {total_orphan:>10,}")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    complete_2021()
