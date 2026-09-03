"""
Geographic & Asset Filtering for Foundation Lists
===================================================
Consolidates: apply_final_filters.py logic

Single source for foundation eligibility: geography, assets, NTEE, score.
"""

import re

# Home state for geographic filtering
HOME_STATE = "SC"

# State names that indicate geographic restriction (when in foundation name)
OTHER_STATE_NAMES = [
    'ALABAMA', 'ALASKA', 'ARIZONA', 'ARKANSAS', 'CALIFORNIA', 'COLORADO',
    'CONNECTICUT', 'DELAWARE', 'FLORIDA', 'GEORGIA', 'HAWAII', 'IDAHO',
    'ILLINOIS', 'INDIANA', 'IOWA', 'KANSAS', 'KENTUCKY', 'LOUISIANA',
    'MAINE', 'MARYLAND', 'MASSACHUSETTS', 'MICHIGAN', 'MINNESOTA',
    'MISSISSIPPI', 'MISSOURI', 'MONTANA', 'NEBRASKA', 'NEVADA',
    'NEW HAMPSHIRE', 'NEW JERSEY', 'NEW MEXICO', 'NEW YORK',
    'NORTH CAROLINA', 'NORTH DAKOTA', 'OHIO', 'OKLAHOMA', 'OREGON',
    'PENNSYLVANIA', 'RHODE ISLAND', 'SOUTH DAKOTA', 'TENNESSEE',
    'TEXAS', 'UTAH', 'VERMONT', 'VIRGINIA', 'WASHINGTON',
    'WEST VIRGINIA', 'WISCONSIN', 'WYOMING',
]
OTHER_STATES_LOWER = [s.lower() for s in OTHER_STATE_NAMES]

# States/countries to keep regardless of location
KEEP_REGIONS = {'SC', 'DC', '', 'ON', 'QC', 'BC', 'AB', 'MB', 'SK', 'NS', 'NB', 'NL', 'PE', 'NT', 'YT', 'NU'}

LOCAL_FOCUS_KEYWORDS = [
    'community foundation', 'foundation of ', 'foundation for ',
    'area foundation', 'regional foundation',
]

MIN_ASSETS = 1_000_000  # $1M minimum


def passes(name, state="", ntee="", score=0, asset_amt="0", priority=""):
    """
    Check if a foundation passes all filters.
    Returns (passes: bool, reasons: [str]).

    Filters: geography → NTEE → assets → score
    """
    reasons = []

    # ── Geography ──
    name_lower = name.lower().strip() if name else ""
    state_upper = state.strip().upper() if state else ""

    # Check for other state names in foundation title
    for s in OTHER_STATES_LOWER:
        if re.search(r'\b' + re.escape(s) + r'\b', name_lower):
            if s != 'south carolina' and 'carolina' not in name_lower:
                return (False, ["other_state_in_name"])

    # Check location-based restriction
    if state_upper and state_upper not in KEEP_REGIONS and state_upper != HOME_STATE:
        has_local_focus = any(kw in name_lower for kw in LOCAL_FOCUS_KEYWORDS)
        if has_local_focus:
            return (False, ["out_of_state_local_focus"])

    # ── NTEE ──
    if ntee and not ntee.startswith(('T', 'X')):
        return (False, ["ntee_not_T_or_X"])

    # ── Assets ──
    if asset_amt and asset_amt != '0':
        try:
            if float(asset_amt) < MIN_ASSETS:
                return (False, [f"assets_below_{MIN_ASSETS}"])
        except ValueError:
            pass

    # ── Score ──
    try:
        if priority != 'HIGH' and int(score) < 30:
            return (False, ["score_below_30"])
    except (ValueError, TypeError):
        pass

    return (True, [])


def filter_foundations(rows, home_state=HOME_STATE):
    """
    Filter a list of foundation dicts. Returns (kept, removed_counts).
    Each dict should have keys: NAME, STATE, NTEE, THEOLOGY_SCORE, ASSET_AMT, PRIORITY
    """
    kept = []
    removed = {"geo": 0, "ntee": 0, "assets": 0, "score": 0}

    for r in rows:
        ok, reasons = passes(
            name=r.get('NAME', ''),
            state=r.get('STATE', ''),
            ntee=r.get('NTEE', ''),
            score=r.get('THEOLOGY_SCORE', 0),
            asset_amt=r.get('ASSET_AMT', '0'),
            priority=r.get('PRIORITY', ''),
        )
        if ok:
            kept.append(r)
        else:
            for reason in reasons:
                if "state" in reason or "geo" in reason:
                    removed["geo"] += 1
                elif "ntee" in reason:
                    removed["ntee"] += 1
                elif "asset" in reason:
                    removed["assets"] += 1
                elif "score" in reason:
                    removed["score"] += 1

    return kept, removed
