import re
from urllib.request import Request, urlopen

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://sportsbite.org/",
}

# 1. Embed sayfasının kendi HTML/JS kodunu çek
embed_url = "https://sportsbite.org"
html = urlopen(Request(embed_url, headers=headers), timeout=15).read().decode("utf-8", errors="ignore")
print("--- EMBED SAYFASI ---")
print(html[:3500])

# 2. Ana sitedeki hls-loader JS dosyasını çek
js_url = "https://sportsbite.org"
js = urlopen(Request(js_url, headers=headers), timeout=15).read().decode("utf-8", errors="ignore")
print("\n--- HLS LOADER JS ---")
print(js[:3500])

