import re
from urllib.request import Request, urlopen

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://sportsbite.org",
}

embed_url = "https://sportsbite.org"
req = Request(embed_url, headers=headers)

with urlopen(req, timeout=15) as res:
    html = res.read().decode("utf-8", errors="ignore")
    print("Sayfa boyutu:", len(html))
    # HTML içindeki tüm m3u8 veya cdn linklerini bul
    links = re.findall(r'https?://[^\s"\'<>]+(?:m3u8|cdn|hls|stream)[^\s"\'<>]*', html)
    print("Bulunan yayın linkleri:", links)
    if not links:
        print("HTML içeriği önizleme:\n", html[:1500])
