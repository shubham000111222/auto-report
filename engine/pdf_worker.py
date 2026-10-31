import sys
from playwright.sync_api import sync_playwright

src, dst = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("file:///" + src.replace("\\", "/"), wait_until="networkidle")
    page.wait_for_timeout(1000)  # let Plotly finish drawing
    page.pdf(path=dst, format="A4", print_background=True, margin={"top": "15mm", "bottom": "15mm"})
    browser.close()
