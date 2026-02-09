import asyncio
from urllib.parse import urljoin

from playwright.async_api import async_playwright
from selectolax.parser import HTMLParser

BASE_URL = "https://sport9.ru/"
OUT_FILE = "spr9.m3u"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

async def get_live_events(html: str):
    soup = HTMLParser(html)
    events = []

    for card in soup.css("a.match-card"):
        badge = card.css_first(".live-badge")
        if not badge or badge.text(strip=True) != "Live":
            continue

        t1 = card.css_first(".team1 .team-name")
        t2 = card.css_first(".team2 .team-name")

        if not t1 or not t2:
            continue

        name = f"{t1.text(strip=True)} vs {t2.text(strip=True)}"
        href = card.attributes.get("href")
        if not href:
            continue

        events.append((name, urljoin(BASE_URL, href)))

    return events


async def extract_m3u8(browser, url):
    page = await browser.new_page(user_agent=UA)
    m3u8_url = None

    async def on_response(resp):
        nonlocal m3u8_url
        if ".m3u8" in resp.url:
            m3u8_url = resp.url

    page.on("response", on_response)

    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(5)
    finally:
        await page.close()

    return m3u8_url


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        page = await browser.new_page(user_agent=UA)
        await page.goto(BASE_URL, wait_until="networkidle")
        html = await page.content()
        await page.close()

        events = await get_live_events(html)

        lines = ["#EXTM3U"]

        for name, link in events:
            m3u8 = await extract_m3u8(browser, link)
            if not m3u8:
                continue

            lines.append(
                f'#EXTINF:-1 group-title="SPORT9",{name}'
            )
            lines.append(m3u8)

        await browser.close()

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())
