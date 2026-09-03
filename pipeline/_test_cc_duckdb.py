"""Test DuckDB access to Common Crawl Parquet"""
import duckdb

con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")

# Configure S3 for anonymous access to CC public dataset
con.execute("SET s3_region='us-east-1'")
con.execute("SET s3_access_key_id=''")
con.execute("SET s3_secret_access_key=''")

# Try latest crawl
try:
    rs = con.execute("""
        SELECT url_host_registered_domain, url, page_title, fetch_status
        FROM read_parquet('s3://commoncrawl/cc-index/table/cc-main/warc/crawl=CC-MAIN-2025-22/*.parquet',
                           hive_partitioning=false)
        WHERE url_host_registered_domain = 'firstbaptistchurch.org'
        LIMIT 5
    """).fetchall()
    print(f"\nFound {len(rs)} pages from firstbaptistchurch.org:")
    for r in rs:
        print(f"  {r[0]} | {r[1][:60]} | title={r[2][:50] if r[2] else 'N/A'} | status={r[3]}")
except Exception as e:
    print(f"Query error: {e}")
    
    # Try without filter to see schema
    try:
        rs = con.execute("""
            DESCRIBE SELECT * FROM read_parquet(
                's3://commoncrawl/cc-index/table/cc-main/warc/crawl=CC-MAIN-2025-22/*.parquet',
                hive_partitioning=false
            ) LIMIT 0
        """).fetchall()
        print("Schema:")
        for r in rs:
            print(f"  {r[0]}: {r[1]}")
    except Exception as e2:
        print(f"Schema error: {e2}")

con.close()
