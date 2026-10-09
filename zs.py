import os
import re

# ============================================================
# AYARLAR
# ============================================================
# Scriptin çalıştığı klasörü (ana dizini) otomatik algılar
ANA_DIZIN = os.path.dirname(os.path.abspath(__file__)) if __file__ else os.getcwd()
CIKIS_DOSYASI = "zs.m3u8"

# ============================================================
# M3U8 GÜNCELLEME VE ÇIKARMA İŞLEMİ
# ============================================================

def m3u8_donustur():
    print(f"🔍 Ana dizindeki .m3u8 dosyaları taranıyor...\n")

    toplam_taranan = 0
    olusturuldu_mu = False

    # Doğrudan ana dizindeki dosyaları listele
    for dosya_adi in os.listdir(ANA_DIZIN):
        
        # Sadece .m3u8 uzantılı dosyaları al ve zs.m3u8'in kendisini atla
        if not dosya_adi.lower().endswith(".m3u8") or dosya_adi.lower() == CIKIS_DOSYASI.lower():
            continue

        dosya_yolu = os.path.join(ANA_DIZIN, dosya_adi)
        toplam_taranan += 1

        try:
            with open(dosya_yolu, "r", encoding="utf-8") as f:
                icerik = f.read()

            # URL sonundaki /index.m3u8 kısmını /index.txt yap
            yeni_icerik = re.sub(
                r'/index\.m3u8(?=\s*$)',
                '/index.txt',
                icerik,
                flags=re.MULTILINE
            )

            # Doğrudan ana dizine zs.m3u8 olarak kaydet
            cikis_yolu = os.path.join(ANA_DIZIN, CIKIS_DOSYASI)
            with open(cikis_yolu, "w", encoding="utf-8") as f:
                f.write(yeni_icerik)

            olusturuldu_mu = True
            print(f"✅ {dosya_adi} dosyası işlendi -> {CIKIS_DOSYASI} olarak ana dizine çıkarıldı.")

        except Exception as e:
            print(f"❌ Hata ({dosya_adi}): {e}")

    print("\n" + "=" * 50)
    print(f"📊 Toplam taranan kaynak dosya: {toplam_taranan}")
    print(f"✏️ {CIKIS_DOSYASI} Oluşturulma Durumu: {'BAŞARILI' if olusturuldu_mu else 'KAYNAK DOSYA BULUNAMADI'}")
    print("=" * 50)
    print("\n🎉 İşlem tamamlandı!")

# ============================================================
# BAŞLAT
# ============================================================

if __name__ == "__main__":
    m3u8_donustur()
