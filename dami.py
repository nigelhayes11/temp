import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin
import requests

BASE_URL = "https://damitv.st"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Origin": BASE_URL,
}


def get_events() -> list[dict]:
    """API üzerinden günün maçlarını çeker ve saat aralığına göre filtreler."""
    api_url = urljoin(BASE_URL, "papi/matches/all-today")
    print(f"📡 Maç listesi çekiliyor: {api_url}")

    try:
        resp = requests.get(api_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        api_data = resp.json()
    except Exception as e:
        print(f"⚠️ Maç listesi alınamadı: {e}")
        return []

    now = datetime.now(timezone.utc)
    # Orijinal koddaki gibi 30 dk öncesi ve 30 dk sonrası arası maçlar
    start_dt = now - timedelta(minutes=30)
    end_dt = now + timedelta(minutes=30)

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

        # Milisaniye cinsinden gelen timestamp'i saniyeye çevir
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


def extract_m3u8(event: dict) -> str | None:
    """Her maç için extract-url API'sine sorarak m3u8 linkini alır."""
    extract_url = urljoin(BASE_URL, f"papi/extract-url/{event['ppv_id']}")
    req_headers = HEADERS.copy()
    req_headers["Referer"] = event["refer"]

    try:
        resp = requests.get(extract_url, headers=req_headers, timeout=10)
        if not resp.ok:
            return None
        data = resp.json() or {}
        m3u8 = data.get("sdUrl") or data.get("hlsUrl")
        if m3u8:
            print(f"✅ Bulundu: [{event['sport']}] {event['name']}")
            return m3u8
        else:
            print(f"❌ Kaynak boş döndü: {event['name']}")
            return None
    except Exception as e:
        print(f"⚠️ Hata ({event['name']}): {e}")
        return None


def save_outputs(streams: list[dict], m3u_filename: str = "dami.m3u", strm_folder: str = "dami_strm"):
    """Bulunan yayınları dami.m3u ve STRM dosyaları olarak kaydeder."""
    with open(m3u_filename, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f"#EXT-X-USER-AGENT:{USER_AGENT}\n")
        f.write(f"#EXT-X-REFERER:{BASE_URL}/\n")
        f.write(f"#EXT-X-ORIGIN:{BASE_URL}\n\n")

        for s in streams:
            title = f"[{s['sport']}] {s['name']}"
            f.write(f'#EXTINF:-1 tvg-name="{title}" tvg-logo="{s["logo"]}" group-title="{s["sport"]}",{title}\n')
            f.write(f'#EXTVLCOPT:http-referrer={s["refer"]}\n')
            f.write(f"{s['url']}\n")

    # STRM klasörü oluşturma
    base_dir = Path(strm_folder)
    base_dir.mkdir(parents=True, exist_ok=True)
    for old_file in base_dir.glob("*.strm"):
        old_file.unlink()

    for s in streams:
        safe_title = re.sub(r'[\\/*?:"<>|]', "", f"[{s['sport']}] {s['name']}").strip()
        file_path = base_dir / f"{safe_title}.strm"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"{s['url']}|Referer={s['refer']}&User-Agent={USER_AGENT}")

    print(f"\n🎉 İşlem tamamlandı! {len(streams)} yayın '{m3u_filename}' dosyasına ve '{strm_folder}' klasörüne kaydedildi.")


def main():
    events = get_events()
    if not events:
        print("📭 Şu anki saat aralığında (±30 dk) aktif maç bulunamadı.")
        sys.exit(0)

    print(f"\n🔍 Toplam {len(events)} maç için yayın linki çekiliyor...\n")
    valid_streams = []

    for ev in events:
        m3u8_url = extract_m3u8(ev)
        if m3u8_url:
            ev["url"] = m3u8_url
            valid_streams.append(ev)

    if valid_streams:
        save_outputs(valid_streams, m3u_filename="dami.m3u")
    else:
        print("😔 Çalışan yayın linki bulunamadı.")


if __name__ == "__main__":
    main()
