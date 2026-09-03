"""_test_po_box_stripping.py — verify PO box stripping."""
import re

def strip_po_box(query):
    """Remove PO box patterns from address query.
    PO boxes like 'BOX 1336, Odgen, IL, 62863' don't geocode well.
    Returns (stripped_query, was_po_box)."""
    if not query:
        return query, False
    up = query.upper()
    # Detect PO box patterns (longer matches first to avoid partial matches)
    if re.search(r'\b(PO BOX|P\.?O\.?\s*BOX|POB|BOX)\b', up):
        # Remove PO box part, keep city/state/zip
        parts = [p.strip() for p in query.split(',')]
        # Keep parts after the PO box (usually city, state, zip)
        # Find the last 2-3 parts which are typically city, state, zip
        if len(parts) >= 3:
            # Take the last 2-3 parts (city, state, zip)
            kept = ', '.join(parts[-3:])
            return kept, True
    return query, False

tests = [
    "BOX 1336, Odgen, IL, 62863",
    "PO BOX 1234, Springfield, MO 65801",
    "P.O. BOX 567, Houston, TX 77001",
    "109 North Mill Street, Colfax, WA 99111",  # not a PO box
    "123 Main St, City, ST 12345",  # not a PO box
]
for t in tests:
    stripped, was = strip_po_box(t)
    print(f"{was:5} | {t:50} -> {stripped}")