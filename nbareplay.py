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
PAGES_TO_SCRAPE = 2  # Taranacak sayfa sayısı (her sayfada ~12-15 maç bulunur)
MAX_CONCURRENT = 10

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": f"{BASE_URL}/",
}

M3U8_PATTERN = re.compile(r"""["'](https?://[^"']+\.m3u8[^"']*)["']""", re.IGNORECASE)


async def extract_m3u8_from_embed(
    client: httpx.AsyncClient, embed_url: str
) -> tuple[str, str] | None:
    """Embed/Vidara sayfasından doğrudan .m3u8 akış linkini ve gerekli Referer bilgisini çıkarır."""
    try:
        res = await client.get(
            embed_url,
            headers={**HEADERS, "Referer": embed_url},
            timeout=12.0,
        )
        if res.status_code >= 400:
            return None

        match = M3U8_PATTERN.search(res.text)
        if match:
            m3u8_url = match.group(1).replace("\\/", "/")
            return m3u8_url, embed_url
    except Exception as e:
        log.debug(f"Embed tarama hatası ({embed_url}): {e}")
    return None


async def get_games_from_page(
    client: httpx.AsyncClient, page: int
) -> list[dict[str, str]]:
    """Ana sayfadan NBA maç başlıklarını, detay linklerini ve kapak görsellerini toplar."""
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
    """Tek bir maç sayfasına girip tüm part/kaynak M3U8 linklerini toplar."""
    async with semaphore:
        streams: list[dict[str, str]] = []
        try:
            res = await client.get(game["url"], headers=HEADERS, timeout=15.0)
            soup = BeautifulSoup(res.text, "html.parser")

            watch_btn = soup.select_one("a.su-button[href*='nhlgamestoday']")
            if watch_btn and watch_btn.get("href"):
                redirect_url = watch_btn["href"]
                res = await client.get(redirect_url, headers=HEADERS, timeout=15.0)
                soup = BeautifulSoup(res.text, "html.parser")

            seen_iframes: set[str] = set()
            part_index = 1

            for iframe in soup.select("iframe"):
                src = iframe.get("src")
                if not src:
                    continue
                if src.startswith("//"):
                    src = "https:" + src
                if src in seen_iframes:
                    continue
                seen_iframes.add(src)

                host = urlparse(src).netloc
                extracted = await extract_m3u8_from_embed(client, src)

                if extracted:
                    m3u8_url, referer = extracted
                    part_label = f"Part {part_index}" if len(seen_iframes) > 1 else "Full"
                    streams.append(
                        {
                            "title": f"{game['title']} [{part_label} - {host}]",
                            "group": "NBA Replays",
                            "logo": game["logo"],
                            "referer": referer,
                            "url": m3u8_url,
                        }
                    )
                    part_index += 1

            if streams:
                log.info(f"✓ {game['title']} ({len(streams)} kaynak bulundu)")
            else:
                log.warning(f"✗ Doğrudan M3U8 bulunamadı: {game['title']}")

        except Exception as e:
            log.warning(f"Maç işleme hatası ({game['title']}): {e}")

        return streams


def write_m3u(streams: list[dict[str, str]], filename: str) -> None:
    lines = ["#EXTM3U"]
    for s in streams:
        extinf = (
            f'#EXTINF:-1 tvg-id="NBA.Replay" '
            f'tvg-logo="{s["logo"]}" '
            f'group-title="{s["group"]}",{s["title"]}'
        )
        lines.append(extinf)
        lines.append(f"#EXTVLCOPT:http-referrer={s['referer']}")
        lines.append(f"#EXTVLCOPT:http-user-agent={HEADERS['User-Agent']}")
        lines.append(s["url"])

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    log.info(f"Toplam {len(streams)} yayın '{filename}' dosyasına kaydedildi.")


async def main() -> None:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
        log.info(f'"{BASE_URL}" üzerinden son NBA maç tekrarları taranıyor...')

        all_games: list[dict[str, str]] = []
        for page in range(1, PAGES_TO_SCRAPE + 1):
            page_games = await get_games_from_page(client, page)
            all_games.extend(page_games)

        if not all_games:
            log.error("Hiçbir NBA maçı bulunamadı.")
            write_m3u([], OUTPUT_FILE)
            return

        log.info(f"{len(all_games)} maç bulundu, yayın akışları ayıklanıyor...")
        tasks = [scrape_game_streams(client, semaphore, game) for game in all_games]
        results = await asyncio.gather(*tasks)

        flat_streams = [item for sublist in results for item in sublist]
        write_m3u(flat_streams, OUTPUT_FILE)


if __name__ == "__main__":
    asyncio.run(main())
