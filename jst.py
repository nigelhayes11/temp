import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class MonoHybridScraper:
    def __init__(self):
        self.api_url = "https://justintvcanli.online/domain.php"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        self.kanallar = {
            "zirve": "beIN Sports 1 A", "trgoals": "beIN Sports 1 B", "yayin1": "beIN Sports 1 C",
            "b2": "beIN Sports 2", "b3": "beIN Sports 3", "b4": "beIN Sports 4", "b5": "beIN Sports 5",
            "bm1": "beIN Sports 1 Max", "bm2": "beIN Sports 2 Max",
            "ss1": "S Sports 1", "ss2": "S Sports 2",
            "t1": "Tivibu Sports 1", "t2": "Tivibu Sports 2", "t3": "Tivibu Sports 3",
            "t4": "Tivibu Sports 4", "as": "A Spor", "trtspor": "TRT Spor",
            "trtspor2": "TRT Spor Yıldız", "trt1": "TRT 1", "atv": "ATV",
            "tv85": "TV8.5"
        }

    def fetch_assets(self):
        referer = None
        print("🌐 Aktif referer aranıyor...")

        for i in range(530, 580):
            url = f"https://monotv{i}.com"
            try:
                r = requests.get(url, headers=self.headers, timeout=4, verify=False)
                if r.status_code == 200:
                    referer = url + "/"
                    print(f"✅ Referer bulundu: {referer}")
                    break
            except:
                pass

        if not referer:
            referer = "https://justintvcanli.online/"
            print("⚠️ Yedek referer kullanılıyor")

        stream = None
        try:
            r = requests.get(self.api_url, headers=self.headers, timeout=8, verify=False)
            if r.status_code == 200:
                stream = r.json().get("baseurl", "").replace("\\", "")
        except:
            pass

        return referer, stream

    def run(self):
        referer, stream = self.fetch_assets()

        if not stream:
            print("❌ Stream adresi alınamadı")
            return

        stream = stream.rstrip("/")
        ua = "Mozilla/5.0"

        m3u = ["#EXTM3U"]

        for cid, name in self.kanallar.items():
            m3u.append(f'#EXTINF:-1 group-title="JEST SPOR",{name}')
            # 🔥 Televizo uyumlu: Referer + UA URL içine gömülü
            m3u.append(
                f'{stream}/{cid}/mono.m3u8'
                f'|Referer={referer}&User-Agent={ua}'
            )

        with open("jst.m3u", "w", encoding="utf-8") as f:
            f.write("\n".join(m3u))

        print(f"🏁 Televizo uyumlu M3U hazır ({len(self.kanallar)} kanal)")

if __name__ == "__main__":
    MonoHybridScraper().run()
