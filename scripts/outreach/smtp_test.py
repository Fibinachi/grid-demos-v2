import smtplib, ssl, os, socket
socket.setdefaulttimeout(10)
PASS = os.environ.get("EMAIL_PASSWORD")
if not PASS:
    print("❌ EMAIL_PASSWORD not set"); exit(1)
for port in [587, 465]:
    try:
        if port == 587:
            with smtplib.SMTP("smtp.hostinger.com", port) as s:
                s.ehlo()
                ctx = ssl.create_default_context()
                s.starttls(context=ctx)
                s.ehlo()
                s.login("charles@columbiataxlawyer.com", PASS)
                print(f"✅ Port {port} connected! SMTP is clear.")
        else:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL("smtp.hostinger.com", port, context=ctx) as s:
                s.login("charles@columbiataxlawyer.com", PASS)
                print(f"✅ Port {port} connected! SMTP is clear.")
        break
    except Exception as e:
        print(f"❌ Port {port}: {e}")
else:
    print("❌ All ports blocked — SMTP still down")
