import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("DAMITV")

TAG = "DAMITV"
BASE_URL = "https://damitv.st"
OUTPUT_M3U = "dami.m3u"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


async def process_event(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    event: dict[str, Any],
    url_num: int,
) -> dict[str, str] | None:
    refer_url = urljoin(BASE_URL, f"embed/?id={event['stream_id']}")
    api_url = urljoin(BASE_URL, f"papi/extract-url/{event['ppv_id']}")

    async with semaphore:
        try:
            response = await client.get(
                api_url,
                headers={**HEADERS, "Referer": refer_url},
                timeout=25.0,
            )
            response.raise_for_status()
            api_data = response.json() or {}
        except Exception as e:
            log.warning(f"URL {url_num}) Request failed: {e}")
            return None

        if not (m3u8 := api_data.get("sdUrl") or api_data.get("hlsUrl")):
            log.warning(f"URL {url_num}) No source found -> {event['name']}")
            return None

        log.info(f"URL {url_num}) Captured M3U8 -> {event['name']}")

        return {
            "sport": event["sport"],
            "name": event["name"],
            "logo": event.get("logo") or "",
            "source": m3u8.strip(),
            "refer": refer_url,
            "tvg-id": "Live.Event.us",
        }


async def get_events(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(minutes=30)
    end_dt = now + timedelta(minutes=30)

    events: list[dict[str, Any]] = []

    try:
        response = await client.get(
            urljoin(BASE_URL, "papi/matches/all-today"),
            headers=HEADERS,
            timeout=20.0,
        )
        response.raise_for_status()
        api_data: list[dict[str, Any]] = response.json() or []
    except Exception as e:
        log.error(f"Failed to fetch matches API: {e}")
        return events

    for event in api_data:
        if not isinstance(event, dict):
            continue

        if not all(
            values := [
                event.get(x)
                for x in ("title", "league", "date", "id", "ppvId")
            ]
        ):
            continue

        name, sport, start_ts, stream_id, ppv_id = values
        stream_id = str(stream_id)
        sport = str(sport)

        if stream_id.lower().startswith(("dl-", "247")):
            continue

        if sport.startswith("24/7"):
            continue

        sport = (
            " ".join(i.capitalize().strip() for i in sport.split("-"))
            if sport.islower()
            else sport
        )

        try:
            event_ts = int(str(start_ts)[:-3])
            event_dt = datetime.fromtimestamp(event_ts, tz=timezone.utc)
        except (ValueError, TypeError):
            continue

        # Sadece başlamasına 30 dk kalan veya başlayalı 30 dk olan canlı maçları al
        if not (start_dt <= event_dt <= end_dt):
            continue

        if poster := event.get("poster"):
            poster = poster if poster.startswith("http") else urljoin(BASE_URL, poster)

        events.append(
            {
                "sport": sport,
                "name": str(name),
                "logo": poster or "",
                "stream_id": stream_id,
                "ppv_id": str(ppv_id),
            }
        )

    return events


def write_m3u(entries: list[dict[str, str]], filename: str = OUTPUT_M3U) -> None:
    lines = ["#EXTM3U"]

    for item in entries:
        title = f"[{item['sport']}] {item['name']} ({TAG})"
        logo_attr = f' tvg-logo="{item["logo"]}"' if item["logo"] else ""
        lines.append(
            f'#EXTINF:-1 tvg-id="{item["tvg-id"]}"{logo_attr} group-title="{item["sport"]}",{title}'
        )
        lines.append(f'#EXTVLCOPT:http-referrer={item["refer"]}')
        lines.append(f'#EXTVLCOPT:http-user-agent={HEADERS["User-Agent"]}')
        lines.append(item["source"])

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    log.info(f"Saved {len(entries)} stream(s) to '{filename}'")


async def scrape() -> None:
    log.info(f'Scraping from "{BASE_URL}"')

    semaphore = asyncio.Semaphore(10)

    async with httpx.AsyncClient(follow_redirects=True) as client:
        events = await get_events(client)

        if not events:
            log.info("No active events found in the +/- 30 min window")
            write_m3u([])
            return

        log.info(f"Processing {len(events)} URL(s)...")

        tasks = [
            process_event(client, semaphore, ev, i)
            for i, ev in enumerate(events, start=1)
        ]

        results = await asyncio.gather(*tasks)
        valid_entries = [res for res in results if res is not None]

    write_m3u(valid_entries)


if __name__ == "__main__":
    asyncio.run(scrape())
