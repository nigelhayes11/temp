
            log.warning(f"URL {url_num}) Request failed ({event['name']}): {e}")
            return None

        if not (m3u8 := api_data.get("sdUrl") or api_data.get("hlsUrl")):
            log.warning(f"URL {url_num}) No source found -> {event['name']}")
            return None

        log.info(f"URL {url_num}) Captured M3U8 -> {event['name']}")
        return {
            "sport": event["sport"],
            "name": event["name"],
            "logo": event.get("logo") or "",
            "source": m3u8.strip(),
            "refer": refer,
            "tvg-id": "Live.Event.us",
        }


async def get_events(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    try:
        response = await client.get(
            urljoin(BASE_URL, "papi/matches/all-today"),
            headers=HEADERS,
            timeout=15.0,
        )
        response.raise_for_status()
        api_data: list[dict[str, Any]] = response.json() or []
    except Exception as e:
        log.error(f"Failed to fetch API data: {e}")
        return events

    for event in api_data:
        name = event.get("title")
        sport = event.get("league") or event.get("category")
        stream_id = event.get("id")
        ppv_id = str(event.get("ppvId") or "").strip()

        if not (name and sport and stream_id and ppv_id):
            continue

        if str(stream_id).lower().startswith(("dl-", "247")):
            continue

        if str(sport).startswith("24/7"):
            continue

        sport_clean = (
            " ".join(i.capitalize().strip() for i in sport.split("-"))
            if sport.islower()
            else sport
        )

        poster = event.get("poster") or ""
        if poster and not poster.startswith("http"):
            poster = urljoin(BASE_URL, poster)

        events.append(
            {
                "sport": sport_clean,
                "name": name,
                "logo": poster,
                "stream_id": str(stream_id),
                "ppv_id": ppv_id,
            }
        )

    return events


def write_m3u(entries: list[dict[str, str]], filename: str = OUTPUT_M3U) -> None:
    lines = ["#EXTM3U"]

    for item in entries:
        title = f"[{item['sport']}] {item['name']} ({TAG})"
        logo_attr = f' tvg-logo="{item["logo"]}"' if item["logo"] else ""
        lines.append(
            f'#EXTINF:-1 tvg-id="{item["tvg-id"]}"{logo_attr} group-title="{item["sport"]}",{title}'
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
            log.info("No PPV events found")
            write_m3u([])
            return

        log.info(f"Processing {len(events)} PPV event(s)...")

        tasks = [
            process_event(client, semaphore, ev, i)
            for i, ev in enumerate(events, start=1)
        ]

        results = await asyncio.gather(*tasks)
        valid_entries = [res for res in results if res is not None]

    write_m3u(valid_entries)


if __name__ == "__main__":
    asyncio.run(scrape())
