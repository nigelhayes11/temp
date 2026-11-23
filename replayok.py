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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{BASE_URL}/",
}


def resolve_okru_mp4(embed_url: str) -> str | None:
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


async def get_games_from_page(
    client: httpx.AsyncClient, url: str, group_name: str, is_euroleague: bool = False
) -> list[dict]:
    games: list[dict] = []
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

            games.append(
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

    return games


async def get_okru_from_redirect(client: httpx.AsyncClient, href: str, referer: str) -> list[str]:
    if "ok.ru" in href:
        return [f"https:{href}" if href.startswith("//") else href]

    found: list[str] = []
    full_href = urljoin(referer, href)
    try:
        r2 = await client.get(full_href, headers={**HEADERS, "Referer": referer}, timeout=8.0)
        sub_soup = BeautifulSoup(r2.text, "html.parser")
        for sub_if in sub_soup.select("iframe"):
            sub_src = sub_if.get("src") or sub_if.get("data-src") or ""
            if "ok.ru" in sub_src:
                clean_src = f"https:{sub_src}" if sub_src.startswith("//") else sub_src
                if clean_src not in found:
                    found.append(clean_src)
    except Exception:
        pass
    return found


async def collect_okru_embeds(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    game: dict,
) -> list[dict]:
    async with semaphore:
        tasks_list: list[dict] = []
        try:
            res = await client.get(game["url"], headers=HEADERS, timeout=12.0)
            soup = BeautifulSoup(res.text, "html.parser")
            story = soup.select_one("div.full_story, div.entry-content, div.text") or soup

            if game["is_euroleague"]:
                date_str = game["title"]
                for btn in story.select("a[href]"):
                    txt = btn.get_text(strip=True).lower()
                    if "watch" not in txt and "su-button" not in btn.get("class", []):
                        continue
                    href = btn.get("href", "")
                    if not href or href.startswith("#"):
                        continue

                    match_name = ""
                    parent_p = btn.find_parent("p")
                    if parent_p:
                        prev = parent_p.find_previous_sibling(["p", "h3", "h4", "strong"])
                        if prev:
                            match_name = prev.get_text(" ", strip=True)
                    if not match_name:
                        prev_el = btn.find_previous(["strong", "b", "h3", "h4"])
                        if prev_el:
                            match_name = prev_el.get_text(" ", strip=True)

                    match_name = match_name.replace("Watch", "").strip(" -:")
                    if not match_name or len(match_name) > 90 or "EuroLeague" in match_name:
                        match_name = f"EuroLeague Match #{len(tasks_list) + 1}"

                    ok_links = await get_okru_from_redirect(client, href, game["url"])
                    for idx, emb in enumerate(ok_links, start=1):
                        tasks_list.append(
                            {
                                "title": f"{match_name} - {date_str}",
                                "group": game["group"],
                                "logo": game["logo"],
                                "embed": emb,
                                "part": idx,
                                "total": len(ok_links),
                            }
                        )
                return tasks_list

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
                    if not href or href.startswith("#") or href == game["url"]:
                        continue
                    if any(x in href for x in ("nbaontv", "gamesontvtoday", "nhlgamestoday", "basketball-video")):
                        ok_embeds = await get_okru_from_redirect(client, href, game["url"])
                        if ok_embeds:
                            break

            for idx, embed in enumerate(ok_embeds, start=1):
                tasks_list.append(
                    {
                        "title": game["title"],
                        "group": game["group"],
                        "logo": game["logo"],
                        "embed": embed,
                        "part": idx,
                        "total": len(ok_embeds),
                    }
                )
        except Exception:
            pass

        return tasks_list


async def resolve_task(semaphore: asyncio.Semaphore, item: dict) -> dict[str, str] | None:
    async with semaphore:
        direct_url = await asyncio.to_thread(resolve_okru_mp4, item["embed"])
        if not direct_url:
            return None

        part_tag = f"Part {item['part']}" if item["total"] > 1 else "Full"
        log.info(f"✓ [{item['group']}] {item['title']} [{part_tag}]")
        return {
            "title": f"{item['title']} [{part_tag}]",
            "group": item["group"],
            "logo": item["logo"],
            "referer": "https://ok.ru",
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
    async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
        page_tasks = []
        for p in range(1, NBA_PAGES + 1):
            url = f"{BASE_URL}/" if p == 1 else f"{BASE_URL}/?page{p}"
            page_tasks.append(get_games_from_page(client, url, NBA_GROUP, is_euroleague=False))

        for p in range(1, EUROLEAGUE_PAGES + 1):
            url = f"{BASE_URL}/euroleague" if p == 1 else f"{BASE_URL}/euroleague?page{p}"
            page_tasks.append(get_games_from_page(client, url, EUROLEAGUE_GROUP, is_euroleague=True))

        page_results = await asyncio.gather(*page_tasks)

        all_games: list[dict] = []
        seen_urls: set[str] = set()
        for p_games in page_results:
            for g in p_games:
                if g["url"] not in seen_urls:
                    seen_urls.add(g["url"])
                    all_games.append(g)

        log.info(f"Toplam {len(all_games)} gönderi bulundu, ok.ru linkleri toplanıyor...")

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
