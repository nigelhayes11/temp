import requests
import re
import base64
import urllib3
import time
import random
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# === YAPILANDIRMA ===
API_CHANNELS = "https://cdnlivetv.tv"
API_EVENTS = "https://cdnlivetv.tv"

CHANNELS_OUTPUT = "cdnlivetv_channels.m3u"
EVENTS_OUTPUT = "cdnlivetv_events.m3u"

# --- SPOR FİLTRESİ ---
# Tüm sporları (Futbol, Basketbol, NBA vb.) çekmek için boş bırakın: []
# Sadece belirli sporları çekmek için örnek: ["Soccer", "Basketball", "NBA"]
ALLOWED_SPORTS = ["Soccer", "Basketball", "NBA"]

# --- ANTI RATE-LIMIT ---
MAX_WORKERS = 3
TIMEOUT = 20
RETRIES = 2
JITTER_MIN = 0.3
JITTER_MAX = 0.7
PAUSE_BETWEEN_PHASES = 15
BACKOFF_BASE = 2
BACKOFF_MAX = 6
MAX_CONSECUTIVE_FAIL = 20

# Sadece çevrimiçi (online) TV kanallarını çekmek için True yapın
ONLY_ONLINE_CHANNELS = True
EVENTS_ONLY_LIVE = False

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://cdnlivetv.tv/",
    "Origin": "https://cdnlivetv.tv",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

_resolve_cache: dict = {}


# ================================================================
# YARDIMCI FONKSİYONLAR
# ================================================================
def b64d(s: str) -> bytes:
    s = s.replace("-", "+").replace("_", "/")
    s += "=" * (-len(s) % 4)
    try:
        return base64.b64decode(s)
    except Exception:
        return b""


def resolve_m3u8(player_url: str):
    if not player_url:
        return None, "player url yok"
    if player_url in _resolve_cache:
        return _resolve_cache[player_url]

    time.sleep(random.uniform(JITTER_MIN, JITTER_MAX))
    last_err = ""

    for attempt in range(RETRIES):
        try:
            r = requests.get(player_url, headers=HEADERS, timeout=TIMEOUT, verify=False)

            if r.status_code in (429, 502, 503):
                wait = min((2 ** attempt) * BACKOFF_BASE, BACKOFF_MAX) + random.uniform(0, 1)
                time.sleep(wait)
                last_err = f"HTTP {r.status_code}"
                continue

            if r.status_code != 200:
                result = (None, f"HTTP {r.status_code}")
                _resolve_cache[player_url] = result
                return result

            html = r.text
            join_match = re.search(
                r"[A-Za-z_$][\w$]*\s*=\s*("
                r"(?:[A-Za-z_$][\w$]*\([A-Za-z_$][\w$]*\)\s*\+\s*)+"
                r"[A-Za-z_$][\w$]*\([A-Za-z_$][\w$]*\))",
                html,
            )
            if not join_match:
                result = (None, "concat bulunamadı")
                _resolve_cache[player_url] = result
                return result

            args = re.findall(
                r"[A-Za-z_$][\w$]*\(([A-Za-z_$][\w$]*)\)", join_match.group(1)
            )
            vars_dict = dict(re.findall(
                r"var\s+([A-Za-z_$][\w$]*)\s*=\s*'([^']*)'", html
            ))

            parts = [b64d(vars_dict[a]).decode("utf-8", errors="replace")
                     for a in args if a in vars_dict]
            url = "".join(parts)

            result = (url, None) if url.startswith("http") else (None, "bozuk url")
            _resolve_cache[player_url] = result
            return result

        except Exception as e:
            last_err = f"{type(e).__name__}: {str(e)[:60]}"
            time.sleep(1 + attempt)

    result = (None, last_err or "bilinmeyen hata")
    _resolve_cache[player_url] = result
    return result


def process_channel(ch: dict) -> dict:
    url, err = resolve_m3u8(ch.get("url", ""))
    return {
        "name": ch.get("name", "Unknown"),
        "code": ch.get("code", ""),
        "img": ch.get("image", ""),
        "url": url,
        "err": err,
    }


def process_event_item(event: dict, sport: str) -> list:
    out = []
    title = event.get("event") or event.get("title") or "Maç Yayını"
    league = event.get("tournament") or event.get("league") or sport
    country = event.get("country") or ""
    status = (event.get("status") or "").lower()

    if status == "canc":
        return out
    if EVENTS_ONLY_LIVE and status not in ("in", "live", "playing"):
        return out

    for ch in event.get("channels", []) or []:
        ch_name = ch.get("channel_name", "")
        ch_url = ch.get("url", "")
        if not ch_url:
            continue
        full_name = f"[{sport}] {title} ({ch_name})" if ch_name else f"[{sport}] {title}"
        url, err = resolve_m3u8(ch_url)
        out.append({
            "name": full_name,
            "league": league,
            "country": country,
            "img": ch.get("image", ""),
            "url": url,
            "err": err,
            "sport": sport,
        })
    return out


