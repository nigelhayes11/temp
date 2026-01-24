import requests
import json

# JSON config oku
with open("config.json", "r", encoding="utf-8") as f:
    cfg = json.load(f)

PREFIXES = cfg["prefixes"]
DOMAIN_RANGE = range(cfg["domain_start"], cfg["domain_end"] + 1)
TLD = cfg["tld"]

PATHS = cfg["paths"]

REFERRER = cfg["referer"]
USER_AGENT = cfg["user_agent"]

HEADERS = {
    "User-Agent": USER_AGENT,
    "Referer": REFERRER
}

OUTPUT = "neon.m3u"

print("🔍 zirvedesin taraması başladı...")

found = 0

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")

    for prefix in PREFIXES:
        for domain in DOMAIN_RANGE:
            base = f"https://{prefix}.zirvedesin{domain}.{TLD}"

            for path in PATHS:
                url = f"{base}/{path}"

                try:
                    r = requests.get(url, headers=HEADERS, timeout=5)
                    if r.status_code == 200 and "#EXTM3U" in r.text:
                        found += 1
                        print("✅ BULUNDU:", url)

                        channel_name = path.replace(".m3u8", "").upper()

                        f.write(f'#EXTINF:-1 group-title="JEST TV",{channel_name}\n')
                        f.write(f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n')
                        f.write(f'#EXTVLCOPT:http-referrer={REFERRER}\n')
                        f.write(url + "\n")
                except:
                    pass

print(f"🎯 neon.m3u hazır | Toplam yayın: {found}")
