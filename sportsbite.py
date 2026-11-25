
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin

# =====================================================
# SPORTSBITE - STANDALONE M3U
# No utils / Cache / Time / leagues
# Uses requests
# =====================================================

TAG = "SPRTSBITE"

BASE_URL = "https://sportsbite.org"
API_URL = urljoin(BASE_URL, "api/forestgump/matches")

OUTPUT_FILE = "sportsbite.m3u"

TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": BASE_URL + "/",
    "Origin": BASE_URL,
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
        session = requests.Session()

        response = session.get(
            API_URL,
            headers=HEADERS,
            timeout=TIMEOUT,
        )

        log.info("HTTP STATUS: %s", response.status_code)

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            log.error(
                "Unexpected API root: %s",
                type(data).__name__,
            )
            return None

        log.info(
            "API KEYS: %s",
            list(data.keys()),
        )

        return data

    except requests.RequestException as e:
        log.error("REQUEST ERROR: %s", e)
        return None

    except ValueError as e:
        log.error("JSON ERROR: %s", e)
        return None


# =====================================================
# ORIGINAL URL PROCESSING
# =====================================================

def process_event(url, url_num):

    stream = url.replace(
        "/embed/",
        "/cdn/",
    )

    log.info(
        "URL %s) Captured M3U8",
        url_num,
    )

    return f"{stream}.m3u8?cdn=1"


# =====================================================
# TIMESTAMP
# =====================================================

def convert_timestamp(value):

    try:
        timestamp = int(value)

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

    if api_data is None:
        return None

    days = api_data.get("days", [])

    if not isinstance(days, list):
        log.error("API days is not a list")
        return None

    now = datetime.now(timezone.utc)

    start_ts = (
        now - timedelta(minutes=30)
    ).timestamp()

    end_ts = (
        now + timedelta(minutes=30)
    ).timestamp()

    counter = defaultdict(int)

    total_matches = 0
    time_matches = 0
    stream_count = 0

    i = 1

    log.info("API DAYS: %s", len(days))

    for game_event in days:

        if not isinstance(game_event, dict):
            continue

        game_list = game_event.get("events", [])

        if not isinstance(game_list, list):
            continue

        total_matches += len(game_list)

        for game_info in game_list:

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

            if not all(
                value is not None and value != ""
                for value in values
            ):
                continue

            name, sport, event_ts, event_streams = values

            if not isinstance(event_streams, list):
                continue

            event_ts = convert_timestamp(event_ts)

            if event_ts is None:
                continue

            # Original doms9 time window
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

                key = (
                    f"[{sport}] {name} "
                    f"{counter[name]} ({TAG})"
                )

                events.append({
                    "name": key,
                    "source": process_event(url, i),
                    "logo": "",
                    "refer": BASE_URL,
                    "timestamp": event_ts,
                    "tvg-id": "Live.Event.us",
                })

                stream_count += 1
                i += 1

    log.info("TOTAL MATCHES: %s", total_matches)
    log.info("MATCHES IN TIME WINDOW: %s", time_matches)
    log.info("SELFHOST STREAMS: %s", stream_count)

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
        ) as f:

            f.write("\n".join(lines) + "\n")

        log.info(
            "Wrote %s event(s) to %s",
            len(events),
            OUTPUT_FILE,
        )

    except OSError as e:
        log.error("M3U WRITE ERROR: %s", e)


# =====================================================
# MAIN
# =====================================================

def scrape():

    log.info('Scraping from "%s"', BASE_URL)

    events = get_events()

    if events is None:
        log.error("API failed. Existing M3U preserved.")
        return

    log.info("Collected %s event(s)", len(events))

    write_m3u(events)


if __name__ == "__main__":
    scrape()
