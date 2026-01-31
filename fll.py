# Birleştirilecek dosya adları
kbl = 'kbl.m3u'
tvf = 'tvf.m3u'
r = 'r.m3u'
r2 = 'r2.m3u'
selcuk = 'selcuk.m3u'
an = 'an.m3u'
ne = 'ne.m3u'
rnl = 'rnl.m3u'
int = 'int.m3u'
liveeventsfilter = 'liveeventsfilter.m3u8'
cafe = 'cafe.m3u'
cikis_dosyasi = 'MAN NORMAL TV 2025.m3u'

# M3U / M3U8 dosyalarını oku (TEK FONKSİYON)
def oku_m3u(dosya_adi):
    try:
        with open(dosya_adi, 'r', encoding='utf-8') as f:
            return [satir.rstrip() for satir in f if satir.strip()]
    except FileNotFoundError:
        print(f"⚠️ Dosya bulunamadı: {dosya_adi}")
        return []

# İçerikleri oku
kbl_icerik = oku_m3u(kbl)
tvf_icerik = oku_m3u(tvf)
r_icerik = oku_m3u(r)
r2_icerik = oku_m3u(r2)
selcuk_icerik = oku_m3u(selcuk)
an_icerik = oku_m3u(an)
ne_icerik = oku_m3u(ne)
rnl_icerik = oku_m3u(rnl)
neon_icerik = oku_m3u(neon)
cafe_icerik = oku_m3u(cafe)
int_icerik = oku_m3u(int)
liveeventsfilter_icerik = oku_m3u(liveeventsfilter)  

# Birleştir
birlesik_icerik = (
    kbl_icerik +
    tvf_icerik +
    r_icerik +
    r2_icerik +
    selcuk_icerik +
    an_icerik +
    ne_icerik +
    rnl_icerik +
    cafe_icerik +
    int_icerik +
    liveeventsfilter_icerik
)

# Yeni dosyaya yaz
with open(cikis_dosyasi, 'w', encoding='utf-8') as f:
    f.write("#EXTM3U\n")
    for satir in birlesik_icerik:
        f.write(satir + '\n')

print(f"✅ {cikis_dosyasi} dosyası başarıyla oluşturuldu.")
