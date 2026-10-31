# Birleştirilecek dosya adları
tvf = 'tvf.m3u'
selcukk = 'selcukk.m3u'
an = 'an.m3u8'
rnl = 'rnl.m3u'
liveeventsfilter = 'liveeventsfilter.m3u8'
madueke = 'madueke.m3u8'
cdnlivetv_channels = 'cdnlivetv_channels.m3u'
cikis_dosyasi = 'MAN NORMAL TV 2025.m3u'

# M3U / M3U8 dosyalarını oku
def oku_m3u(dosya_adi):
    try:
        with open(dosya_adi, 'r', encoding='utf-8') as f:
            # Satırları temizle, boş olanları ve en baştaki #EXTM3U etiketini filtrele
            return [satir.rstrip() for satir in f if satir.strip() and not satir.startswith("#EXTM3U")]
    except FileNotFoundError:
        print(f"⚠️ Dosya bulunamadı: {dosya_adi}")
        return []

# İçerikleri oku
tvf_icerik = oku_m3u(tvf)
selcukk_icerik = oku_m3u(selcukk)
an_icerik = oku_m3u(an)
rnl_icerik = oku_m3u(rnl)
madueke_icerik = oku_m3u(madueke)
liveeventsfilter_icerik = oku_m3u(liveeventsfilter)
cdnlivetv_channels_icerik = oku_m3u(cdnlivetv_channels) # Hata düzeltildi

# Birleştir 
birlesik_icerik = (
    tvf_icerik + 
    selcukk_icerik + 
    an_icerik + 
    rnl_icerik + 
    madueke_icerik + 
    cdnlivetv_channels_icerik + # _icerik takısı eklendi (Hata düzeltildi)
    liveeventsfilter_icerik
)

# Yeni dosyaya yaz
with open(cikis_dosyasi, 'w', encoding='utf-8') as f:
    f.write("#EXTM3U\n")
    for satir in birlesik_icerik:
        f.write(satir + '\n')

print(f"✅ {cikis_dosyasi} dosyası başarıyla oluşturuldu.")
