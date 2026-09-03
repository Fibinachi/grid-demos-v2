#!/usr/bin/env python3
"""
WPA Directory Bulk Import Preparation
===================================
Ready for laguna-m.1 processing to extract church entries.

FILES CLEANED:
- cleaned_AR.txt (232K chars, 5,795 lines) - Arkansas POC
- cleaned_DE.txt (234K chars) - Delaware
- cleaned_DC.txt (176K chars) - District of Columbia
- cleaned_ID.txt (152K chars) - Idaho
- cleaned_NM.txt (204K chars) - New Mexico
- cleaned_ME.txt (262K chars) - Maine
- cleaned_MN.txt (459K chars) - Minnesota  
- cleaned_MI_Rc.txt (105K chars) - Michigan (Catholic)
- cleaned_NY.txt (196K chars) - New York
- cleaned_PA_Friends.txt (511K chars) - Pennsylvania (Society of Friends)

FORMAT:
Directory files: [church name + address] | [town] | [county]
Denomination sections with entries like:
  "Church name, street address, City, County"

NEXT STEPS:
1. Use laguna-m.1 to extract structured entries from each cleaned file
2. Parse into: church_name, address, city, county, denomination, pastor_name
3. Import into churches.db

COMMANDS TO RUN:
python scripts/ingest/parse_wpa_laguna.py --state AR    # POC for Arkansas
python scripts/ingest/parse_wpa_laguna.py --all          # All states
"""
print(__doc__)