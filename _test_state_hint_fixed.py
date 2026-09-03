"""_test_state_hint_fixed.py — verify extraction excludes foreign words."""
import sys
sys.path.insert(0, r"E:\grid")
from _recover_shared_coords_v2 import extract_state_hint

tests = [
    "FIRST BAPTIST CHURCH OF WASHINGTON MICHIGAN",
    "IGLESIA DE DIOS DE LA PROFECIA",
    "IGLESIA DE DIOS PENTECOSTAL",
    "TRINIDAD DE DIOS",
    "IGLESIA PENTECOSTAL ALPHA OMEGA CASA DE LUZ",
    "AL ROWDA MOSQUE",
    "MT CALVARY BAPTIST CHURCH",
    "MT VERNON BAPTIST CHURCH",
    "Protestant Episcopal Church in the United States",
]
for t in tests:
    print(f"{extract_state_hint(t)[0]!s:4} | {t}")