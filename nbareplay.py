import asyncio
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
MAX_CONCURRENT = 6

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{BASE_URL}/",
}


async def resolve_okru(client: httpx.AsyncClient, embed_url: str) -> str | None:
    """m.ok.ru videoPlayerMetadata API üzerinden doğrudan m3u8 veya mp4 linkini çeker."""
    match = re.search(r"videoembed/(\d+)", embed_url)
    if not match:
        return None

    video_id = match.group(1)
    api_url = f"https://ok.ru{video_id}"
    mobile_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13; SM-G991B) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
        ),
        "Referer": f"https://ok.ru{video_id}",
        "X-Requested-With": "XMLHttpRequest",
    }

    try:
        res = await client.post(api_url, headers=mobile_headers, timeout=15.0)
        if res.status_code != 200:
            return None

        data = res.json()

        # 1. Öncelik: HLS (.m3u8) akışı
        if hls_url := (data.get("hlsManifestUrl") or data.get("hlsMasterPlaylistUrl")):
            return hls_url

        # 2. Yedek: En yüksek kaliteli MP4 akışı
        videos = data.get("videos", [])
        quality_order = {"ultra": 5, "quad": 4, "full": 3, "hd": 2, "sd": 1, "low": 0}
        videos_sorted = sorted(
            [v for v in videos if v.get("url")],
            key=lambda x: quality_order.get(x.get("name", ""), -1),
            reverse=True,
        )
        if videos_sorted:
            return videos_sorted["url"]

    except Exception as e:
        log.debug(f"m.ok.ru API hatası ({video_id}): {e}")

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

            if not any(g["url"] == href for g in games):
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

            seen_iframes: set[str] = set()
            part_num = 1

            for iframe in soup.select("iframe"):
                src = iframe.get("src") or iframe.get("data-src")
                if not src:
                    continue
                if src.startswith("//"):
                    src = "https:" + src
                if src in seen_iframes:
                    continue
                seen_iframes.add(src)

                host = urlparse(src).netloc
                if "ok.ru" in host:
                    stream_url = await resolve_okru(client, src)
                    if stream_url:
                        streams.append(
                            {
                                "title": f"{game['title']} [Part {part_num}]",
                                "group": "NBA Replays",
                                "logo": game["logo"],
                                "referer": "https://m.ok.ru/",
                                "url": stream_url,
                            }
                        )
                        part_num += 1

            if streams:
                log.info(f"✓ Yakalandı ({len(streams)} part): {game['title']}")
            else:
                log.warning(f"✗ ok.ru akışı bulunamadı: {game['title']}")

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
        lines.append(
            "#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
        )
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

        log.info(f"Toplam {len(all_games)} maç bulundu, m.ok.ru API üzerinden yayınlar çekiliyor...")
        if not all_games:
            write_m3u([], OUTPUT_FILE)
            return

        tasks = [scrape_game_streams(client, semaphore, game) for game in all_games]
        results = await asyncio.gather(*tasks)

        flat_streams = [item for sublist in results for item in sublist]
        write_m3u(flat_streams, OUTPUT_FILE)


if __name__ == "__main__":
    asyncio.run(main())
