"""
SES Sender Status Monitor
=========================
Displays a live-updating status bar for the SES foundation sender.
Run this in a separate terminal while the sender runs.

Usage:
  python ses_status.py          # One-time check
  python ses_status.py --watch  # Live-updating status bar
"""

import os
import sys
import time
import json
from datetime import datetime, timedelta

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ses_logs")
SENT_LOG = os.path.join(LOG_DIR, "ses_sent.txt")
ERROR_LOG = os.path.join(LOG_DIR, "ses_errors.txt")

def get_status():
    """Get current sending stats."""
    sent = 0
    if os.path.exists(SENT_LOG):
        with open(SENT_LOG, 'r') as f:
            lines = [l for l in f if l.strip()]
            sent = len(lines)
            first_time = None
            last_time = None
            if lines:
                try:
                    first_time = datetime.fromisoformat(lines[0].split('|')[-1].strip())
                    last_time = datetime.fromisoformat(lines[-1].split('|')[-1].strip())
                except:
                    pass
    
    errors = 0
    if os.path.exists(ERROR_LOG):
        with open(ERROR_LOG, 'r') as f:
            errors = sum(1 for l in f if l.strip())
    
    return sent, errors, first_time, last_time


def format_bar(pct, width=30):
    """Render a text progress bar."""
    filled = int(width * pct / 100)
    bar = '█' * filled + '░' * (width - filled)
    return bar


def main():
    watch = '--watch' in sys.argv
    
    TARGET = 25860  # Total targets from the turbo launch
    
    if watch:
        print("\n" + "=" * 70)
        print("  📡 SES SENDER STATUS MONITOR  (Ctrl+C to stop)")
        print("=" * 70)
        print()
        
        try:
            while True:
                sent, errors, first, last = get_status()
                
                elapsed = 0
                rate = 0
                eta = "N/A"
                
                if sent > 0 and first and last:
                    elapsed = (datetime.now() - first).total_seconds()
                    if elapsed > 0:
                        rate = sent / elapsed * 3600
                    
                    if rate > 0:
                        remaining = TARGET - sent
                        eta_sec = remaining / rate * 3600
                        eta = str(timedelta(seconds=int(eta_sec)))
                
                pct = min(sent / TARGET * 100, 100) if TARGET > 0 else 0
                bar = format_bar(pct)
                
                # Clear previous lines and redraw
                sys.stdout.write('\033[2J\033[H')  # Clear screen
                
                print(f"  ╔═══ SES Foundation Sender ──── {'🟢 RUNNING' if rate > 0 else '🟡 STARTING'} ")
                print(f"  ║")
                print(f"  ║  {bar}  {pct:.1f}%")
                print(f"  ║")
                print(f"  ║  📨 Sent:     {sent:>6,} / {TARGET:,}")
                print(f"  ║  ❌ Errors:   {errors:>6,}  ({'%.1f' % (errors/max(sent,1)*100)}% failure rate)")
                print(f"  ║  ⚡ Rate:     {rate:>6.0f} / hour")
                print(f"  ║  ⏱️  Elapsed:  {str(timedelta(seconds=int(elapsed)))}")
                print(f"  ║  ⏳ ETA:      {eta}")
                print(f"  ║")
                
                if sent > 0:
                    success_rate = (1 - errors / max(sent, 1)) * 100
                    if success_rate > 90:
                        print(f"  ║  ✅ Delivery rate: {success_rate:.0f}% — looking good!")
                    elif success_rate > 70:
                        print(f"  ║  ⚠️  Delivery rate: {success_rate:.0f}% — some bounces")
                    else:
                        print(f"  ║  🔴 Delivery rate: {success_rate:.0f}% — check error log")
                
                print(f"  ║")
                print(f"  ║  Logs: {LOG_DIR}")
                print(f"  ╚═ Ctrl+C to stop monitoring ═")
                print()
                
                sys.stdout.flush()
                time.sleep(5)
                
        except KeyboardInterrupt:
            print("\n  Monitoring stopped.\n")
    else:
        # One-time status
        sent, errors, first, last = get_status()
        elapsed = 0
        rate = 0
        if sent > 0 and first and last:
            elapsed = (datetime.now() - first).total_seconds()
            if elapsed > 0:
                rate = sent / elapsed * 3600
        
        pct = min(sent / TARGET * 100, 100) if TARGET > 0 else 0
        bar = format_bar(pct)
        
        print()
        print(f"  {bar}  {pct:.1f}%")
        print(f"  📨 {sent:,} sent | ❌ {errors:,} errors | ⚡ {rate:.0f}/hr")
        print(f"  ⏱️  {str(timedelta(seconds=int(elapsed)))} elapsed | ETA: {str(timedelta(seconds=int((TARGET-sent)/rate*3600))) if rate > 0 else 'N/A'}")
        print()


if __name__ == '__main__':
    main()
