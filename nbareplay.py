import asyncio
import logging
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
import yt_dlp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("NBAREPLAY")

BASE_URL = "https://nbareplay.net"
OUTPUT_FILE = "nbareplay.m3u"
MAX_GAMES = 12  # Son 12 maçı tarar

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": f"{BASE_URL}/",
}


def extract_with_ytdlp(embed_url: str) -> str | None:
    """yt-dlp kullanarak Dailymotion, OK.ru, VK veya gömülü oynatıcıdan doğrudan yayın linki alır."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "best[protocol*=m3u8]/best",
        "http_headers": HEADERS,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(embed_url, download=False)
            if info and info.get("url"):
                return info["url"]
    except Exception:
        return None
    return None


async def get_recent_games(client: httpx.AsyncClient) -> list[dict[str, str]]:
    """nbareplay.net ana sayfasından son NBA maçlarını toplar."""
    games: list[dict[str, str]] = []
    try:
        res = await client.get(BASE_URL, headers=HEADERS, timeout=15.0)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        for article in soup.select("article"):
            a = article.select_one("h2 a, h3 a, a[rel='bookmark']")
            if not a or not a.get("href"):
                continue

            title = a.get_text(strip=True).replace("Full Game Replay", "").strip(" -–")
            href = urljoin(BASE_URL, a["href"])
            img = article.select_one("img")
            logo = img.get("data-src") or img.get("src") or "" if img else ""

            if not any(g["url"] == href for g in games):
                games.append({"title": title, "url": href, "logo": logo})

            if len(games) >= MAX_GAMES:
                break
    except Exception as e:
        log.error(f"Ana sayfa çekilemedi: {e}")

    return games


async def process_game(client: httpx.AsyncClient, game: dict[str, str]) -> list[dict[str, str]]:
    """Maç sayfasındaki iframe veya video linklerini bulup yt-dlp ile çözer."""
    streams: list[dict[str, str]] = []
    try:
        res = await client.get(game["url"], headers=HEADERS, timeout=15.0)
        soup = BeautifulSoup(res.text, "html.parser")

        embed_urls: list[str] = []
        for iframe in soup.select("iframe"):
            src = iframe.get("src") or iframe.get("data-src")
            if src:
                if src.startswith("//"):
                    src = "https:" + src
                if src not in embed_urls and not any(x in src for x in ("facebook", "twitter", "ads")):
                    embed_urls.append(src)

        for idx, embed in enumerate(embed_urls, start=1):
            direct_url = await asyncio.to_thread(extract_with_ytdlp, embed)
            if direct_url:
                label = f"Part {idx}" if len(embed_urls) > 1 else "Full"
                streams.append(
                    {
                        "title": f"{game['title']} [{label}]",
                        "group": "NBA Replays",
                        "logo": game["logo"],
                        "referer": embed,
                        "url": direct_url,
                    }
                )

        if streams:
            log.info(f"✓ {game['title']} ({len(streams)} part eklendi)")
        else:
            log.warning(f"✗ Oynatıcı çözülemedi: {game['title']}")

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
        games = await get_recent_games(client)
        log.info(f"{len(games)} NBA maçı bulundu, linkler çözülüyor...")

        if not games:
            write_m3u([], OUTPUT_FILE)
            return

        all_streams: list[dict[str, str]] = []
        for game in games:
            game_streams = await process_game(client, game)
            all_streams.extend(game_streams)

        write_m3u(all_streams, OUTPUT_FILE)


if __name__ == "__main__":
    asyncio.run(main())
