#!/usr/bin/env python3
"""Send SBC pitch to Amy Thompson via Hostinger SMTP."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = "smtp.hostinger.com"
SMTP_PORT = 587
SMTP_USER = "charles@columbiataxlawyer.com"
SMTP_PASS = "FlorenceFlamingo1!"

TO = "athompson@sbc.net"
FROM = "charles@columbiataxlawyer.com"

subject = "A data tool that could help SBC churches in high-poverty areas"

html_body = """<html><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<p>Hi Amy,</p>

<p>I've been building a national church database (385K records) cross-referenced against ACS poverty and income data, and thought your team at the EC might find this useful. It's designed to help denominations identify where their churches are serving in the highest-need areas — not as a critique, but as a practical tool for targeting revitalization, planting, and grant resources effectively.</p>

<p>Here's a sample: <strong>25 SBC churches in the highest-poverty ZIP codes in America</strong> — neighborhoods where the poverty rate exceeds 47% and median income is below $20,000:</p>

<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; font-size:12px; width:100%">
<tr style="background:#1a3a5c; color:white;">
<th>#</th><th>Church</th><th>City, State</th><th>ZIP Poverty</th><th>Med. Income</th>
</tr>
<tr><td>1</td><td>LAKE WASHINGTON FIRST BAPTIST CHURCH</td><td>Glen Allan, MS</td><td>57.9%</td><td>$19,194</td></tr>
<tr><td>2</td><td>RAY OF HOPE MINISTRIES</td><td>Cleveland, OH</td><td>57.4%</td><td>$19,247</td></tr>
<tr><td>3</td><td>KING'S CROSS CHURCH</td><td>Cleveland, OH</td><td>57.4%</td><td>$19,247</td></tr>
<tr><td>4</td><td>GATEWAY CHURCH DOWNTOWN CLEVELAND</td><td>Cleveland, OH</td><td>57.4%</td><td>$19,247</td></tr>
<tr><td>5</td><td>ORRVILLE</td><td>Orrville, AL</td><td>57.3%</td><td>$30,608</td></tr>
<tr><td>6</td><td>IGLESIA BAUTISTA DEL CENTRO</td><td>El Paso, TX</td><td>54.5%</td><td>$14,142</td></tr>
<tr><td>7</td><td>SAINT FRANCIS BAPTIST CHURCH</td><td>Saint Francis, AR</td><td>54.5%</td><td>$43,750</td></tr>
<tr><td>8</td><td>LA PRIMERA IGLESIA BAUTISTA</td><td>Toledo, OH</td><td>54.2%</td><td>$16,651</td></tr>
<tr><td>9</td><td>FIRST BAPTIST CHURCH OF MAGDALENA</td><td>Magdalena, NM</td><td>53.9%</td><td>$26,920</td></tr>
<tr><td>10</td><td>TURTLETOWN MISSIONARY BAPTIST CHURCH</td><td>Farner, TN</td><td>53.3%</td><td>$30,029</td></tr>
<tr><td>11</td><td>NEW ZION BAPTIST CHURCH</td><td>Farner, TN</td><td>53.3%</td><td>$30,029</td></tr>
<tr><td>12</td><td>ROSE HILL BAPTIST CHURCH</td><td>Gunnsion, MS</td><td>52.4%</td><td>$23,000</td></tr>
<tr><td>13</td><td>SECOND MISSIONARY BAPTIST CHURCH</td><td>Waco, TX</td><td>52.2%</td><td>$19,966</td></tr>
<tr><td>14</td><td>LAPLANT BAPTIST CHURCH</td><td>La Plant, SD</td><td>51.8%</td><td>$26,750</td></tr>
<tr><td>15</td><td>COTTON PLANT FIRST BAPTIST CHURCH</td><td>Cotton Plant, AR</td><td>51.5%</td><td>$17,063</td></tr>
<tr><td>16</td><td>LIVINGSTON BAPTIST CHURCH</td><td>Livingston, KY</td><td>50.9%</td><td>$23,621</td></tr>
<tr><td>17</td><td>PRIMERA IGLESIA GARCIASVILLE</td><td>Garciasville, TX</td><td>50.6%</td><td>$11,125</td></tr>
<tr><td>18</td><td>HOUSE OF HOPE MINISTRIES</td><td>Cleveland, OH</td><td>50.6%</td><td>$21,333</td></tr>
<tr><td>19</td><td>JESUS WAY BAPTIST CHURCH</td><td>Houston, TX</td><td>50.4%</td><td>$30,750</td></tr>
<tr><td>20</td><td>FIRST BAPTIST CHURCH OF MONROE</td><td>Monroe, OK</td><td>50.4%</td><td>$33,750</td></tr>
<tr><td>21</td><td>CHRIST'S COMMUNITY CHURCH</td><td>Memphis, TN</td><td>50.3%</td><td>$19,844</td></tr>
<tr><td>22</td><td>IGLESIA BAUTISTA LA HERMOSA</td><td>Presidio, TX</td><td>50.2%</td><td>$19,650</td></tr>
<tr><td>23</td><td>IDEAL BAPTIST CHURCH, INC.</td><td>Ideal, GA</td><td>50.2%</td><td>$24,539</td></tr>
<tr><td>24</td><td>WATERBURY BAPTIST MINISTRIES</td><td>Waterbury, CT</td><td>48.3%</td><td>$14,852</td></tr>
<tr><td>25</td><td>FIRST BAPTIST CHURCH ROSEDALE</td><td>Rosedale, MS</td><td>47.8%</td><td>$18,542</td></tr>
</table>

