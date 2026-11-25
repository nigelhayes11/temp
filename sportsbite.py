
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from collections import defaultdict

# =====================================================
# SPORTSBITE - STANDALONE M3U
# Original doms9 scraper logic
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
# API REQUEST
# =====================================================

def get_api_data():

    try:
        request = Request(API_URL, headers=HEADERS)

        with urlopen(request, timeout=30) as response:

            log.info("HTTP STATUS: %s", response.status)

            raw = response.read()

        data = json.loads(raw.decode("utf-8"))

        log.info("API RESPONSE TYPE: %s", type(data).__name__)

        if isinstance(data, dict):
            log.info("API KEYS: %s", list(data.keys()))

        return data

    except Exception as e:
        log.error("API REQUEST ERROR: %s", e)
        return None


# =====================================================
# ORIGINAL STREAM CONVERSION
# =====================================================

def process_event(url, url_num):

    stream = url.replace("/embed/", "/cdn/")

    log.info("URL %s) M3U8 captured", url_num)

    return f"{stream}.m3u8?cdn=1"


# =====================================================
# TIMESTAMP CONVERSION
# =====================================================

def convert_timestamp(value):

    try:
        timestamp = int(value)

        # Milliseconds -> seconds
        if timestamp > 10_000_000_000:
            timestamp //= 1000

        return timestamp

    except (ValueError, TypeError):
        return None


# =====================================================
# GET EVENTS
# =====================================================

def get_events():

    events = []

    api_data = get_api_data()

    if not api_data:
        log.error("API returned no data")
        return None

    if not isinstance(api_data, dict):
        log.error("API root is not a dictionary")
        return None

    days = api_data.get("days", [])

    if not isinstance(days, list):
        log.error("Invalid days structure")
        return None

    now = datetime.now(timezone.utc)

    start_ts = (
        now - timedelta(minutes=30)
    ).timestamp()

    end_ts = (
        now + timedelta(minutes=30)
    ).timestamp()

    log.info("API DAYS: %s", len(days))

    log.info(
        "TIME WINDOW: %s - %s",
        datetime.fromtimestamp(start_ts, timezone.utc),
        datetime.fromtimestamp(end_ts, timezone.utc),
    )

    counter = defaultdict(int)

    total_matches = 0
    time_matches = 0
    selfhost_matches = 0

    i = 1

    for game_event in days:

        if not isinstance(game_event, dict):
            continue

        day_events = game_event.get("events", [])

        if not isinstance(day_events, list):
            continue

        total_matches += len(day_events)

        for game_info in day_events:

            if not isinstance(game_info, dict):
                continue

            name = game_info.get("title")
            sport = game_info.get("category")
            event_ts = game_info.get("kickoffMs")
            event_streams = game_info.get("streams")

            if not name or not sport or event_ts is None:
                continue

            if not isinstance(event_streams, list):
                continue

            event_ts = convert_timestamp(event_ts)

            if event_ts is None:
                continue

            if not start_ts <= event_ts <= end_ts:
                continue

            time_matches += 1

            for stream_info in event_streams:

                if not isinstance(stream_info, dict):
                    continue

                counter[name] += 1

                if stream_info.get("source") != "selfhost":
                    continue

                url = stream_info.get("manifest_url")

                if not url:
                    continue

                selfhost_matches += 1

                key = (
                    f"[{sport}] {name} "
                    f"{counter[name]} ({TAG})"
                )

                events.append({
                    "name": key,
                    "source": process_event(url, i),
                    "logo": "",
                    "tvg-id": "Live.Event.us",
                })

                i += 1

    log.info("TOTAL MATCHES: %s", total_matches)
    log.info("MATCHES IN TIME WINDOW: %s", time_matches)
    log.info("SELFHOST STREAMS: %s", selfhost_matches)

    return events


# =====================================================
# WRITE M3U
# =====================================================

def write_m3u(events):

    lines = ["#EXTM3U"]

    for event in events:

        lines.append(
            '#EXTINF:-1 tvg-id="{}" tvg-logo="" '
            'group-title="SportsBite",{}'.format(
                event["tvg-id"],
                event["name"],
            )
        )

        lines.append(event["source"])

    try:

        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8",
        ) as file:

            file.write("\n".join(lines) + "\n")

        log.info(
            "WROTE %s EVENT(S) TO %s",
            len(events),
            OUTPUT_FILE,
        )

    except Exception as e:
        log.error("M3U WRITE ERROR: %s", e)


# =====================================================
# MAIN
# =====================================================

def scrape():

    log.info('Scraping from "%s"', BASE_URL)

    events = get_events()

    if events is None:
        log.error("Scraping failed. Existing M3U preserved.")
        return

    log.info("COLLECTED: %s", len(events))

    write_m3u(events)


if __name__ == "__main__":
    scrape()
