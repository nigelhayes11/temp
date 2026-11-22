#!/usr/bin/env python3
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx

# ------------------------------------------------------------
# AYARLAR
# ------------------------------------------------------------

BASE_URL = "https://damitv.st"
OUTPUT_FILE = "dami.m3u"
TAG = "DAMITV"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

CONCURRENCY = 8
TIMEOUT = 25.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(TAG)


# ------------------------------------------------------------
# VERİ MODELİ
# ------------------------------------------------------------

@dataclass(slots=True)
class DAMIEvent:
    sport: str
    name: str
    stream_id: str
    ppv_id: str
    timestamp: int
    logo: str = ""
    source: str = ""
    refer: str = ""


# ------------------------------------------------------------
# YAYIN ÇÖZÜMLEME
# ------------------------------------------------------------

async def process_event(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    event: DAMIEvent,
    url_num: int,
) -> DAMIEvent | None:
    async with semaphore:
        refer = urljoin(BASE_URL, f"embed/?id={event.stream_id}")
        extract_url = urljoin(BASE_URL, f"papi/extract-url/{event.ppv_id}")

        try:
            resp = await client.get(
                extract_url,
                headers={"Referer": refer},
            )
            if resp.status_code != 200:
                log.warning(f"URL {url_num}) HTTP {resp.status_code} - {event.name}")
                return None

            api_data = resp.json() or {}
            m3u8 = api_data.get("sdUrl") or api_data.get("hlsUrl")

            if not m3u8:
                log.warning(f"URL {url_num}) Kaynak bulunamadı: {event.name}")
                return None

            log.info(f"URL {url_num}) M3U8 yakalandı: {event.name}")
            event.source = m3u8
            event.refer = refer
            return event

        except Exception as exc:
            log.warning(f"URL {url_num}) Hata ({event.name}): {exc}")
            return None


# ------------------------------------------------------------
# ETKİNLİK LİSTESİ ÇEKME
# ------------------------------------------------------------

async def get_events(client: httpx.AsyncClient) -> list[DAMIEvent]:
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(minutes=30)
    end_dt = now + timedelta(minutes=30)

    events: list[DAMIEvent] = []

    try:
        r = await client.get(urljoin(BASE_URL, "papi/matches/all-today"))
        if r.status_code != 200:
            log.error(f"API HTTP {r.status_code}")
            return events
        api_data: list[dict[str, Any]] = r.json() or []
    except Exception as exc:
        log.error(f"API okuma hatası: {exc}")
        return events

    for event in api_data:
        if not isinstance(event, dict):
            continue

        values = [event.get(x) for x in ("title", "league", "date", "id", "ppvId")]
        if not all(values):
            continue

        name, sport, start_ts, stream_id, ppv_id = values
        stream_id = str(stream_id).strip()
        ppv_id = str(ppv_id).strip()
        name = str(name).strip()
        sport = str(sport).strip()

        # 7/24 kanalları atla (istenirse bu 4 satır silinebilir)
        if stream_id.lower().startswith(("dl-", "247")):
            continue
        if sport.startswith("24/7"):
            continue

        sport = (
            " ".join(i.capitalize().strip() for i in sport.split("-"))
            if sport.islower()
            else sport
        )

        # Milisaniye timestamp -> saniye dönüşümü
        try:
            event_ts = int(str(start_ts)[:-3])
            event_dt = datetime.fromtimestamp(event_ts, tz=timezone.utc)
        except ValueError:
            continue

        # Sadece başlama saatine +-30 dk olan canlı maçları al
        if not (start_dt <= event_dt <= end_dt):
            continue

        poster = event.get("poster") or ""
        if poster and not poster.startswith("http"):
            poster = urljoin(BASE_URL, poster)

        events.append(
            DAMIEvent(
                sport=sport,
                name=name,
                logo=poster,
                stream_id=stream_id,
                ppv_id=ppv_id,
                timestamp=event_ts,
            )
        )

    return events


# ------------------------------------------------------------
# M3U DOSYASI OLUŞTURMA (TELEVIZO UYUMLU)
# ------------------------------------------------------------

def write_m3u(events: list[DAMIEvent]) -> None:
    lines = ["#EXTM3U"]

    for ev in events:
        title = f"[{ev.sport}] {ev.name} ({TAG})"
        lines.append(
            f'#EXTINF:-1 tvg-id="Live.Event.us" tvg-name="{title}" '
            f'tvg-logo="{ev.logo}" group-title="{ev.sport}",{title}'
        )
        if ev.refer:
            lines.append(f"#EXTVLCOPT:http-referrer={ev.refer}")
        lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")
        lines.append(ev.source)

    Path(OUTPUT_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info(f"{len(events)} canlı yayın '{OUTPUT_FILE}' dosyasına kaydedildi.")


# ------------------------------------------------------------
# ANA ÇALIŞTIRICI
# ------------------------------------------------------------

async def main() -> None:
    log.info(f'"{BASE_URL}" taranıyor...')

    async with httpx.AsyncClient(
        headers=HEADERS,
        follow_redirects=True,
        timeout=httpx.Timeout(TIMEOUT),
    ) as client:
        events = await get_events(client)

        if not events:
            log.info("Şu an uygun canlı etkinlik bulunamadı.")
            write_m3u([])
            return

        log.info(f"{len(events)} yeni etkinlik işleniyor...")
        semaphore = asyncio.Semaphore(CONCURRENCY)

        tasks = [
            process_event(client, semaphore, ev, i)
            for i, ev in enumerate(events, start=1)
        ]
        results = await asyncio.gather(*tasks)

        valid_events = [ev for ev in results if ev is not None]
        write_m3u(valid_events)


if __name__ == "__main__":
    asyncio.run(main())
