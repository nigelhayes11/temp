import os
import csv
import re
import time
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# ======= Ayarlar =======
SHORT_URL   = "https://dengetv54.live/"  # Kısayol link burada
CSV_FILE    = "kanallar.csv"             # Başlıklı CSV: dosya,tvg_id,kanal_adi
OUTPUT_M3U  = "MAN NORMAL TV 2025.m3u"
USER_AGENT  = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
# ========================

def load_channels_from_csv(path):
    """
    Beklenen başlıklar: dosya, tvg_id, kanal_adi
    Hatalara dayanıklı: başlık yoksa 2/3 sütunlu satırları da tolere eder.
    """
    channels = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        sample = f.read(2048)
        f.seek(0)
        has_header = csv.Sniffer().has_header(sample)
        if has_header:
            reader = csv.DictReader(f)
            for row in reader:
                dosya = (row.get("dosya") or "").strip()
                tvg_id = (row.get("tvg_id") or "").strip()
                kanal  = (row.get("kanal_adi") or "").strip()
                if dosya and kanal:
                    channels.append({"dosya": dosya, "tvg_id": tvg_id, "kanal_adi": kanal})
        else:
            r = csv.reader(f)
            for row in r:
                if not row or all(not (c or "").strip() for c in row):
                    continue
                if len(row) >= 3:
                    dosya, tvg_id, kanal = row[0].strip(), row[1].strip(), row[2].strip()
                elif len(row) >= 2:
                    # 2 sütun: kanal adı, dosya
                    kanal, dosya = row[0].strip(), row[1].strip()
                    tvg_id = ""
                else:
                    continue
                if dosya and kanal:
                    channels.append({"dosya": dosya, "tvg_id": tvg_id, "kanal_adi": kanal})
    return channels

def start_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(f"--user-agent={USER_AGENT}")

    # GitHub Actions'ta Chrome'u action kuruyor; lokal/Windows'ta gerek yok.
    chrome_path = os.getenv("CHROME_PATH") or os.getenv("GOOGLE_CHROME_BIN")
    if chrome_path:
        opts.binary_location = chrome_path

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(60)
    return driver

def resolve_url_with_browser(url):
    d = start_driver()
    try:
        d.get(url)
        time.sleep(3)  # yönlendirme için kısa bekleme
        return d.current_url, d.page_source
    finally:
        d.quit()

def fetch_page_source(url):
    d = start_driver()
    try:
        d.get(url)
        time.sleep(3)
        return d.page_source
    finally:
        d.quit()

def extract_baseurl(html):
    # 1) baseurl = "..." veya "baseurl":"..." desenleri
    patterns = [
        r'baseurl\s*[:=]\s*["\']([^"\']+)["\']',
        r'"baseurl"\s*:\s*"([^"]+)"',
        r"data-baseurl\s*=\s*['\"]([^'\"]+)['\"]",
    ]
    for p in patterns:
        m = re.search(p, html, flags=re.IGNORECASE)
        if m:
            return m.group(1)

    # 2) Yedek: HTML içinde tam .m3u8 URL bul, oradan klasör tabanını çıkar
    m = re.search(r'https?://[^"\']+?/(?:[^"\']*?)\.m3u8', html)
    if m:
        full = m.group(0)
        base = full.rsplit("/", 1)[0] + "/"
        return base

    return None

def generate_m3u(base_url, referer, user_agent, channels):
    lines = ["#EXTM3U"]
    for k in channels:
        tvg_id = k["tvg_id"]
        name   = k["kanal_adi"]
        dosya  = k["dosya"]
        lines.append(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{name}",{name}')
        lines.append(f'#EXTVLCOPT:http-user-agent={user_agent}')
        lines.append(f'#EXTVLCOPT:http-referrer={referer}')
        lines.append(urljoin(base_url, dosya))
    return "\n".join(lines)

if __name__ == "__main__":
    print("Kanal listesi CSV'den okunuyor...")
    channels = load_channels_from_csv(CSV_FILE)
    if not channels:
        print("CSV boş ya da okunamadı.")
        raise SystemExit(1)

    print("Kısa URL çözülüyor...")
    site_url, _ = resolve_url_with_browser(SHORT_URL)
    print("Site ana adresi:", site_url)

    # Orijinal mantık: /channel.html?id=yayinzirve
    channel_url = site_url.rstrip("/") + "/channel.html?id=yayinzirve"
    print("Kanal sayfası açılıyor:", channel_url)
    channel_html = fetch_page_source(channel_url)

    base_url = extract_baseurl(channel_html)
    if not base_url:
        print("Base URL bulunamadı.")
        raise SystemExit(1)

    print("Base URL bulundu:", base_url)

    playlist = generate_m3u(base_url, site_url, USER_AGENT, channels)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write(playlist)

    print(f"{OUTPUT_M3U} başarıyla oluşturuldu.")
