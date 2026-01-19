import requests

PREFIXES = ["75d", "j5d", "k3d", "a9d"]
DOMAIN_NUM_START = 110
DOMAIN_NUM_END = 130
TLDS = ["lat", "cfd"]

PATHS = [
    "/yayinzirve.m3u8",
    "/yayinb2.m3u8",
    "/yayinb3.m3u8",
    "/yayinb4.m3u8",
    "/yayinb5.m3u8",
    "/yayinbm1.m3u8",
    "/yayinbm2.m3u8",
    "/yayinss.m3u8",
    "/yayinss2.m3u8",
    "/yayinex1.m3u8",
    "/yayinex2.m3u8",
    "/yayinex3.m3u8",
    "/yayinex4.m3u8",
    "/yayinex5.m3u8",
    "/yayinex6.m3u8",
    "/yayinex7.m3u8",
    "/yayinex8.m3u8",
    "/yayinsmarts.m3u8",
    "/yayinsms2.m3u8",
    "/yayint1.m3u8",
    "/yayint2.m3u8",
    "/yayint3.m3u8",
    "/yayinatv.m3u8",
]

CHANNELS = [
    {
        "name": "BeIN Sport 1",
        "tvg_id": "bein_sport",
        "logo": "https://seeklogo.com/images/B/bein-sports-1-logo-4E5E4AE6B8-seeklogo.com.png",
        "group": "Spor - Maç"
    },
    {
        "name": "BeIN Sport 2",
        "tvg_id": "bein_sport",
        "logo": "https://seeklogo.com/images/B/bein-sports-2-logo-56F85DDE25-seeklogo.com.png",
        "group": "Spor - Maç"
    },
    # ... diğer tüm kanalları buraya aynı formatta ekle
]

REFERRER = "https://monotv529.com/"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5)"

OUTPUT = "neon.m3u"

headers = {
    "User-Agent": USER_AGENT,
    "Referer": REFERRER
}

def find_stream(path):
    for num in range(DOMAIN_NUM_START, DOMAIN_NUM_END + 1):
        for prefix in PREFIXES:
            for tld in TLDS:
                url = f"https://{prefix}.zirvedesin{num}.{tld}{path}"
                try:
                    r = requests.get(url, headers=headers, timeout=8)
                    if r.status_code == 200 and "#EXTM3U" in r.text:
                        print("✅ BULUNDU:", url)
                        return url
                    else:
                        print("❌", url)
                except:
                    pass
    return None

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    for i, path in enumerate(PATHS):
        stream = find_stream(path)
        if stream:
            channel = CHANNELS[i] if i < len(CHANNELS) else {
                "name": f"Kanal {i+1}", "tvg_id": "", "logo": "", "group": "Spor"
            }
            f.write(f'#EXTINF:-1 tvg-id="{channel["tvg_id"]}" tvg-name="{channel["name"]}" tvg-logo="{channel["logo"]}" group-title="{channel["group"]}",{channel["name"]}\n')
            f.write(f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n')
            f.write(f'#EXTVLCOPT:http-referrer={REFERRER}\n')
            f.write(stream + "\n")
        else:
            print(f"⚠️ Stream bulunamadı: {path}")

print(f"🎯 {OUTPUT} dosyası hazır")
