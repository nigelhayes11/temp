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
log = logging.getLogger("NBAVIDEO")

BASE_URL = "https://basketball-video.com"
LIST_URL = f"{BASE_URL}/2026-27-nba-replays"
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

REDIRECT_DOMAINS = (
    "nfl-replays",
    "nfl-video",
    "basketball-video",
    "nbaontv",
    "gamesontvtoday",
    "nbatraderumors",
    "nhlgamestoday",
)

M3U8_OR_MP4_PATTERN = re.compile(
    r"""["'](https?://[^"'\s<>]+?\.(?:m3u8|mp4)[^"'\s<>]*)["']""",
    re.IGNORECASE,
)


async def resolve_okru(client: httpx.AsyncClient, embed_url: str) -> str | None:
    """m.ok.ru mobil API üzerinden doğrudan m3u8/mp4 linkini çeker."""
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

        if hls_url := (data.get("hlsManifestUrl") or data.get("hlsMasterPlaylistUrl")):
            return hls_url

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
        log.debug(f"ok.ru API hatası ({video_id}): {e}")

    return None


async def resolve_generic_embed(
    client: httpx.AsyncClient, embed_url: str, referer: str
) -> str | None:
    """luluvdo ve diğer standart embed sayfalarından doğrudan m3u8/mp4 çıkarır."""
    embed_url = embed_url.replace("luluvid.com", "luluvdo.com")
    try:
        res = await client.get(
            embed_url,
            headers={**HEADERS, "Referer": referer},
            timeout=15.0,
        )
        if res.status_code >= 400:
            return None

        match = M3U8_OR_MP4_PATTERN.search(res.text)
        if match:
            return match.group(1).replace("\\/", "/")
    except Exception as e:
        log.debug(f"Embed çözümleme hatası ({embed_url}): {e}")

    return None


async def get_games_from_page(
    client: httpx.AsyncClient, page: int
) -> list[dict[str, str]]:
    url = LIST_URL if page == 1 else f"{LIST_URL}?page{page}"
    games: list[dict[str, str]] = []
    try:
        res = await client.get(url, headers=HEADERS, timeout=15.0)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        for game in soup.select("div.short_item.block_elem"):
            h3_a = game.select_one("h3 a")
            main_a = game.select_one("a[href]")
            if not h3_a or not main_a:
                continue

            title = h3_a.get_text(strip=True).replace("Full Game Replay ", "").replace(" - Full Game Replay", "")
            href = urljoin(BASE_URL, main_a["href"])
            img = game.select_one("img")
            logo = urljoin(BASE_URL, img["src"]) if img and img.get("src") else ""

            if not any(g["url"] == href for g in games):
                games.append({"title": title, "url": href, "logo": logo})
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

            candidate_links: list[str] = []

            # 1. Sayfadaki doğrudan iframe'leri al
            for iframe in soup.select("iframe"):
                src = iframe.get("src") or iframe.get("data-src")
                if src:
                    candidate_links.append(src)

            # 2. Butonların (su-button) içindeki yönlendirme linklerini al
            for btn in soup.select("a.su-button[href]"):
                href = btn.get("href")
                if href:
                    candidate_links.append(href)

            seen_embeds: set[str] = set()
            part_num = 1

            for raw_link in candidate_links:
                link = f"https:{raw_link}" if raw_link.startswith("//") else urljoin(game["url"], raw_link)

                # Ara yönlendirme sitesiyse içine girip gerçek iframe'i bul
                if any(dom in link for dom in REDIRECT_DOMAINS) and link != game["url"]:
                    try:
                        r2 = await client.get(
                            link,
                            headers={**HEADERS, "Referer": game["url"]},
                            timeout=12.0,
                        )
                        sub_soup = BeautifulSoup(r2.text, "html.parser")
                        sub_iframe = sub_soup.select_one("iframe")
                        if sub_iframe and (sub_iframe.get("src") or sub_iframe.get("data-src")):
                            link = sub_iframe.get("src") or sub_iframe.get("data-src")
                            if link.startswith("//"):
                                link = f"https:{link}"
                        else:
                            continue
                    except Exception:
                        continue

                if not link or link in seen_embeds:
                    continue
                seen_embeds.add(link)

                host = urlparse(link).netloc
                stream_url = None
                referer = link

                if "ok.ru" in host:
                    stream_url = await resolve_okru(client, link)
                    referer = "https://ok.ru"
                else:
                    stream_url = await resolve_generic_embed(client, link, game["url"])

                if stream_url:
                    streams.append(
                        {
                            "title": f"{game['title']} [Part {part_num} - {host}]",
                            "group": "NBA Replays",
                            "logo": game["logo"],
                            "referer": referer,
                            "url": stream_url,
                        }
                    )
                    part_num += 1

            if streams:
                log.info(f"✓ {game['title']} ({len(streams)} akış bulundu)")
            else:
                log.warning(f"✗ Uygun akış bulunamadı: {game['title']}")

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

        log.info(f"{len(all_games)} NBA maçı bulundu, linkler ayıklanıyor...")
        if not all_games:
            write_m3u([], OUTPUT_FILE)
            return

        tasks = [scrape_game_streams(client, semaphore, game) for game in all_games]
        results = await asyncio.gather(*tasks)

        flat_streams = [item for sublist in results for item in sublist]
        write_m3u(flat_streams, OUTPUT_FILE)


if __name__ == "__main__":
    asyncio.run(main())
