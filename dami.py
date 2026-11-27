import asyncio
import logging
import re
from typing import Any
from urllib.parse import quote, urljoin

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


async def extract_ppv(
    client: httpx.AsyncClient,
    ppv_id: str,
    refer: str,
) -> str | None:
    try:
        r = await client.get(
            urljoin(BASE_URL, f"papi/extract-url/{ppv_id}"),
            headers={**HEADERS, "Referer": refer},
            timeout=20.0,
        )
        if r.status_code == 200:
            data = r.json() or {}
            return data.get("sdUrl") or data.get("hlsUrl")
    except Exception:
        pass
    return None


async def extract_channel(
    client: httpx.AsyncClient,
    channel_id: str,
    stream_id: str,
    refer: str,
) -> str | None:
    endpoints = [
        f"papi/channel/{channel_id}",
        f"papi/stream/{channel_id}",
        f"papi/c/{channel_id}",
        f"papi/tv/{channel_id}",
        f"papi/extract-url/{channel_id}",
        f"papi/source/{stream_id}",
    ]

    for ep in endpoints:
        try:
            r = await client.get(
                urljoin(BASE_URL, ep),
                headers={**HEADERS, "Referer": refer},
                timeout=15.0,
            )
            if r.status_code == 200:
                text = r.text
                if ".m3u8" in text:
                    if m := re.search(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', text):
                        return m.group(0)
                try:
                    data = r.json()
                    if isinstance(data, dict):
                        for key in ("url", "hlsUrl", "sdUrl", "stream", "src", "file"):
                            if val := data.get(key):
                                if ".m3u8" in str(val):
                                    return str(val)
                except Exception:
                    pass
        except Exception:
            continue

    for embed_path in (f"embed/?id={stream_id}", f"embed/?c={channel_id}", f"c/{channel_id}"):
        try:
            r = await client.get(
                urljoin(BASE_URL, embed_path),
                headers={**HEADERS, "Referer": BASE_URL},
                timeout=15.0,
            )
            if r.status_code == 200:
                if m := re.search(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', r.text):
                    return m.group(0)
        except Exception:
            continue

    return None


async def process_event(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    event: dict[str, Any],
    url_num: int,
) -> dict[str, str] | None:
    stream_id = event["stream_id"]
    refer = urljoin(BASE_URL, f"embed/?id={stream_id}")

    async with semaphore:
        m3u8 = None

        if event.get("ppv_id"):
            m3u8 = await extract_ppv(client, event["ppv_id"], refer)

        if not m3u8 and event.get("channel_ids"):
            for ch_id in event["channel_ids"]:
                if m3u8 := await extract_channel(client, ch_id, stream_id, refer):
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
            "refer": f"{BASE_URL}/",
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

        if str(stream_id).lower().startswith("247") or str(sport).startswith("24/7"):
            continue

        ppv_id = str(event.get("ppvId") or "").strip()
        channel_ids = [
            str(ch["id"])
            for ch in (event.get("tvChannels") or [])
            if isinstance(ch, dict) and ch.get("id")
        ]

        if status != "live" and not ppv_id:
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
                "stream_id": str(stream_id),
                "ppv_id": ppv_id,
                "channel_ids": channel_ids,
            }
        )

    return events


def write_m3u(entries: list[dict[str, str]], filename: str = OUTPUT_M3U) -> None:
    lines = ["#EXTM3U"]
    ua_encoded = quote(HEADERS["User-Agent"], safe="")

    for item in entries:
        title = f"[{item['sport']}] {item['name']} ({TAG})"
        logo_attr = f' tvg-logo="{item["logo"]}"' if item["logo"] else ""
        ref_encoded = quote(item["refer"], safe="")

        lines.append(
            f'#EXTINF:-1 tvg-id="{item["tvg-id"]}"{logo_attr} group-title="{item["sport"]}",{title}'
        )
        lines.append(f'#EXTVLCOPT:http-referrer={item["refer"]}')
        lines.append(f'#EXTVLCOPT:http-user-agent={HEADERS["User-Agent"]}')
        lines.append(f'{item["source"]}|Referer={ref_encoded}&User-Agent={ua_encoded}')

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
