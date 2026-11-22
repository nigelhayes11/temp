import asyncio
import re
import sys
from urllib.parse import urljoin
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

BASE_URL = "https://streamseast.dad"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
CONCURRENCY = 8  # Aynı anda taranacak maksimum sekme sayısı

SPORTS = [
    "NBA",
    # "NFL",
    "Soccer",
    # "MMA",
    # "Boxing",
    # "F1",
    # "MLB",
    # "NHL",
]

SPORT_ICONS = {
    "NBA": {
        "emoji": "🏀",
        "logo": "https://espncdn.com",
    },
    "Soccer": {
        "emoji": "⚽",
        "logo": "https://flaticon.com",
    },
}


def is_eligible_match(sport: str, card_text: str) -> bool:
    upper_text = card_text.upper()
    tokens = upper_text.split()

    # Biten veya ertelenen maçları ele
    if any(w in tokens for w in ["FT", "FINISHED", "AET", "PEN", "POSTPONED", "CANC"]):
        return False

    # NBA için bitmemiş tüm maçları kontrol et
    if sport.upper() == "NBA":
        return True

    # Diğer sporlarda: LIVE, devre arası, dakika (45') VEYA saat yazmıyorsa canlı kabul et
    if "LIVE" in tokens or "HT" in tokens or re.search(r"\b\d{1,3}(\+\d+)?'", upper_text):
        return True

    if not re.search(r"\b\d{1,2}:\d{2}\b", upper_text):
        return True

    return False



async def get_event_links(page) -> list[dict]:
    """Kriterlere uyan maç linklerini toplar."""
    events = []
    seen_links = set()

    for sport in SPORTS:
        sport_url = urljoin(BASE_URL, sport.lower())
        print(f"📡 {sport} maçları taranıyor: {sport_url}")
        try:
            await page.goto(sport_url, timeout=15000, wait_until="domcontentloaded")
            await page.wait_for_timeout(1200)

            match_elements = await page.query_selector_all("a.matches")
            for el in match_elements:
                card_text = await el.inner_text()
                if not is_eligible_match(sport, card_text):
                    continue

                href = await el.get_attribute("href")
                if not href:
                    continue

                full_link = urljoin(BASE_URL, href)
                if full_link not in seen_links:
                    seen_links.add(full_link)
                    events.append({"sport": sport, "link": full_link})

        except Exception as e:
            print(f"⚠️ {sport} sayfası taranırken hata: {e}")

    return events


async def extract_m3u8_from_event(semaphore, context, event: dict) -> dict | None:
    """Maç sayfasına girer, oynatıcı aktifse M3U8 linkini yakalar."""
    async with semaphore:
        page = await context.new_page()
        captured_m3u8 = []

        def handle_request(request):
            req_url = request.url
            if ".m3u8" in req_url.lower() and "indianservers" not in req_url.lower():
                if not captured_m3u8:
                    captured_m3u8.append(req_url)

        page.on("request", handle_request)
        event_name = "Canlı Yayın"

        try:
            await page.goto(event["link"], timeout=10000, wait_until="domcontentloaded")

            title_el = await page.query_selector("h1.match-head")
            if title_el:
                event_name = (await title_el.inner_text()).strip()

            # Oynatıcı iframe'i yoksa yayın henüz sisteme yüklenmemiştir
            iframe_el = await page.wait_for_selector("iframe.embed-responsive-item", timeout=3000)
            ifr_src = await iframe_el.get_attribute("src") if iframe_el else None
            if not ifr_src:
                return None

            await page.goto(urljoin(BASE_URL, ifr_src), timeout=8000, wait_until="domcontentloaded")

            # Oynat butonuna tıkla
            try:
                play_btn = page.locator(".vjs-big-play-button").first
                await play_btn.dblclick(force=True, timeout=1500)
            except PlaywrightTimeoutError:
                pass

            # M3U8 akışı yakalanana kadar en fazla 4 saniye bekle
            for _ in range(8):
                if captured_m3u8:
                    break
                await page.wait_for_timeout(500)

            if captured_m3u8:
                print(f"✅ Eklendi: [{event['sport']}] {event_name}")
                return {
                    "name": event_name,
                    "sport": event["sport"],
                    "url": captured_m3u8[0],
                }
            else:
                print(f"⏳ Yayın akışı henüz aktif değil: [{event['sport']}] {event_name}")
                return None

        except Exception:
            return None
        finally:
            await page.close()


def save_outputs(streams: list[dict], m3u_filename: str = "nba.m3u"):
    """Toplanan yayınları M3U dosyası olarak kaydeder."""
    with open(m3u_filename, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for s in streams:
            info = SPORT_ICONS.get(s["sport"], {"emoji": "📺", "logo": ""})
            title = f"{info['emoji']} [{s['sport']}] {s['name']}"
            f.write(
                f'#EXTINF:-1 tvg-name="{title}" tvg-logo="{info["logo"]}" '
                f'group-title="🏀 NBA+SOCCER LİVE ⚽",{title}\n'
            )
            f.write(f"#EXTVLCOPT:http-user-agent={USER_AGENT}\n")
            f.write(f"#EXTVLCOPT:http-referrer={BASE_URL}/\n")
            f.write(f"{s['url']}\n")

    print(f"\n🎉 İşlem tamamlandı! {len(streams)} yayın '{m3u_filename}' dosyasına kaydedildi.")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)

        await context.route(
            "**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}",
            lambda route: route.abort(),
        )

        page = await context.new_page()
        events = await get_event_links(page)
        await page.close()

        if not events:
            print("📭 Şu an canlı veya yayını yüklenmiş maç bulunamadı.")
            save_outputs([])
            await browser.close()
            sys.exit(0)

        print(f"\n🔍 Toplam {len(events)} aday maç kontrol ediliyor...\n")
        semaphore = asyncio.Semaphore(CONCURRENCY)
        tasks = [extract_m3u8_from_event(semaphore, context, ev) for ev in events]
        results = await asyncio.gather(*tasks)

        valid_streams = [r for r in results if r is not None]
        save_outputs(valid_streams)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
