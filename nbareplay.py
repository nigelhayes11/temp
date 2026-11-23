import asyncio
import logging
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
import yt_dlp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("NBAREPLAY")

BASE_URL = "https://basketball-video.com"
OUTPUT_FILE = "nbareplay.m3u"
MAX_GAMES = 15

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

M3U8_REGEX = re.compile(r"""["'](https?://[^"'\s<>]+\.m3u8[^"'\s<>]*)["']""", re.IGNORECASE)


def resolve_video_url(embed_url: str, referer: str) -> str | None:
    """Önce yt-dlp ile (ok.ru, filemoon, dailymotion vb.), olmazsa HTML regex ile m3u8/mp4 çeker."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "best[protocol*=m3u8]/best",
        "http_headers": {**HEADERS, "Referer": referer},
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(embed_url, download=False)
            if info and info.get("url"):
                return info["url"]
    except Exception:
        pass
    return None


async def fallback_jw_scan(client: httpx.AsyncClient, embed_url: str, referer: str) -> str | None:
    """yt-dlp'nin tanımadığı özel JW Player sayfalarından doğrudan m3u8 ayıklar."""
    try:
        res = await client.get(embed_url, headers={**HEADERS, "Referer": referer}, timeout=12.0)
        text = res.text.replace("\\/", "/")
        match = M3U8_REGEX.search(text)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None


async def get_nba_games(client: httpx.AsyncClient) -> list[dict[str, str]]:
    games: list[dict[str, str]] = []
    try:
        res = await client.get(f"{BASE_URL}/", headers=HEADERS, timeout=15.0)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        for item in soup.select("div.short_item.block_elem"):
            h3_a = item.select_one("h3 a")
            main_a = item.select_one("a[href]")
            if not h3_a or not main_a:
                continue

            raw_title = h3_a.get_text(strip=True)
            if "NBA" not in raw_title or "WNBA" in raw_title:
                continue

            title = raw_title.replace("Full Game Replay ", "").replace(" - Full Game Replay", "").strip(" -")
            href = urljoin(BASE_URL, main_a["href"])
            img = item.select_one("img")
            logo = urljoin(BASE_URL, img["src"]) if img and img.get("src") else ""

            if not any(g["url"] == href for g in games):
                games.append({"title": title, "url": href, "logo": logo})

            if len(games) >= MAX_GAMES:
                break
    except Exception as e:
        log.error(f"Ana sayfa çekilemedi: {e}")

    return games


async def scrape_game(client: httpx.AsyncClient, game: dict[str, str]) -> list[dict[str, str]]:
    streams: list[dict[str, str]] = []
    try:
        res = await client.get(game["url"], headers=HEADERS, timeout=15.0)
        soup = BeautifulSoup(res.text, "html.parser")

        # Maç yazısı içindeki tüm izleme linklerini ve iframe'leri bul
        story = soup.select_one("div.full_story, div.entry-content, div.text") or soup
        candidate_urls: list[str] = []

        for iframe in story.select("iframe"):
            src = iframe.get("src") or iframe.get("data-src")
            if src:
                candidate_urls.append(src)

        for a in story.select("a[href]"):
            href = a.get("href", "")
            text = a.get_text(strip=True).lower()
            if "watch" in text or "su-button" in a.get("class", []) or any(d in href for d in REDIRECT_DOMAINS):
                if href and not href.startswith("#"):
                    candidate_urls.append(href)

        embed_urls: list[str] = []
        for raw in candidate_urls:
            link = f"https:{raw}" if raw.startswith("//") else urljoin(game["url"], raw)

            # Ara yönlendirme sayfasıysa (nbaontv, gamesontvtoday vb.) içine girip tüm iframe'leri al
            if any(dom in link for dom in REDIRECT_DOMAINS) and link != game["url"]:
                try:
                    r2 = await client.get(link, headers={**HEADERS, "Referer": game["url"]}, timeout=12.0)
                    sub_soup = BeautifulSoup(r2.text, "html.parser")
                    for sub_iframe in sub_soup.select("iframe"):
                        sub_src = sub_iframe.get("src") or sub_iframe.get("data-src")
                        if sub_src:
                            if sub_src.startswith("//"):
                                sub_src = "https:" + sub_src
                            if sub_src not in embed_urls:
                                embed_urls.append(sub_src)
                except Exception:
                    continue
            elif link not in embed_urls and link != game["url"]:
                embed_urls.append(link)

        for idx, embed in enumerate(embed_urls, start=1):
            embed_clean = embed.replace("luluvid.com", "luluvdo.com")
            host = urlparse(embed_clean).netloc

            # Önce yt-dlp ile dene, olmazsa JW Player M3U8 taraması yap
            direct_url = await asyncio.to_thread(resolve_video_url, embed_clean, game["url"])
            if not direct_url:
                direct_url = await fallback_jw_scan(client, embed_clean, game["url"])

            if direct_url:
                streams.append(
                    {
                        "title": f"{game['title']} [Part {idx} - {host}]",
                        "group": "NBA Replays",
                        "logo": game["logo"],
                        "referer": embed_clean,
                        "url": direct_url,
                    }
                )

        if streams:
            log.info(f"✓ {game['title']} ({len(streams)} kaynak eklendi)")
        else:
            log.warning(f"✗ Çözülemedi ({len(embed_urls)} embed bulundu): {game['title']}")

    except Exception as e:
        log.warning(f"Hata ({game['title']}): {e}")

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
    async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
        games = await get_nba_games(client)
        log.info(f"{len(games)} NBA maçı bulundu, linkler çözülüyor...")

        if not games:
            write_m3u([], OUTPUT_FILE)
            return

        all_streams: list[dict[str, str]] = []
        for game in games:
            all_streams.extend(await scrape_game(client, game))

        write_m3u(all_streams, OUTPUT_FILE)


if __name__ == "__main__":
    asyncio.run(main())
