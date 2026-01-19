import requests

PREFIX = "75d"
DOMAIN_NUM = 114
TLD = "lat"

PATHS = [
    "/yayinzirve.m3u8",
    "/yayinb2.m3u8",
    "/yayinb3.m3u8",
    "/yayinb4.m3u8",
    "/yayinb5.m3u8",
    "/yayinbm1.m3u8",
    "/yayinbm2.m3u8",
    "/yayinss.m3u8",
    "/yayinss2.m3u8"
]

CHANNEL_NAMES = [
    "Neon Kanal 1",
    "Neon Kanal 2",
    "Neon Kanal 3",
    "Neon Kanal 4",
    "Neon Kanal 5",
    "Neon Kanal 6",
    "Neon Kanal 7",
    "Neon Kanal 8",
    "Neon Kanal 9"
]

REFERRER = "https://monotv524.com/"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5)"
OUTPUT = "neon.m3u"

headers = {
    "User-Agent": USER_AGENT,
    "Referer": REFERRER
}

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    for path, channel in zip(PATHS, CHANNEL_NAMES):
        url = f"https://{PREFIX}.zirvedesin{DOMAIN_NUM}.{TLD}{path}"
        try:
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200 and "#EXTM3U" in r.text:
                print("✅ BULUNDU:", url)
                f.write(f'#EXTINF:-1 group-title="Neon Spor",{channel}\n')
                f.write(f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n')
                f.write(f'#EXTVLCOPT:http-referrer={REFERRER}\n')
                f.write(url + "\n")
            else:
                print("❌ BULUNAMADI:", url)
        except Exception as e:
            print("❌ HATA:", url, e)

print("🎯 neon.m3u hazır")
