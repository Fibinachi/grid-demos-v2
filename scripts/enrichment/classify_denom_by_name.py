#!/usr/bin/env python3
"""
Name-based Denomination Classifier (Expanded v2)
================================================
Classifies churches by denomination using name patterns.
Covers 40+ denominational families including:
- Catholic (Roman, Maronite, Byzantine, ethnic Catholic)
- Baptist (Southern, Independent, Missionary, Free Will, Primitive, Regular,
  General, Reformed, Sovereign Grace, National Baptist x3, Progressive,
  Full Gospel, American, Separate, Duck River)
- Methodist (United, AME, AME Zion, CME, Free, Congregational, Wesleyan)
- Lutheran (LCMS, ELCA, WELS, ELS, American, Apostolic, Brethren, ethnic)
- Presbyterian (PCUSA, PCA, Cumberland, OPC, Associate Reformed)
- Pentecostal (AG, UPCI, PAW, COGIC, COGOP, IPHC, Oneness, Apostolic)
- Episcopal/Anglican (TEC, ACNA)
- Restoration Movement (CoC, Disciples, Independent Christian)
- Adventist (SDA, Sabbath)
- Nazarene/Holiness (Nazarene, Salvation Army, Sanctified)
- Reformed (RCA, CRC, Protestant Reformed, Netherlands Reformed)
- Orthodox (Greek, Russian/OCA, Antiochian, Serbian, Romanian, Bulgarian,
  Coptic, Ethiopian, Eritrean, Armenian)
- Mennonite/Brethren/Quaker
- Jewish, Muslim, Buddhist, Hindu, Sikh, Bahai, Unitarian
- Modern non-denom indicators
- Ethnic/immigrant church indicators
- Other traditions (Spiritualist, Pagan, Indigenous, etc.)

Already 129,920 churches have classification_source='name_heuristic'.
This extends and refines that to cover all churches.

Usage:
    python scripts/enrichment/classify_denom_by_name.py
    python scripts/enrichment/classify_denom_by_name.py --dry-run --limit 1000
"""
import sqlite3, re
from collections import Counter

DB = r'E:\grid\churches.db'

