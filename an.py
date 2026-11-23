import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote, urlencode, urljoin

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("STRMFREE")

BASE_URL = "https://streamfree.top"
OUTPUT_FILE = "strmfree.m3u"
TAG = "STRMFREE"


@dataclass(slots=True)
class STFEvent:
    sport: str
    name: str
    category: str
    stream_key: str
    logo: str | None = None


async def fetch_json(
    client: httpx.AsyncClient, url: str, params: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    try:
        r = await client.get(url, params=params, headers={"Referer": BASE_URL})
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.debug(f"İstek hatası ({url}): {e}")
        return None


async def process_event(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    ev: STFEvent,
    url_num: int,
) -> dict[str, str] | None:
    async with semaphore:
        quality_info = await fetch_json(
            client, urljoin(BASE_URL, f"api/stream-status/{ev.stream_key}")
        )
        if not quality_info or not quality_info.get("available"):
            log.warning(f"URL {url_num}) Yayın aktif değil: {ev.name}")
            return None

        sources = quality_info.get("sources")
        if not sources:
            log.warning(f"URL {url_num}) Kaynak bulunamadı: {ev.name}")
            return None

        quality_sources = {
            f"{quality}{source_num}": value
            for source_num, source_data in sources.items()
            for quality, value in source_data.get("qualities", {}).items()
        }

        available_quals = sorted(
            [qual.split("p") for qual, flag in quality_sources.items() if flag],
            key=lambda x: int(x[-1]),
        )

        if not available_quals:
            log.warning(f"URL {url_num}) Uygun kalite bulunamadı: {ev.name}")
            return None

        qual, num = f"{available_quals[0][0]}p", available_quals[0][-1]
        num = "" if num == "1" else num

        server_name = "cdn"
        server_info = await fetch_json(
            client, urljoin(BASE_URL, f"get-stream-key/{ev.stream_key}")
        )
        if server_info:
            server_name = server_info.get("server_name", "cdn")

        try:
            stream_res = await client.get(
                urljoin(BASE_URL, f"embed/{ev.category}/{ev.stream_key}{num}"),
                params={"quality": qual, "category": ev.category},
                timeout=25.0,
            )
            stream_res.raise_for_status()
        except Exception as e:
            log.warning(f"URL {url_num}) Embed sayfası alınamadı: {e}")
            return None

        ptrn = re.compile(r"_0x\s+=\s+(.*?);", re.S)
        match = ptrn.search(stream_res.text)
        if not match:
            log.warning(f"URL {url_num}) Yayın token bilgisi bulunamadı.")
            return None

        try:
            m3u_info = json.loads(match[1])[f"{ev.stream_key}{qual}"]
            query = urlencode(m3u_info)
        except Exception as e:
            log.warning(f"URL {url_num}) JSON ayrıştırma hatası: {e}")
            return None

        m3u8_url = urljoin(
            BASE_URL,
            f"live-{server_name}/{ev.stream_key}{qual}{num}/index.m3u8?{query}",
        )
        log.info(f"URL {url_num}) M3U8 yakalandı: [{ev.sport}] {ev.name}")

        return {
            "title": f"[{ev.sport}] {ev.name} ({TAG})",
            "group": ev.sport,
            "logo": ev.logo or "",
            "url": m3u8_url,
        }


async def get_events(client: httpx.AsyncClient) -> list[STFEvent]:
    now = datetime.now(timezone.utc)
    start_ts = (now - timedelta(hours=2)).timestamp()
    now_ts = now.timestamp()

    api_data = await fetch_json(client, urljoin(BASE_URL, "api/v1/streams"))
    if not api_data:
        log.error("API verisi çekilemedi.")
        return []

    events: list[STFEvent] = []
    for stream_info in api_data.get("streams", []):
        values = [
            stream_info.get(k)
            for k in ("league", "category", "name", "match_timestamp", "stream_key")
        ]
        if not all(values):
            continue

        sport, category, name, event_time, stream_key = values

        if not (start_ts <= (event_time + 1800) <= now_ts):
            continue

        events.append(
            STFEvent(
                sport=sport,
                name=name,
                category=category,
                stream_key=quote(stream_key),
                logo=stream_info.get("thumbnail_url"),
            )
        )

    return events


def write_m3u(streams: list[dict[str, str]], filename: str) -> None:
    lines = ["#EXTM3U"]
    for s in streams:
        extinf = (
            f'#EXTINF:-1 tvg-id="Live.Event.us" '
            f'tvg-logo="{s["logo"]}" '
            f'group-title="{s["group"]}",{s["title"]}'
        )
        lines.append(extinf)
        lines.append(f"#EXTVLCOPT:http-referrer={BASE_URL}/")
        lines.append(s["url"])

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    log.info(f"Toplam {len(streams)} yayın '{filename}' dosyasına yazıldı.")


async def main() -> None:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    semaphore = asyncio.Semaphore(10)

    async with httpx.AsyncClient(headers=headers, timeout=15.0, follow_redirects=True) as client:
        log.info(f'"{BASE_URL}" üzerinden aktif maçlar taranıyor...')
        events = await get_events(client)

        if not events:
            log.info("Şu an aktif yayın bulunamadı.")
            write_m3u([], OUTPUT_FILE)
            return

        log.info(f"{len(events)} aktif yayın bulundu, linkler çekiliyor...")
        tasks = [
            process_event(client, semaphore, ev, i)
            for i, ev in enumerate(events, start=1)
        ]
        results = await asyncio.gather(*tasks)

        valid_streams = [res for res in results if res is not None]
        write_m3u(valid_streams, OUTPUT_FILE)


if __name__ == "__main__":
    asyncio.run(main())

