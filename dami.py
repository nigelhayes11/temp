import asyncio
import logging
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
    refer = urljoin(BASE_URL, f"embed/?id={event['stream_id']}")

    async with semaphore:
        try:
            response = await client.get(
                urljoin(BASE_URL, f"papi/extract-url/{event['ppv_id']}"),
                headers={**HEADERS, "Referer": refer},
                timeout=25.0,
            )
            response.raise_for_status()
            api_data = response.json() or {}
        except Exception as e:
            log.warning(f"URL {url_num}) Request failed ({event['name']}): {e}")
            return None

        if not (m3u8 := api_data.get("sdUrl") or api_data.get("hlsUrl")):
            log.warning(f"URL {url_num}) No source found for {event['name']}")
            return None

        log.info(f"URL {url_num}) Captured M3U8 -> {event['name']}")
        return {
            "sport": event["sport"],
            "name": event["name"],
            "logo": event.get("logo") or "",
            "source": m3u8.strip(),
            "refer": refer,
            "tvg-id": "Live.Event.us",
        }


async def get_events(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    try:
        response = await client.get(
            urljoin(BASE_URL, "papi/matches/all-today"),
            headers=HEADERS,
            timeout=15.0,
        )
        response.raise_for_status()
        api_data: list[dict[str, Any]] = response.json() or []
    except Exception as e:
        log.error(f"Failed to fetch API data: {e}")
        return events

    for event in api_data:
        name = event.get("title")
        sport = event.get("league") or event.get("category")
        stream_id = event.get("id")
        status = str(event.get("status", "")).lower()

        if not (name and sport and stream_id):
            continue

        # Sadece canlı (live) veya yaklaşan (upcoming) yayınları al
        if status not in ("live", "upcoming"):
            continue

        # 24/7 kanalları atla (İstersen bu iki if bloğunu silebilirsin)
        if str(stream_id).lower().startswith(("dl-", "247")):
            continue
        if str(sport).startswith("24/7") or str(event.get("category", "")).startswith("24/7"):
            continue

        # ppvId boşsa, substreams içindeki ilk id'yi veya ana stream_id'yi kullan
        ppv_id = event.get("ppvId")
        if not ppv_id:
            substreams = event.get("substreams") or []
            if substreams and isinstance(substreams[0], dict) and substreams[0].get("id"):
                ppv_id = substreams[0]["id"]
            else:
                ppv_id = stream_id

        sport = (
            " ".join(i.capitalize().strip() for i in sport.split("-"))
            if sport.islower()
            else sport
        )

        poster = event.get("poster") or ""
        if poster and not poster.startswith("http"):
            poster = urljoin(BASE_URL, poster)

        events.append(
            {
                "sport": sport,
                "name": name,
                "logo": poster,
                "stream_id": stream_id,
                "ppv_id": ppv_id,
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
            log.info("No events found")
            write_m3u([])
            return

        log.info(f"Processing {len(events)} event(s)...")

        tasks = [
            process_event(client, semaphore, ev, i)
            for i, ev in enumerate(events, start=1)
        ]

        results = await asyncio.gather(*tasks)
        valid_entries = [res for res in results if res is not None]

    write_m3u(valid_entries)


if __name__ == "__main__":
    asyncio.run(scrape())
