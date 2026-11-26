import re
from urllib.request import Request, urlopen

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://sportsbite.org/",
    "Origin": "https://sportsbite.org",
}

# 1. İframe adresinin içindeki gerçek m3u8/stream linkini ara
iframe_url = "https://embed.sportsbite.org/247-embed/embed/bbcone?e=1"
try:
    html = urlopen(Request(iframe_url, headers=headers), timeout=15).read().decode("utf-8", errors="ignore")
    links = re.findall(r'https?://[^\s"\'<>]+(?:m3u8|cdn|hls|stream|token)[^\s"\'<>]*', html)
    print("İframe içinden çıkan linkler:", links)
    if not links:
        print("İframe HTML önizleme:\n", html[:1500])
except Exception as e:
    print("İframe hatası:", e)

# 2. Doğrudan embed.sportsbite.org üzerinde /cdn/ dönüşümünü test et
cdn_url = "https://sportsbite.org"
try:
    res = urlopen(Request(cdn_url, headers=headers), timeout=10)
    print("\nCDN Linki BAŞARILI! Durum:", res.status)
    print("M3U8 İçeriği:\n", res.read().decode("utf-8", errors="ignore")[:300])
except Exception as e:
    print("\nCDN Linki hatası:", e)
