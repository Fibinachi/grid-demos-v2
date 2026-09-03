"""Test Chromium on EC2"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--no-sandbox"])
    print("CHROMIUM OK version=" + b.version)
    b.close()
