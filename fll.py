dosyalar = [
    'kbl.m3u',
    'tvf.m3u',
    'r2.m3u',
    'selcukk.m3u',
    'an.m3u',
    'ne.m3u',
    'rnl.m3u',
    'cafe.m3u',
    'liveeventsfilter.m3u8'
]

cikis_dosyasi = 'MAN NORMAL TV 2025.m3u'

def oku_m3u(dosya_adi):
    try:
        with open(dosya_adi, 'r', encoding='utf-8') as f:
            return [satir.rstrip() for satir in f if satir.strip() and satir.strip() != "#EXTM3U"]
    except FileNotFoundError:
        print(f"⚠️ Dosya bulunamadı: {dosya_adi}")
        return []

birlesik_icerik = []
for d in dosyalar:
    birlesik_icerik += oku_m3u(d)

with open(cikis_dosyasi, 'w', encoding='utf-8') as f:
    f.write("#EXTM3U\n")
    for satir in birlesik_icerik:
        f.write(satir + "\n")

print(f"✅ {cikis_dosyasi} dosyası başarıyla oluşturuldu.")
