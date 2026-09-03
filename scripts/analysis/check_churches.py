#!/usr/bin/env python3
"""Count churches with websites and phones."""
import csv

for fname, web_col in [("church_contacts.csv", 7), ("church_anglican_episcopal.csv", 5)]:
    with open(f"/home/ubuntu/grantwizard/{fname}") as f:
        rows = list(csv.reader(f))
    total = len(rows) - 1
    has_web = sum(1 for r in rows[1:] if len(r) > web_col and r[web_col].strip().startswith("http"))
    has_phone = sum(1 for r in rows[1:] if len(r) > web_col-1 and r[web_col-1].strip().startswith("("))
    print(f"{fname}: {total} rows, {has_web} with websites, {has_phone} with phones")