<p>And here are the <strong>25 SBC churches in South Carolina</strong> serving in the highest-poverty ZIPs:</p>

<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; font-size:12px; width:100%">
<tr style="background:#1a3a5c; color:white;">
<th>#</th><th>Church</th><th>City</th><th>ZIP Poverty</th><th>Med. Income</th>
</tr>
<tr><td>1</td><td>MAITIAN CHINESE BAPTIST CHURCH</td><td>Columbia</td><td>39.8%</td><td>$33,561</td></tr>
<tr><td>2</td><td>PALMETTO LIFE CHURCH</td><td>Columbia</td><td>39.8%</td><td>$33,561</td></tr>
<tr><td>3</td><td>BEAR SWAMP</td><td>Lake View</td><td>36.5%</td><td>$37,727</td></tr>
<tr><td>4</td><td>VILLAGE CHURCH OF PENDLETON</td><td>Clemson</td><td>36.3%</td><td>$50,348</td></tr>
<tr><td>5</td><td>ID CHURCH DOWNTOWN</td><td>Spartanburg</td><td>33.3%</td><td>$35,439</td></tr>
<tr><td>6</td><td>SPARTANBURG FIRST BAPTIST CHURCH</td><td>Spartanburg</td><td>33.3%</td><td>$35,439</td></tr>
<tr><td>7</td><td>GOVAN FIRST BAPTIST CHURCH</td><td>Olar</td><td>31.6%</td><td>$50,170</td></tr>
<tr><td>8</td><td>CITY OF REFUGE CHURCH</td><td>Columbia</td><td>28.8%</td><td>$39,015</td></tr>
<tr><td>9</td><td>GREATER FAITH UNITED BAPTIST CHURCH</td><td>Columbia</td><td>28.8%</td><td>$39,015</td></tr>
<tr><td>10</td><td>BERMUDA BAPTIST CHURCH</td><td>Dillon</td><td>28.7%</td><td>$42,835</td></tr>
<tr><td>11</td><td>ALLIANCE BAPTIST MISSION</td><td>Johnsonville</td><td>27.9%</td><td>$57,660</td></tr>
<tr><td>12</td><td>NORTHWOOD BAPTIST EAST BAY</td><td>Charleston</td><td>27.0%</td><td>$62,281</td></tr>
<tr><td>13</td><td>READY CHURCH</td><td>N Charleston</td><td>25.7%</td><td>$45,797</td></tr>
<tr><td>14</td><td>COMUNIDADE BATISTA DE CHARLESTON</td><td>N Charleston</td><td>25.7%</td><td>$45,797</td></tr>
<tr><td>15</td><td>BROCK'S MILL BAPTIST CHURCH</td><td>Cheraw</td><td>24.9%</td><td>$40,724</td></tr>
<tr><td>16</td><td>MOUNT ZION, HAMER</td><td>Hamer</td><td>23.6%</td><td>$44,413</td></tr>
<tr><td>17</td><td>FIRE ON THE MOUNTAIN CHURCH</td><td>Greenville</td><td>23.4%</td><td>$45,291</td></tr>
<tr><td>18</td><td>CHRIST THE REDEEMER</td><td>Greenville</td><td>23.4%</td><td>$45,291</td></tr>
<tr><td>19</td><td>HILLCREST CHURCH</td><td>Gaston</td><td>22.6%</td><td>$50,534</td></tr>
<tr><td>20</td><td>PINE PLEASANT BAPTIST CHURCH</td><td>Saluda</td><td>22.5%</td><td>$39,607</td></tr>
<tr><td>21</td><td>GREELEYVILLE BAPTIST CHURCH</td><td>Greeleyville</td><td>21.9%</td><td>$42,197</td></tr>
<tr><td>22</td><td>LOVE SPRINGS BAPTIST CHURCH</td><td>Cowpens</td><td>21.9%</td><td>$53,762</td></tr>
<tr><td>23</td><td>DRAYTONVILLE BAPTIST CHURCH</td><td>Gaffney</td><td>21.9%</td><td>$40,242</td></tr>
<tr><td>24</td><td>EAST GAFFNEY BAPTIST CHURCH</td><td>Gaffney</td><td>21.9%</td><td>$40,242</td></tr>
<tr><td>25</td><td>ELKO BAPTIST CHURCH</td><td>Williston</td><td>21.6%</td><td>$43,934</td></tr>
</table>

