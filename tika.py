# ================================================================
# CDN Live TV - Extractor v4 (Soccer & Basketball + anti rate-limit + abort)
# Estrae canali TV + eventi calcio e basket dall'API cdnlivetv.is
# ================================================================

import requests
import re
import base64
import urllib3
import time
import random
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# === CONFIGURAZIONE ===
API_CHANNELS = "https://cdnlivetv.is"
API_EVENTS = "https://cdnlivetv.is"

CHANNELS_OUTPUT = "cdnlivetv_channels.m3u"
EVENTS_OUTPUT = "cdnlivetv_events.m3u"

# --- SOLO CALCIO E BASKET ---
ONLY_SPORTS = ["Soccer", "Basketball"]

# --- ANTI RATE-LIMIT ---
MAX_WORKERS = 3
TIMEOUT = 20
RETRIES = 2
JITTER_MIN = 0.3
JITTER_MAX = 0.7
PAUSE_BETWEEN_PHASES = 45
BACKOFF_BASE = 2
BACKOFF_MAX = 6
MAX_CONSECUTIVE_FAIL = 20

MAX_CHANNELS = 0
EVENTS_ONLY_LIVE = False

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://cdnlivetv.tv",
    "Origin": "https://cdnlivetv.tv",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

_resolve_cache: dict = {}


# ================================================================
# UTILITY
# ================================================================
def b64d(s: str) -> bytes:
    s = s.replace("-", "+").replace("_", "/")
    s += "=" * (-len(s) % 4)
    try:
        return base64.b64decode(s)
    except Exception:
        return b""


def normalize_event_name(name: str) -> str:
    if not name:
        return ""
    name = re.sub(
        r"\s*-\s*[^-]*(?:HD|FHD|SD|UHD|4K|CA|US|UK|BR|PT|ES|IT|DE|FR|AR|MX|NL|PL)\s*$",
        "", name, flags=re.IGNORECASE,
    )
    name = re.sub(
        r"\s*-\s*(?:Premiere|TSN|Sportsnet|Sky Sport|DAZN|ESPN|Fox|beIN|Sport TV|"
        r"Polsat|Movistar|Canal|Nova|V Sport|Stan Sport|Fox Sports|Max Sport|"
        r"Cosmote|Cytavision|Digi Sport|Prima Sport|Sport 5|Sport)\s*\d*\s*"
        r"(?:HD|FHD|SD)?\s*$",
        "", name, flags=re.IGNORECASE,
    )
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", name).strip().lower()


# ================================================================
# RISOLUZIONE TOKEN
# ================================================================
def resolve_m3u8(player_url: str):
    if not player_url:
        return None, "no player url"
    if player_url in _resolve_cache:
        return _resolve_cache[player_url]

    time.sleep(random.uniform(JITTER_MIN, JITTER_MAX))
    last_err = ""

    for attempt in range(RETRIES):
        try:
            r = requests.get(player_url, headers=HEADERS,
                             timeout=TIMEOUT, verify=False)

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
                result = (None, "no concat")
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

            result = (url, None) if url.startswith("http") else (None, "url malformato")
            _resolve_cache[player_url] = result
            return result

        except Exception as e:
            last_err = f"{type(e).__name__}: {str(e)[:60]}"
            time.sleep(1 + attempt)

    result = (None, last_err or "unknown")
    _resolve_cache[player_url] = result
    return result


# ================================================================
# PROCESSORI
# ================================================================
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
    title = event.get("event") or event.get("title") or "Evento"
    league = event.get("tournament") or event.get("league") or ""
    country = event.get("country") or ""
    status = (event.get("status") or "").lower()

    if EVENTS_ONLY_LIVE and status not in ("in", "live", "playing"):
        return out

    for ch in event.get("channels", []) or []:
        ch_name = ch.get("channel_name", "")
        ch_url = ch.get("url", "")
        if not ch_url:
            continue
        full_name = f"{title} - {ch_name}" if ch_name else title
        url, err = resolve_m3u8(ch_url)
        out.append({
            "name": full_name, "title": title, "league": league,
            "country": country, "code": ch.get("channel_code", ""),
            "img": ch.get("image", ""), "url": url, "err": err, "sport": sport,
        })
    return out


# ================================================================
# FETCH API
# ================================================================
def fetch_api(url: str, label: str):
    for attempt in range(RETRIES):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
            if r.status_code in (429, 502, 503):
                wait = min((2 ** attempt) * BACKOFF_BASE, BACKOFF_MAX) + random.uniform(0, 1)
                print(f"  ⏸️ {label} HTTP {r.status_code}, attendo {wait:.1f}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"  ⚠️ {label} attempt {attempt+1}: {type(e).__name__}: {e}")
            time.sleep(2 + attempt)
    return None


# ================================================================
# SCRITTURA M3U
# ================================================================
def write_events_m3u(items: list, filepath: str):
    valid = [x for x in items if x.get("url")]
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in valid:
            sport = item.get("sport", "Sport")
            league = item.get("league", "")
            group = f"{sport} - {league}" if league else sport
            logo = item.get("img", "")
            name = item.get("name", "Evento")
            url = item["url"]
            f.write(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{name}\n')
            f.write(f"{url}\n")
    print(f"💾 Salvati {len(valid)}/{len(items)} stream eventi in {filepath}")


def write_channels_m3u(items: list, filepath: str):
    valid = [x for x in items if x.get("url")]
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in valid:
            code = item.get("code", "").upper()
            group = f"TV ({code})" if code else "TV Channels"
            logo = item.get("img", "")
            name = item.get("name", "Channel")
            url = item["url"]
            f.write(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{name}\n')
            f.write(f"{url}\n")
    print(f"💾 Salvati {len(valid)}/{len(items)} canali TV in {filepath}")


# ================================================================
# MAIN
# ================================================================
def main():
    print("=" * 60)
    print(" CDN Live TV - Extractor v4 (Soccer & Basketball + abort)")
    print(f" Workers: {MAX_WORKERS} | Jitter: {JITTER_MIN}-{JITTER_MAX}s")
    print(f" Retries: {RETRIES} | Backoff max: {BACKOFF_MAX}s | Abort: {MAX_CONSECUTIVE_FAIL} KO di fila")
    if ONLY_SPORTS:
        print(f" Filtro sport: {', '.join(ONLY_SPORTS)}")
    print("=" * 60)

    # ============ FASE 1: EVENTI ============
    print(f"\n[1/2] Scarico API eventi sport...")
    data_ev = fetch_api(API_EVENTS, "API eventi")

    results_ev_raw = []
    if data_ev:
        root = data_ev.get("cdn-live-tv", {})
        all_events = []
        for sport, evs in root.items():
            if not isinstance(evs, list):
                continue
            if ONLY_SPORTS and sport not in ONLY_SPORTS:
                continue
            for ev in evs:
                all_events.append((sport, ev))

        print(f"✓ {len(all_events)} eventi" +
              (f" (solo {', '.join(ONLY_SPORTS)})" if ONLY_SPORTS else ""))

        if all_events:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
                futures = [ex.submit(process_event_item, ev, sp) for sp, ev in all_events]
                for fut in as_completed(futures):
                    try:
                        res = fut.result()
                        if res:
                            results_ev_raw.extend(res)
                    except Exception as e:
