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


async def try_extract(
    client: httpx.AsyncClient,
    target_id: str,
    refer: str,
) -> str | None:
    try:
        response = await client.get(
            urljoin(BASE_URL, f"papi/extract-url/{target_id}"),
            headers={**HEADERS, "Referer": refer},
            timeout=20.0,
        )
        if response.status_code != 200:
            return None
        data = response.json() or {}
        return data.get("sdUrl") or data.get("hlsUrl")
    except Exception:
        return None


async def process_event(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    event: dict[str, Any],
    url_num: int,
) -> dict[str, str] | None:
    refer = urljoin(BASE_URL, f"embed/?id={event['stream_id']}")

    async with semaphore:
        m3u8 = None
        for candidate_id in event["candidate_ids"]:
            if m3u8 := await try_extract(client, candidate_id, refer):
                break

        if not m3u8:
            log.warning(f"URL {url_num}) No M3U8 found -> {event['name']}")
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

        # 24/7 kanalları atla
        if str(stream_id).lower().startswith("247") or str(sport).startswith("24/7"):
            continue

        # Denenecek tüm olası yayın ID'lerini topla (ppvId, substreams, sources, tvChannels)
        candidate_ids: list[str] = []

        if ppv_id := event.get("ppvId"):
            candidate_ids.append(str(ppv_id))

        for sub in event.get("substreams") or []:
            if isinstance(sub, dict) and sub.get("id"):
                candidate_ids.append(str(sub["id"]))

        for src in event.get("sources") or []:
            if isinstance(src, dict) and src.get("id") and src["id"] != "s1":
                candidate_ids.append(str(src["id"]))

        for ch in event.get("tvChannels") or []:
            if isinstance(ch, dict) and ch.get("id"):
                candidate_ids.append(str(ch["id"]))

        candidate_ids.append(str(stream_id))

        # Tekrarlanan ID'leri sırayı bozmadan temizle
        unique_ids = list(dict.fromkeys(candidate_ids))

        # Sadece şu an canlı (live) olanları VEYA ppvId'si tanımlı yaklaşan maçları al
        if status != "live" and not event.get("ppvId"):
            continue

        sport_clean = (
            " ".join(i.capitalize().strip() for i in sport.split("-"))
            if sport.islower()
            else sport
        )

        poster = event.get("poster") or ""
        if poster and not poster.startswith("http"):
            poster = urljoin(BASE_URL, poster)

        events.append(
            {
                "sport": sport_clean,
                "name": name,
                "logo": poster,
                "stream_id": stream_id,
                "candidate_ids": unique_ids,
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
            log.info("No matching events found")
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
