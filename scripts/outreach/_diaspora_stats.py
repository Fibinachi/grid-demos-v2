"""Diaspora stats for reference."""
import sqlite3
db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

print("=== DIASPORA QUICK STATS ===")
queries = [
    ("796 Chinese folk shrines in Thailand", "SELECT COUNT(*) FROM churches WHERE country='TH' AND (faith='Taoist' OR faith='Confucian' OR (faith='Other' AND tradition LIKE '%Chinese%' OR tradition LIKE '%Folk%'))"),
    ("5,242 Hindu temples in the US", "SELECT COUNT(*) FROM churches WHERE country='US' AND faith='Hindu'"),
    ("2,869 Turkish mosques in Germany", "SELECT COUNT(*) FROM churches WHERE country='DE' AND faith='Islam'"),
    ("906 Thai Buddhist temples in the US", "SELECT COUNT(*) FROM churches WHERE country='US' AND faith='Buddhist' AND tradition LIKE '%Theravada%'"),
    ("758 Chinese shrines in Malaysia", "SELECT COUNT(*) FROM churches WHERE country='MY' AND (faith='Taoist' OR faith='Confucian' OR (faith='Other' AND tradition LIKE '%Chinese%')))"),
    ("462 Hindu temples in Canada", "SELECT COUNT(*) FROM churches WHERE country='CA' AND faith='Hindu'"),
    ("456 Hindu temples in the UK", "SELECT COUNT(*) FROM churches WHERE country='GB' AND faith='Hindu'"),
    ("409 Vietnamese Buddhist temples in the US", "SELECT COUNT(*) FROM churches WHERE country='US' AND faith='Buddhist' AND tradition LIKE '%Vietnamese%'"),
    ("783 mosques in the Netherlands", "SELECT COUNT(*) FROM churches WHERE country='NL' AND faith='Islam'"),
    ("311 mosques in Austria", "SELECT COUNT(*) FROM churches WHERE country='AT' AND faith='Islam'"),
    ("2,788 mosques in the UK", "SELECT COUNT(*) FROM churches WHERE country='GB' AND faith='Islam'"),
    ("1,491 mosques in France", "SELECT COUNT(*) FROM churches WHERE country='FR' AND faith='Islam'"),
    ("1,636 Hindu temples in Malaysia", "SELECT COUNT(*) FROM churches WHERE country='MY' AND faith='Hindu'"),
    ("13,301 Hindu temples in China (!)", "SELECT COUNT(*) FROM churches WHERE country='CN' AND faith='Hindu'"),
    ("500 Sikh gurdwaras in the US", "SELECT COUNT(*) FROM churches WHERE country='US' AND faith='Sikh'"),
]
for label, sql in queries:
    n = db.execute(sql).fetchone()[0]
    print(f"  {label}: {n:,}")

db.close()
