from httpx import Client
import os

class Dengetv54Manager:
    def __init__(self, ana_m3u_dosyasi):
        self.ana_m3u_dosyasi = ana_m3u_dosyasi
        self.httpx = Client(timeout=10, verify=False)
        self.base_stream_url = "https://four.zirvestream4.cfd/"
        self.referer_url = None
        self.channel_files = {
            1: "yayinzirve.m3u8",
            2: "yayin1.m3u8",
            3: "yayininat.m3u8",
            4: "yayinb2.m3u8",
            5: "yayinb3.m3u8",
            6: "yayinb4.m3u8",
            7: "yayinb5.m3u8",
            8: "yayinbm1.m3u8",
            9: "yayinbm2.m3u8",
            10: "yayinss.m3u8",
            11: "yayinss2.m3u8",
            13: "yayint1.m3u8",
            14: "yayint2.m3u8",
            15: "yayint3.m3u8",
            16: "yayinsmarts.m3u8",
            17: "yayinsms2.m3u8",
            18: "yayintrtspor.m3u8",
            19: "yayintrtspor2.m3u8",
            20: "yayintrt1.m3u8",
            21: "yayinas.m3u8",
            22: "yayinatv.m3u8",
            23: "yayintv8.m3u8",
            24: "yayintv85.m3u8",
            25: "yayinf1.m3u8",
            26: "yayinnbatv.m3u8",
            27: "yayineu1.m3u8",
            28: "yayineu2.m3u8",
            29: "yayinex1.m3u8",
            30: "yayinex2.m3u8",
            31: "yayinex3.m3u8",
            32: "yayinex4.m3u8",
            33: "yayinex5.m3u8",
            34: "yayinex6.m3u8",
            35: "yayinex7.m3u8",
            36: "yayinex8.m3u8"
        }

    def find_working_domain(self):
        headers = {"User-Agent": "Mozilla/5.0"}
        for i in range(54, 105):  # 54'ten 104'e kadar
            test_domain = f"https://dengetv{i}.live/"
            print(f"🔍 {test_domain} kontrol ediliyor...")
            try:
                r = self.httpx.get(test_domain, headers=headers)
                if r.status_code == 200 and r.text.strip():
                    print(f"✅ Çalışan domain bulundu: {test_domain}")
                    return test_domain
            except:
                continue
        print("❌ Hiçbir domain bulunamadı!")
        return None

    def build_m3u8_content(self):
        m3u_content = []
        for idx, file_name in self.channel_files.items():
            channel_name = file_name.replace(".m3u8", "").capitalize()
            m3u_content.append(f'#EXTINF:-1 group-title="Dengetv54",{channel_name}')
            m3u_content.append('#EXTVLCOPT:http-user-agent=Mozilla/5.0')
            m3u_content.append(f'#EXTVLCOPT:http-referrer={self.referer_url}')
            m3u_content.append(f"{self.base_stream_url}{file_name}")
        return "\n".join(m3u_content)

    def ana_m3u_guncelle(self, yeni_icerik):
        if not os.path.exists(self.ana_m3u_dosyasi):
            raise FileNotFoundError(f"Dosya bulunamadı: {self.ana_m3u_dosyasi}")
        
        with open(self.ana_m3u_dosyasi, "r", encoding='utf-8') as dosya:
            ana_icerik = dosya.read()

        lines = ana_icerik.split("\n")
        filtered_lines = []
        skip = False
        for line in lines:
            if line.startswith("#EXTINF") and 'group-title="Dengetv54"' in line:
                skip = True
                continue
            if skip and line and not line.startswith("#EXTINF"):
                continue
            skip = False
            filtered_lines.append(line)

        yeni_dosya_icerik = "\n".join(filtered_lines) + "\n\n" + yeni_icerik
        with open(self.ana_m3u_dosyasi, "w", encoding='utf-8') as dosya:
            dosya.write(yeni_dosya_icerik)

    def calistir(self):
        self.referer_url = self.find_working_domain()
        if not self.referer_url:
            return
        
        m3u8_icerik = self.build_m3u8_content()
        self.ana_m3u_guncelle(m3u8_icerik)
        print("✅ Dengetv54 kanalları başarıyla eklendi.")

if __name__ == "__main__":
    manager = Dengetv54Manager("https://github.com/nigelhayes11/temp/blob/main/omit.m3u")
    manager.calistir()
