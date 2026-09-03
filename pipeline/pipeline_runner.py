"""
Pipeline Runner
===============
Runs a sequence of tasks on an EC2, chaining automatically.
Usage: python3 pipeline_runner.py <instance_id> <log_prefix>
Tasks are defined in TASKS dict below.
"""
import subprocess, sys, time, os

# ─── Task definitions ─────────────────────────────────────────────
# Each task: (description, shell_command)
# Commands use && chaining: each only runs if previous succeeded
# Use || to handle expected failures gracefully

TASKS = {
    "phase1_chunk0": [
        ("Deep scrape 1,861 sites",
         "cd ~ && python3 -u ec2_deep_scrape.py scraped_chunk_0.csv deep_profiles.csv"),
    ],
    "phase1_chunk1": [
        ("Phase 1 phones/emails",
         "cd ~ && python3 -u ec2_phones_scraper.py 1"),
        ("Deep scrape results",
         "cd ~ && ls scraped_chunk_1.csv 2>/dev/null && python3 -u ec2_deep_scrape.py scraped_chunk_1.csv deep_profiles_1.csv || echo 'No output yet, skipping'"),
    ],
    "phase1_chunk2": [
        ("Phase 1 phones/emails",
         "cd ~ && python3 -u ec2_phones_scraper.py 2"),
        ("Deep scrape results",
         "cd ~ && ls scraped_chunk_2.csv 2>/dev/null && python3 -u ec2_deep_scrape.py scraped_chunk_2.csv deep_profiles_2.csv || echo 'No output yet, skipping'"),
    ],
    "irs_finder": [
        ("Website discovery (91K churches)",
         "cd ~ && python3 -u ec2_find_websites.py 0"),
        ("Phase 1 scrape on found websites",
         "cd ~ && ls found_chunk_0.csv 2>/dev/null && mkdir -p phase1_chunks && python3 -u ec2_phones_scraper.py --input found_chunk_0.csv --output scraped_irs.csv || echo 'No found.csv yet'"),
    ],
}

def run_task(desc, cmd, logfile):
    """Run a task, log output, return True on success."""
    print(f"\n{'='*60}")
    print(f"[{time.strftime('%H:%M:%S')}] START: {desc}")
    print(f"  Command: {cmd[:100]}...")
    print(f"  Log: {logfile}")
    print(f"{'='*60}")
    
    full_cmd = f"{cmd} >> {logfile} 2>&1"
    result = subprocess.run(full_cmd, shell=True)
    
    status = "SUCCESS" if result.returncode == 0 else f"FAILED (code {result.returncode})"
    print(f"[{time.strftime('%H:%M:%S')}] {status}: {desc}")
    print(f"  Last 3 log lines:")
    try:
        tail = subprocess.run(f"tail -3 {logfile}", shell=True, capture_output=True, text=True)
        for line in tail.stdout.strip().split('\n'):
            print(f"    {line}")
    except:
        pass
    return result.returncode == 0

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 pipeline_runner.py <task_chain>")
        print("Task chains: phase1_chunk0, phase1_chunk1, phase1_chunk2, irs_finder")
        sys.exit(1)
    
    chain_name = sys.argv[1]
    tasks = TASKS.get(chain_name)
    if not tasks:
        print(f"Unknown chain: {chain_name}")
        print(f"Available: {list(TASKS.keys())}")
        sys.exit(1)
    
    logfile = f"pipeline_{chain_name}.log"
    print(f"Pipeline: {chain_name} ({len(tasks)} tasks)")
    print(f"Start: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Log: {logfile}")
    
    for i, (desc, cmd) in enumerate(tasks, 1):
        success = run_task(desc, cmd, logfile)
        if not success:
            print(f"\n⚠️  Task {i}/{len(tasks)} FAILED. Retrying once after 30s...")
            time.sleep(30)
            success = run_task(desc, cmd, logfile)
            if not success:
                print(f"\n❌ Pipeline failed at task {i}/{len(tasks)}: {desc}")
                sys.exit(1)
        
        # Small delay between tasks
        time.sleep(5)
    
    print(f"\n{'='*60}")
    print(f"✅ Pipeline complete: {chain_name}")
    print(f"All {len(tasks)} tasks finished successfully")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
