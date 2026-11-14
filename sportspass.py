import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE_URL = "https://streamseast.dad"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"

# Tarama yapılacak spor dalları (İstemediklerinizi # ile kapatabilirsiniz)
SPORTS = [
    "NBA",
    "NFL",
    # "Soccer",
    # "MMA",
    # "Boxing",
    # "F1",
    # "MLB",
    # "NHL",
]


def get_event_links(page) -> list[dict]:
    """Ana spor sayfalarından aktif veya başlamak üzere olan maç linklerini toplar."""
    events = []
    seen_links = set()
    now = datetime.now(timezone.utc)
    start_window = now - timedelta(hours=3)
    end_window = now + timedelta(minutes=15)
    date_ptrn = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z", re.I)

    for sport in SPORTS:
        sport_url = urljoin(BASE_URL, sport.lower())
        print(f"📡 {sport} maçları taranıyor: {sport_url}")
        try:
            page.goto(sport_url, timeout=20000, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            
            match_elements = page.query_selector_all("a.matches")
            for el in match_elements:
                href = el.get_attribute("href")
                if not href:
                    continue
                
                full_link = urljoin(BASE_URL, href)
                if full_link in seen_links:
                    continue

                # Tarih veya canlı yayın rozeti kontrolü
                is_valid_time = False
                script_el = el.query_selector("script")
                if script_el:
                    match = date_ptrn.search(script_el.inner_text())
                    if match:
                        event_dt = datetime.fromisoformat(match.group(0).replace("Z", "+00:00"))
                        if start_window <= event_dt <= end_window:
                            is_valid_time = True
                
                if not is_valid_time and el.query_selector("span.status-badge.badge.bg-success"):
                    is_valid_time = True

                if is_valid_time:
                    seen_links.add(full_link)
                    events.append({"sport": sport, "link": full_link})
                    
        except Exception as e:
            print(f"⚠️ {sport} sayfası taranırken hata: {e}")

    return events


def extract_m3u8_from_event(context, event: dict) -> dict | None:
    """Maç sayfasına girer, oynatıcıyı tetikler ve ağ trafiğinden M3U8 linkini yakalar."""
    page = context.new_page()
    captured_m3u8 = []

    def handle_request(request):
        req_url = request.url
        if ".m3u8" in req_url.lower() and "indianservers" not in req_url.lower():
            if not captured_m3u8:
                captured_m3u8.append(req_url)

    page.on("request", handle_request)
    event_name = "Canlı Yayın"

    try:
        page.goto(event["link"], timeout=15000, wait_until="domcontentloaded")
        
        title_el = page.query_selector("h1.match-head")
        if title_el:
            event_name = title_el.inner_text().strip()

        iframe_el = page.wait_for_selector("iframe.embed-responsive-item", timeout=5000)
        ifr_src = iframe_el.get_attribute("src") if iframe_el else None
        if not ifr_src:
            return None

        page.goto(urljoin(BASE_URL, ifr_src), timeout=10000, wait_until="domcontentloaded")
        
        # Oynat butonuna tıkla
        try:
            play_btn = page.locator(".vjs-big-play-button").first
            play_btn.dblclick(force=True, timeout=3000)
        except PlaywrightTimeoutError:
            pass

        # M3U8 yakalanana kadar en fazla 6 saniye bekle
        for _ in range(12):
            if captured_m3u8:
                break
            page.wait_for_timeout(500)

        if captured_m3u8:
            print(f"✅ Bulundu: [{event['sport']}] {event_name}")
            return {
                "name": event_name,
                "sport": event["sport"],
                "url": captured_m3u8[0]
            }
        else:
            print(f"❌ Yayın linki yakalanamadı: {event_name}")
            return None

    except Exception as e:
        print(f"⚠️ Hata ({event['link']}): {e}")
        return None
    finally:
        page.close()


def save_outputs(streams: list[dict], m3u_filename: str = "streamseast.m3u8", strm_folder: str = "strm_streams"):
    """Toplanan yayınları hem M3U8 hem de STRM olarak kaydeder."""
    # 1. M3U8 Çıktısı (Örnek kodunuzdaki başlık formatıyla aynı)
    with open(m3u_filename, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f"#EXT-X-USER-AGENT:{USER_AGENT}\n")
        f.write(f"#EXT-X-REFERER:{BASE_URL}/\n")
        f.write(f"#EXT-X-ORIGIN:{BASE_URL}\n\n")

        for s in streams:
            title = f"[{s['sport']}] {s['name']}"
            f.write(f'#EXTINF:-1 tvg-name="{title}" group-title="{s["sport"]}",{title}\n')
            f.write(f"{s['url']}\n")

    # 2. STRM Çıktısı
    base_dir = Path(strm_folder)
    base_dir.mkdir(parents=True, exist_ok=True)
    for old_file in base_dir.glob("*.strm"):
        old_file.unlink()

    for s in streams:
        safe_title = re.sub(r'[\\/*?:"<>|]', "", f"[{s['sport']}] {s['name']}").strip()
        file_path = base_dir / f"{safe_title}.strm"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"{s['url']}|Referer={BASE_URL}/&User-Agent={USER_AGENT}")

    print(f"\n🎉 İşlem tamamlandı! {len(streams)} yayın '{m3u_filename}' dosyasına ve '{strm_folder}' klasörüne kaydedildi.")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()

        events = get_event_links(page)
        page.close()

        if not events:
            print("📭 Şu anda aktif veya başlamak üzere olan maç bulunamadı.")
            browser.close()
            sys.exit(0)

        print(f"\n🔍 Toplam {len(events)} maç kontrol ediliyor...\n")
        valid_streams = []
        for ev in events:
            result = extract_m3u8_from_event(context, ev)
            if result:
                valid_streams.append(result)

        if valid_streams:
            save_outputs(valid_streams)
        else:
            print("😔 Çalışan yayın linki elde edilemedi.")

        browser.close()


if __name__ == "__main__":
    main()
