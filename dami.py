#!/usr/bin/env python3
import asyncio
import html
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
CONCURRENCY = 5

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
    cache_key: str
    m3u8_url: str = ""
    referer: str = ""
    origin: str = ""


def build_cache_key(embed_url: str) -> str:
    parsed = urlparse(embed_url)
    url_list = parse_qs(parsed.query).get("url", [])
    if url_list and isinstance(url_list, str):
        return unquote(url_list).strip()
    return embed_url.strip()


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
                        cache_key=build_cache_key(embed_url),
                    )
                )

    return items


async def resolve_unique_embed(
    context,
    semaphore: asyncio.Semaphore,
    cache_key: str,
    embed_url: str,
    cache: dict[str, tuple[str, str, str]],
) -> None:
    async with semaphore:
        page = await context.new_page()
        captured_url = ""
        found_event = asyncio.Event()

        def handle_request(request):
            nonlocal captured_url
            url = request.url
            low = url.lower()
            if ".m3u8" in low and "player/hls" not in low:
                if ("ct=" in low or "tk=" in low) or not captured_url:
                    captured_url = url
                    if "ct=" in low or "tk=" in low:
                        found_event.set()

        page.on("request", handle_request)

        try:
            # Sandbox Error'u asmak icin ondemand.st baglaminda gercek iframe icinde ac
            safe_src = html.escape(embed_url, quote=True)
            wrapper_html = f"""
            <!DOCTYPE html>
            <html><body>
              <iframe src="{safe_src}" width="800" height="450" allowfullscreen></iframe>
            </body></html>
            """
            await page.route(
                f"{BASE_URL}/wrapper-frame",
                lambda route: route.fulfill(status=200, content_type="text/html", body=wrapper_html),
            )
            await page.goto(f"{BASE_URL}/wrapper-frame", wait_until="domcontentloaded", timeout=12000)
            await asyncio.wait_for(found_event.wait(), timeout=10.0)
        except Exception:
            pass
        finally:
            await page.close()

        if captured_url:
            parsed_embed = urlparse(embed_url)
            embed_org = f"{parsed_embed.scheme}://{parsed_embed.netloc}"
            cache[cache_key] = (captured_url, embed_org + "/", embed_org)
            log.info(f"İmzalı M3U8 yakalandı: {captured_url[:80]}...")
        else:
            cache[cache_key] = ("", "", "")
            log.warning(f"Token üretilmedi: {cache_key}")


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

    unique_embeds: dict[str, str] = {}
    for item in items:
        if item.cache_key not in unique_embeds:
            unique_embeds[item.cache_key] = item.embed_url

    log.info(f"{len(items)} maç kaynağı için {len(unique_embeds)} benzersiz kanal çözülüyor...")
    semaphore = asyncio.Semaphore(CONCURRENCY)
    cache: dict[str, tuple[str, str, str]] = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
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
            resolve_unique_embed(context, semaphore, key, url, cache)
            for key, url in unique_embeds.items()
        ]
        await asyncio.gather(*tasks)
        await browser.close()

    valid_streams: list[MatchSource] = []
    for item in items:
        m3u8, ref, org = cache.get(item.cache_key, ("", "", ""))
        if m3u8:
            item.m3u8_url = m3u8
            item.referer = ref
            item.origin = org
            valid_streams.append(item)

    write_m3u(valid_streams)


if __name__ == "__main__":
    asyncio.run(main())
