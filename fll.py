# Birleştirilecek dosya adları (Deponuzdaki güncel liste)
dosyalar = [
    'liveeventsfilter.m3u8',
   
 
]

cikis_dosyasi = 'MAN NORMAL TV 2025.m3u'


def oku_m3u(dosya_adi):
    try:
        with open(dosya_adi, 'r', encoding='utf-8') as f:
            return [satir.rstrip() for satir in f if satir.strip() and not satir.startswith("#EXTM3U")]
    except FileNotFoundError:
        print(f"⚠️ Dosya bulunamadı: {dosya_adi}")
        return []


birlesik_icerik = []
for dosya in dosyalar:
    icerik = oku_m3u(dosya)
    if icerik:
        print(f"➕ Eklendi: {dosya} ({len(icerik)} satır)")
        birlesik_icerik.extend(icerik)

with open(cikis_dosyasi, 'w', encoding='utf-8') as f:
    f.write("#EXTM3U\n")
    for satir in birlesik_icerik:
        f.write(satir + '\n')

print(f"\n✅ {cikis_dosyasi} dosyası toplam {len(birlesik_icerik)} satır ile başarıyla oluşturuldu.")