<p>Altogether, <strong>4,940 SBC directory churches (21% of the total)</strong> are in ZIPs where poverty exceeds 20% — these are churches already on the front lines in hard places, and the data can help tell that story and target support.</p>

<p>Currently this is ZIP-level analysis because the SBC directory doesn't include street addresses (which is totally normal for a directory). If addresses were available, I could drill down to the <strong>census tract level</strong> — think neighborhood-sized, typically 4,000-8,000 people — which captures the kind of micro-targeting that makes grant applications and strategic plans really compelling. I can also layer in food access, school performance, broadband availability, FEMA risk data, or anything else useful.</p>

<p>This is a service I'm offering — no obligation, no pitch beyond this email. If it's useful, I'd be glad to run specific queries for your team. If not, no hard feelings at all.</p>

<p>Best,<br>Charles Prescott</p>
</body></html>"""


text_body = """Hi Amy,

I've been building a national church database (385K records) cross-referenced against ACS poverty and income data, and thought your team at the EC might find this useful. It's designed to help denominations identify where their churches are serving in the highest-need areas — not as a critique, but as a practical tool for targeting revitalization, planting, and grant resources effectively.

Here's a sample: 25 SBC churches in the highest-poverty ZIP codes in America — neighborhoods where the poverty rate exceeds 47% and median income is below $20,000:

 1. LAKE WASHINGTON FIRST BAPTIST CHURCH — Glen Allan, MS — 57.9% poverty, $19,194 med. income
 2. RAY OF HOPE MINISTRIES — Cleveland, OH — 57.4% poverty, $19,247
 3. KING'S CROSS CHURCH — Cleveland, OH — 57.4% poverty, $19,247
 4. GATEWAY CHURCH DOWNTOWN CLEVELAND — Cleveland, OH — 57.4% poverty, $19,247
 5. ORRVILLE — Orrville, AL — 57.3% poverty, $30,608
 6. IGLESIA BAUTISTA DEL CENTRO — El Paso, TX — 54.5% poverty, $14,142
 7. SAINT FRANCIS BAPTIST CHURCH — Saint Francis, AR — 54.5% poverty, $43,750
 8. LA PRIMERA IGLESIA BAUTISTA — Toledo, OH — 54.2% poverty, $16,651
 9. FIRST BAPTIST CHURCH OF MAGDALENA — Magdalena, NM — 53.9% poverty, $26,920
10. TURTLETOWN MISSIONARY BAPTIST CHURCH — Farner, TN — 53.3% poverty, $30,029
11. NEW ZION BAPTIST CHURCH — Farner, TN — 53.3% poverty, $30,029
12. ROSE HILL BAPTIST CHURCH — Gunnsion, MS — 52.4% poverty, $23,000
13. SECOND MISSIONARY BAPTIST CHURCH — Waco, TX — 52.2% poverty, $19,966
14. LAPLANT BAPTIST CHURCH — La Plant, SD — 51.8% poverty, $26,750
15. COTTON PLANT FIRST BAPTIST CHURCH — Cotton Plant, AR — 51.5% poverty, $17,063
16. LIVINGSTON BAPTIST CHURCH — Livingston, KY — 50.9% poverty, $23,621
17. PRIMERA IGLESIA GARCIASVILLE — Garciasville, TX — 50.6% poverty, $11,125
18. HOUSE OF HOPE MINISTRIES — Cleveland, OH — 50.6% poverty, $21,333
19. JESUS WAY BAPTIST CHURCH — Houston, TX — 50.4% poverty, $30,750
20. FIRST BAPTIST CHURCH OF MONROE — Monroe, OK — 50.4% poverty, $33,750
21. CHRIST'S COMMUNITY CHURCH — Memphis, TN — 50.3% poverty, $19,844
22. IGLESIA BAUTISTA LA HERMOSA — Presidio, TX — 50.2% poverty, $19,650
23. IDEAL BAPTIST CHURCH, INC. — Ideal, GA — 50.2% poverty, $24,539
24. WATERBURY BAPTIST MINISTRIES — Waterbury, CT — 48.3% poverty, $14,852
25. FIRST BAPTIST CHURCH ROSEDALE — Rosedale, MS — 47.8% poverty, $18,542

