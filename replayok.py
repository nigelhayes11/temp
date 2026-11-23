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
log = logging.getLogger("REPLAYOK")

BASE_URL = "https://basketball-video.com"
OUTPUT_FILE = "replayok.m3u"
PAGES_TO_SCRAPE = 4  # Son 1 haftalık tüm NBA maçları (~45 maç)
MAX_CONCURRENT = 12  # Aynı anda 12 video linkini paralel çözer

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{BASE_URL}/",
}


def resolve_okru_mp4(embed_url: str) -> str | None:
    """Sadece ok.ru linklerinden IP kilitsiz tek parça MP4 akışını hızlıca çeker."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 8,
        "format": "best[ext=mp4]/best[protocol^=http]/best",
        "http_headers": {**HEADERS, "Referer": "https://ok.ru"},
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(embed_url, download=False)
            if info and info.get("url"):
                return info["url"]
    except Exception:
        pass
    return None


async def get_games_from_page(client: httpx.AsyncClient, page: int) -> list[dict[str, str]]:
    url = f"{BASE_URL}/" if page == 1 else f"{BASE_URL}/?page{page}"
    games: list[dict[str, str]] = []
    try:
        res = await client.get(url, headers=HEADERS, timeout=12.0)
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

            title = (
                raw_title.replace("Full Game Replay ", "")
                .replace(" - Full Game Replay", "")
                .replace(" - NBA - ", " - ")
                .strip(" -")
            )
            href = urljoin(BASE_URL, main_a["href"])
            img = item.select_one("img")
            logo = urljoin(BASE_URL, img["src"]) if img and img.get("src") else ""

            games.append({"title": title, "url": href, "logo": logo})
    except Exception as e:
        log.warning(f"Sayfa {page} çekilemedi: {e}")

    return games


async def collect_okru_embeds(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    game: dict[str, str],
) -> list[dict[str, str]]:
    """Maç sayfasından sadece ok.ru embed linklerini toplar, diğer sunucuları atlar."""
    async with semaphore:
        ok_embeds: list[str] = []
        try:
            res = await client.get(game["url"], headers=HEADERS, timeout=12.0)
            soup = BeautifulSoup(res.text, "html.parser")
            story = soup.select_one("div.full_story, div.entry-content, div.text") or soup

            # 1. Doğrudan sayfadaki ok.ru iframe'leri
            for iframe in story.select("iframe"):
                src = iframe.get("src") or iframe.get("data-src") or ""
                if "ok.ru" in src:
                    full_src = f"https:{src}" if src.startswith("//") else src
                    if full_src not in ok_embeds:
                        ok_embeds.append(full_src)

            # 2. Yönlendirme butonlarının (Server #1 OK) arkasındaki ok.ru iframe'leri
            if not ok_embeds:
                for a in story.select("a.su-button[href], p a[href]"):
                    href = a.get("href", "")
                    if not href or href.startswith("#") or href == game["url"]:
                        continue
                    # Sadece Server #1 veya ilk yönlendirme linklerine bak
                    if any(x in href for x in ("nbaontv", "gamesontvtoday", "nhlgamestoday", "basketball-video")):
                        full_href = urljoin(game["url"], href)
                        try:
                            r2 = await client.get(full_href, headers={**HEADERS, "Referer": game["url"]}, timeout=8.0)
                            sub_soup = BeautifulSoup(r2.text, "html.parser")
                            for sub_if in sub_soup.select("iframe"):
                                sub_src = sub_if.get("src") or sub_if.get("data-src") or ""
                                if "ok.ru" in sub_src:
                                    clean_src = f"https:{sub_src}" if sub_src.startswith("//") else sub_src
                                    if clean_src not in ok_embeds:
                                        ok_embeds.append(clean_src)
                        except Exception:
                            continue
                        if ok_embeds:
                            break
        except Exception:
            pass

        return [
            {"game": game, "embed": embed, "part": idx, "total": len(ok_embeds)}
            for idx, embed in enumerate(ok_embeds, start=1)
        ]


async def resolve_task(
    semaphore: asyncio.Semaphore, item: dict
) -> dict[str, str] | None:
    async with semaphore:
        direct_url = await asyncio.to_thread(resolve_okru_mp4, item["embed"])
        if not direct_url:
            return None

        game = item["game"]
        part_tag = f"Part {item['part']}" if item["total"] > 1 else "Full"
        log.info(f"✓ {game['title']} [{part_tag}]")
        return {
            "title": f"{game['title']} [{part_tag}]",
            "group": "NBA Replays",
            "logo": game["logo"],
            "referer": "https://ok.ru",
            "url": direct_url,
        }


def write_m3u(streams: list[dict[str, str]], filename: str) -> None:
    lines = ["#EXTM3U"]
    for s in streams:
        lines.append(
            f'#EXTINF:-1 tvg-id="NBA.Replay" tvg-logo="{s["logo"]}" group-title="{s["group"]}",{s["title"]}'
        )
        lines.append(f"#EXTVLCOPT:http-referrer={s['referer']}")
        lines.append(f"#EXTVLCOPT:http-user-agent={HEADERS['User-Agent']}")
        lines.append("#EXTVLCOPT:http-no-tls-verify")
        lines.append(s["url"])

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    log.info(f"Toplam {len(streams)} yayın '{filename}' dosyasına kaydedildi.")


async def main() -> None:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
        all_games: list[dict[str, str]] = []
        seen_urls: set[str] = set()

        # 4 sayfayı aynı anda çek
        page_results = await asyncio.gather(
            *[get_games_from_page(client, p) for p in range(1, PAGES_TO_SCRAPE + 1)]
        )
        for p_games in page_results:
            for g in p_games:
                if g["url"] not in seen_urls:
                    seen_urls.add(g["url"])
                    all_games.append(g)

        log.info(f"Son 1 haftadan {len(all_games)} NBA maçı bulundu, ok.ru linkleri toplanıyor...")

        embed_lists = await asyncio.gather(
            *[collect_okru_embeds(client, semaphore, g) for g in all_games]
        )
        flat_embeds = [item for sublist in embed_lists for item in sublist]

        log.info(f"{len(flat_embeds)} ok.ru videosu paralel çözülüyor...")
        resolved = await asyncio.gather(
            *[resolve_task(semaphore, item) for item in flat_embeds]
        )

        valid_streams = [r for r in resolved if r is not None]
        write_m3u(valid_streams, OUTPUT_FILE)


if __name__ == "__main__":
    asyncio.run(main())
