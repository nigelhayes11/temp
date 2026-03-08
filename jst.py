import requests
import base64
import re

BASE_DOMAIN_PATTERN = "zeustv{}.com"
START_INDEX = 230
END_INDEX = 500

CHANNEL_IDS = [
'b1','b1local','b2','b3','b4','bein5','b1max','b2max',
's1','s2','smart1','smart2','tivibu','tivibu1','tivibu2','tivibu3',
'sifirtv','euro1','euro2','tabiiyedek','tabii1','tabii2','tabii3',
'tabii4','tabii5','tabii6','xexxen','xexxen1'
]

HEADERS = {
"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
}


def get_base_url(domain):

    url = f"{domain}/ch.html?id=b1"

    try:
        r = requests.get(url, headers=HEADERS, timeout=5)
        html = r.text

        patterns = [
            r'atob\("([A-Za-z0-9+/=]+)"\)',
            r'var\s+\w+\s*=\s*"([A-Za-z0-9+/=]+)"'
        ]

        for p in patterns:
            m = re.search(p, html)
            if m:
                code = m.group(1)
                decoded = base64.b64decode(code).decode()

                if not decoded.endswith("/"):
                    decoded += "/"

                return decoded

    except:
        pass

    return None


def find_working_base():

    for i in range(START_INDEX, END_INDEX+1):

        domain = f"https://{BASE_DOMAIN_PATTERN.format(i)}"

        try:
            r = requests.get(domain, headers=HEADERS, timeout=3)

            if r.status_code == 200:
                print("Aktif domain:", domain)

                base = get_base_url(domain)

                if base:
                    print("Base bulundu:", base)
                    return base

        except:
            pass

    return None


def create_m3u(base):

    with open("zeus.m3u","w",encoding="utf8") as f:

        f.write("#EXTM3U\n")

        for ch in CHANNEL_IDS:

            stream = f"{base}{ch}/index.m3u8"
            name = ch.upper()

            f.write(f'#EXTINF:-1 group-title="ZeusTV",{name}\n')
            f.write(f"{stream}\n")

    print("zeus.m3u oluşturuldu")


def main():

    base = find_working_base()

    if not base:
        print("base bulunamadı")
        return

    create_m3u(base)


if __name__ == "__main__":
    main()
