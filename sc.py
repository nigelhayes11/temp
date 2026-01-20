import requests
import re

def find_working_sporcafe(start=1, end=100):
    print("🧭 sporcafe domainleri taranıyor...")
    headers = {"User-Agent": "Mozilla/5.0"}

    for i in range(start, end + 1):
        url = f"https://www.sporcafe{i}.xyz/"
        print(f"🔍 Taranıyor: {url}")
        try:
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200 and "uxsyplayer" in response.text:
                print(f"✅ Aktif domain bulundu: {url}")
                return response.text, url
        except:
            continue

    print("❌ Aktif domain bulunamadı.")
    return None, None


def find_dynamic_player_domain(page_html):
    match = re.search(r'https?://(main\.uxsyplayer[0-9a-zA-Z\-]+\.click)', page_html)
    if match:
        return f"https://{match.group(1)}"
    return None


def extract_base_stream_url(html):
    match = re.search(r'this\.adsBaseUrl\s*=\s*[\'"]([^\'"]+)', html)
    if match:
        return match.group(1)
    return None


def build_m3u8_links(stream_domain, referer, channel_ids):
    m3u8_links = []
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": referer
    }

    for cid in channel_ids:
        try:
            url = f"{stream_domain}/index.php?id={cid}"
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                base_url = extract_base_stream_url(response.text)
                if base_url:
                    full_url = f"{base_url}{cid}/playlist.m3u8"
                    print(f"✅ {cid} için M3U8 bulundu")
                    m3u8_links.append((cid, full_url))
        except:
            continue

    return m3u8_links


def write_m3u_file(m3u8_links, filename="cafe.m3u", referer=""):
    lines = ["#EXTM3U"]

    for cid, url in m3u8_links:
        kanal_adi = cid.replace("-", " ").title()
        lines.append(
            f'#EXTINF:-1 group-title="Spor Cafe",{kanal_adi}'
        )
        lines.append(f'#EXTVLCOPT:http-referrer={referer}')
        lines.append(url)

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"✅ cafe.m3u oluşturuldu ({len(m3u8_links)} kanal)")


# Kanal ID listesi
channel_ids = [
    "sbeinsports-1",
    "sbeinsports-2",
    "sbeinsports-3",
    "sbeinsports-4",
    "sbeinsports-5",
    "sbeinsportsmax-1",
    "sbeinsportsmax-2",
    "sssport",
    "sssport2",
    "ssmartspor",
    "ssmartspor2",
    "stivibuspor-1",
    "stivibuspor-2",
    "stivibuspor-3",
    "stivibuspor-4",
    "sbeinsportshaber",
    "saspor",
    "seurosport1",
    "seurosport2",
    "sf1",
    "stabiispor",
    "strt1",
    "stv8",
    "strtspor",
    "strtspor2",
    "satv",
    "sdazn1",
    "sdazn2",
    "sssportplus1"
]


# Ana akış
html, referer_url = find_working_sporcafe()

if html:
    stream_domain = find_dynamic_player_domain(html)
    if stream_domain:
        print(f"🔗 Yayın domaini: {stream_domain}")
        m3u8_list = build_m3u8_links(stream_domain, referer_url, channel_ids)
        if m3u8_list:
            write_m3u_file(m3u8_list, referer=referer_url)
        else:
            print("❌ Yayın bulunamadı")
    else:
        print("❌ Player domaini bulunamadı")
else:
    print("⛔ Aktif site yok")
