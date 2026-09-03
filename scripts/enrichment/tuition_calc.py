"""Calculate tuition breakdown."""
import urllib.request, json

url = 'https://api.exchangerate-api.com/v4/latest/CAD'
resp = urllib.request.urlopen(url, timeout=10)
data = json.loads(resp.read())
usd = data['rates']['USD']

cad = 30000
total = cad * usd
monthly = total / 12
daily = total / 365

print(f'1 CAD = {usd:.4f} USD')
print(f'30,000 CAD = ${total:,.0f} USD')
print()
print(f'Year:  ${total:,.0f}')
print(f'Month: ${monthly:,.0f}')
print(f'Week:  ${monthly/4:,.0f}')
print(f'Day:   ${daily:.0f}')
print()
print('What that looks like:')
print(f'  {int(total/25)} people giving $25  = ${total:,.0f}')
print(f'  {int(total/50)} people giving $50  = ${total:,.0f}')
print(f'  {int(total/100)} people giving $100 = ${total:,.0f}')
print(f'  {int(total/25/12)} sustainers at $25/mo = ${total:,.0f}/yr')
print(f'  {int(total/50/12)} sustainers at $50/mo = ${total:,.0f}/yr')
print()
print('Per month:')
print(f'  {int(monthly/25)} people x $25 = ${monthly:,.0f}')
print(f'  {int(monthly/50)} people x $50 = ${monthly:,.0f}')
print(f'  {int(monthly/100)} people x $100 = ${monthly:,.0f}')
