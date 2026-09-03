"""Download FCC files via Playwright with persistent Chrome profile (cookies survive restarts)."""
import asyncio, os, shutil
from playwright.async_api import async_playwright

FCC_FILES = [
    "https://transition.fcc.gov/ftp/Bureaus/MB/Databases/fm_fac.zip",
    "https://transition.fcc.gov/ftp/Bureaus/MB/Databases/lpfm_fac.zip",
    "https://transition.fcc.gov/ftp/Bureaus/MB/Databases/am_fac.zip",
    "https://transition.fcc.gov/ftp/Bureaus/MB/Databases/fm_tv_fac.zip",
]
OUT_DIR = "E:/grid/data/fcc"
USER_DATA = "E:/grid/data/fcc/chrome_profile"

async def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    
    async with async_playwright() as p:
        # Persistent context — cookies, localStorage, everything saved to USER_DATA
        context = await p.chromium.launch_persistent_context(
            USER_DATA,
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            args=["--disable-blink-features=AutomationControlled"],
            accept_downloads=True,
        )
        
        # First visit FCC to get cookies
        page = await context.new_page()
        print("Visiting FCC to establish session...", flush=True)
        await page.goto("https://transition.fcc.gov/ftp/Bureaus/MB/Databases/", timeout=30000)
        await page.wait_for_timeout(2000)
        print(f"  Cookies: {len(await context.cookies())}", flush=True)
        
        for url in FCC_FILES:
            name = url.split("/")[-1]
            out_path = os.path.join(OUT_DIR, name)
            
            if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
                print(f"  SKIP {name} — already downloaded ({os.path.getsize(out_path):,} bytes)", flush=True)
                continue
            
            print(f"  Downloading {name}...", end=" ", flush=True)
            try:
                async with page.expect_download(timeout=180000) as download_info:
                    await page.evaluate(f"window.location.href = '{url}'")
                download = await download_info.value
                await download.save_as(out_path)
                size = os.path.getsize(out_path)
                print(f"OK {size:,} bytes", flush=True)
            except Exception as e:
                print(f"FAILED: {e}", flush=True)
        
        await context.close()
    
    # Summary
    print("\nFiles:", flush=True)
    for f in sorted(os.listdir(OUT_DIR)):
        if f.endswith(".zip"):
            sz = os.path.getsize(os.path.join(OUT_DIR, f))
            print(f"  {f}: {sz:,} bytes ({sz/1024:.0f} KB)", flush=True)

asyncio.run(main())
