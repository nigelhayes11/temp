import asyncio
import json
import logging
import re
import zipfile
import io
import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("WIOSPOR")

OUTPUT_FILE = "wiospor.m3u"

# WioSpor deposundaki BeyazElma.cs3 ve hazır canlı katalog adresleri
WIOSPOR_RAW_BASE = "https://githubusercontent.com"
BEYAZELMA_CS3_URL = f"{WIOSPOR_RAW_BASE}/builds/BeyazElma.cs3"
CIFD2M_JSON_URL = f"{WIOSPOR_RAW_BASE}/main/cifd2m_live.json"

# RecTV güncel API havuzu
RECTV_DOMAINS = [
    "https://cloudflareaccess.com",
    "https://cloudflareaccess.com",
    "https://cloudflareaccess.com",
    "https://prectv59.lol",
    "https://prectv58.lol",
]
RECTV_API_KEY = "4F5A9C3D9A86FA54EACEDDD635185/c3c5bd17-e37b-4b94-a944-8a3688a30452"

HEADERS_MOBILE = {
    "User-Agent": "okhttp/4.12.0",
    "Accept": "application/json",
    "Referer": "https://twitter.com",
}

HEADERS_WEB = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


async def fetch_rectv_channels(client: httpx.AsyncClient) -> list[dict]:
    """RecTV API üzerinden canlı kanalları çeker."""
    channels: list[dict] = []
    active_domain = None

    for domain in RECTV_DOMAINS:
        test_url = f"{domain}/api/channel/by/filtres/0/0/0/{RECTV_API_KEY}/"
        try:
            res = await client.get(test_url, headers=HEADERS_MOBILE, timeout=8.0)
            if res.status_code == 200 and res.text.strip().startswith("["):
                active_domain = domain
                log.info(f"✓ RecTV aktif domain: {domain}")
                break
        except Exception:
            continue

    if not active_domain:
        log.warning("RecTV API şu an yanıt vermiyor (Geo-block veya domain değişmiş olabilir).")
        return channels

    seen: set[str] = set()
    for page in range(0, 12):
        url = f"{active_domain}/api/channel/by/filtres/0/0/{page}/{RECTV_API_KEY}/"
        try:
            res = await client.get(url, headers=HEADERS_MOBILE, timeout=10.0)
            if res.status_code != 200:
                break
            data = res.json()
            if not data or not isinstance(data, list):
                break

            for item in data:
                title = (item.get("title") or "").strip()
                logo = (item.get("image") or "").strip()
                for src in item.get("sources") or []:
                    stream_url = (src.get("url") or "").strip()
                    if stream_url and stream_url not in seen:
                        seen.add(stream_url)
                        channels.append(
                            {
                                "title": title,
                                "logo": logo,
                                "group": "📺 RecTV Canlı",
                                "referer": "https://twitter.com",
                                "ua": "okhttp/4.12.0",
                                "url": stream_url,
                            }
                        )
        except Exception:
            break

    log.info(f"RecTV: {len(channels)} kanal eklendi.")
    return channels


async def extract_beyazelma_domain(client: httpx.AsyncClient) -> str | None:
    """WioSpor/builds içindeki BeyazElma.cs3 (ZIP/DEX) paketinden güncel mainUrl adresini okur."""
    try:
        res = await client.get(BEYAZELMA_CS3_URL, headers=HEADERS_WEB, timeout=15.0)
        if res.status_code != 200:
            return None

        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            for name in zf.namelist():
                if name.endswith(".dex"):
                    dex_bytes = zf.read(name)
                    # DEX string havuzundan http/https URL'lerini çıkar
                    urls = re.findall(rb"https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\x00-\x1f\"'<> ]*)?", dex_bytes)
                    for raw_u in urls:
                        u = raw_u.decode("utf-8", errors="ignore")
                        if any(skip in u for skip in ("github", "google", "schema.org", "android", "w3.org", "cloudflare", "themoviedb")):
                            continue
                        log.info(f"✓ BeyazElma.cs3 içinden hedef adres bulundu: {u}")
                        return u.rstrip("/")
    except Exception as e:
        log.warning(f"BeyazElma.cs3 okunamadı: {e}")
    return None


async def fetch_beyazelma_and_wiospor(client: httpx.AsyncClient) -> list[dict]:
    """BeyazElma kaynağını ve WioSpor deposundaki canlı JSON akışlarını toplar."""
    channels: list[dict] = []
    seen: set[str] = set()

    # 1. BeyazElma.cs3 içindeki hedef adresten canlı yayın/M3U8 linklerini tara
    be_url = await extract_beyazelma_domain(client)
    if be_url:
        try:
            res = await client.get(be_url, headers={**HEADERS_WEB, "Referer": f"{be_url}/"}, timeout=12.0)
            m3u8_links = re.findall(r"""["'](https?://[^"'\s<>]+\.m3u8[^"'\s<>]*)["']""", res.text)
            for idx, link in enumerate(dict.fromkeys(m3u8_links), start=1):
                if link not in seen:
                    seen.add(link)
                    channels.append(
                        {
                            "title": f"BeyazElma Kanal #{idx}",
                            "logo": "",
                            "group": "🍎 BeyazElma 🍎",
                            "referer": f"{be_url}/",
                            "ua": HEADERS_WEB["User-Agent"],
                            "url": link,
                        }
                    )
        except Exception as e:
            log.debug(f"BeyazElma site taraması: {e}")

    # 2. WioSpor deposundaki güncel cifd2m_live.json canlı akışları
    try:
        res = await client.get(CIFD2M_JSON_URL, headers=HEADERS_WEB, timeout=10.0)
        if res.status_code == 200:
            data = res.json()
            items = data if isinstance(data, list) else data.get("channels", []) or data.get("streams", [])
            for item in items:
                if not isinstance(item, dict):
                    continue
                title = (item.get("name") or item.get("title") or "").strip()
                stream_url = (item.get("url") or item.get("stream_url") or "").strip()
                logo = (item.get("logo") or item.get("image") or "").strip()
                referer = (item.get("referer") or "").strip()
                if title and stream_url and stream_url not in seen:
                    seen.add(stream_url)
                    channels.append(
                        {
                            "title": title,
                            "logo": logo,
                            "group": "⚽ WioSpor Canlı",
                            "referer": referer,
                            "ua": HEADERS_WEB["User-Agent"],
                            "url": stream_url,
                        }
                    )
    except Exception as e:
        log.debug(f"WioSpor JSON hatası: {e}")

    log.info(f"BeyazElma & WioSpor: {len(channels)} yayın eklendi.")
    return channels


def write_m3u(channels: list[dict], filename: str) -> None:
    lines = ["#EXTM3U"]
    for ch in channels:
        lines.append(
            f'#EXTINF:-1 tvg-id="{ch["title"]}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}",{ch["title"]}'
        )
        if ch.get("referer"):
            lines.append(f"#EXTVLCOPT:http-referrer={ch['referer']}")
        lines.append(f"#EXTVLCOPT:http-user-agent={ch['ua']}")
        lines.append("#EXTVLCOPT:http-no-tls-verify")
        lines.append(ch["url"])

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    log.info(f"Toplam {len(channels)} yayın '{filename}' dosyasına kaydedildi.")


async def main() -> None:
    async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
        rectv_list, wiospor_list = await asyncio.gather(
            fetch_rectv_channels(client),
            fetch_beyazelma_and_wiospor(client),
        )
        all_channels = rectv_list + wiospor_list
        write_m3u(all_channels, OUTPUT_FILE)


if __name__ == "__main__":
    asyncio.run(main())
