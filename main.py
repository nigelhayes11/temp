import asyncio
import json
import re
from playwright.async_api import async_playwright

OUTPUT_JSON = "watchfty.json"
BASE_URL = "https://www.watchfooty.st"

async def run():
    results = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        await page.goto(BASE_URL, timeout=30000)
        await page.wait_for_timeout(3000)

        requests = []

        def capture(req):
            if ".m3u8" in req.url:
                requests.append(req.url)

        page.on("request", capture)

        await page.wait_for_timeout(8000)

        for i, url in enumerate(set(requests), start=1):
            results[f"WatchFTY {i}"] = {
                "url": url,
                "logo": "",
                "group": "WATCHFTY LIVE"
            }

        await browser.close()

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("JSON hazır:", len(results))

asyncio.run(run())
