
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from collections import defaultdict
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin
from urllib.request import Request, urlopen
import asyncio
import json
import logging

# =====================================================
# SPORTSBITE - STANDALONE M3U SCRAPER
# Original doms9 logic
# No utils / Cache / Time / network / leagues
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
# NETWORK - replaces utils.network
# =====================================================

def get_api_data():

    try:
        request = Request(
            API_URL,
            headers=HEADERS,
        )

        with urlopen(request, timeout=30) as response:

            if response.status != 200:
                log.error("HTTP error: %s", response.status)
                return None

            data = json.loads(
                response.read().decode("utf-8")
            )

        if not isinstance(data, dict):
            log.error("Unexpected API response")
            return None

        return data

    except Exception as e:
        log.error("API request failed: %s", e)
        return None


# =====================================================
# ORIGINAL PROCESS_EVENT
# =====================================================

def process_event(url: str, url_num: int) -> str:

    s = url.replace("/embed/", "/cdn/")

    log.info("URL %s) Captured M3U8", url_num)

    return f"{s}.m3u8?cdn=1"


# =====================================================
# ORIGINAL GET_EVENTS
# Cache / Time / leagues removed
# =====================================================

async def get_events():

    now = datetime.now(timezone.utc)

    events = []

    api_data = await asyncio.to_thread(get_api_data)

    if not api_data:
        return None

    start_ts = (
        now - timedelta(minutes=30)
    ).timestamp()

    end_ts = (
        now + timedelta(minutes=30)
    ).timestamp()

    counter = defaultdict(int)

    i = 1

    for game_event in api_data.get("days", []):

        if not isinstance(game_event, dict):
            continue

        for game_info in game_event.get("events", []):

            if not isinstance(game_info, dict):
                continue

            if not all(
                values := [
                    game_info.get(x)
                    for x in (
                        "title",
                        "category",
                        "kickoffMs",
                        "streams",
                    )
                ]
            ):
                continue

            name, sport, event_ts, event_streams = values

            try:
                # Original timestamp conversion
                event_ts = int(f"{event_ts}"[:-3])
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

                elif not (
                    url := stream_info.get("manifest_url")
                ):
                    continue

                key = (
                    f"[{sport}] {name} "
                    f"{counter[name]} ({TAG})"
                )

                events.append({
                    "name": key,
                    "source": process_event(url, i),
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

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        file.write("\n".join(lines) + "\n")

    log.info(
        "Wrote %s event(s) to %s",
        len(events),
        OUTPUT_FILE,
    )


# =====================================================
# ORIGINAL SCRAPE - WITHOUT CACHE
# =====================================================

async def scrape():

    log.info('Scraping from "%s"', BASE_URL)

    events = await get_events()

    # API failed: don't overwrite existing playlist
    if events is None:
        log.error("Scraping failed. Existing M3U preserved.")
        return

    log.info(
        "Collected %s event(s)",
        len(events),
    )

    write_m3u(events)


# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    asyncio.run(scrape())
