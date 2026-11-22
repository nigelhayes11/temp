#!/usr/bin/env python3
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import httpx

# ------------------------------------------------------------
# AYARLAR
# ------------------------------------------------------------

BASE_URL = "https://ondemand.st"
API_URL = f"{BASE_URL}/papi/api/streams"
OUTPUT_FILE = "dami.m3u"
TAG = "DAMITV"

TARGET_CATEGORY = "football"
MAX_HOURS_AHEAD = 24  # Önümüzdeki 24 saatteki maçlar (Hepsi için None yapın)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{BASE_URL}/sport/{TARGET_CATEGORY}",
    "Origin": BASE_URL,
}

TIMEOUT = 25.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(TAG)


@dataclass(slots=True)
class FootballStream:
    title: str
    league: str
    logo: str
    m3u8_url: str
    referer: str
    origin: str


def extract_m3u8_from_embed(embed_url: str) -> tuple[str, str, str]:
    if not embed_url:
        return "", "", ""

    parsed = urlparse(embed_url)
    embed_origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else "https://damitv.st"

    if ".m3u8" in parsed.path.lower():
        return embed_url, embed_origin + "/", embed_origin

    query_params = parse_qs(parsed.query)
    raw_list = query_params.get("url", [])
    if raw_list:
        decoded = unquote(raw_list[0]).strip()
        if ".m3u8" in decoded.lower():
            full_m3u8 = decoded if decoded.startswith("http") else urljoin(embed_origin, decoded)
            return full_m3u8, embed_url, embed_origin

    return "", "", ""


async def fetch_football_streams() -> list[FootballStream]:
    results: list[FootballStream] = []
    now_ts = int(datetime.now(timezone.utc).timestamp())

    async with httpx.AsyncClient(
        headers=HEADERS,
        follow_redirects=True,
        timeout=httpx.Timeout(TIMEOUT),
    ) as client:
        log.info(f"API sorgulanıyor: {API_URL}")
        try:
            resp = await client.get(API_URL)
            if resp.status_code != 200:
                log.error(f"API HTTP {resp.status_code} hatası!")
                return results
            data = resp.json()
        except Exception as exc:
            log.error(f"API bağlantı hatası: {exc}")
            return results

        for cat in data.get("streams", []):
            if str(cat.get("category", "")).strip().lower() != TARGET_CATEGORY:
                continue

            for stream in cat.get("streams", []):
                if stream.get("always_live") == 1 or str(stream.get("id", "")).startswith("247"):
                    continue

                starts_at = stream.get("starts_at")
                if MAX_HOURS_AHEAD and starts_at:
                    if int(starts_at) > now_ts + (MAX_HOURS_AHEAD * 3600):
                        continue

                match_name = str(stream.get("name", "")).strip()
                league = str(stream.get("league", "Football")).strip() or "Football"
                status = str(stream.get("status", "")).strip().lower()
                poster = str(stream.get("poster", "")).strip()
                if poster and not poster.startswith("http"):
                    poster = urljoin(BASE_URL, poster)

                time_tag = ""
                if starts_at:
                    tr_time = datetime.fromtimestamp(int(starts_at) + 10800, tz=timezone.utc)
                    time_tag = tr_time.strftime("%H:%M")

                prefix = "CANLI" if status == "live" else time_tag

                for idx, src in enumerate(stream.get("sources") or [], start=1):
                    src_name = str(src.get("name") or f"Kaynak {idx}").strip()
                    embed_url = str(src.get("embed") or "").strip()

                    m3u8_url, referer, origin = extract_m3u8_from_embed(embed_url)
                    if not m3u8_url:
                        continue

                    title = f"[{prefix}] {match_name} [{src_name}]" if prefix else f"{match_name} [{src_name}]"
                    results.append(
                        FootballStream(
                            title=title,
                            league=league,
                            logo=poster,
                            m3u8_url=m3u8_url,
                            referer=referer,
                            origin=origin,
                        )
                    )

    return results


def write_m3u(streams: list[FootballStream]) -> None:
    lines = ["#EXTM3U"]

    for item in streams:
        full_title = f"[{item.league}] {item.title} ({TAG})"
        lines.append(
            f'#EXTINF:-1 tvg-id="Football.Live" tvg-name="{full_title}" '
            f'tvg-logo="{item.logo}" group-title="{item.league}",{full_title}'
        )
        if item.referer:
            lines.append(f"#EXTVLCOPT:http-referrer={item.referer}")
        if item.origin:
            lines.append(f"#EXTVLCOPT:http-origin={item.origin}")
        lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")
        lines.append(item.m3u8_url)

    Path(OUTPUT_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info(f"Toplam {len(streams)} futbol yayını '{OUTPUT_FILE}' dosyasına kaydedildi.")


async def main() -> None:
    streams = await fetch_football_streams()
    write_m3u(streams)


if __name__ == "__main__":
    asyncio.run(main())
