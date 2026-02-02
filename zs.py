import requests
import re
import sys

def main():
    try:
        # Domain aralığı (25–99)
        active_domain = None
        print("🔍 Aktif domain aranıyor...")
        
        for i in range(25, 1000):
            url = f"https://zeustv{i}.com/"
            try:
                r = requests.head(url, timeout=5)
                if r.status_code == 200:
                    active_domain = url
                    print(f"✅ Aktif domain bulundu: {active_domain}")
                    break
            except Exception as e:
                continue
        
        if not active_domain:
            print("⚠️  Aktif domain bulunamadı. Boş M3U dosyası oluşturuluyor...")
            create_empty_m3u()
            return 0
        
        # İlk kanal ID'si al
        print("📡 Kanal ID'si alınıyor...")
        try:
            html = requests.get(active_domain, timeout=10).text
            m = re.search(r'<iframe[^>]+id="matchPlayer"[^>]+src="event\.html\?id=([^"]+)"', html)
            
            if not m:
                print("⚠️  Kanal ID bulunamadı. Boş M3U dosyası oluşturuluyor...")
                create_empty_m3u()
                return 0
            
            first_id = m.group(1)
            print(f"✅ Kanal ID bulundu: {first_id}")
            
        except Exception as e:
            print(f"⚠️  HTML alınırken hata: {str(e)}")
            create_empty_m3u()
            return 0
        
        # Base URL çek
        print("🔗 Base URL alınıyor...")
        try:
            event_source = requests.get(active_domain + "event.html?id=" + first_id, timeout=10).text
            b = re.search(r'const\s+baseurls\s*=\s*\[\s*"([^"]+)"', event_source)
            
            if not b:
                print("⚠️  Base URL bulunamadı. Boş M3U dosyası oluşturuluyor...")
                create_empty_m3u()
                return 0
            
            base_url = b.group(1)
            print(f"✅ Base URL bulundu: {base_url}")
            
        except Exception as e:
            print(f"⚠️  Event source alınırken hata: {str(e)}")
            create_empty_m3u()
            return 0
        
        # Kanal listesi
        channels = [
            ("beIN Sport 1 HD","bein1","bn TV"),
            ("beIN Sport 2 HD","bein2","bn TV"),
            ("beIN Sport 3 HD","bein3","bn TV"),
            ("beIN Sport 4 HD","bein4","bn TV"),
            ("beIN Sport 5 HD","bein5","bn TV"),
            
        ]
        
        # M3U dosyası oluştur
        print("📝 M3U dosyası oluşturuluyor...")
        lines = [""]
        for name, cid, title in channels:
            lines.append(f'#EXTINF:-1 tvg-id="sport.tr" tvg-name="TR:{name}" group-title="{title}" ,{name}')
            full_url = f"{base_url}{cid}.m3u8"
            lines.append(full_url)
        
        with open("zs.m3u", "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        print(f"✅ zs.m3u başarıyla oluşturuldu ({len(channels)} kanal)")
        return 0
        
    except Exception as e:
        print(f"❌ Beklenmeyen hata: {str(e)}")
        print("⚠️  Boş M3U dosyası oluşturuluyor...")
        create_empty_m3u()
        return 0

def create_empty_m3u():
    """Hata durumunda boş/placeholder M3U dosyası oluştur"""
    try:
        with open("zs.m3u", "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            f.write("# Kanal listesi şu anda kullanılamıyor\n")
        print("✅ Placeholder M3U dosyası oluşturuldu")
    except Exception as e:
        print(f"❌ M3U dosyası oluşturulamadı: {str(e)}")

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
