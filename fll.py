# Birleştirilecek dosya adları
tvf = 'tvf.m3u'
ftb = 'ftb.m3u'
r = 'r.m3u'
r2 = 'r2.m3u'
inn = 'inn.m3u'
selcuk = 'selcuk.m3u'
an = 'an.m3u'
kbl = 'kbl.m3u'
ne = 'ne.m3u'
rnl = 'rnl.m3u'
liveeventsfilter = 'liveeventsfilter.m3u8'
cikis_dosyasi = 'man26.m3u'

# M3U / M3U8 dosyalarını oku (TEK FONKSİYON)
def oku_m3u(dosya_adi):
    try:
        with open(dosya_adi, 'r', encoding='utf-8') as f:
            return [satir.rstrip() for satir in f if satir.strip()]
    except FileNotFoundError:
        print(f"⚠️ Dosya bulunamadı: {dosya_adi}")
        return []

# İçerikleri oku
tvf_icerik = oku_m3u(tvf)
ftb_icerik = oku_m3u(ftb)
r_icerik = oku_m3u(r)
r2_icerik = oku_m3u(r2)
inn_icerik = oku_m3u(inn)
selcuk_icerik = oku_m3u(selcuk)
an_icerik = oku_m3u(an)
kbl_icerik = oku_m3u(kbl)
ne_icerik = oku_m3u(ne)
rnl_icerik = oku_m3u(rnl)
liveeventsfilter_icerik = oku_m3u(liveeventsfilter)  

# Birleştir
birlesik_icerik = (
    tvf_icerik +
    kbl_icerik +
    ftb_icerik +
    r_icerik +
    r2_icerik +
    inn_icerik +
    selcuk_icerik +
    an_icerik +
    ne_icerik +
    rnl_icerik +
    liveeventsfilter_icerik
)

# Yeni dosyaya yaz
with open(cikis_dosyasi, 'w', encoding='utf-8') as f:
    f.write("#EXTM3U\n")
    for satir in birlesik_icerik:
        f.write(satir + '\n')

print(f"✅ {cikis_dosyasi} dosyası başarıyla oluşturuldu.")
