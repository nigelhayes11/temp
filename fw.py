import asyncio
import logging
import re
from urllib.parse import quote, urljoin

import httpx
from selectolax.lexbor import LexborHTMLParser as HTMLParser

# Loglama ayarları
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("FAWA")

TAG = "FAWA"
BASE_URL = "http://fawanews.sc"
OUTPUT_M3U = "fawa.m3u"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


async def process_event(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    event: dict[str, str],
    url_num: int,
) -> dict[str, str] | None:
    async with semaphore:
        try:
            response = await client.get(
                event["link"],
                headers={**HEADERS, "Referer": BASE_URL},
                timeout=15.0,
            )
            response.raise_for_status()
        except Exception as e:
            log.warning(f"URL {url_num}) Request failed: {e}")
            return None

        if f"{response.url}" in (BASE_URL, BASE_URL.rstrip("/")):
            log.info(f"URL {url_num}) No event found.")
            return None

        valid_m3u8 = re.compile(r"var\s*\w*\s*=\s+\[(.*)];", re.I)

        if not (match := valid_m3u8.search(response.text)):
            log.warning(f"URL {url_num}) Unable to parse event source")
            return None

        try:
            source = "".join(
                re.search(rf'var\s*{var}\s*=\s*"(.*)";', response.text, re.I)[1]
                for var in (i.strip() for i in match[1].split("+"))
            ).strip()
        except (TypeError, IndexError):
            source = ""

        if source:
            log.info(f"URL {url_num}) Captured M3U8 -> {event['name']}")
            return {
                "sport": event["sport"],
                "name": event["name"],
                "source": source,
                "refer": BASE_URL,
                "tvg-id": "Live.Event.us",
            }

        log.warning(f"URL {url_num}) No M3U8 found")
        return None


async def get_events(client: httpx.AsyncClient) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []

    try:
        response = await client.get(BASE_URL, headers=HEADERS, timeout=15.0)
        response.raise_for_status()
    except Exception as e:
        log.error(f"Failed to fetch main page: {e}")
        return events

    soup = HTMLParser(response.content)

    valid_event = re.compile(r"\d{1,2}:\d{1,2}")
    clean_event = re.compile(r"\s+-+\s+\w{1,4}")

    for item in soup.css(".user-item"):
        text_elem = item.css_first(".user-item__name")
        subtext_elem = item.css_first(".user-item__playing")
        link_elem = item.css_first("a[href]")

        if not (text_elem and subtext_elem and link_elem):
            continue

        if not (href := link_elem.attributes.get("href")):
            continue

        link = urljoin(f"{response.url}", quote(href))
        event_name = text_elem.text(strip=True)
        details = subtext_elem.text(strip=True)

        if not valid_event.search(details):
            continue

        sport = valid_event.split(details)[0].strip()

        events.append(
            {
                "sport": sport,
                "name": clean_event.sub("", event_name),
                "link": link,
            }
        )

    return events


def write_m3u(entries: list[dict[str, str]], filename: str = OUTPUT_M3U) -> None:
    lines = ["#EXTM3U"]

    for item in entries:
        title = f"[{item['sport']}] {item['name']} ({TAG})"
        lines.append(
            f'#EXTINF:-1 tvg-id="{item["tvg-id"]}" group-title="{item["sport"]}",{title}'
        )
        lines.append(f'#EXTVLCOPT:http-referrer={item["refer"]}')
        lines.append(f'#EXTVLCOPT:http-user-agent={HEADERS["User-Agent"]}')
        lines.append(item["source"])

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    log.info(f"Saved {len(entries)} stream(s) to '{filename}'")


async def scrape() -> None:
    log.info(f'Scraping from "{BASE_URL}"')

    semaphore = asyncio.Semaphore(10)

    async with httpx.AsyncClient(follow_redirects=True) as client:
        events = await get_events(client)

        if not events:
            log.info("No events found")
            write_m3u([])
            return

        log.info(f"Processing {len(events)} URL(s)...")

        tasks = [
            process_event(client, semaphore, ev, i)
            for i, ev in enumerate(events, start=1)
        ]

        results = await asyncio.gather(*tasks)
        valid_entries = [res for res in results if res is not None]

    write_m3u(valid_entries)


if __name__ == "__main__":
    asyncio.run(scrape())