And here are the 25 SBC churches in South Carolina serving in the highest-poverty ZIPs:

 1. MAITIAN CHINESE BAPTIST CHURCH — Columbia — 39.8% poverty, $33,561
 2. PALMETTO LIFE CHURCH — Columbia — 39.8% poverty, $33,561
 3. BEAR SWAMP — Lake View — 36.5% poverty, $37,727
 4. VILLAGE CHURCH OF PENDLETON — Clemson — 36.3% poverty, $50,348
 5. ID CHURCH DOWNTOWN — Spartanburg — 33.3% poverty, $35,439
 6. SPARTANBURG FIRST BAPTIST CHURCH — Spartanburg — 33.3% poverty, $35,439
 7. GOVAN FIRST BAPTIST CHURCH — Olar — 31.6% poverty, $50,170
 8. CITY OF REFUGE CHURCH — Columbia — 28.8% poverty, $39,015
 9. GREATER FAITH UNITED BAPTIST CHURCH — Columbia — 28.8% poverty, $39,015
10. BERMUDA BAPTIST CHURCH — Dillon — 28.7% poverty, $42,835
11. ALLIANCE BAPTIST MISSION — Johnsonville — 27.9% poverty, $57,660
12. NORTHWOOD BAPTIST EAST BAY — Charleston — 27.0% poverty, $62,281
13. READY CHURCH — N Charleston — 25.7% poverty, $45,797
14. COMUNIDADE BATISTA DE CHARLESTON — N Charleston — 25.7% poverty, $45,797
15. BROCK'S MILL BAPTIST CHURCH — Cheraw — 24.9% poverty, $40,724
16. MOUNT ZION, HAMER — Hamer — 23.6% poverty, $44,413
17. FIRE ON THE MOUNTAIN CHURCH — Greenville — 23.4% poverty, $45,291
18. CHRIST THE REDEEMER — Greenville — 23.4% poverty, $45,291
19. HILLCREST CHURCH — Gaston — 22.6% poverty, $50,534
20. PINE PLEASANT BAPTIST CHURCH — Saluda — 22.5% poverty, $39,607
21. GREELEYVILLE BAPTIST CHURCH — Greeleyville — 21.9% poverty, $42,197
22. LOVE SPRINGS BAPTIST CHURCH — Cowpens — 21.9% poverty, $53,762
23. DRAYTONVILLE BAPTIST CHURCH — Gaffney — 21.9% poverty, $40,242
24. EAST GAFFNEY BAPTIST CHURCH — Gaffney — 21.9% poverty, $40,242
25. ELKO BAPTIST CHURCH — Williston — 21.6% poverty, $43,934

Altogether, 4,940 SBC directory churches (21% of the total) are in ZIPs where poverty exceeds 20% — these are churches already on the front lines in hard places, and the data can help tell that story and target support.

Currently this is ZIP-level analysis because the SBC directory doesn't include street addresses (which is totally normal for a directory). If addresses were available, I could drill down to the census tract level — neighborhood-sized — which captures the kind of micro-targeting that makes grant applications and strategic plans really compelling.

This is a service I'm offering — no obligation, no pitch beyond this email. If it's useful, I'd be glad to run specific queries for your team. If not, no hard feelings at all.

Best,
Charles Prescott"""


msg = MIMEMultipart('alternative')
msg['Subject'] = subject
msg['From'] = FROM
msg['To'] = TO
msg.attach(MIMEText(text_body, 'plain'))
msg.attach(MIMEText(html_body, 'html'))

print(f"Connecting to {SMTP_HOST}:{SMTP_PORT}...")
with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
    s.starttls()
    s.login(SMTP_USER, SMTP_PASS)
    s.send_message(msg)
    print(f"Sent! From {FROM} -> {TO}")
    print(f"Subject: {subject}")
