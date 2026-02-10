import re
import sys
import time
from urllib.parse import urlparse, parse_qs, urljoin
from playwright.sync_api import sync_playwright, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

TARAFTARIUM_DOMAIN = "https://taraftarium24.xyz/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"


def scrape_default_channel_info(page):
    print(f"\n📡 Varsayılan kanal bilgisi alınıyor...")
    try:
        page.goto(TARAFTARIUM_DOMAIN, timeout=180000, wait_until="domcontentloaded")
        iframe_selector = "iframe#customIframe"
        page.wait_for_selector(iframe_selector, timeout=15000)
        iframe = page.query_selector(iframe_selector)

        if not iframe:
            return None, None

        iframe_src = iframe.get_attribute("src")
        event_url = urljoin(TARAFTARIUM_DOMAIN, iframe_src)

        parsed = urlparse(event_url)
        stream_id = parse_qs(parsed.query).get("id", [None])[0]

        return event_url, stream_id

    except Exception:
        return None, None


def extract_base_m3u8_url(page, event_url):
    try:
        page.goto(event_url, timeout=30000, wait_until="domcontentloaded")
        content = page.content()

        match = re.search(r"(https?://[^\"']+/checklist/)", content)
        if match:
            return match.group(1)

        return None

    except Exception:
        return None


def scrape_all_channels(page):
    print(f"\n📡 Kanal listesi çekiliyor...")
    channels = []

    try:
        page.goto(TARAFTARIUM_DOMAIN, timeout=180000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        elements = page.query_selector_all(".mac[data-url]")

        for el in elements:
            name_el = el.query_selector(".takimlar")
            name = name_el.inner_text().strip() if name_el else "İsimsiz Kanal"
            name = name.replace("CANLI", "").strip()

            data_url = el.get_attribute("data-url")
            if not data_url:
                continue

            parsed = urlparse(data_url)
            stream_id = parse_qs(parsed.query).get("id", [None])[0]

            if stream_id:
                channels.append({
                    "name": name,
                    "id": stream_id
                })

        return channels

    except Exception:
        return []


# 🔥 SADELEŞTİRİLMİŞ GRUP MANTIĞI
def get_channel_group(channel_name):
    # Maç yayını tespiti
    if re.search(r"\d{2}:\d{2}", channel_name) or " - " in channel_name:
        return "MAÇ SEÇ İZLE (VPN)"

    # Geri kalan HER ŞEY
    return "ANDRO TV FULL (VPN)"


def main():
    with sync_playwright() as p:
        print("🚀 Taraftarium24 M3U oluşturucu başlatıldı")

        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()

        event_url, default_stream_id = scrape_default_channel_info(page)

        if not event_url:
            print("⚠️ Fallback kullanılıyor")
            base_m3u8_url = "https://andro.okan11gote12sokan.cfd/checklist/"
            channels = [{
                "name": "Varsayılan Kanal",
                "id": default_stream_id or "androstreamlivebs1"
            }]
        else:
            base_m3u8_url = extract_base_m3u8_url(page, event_url)
            channels = scrape_all_channels(page)

        if not base_m3u8_url or not channels:
            print("❌ Kanal veya base URL bulunamadı")
            browser.close()
            return

        output_file = "msi.m3u"

        lines = [
            "#EXTM3U",
            f"#EXT-X-USER-AGENT:{USER_AGENT}",
            f"#EXT-X-ORIGIN:{TARAFTARIUM_DOMAIN.rstrip('/')}"
        ]

        for ch in channels:
            group = get_channel_group(ch["name"])
            m3u8 = f"{base_m3u8_url}{ch['id']}.m3u8"

            lines.append(
                f'#EXTINF:-1 tvg-name="{ch["name"]}" group-title="{group}",{ch["name"]}'
            )
            lines.append(m3u8)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        browser.close()
        print(f"\n✅ {len(channels)} kanal yazıldı → {output_file}")
        print("🎉 İşlem tamamlandı!")


if __name__ == "__main__":
    main()
