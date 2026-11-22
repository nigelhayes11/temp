#!/usr/bin/env python3
import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import httpx
from playwright.async_api import async_playwright

BASE_URL = "https://ondemand.st"
API_URL = f"{BASE_URL}/papi/api/streams"
OUTPUT_FILE = "dami.m3u"
TAG = "DAMITV"

TARGET_CATEGORY = "football"
MAX_HOURS_AHEAD = 6
CONCURRENCY = 4

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "*/*",
    "Referer": f"{BASE_URL}/sport/{TARGET_CATEGORY}",
    "Origin": BASE_URL,
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(TAG)


@dataclass(slots=True)
class MatchSource:
    title: str
    league: str
    logo: str
    embed_url: str
    m3u8_url: str = ""
    referer: str = ""
    origin: str = ""


async def get_football_list(client: httpx.AsyncClient) -> list[MatchSource]:
    items: list[MatchSource] = []
    now_ts = int(datetime.now(timezone.utc).timestamp())

    try:
        resp = await client.get(API_URL)
        if resp.status_code != 200:
            log.error(f"API HTTP {resp.status_code}")
            return items
        data = resp.json()
    except Exception as exc:
        log.error(f"API hatası: {exc}")
        return items

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
                if not embed_url:
                    continue

                title = f"[{prefix}] {match_name} [{src_name}]" if prefix else f"{match_name} [{src_name}]"
                items.append(
                    MatchSource(
                        title=title,
                        league=league,
                        logo=poster,
                        embed_url=embed_url,
                    )
                )

    return items


async def capture_signed_m3u8(
    context,
    semaphore: asyncio.Semaphore,
    item: MatchSource,
    cache: dict[str, tuple[str, str, str]],
) -> MatchSource | None:
    parsed_embed = urlparse(item.embed_url)
    raw_target = parse_qs(parsed_embed.query).get("url", [item.embed_url])
    cache_key = unquote(raw_target)

    if cache_key in cache:
        m3u8, ref, org = cache[cache_key]
        if m3u8:
            item.m3u8_url, item.referer, item.origin = m3u8, ref, org
            return item
        return None

    async with semaphore:
        if cache_key in cache:
            m3u8, ref, org = cache[cache_key]
            if m3u8:
                item.m3u8_url, item.referer, item.origin = m3u8, ref, org
                return item
            return None

        page = await context.new_page()
        captured_url = ""
        found_event = asyncio.Event()

        def handle_request(request):
            nonlocal captured_url
            url = request.url
            if ".m3u8" in url.lower() and not captured_url:
                captured_url = url
                found_event.set()

        page.on("request", handle_request)

        try:
            await page.goto(
                item.embed_url,
                referer=f"{BASE_URL}/",
                wait_until="domcontentloaded",
                timeout=15000,
            )
            await asyncio.wait_for(found_event.wait(), timeout=8.0)
        except Exception:
            pass
        finally:
            await page.close()

        if captured_url:
            embed_org = f"{parsed_embed.scheme}://{parsed_embed.netloc}"
            cache[cache_key] = (captured_url, embed_org + "/", embed_org)
            item.m3u8_url = captured_url
            item.referer = embed_org + "/"
            item.origin = embed_org
            log.info(f"İmzalı M3U8 yakalandı: {item.title}")
            return item

        cache[cache_key] = ("", "", "")
        log.warning(f"Token alınamadı: {item.title}")
        return None


def write_m3u(streams: list[MatchSource]) -> None:
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
    log.info(f"Toplam {len(streams)} imzalı yayın '{OUTPUT_FILE}' dosyasına kaydedildi.")


async def main() -> None:
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20.0) as client:
        items = await get_football_list(client)

    if not items:
        log.info("Uygun futbol maçı bulunamadı.")
        write_m3u([])
        return

    log.info(f"{len(items)} kaynak için imzalı token çözülüyor...")
    semaphore = asyncio.Semaphore(CONCURRENCY)
    cache: dict[str, tuple[str, str, str]] = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            user_agent=USER_AGENT,
            extra_http_headers={"Referer": f"{BASE_URL}/"},
        )

        await context.route(
            re.compile(r"\.(png|jpg|jpeg|gif|webp|svg|css|woff2?)$", re.I),
            lambda route: route.abort(),
        )

        tasks = [
            capture_signed_m3u8(context, semaphore, item, cache)
            for item in items
        ]
        results = await asyncio.gather(*tasks)
        await browser.close()

    valid_streams = [r for r in results if r is not None]
    write_m3u(valid_streams)


if __name__ == "__main__":
    asyncio.run(main())
