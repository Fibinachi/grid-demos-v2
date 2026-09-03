#!/usr/bin/env python3
"""
Full pipeline: Download all LOC phone dirs, extract churches, match to GRID.
Run this in background to process all 2,365 Yellow Pages.
"""
import subprocess, sys, time
from pathlib import Path

BASE = Path("E:/grid")
SCRIPT = BASE / "scripts" / "ingest" / "loc_phone_directories.py"
PYTHON = BASE / ".venv" / "Scripts" / "python.exe"

steps = [
    (["--download"], "Download OCR text"),
    (["--extract", "--match"], "Extract churches + match to GRID"),
]

for args, desc in steps:
    print(f"\n{'='*60}")
    print(f"  {desc}")
    print(f"{'='*60}")
    
    cmd = [str(PYTHON), str(SCRIPT)] + args
    result = subprocess.run(cmd, cwd=str(BASE))
    
    if result.returncode != 0:
        print(f"  ❌ Failed with exit code {result.returncode}")
        # Continue anyway — next step may work with partial data
    
    print()

print("\n✅ Full pipeline complete!")
