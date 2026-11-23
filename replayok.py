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
NBA_PAGES = 4
EUROLEAGUE_PAGES = 1
MAX_CONCURRENT = 12

NBA_GROUP = "🏀 NBA Replays 🏀"
EUROLEAGUE_GROUP = "🏆 EuroLeague Replays 🏆"

FALLBACK_LOGOS = {
    NBA_GROUP: "https://espncdn.com",
    EUROLEAGUE_GROUP: "https://wikimedia.org",
}

SKIP_HOSTS = ("bysesukior", "czzbgnw", "facebook.com", "twitter.com", "google.com")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{BASE_URL}/",
}


def resolve_video_mp4(embed_url: str) -> str | None:
    """ok.ru, dailymotion, vk vb. desteklenen embedlerden tek parça MP4/HTTP akışı çeker."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 8,
        "format": "best[ext=mp4]/best[protocol^=http]/best",
        "http_headers": {**HEADERS, "Referer": embed_url},
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(embed_url, download=False)
            if info and info.get("url"):
                return info["url"]
    except Exception:
        pass
    return None


async def get_posts_from_url(
    client: httpx.AsyncClient, url: str, group_name: str, is_euroleague: bool = False
) -> list[dict]:
    posts: list[dict] = []
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
            if not is_euroleague and ("NBA" not in raw_title or "WNBA" in raw_title):
                continue

            title = (
                raw_title.replace("Full Game Replay ", "")
                .replace(" - Full Game Replay", "")
                .replace(" - NBA - ", " - ")
                .replace("EuroLeague Basketball - Full Game Replays - ", "")
                .strip(" -")
            )
            href = urljoin(BASE_URL, main_a["href"])
            img = item.select_one("img")
            logo = urljoin(BASE_URL, img["src"]) if img and img.get("src") else FALLBACK_LOGOS[group_name]

            posts.append(
                {
                    "title": title,
                    "url": href,
                    "logo": logo,
                    "group": group_name,
                    "is_euroleague": is_euroleague,
                }
            )
    except Exception as e:
        log.warning(f"Sayfa çekilemedi ({url}): {e}")

    return posts


async def extract_embeds_from_redirect(
    client: httpx.AsyncClient, href: str, referer: str
) -> list[str]:
    """Butonun yönlendirdiği ara sayfadan desteklenen (ok.ru, dailymotion, vk) iframe'leri alır."""
    if any(s in href for s in SKIP_HOSTS):
        return []

    if any(d in href for d in ("ok.ru", "dailymotion.com", "vk.com")):
        return [f"https:{href}" if href.startswith("//") else href]

    found: list[str] = []
    full_href = urljoin(referer, href)
    try:
        r2 = await client.get(full_href, headers={**HEADERS, "Referer": referer}, timeout=8.0)
        sub_soup = BeautifulSoup(r2.text, "html.parser")
        for sub_if in sub_soup.select("iframe"):
            sub_src = sub_if.get("src") or sub_if.get("data-src") or ""
            if not sub_src or any(s in sub_src for s in SKIP_HOSTS):
                continue
            clean_src = f"https:{sub_src}" if sub_src.startswith("//") else sub_src
            if clean_src not in found:
                found.append(clean_src)
    except Exception:
        pass
    return found


async def collect_embeds(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    post: dict,
) -> list[dict]:
    async with semaphore:
        tasks_to_resolve: list[dict] = []
        try:
            res = await client.get(post["url"], headers=HEADERS, timeout=12.0)
            soup = BeautifulSoup(res.text, "html.parser")
            story = soup.select_one("div.full_story, div.entry-content, div.text") or soup

            # EUROLEAGUE: Sayfadaki her "Watch" butonunu ve hemen üstündeki maç başlığını eşleştir
            if post["is_euroleague"]:
                date_suffix = post["title"]
                watch_links = [
                    a for a in story.select("a[href]")
                    if "watch" in a.get_text(strip=True).lower() or "su-button" in a.get("class", [])
                ]

                for btn in watch_links:
                    href = btn.get("href", "")
                    if not href or href.startswith("#"):
                        continue

                    # Butonun üstündeki metin bloğundan takım isimlerini al
                    match_name = ""
                    prev_p = btn.find_parent("p")
                    if prev_p:
                        prev_sibling = prev_p.find_previous_sibling(["p", "h3", "h4", "strong"])
                        if prev_sibling:
                            match_name = prev_sibling.get_text(" ", strip=True)
                    if not match_name:
                        prev_any = btn.find_previous(["strong", "b", "h3", "h4"])
                        if prev_any:
                            match_name = prev_any.get_text(" ", strip=True)

                    match_name = match_name.replace("Watch", "").strip(" -:")
                    if not match_name or len(match_name) > 90 or "EuroLeague" in match_name:
                        match_name = f"EuroLeague Match #{len(tasks_to_resolve) + 1}"

                    embeds = await extract_embeds_from_redirect(client, href, post["url"])
                    for idx, emb in enumerate(embeds, start=1):
                        tasks_to_resolve.append(
                            {
                                "title": f"{match_name} - {date_suffix}",
                                "group": post["group"],
                                "logo": post["logo"],
                                "embed": emb,
                                "part": idx,
                                "total": len(embeds),
                            }
                        )

                log.info(f"EuroLeague ({date_suffix}): {len(tasks_to_resolve)} maç bağlantısı ayrıştırıldı")
                return tasks_to_resolve

            # NBA: Tek maç sayfasındaki ok.ru iframe veya Server #1 butonunu al
            ok_embeds: list[str] = []
            for iframe in story.select("iframe"):
                src = iframe.get("src") or iframe.get("data-src") or ""
                if "ok.ru" in src:
                    full_src = f"https:{src}" if src.startswith("//") else src
                    if full_src not in ok_embeds:
                        ok_embeds.append(full_src)

            if not ok_embeds:
                for a in story.select("a.su-button[href], p a[href]"):
                    href = a.get("href", "")
                    if not href or href.startswith("#") or href == post["url"]:
                        continue
                    if any(x in href for x in ("nbaontv", "gamesontvtoday", "nhlgamestoday", "basketball-video")):
                        ok_embeds = await extract_embeds_from_redirect(client, href, post["url"])
                        if ok_embeds:
                            break

            for idx, embed in enumerate(ok_embeds, start=1):
                tasks_to_resolve.append(
                    {
                        "title": post["title"],
                        "group": post["group"],
                        "logo": post["logo"],
                        "embed": embed,
                        "part": idx,
                        "total": len(ok_embeds),
                    }
                )
        except Exception as e:
            log.debug(f"Sayfa ayrıştırma hatası ({post['url']}): {e}")

        return tasks_to_resolve


async def resolve_task(semaphore: asyncio.Semaphore, item: dict) -> dict[str, str] | None:
    async with semaphore:
        direct_url = await asyncio.to_thread(resolve_video_mp4, item["embed"])
        if not direct_url:
            return None

        part_tag = f"Part {item['part']}" if item["total"] > 1 else "Full"
        log.info(f"✓ [{item['group']}] {item['title']} [{part_tag}]")
        return {
            "title": f"{item['title']} [{part_tag}]",
            "group": item["group"],
            "logo": item["logo"],
            "referer": "https://ok.ru" if "ok.ru" in item["embed"] else item["embed"],
            "url": direct_url,
        }


def write_m3u(streams: list[dict[str, str]], filename: str) -> None:
    lines = ["#EXTM3U"]
    for s in streams:
        lines.append(
            f'#EXTINF:-1 tvg-id="Basketball.Replay" tvg-logo="{s["logo"]}" group-title="{s["group"]}",{s["title"]}'
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
