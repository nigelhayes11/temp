#!/usr/bin/env python3
import asyncio
import logging
import re
from dataclasses import dataclass
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

# Sadece çekmek istediğiniz kategori (küçük harfle)
TARGET_CATEGORY = "football"

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


# ------------------------------------------------------------
# VERİ MODELİ
# ------------------------------------------------------------

@dataclass(slots=True)
class FootballStream:
    title: str
    league: str
    logo: str
    m3u8_url: str
    referer: str


# ------------------------------------------------------------
# EMBED -> M3U8 ÇÖZÜMLEYİCİ
# ------------------------------------------------------------

def extract_m3u8_from_embed(embed_url: str) -> tuple[str, str]:
    """
    API dokümantasyonundaki örnek:
    https://damitv.st...
    İçindeki 'url' parametresini çözüp tam m3u8 adresine çevirir.
    """
    if not embed_url:
        return "", ""

    parsed = urlparse(embed_url)
    base_domain = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else BASE_URL

    # 1. Doğrudan .m3u8 ise
    if ".m3u8" in parsed.path.lower():
        return embed_url, base_domain + "/"

    # 2. Query içindeki 'url=' parametresini çöz
    query_params = parse_qs(parsed.query)
    raw_stream = query_params.get("url", [""])[0]
    if raw_stream:
        decoded = unquote(raw_stream)
        full_m3u8 = urljoin(base_domain, decoded)
        return full_m3u8, embed_url

    return "", ""


async def fallback_scrape_embed(client: httpx.AsyncClient, embed_url: str) -> str:
    """Eğer embed linkinde url= parametresi yoksa sayfayı açıp içinden .m3u8 arar."""
    try:
        resp = await client.get(embed_url, headers={"Referer": f"{BASE_URL}/"})
        if resp.status_code == 200:
            matches = re.findall(
                r"""https?://[^\s"'<>]+\.m3u8(?:\?[^\s"'<>]*)?""",
                resp.text,
                re.IGNORECASE,
            )
            if matches:
                return matches[0].rstrip("\\);,")
    except Exception:
        pass
    return ""


# ------------------------------------------------------------
# FOOTBALL CANLI YAYINLARI ÇEKME
# ------------------------------------------------------------

async def fetch_football_streams() -> list[FootballStream]:
    results: list[FootballStream] = []

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

        categories = data.get("streams", [])
        for cat in categories:
            cat_name = str(cat.get("category", "")).strip().lower()

            # Sadece 'football' kategorisini al
            if cat_name != TARGET_CATEGORY:
                continue

            for stream in cat.get("streams", []):
                # 7/24 kanalları atla (isterseniz bu bloğu silebilirsiniz)
                if stream.get("always_live") == 1 or str(stream.get("id", "")).startswith("247"):
                    continue

                # Sadece şu an CANLI (live) olan maçları al
                status = str(stream.get("status", "")).strip().lower()
                if status != "live":
                    continue

                match_name = str(stream.get("name", "")).strip()
                league = str(stream.get("league", "Football")).strip() or "Football"
                poster = str(stream.get("poster", "")).strip()
                if poster and not poster.startswith("http"):
                    poster = urljoin(BASE_URL, poster)

                sources = stream.get("sources") or []
                for idx, src in enumerate(sources, start=1):
                    src_name = str(src.get("name") or f"Kaynak {idx}").strip()
                    embed_url = str(src.get("embed") or "").strip()

                    m3u8_url, referer = extract_m3u8_from_embed(embed_url)

                    # Eğer parametreden çıkmadıysa embed sayfasının içine bak
                    if not m3u8_url and embed_url:
                        m3u8_url = await fallback_scrape_embed(client, embed_url)
                        referer = embed_url

                    if m3u8_url:
                        results.append(
                            FootballStream(
                                title=f"{match_name} [{src_name}]",
                                league=league,
                                logo=poster,
                                m3u8_url=m3u8_url,
                                referer=referer,
                            )
                        )
                        log.info(f"Yakalandı: {match_name} [{src_name}]")

    return results


# ------------------------------------------------------------
# M3U DOSYASI YAZMA (TELEVIZO UYUMLU)
# ------------------------------------------------------------

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
        lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")
        lines.append(item.m3u8_url)

    Path(OUTPUT_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info(f"Toplam {len(streams)} canlı futbol yayını '{OUTPUT_FILE}' dosyasına kaydedildi.")


async def main() -> None:
    streams = await fetch_football_streams()
    write_m3u(streams)


if __name__ == "__main__":
    asyncio.run(main())
