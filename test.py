import re
from urllib.request import Request, urlopen

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://sportsbite.org",
}

url = "https://sportsbite.org"
html = urlopen(Request(url, headers=headers), timeout=15).read().decode("utf-8", errors="ignore")

scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
print(f"Toplam {len(scripts)} adet script bloğu bulundu.\n")

for idx, s in enumerate(scripts, 1):
    if s.strip():
        print(f"--- SCRIPT {idx} ---")
        print(s.strip()[:2000])
