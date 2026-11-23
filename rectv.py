import asyncio
import logging
import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("RECTV")

API_URLS = [
    "https://rectv13cloudflareaccess.com",
    "https://cloudflareaccess.com",
    "https://cloudflareaccess.com",
    "https://cloudflareaccess.com",
    "https://cloudflareaccess.com",
]

API_KEY = "4F5A9C3D9A86FA54EACEDDD635185/c3c5bd17-e37b-4b94-a944-8a3688a30452"
OUTPUT_FILE = "rec.m3u"

HEADERS = {
    "User-Agent": "okhttp/4.12.0",
    "Accept": "application/json",
    "Referer": "https://twitter.com",
}


async def find_working_api(client: httpx.AsyncClient) -> str | None:
    for base_url in API_URLS:
        test_url = f"{base_url}/api/channel/by/filtres/0/0/0/{API_KEY}/"
        try:
            res = await client.get(test_url, headers=HEADERS, timeout=10.0)
            log.info(f"[{base_url}] HTTP {res.status_code}")
            if res.status_code == 200 and res.text.strip().startswith("["):
                log.info(f"✓ Aktif RecTV API bulundu: {base_url}")
                return base_url
        except Exception as e:
            log.info(f"[{base_url}] Bağlantı hatası: {type(e).__name__}")
    return None


async def fetch_all_channels(client: httpx.AsyncClient, base_url: str) -> list[dict]:
    channels: list[dict] = []
    seen_urls: set[str] = set()

    for page in range(0, 15):
        url = f"{base_url}/api/channel/by/filtres/0/0/{page}/{API_KEY}/"
        try:
            res = await client.get(url, headers=HEADERS, timeout=12.0)
            if res.status_code != 200:
                break

            data = res.json()
            if not data or not isinstance(data, list):
                break

            for item in data:
                title = (item.get("title") or "").strip()
                logo = (item.get("image") or "").strip()
                categories = item.get("categories") or []
                group = categories.get("title", "RecTV Canlı") if categories else "RecTV Canlı"

                sources = item.get("sources") or []
                for src in sources:
                    stream_url = (src.get("url") or "").strip()
                    if not stream_url or stream_url in seen_urls:
                        continue

                    seen_urls.add(stream_url)
                    channels.append(
                        {
                            "title": title,
                            "logo": logo,
                            "group": f"📺 {group}",
                            "url": stream_url,
                        }
                    )
        except Exception:
            break

    return channels


def write_m3u(channels: list[dict], filename: str) -> None:
    lines = ["#EXTM3U"]
    for ch in channels:
        lines.append(
            f'#EXTINF:-1 tvg-id="{ch["title"]}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}",{ch["title"]}'
        )
        lines.append("#EXTVLCOPT:http-referrer=https://twitter.com")
        lines.append("#EXTVLCOPT:http-user-agent=okhttp/4.12.0")
        lines.append("#EXTVLCOPT:http-no-tls-verify")
        lines.append(ch["url"])

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    log.info(f"Toplam {len(channels)} canlı TV kanalı '{filename}' dosyasına kaydedildi.")


async def main() -> None:
    async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
        base_url = await find_working_api(client)
        if not base_url:
            log.error("Aktif RecTV API adresi bulunamadı!")
            write_m3u([], OUTPUT_FILE)
            return

        channels = await fetch_all_channels(client, base_url)
        write_m3u(channels, OUTPUT_FILE)


if __name__ == "__main__":
    asyncio.run(main())
