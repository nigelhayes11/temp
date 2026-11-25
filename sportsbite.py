
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin
from urllib.request import Request, urlopen
import json
import logging

# =====================================================
# SPORTSBITE - STANDALONE M3U
# No utils / Cache / leagues / JSON cache
# =====================================================

TAG = "SPRTSBITE"
BASE_URL = "https://sportsbite.org"
API_URL = urljoin(BASE_URL, "api/forestgump/matches")
OUTPUT_FILE = "sportsbite.m3u"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": BASE_URL + "/",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

log = logging.getLogger("SPORTSBITE")


# =====================================================
# NETWORK
# =====================================================

def get_api_data():

    try:
        request = Request(
            API_URL,
            headers=HEADERS,
        )

        with urlopen(request, timeout=30) as response:
            if response.status != 200:
                log.error("HTTP status: %s", response.status)
                return None

            data = json.loads(
                response.read().decode("utf-8")
            )

        if not isinstance(data, dict):
            log.error("Unexpected API response format")
            return None

        return data

    except Exception as e:
        log.error("API request error: %s", e)
        return None


# =====================================================
# STREAM PROCESSING
# ORIGINAL SPORTSBITE LOGIC
# =====================================================

def process_event(url, url_num):

    stream_url = url.replace(
        "/embed/",
        "/cdn/"
    )

    log.info("URL %s) M3U8 captured", url_num)

    return f"{stream_url}.m3u8?cdn=1"


# =====================================================
# EVENT SCRAPER
# =====================================================

def get_events():

    events = []

    now = datetime.now(timezone.utc)

    start_ts = (
        now - timedelta(minutes=30)
    ).timestamp()

    end_ts = (
        now + timedelta(minutes=30)
    ).timestamp()

    api_data = get_api_data()

    if not api_data:
        return events

    counter = defaultdict(int)
    i = 1

    days = api_data.get("days", [])

    if not isinstance(days, list):
        log.error("API days field is not a list")
        return events

    for game_event in days:

        if not isinstance(game_event, dict):
            continue

        for game_info in game_event.get("events", []):

            if not isinstance(game_info, dict):
                continue

            values = [
                game_info.get(x)
                for x in (
                    "title",
                    "category",
                    "kickoffMs",
                    "streams",
                )
            ]

            if not all(values):
                continue

            name, sport, event_ts, event_streams = values

            try:
                event_ts = int(event_ts) // 1000
            except (ValueError, TypeError):
                continue

            if not start_ts <= event_ts <= end_ts:
                continue

            # leagues.get_tvg_info removed
            tvg_id = "Live.Event.us"
            logo = ""

            for stream_info in event_streams:

                if not isinstance(stream_info, dict):
                    continue

                counter[name] += 1

                if stream_info.get("source") != "selfhost":
                    continue

                url = stream_info.get("manifest_url")

                if not url:
                    continue

                key = (
                    f"[{sport}] {name} "
                    f"{counter[name]} ({TAG})"
                )

                stream_url = process_event(url, i)

                events.append({
                    "name": key,
                    "source": stream_url,
                    "logo": logo,
                    "refer": BASE_URL,
                    "timestamp": event_ts,
                    "tvg-id": tvg_id,
                })

                i += 1

    return events


# =====================================================
# M3U WRITER
# =====================================================

def write_m3u(events):

    lines = ["#EXTM3U"]

    for event in events:

        name = event["name"]
        source = event["source"]
        logo = event["logo"]
        tvg_id = event["tvg-id"]

        lines.append(
            f'#EXTINF:-1 tvg-id="{tvg_id}" '
            f'tvg-logo="{logo}" '
            f'group-title="SportsBite",{name}'
        )

        lines.append(source)

    try:
        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8"
        ) as file:
            file.write("\n".join(lines) + "\n")

        log.info(
            "Wrote %s event(s) to %s",
            len(events),
            OUTPUT_FILE
        )

    except Exception as e:
        log.error("M3U write error: %s", e)


# =====================================================
# MAIN
# =====================================================

def scrape():

    log.info('Scraping from "%s"', BASE_URL)

    events = get_events()

    log.info(
        "Collected %s event(s)",
        len(events)
    )

    write_m3u(events)


if __name__ == "__main__":
    scrape()
