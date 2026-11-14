import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

BASE_URL = "https://damitv.st"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def get_events(page) -> list[dict]:
    """Tarayıcı üzerinden API'ye gidip günün maçlarını çeker."""
    api_url = urljoin(BASE_URL, "papi/matches/all-today")
    print(f"📡 Maç listesi tarayıcı ile çekiliyor: {api_url}")

    try:
        page.goto(BASE_URL, timeout=20000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        api_data = page.evaluate(f"""async () => {{
            const res = await fetch("{api_url}");
            return await res.json();
        }}""")
    except Exception as e:
        print(f"⚠️ Maç listesi alınamadı: {e}")
        return []

    if not isinstance(api_data, list):
        print("⚠️ API beklenmeyen bir format döndürdü (Koruma engeli olabilir).")
        return []

    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(hours=3)
    end_dt = now + timedelta(hours=6)

    events = []
    for event in api_data:
        name = event.get("title")
        sport = event.get("league")
        start_ts = event.get("date")
        stream_id = event.get("id")
        ppv_id = event.get("ppvId")

        if not all([name, sport, start_ts, stream_id, ppv_id]):
            continue

        if str(stream_id).lower().startswith(("dl-", "247")) or str(sport).startswith("24/7"):
            continue

        sport_clean = (
            " ".join(i.capitalize().strip() for i in sport.split("-"))
            if sport.islower()
            else sport
        )

        try:
            event_ts = int(str(start_ts)[:-3])
            event_dt = datetime.fromtimestamp(event_ts, tz=timezone.utc)
        except ValueError:
            continue

        if not (start_dt <= event_dt <= end_dt):
            continue

        poster = event.get("poster", "")
        if poster and not poster.startswith("http"):
            poster = urljoin(BASE_URL, poster)

        events.append({
            "sport": sport_clean,
            "name": name,
            "logo": poster,
            "stream_id": stream_id,
            "ppv_id": ppv_id,
            "refer": urljoin(BASE_URL, f"embed/?id={stream_id}")
        })

    return events


def extract_m3u8(page, event: dict) -> str | None:
    """Tarayıcı oturumu içinden extract-url API'sine sorarak m3u8 linkini alır."""
    extract_url = urljoin(BASE_URL, f"papi/extract-url/{event['ppv_id']}")

    try:
        data = page.evaluate(f"""async () => {{
            const res = await fetch("{extract_url}", {{
                headers: {{
                    "Referer": "{event['refer']}"
                }}
            }});
            if (!res.ok) return null;
            return await res.json();
        }}""")

        if not data:
            return None

        m3u8 = data.get("sdUrl") or data.get("hlsUrl")
        if m3u8:
            print(f"✅ Bulundu: [{event['sport']}] {event['name']}")
            return m3u8
        else:
            print(f"❌ Kaynak henüz aktif değil: {event['name']}")
            return None

    except Exception as e:
        print(f"⚠️ Hata ({event['name']}): {e}")
        return None


def save_outputs(streams: list[dict], user_agent: str, m3u_filename: str = "dami.m3u", strm_folder: str = "dami_strm"):
    """Bulunan yayınları dami.m3u ve STRM dosyaları olarak kaydeder."""
    with open(m3u_filename, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f"#EXT-X-USER-AGENT:{user_agent}\n")
        f.write(f"#EXT-X-REFERER:{BASE_URL}/\n")
        f.write(f"#EXT-X-ORIGIN:{BASE_URL}\n\n")

        for s in streams:
            title = f"[{s['sport']}] {s['name']}"
            f.write(f'#EXTINF:-1 tvg-name="{title}" tvg-logo="{s["logo"]}" group-title="{s["sport"]}",{title}\n')
            f.write(f'#EXTVLCOPT:http-referrer={s["refer"]}\n')
            f.write(f'#EXTVLCOPT:http-user-agent={user_agent}\n')
            f.write(f"{s['url']}\n")

    base_dir = Path(strm_folder)
    base_dir.mkdir(parents=True, exist_ok=True)

    for old_file in base_dir.glob("*.strm"):
        old_file.unlink()

    for s in streams:
        safe_title = re.sub(r'[\\/*?:"<>|]', "", f"[{s['sport']}] {s['name']}").strip()
        file_path = base_dir / f"{safe_title}.strm"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"{s['url']}|Referer={s['refer']}&User-Agent={user_agent}")

    print(f"\n🎉 İşlem tamamlandı! {len(streams)} yayın '{m3u_filename}' dosyasına ve '{strm_folder}' klasörüne kaydedildi.")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        raw_ua = page.evaluate("() => navigator.userAgent")
        active_ua = raw_ua.replace("HeadlessChrome", "Chrome") if raw_ua else DEFAULT_USER_AGENT

        context.close()
        context = browser.new_context(user_agent=active_ua)
        page = context.new_page()

        events = get_events(page)
        if not events:
            print("📭 Belirtilen saat aralığında maç bulunamadı veya site erişimi engelledi.")
            browser.close()
            sys.exit(0)

        print(f"\n🔍 Toplam {len(events)} maç için yayın linki çekiliyor...\n")
        valid_streams = []

        for ev in events:
            m3u8_url = extract_m3u8(page, ev)
            if m3u8_url:
                ev["url"] = m3u8_url
                valid_streams.append(ev)

        if valid_streams:
            save_outputs(valid_streams, user_agent=active_ua, m3u_filename="dami.m3u")
        else:
            print("😔 Çalışan yayın linki bulunamadı (Maçlar henüz başlamamış olabilir).")

        browser.close()


if __name__ == "__main__":
    main()
