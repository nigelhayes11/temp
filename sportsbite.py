from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
from urllib.parse import urljoin
from urllib.request import Request, urlopen

TAG = "SPRTSBITE"
BASE_URL = "https://sportsbite.org"
OUTPUT_FILE = "bite.m3u"


def process_event(url: str, url_num: int) -> str:
    s = url.replace("/embed/", "/cdn/")
    print(f"URL {url_num}) Yakalandı: {s}.m3u8?cdn=1")
    return f"{s}.m3u8?cdn=1"


def get_events() -> dict[str, dict[str, str | int]]:
    now = datetime.now(timezone.utc)
    start_ts = (now - timedelta(minutes=30)).timestamp()
    end_ts = (now + timedelta(minutes=30)).timestamp()

    events = {}
    api_url = urljoin(BASE_URL, "api/forestgump/matches")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        ),
        "Referer": BASE_URL,
    }

    try:
        req = Request(api_url, headers=headers)
        with urlopen(req, timeout=15) as response:
            raw_data = response.read().decode("utf-8")
            api_data = json.loads(raw_data)
    except Exception as e:
        print(f"API isteği başarısız oldu: {e}")
        return events

    counter: dict[str, int] = defaultdict(int)
    i = 1

    days = api_data.get("days", []) if isinstance(api_data, dict) else api_data

    for game_event in days:
        for game_info in game_event.get("events", []):
            title = game_info.get("title")
            sport = game_info.get("category")
            kickoff_ms = game_info.get("kickoffMs")
            event_streams = game_info.get("streams")

            if not all([title, sport, kickoff_ms, event_streams]):
                continue

            event_ts = int(int(kickoff_ms) / 1000)

            if not (start_ts <= event_ts <= end_ts):
                continue

            for stream_info in event_streams:
                counter[title] += 1

                if stream_info.get("source") != "selfhost":
                    continue

                url = stream_info.get("manifest_url")
                if not url:
                    continue

                key = f"[{sport}] {title} {counter[title]} ({TAG})"

                events[key] = {
                    "source": process_event(url, i),
                    "logo": "",
                    "refer": BASE_URL,
                    "timestamp": event_ts,
                    "tvg-id": "Live.Event.us",
                    "group": sport,
                }
                i += 1

    return events


def save_to_m3u(events: dict) -> None:
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for name, info in events.items():
            f.write(
                f'#EXTINF:-1 tvg-id="{info["tvg-id"]}" tvg-logo="{info["logo"]}"'
                f' group-title="{info["group"]}",{name}\n'
            )
            f.write(f'#EXTVLCOPT:http-referrer={info["refer"]}\n')
            f.write(
                "#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64;"
                " x64)\n"
            )
            f.write(f'{info["source"]}\n')

    print(f"\nToplam {len(events)} yayın '{OUTPUT_FILE}' dosyasına kaydedildi.")


if __name__ == "__main__":
    print(f'"{BASE_URL}" üzerinden yayınlar çekiliyor...')
    collected_events = get_events()
    save_to_m3u(collected_events)
