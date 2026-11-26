import json
from urllib.request import Request, urlopen

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://sportsbite.org/channels",
}

for endpoint in ["api/forestgump/channels", "api/channels", "api/forestgump/live"]:
    url = f"https://sportsbite.org/{endpoint}"
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=10) as res:
            data = json.loads(res.read().decode("utf-8"))
            print(f"BAŞARILI ({endpoint}):")
            print(json.dumps(data, indent=2)[:1000])  # İlk 1000 karakteri basar
            break
    except Exception as e:
        print(f"Denenen {endpoint} başarısız: {e}")
