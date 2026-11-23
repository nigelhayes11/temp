import asyncio
from playwright.async_api import async_playwright

BASE_URL = "https://beyazelma78.com/"
OUTPUT_M3U = "beyazelma.m3u"

async def scrape_streams():
    channels = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Canlı Kanallar sekmesine veya ana sayfaya git
        await page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        # Sayfadaki "İzle" veya kanal bağlantılarını topla
        links = await page.eval_on_selector_all(
            "a[href]",
            """els => els.map(e => ({text: e.innerText.trim(), href: e.href}))"""
        )

        target_links = []
        seen = set()
        for item in links:
            href = item["href"]
            text = " ".join(item["text"].split())
            if BASE_URL in href and href not in seen and href != BASE_URL:
                if any(k in href.lower() for k in ["izle", "kanal", "mac", "tv", "stream", "watch"]) or len(text) > 2:
                    seen.add(href)
                    target_links.append((text or href.split("/")[-1], href))

        print(f"Bulunan alt sayfa sayısı: {len(target_links)}")

        # Her kanal/maç sayfasında ağ trafiğindeki .m3u8 isteğini dinle
        for title, url in target_links[:25]:
            found_m3u8 = []

            def handle_request(req):
                if ".m3u8" in req.url and req.url not in found_m3u8:
                    found_m3u8.append(req.url)

            page.on("request", handle_request)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_timeout(4000)
            except Exception:
                pass
            page.remove_listener("request", handle_request)

            if found_m3u8:
                print(f"[+] Yakalandı: {title} -> {found_m3u8}")
                channels.append((title, found_m3u8))

        await browser.close()

    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for name, stream_url in channels:
            f.write(f'#EXTINF:-1 group-title="BeyazElma",{name}\n')
            f.write(f"#EXTVLCOPT:http-referrer={BASE_URL}\n")
            f.write(f"{stream_url}\n")

    print(f"Toplam kaydedilen kanal: {len(channels)}")

if __name__ == "__main__":
    asyncio.run(scrape_streams())
