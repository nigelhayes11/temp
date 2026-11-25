
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin

# =====================================================
# SPORTSBITE - STANDALONE M3U SCRAPER
# Original source: doms9/iptv
# No utils / leagues / external project modules
# =====================================================

BASE_URL = "https://sportsbite.org"
API_URL = urljoin(BASE_URL, "api/forestgump/matches")

TAG = "SPRTSBITE"

OUTPUT_FILE = "sportsbite.m3u"
CACHE_FILE = "sportsbite_cache.json"

CACHE_EXPIRY = 10800

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

urls = {}


# =====================================================
# CACHE
# =====================================================

def load_cache():
    path = Path(CACHE_FILE)

    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))

        saved_at = data.get("saved_at", 0)

        if time.time() - saved_at > CACHE_EXPIRY:
            log.info("Cache expired")
            return {}

        return data.get("events", {})

    except Exception as e:
        log.warning("Cache read error: %s", e)
        return {}


def save_cache(events):
    try:
        data = {
            "saved_at": time.time(),
            "events": events,
        }

        Path(CACHE_FILE).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    except Exception as e:
        log.error("Cache write error: %s", e)


# =====================================================
# API REQUEST
# =====================================================

def get_api_data():
    try:
        request = Request(API_URL, headers=HEADERS)

        with urlopen(request, timeout=25) as response:
            raw = response.read()

            print("HTTP STATUS:", response.status)
            print("RESPONSE:", raw[:3000].decode(
                "utf-8", errors="replace"
            ))

        return json.loads(raw.decode("utf-8"))

    except Exception as e:
        log.error("API ERROR: %s", e)
        return None


# =====================================================
# STREAM PROCESSING
# =====================================================

def process_event(url, url_num):

    stream_url = url.replace(
        "/embed/",
        "/cdn/",
    )

    log.info(
        "URL %s) Captured M3U8",
        url_num,
    )

    return f"{stream_url}.m3u8?cdn=1"


# =====================================================
# EVENT SCRAPER
# =====================================================

def get_events(cached_keys):

    now = int(time.time())

    start_ts = now - (30 * 60)
    end_ts = now + (30 * 60)

    events = {}

    api_data = get_api_data()

    if not api_data:
        return events

    days = api_data.get("days", [])

    if not isinstance(days, list):
        log.warning("Unexpected API days format")
        return events

    counter = {}
    i = 1

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
                event_ts = int(event_ts)

                # Milliseconds -> seconds
                if event_ts > 9999999999:
                    event_ts //= 1000

            except (ValueError, TypeError):
                continue

            if not start_ts <= event_ts <= end_ts:
                continue

            # Standalone version:
            # leagues.get_tvg_info() removed.
            tvg_id = "Live.Event.us"
            logo = ""

            for stream_info in event_streams:

                if not isinstance(stream_info, dict):
                    continue

                counter[name] = counter.get(name, 0) + 1

                if stream_info.get("source") != "selfhost":
                    continue

                url = stream_info.get("manifest_url")

                if not url:
                    continue

                key = (
                    f"[{sport}] {name} "
                    f"{counter[name]} ({TAG})"
                )

                if key in cached_keys:
                    continue

                events[key] = {
                    "source": process_event(url, i),
                    "logo": logo,
                    "refer": BASE_URL,
                    "timestamp": event_ts,
                    "tvg-id": tvg_id,
                }

                i += 1

    return events


# =====================================================
# M3U WRITER
# =====================================================

def write_m3u(events):

    lines = [
        "#EXTM3U"
    ]

    for name, info in events.items():

        source = info.get("source", "")

        if not source:
            continue

        logo = info.get("logo", "")
        tvg_id = info.get("tvg-id", "Live.Event.us")

        group = "SportsBite"

        lines.append(
            f'#EXTINF:-1 tvg-id="{tvg_id}" '
            f'tvg-logo="{logo}" '
            f'group-title="{group}",{name}'
        )

        lines.append(source)

    try:
        Path(OUTPUT_FILE).write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
        )

        log.info(
            "Wrote %s event(s) to %s",
            len(lines) // 2,
            OUTPUT_FILE,
        )

    except Exception as e:
        log.error("M3U write error: %s", e)


# =====================================================
# MAIN
# =====================================================

def scrape():

    cached_sources = load_cache()

    valid_sources = {
        key: value
        for key, value in cached_sources.items()
        if value.get("source")
    }

    urls.update(valid_sources)

    log.info(
        "Loaded %s event(s) from cache",
        len(valid_sources),
    )

    log.info(
        'Scraping from "%s"',
        BASE_URL,
    )

    new_events = get_events(
        cached_sources.keys()
    )

    urls.update(new_events)

    log.info(
        "Collected %s new event(s)",
        len(new_events),
    )

    save_cache(urls)

    write_m3u(urls)


# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    scrape()
