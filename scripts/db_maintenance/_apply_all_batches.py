"""Apply all remaining Phase 2 batches autonomously."""
import subprocess, sys

VENV_PYTHON = r'E:\grid\.venv\Scripts\python.exe'
SCRIPT = r'E:\grid\_review_batch.py'

start_batch = 19  # Resume from where previous run crashed

print(f"Starting automatic apply from batch {start_batch}")
print("=" * 60)

batch = start_batch
while True:
    cmd = [VENV_PYTHON, SCRIPT, '--batch', str(batch), '--rule', 'phase2', '--apply']
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    out = result.stdout
    err = result.stderr

    # Parse applied count
    applied = 0
    for line in out.splitlines():
        if 'Applied:' in line and 'Total:' in line:
            parts = line.strip().split('|')
            for p in parts:
                if 'Applied:' in p:
                    applied = int(p.split(':')[1].strip())
            break

    print(f"Batch {batch}: Applied {applied} records. "
          f"{'OK' if result.returncode == 0 else f'ERROR (rc={result.returncode})'}")

    if result.returncode != 0:
        print(f"STDERR: {err[:500]}")
        print(f"STDOUT (last 10 lines):")
        for l in out.splitlines()[-10:]:
            print(f"  {l}")
        break

    if applied == 0:
        print("No changes — likely end of candidates. Stopping.")
        break

    batch += 1

print(f"\nDone. Applied through batch {batch - 1}.")
