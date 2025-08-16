import re
from datetime import datetime
from httpx import Client

# ---------------- Dengetv54 ----------------
class Dengetv54Manager:
    def __init__(self):
        self.httpx = Client(timeout=10, verify=False)
        self.base_stream_url = None  # Dinamik alınacak
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
        for i in range(54, 105):
            url = f"https://dengetv{i}.live/"
            try:
                r = self.httpx.get(url, headers=headers)
                if r.status_code == 200 and r.text.strip():
                    # HTML içinden zirvestreamX.cfd domainini yakala
                    match = re.search(r"https://[a-z0-9\-\.]*zirvestream\d+\.cfd", r.text)
                    if match:
                        self.base_stream_url = match.group(0) + "/"
                        return url
            except:
                continue
        # fallback (hiç bulunamazsa)
        self.base_stream_url = "https://four.zirvestream5.cfd/"
        return "https://dengetv54.live/"

    def build_m3u8_content(self, referer_url):
        if not self.base_stream_url:
            raise ValueError("Dengetv54: Base stream URL bulunamadı!")
        m3u = []
        for _, file_name in self.channel_files.items():
            channel_name = file_name.replace(".m3u8", "").capitalize()
            m3u.append(f'#EXTINF:-1 group-title="Dengetv54",{channel_name}')
            m3u.append('#EXTVLCOPT:http-user-agent=Mozilla/5.0')
            m3u.append(f'#EXTVLCOPT:http-referrer={referer_url}')
            m3u.append(f'{self.base_stream_url}{file_name}')
        return "\n".join(m3u)

    def calistir(self):
        referer = self.find_working_domain()
        m3u = self.build_m3u8_content(referer)
        print(f"Dengetv54: içerik uzunluğu {len(m3u)}")
        return m3u


# ---------------- XYZsports ----------------
class XYZsportsManager:
    def __init__(self, channel_ids=None):
        self.httpx = Client(timeout=10, verify=False)
        self.channel_ids = channel_ids or [
            "bein-sports-1", "bein-sports-2", "bein-sports-3",
            "bein-sports-4", "bein-sports-5", "bein-sports-max-1",
            "bein-sports-max-2", "smart-spor", "smart-spor-2",
            "trt-spor", "trt-spor-2", "aspor", "s-sport",
            "s-sport-2", "s-sport-plus-1", "s-sport-plus-2"
        ]

    def find_working_domain(self, start=248, end=350):
        headers = {"User-Agent": "Mozilla/5.0"}
        for i in range(start, end + 1):
            url = f"https://www.xyzsports{i}.xyz/"
            try:
                r = self.httpx.get(url, headers=headers)
                if r.status_code == 200 and "uxsyplayer" in r.text:
                    return r.text, url
            except:
                continue
        return None, None

    def find_dynamic_player_domain(self, html):
        m = re.search(r'https?://([a-z0-9\-]+\.[0-9a-z]+\.click)', html)
        return f"https://{m.group(1)}" if m else None

    def extract_base_stream_url(self, html):
        m = re.search(r'this\.baseStreamUrl\s*=\s*[\'"]([^\'"]+)', html)
        return m.group(1) if m else None

    def build_m3u8_content(self, base_url, referer_url):
        m3u = []
        for cid in self.channel_ids:
            channel_name = cid.replace("-", " ").title()
            m3u.append(f'#EXTINF:-1 group-title="XYZSport",{channel_name}')
            m3u.append('#EXTVLCOPT:http-user-agent=Mozilla/5.0')
            m3u.append(f'#EXTVLCOPT:http-referrer={referer_url}')
            m3u.append(f'{base_url}{cid}/playlist.m3u8')
        return "\n".join(m3u)

    def calistir(self):
        html, referer_url = self.find_working_domain()
        if not html:
            print("XYZsports: Çalışan domain bulunamadı!")
            return ""
        player_domain = self.find_dynamic_player_domain(html)
        if not player_domain:
            print("XYZsports: Player domain bulunamadı!")
            return ""
        r = self.httpx.get(f"{player_domain}/index.php?id={self.channel_ids[0]}", headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": referer_url
        })
        base_url = self.extract_base_stream_url(r.text)
        if not base_url:
            print("XYZsports: Base stream URL bulunamadı!")
            return ""
        return self.build_m3u8_content(base_url, referer_url)