def fetch_api(url: str, label: str):
    for attempt in range(RETRIES):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
            if r.status_code in (429, 502, 503):
                wait = min((2 ** attempt) * BACKOFF_BASE, BACKOFF_MAX) + random.uniform(0, 1)
                print(f"  ⏸️ {label} HTTP {r.status_code}, {wait:.1f}s bekleniyor...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"  ⚠️ {label} deneme {attempt+1}: {type(e).__name__}: {e}")
            time.sleep(2 + attempt)
    return None


def write_m3u(filename: str, items: list, is_event: bool = False):
    valid_items = [x for x in items if x.get("url")]
    with open(filename, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f"#EXT-X-USER-AGENT:{HEADERS['User-Agent']}\n")
        f.write(f"#EXT-X-REFERER:{HEADERS['Referer']}\n")
        f.write(f"#EXT-X-ORIGIN:{HEADERS['Origin']}\n\n")

        for item in valid_items:
            group = item["league"] if is_event else (item["code"].upper() or "TV Kanalları")
            logo = item.get("img", "")
            name = item["name"]
            f.write(f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="{group}",{name}\n')
            f.write(f"#EXTVLCOPT:http-referrer={HEADERS['Referer']}\n")
            f.write(f"{item['url']}\n")

    print(f"💾 {len(valid_items)} çalışan yayın '{filename}' dosyasına kaydedildi.")


# ================================================================
# MAIN (TAMAMLANMIŞ BÖLÜM)
# ================================================================
def main():
    print("=" * 60)
    print(" CDN Live TV - Extractor v4 (Tamamlanmış Sürüm)")
    print(f" Seçili Sporlar: {ALLOWED_SPORTS or 'Tümü'}")
    print("=" * 60)

    # ============ 1. AŞAMA: SPOR KARŞILAŞMALARI ============
    print("\n[1/2] Spor etkinlikleri API'den çekiliyor...")
    data_ev = fetch_api(API_EVENTS, "API Etkinlikler")

    results_ev = []
    if data_ev:
        # API yanıtındaki kök anahtar 'cdn-live-tv' veya 'cdnlivetv.tv' olabilir
        root = data_ev.get("cdn-live-tv") or data_ev.get("cdnlivetv.tv") or {}
        all_events = []

        for sport, evs in root.items():
            if not isinstance(evs, list):
                continue
            if ALLOWED_SPORTS and sport not in ALLOWED_SPORTS:
                continue
            for ev in evs:
                if ev.get("channels"):  # Sadece kanalı atanmış maçları al
                    all_events.append((sport, ev))

        print(f"✓ Kanalı atanmış {len(all_events)} maç bulundu.")

        if all_events:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = [executor.submit(process_event_item, ev, sport) for sport, ev in all_events]
                for fut in as_completed(futures):
                    res_list = fut.result()
                    for item in res_list:
                        if item["url"]:
                            print(f"  ✅ {item['name']}")
                            results_ev.append(item)

    write_m3u(EVENTS_OUTPUT, results_ev, is_event=True)

    # Rate-limit yememek için iki aşama arası bekleme
    print(f"\n⏳ Kanallara geçmeden önce {PAUSE_BETWEEN_PHASES} saniye bekleniyor...")
    time.sleep(PAUSE_BETWEEN_PHASES)

    # ============ 2. AŞAMA: 7/24 TV KANALLARI ============
    print("\n[2/2] TV Kanalları API'den çekiliyor...")
    data_ch = fetch_api(API_CHANNELS, "API Kanallar")

    results_ch = []
    if data_ch:
        channels = data_ch.get("channels", [])
        if ONLY_ONLINE_CHANNELS:
            channels = [c for c in channels if c.get("status") == "online"]

        print(f"✓ Taranacak {len(channels)} çevrimiçi kanal bulundu.")
        consecutive_fails = 0

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_channel, ch): ch for ch in channels}
            for fut in as_completed(futures):
                res = fut.result()
                if res["url"]:
                    consecutive_fails = 0
                    results_ch.append(res)
                else:
                    consecutive_fails += 1
                    if consecutive_fails >= MAX_CONSECUTIVE_FAIL:
                        print(f"🛑 Arka arkaya {MAX_CONSECUTIVE_FAIL} hata alındı (Rate-limit). Tarama durduruluyor...")
                        for f_cancel in futures:
                            f_cancel.cancel()
                        break

    write_m3u(CHANNELS_OUTPUT, results_ch, is_event=False)
    print("\n🎉 Tüm işlemler tamamlandı!")


if __name__ == "__main__":
    main()
