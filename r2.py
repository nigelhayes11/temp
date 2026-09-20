import requests
import re
import urllib3
import warnings
import os
import concurrent.futures
import base64
import json
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}
TIMEOUT_VAL = 15
PROXY_URL = "https://seep.eu.org/"
OUTPUT_FILENAME = "r2.m3u"
STATIC_LOGO = "https://i.hizliresim.com/jula4yan.jpg"



import json
import re
from cloudscraper import CloudScraper

def get_palazzo_domain():
    print("🔎 Palazzo aktif domain aranıyor...")
    base_pattern = "https://palazzocanli{}.com"

    def check(i):
        url = base_pattern.format(i)
        try:
            r = requests.get(url, headers=HEADERS, timeout=5, verify=False)
            if (
                r.status_code == 200
                and (
                    "player2.php" in r.text
                    or "primaryStream" in r.text
                    or "decryptUrl" in r.text
                )
            ):
                return url
        except:
            pass
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as ex:
        futures = [ex.submit(check, i) for i in range(28, 201)]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res:
                return res

    return None


def get_palazzo_template(main_html):
    patterns = [
        r'"url":"(https?:\/\/[^"]+?player2\.php\?[^"]*?id=)',
        r'(https:\/\/[^"\']+player2\.php\?[^"\']*?id=)',
        r'(https:\/\/[^"\']+\/player\/player2\.php\?[^"\']*?id=)',
        r'(https:\/\/[^"\']+\/embed\/player2\.php\?[^"\']*?id=)'
    ]

    for pat in patterns:
        m = re.search(pat, main_html)
        if m:
            template = m.group(1)
            template = template.replace('\\/', '/')
            template = template.replace('&amp;', '&')
            print("🎯 Player template bulundu:", template)
            return template

    return None


def fetch_palazzo_channel(cid, player_template, active_site):
    try:
        full_url = f"{player_template}{cid}"
        p_headers = HEADERS.copy()
        
        # PLAYERA BAĞLANIRKEN PALAZZO'NUN GÜNCEL DOMAINİ (active_site) REFERER/ORIGIN KULLANILIYOR
        p_headers["Referer"] = active_site + "/"
        p_headers["Origin"] = active_site

        r = requests.get(full_url, headers=p_headers, timeout=10, verify=False)
        stream = decrypt_palazzo(r.text)

        return cid, stream

    except Exception as e:
        print("FAIL:", cid, e)
        return cid, None


def get_renconnect_content():
    print("--- 6. Palazzo AES Bot (Renconnect) ---")

    channels = [
        ("601", "beIN Sports 1"),
        ("602", "beIN Sports 2"),
        ("603", "beIN Sports 3"),
        ("604", "beIN Sports 4"),
        ("605", "beIN Sports 5"),
        ("607", "S Sport 1"),
        ("608", "S Sport 2"),
        ("609", "Smart Spor 1"),
        ("610", "Smart Spor 2"),
        ("701", "Tivibu Spor 1"),
        ("702", "Tivibu Spor 2"),
        ("703", "Tivibu Spor 3"),
        ("704", "Tivibu Spor 4"),
        ("beinsportshaber", "beIN Haber"),
        ("eurosport1", "Eurosport 1"),
        ("eurosport2", "Eurosport 2"),
    ]

    results_map = {}
    ordered_results = []
    old_links = []

    # Eski linkleri korumak için mevcut dosyadan okuma işlemi
    if os.path.exists(OUTPUT_FILENAME):
        try:
            with open(OUTPUT_FILENAME, 'r', encoding='utf-8') as f:
                content = f.read()
            # Dosyayı #EXTINF bloklarına böl ve sadece renconnect olanları ayıkla
            blocks = content.split('#EXTINF:')
            for block in blocks[1:]:
                if 'group-title="renconnect"' in block:
                    old_links.append('#EXTINF:' + block.strip())
        except Exception as e:
            print(f"Eski linkleri okuma hatasi: {e}")

    active_site = get_palazzo_domain()
    
    # HATA KONTROL 1: Site Bulunamazsa
    if not active_site:
        print("❌ Palazzo: Site bulunamadı")
        if old_links:
            print("⚠️ Mevcut (Eski) renconnect linkleri korunuyor...")
            return old_links
        return []

    print("🌐 Palazzo Domain:", active_site)

    try:
        r = requests.get(active_site, headers=HEADERS, timeout=10, verify=False)
        player_template = get_palazzo_template(r.text)
    except Exception as e:
        player_template = None
        print(f"Palazzo HTML Okuma Hatası: {e}")

    # HATA KONTROL 2: Şablon Çözülemezse
    if not player_template:
        print("❌ Palazzo: Template bulunamadı")
        if old_links:
            print("⚠️ Mevcut (Eski) renconnect linkleri korunuyor...")
            return old_links
        return []

    # PLAYER LİNKİNİN DOMAINİNİ AYIR (M3U ÇIKTISINDA YAYINI OYNATMAK İÇİN REF OLARAK KULLANILACAK)
    parsed_uri = urlparse(player_template)
    player_domain = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
    print(f"🔑 M3U Player Ref Domaini: {player_domain}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        futures = [
            ex.submit(fetch_palazzo_channel, cid, player_template, active_site)
            for cid, _ in channels
        ]

        for f in concurrent.futures.as_completed(futures):
            cid, stream = f.result()
            name = next(n for c, n in channels if c == cid)

            if not stream:
                print("❌ FAIL:", name)
                continue

            print("✅ OK:", name)

            entry = (
                f'#EXTINF:-1 '
                f'tvg-logo="{STATIC_LOGO}" '
                f'group-title="renconnect",{name}\n'
                f'#EXTVLCOPT:http-user-agent={HEADERS["User-Agent"]}\n'
                f'#EXTVLCOPT:http-referrer={player_domain}/\n'
                f'#EXTVLCOPT:http-origin={player_domain}\n'
                f'{stream}'
            )

            results_map[cid] = entry

    for cid, _ in channels:
        if cid in results_map:
            ordered_results.append(results_map[cid])

    # HATA KONTROL 3: Şifreler çözülemez ve 0 kanal çekilirse
    if not ordered_results:
        print("❌ Palazzo: Hiçbir kanal çekilemedi.")
        if old_links:
            print("⚠️ Mevcut (Eski) renconnect linkleri korunuyor...")
            return old_links

    return ordered_results
# ============================================
# MAIN
# ============================================

def main():
    print("🔥 r2 v3.3 Başladı")

    all_content = ["#EXTM3U"]
    all_content.extend(get_r2_content())
  

    try:
        with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
            f.write("\n".join(all_content))

        full_path = os.path.abspath(OUTPUT_FILENAME)
        total_channels = len(all_content) - 1

        print("\n✅ Tamamlandı!")
        print(f"📄 Dosya: {OUTPUT_FILENAME}")
        print(f"📺 Kanal Sayısı: {total_channels}")
        print(f"📂 Konum: {full_path}")

    except IOError as e:
        print(f"\n❌ Hata: {e}")


if __name__ == "__main__":
    main()
