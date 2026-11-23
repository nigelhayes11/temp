import asyncio
import html
import json
import logging
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("NBAREPLAY")

BASE_URL = "https://basketballreplays.net"
OUTPUT_FILE = "nbareplay.m3u"
PAGES_TO_SCRAPE = 2
MAX_CONCURRENT = 8

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{BASE_URL}/",
}


async def resolve_okru(client: httpx.AsyncClient, embed_url: str) -> str | None:
    """ok.ru/videoembed sayfasındaki JSON verisinden doğrudan m3u8 veya mp4 linkini çıkarır."""
    try:
        res = await client.get(embed_url, headers=HEADERS, timeout=15.0)
        soup = BeautifulSoup(res.text, "html.parser")
        player_div = soup.find("div", attrs={"data-options": True})
        if not player_div:
            return None

        raw_options = html.unescape(player_div["data-options"])
        options_json = json.loads(raw_options)
        metadata_str = options_json.get("flashvars", {}).get("metadata")
        if not metadata_str:
            return None

        metadata = json.loads(metadata_str)

        # 1. Öncelik: HLS (.m3u8) akışı
        if hls_url := metadata.get("hlsManifestUrl"):
            return hls_url

        # 2. Yedek: En yüksek kaliteli doğrudan MP4 akışı
        videos = metadata.get("videos", [])
        quality_order = {"ultra": 5, "quad": 4, "full": 3, "hd": 2, "sd": 1, "low": 0}
        videos_sorted = sorted(
            [v for v in videos if v.get("url")],
            key=lambda x: quality_order.get(x.get("name", ""), -1),
            reverse=True,
        )
        if videos_sorted:
            return videos_sorted[0]["url"]

    except Exception as e:
        log.debug(f"ok.ru çözümleme hatası ({embed_url}): {e}")
    return None


async def resolve_byse(client: httpx.AsyncClient, embed_url: str) -> str | None:
    """bysesukior.com / vidara benzeri oynatıcılardan m3u8 çıkarmayı dener."""
    try:
        parsed = urlparse(embed_url)
        video_id = parsed.path.rstrip("/").split("/")[-1]
        domain = f"{parsed.scheme}://{parsed.netloc}"

        res = await client.get(
            embed_url,
            headers={**HEADERS, "Referer": f"{BASE_URL}/"},
            timeout=12.0,
        )
        m3u8_match = re.search(r"""["'](https?://[^"']+\.m3u8[^"']*)["']""", res.text)
        if m3u8_match:
            return m3u8_match.group(1).replace("\\/", "/")

        # Byse / Vidara API uç noktalarını dene
        for api_path in (f"/api/videos/{video_id}", f"/api/stream/{video_id}"):
            api_res = await client.get(
                urljoin(domain, api_path),
                headers={**HEADERS, "Referer": embed_url, "Accept": "application/json"},
                timeout=10.0,
            )
            if api_res.status_code == 200:
                m = re.search(r"""["'](https?://[^"']+\.m3u8[^"']*)["']""", api_res.text)
                if m:
                    return m.group(1).replace("\\/", "/")
    except Exception as e:
        log.debug(f"Byse çözümleme hatası ({embed_url}): {e}")
    return None


async def get_games_from_page(
    client: httpx.AsyncClient, page: int
) -> list[dict[str, str]]:
    url = f"{BASE_URL}/?page={page}"
    games: list[dict[str, str]] = []
    try:
        res = await client.get(url, headers=HEADERS, timeout=15.0)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        for item in soup.select("div.h_post"):
            a = item.select_one("div.h_post_title > a")
            if not a or not a.get("href"):
                continue
            title = a.get_text(strip=True).replace(" - Full Game Replay", "")
            href = urljoin(BASE_URL, a["href"])
            img = item.select_one("img")
            icon = urljoin(BASE_URL, img["src"]) if img and img.get("src") else ""
            games.append({"title": title, "url": href, "logo": icon})
    except Exception as e:
        log.error(f"Sayfa {page} çekilemedi: {e}")

    return games


async def scrape_game_streams(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    game: dict[str, str],
) -> list[dict[str, str]]:
    async with semaphore:
        streams: list[dict[str, str]] = []
        try:
            res = await client.get(game["url"], headers=HEADERS, timeout=15.0)
            soup = BeautifulSoup(res.text, "html.parser")

            watch_btn = soup.select_one("a.su-button[href*='nhlgamestoday']")
            if watch_btn and watch_btn.get("href"):
                res = await client.get(watch_btn["href"], headers=HEADERS, timeout=15.0)
                soup = BeautifulSoup(res.text, "html.parser")

            seen_iframes: set[str] = set()
            for iframe in soup.select("iframe"):
                src = iframe.get("src")
                if not src:
                    continue
                if src.startswith("//"):
                    src = "https:" + src
                if src in seen_iframes:
                    continue
                seen_iframes.add(src)

                stream_url = None
                referer = src

                if "ok.ru" in src:
                    stream_url = await resolve_okru(client, src)
                    referer = "https://ok.ru/"
                elif "bysesukior" in src or "vidara" in src:
                    stream_url = await resolve_byse(client, src)

                if stream_url:
                    host = urlparse(src).netloc
                    streams.append(
                        {
                            "title": f"{game['title']} [Part {len(streams)+1} - {host}]",
                            "group": "NBA Replays",
                            "logo": game["logo"],
                            "referer": referer,
                            "url": stream_url,
                        }
                    )

            if streams:
                log.info(f"✓ {game['title']} ({len(streams)} akış eklendi)")
            else:
                log.warning(f"✗ Akış çözülemedi: {game['title']}")

        except Exception as e:
            log.warning(f"Maç işleme hatası ({game['title']}): {e}")

        return streams


def write_m3u(streams: list[dict[str, str]], filename: str) -> None:
    lines = ["#EXTM3U"]
    for s in streams:
        lines.append(
            f'#EXTINF:-1 tvg-id="NBA.Replay" tvg-logo="{s["logo"]}" group-title="{s["group"]}",{s["title"]}'
        )
        lines.append(f"#EXTVLCOPT:http-referrer={s['referer']}")
        lines.append(f"#EXTVLCOPT:http-user-agent={HEADERS['User-Agent']}")
        lines.append(s["url"])

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    log.info(f"Toplam {len(streams)} yayın '{filename}' dosyasına kaydedildi.")


async def main() -> None:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
        all_games: list[dict[str, str]] = []
        for page in range(1, PAGES_TO_SCRAPE + 1):
            all_games.extend(await get_games_from_page(client, page))

        if not all_games:
            log.error("Maç listesi alınamadı.")
            write_m3u([], OUTPUT_FILE)
            return

        log.info(f"{len(all_games)} maç taranıyor...")
        tasks = [scrape_game_streams(client, semaphore, game) for game in all_games]
        results = await asyncio.gather(*tasks)

        flat_streams = [item for sublist in results for item in sublist]
        write_m3u(flat_streams, OUTPUT_FILE)


if __name__ == "__main__":
    asyncio.run(main())
