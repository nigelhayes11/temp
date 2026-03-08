import requests
import base64
import re
from concurrent.futures import ThreadPoolExecutor

BASE_PATTERN = "https://zeustv{}.com"

START = 200
END = 1200

CHANNELS = [
'b1','b1local','b2','b3','b4','bein5','b1max','b2max',
's1','s2','smart1','smart2','tivibu','tivibu1','tivibu2','tivibu3',
'sifirtv','euro1','euro2','tabiiyedek','tabii1','tabii2','tabii3',
'tabii4','tabii5','tabii6','xexxen','xexxen1'
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
REFERER = "https://google.com/"

HEADERS = {
"User-Agent": USER_AGENT
}


# DOMAIN KONTROL
def check_domain(i):

    domain = BASE_PATTERN.format(i)

    try:

        r = requests.get(domain, headers=HEADERS, timeout=3)

        if r.status_code == 200:
            return domain

    except:
        pass

    return None


# BASE64 ÇÖZ
def extract_base(domain):

    try:

        url = f"{domain}/ch.html?id=b1"

        r = requests.get(url, headers=HEADERS, timeout=5)

        html = r.text

        match = re.search(r'atob\("([A-Za-z0-9+/=]+)"\)', html)

        if match:

            code = match.group(1)

            decoded = base64.b64decode(code).decode()

            if not decoded.endswith("/"):
                decoded += "/"

            return decoded

    except:
        pass

    return None


# STREAM KONTROL
def check_stream(url):

    try:

        r = requests.get(url, headers=HEADERS, timeout=5)

        if "#EXTM3U" in r.text:
            return True

    except:
        pass

    return False


# M3U OLUŞTUR
def create_m3u(base):

    with open("zeus.m3u","w",encoding="utf8") as f:

        f.write("#EXTM3U\n")

        for ch in CHANNELS:

            stream = f"{base}{ch}/index.m3u8"

            if check_stream(stream):

                name = ch.upper()

                f.write(f'#EXTINF:-1 group-title="ZeusTV",{name}\n')
                f.write(f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n')
                f.write(f'#EXTVLCOPT:http-referrer={REFERER}\n')
                f.write(f'{stream}\n')


# ANA
def main():

    print("Domain taranıyor...")

    domains = []

    with ThreadPoolExecutor(max_workers=50) as executor:

        results = executor.map(check_domain, range(START, END))

        for r in results:
            if r:
                domains.append(r)

    print("Bulunan domain:", domains)

    for d in domains:

        base = extract_base(d)

        if base:

            print("Base bulundu:", base)

            create_m3u(base)

            return

    print("Base bulunamadı")


if __name__ == "__main__":
    main()