# Denomination classification rules — ordered by specificity
# (keyword_pattern, denomination, family, faith_tradition)
RULES = [
    # ─── CATHOLIC ───
    (r'\b(?:roman\s+catholic|catholic\s+church)\b', "Roman Catholic Church", "Catholic Churches", "christian"),
    (r'\b(st\.?\s+\w+\s+(?:church|parish))\b(?!.*\b(baptist|methodist|lutheran|presbyterian|episcopal)\b)', None, "Catholic Churches", "christian"),
    (r'\b(catholic|parish)\b', None, "Catholic Churches", "christian"),
    (r'\bmaronite\b', "Maronite Catholic Church", "Catholic Churches", "christian"),
    (r'\bbyzantine\s+catholic\b', "Byzantine Catholic Church", "Catholic Churches", "christian"),
    (r'\b(?:ukrainian|polish|slovak)\s+catholic\b', None, "Catholic Churches", "christian"),

    # ─── BAPTIST ───
    (r'\bsouthern\s+baptist\b', "Southern Baptist Convention", "Baptist Churches", "christian"),
    (r'\b(?:independent\s+baptist|baptist\s+bible|fundamental\s+baptist)\b', "Independent Baptist", "Baptist Churches", "christian"),
    (r'\bmissionary\s+baptist\b', "Missionary Baptist", "Baptist Churches", "christian"),
    (r'\bfree\s+will\s+baptist\b', "Free Will Baptist", "Baptist Churches", "christian"),
    (r'\bprimitive\s+baptist\b', "Primitive Baptist", "Baptist Churches", "christian"),
    (r'\b(?:regular\s+baptist|general\s+baptist|united\s+baptist)\b', None, "Baptist Churches", "christian"),
    (r'\breformed\s+baptist|sovereign\s+grace\s+baptist\b', "Reformed Baptist", "Baptist Churches", "christian"),
    (r'\bnational\s+baptist\s+convention\b', "National Baptist Convention", "Baptist Churches", "christian"),
    (r'\bnational\s+baptist\b(?!.*convention)', "National Baptist Convention of America", "Baptist Churches", "christian"),
    (r'\bprogressive\s+baptist\b', "Progressive National Baptist Convention", "Baptist Churches", "christian"),
    (r'\bfull\s+gospel\s+baptist\b', "Full Gospel Baptist Church Fellowship", "Baptist Churches", "christian"),
    (r'\b(?:american\s+baptist|abcusa)\b', "American Baptist Churches USA", "Baptist Churches", "christian"),
    (r'\b(?:separate\s+baptist|duck\s+river\s+baptist)\b', None, "Baptist Churches", "christian"),
    (r'\bbaptist\b', None, "Baptist Churches", "christian"),

    # ─── METHODIST ───
    (r'\b(?:united\s+methodist|umc)\b', "United Methodist Church", "Methodist Churches", "christian"),
    (r'\b(?:african\s+methodist\s+episcopal\s+zion|ame\s+zion)\b', "African Methodist Episcopal Zion Church", "Methodist Churches", "christian"),
    (r'\b(?:african\s+methodist\s+episcopal|ame\s+church)\b', "African Methodist Episcopal Church", "Methodist Churches", "christian"),
    (r'\b(?:christian\s+methodist\s+episcopal|cme)\b', "Christian Methodist Episcopal Church", "Methodist Churches", "christian"),
    (r'\bfree\s+methodist\b', "Free Methodist Church", "Methodist Churches", "christian"),
    (r'\bcongregational\s+methodist\b', "Congregational Methodist Church", "Methodist Churches", "christian"),
    (r'\bwesleyan\b', "Wesleyan Church", "Methodist Churches", "christian"),
    (r'\bmethodist\b', None, "Methodist Churches", "christian"),

    # ─── LUTHERAN ───
    (r'\b(?:lcms|lutheran\s+church\s+missouri\s+synod|missouri\s+synod)\b', "Lutheran Church Missouri Synod", "Lutheran Churches", "christian"),
    (r'\b(?:elca|evangelical\s+lutheran\s+church)\b', "Evangelical Lutheran Church in America", "Lutheran Churches", "christian"),
    (r'\b(?:wisconsin\s+synod|wels)\b', "Wisconsin Evangelical Lutheran Synod", "Lutheran Churches", "christian"),
    (r'\b(?:evangelical\s+lutheran\s+synod|els)\b', "Evangelical Lutheran Synod", "Lutheran Churches", "christian"),
    (r'\b(?:american\s+lutheran|apostolic\s+lutheran|lutheran\s+brethren)\b', None, "Lutheran Churches", "christian"),
    (r'\b(?:swedish|danish|norwegian|finnish|german)\s+lutheran\b', None, "Lutheran Churches", "christian"),
    (r'\blutheran\b', None, "Lutheran Churches", "christian"),

    # ─── PRESBYTERIAN ───
    (r'\b(?:pcusa|presbyterian\s+church\s+usa)\b', "Presbyterian Church USA", "Presbyterian Churches", "christian"),
    (r'\b(?:pca|presbyterian\s+church\s+in\s+america)\b', "Presbyterian Church in America", "Presbyterian Churches", "christian"),
    (r'\b(?:cumberland\s+presbyterian|arp|associate\s+reformed\s+presbyterian)\b', "Cumberland Presbyterian", "Presbyterian Churches", "christian"),
    (r'\b(?:orthodox\s+presbyterian|opc)\b', "Orthodox Presbyterian Church", "Presbyterian Churches", "christian"),
    (r'\b(?:evangelical\s+covenant|ec church)\b', "Evangelical Covenant Church", "Presbyterian Churches", "christian"),
    (r'\bpresbyterian\b', None, "Presbyterian Churches", "christian"),

    # ─── PENTECOSTAL ───
    (r'\b(?:assemblies\s+of\s+god|ag\b\.?)\b', "Assemblies of God", "Pentecostal Churches", "christian"),
    (r'\b(?:united\s+pentecostal|upci)\b', "United Pentecostal Church International", "Pentecostal Churches", "christian"),
    (r'\bpentecostal\s+assemblies\s+of\s+the\s+world\b', "Pentecostal Assemblies of the World", "Pentecostal Churches", "christian"),
    (r'\b(?:church\s+of\s+god\s+in\s+christ|cogic)\b', "Church of God in Christ", "Pentecostal Churches", "christian"),
    (r'\b(?:church\s+of\s+god\s+of\s+prophecy|cogop)\b', "Church of God of Prophecy", "Pentecostal Churches", "christian"),
    (r'\b(?:international\s+pentecostal\s+holiness|iphc)\b', "International Pentecostal Holiness Church", "Pentecostal Churches", "christian"),
    (r'\b(?:oneness|jesus\s+name|apostolic\s+pentecostal)\b', None, "Pentecostal Churches", "christian"),
    (r'\b(?:pentecostal|full\s+gospel)\b', None, "Pentecostal Churches", "christian"),

    # ─── CHURCH OF GOD ───
    (r'\bchurch\s+of\s+god\b(?!.*\b(in\s+christ|prophecy|apostolic)\b)', "Church of God (Cleveland, TN)", "Pentecostal Churches", "christian"),

    # ─── EPISCOPAL / ANGLICAN ───
    (r'\b(?:episcopal\s+church|tec)\b', "Episcopal Church", "Episcopal and Anglican Churches", "christian"),
    (r'\b(?:anglican|acna)\b', "Anglican Church in North America", "Episcopal and Anglican Churches", "christian"),
    (r'\bepiscopal\b', None, "Episcopal and Anglican Churches", "christian"),

    # ─── RESTORATION MOVEMENT ───
    (r'\bchurches?\s+of\s+christ\b', "Churches of Christ", "Christian and Restorationist Churches", "christian"),
    (r'\b(?:christian\s+church|disciples\s+of\s+christ)\b', "Christian Church (Disciples of Christ)", "Christian and Restorationist Churches", "christian"),
    (r'\b(?:independent\s+christian|christian\s+chapel)\b', None, "Christian and Restorationist Churches", "christian"),

    # ─── ADVENTIST ───
    (r'\b(?:seventh.day\s+adventist|sda|adventist)\b', "Seventh-day Adventist Church", "Adventist Churches", "christian"),
    (r'\bsabbath\b', None, "Adventist Churches", "christian"),

    # ─── NAZARENE / HOLINESS ───
    (r'\bnazarene\b', "Church of the Nazarene", "Holiness Churches", "christian"),
    (r'\bsalvation\s+army\b', "Salvation Army", "Holiness Churches", "christian"),
    (r'\b(?:holiness|sanctified|christian\s+assembly)\b', None, "Holiness Churches", "christian"),

    # ─── REFORMED ───
    (r'\b(?:reformed\s+church\s+in\s+america|rca)\b', "Reformed Church in America", "Reformed Churches", "christian"),
    (r'\b(?:christian\s+reformed|crc)\b', "Christian Reformed Church in North America", "Reformed Churches", "christian"),
    (r'\b(?:protestant\s+reformed|netherlands\s+reformed|free\s+reformed|heritage\s+reformed)\b', None, "Reformed Churches", "christian"),
    (r'\breformed\s+(?:church|baptist|presbyterian)\b', None, "Reformed Churches", "christian"),

    # ─── CONGREGATIONAL ───
    (r'\b(?:congregational|ucc|united\s+church\s+of\s+christ)\b', "United Church of Christ", "Congregational Churches", "christian"),

    # ─── MENNONITE / BRETHREN ───
    (r'\b(?:mennonite\s+brethren)\b', "Mennonite Brethren", "Mennonite Churches", "christian"),
    (r'\b(?:mennonite\s+church\s+usa|mennonite\s+church,\s|\bmc\s+usa)\b', "Mennonite Church USA", "Mennonite Churches", "christian"),
    (r'\bconservative\s+mennonite\b', "Conservative Mennonite", "Mennonite Churches", "christian"),
    (r'\bold\s+order\s+mennonite\b', "Old Order Mennonite", "Mennonite Churches", "christian"),
    (r'\b(?:mennonite|amis)\b', "Mennonite (unspecified)", "Mennonite Churches", "christian"),
    (r'\b(?:brethren\s+in\s+christ|church\s+of\s+the\s+brethren)\b', None, "Brethren Churches", "christian"),
    (r'\bbrethren\b', None, "Brethren Churches", "christian"),
    (r'\b(?:quaker|friends\s+(?:church|meeting)|society\s+of\s+friends)\b', "Religious Society of Friends (Quakers)", "Friends (Quaker) Churches", "christian"),

    # ─── ORTHODOX ───
    (r'\b(?:greek\s+orthodox|holy\s+trinity\s+greek)\b', "Greek Orthodox Archdiocese of America", "Orthodox Churches", "christian"),
    (r'\b(?:russian\s+orthodox|orthodox\s+church\s+in\s+america|oca)\b', "Orthodox Church in America", "Orthodox Churches", "christian"),
    (r'\b(?:antiochian\s+orthodox|syrian\s+orthodox)\b', "Antiochian Orthodox Christian Archdiocese", "Orthodox Churches", "christian"),
    (r'\bserbian\s+orthodox\b', "Serbian Orthodox Church", "Orthodox Churches", "christian"),
    (r'\bromanian\s+orthodox\b', "Romanian Orthodox Church", "Orthodox Churches", "christian"),
    (r'\bbulgarian\s+orthodox\b', "Bulgarian Orthodox Church", "Orthodox Churches", "christian"),
    (r'\b(?:ukrainian\s+orthodox|ukrainian\s+autocephalous)\b', "Ukrainian Orthodox Church", "Orthodox Churches", "christian"),
    (r'\bcoptic\s+orthodox\b', "Coptic Orthodox Church", "Orthodox Churches", "christian"),
    (r'\b(?:ethiopian\s+orthodox|eritrean\s+orthodox|tewahedo|tewahdo|tewahedo)\b', "Ethiopian Orthodox Tewahedo Church", "Orthodox Churches", "christian"),
    (r'\b(?:armenian\s+apostolic|armenian\s+orthodox)\b', "Armenian Apostolic Church", "Orthodox Churches", "christian"),
    (r'\b(?:malankara\s+orthodox\s+syrian|malankara)\b', "Malankara Orthodox Syrian Church", "Orthodox Churches", "christian"),
    (r'\b(?:albanian\s+orthodox|macedonian\s+orthodox)\b', None, "Orthodox Churches", "christian"),
    (r'\borthodox\b', None, "Orthodox Churches", "christian"),

    # ─── EVANGELICAL ───
    (r'\bevangelical\s+free\b', "Evangelical Free Church of America", "Other Churches", "christian"),

    # ─── FOURSQUARE ───
    (r'\b(?:foursquare|international\s+church\s+of\s+the\s+foursquare\s+gospel)\b', "Foursquare Church", "Pentecostal Churches", "christian"),

    # ─── VINEYARD ───
    (r'\bvineyard\s+church\b', "Vineyard Churches", "Other Churches", "christian"),
    (r'\bvineyard\b', None, "Other Churches", "christian"),

    # ─── CALVARY CHAPEL ───
    (r'\bcalvary\s+chapel\b', "Calvary Chapel", "Other Churches", "christian"),
    (r'\bevangelical\s+(?:covenant|church)\b', None, "Other Churches", "christian"),

    # ─── NON-DENOMINATIONAL ───
    (r'\b(?:non.?denom|nondenom|independent\s+bible)\b', "Non-Denominational / Independent", "Other Churches", "christian"),
    (r'\binterdenominational\b', "Interdenominational", "Other Churches", "christian"),
    (r'\b(?:nondenominational|independent\s+church)\b', "Non-Denominational / Independent", "Other Churches", "christian"),
    (r'\bcommunity\s+church\b', None, "Other Churches", "christian"),
    (r'\b(?:fellowship|bible\s+church|chapel|calvary\s+temple)\b', None, "Other Churches", "christian"),

    # Modern non-denom indicators
    (r'\b(?:new\s+life|abundant\s+life|victory\s+church|harvest\s+church|destiny|kingdom\s+church)\b', None, "Other Churches", "christian"),
    (r'\b(?:river\s+church|gateway\s+church|the\s+rock\s+church|elevation|passion|hillsong)\b', None, "Other Churches", "christian"),

    # Ethnic/Immigrant church indicators
    (r'\b(?:korean\s+presbyterian|korean\s+baptist|korean\s+methodist|korean\s+church)\b', None, None, "christian"),
    (r'\b(?:chinese\s+church|vietnamese\s+catholic|vietnamese\s+buddhist)\b', None, None, "christian"),
    (r'\b(?:hispanic|latino)\s+(?:church|congregation|assembly)\b', None, None, "christian"),
    (r'\b(?:igbo|nigerian|ghanaian|kenyan|ethiopian)\s+(?:church|congregation)\b', None, None, "christian"),
    (r'\b(?:swedish|norwegian|danish|finnish|german|dutch|swiss)\s+(?:church|congregation|evangelical|lutheran)\b', None, None, "christian"),

    # ─── LDS ───
    (r'\b(?:lds|latter.day\s+saint|mormon|jesus\s+christ\s+of\s+latter)\b', "Church of Jesus Christ of Latter-day Saints", "Other Churches", "christian"),
    (r'\breorganized\s+lds|rlds\b', "Community of Christ", "Other Churches", "christian"),

    # ─── JEWISH ───
    (r'\b(?:synagogue|temple|congregation|beth\s+|shalom|chabad|temple\s+israel|b\s+nai)\b', None, None, "jewish"),
    (r'\bjewish\b', None, None, "jewish"),
    (r'\b(?:conservative\s+judaism|reform\s+temple|orthodox\s+synagogue)\b', None, None, "jewish"),

    # ─── MUSLIM ───
    (r'\b(?:mosque|masjid|islamic|muslim)\b', None, None, "muslim"),
    (r'\b(?:sunni|shia|nation\s+of\s+islam)\b', None, None, "muslim"),

    # ─── BUDDHIST ───
    (r'\b(?:buddhist|buddha|temple\b.*\bbudd|dharma|sangha|zen|vihara|stupa)\b', None, None, "buddhist"),

    # ─── HINDU ───
    (r'\b(?:hindu|mandir|temple\b.*\bhind|sanatan|vedic)\b', None, None, "hindu"),

    # ─── SIKH ───
    (r'\b(?:sikh|gurdwara)\b', None, None, "sikh"),

    # ─── OTHER TRADITIONS ───
    (r'\b(?:unity\s+church|unitarian|universalist|uus)\b', "Unitarian Universalist", None, "other"),
    (r'\b(?:religious\s+science|divine\s+science|christian\s+scientist)\b', None, None, "other"),
    (r'\b(?:spiritualist|bahai|baha\'i|zoroastrian|jain)\b', None, None, "other"),
    (r'\b(?:pagan|wicca|coven|earth\s+centered|heathen)\b', None, None, "other"),
    (r'\b(?:native\s+american|indigenous\s+church|sweat\s+lodge|powwow)\b', None, None, "other"),
]

