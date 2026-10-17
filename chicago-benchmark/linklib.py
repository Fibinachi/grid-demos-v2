"""Normalization + matching primitives for the Cook County benchmark linkage."""
import re

ABBR = {
    "ST": "SAINT", "ST.": "SAINT", "MT": "MOUNT", "MT.": "MOUNT",
    "AVE": "AVENUE", "AV": "AVENUE", "ST": "STREET", "BLVD": "BOULEVARD",
    "N": "NORTH", "S": "SOUTH", "E": "EAST", "W": "WEST",
    "CH": "CHURCH", "CH.": "CHURCH",
}
STREET_SUFFIX = {"AVENUE", "STREET", "BOULEVARD", "ROAD", "DRIVE", "PLACE",
                 "COURT", "LANE", "TERRACE", "PARKWAY", "SQUARE"}
DIRECTIONS = {"NORTH", "SOUTH", "EAST", "WEST"}

def normalize_name(s):
    if not s:
        return ""
    s = s.upper()
    s = re.sub(r"[^\w\s]", " ", s)
    toks = []
    for t in s.split():
        t = ABBR.get(t, t)
        toks.append(t)
    # drop pure generic leading tokens? keep all; matching handles it
    return " ".join(toks)

def parse_address(s):
    """Return (house_number, direction, street_stem, suffix) normalized."""
    if not s:
        return ("", "", "", "")
    s = s.upper()
    s = re.sub(r"[^\w\s]", " ", s)
    toks = [ABBR.get(t, t) for t in s.split()]
    num, direction, suffix = "", "", ""
    rest = list(toks)
    if rest and re.fullmatch(r"\d+[A-Z]?", rest[0]):
        num = rest.pop(0)
    if rest and rest[0] in DIRECTIONS:
        direction = rest.pop(0)
    if rest and rest[-1] in STREET_SUFFIX:
        suffix = rest.pop(-1)
    stem = " ".join(rest)
    return (num, direction, stem, suffix)

def address_key(s):
    n, d, stem, suf = parse_address(s)
    return f"{n}|{d}|{stem}|{suf}"

def address_match(a, b):
    """Tier-1 address equality: same number+direction+street stem (suffix optional)."""
    na, da, sa, fa = parse_address(a)
    nb, db, sb, fb = parse_address(b)
    if not sa or not sb:
        return False
    if na and nb and na != nb:
        return False
    if not na and not nb:
        return False  # need a house number to call it the same address
    return da == db and sa == sb

def soundex(word):
    word = word.upper()
    if not word:
        return "0000"
    codes = {"BFPV": "1", "CGJKQSXZ": "2", "DT": "3", "L": "4",
             "MN": "5", "R": "6"}
    first = word[0]
    coded = first
    prev = None
    for ch in word[1:]:
        c = "0"
        for k, v in codes.items():
            if ch in k:
                c = v
                break
        if c != "0" and c != prev:
            coded += c
        prev = c if c != "0" else prev
    return (coded + "0000")[:4]

def name_block_key(name):
    toks = [t for t in normalize_name(name).split() if len(t) > 2]
    if not toks:
        return "XXXX"
    # soundex of first two significant tokens
    return "|".join(soundex(t) for t in toks[:2])

def street_block_key(addr):
    n, d, stem, suf = parse_address(addr)
    first = stem.split()[0] if stem else ""
    return soundex(first) if first else "XXXX"

def jaro_winkler(s1, s2):
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    len1, len2 = len(s1), len(s2)
    match_dist = max(len1, len2) // 2 - 1
    if match_dist < 0:
        match_dist = 0
    s1_match = [False] * len1
    s2_match = [False] * len2
    matches = 0
    for i in range(len1):
        lo = max(0, i - match_dist)
        hi = min(i + match_dist + 1, len2)
        for j in range(lo, hi):
            if not s2_match[j] and s1[i] == s2[j]:
                s1_match[i] = True
                s2_match[j] = True
                matches += 1
                break
    if matches == 0:
        return 0.0
    t = 0
    k = 0
    for i in range(len1):
        if s1_match[i]:
            while not s2_match[k]:
                k += 1
            if s1[i] != s2[k]:
                t += 1
            k += 1
    t //= 2
    jaro = (matches / len1 + matches / len2 + (matches - t) / matches) / 3.0
    # winkler boost
    prefix = 0
    for i in range(min(4, len1, len2)):
        if s1[i] == s2[i]:
            prefix += 1
        else:
            break
    return jaro + prefix * 0.1 * (1 - jaro)

def denom_branch(denom):
    """Coarse branch for denomination continuity check."""
    if not denom:
        return ""
    d = denom.upper()
    return d
