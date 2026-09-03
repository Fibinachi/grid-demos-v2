#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║                     REACH — GrantWizard CLI                 ║
║     One menu to rule all your foundation outreach tools     ║
╚══════════════════════════════════════════════════════════════╝

Usage:
  python reach.py          # Launch interactive menu
  python reach.py <cmd>    # Run a command directly (e.g. "status")
"""

import os
import sys
import time
import subprocess
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "ses_logs")
SENT_LOG = os.path.join(LOG_DIR, "ses_sent.txt")
ERROR_LOG = os.path.join(LOG_DIR, "ses_errors.txt")

# ── Utilities ─────────────────────────────────────────────────────

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

def header():
    print()
    print("  ╔══════════════════════════════════════════════════════════╗")
    print("  ║               🌊  REACH  —  GrantWizard                ║")
    print("  ║     Foundation outreach command center for the win      ║")
    print("  ╚══════════════════════════════════════════════════════════╝")
    print()

def pause():
    input("\n  Press Enter to return to menu...")

def run(cmd, desc, env_add=None):
    """Run a command in the same terminal, showing live output."""
    print(f"\n  ▶ {desc}...\n")
    sys.stdout.flush()
    # Build environment
    env = os.environ.copy()
    if env_add:
        env.update(env_add)
    # Strip PS env prefix for subprocess
    clean_cmd = cmd
    if clean_cmd.startswith("$env:"):
        # Extract env vars from PowerShell syntax and pass via env param
        import re
        parts = re.findall(r'\$env:(\w+)\s*=\s*"([^"]*)"', clean_cmd)
        for k, v in parts:
            env[k] = v
        clean_cmd = re.sub(r'\$env:\w+\s*=\s*"[^"]*";?\s*', '', clean_cmd).strip()
        # Remove leading semicolons
        clean_cmd = clean_cmd.lstrip("; ")
    result = subprocess.run(clean_cmd, shell=True, cwd=SCRIPT_DIR, env=env)
    if result.returncode != 0:
        print(f"\n  ⚠️  Command exited with code {result.returncode}")
    pause()

def run_bg(cmd, desc):
    """Launch a command in a new terminal window."""
    print(f"\n  ▶ Launching {desc} in a new window...")
    sys.stdout.flush()
    if os.name == 'nt':
        subprocess.Popen(['start', 'cmd', '/k', cmd], shell=True, cwd=SCRIPT_DIR)
    else:
        subprocess.Popen(['x-terminal-emulator', '-e', cmd], shell=True, cwd=SCRIPT_DIR)
    pause()

def count_lines(path):
    if not os.path.exists(path):
        return 0
    with open(path, 'r') as f:
        return sum(1 for l in f if l.strip())

def count_unique_eins(path):
    """Count unique EINs in a log file."""
    if not os.path.exists(path):
        return 0, 0
    eins = set()
    total = 0
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            parts = line.split('|')
            if parts:
                eins.add(parts[0])
    return len(eins), total

# ── Summary Banner ───────────────────────────────────────────────

def show_summary():
    sent_eins, sent_lines = count_unique_eins(SENT_LOG)
    err_lines = count_lines(ERROR_LOG)
    
    # Calculate rate
    rate = 0
    elapsed_str = "0:00:00"
    if sent_lines > 0 and os.path.exists(SENT_LOG):
        with open(SENT_LOG, 'r') as f:
            lines = [l.strip() for l in f if l.strip()]
        if len(lines) >= 2:
            try:
                first = datetime.fromisoformat(lines[0].split('|')[-1].strip())
                last = datetime.fromisoformat(lines[-1].split('|')[-1].strip())
                elapsed = (last - first).total_seconds()
                if elapsed > 0:
                    rate = sent_lines / elapsed * 3600
                elapsed_str = str(timedelta(seconds=int(elapsed)))
            except:
                pass
    
    # Error rate
    err_pct = (err_lines / max(sent_lines, 1)) * 100
    
    print(f"  ┌{'─'*56}┐")
    print(f"  │  📨  Sent:       {sent_lines:>6,} unique EINs: {sent_eins:>6,}          │")
    print(f"  │  ❌  Errors:     {err_lines:>6,} ({err_pct:.0f}% of sends)          │")
    print(f"  │  ⚡  Rate:       {rate:>6.0f}/hr across {elapsed_str}         │")
    print(f"  │  📁  Log dir:    {LOG_DIR}  │")
    print(f"  └{'─'*56}┘")
    print()

# ── Menu ────────────────────────────────────────────────────────

MENU_ITEMS = [
    ("1", "🚀  Start SES Sender", "turbo"),
    ("2", "📊  Live Status Monitor", "status-watch"),
    ("3", "📊  Quick Status Check", "status"),
    ("4", "📬  Check for Replies", "replies"),
    ("5", "📋  View Sent Log (last 10)", "sent-log"),
    ("6", "❌  View Error Log (last 10)", "error-log"),
    ("7", "📧  View Last 50 Sent Names Only", "sent-names"),
    ("8", "🔍  Search Sent for Foundation", "search-sent"),
    ("9", "✅  Verify Email Addresses (full)", "verify"),
    ("10", "✅  Verify Email Addresses (quick 100)", "verify-quick"),
    ("11", "📊  Verify Stats", "verify-stats"),
    ("12", "⏰  60-Day Follow-up (preview)", "followup"),
    ("13", "🧹  Clean Bad Addresses", "clean"),
    ("14", "☕  Exit", "exit"),
]

def show_menu():
    clear()
    header()
    show_summary()
    
    print(f"  {'─'*56}")
    print(f"   MENU")
    print(f"  {'─'*56}")
    for key, label, _ in MENU_ITEMS:
        print(f"    {key}.  {label}")
    print(f"  {'─'*56}")
    print()

# ── Command Dispatch ─────────────────────────────────────────────

def cmd_turbo():
    cmd = "python ses_foundation_sender.py --tier theology --workers 5 --turbo --resume"
    if sys.platform == "win32":
        cmd = f'$env:EMAIL_PASSWORD = "FlorenceFlamingo1!"; {cmd}'
    run(cmd, "Starting SES sender (turbo, 5 workers, resume enabled)")

def cmd_status_watch():
    run("python ses_status.py --watch", "Live status monitor (Ctrl+C to stop)")

def cmd_status():
    run("python ses_status.py", "Quick status check")

def cmd_replies():
    cmd = "python track_replies.py"
    if sys.platform == "win32":
        cmd = f'$env:EMAIL_PASSWORD = "FlorenceFlamingo1!"; {cmd}'
    run(cmd, "Scanning inbox for foundation replies")

def cmd_sent_log():
    """Show last 10 sent records using Python."""
    path = SENT_LOG
    if not os.path.exists(path):
        print("  No sent log found.")
        pause()
        return
    with open(path, 'r') as f:
        lines = f.readlines()
    print()
    for line in lines[-10:]:
        parts = line.strip().split('|')
        if len(parts) >= 3:
            print(f"  {parts[1][:50]:50s} | {parts[2]}")
    pause()

def cmd_error_log():
    """Show last 10 errors using Python."""
    path = ERROR_LOG
    if not os.path.exists(path):
        print("  No error log found.")
        pause()
        return
    with open(path, 'r') as f:
        lines = f.readlines()
    print()
    for line in lines[-10:]:
        parts = line.strip().split('|')
        if len(parts) >= 3:
            print(f"  {parts[1][:50]:50s} | {parts[3][:80]}")
    pause()

def cmd_sent_names():
    """Show last 50 sent foundation names."""
    path = SENT_LOG
    if not os.path.exists(path):
        print("  No sent log found.")
        pause()
        return
    with open(path, 'r') as f:
        lines = f.readlines()
    print()
    for line in lines[-50:]:
        parts = line.strip().split('|')
        if len(parts) >= 2:
            print(f"  {parts[1][:60]}")
    pause()

def cmd_search_sent():
    query = input("  Enter foundation name to search: ").strip().lower()
    if query:
        path = SENT_LOG
        if not os.path.exists(path):
            print("  No sent log found.")
            pause()
            return
        with open(path, 'r') as f:
            matches = [l for l in f if query in l.lower()]
        print()
        if matches:
            for line in matches:
                parts = line.strip().split('|')
                if len(parts) >= 3:
                    print(f"    {parts[1][:50]:50s} | {parts[2].strip()}")
        else:
            print("  No matches found.")
        pause()

def cmd_followup():
    cmd = "python follow_up_60day.py"
    if sys.platform == "win32":
        cmd = f'$env:EMAIL_PASSWORD = "FlorenceFlamingo1!"; {cmd}'
    run(cmd, "60-day follow-up preview (use --send to actually send)")

def cmd_verify():
    run("python verify_emails.py", "Verifying all email addresses via SMTP handshake")

def cmd_verify_quick():
    run("python verify_emails.py --quick", "Quick-checking first 100 addresses")

def cmd_verify_stats():
    run("python verify_emails.py --stats", "Verification stats")

def cmd_clean():
    print()
    print("  🧹 Clean bad addresses from enriched_contacts.csv?")
    print("  This removes addresses listed in bad_addresses.txt.")
    confirm = input("  Are you sure? (y/N): ").strip().lower()
    if confirm == 'y':
        bad_file = os.path.join(SCRIPT_DIR, "bad_addresses.txt")
        csv_file = os.path.join(SCRIPT_DIR, "enriched_contacts.csv")
        if os.path.exists(bad_file) and os.path.exists(csv_file):
            with open(bad_file, 'r') as f:
                bad = set(line.strip().lower() for line in f if line.strip())
            import csv
            rows = []
            removed = 0
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                for row in reader:
                    email = (row.get('EMAIL', '') or row.get('SCRAPED_EMAIL', '') or '').strip().lower()
                    if email in bad:
                        removed += 1
                    else:
                        rows.append(row)
            with open(csv_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            print(f"  ✅ Removed {removed} bad addresses. {len(rows)} remaining.")
        else:
            print("  No bad_addresses.txt or enriched_contacts.csv found.")
    else:
        print("  Skipped.")
    pause()

def cmd_exit():
    print("\n  Keep making it rain. 🌊\n")
    sys.exit(0)

DISPATCH = {
    "turbo": cmd_turbo,
    "status-watch": cmd_status_watch,
    "status": cmd_status,
    "replies": cmd_replies,
    "sent-log": cmd_sent_log,
    "error-log": cmd_error_log,
    "sent-names": cmd_sent_names,
    "search-sent": cmd_search_sent,
    "followup": cmd_followup,
    "verify": cmd_verify,
    "verify-quick": cmd_verify_quick,
    "verify-stats": cmd_verify_stats,
    "clean": cmd_clean,
    "exit": cmd_exit,
    "1": cmd_turbo,
    "2": cmd_status_watch,
    "3": cmd_status,
    "4": cmd_replies,
    "5": cmd_sent_log,
    "6": cmd_error_log,
    "7": cmd_sent_names,
    "8": cmd_search_sent,
    "9": cmd_verify,
    "10": cmd_verify_quick,
    "11": cmd_verify_stats,
    "12": cmd_followup,
    "13": cmd_clean,
    "14": cmd_exit,
}

# ── Main ─────────────────────────────────────────────────────────

def main():
    # Direct command mode
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd in DISPATCH:
            DISPATCH[cmd]()
        else:
            print(f"  Unknown command: {cmd}")
            print(f"  Available: {', '.join(k for k in DISPATCH.keys() if not k.isdigit())}")
        return

    # Interactive menu mode
    try:
        while True:
            show_menu()
            choice = input("  Enter choice [1-14]: ").strip()
            if choice in DISPATCH:
                DISPATCH[choice]()
            else:
                print("\n  Invalid choice.")
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n  Keep making it rain. 🌊\n")
        sys.exit(0)

if __name__ == '__main__':
    main()
