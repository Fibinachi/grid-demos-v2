"""Send remaining targets from failed_targets.txt and batch3."""
import smtplib, ssl, os, re, sys, time, random

PASS = os.environ.get("EMAIL_PASSWORD")
if not PASS:
    print("ERROR: EMAIL_PASSWORD not set"); sys.exit(1)

SENDER = "charles@columbiataxlawyer.com"

STORY = "I am a 44-year-old US citizen, father of three (two autistic), Rutgers Law JD (David Delgones Award), Alabama LLM, Mensa-qualified WAIS-III 143. Seeking theological studies at Trinity College, U of T. Income ~$55K, no federal loan eligibility. Father 100% VA disabled. Self-employed SC attorney, CLE instructor, founding director Midlands Light Opera Society, church formation attorney, founded health/cancer nonprofits, IMDb credit."

def send_email(to, subj, body):
    try:
        msg = "From: %s\r\nTo: %s\r\nSubject: %s\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n%s" % (SENDER, to, subj, body)
        s = smtplib.SMTP("smtp.hostinger.com", 587, timeout=30)
        s.ehlo()
        s.starttls(context=ssl.create_default_context())
        s.ehlo()
        s.login(SENDER, PASS)
        s.sendmail(SENDER, to, msg.encode("utf-8"))
        s.quit()
        return True
    except:
        return False

# Load failed_targets
with open("failed_targets.txt") as f:
    failed = [l.strip() for l in f if l.strip() and "@" in l]

print("Failed targets: %d" % len(failed))

# Send in batches of 50
batch_size = 50
total_sent = 0
total_failed = 0

for batch_num in range(0, len(failed), batch_size):
    batch = failed[batch_num:batch_num + batch_size]
    sent = 0
    start_time = time.time()
    
    for i, email in enumerate(batch, 1):
        domain = email.split("@")[1].split(".")[0].title() if "@" in email else "Foundation"
        subj = "Inquiry - Scholarship Opportunities for Theological Studies"
        body = "Dear %s,\n\n%s\n\nPlease advise on any scholarship opportunities for which I might be eligible.\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542" % (domain, STORY)
        
        if send_email(email, subj, body):
            sent += 1
            sys.stdout.write(".")
        else:
            sys.stdout.write("x")
        sys.stdout.flush()
        
        # Random 2-5 minute delay between sends to avoid bulk detection
        if i < len(batch):
            delay = random.randint(120, 300)
            mins = delay // 60
            secs = delay % 60
            sys.stdout.write(" [~%dm wait]" % mins)
            sys.stdout.flush()
            time.sleep(delay)
        
        # Progress update every 5 emails
        if i % 5 == 0:
            elapsed = time.time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            eta = (len(batch) - i) / rate if rate > 0 else 0
            eta_m = eta / 60
            eta_h = eta_m / 60
            print(" [%d/%d | %d sent | ETA: %.1fh]" % (i, len(batch), sent, eta_h))
    
    total_sent += sent
    total_failed += len(batch) - sent
    print("")  # newline after batch
    print("Batch %d complete: %d sent, %d failed | Overall: %d/%d" % (
        batch_num//batch_size + 1, sent, len(batch)-sent, total_sent, batch_num + len(batch)))

print("\n\nDONE: %d sent, %d failed out of %d" % (total_sent, total_failed, len(failed)))