# Name patterns that are STRONGLY christian (default for "St." names etc)
CHRISTIAN_INDICATORS = [
    r'\bst\.?\s+\w+\b', r'\bfirst\s+\w+\b', r'\bgrace\b', r'\bfaith\b',
    r'\btrinity\b', r'\bhope\b', r'\bcross\b', r'\bnew\s+\w+\s+baptist\b',
    r'\bpeace\b', r'\bunity\b', r'\bword\s+of\s+god\b', r'\bbible\b',
    r'\bpraise\b', r'\bworship\b', r'\bredeemer\b', r'\bsavior\b',
    r'\bgospel\b', r'\b(?:kingdom|harvest|victory|destiny)\s+church\b',
    r'\babundant\s+life\b', r'\bnew\s+(?:life|covenant|hope|vision|birth|day)\b',
    r'\b(?:living|life|light|love|living\s+water)\b',
    r'\b(?:good\s+shepherd|great\s+physician|rock\s+of\s+ages)\b',
    r'\b(?:overcomer|champion|generation|freedom|legacy)\s+church\b',
    r'\b(?:river|gateway|summit|impact|mercy|cornerstone)\s+church\b',
]


def classify_church(name, current_denom="", current_family="", current_tradition=""):
    """Classify a church by name. Returns (denomination, family, faith_tradition)."""
    if not name:
        return current_denom, current_family, current_tradition
    
    name_lower = name.lower()
    name_upper = name.upper()
    
    best = {"denom": current_denom, "family": current_family, "tradition": current_tradition, "priority": 0}
    
    for pattern, denom, family, tradition in RULES:
        m = re.search(pattern, name_lower)
        if m:
            priority = len(m.group(0)) if m.group(0) else 5
            if best["denom"] and not denom:
                priority -= 1  # existing specific denom takes priority
            if priority > best["priority"]:
                best["denom"] = denom or best["denom"]
                best["family"] = family or best["family"]
                best["tradition"] = tradition or best["tradition"]
                best["priority"] = priority
    
    # Default to christian if name looks christian
    if best["tradition"] in ("", None):
        for indicator in CHRISTIAN_INDICATORS:
            if re.search(indicator, name_lower):
                best["tradition"] = "christian"
                best["family"] = best["family"] or "Other Churches"
                break
    
    return best["denom"], best["family"], best["tradition"]


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    
    db = sqlite3.connect(DB)
    
    # Get churches needing classification improvement
    rows = db.execute("""
        SELECT id, name, denomination, family, faith_tradition
        FROM churches
        ORDER BY 
            CASE WHEN denomination = '' THEN 0 ELSE 1 END,
            id
    """).fetchall()
    
    if args.limit:
        rows = rows[:args.limit]
    
    print(f"Processing {len(rows):,} churches...")
    
    updates = {"denom": 0, "family": 0, "tradition": 0}
    
    for row in rows:
        cid, name, curr_denom, curr_family, curr_tradition = row
        
        new_denom, new_family, new_tradition = classify_church(
            name, curr_denom, curr_family, curr_tradition
        )
        
        parts = []
        
        if new_denom and new_denom != curr_denom:
            parts.append(f"denomination='{new_denom.replace(chr(39), chr(39)*2)}'")
            updates["denom"] += 1
        
        if new_family and new_family != curr_family:
            parts.append(f"family='{new_family.replace(chr(39), chr(39)*2)}'")
            updates["family"] += 1
        
        if new_tradition and new_tradition != curr_tradition:
            parts.append(f"faith_tradition='{new_tradition.replace(chr(39), chr(39)*2)}'")
            updates["tradition"] += 1
        
        if parts:
            parts.append("classification_source=CASE WHEN classification_source='' THEN 'name_heuristic' ELSE classification_source END")
            if not args.dry_run:
                db.execute(f"UPDATE churches SET {', '.join(parts)} WHERE id=?", (cid,))
    
    if not args.dry_run:
        db.commit()
    
    print(f"\nDone!")
    print(f"  Denominations updated: {updates['denom']:,}")
    print(f"  Families updated: {updates['family']:,}")
    print(f"  Traditions updated: {updates['tradition']:,}")
    
    # Show new distribution
    print(f"\nTop 20 denominations:")
    rs = db.execute("""
        SELECT denomination, COUNT(*) FROM churches 
        WHERE denomination != '' 
        GROUP BY denomination 
        ORDER BY COUNT(*) DESC LIMIT 20
    """).fetchall()
    for r in rs:
        print(f"  {r[0]:35s} {r[1]:>8,}")
    
    db.close()


if __name__ == "__main__":
    main()
