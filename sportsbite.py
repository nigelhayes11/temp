
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen
import asyncio
import json
import logging
import time

# =====================================================
# SPORTSBITE - STANDALONE SCRAPER
# Original scraper logic preserved
# utils.py dependency removed
# =====================================================

log = logging.getLogger(__name__)

if not log.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

urls = {}

TAG = "SPRTSBITE"
BASE_URL = "https://sportsbite.org"
API_URL = urljoin(BASE_URL, "api/forestgump/matches")

CACHE_FILE = Path("sportsbite_cache.json")
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


# =====================================================
# CACHE - replaces utils.Cache
# =====================================================

class LocalCache:

    def load(self):
        try:
            if not CACHE_FILE.exists():
                return {}

            data = json.loads(
                CACHE_FILE.read_text(encoding="utf-8")
            )

            if time.time() - data.get("saved_at", 0) > CACHE_EXPIRY:
                return {}

            return data.get("events", {})

        except Exception as e:
            log.warning("Cache load error: %s", e)
            return {}

    def write(self, data):
        try:
            payload = {
                "saved_at": time.time(),
                "events": data,
            }

            CACHE_FILE.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )

        except Exception as e:
            log.error("Cache write error: %s", e)


CACHE_FILE_OBJ = LocalCache()


# =====================================================
# NETWORK - replaces utils.network
# =====================================================

def request_api():

    request = Request(
        API_URL,
        headers=HEADERS,
        method="GET",
    )

    with urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(
                f"HTTP status: {response.status}"
            )

        return json.loads(
            response.read().decode("utf-8")
        )


async def network_request():

    try:
        return await asyncio.to_thread(request_api)

    except Exception as e:
        log.error("SportsBite request failed: %s", e)
        return None


# =====================================================
# TIME - replaces utils.Time
# =====================================================

def current_time():
    return datetime.now(timezone.utc)


# =====================================================
# STREAM PROCESSING - ORIGINAL LOGIC
# =====================================================

def process_event(url: str, url_num: int) -> str:

    s = url.replace("/embed/", "/cdn/")

    log.info(f"URL {url_num}) Captured M3U8")

    return f"{s}.m3u8?cdn=1"


# =====================================================
# EVENT SCRAPER - ORIGINAL FILTERS
# =====================================================

async def get_events(cached_keys):

    now = current_time()

    events = {}

    api_data = await network_request()

    if not api_data:
        return events

    start_ts = (now - timedelta(minutes=30)).timestamp()
    end_ts = (now + timedelta(minutes=30)).timestamp()

    counter = defaultdict(int)

    i = 1

    for game_event in api_data.get("days", [{}]):

        for game_info in game_event.get("events", [{}]):

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

            event_ts = int(f"{event_ts}"[:-3])

            if not start_ts <= event_ts <= end_ts:
                continue

            # leagues.get_tvg_info removed.
            # Default values preserve stream collection.

            tvg_id = "Live.Event.us"
            logo = ""

            for stream_info in event_streams:

                counter[name] += 1

                if stream_info.get("source") != "selfhost":
                    continue

                elif not (
                    url := stream_info.get("manifest_url")
                ):
                    continue

                elif (
                    key := (
                        f"[{sport}] {name} "
                        f"{counter[name]} ({TAG})"
                    )
                ) in cached_keys:
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
# SCRAPE - ORIGINAL MAIN INTERFACE
# =====================================================

async def scrape():

    cached_sources = CACHE_FILE_OBJ.load()

    valid_sources = {
        k: v
        for k, v in cached_sources.items()
        if v.get("source")
    }

    valid_count = len(valid_sources)

    urls.update(valid_sources)

    log.info(
        f"Loaded {valid_count} event(s) from cache"
    )

    log.info(
        f'Scraping from "{BASE_URL}"'
    )

    new_events = await get_events(
        cached_sources.keys()
    )

    urls.update(new_events)

    new_count = len(urls) - valid_count

    if new_count:
        log.info(
            f"Collected and cached {new_count} new event(s)"
        )
    else:
        log.info("No new events found")

    CACHE_FILE_OBJ.write(urls)
