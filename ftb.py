import requests
import re
import sys
from bs4 import BeautifulSoup

def main():
    try:
        # Domain aralığı
        active_domain = None
        print("🔍 Aktif domain aranıyor...")
        
        for i in range(1497, 2000):
            url = f"https://trgoals{i}.xyz/"
            try:
                r = requests.head(url, timeout=5)
                if r.status_code == 200:
                    active_domain = url
                    print(f"✅ Aktif domain bulundu: {active_domain}")
                    break
            except Exception:
                continue
        
        if not active_domain:
            print("⚠️  Aktif domain bulunamadı. Boş M3U dosyası oluşturuluyor...")
            with open("ftb.m3u", "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
            return 0

        # Base URL çek
        print("🔗 Base URL alınıyor...")
        try:
            channel_url = active_domain + "channel.html?id=yayinzirve"
            event_source = requests.get(channel_url, timeout=10).text
            
            b = re.search(r'baseUrl\s*[:=]\s*["\']([^"\']+)["\']', event_source)
            
            if not b:
                print("⚠️  Base URL bulunamadı. Boş M3U dosyası oluşturuluyor...")
                with open("ftb.m3u", "w", encoding="utf-8") as f:
                    f.write("#EXTM3U\n")
                return 0
            
            base_url = b.group(1)
            print(f"✅ Base URL bulundu: {base_url}")
            
        except Exception as e:
            print(f"⚠️  Base URL alınırken hata: {str(e)}")
            with open("ftb.m3u", "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
            return 0
        
        # Dinamik kanal listesi çek
        print("📡 Dinamik kanal listesi alınıyor...")
        try:
            response = requests.get(active_domain, timeout=10)
            response.encoding = 'utf-8'
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')
            
            matches_tab = soup.find(id='matches-tab')
            if not matches_tab:
                print("⚠️  matches-tab bulunamadı. Boş M3U dosyası oluşturuluyor...")
                with open("ftb.m3u", "w", encoding="utf-8") as f:
                    f.write("#EXTM3U\n")
                return 0
            
            channel_links = matches_tab.find_all('a', href=re.compile(r'/channel\.html\?id='))
            if not channel_links:
                print("⚠️  Kanal linki bulunamadı. Boş M3U dosyası oluşturuluyor...")
                with open("ftb.m3u", "w", encoding="utf-8") as f:
                    f.write("#EXTM3U\n")
                return 0
            
            channels = []
            for link in channel_links:
                href = link.get('href', '')
                id_match = re.search(r'id=([^&]+)', href)
                if not id_match:
                    continue
                cid = id_match.group(1)
                
                channel_name_elem = link.find(class_='channel-name')
                channel_status_elem = link.find(class_='channel-status')
                if not channel_name_elem or not channel_status_elem:
                    continue
                
                channel_name = channel_name_elem.get_text(strip=True)
                channel_time = channel_status_elem.get_text(strip=True)
                
                display_name = f"{channel_time} | {channel_name}"
                channels.append({
                    'cid': cid,
                    'name': display_name
                })
            
            print(f"✅ {len(channels)} kanal bulundu")
            
        except Exception as e:
            print(f"⚠️  Kanal listesi alınırken hata: {str(e)}")
            with open("ftb.m3u", "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
            return 0
        
        # M3U dosyası oluştur
        print("📝 M3U dosyası oluşturuluyor...")
        with open("ftb.m3u", "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")  # MUTLAKA BAŞTA
            for channel in channels:
                cid = channel['cid']
                name = channel['name']
                
                f.write(f'#EXTINF:-1 group-title="TR MAÇ SEÇ İZLE",{name}\n')
                f.write(f'#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5)\n')
                f.write(f'#EXTVLCOPT:http-referrer={active_domain}\n')
                f.write(f'{base_url}{cid}.m3u8\n')
        
        print(f"✅ ftb.m3u başarıyla oluşturuldu ({len(channels)} kanal)")
        return 0
        
    except Exception as e:
        print(f"❌ Beklenmeyen hata: {str(e)}")
        with open("ftb.m3u", "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
        return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