# ---------------- Main ----------------
if __name__ == "__main__":
    CIKTI_DOSYASI = "cinos.m3u"

    all_m3u = ["#EXTM3U"]

    # Dengetv54
    dengetv = Dengetv54Manager()
    all_m3u.append(dengetv.calistir())

    # XYZsports
    xyz = XYZsportsManager()
    m3u_xyz = xyz.calistir()
    if m3u_xyz:
        all_m3u.append(m3u_xyz)

    # Timestamp ekle
    all_m3u.append(f'# Generated: {datetime.utcnow().isoformat()}')

    with open(CIKTI_DOSYASI, "w", encoding="utf-8") as f:
        f.write("\n".join(all_m3u))

    print(f"✅ cinos M3U oluşturuldu: {CIKTI_DOSYASI}")


from Kekik.cli import konsol
from httpx     import Client
from parsel    import Selector
import re

class TRGoals:
    def __init__(self, m3u_dosyasi):
        self.m3u_dosyasi = m3u_dosyasi
        self.httpx       = Client(timeout=10, verify=False)

    def referer_domainini_al(self):
        referer_deseni = r'#EXTVLCOPT:http-referrer=(https?://[^/]*trgoals[^/]*\.[^\s/]+)'
        with open(self.m3u_dosyasi, "r") as dosya:
            icerik = dosya.read()

        if eslesme := re.search(referer_deseni, icerik):
            return eslesme[1]
        else:
            raise ValueError("M3U dosyasında 'trgoals' içeren referer domain bulunamadı!")

    def trgoals_domaini_al(self):
        redirect_url = "https://bit.ly/m/taraftarium24w"
        deneme = 0
        while "bit.ly" in redirect_url and deneme < 5:
            try:
                redirect_url = self.redirect_gec(redirect_url)
            except Exception as e:
                konsol.log(f"[red][!] redirect_gec hata: {e}")
                break
            deneme += 1

        if "bit.ly" in redirect_url or "error" in redirect_url:
            konsol.log("[yellow][!] 5 denemeden sonra bit.ly çözülemedi, yedek linke geçiliyor...")
            try:
                redirect_url = self.redirect_gec("https://t.co/aOAO1eIsqE")
            except Exception as e:
                raise ValueError(f"Yedek linkten de domain alınamadı: {e}")

        return redirect_url

    def redirect_gec(self, redirect_url: str):
        konsol.log(f"[cyan][~] redirect_gec çağrıldı: {redirect_url}")
        try:
            response = self.httpx.get(redirect_url, follow_redirects=True)
        except Exception as e:
            raise ValueError(f"Redirect sırasında hata oluştu: {e}")

        # Tüm yönlendirme zincirlerini al
        tum_url_listesi = [str(r.url) for r in response.history] + [str(response.url)]

        # İlk "trgoals" içeren linki bul
        for url in tum_url_listesi[::-1]:  # sondan başlayarak kontrol et
            if "trgoals" in url:
                return url.strip("/")

        raise ValueError("Redirect zincirinde 'trgoals' içeren bir link bulunamadı!")

    def yeni_domaini_al(self, eldeki_domain: str) -> str:
        def check_domain(domain: str) -> str:
            if domain == "https://trgoalsgiris.xyz":
                raise ValueError("Yeni domain alınamadı")
            return domain

        try:
            # İlk kontrol: Redirect geçiş
            yeni_domain = check_domain(self.redirect_gec(eldeki_domain))
        except Exception:
            konsol.log("[red][!] `redirect_gec(eldeki_domain)` fonksiyonunda hata oluştu.")
            try:
                # İkinci kontrol: trgoals domainini al
                yeni_domain = check_domain(self.trgoals_domaini_al())
            except Exception:
                konsol.log("[red][!] `trgoals_domaini_al` fonksiyonunda hata oluştu.")
                try:
                    # Üçüncü kontrol: Alternatif bir URL üzerinden redirect geç
                    yeni_domain = check_domain(self.redirect_gec("https://t.co/MTLoNVkGQN"))
                except Exception:
                    konsol.log("[red][!] `redirect_gec('https://t.co/MTLoNVkGQN')` fonksiyonunda hata oluştu.")
                    # Son çare: Yeni bir domain üret
                    rakam = int(eldeki_domain.split("trgoals")[1].split(".")[0]) + 1
                    yeni_domain = f"https://trgoals{rakam}.xyz"

        return yeni_domain

    def m3u_guncelle(self):
        eldeki_domain = self.referer_domainini_al()
        konsol.log(f"[yellow][~] Bilinen Domain : {eldeki_domain}")
    
        yeni_domain = self.yeni_domaini_al(eldeki_domain)
        konsol.log(f"[green][+] Yeni Domain    : {yeni_domain}")
    
        kontrol_url = f"{yeni_domain}/channel.html?id=yayin1"
    
        with open(self.m3u_dosyasi, "r") as dosya:
            m3u_icerik = dosya.read()
    
        # Sadece "# * » Spor « * #" başlığı altındaki kısmı bul
        desen = r"(# \* » Spor « \* #\s*)(.*?)(\n# \*|$)"  # Bir sonraki başlığa kadar al
        eslesme = re.search(desen, m3u_icerik, re.DOTALL)
    
        if not eslesme:
            raise ValueError("Spor başlığı bulunamadı!")
    
        spor_baslik = eslesme[1]
        spor_icerik = eslesme[2]
        sonraki_baslik = eslesme[3]
    
        if not (eski_yayin_url := re.search(r'https?:\/\/[^\/]+\.(workers\.dev|shop|click|lat)\/?', spor_icerik)):
            raise ValueError("Spor bölümünde eski yayın URL'si bulunamadı!")
    
        eski_yayin_url = eski_yayin_url[0]
        konsol.log(f"[yellow][~] Eski Yayın URL : {eski_yayin_url}")
    
        response = self.httpx.get(kontrol_url, follow_redirects=True)
    
        if not (yayin_ara := re.search(r'(?:var|let|const)\s+baseurl\s*=\s*"(https?://[^"]+)"', response.text)):
            secici = Selector(response.text)
            baslik = secici.xpath("//title/text()").get()
            if baslik == "404 Not Found":
                yeni_domain = eldeki_domain
                yayin_ara   = [None, eski_yayin_url]
            else:
                konsol.print(response.text)
                raise ValueError("Base URL bulunamadı!")
    
        yayin_url = yayin_ara[1]
        konsol.log(f"[green][+] Yeni Yayın URL : {yayin_url}")
    
        # Spor içeriğini güncelle
        yeni_spor_icerik = spor_icerik.replace(eski_yayin_url, yayin_url)
        yeni_spor_icerik = yeni_spor_icerik.replace(eldeki_domain, yeni_domain)
    
        # Yeni M3U içeriğini oluştur
        yeni_m3u_icerik = re.sub(
            desen,
            f"{spor_baslik}{yeni_spor_icerik}{sonraki_baslik}",
            m3u_icerik,
            flags=re.DOTALL
        )
    
        with open(self.m3u_dosyasi, "w") as dosya:
            dosya.write(yeni_m3u_icerik)

if __name__ == "__main__":
    guncelleyici = TRGoals ("cinos.m3u")
    guncelleyici.m3u_guncelle()
