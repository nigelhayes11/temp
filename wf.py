import asyncio
from playwright.async_api import async_playwright

OUTPUT = "watchfty.m3u"
GROUP = "WATCHFTY LIVE"

TARGET_URLS = [
    "https://www.watchfooty.st",
    "https://www.watchfooty.top",
    "https://www.watchfooty.su",
]

async def run():
    m3u8_links = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        page = await context.new_page()

        def capture(req):
            url = req.url
            if ".m3u8" in url and "http" in url:
                m3u8_links.add(url)

        page.on("request", capture)

        for site in TARGET_URLS:
            try:
                await page.goto(site, timeout=15000)
                await page.wait_for_timeout(4000)
            except:
                continue

        await browser.close()

    if not m3u8_links:
        print("❌ M3U8 bulunamadı")
        return

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for i, link in enumerate(m3u8_links, 1):
            f.write(
