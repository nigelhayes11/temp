import requests
import re

BASE_DOMAIN_NUM = 117   # sadece burası değişir
TLD = "lat"

REFERRER = "https://monotv524.com/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5)"

OUTPUT = "neon.m3u"

headers = {
    "User-Agent": UA,
    "Referer": REFERRER
}

def find_active_subdomain():
    main_url = f"https://zirvedesin{BASE_DOMAIN_NUM}.{TLD}"
    print("🔍 Ana site çekiliyor:", main_url)

    r = requests.get(main_url, headers=headers, timeout=10)
    html = r.text

    # j7i tarzı subdomain yakala
    pattern = rf"https://([a-z0-9]{{3}})\.zirvedesin{BASE_DOMAIN_NUM}\.{TLD}"
    matches = set(re.findall(pattern, html))

    print("🧩 Bulunan adaylar:", matches)

    for sub in matches:
        test_url = f"https://{sub}.zirvedesin{BASE_DOMAIN_NUM}.{TLD}/yayinzirve.m3u8"
        try:
            t = requests.get(test_url, headers=headers, timeout=5)
            if t.status_code == 200 and "#EXTM3U" in t.text:
                print("✅ ÇALIŞAN BULUNDU:", test_url)
                return test_url
        except:
            pass

    return None


def write_m3u(url):
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write('#EXTINF:-1 group-title="ZİRVEDE",YAYIN ZİRVE\n')
        f.write(f"#EXTVLCOPT:http-user-agent={UA}\n")
        f.write(f"#EXTVLCOPT:http-referrer={REFERRER}\n")
        f.write(url + "\n")

    print("🎯 M3U OLUŞTU:", OUTPUT)


def main():
    stream = find_active_subdomain()
    if not stream:
        print("❌ Yayın bulunamadı")
        return

    write_m3u(stream)


if __name__ == "__main__":
    main()import requests

PREFIX = "v79"
DOMAIN_NUM = 116
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
    "BEİN 1",
    "BEİN 2",
    "BEİN 3",
    "BEİN 4",
    "BEİN 5",
    "BEİN MX1",
    "BEİN MX2",
    "SSPORT",
    "SSPORT2",
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
                f.write(f'#EXTINF:-1 group-title="JEST TV",{channel}\n')
                f.write(f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n')
                f.write(f'#EXTVLCOPT:http-referrer={REFERRER}\n')
                f.write(url + "\n")
            else:
                print("❌ BULUNAMADI:", url)
        except Exception as e:
            print("❌ HATA:", url, e)

print("🎯 neon.m3u hazır")
