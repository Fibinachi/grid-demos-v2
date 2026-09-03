import smtplib, ssl
context = ssl.create_default_context()
s = smtplib.SMTP('email-smtp.us-east-1.amazonaws.com', 587, timeout=15)
s.starttls(context=context)
s.login('AKIASKQS5JXODSJERNES', 'BCRaP22/Crmx5/SBb63vMJL3O2Tvm1oxwh+hgPPhW3xv')
msg = 'From: Charles Prescott <charles@columbiataxlawyer.com>\nTo: info@gatesfoundation.org\nSubject: EC2 Test\n\nHello from AWS server'
s.sendmail('charles@columbiataxlawyer.com', 'info@gatesfoundation.org', msg.encode('utf-8'))
s.quit()
print('SES_EC2_OK')
