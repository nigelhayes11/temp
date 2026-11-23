import asyncio
import logging
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

BASE_URL = "https://basketball-video.com"
OUTPUT_FILE = "nbareplay.m3u"
MAX_GAMES = 12  # Son 12 NBA maçını çeker

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
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


def extract_direct_stream(embed_url: str) -> str | None:
    """yt-dlp ile ok.ru, dailymotion, vk vb. oynatıcılardan doğrudan m3u8/mp4 çeker."""
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


async def get_nba_games(client: httpx.AsyncClient) -> list[dict[str, str]]:
    """basketball-video.com ana sayfasından sadece NBA maç tekrarlarını alır."""
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
    """Maç sayfasındaki Watch butonlarını ve iframe'leri takip edip yt-dlp ile çözer."""
    streams: list[dict[str, str]] = []
    try:
        res = await client.get(game["url"], headers=HEADERS, timeout=15.0)
        soup = BeautifulSoup(res.text, "html.parser")

        # Sadece içerik alanındaki izleme butonlarını ve iframe'leri topla
        content_area = soup.select_one("div.full_story, div.entry-content, article") or soup
        raw_links: list[str] = []

        for iframe in content_area.select("iframe"):
            src = iframe.get("src") or iframe.get("data-src")
            if src:
                raw_links.append(src)

        for btn in content_area.select("a.su-button[href]"):
            href = btn.get("href")
            if href:
                raw_links.append(href)

        embed_urls: list[str] = []
        for raw in raw_links:
            link = f"https:{raw}" if raw.startswith("//") else urljoin(game["url"], raw)

            # Ara yönlendirme sayfasıysa (nbaontv, nhlgamestoday vb.) içine girip iframe al
            if any(dom in link for dom in REDIRECT_DOMAINS) and link != game["url"]:
                try:
                    r2 = await client.get(link, headers={**HEADERS, "Referer": game["url"]}, timeout=12.0)
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

            if link and link not in embed_urls and "bysesukior" not in link:
                embed_urls.append(link)

        for idx, embed in enumerate(embed_urls, start=1):
            direct_url = await asyncio.to_thread(extract_direct_stream, embed)
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
            log.info(f"✓ {game['title']} ({len(streams)} kaynak eklendi)")
        else:
            log.warning(f"✗ Uygun kaynak çözülemedi: {game['title']}")

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
        log.info(f"{len(games)} NBA maçı bulundu, yt-dlp ile yayın akışları çekiliyor...")

        if not games:
            write_m3u([], OUTPUT_FILE)
            return

        all_streams: list[dict[str, str]] = []
        for game in games:
            all_streams.extend(await scrape_game(client, game))

        write_m3u(all_streams, OUTPUT_FILE)


if __name__ == "__main__":
    asyncio.run(main())
