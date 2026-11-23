import re
import urllib.parse
import requests
from bs4 import BeautifulSoup

START_URL = "https://beyazelma78.com"
OUTPUT_M3U = "beyazelma.m3u"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

def get_active_domain(session, url):
    try:
        res = session.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        parsed = urllib.parse.urlparse(res.url)
        return f"{parsed.scheme}://{parsed.netloc}/", res.text
    except Exception as e:
        print(f"Başlangıç adresine erişilemedi: {e}")
        return None, None

def extract_m3u8(session, page_url, referer):
    try:
        res = session.get(page_url, headers={**HEADERS, "Referer": referer}, timeout=10)
        m3u8 = re.findall(r'https?://[^\s"\'<>\\]+?\.m3u8[^\s"\'<>\\]*', res.text)
        if m3u8:
            return m3u8[0]

        soup = BeautifulSoup(res.text, "html.parser")
        for iframe in soup.find_all("iframe", src=True):
            iframe_url = urllib.parse.urljoin(page_url, iframe["src"])
            res2 = session.get(iframe_url, headers={**HEADERS, "Referer": page_url}, timeout=10)
            m3u8_2 = re.findall(r'https?://[^\s"\'<>\\]+?\.m3u8[^\s"\'<>\\]*', res2.text)
            if m3u8_2:
                return m3u8_2[0]
    except Exception:
        pass
    return None

def main():
    session = requests.Session()
    base_url, html = get_active_domain(session, START_URL)
    if not base_url or not html:
        return

    soup = BeautifulSoup(html, "html.parser")
    channels = []
    seen_urls = set()

    for a in soup.find_all("a", href=True):
        title = re.sub(r'\s+', ' ', a.get_text(strip=True))
        href = a["href"].strip()
        if not title or len(title) < 2 or href.startswith(("#", "javascript:", "mailto:", "tg:")):
            continue

        full_url = urllib.parse.urljoin(base_url, href)
        if base_url not in full_url or full_url in seen_urls or full_url == base_url:
            continue

        seen_urls.add(full_url)
        stream_url = extract_m3u8(session, full_url, base_url)
        if stream_url:
            channels.append((title, stream_url))

    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for name, link in channels:
            f.write(f'#EXTINF:-1 group-title="BeyazElma",{name}\n')
            f.write(f'#EXTVLCOPT:http-referrer={base_url}\n')
            f.write(f"{link}\n")

    print(f"Güncel Domain: {base_url} | Kaydedilen Kanal: {len(channels)}")

if __name__ == "__main__":
    main()
