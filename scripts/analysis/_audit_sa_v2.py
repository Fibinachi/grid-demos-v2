"""Quick audit of SA classification v2."""
import sqlite3, sys
sys.path.insert(0, 'e:\\grid\\scripts\\db_maintenance')
from standardize_salvation_army import classify_sa_name

db = sqlite3.connect('E:\\grid\\churches.db')

# Check specific problematic patterns
checks = [
    "Salvation Army Prayer Hall",
    "Salvation Army Hall",
    "Salvation Army Central Hall",
    "Salvation Army Regent Hall",
    "Salvation Army Chapel",
    "Salvation Army Chapel Rideau Heights",
    "SALVATION ARMY THRIFT STORE",
    "Salvation Army Employment Plus",
    "Salvation Army Church and Social Services",
    "Salvation Army Territorial Headquarters",
    "Salvation Army Divisional Headquarters",
    "Fiji Division The Salvation Army",
    "Salvation Army Church",
    "Salvation Army Church and Community Centre",
    "GOVERNING COUNCIL OF THE SALVATION ARMY IN CANADA/CONSEIL DE DIRECTION DE L'ARMÉE DU SALUT DU CANADA",
    "Ringwood Salvation Army Citadel Band",
    "ETOBICOKE TEMPLE BAND OF THE SALVATION ARMY",
    "Cradley Heath Songsters of The Salvation Army",
    "CANADIAN STAFF SONGSTERS OF THE SALVATION ARMY",
    "Salvation Army - NazCorps",
    "Salvation Army San Jose Corps",
    "Salvation Army",
    "salvation army",
    "Armée du Salut",
    "Heilsarmee",
    "Ejército de Salvación",
    "Exército de Salvação",
    "Frelsesarmeen",
    "Fr\u00e4lsningsarm\u00e9n",
    "Pelastusarmeija",
    "Salvation Army - Bedford Congress Hall",
    "SALVATION ARMY ARC",
    "SALVATION ARMY LONG BEACH RED SHIELD",
]

print(f'{"TYPE":20s} {"NORMALIZED":60s} {"DETAIL":30s}')
print('-' * 110)
for name in checks:
    sa_type, detail, normalized, extracted = classify_sa_name(name, '', '')
    print(f'{sa_type:20s} {normalized:60s} {detail:30s}')

db.close()
