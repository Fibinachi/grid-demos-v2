"""Add AK/HI/TX bboxes to overture and process remaining states"""
import os, subprocess, time

script = os.path.expanduser("~/overture_enrich.py")
csv = os.path.expanduser("~/church_names_for_overture.csv")
log = os.path.expanduser("~/overture_remaining.log")

with open(script) as f:
    content = f.read()

if '"AK"' not in content:
    additions = '\n    "AK":[-180.0,51.0,-130.0,72.0],\n    "HI":[-160.0,18.5,-154.7,22.5],\n    "TX-NW":[-106.7,31.5,-98.0,36.5],\n    "TX-NE":[-98.0,31.5,-93.5,36.5],\n    "TX-SW":[-106.7,25.8,-98.0,31.5],\n    "TX-SE":[-98.0,25.8,-93.5,31.5],\n'
    content = content.replace('"DC":[-77.2,38.8,-76.9,39.0]',
                              '"DC":[-77.2,38.8,-76.9,39.0],' + additions)
    with open(script, 'w') as f:
        f.write(content)
    print("Added missing bboxes")
else:
    print("Bboxes already exist")

remaining = "TX-NW,TX-NE,TX-SW,TX-SE,UT,VT,VA,WA,WV,WI,WY,DC,AK,HI"
print(f"Processing: {remaining}")

with open(log, 'a') as lf:
    lf.write(f"\n[{time.strftime('%H:%M:%S')}] Started: {remaining}\n")

result = subprocess.run(
    ["python3", "-u", script, "--churches-csv", csv, "--states", remaining],
    capture_output=True, text=True, timeout=3600
)

with open(log, 'a') as lf:
    lf.write(result.stdout[-2000:] + "\n")
    if result.stderr:
        lf.write("STDERR:\n" + result.stderr[-2000:] + "\n")
    lf.write(f"exit: {result.returncode}\n")

print(f"Done. exit={result.returncode}")
print(result.stdout[-500:])
