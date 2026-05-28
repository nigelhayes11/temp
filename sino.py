#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Gereksinim: pip install requests
# Calistir:   python sinewix_gui.py

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading, requests, time, os

# ─── API ──────────────────────────────────────────────────────────────────────
API_BASE  = "https://ydfvfdizipanel.ru/public/api"
API_KEY   = "9iQNC5HQwPlaFuJDkhncJ5XTJ8feGXOJatAA"
SIGNATURE = "3082058830820370a00302010202145bbfbba9791db758ad12295636e094ab4b07dc24300d06092a864886f70d01010b05003074310b3009060355040613025553311330110603550408130a43616c69666f726e6961311630140603550407130d4d6f756e7461696e205669657731143012060355040a130b476f6f676c6520496e632e3110300e060355040b1307416e64726f69643110300e06035504031307416e64726f69643020170d3231313231353232303433335a180f32303531313231353232303433335a3074310b3009060355040613025553311330110603550408130a43616c69666f726e6961311630140603550407130d4d6f756e7461696e205669657731143012060355040a130b476f6f676c6520496e632e3110300e060355040b1307416e64726f69643110300e06035504031307416e64726f696430820222300d06092a864886f70d01010105000382020f003082020a0282020100a5106a24bb3f9c0aaf3a2b228f794b5eaf1757ba758b19736a39d1bdc73fc983a7237b8d5ca5156cfa999c1dab3418bbc2be0920e0ee001c8aa4812d1dae75d080f09e91e0abda83ff9a76e8384a4429f4849248069a59505b12ac2c14ba2e4d1a13afcdaf54e508697ff928a9f738e6f4a6fc27409c55329eb149b5ff89c5a2d7c06bf9e62086f955cad17d7be2623ee9d5ec56068eadc23cb0965a13ff97d49fe10ef41afc6eeca36b4ace9582097faff89f590bc831cdb3a69eec5d15b67c3f2cad49e37ed053733e3d2d400c47755b932bdbe15d749fd6ad1dce30ba5e66094dfb6ee6f64cafb807e11b19a990c5d078c6d6701cda0bdeb21e99404ff166074f4c89b04c418f4e7940db5c78647c475bcfb85d4c4e836ee7d7c1d53e9e736b5d96d4b4d8b98209064b729ac6a682d55a6a930e518d849898bb28329ca0aaa133b5e5270a9d5940cac6af4802a57fd971efda91abb602882dd6aa6ce2b236b57b52ee2481498f0cacbcc2c36c238bc84becad7eaaf1125b9a1ca9ded6c79f3f283a52050377809b2a9995d66e1636b0ed426fdd8685c47cb18e82077f4aefcc07887e1dc58b4d64be1632f0e7b4625da6f40c65a8512a6454a4b96963e7f876136e6c0069a519a79ad632078ed965aa12482458060c030ed50db706d854f88cb004630b49285d8af8b471ff8f6070687826412287b50049bcb7d1b6b62ef90203010001a310300e300c0603551d13040530030101ff300d06092a864886f70d01010b0500038202010051c0b7bd793181dc29ca777d3773f928a366c8469ecf2fa3cfb076e8831970d19bb2b96e44e8ccc647cf0696bb824ac61c23d958525d283cab26037b04d58aa79bf92192db843adf5c26a980f081d2f0e14f759fc5ff4c5bb3dce0860299bfe7b349a8155a2efaf731ba25ce796a80c1442c7bf80f8c1a7912ff0b6f6592264315337251a846460194fa594f81f38f9e5233a63201e931ad9cab5bf119f24025613f307194eaa6eb39a83f3c05a49ba34455b1aff7c6839bbb657d9392ffdf397432af6e56ba9534a8b07d7060fe09691c6cf07cb5324f67b3cc0871a8c621d81fe71d71085c55206a4f57e25f774fd4b979b299e8bb076b50fca42fa57da2d519fd35a4a7c0137babaed4345f8031b63b6a71f5e8268f709d658ccd7c2a58849379d25bfa598c3f4a2c3d9b7d89285fefeb7f0ec65137d38b08ce432a15688b624a179e6a4a505ebc3bcdfbc4d4330508ee2d8d0f016924dcec21a6838ef7d834c6f43bde4a5201ed0b3bb4e9bd377b470e36bcf5bc3d56169dbd8e39567aa7dce4d1a8a8a54a5e1aa6fb1a8aab0062669a966f96e15ccce6fe12ea5e6a8b8c8823bdc94988ca39759fd1cc8fd8ae5c3d74db50b174cf7d77655016c075c91d439ed01cc0a9f695c99fad3b5495fb6cb1e01a5fa020cc6022a85c07ec55f9eba89719f86e49d34ab5bd208c5f70cced2b7b7963c014f8404432979b506de29e"

HEADERS = {
    "Accept":           "application/json",
    "Accept-Encoding":  "identity",
    "Cache-Control":    "max-age=0",
    "Connection":       "Keep-Alive",
    "hash256":          "711bff4afeb47f07ab08a0b07e85d3835e739295e8a6361db77eebd93d96306b",
    "signature":        SIGNATURE,
    "User-Agent":       "EasyPlex (Android 14; SM-A546B; Samsung Galaxy A54 5G; tr)",
}

# ─── Renkler ──────────────────────────────────────────────────────────────────
BG      = "#0f1117"
BG2     = "#1a1d27"
BG3     = "#22263a"
ACCENT  = "#e50914"
TEXT    = "#e8eaf0"
TEXT2   = "#8b8fa8"
SUCCESS = "#22c55e"
WARNING = "#f59e0b"
BORDER  = "#2e3248"

PAGE_OPTIONS = ["5", "10", "20", "50", "100", "Hepsi"]

# ─── API Yardimcilari ─────────────────────────────────────────────────────────

def api_get(path, retries=3):
    url = API_BASE + path
    for _ in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.json()
        except Exception:
            time.sleep(1)
    return None

def safe_url(url):
    return url.replace("http://", "https://") if url else None

def extract_items(data):
    if not data:
        return [], False
    if isinstance(data, list):
        return data, len(data) >= 10
    for key in ("data", "results", "items", "movies", "media", "series"):
        if key in data and isinstance(data[key], list):
            items = data[key]
            has_next = bool(
                data.get("next_page_url") or
                (data.get("current_page") and data.get("last_page") and
                 int(data.get("current_page", 0)) < int(data.get("last_page", 0)))
            ) or len(items) >= 10
            return items, has_next
    return [], False

def get_pages(path, max_pages, log_fn, stop_ev):
    all_items, page = [], 1
    while True:
        if stop_ev.is_set():
            break
        if max_pages and page > max_pages:
            break
        log_fn(f"  -> Sayfa {page} cekiliyor...\n", "dim")
        items, has_next = extract_items(api_get(f"{path}?page={page}"))
        if not items:
            break
        all_items.extend(items)
        log_fn(f"  + {len(items)} oge (toplam {len(all_items)})\n")
        if not has_next:
            break
        page += 1
        time.sleep(0.1)
    return all_items

def m3u_entry(name, group, logo, url):
    logo_attr = f' tvg-logo="{logo}"' if logo else ""
    return f'#EXTINF:-1 group-title="{group}"{logo_attr},{name}\n{url}\n'

# ─── Uygulama ─────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SineWix  M3U  Olusturucu")
        self.geometry("820x700")
        self.minsize(700, 580)
        self.configure(bg=BG)
        self._stop = threading.Event()
        self._build()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build(self):
        # Üst şerit
        tk.Frame(self, bg=ACCENT, height=4).pack(fill="x")
        hf = tk.Frame(self, bg=BG, padx=26, pady=16)
        hf.pack(fill="x")
        tk.Label(hf, text="SINEWIX", font=("Courier New", 21, "bold"),
                 fg=ACCENT, bg=BG).pack(side="left")
        tk.Label(hf, text="  M3U Olusturucu", font=("Courier New", 21, "bold"),
                 fg=TEXT, bg=BG).pack(side="left")

        body = tk.Frame(self, bg=BG, padx=26)
        body.pack(fill="both", expand=True)

        # İçerik türü
        self._slabel(body, "1 — ICERIK TURU")
        cf = self._card(body)
        self.v_film  = tk.BooleanVar(value=True)
        self.v_dizi  = tk.BooleanVar(value=True)
        self.v_anime = tk.BooleanVar(value=False)
        for col, (lbl, icon, var) in enumerate([
            ("Filmler",  "🎬", self.v_film),
            ("Diziler",  "📺", self.v_dizi),
            ("Animeler", "⛩", self.v_anime),
        ]):
            tk.Checkbutton(cf, text=f" {icon}  {lbl}", variable=var,
                           font=("Courier New", 12), fg=TEXT, bg=BG2,
                           selectcolor=BG3, activebackground=BG2,
                           activeforeground=TEXT, highlightthickness=0,
                           cursor="hand2").grid(row=0, column=col, padx=(0,32), sticky="w")

        # Sayfa sayısı
        self._slabel(body, "2 — SAYFA SAYISI  (her sayfa ~12 oge  |  'Hepsi' = tumu)")
        pf = self._card(body)
        self.page_var = tk.StringVar(value="10")
        for col, val in enumerate(PAGE_OPTIONS):
            tk.Radiobutton(pf, text=f"  {val}  ", variable=self.page_var, value=val,
                           font=("Courier New", 11), fg=TEXT, bg=BG2,
                           selectcolor=ACCENT, activebackground=BG2,
                           activeforeground=TEXT, highlightthickness=0,
                           cursor="hand2", indicatoron=False,
                           relief="flat", bd=0,
                           selectimage="", pady=6, padx=6
                           ).grid(row=0, column=col, padx=(0,6), sticky="w")

        # Seçenekler
        self._slabel(body, "3 — SECENEKLER")
        of = self._card(body)
        of.columnconfigure(1, weight=1)

        tk.Label(of, text="Istek araligi (sn):", font=("Courier New", 11),
                 fg=TEXT2, bg=BG2).grid(row=0, column=0, sticky="w")
        self.delay_var = tk.DoubleVar(value=0.2)
        tk.Spinbox(of, textvariable=self.delay_var, from_=0.0, to=3.0,
                   increment=0.1, width=5, font=("Courier New", 11),
                   bg=BG3, fg=TEXT, relief="flat",
                   highlightbackground=BORDER, highlightthickness=1
                   ).grid(row=0, column=1, sticky="w", padx=(14,0))

        tk.Label(of, text="Kayit yeri:", font=("Courier New", 11),
                 fg=TEXT2, bg=BG2).grid(row=1, column=0, sticky="w", pady=(10,0))
        row_f = tk.Frame(of, bg=BG2)
        row_f.grid(row=1, column=1, sticky="ew", padx=(14,0), pady=(10,0))
        row_f.columnconfigure(0, weight=1)
        self.out_var = tk.StringVar(
            value=os.path.join(os.path.expanduser("~"), "sinewix.m3u"))
        tk.Entry(row_f, textvariable=self.out_var, font=("Courier New", 10),
                 bg=BG3, fg=TEXT, insertbackground=TEXT, relief="flat",
                 highlightbackground=BORDER, highlightthickness=1
                 ).grid(row=0, column=0, sticky="ew", ipady=5)
        tk.Button(row_f, text=" ... ", font=("Courier New", 10, "bold"),
                  bg=BG3, fg=TEXT, relief="flat", cursor="hand2",
                  command=self._browse).grid(row=0, column=1, padx=(6,0))

        # Log
        self._slabel(body, "4 — LOG")
        lf = tk.Frame(body, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        lf.pack(fill="both", expand=True, pady=(4,0))
        self.log_box = tk.Text(lf, font=("Courier New", 10), bg=BG2, fg=TEXT2,
                               relief="flat", state="disabled", wrap="word",
                               padx=10, pady=8, cursor="arrow")
        sb = tk.Scrollbar(lf, command=self.log_box.yview, bg=BG3,
                          troughcolor=BG2, relief="flat")
        self.log_box.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log_box.pack(fill="both", expand=True)
        for tag, fg, bold in [
            ("acc", ACCENT, False), ("ok", SUCCESS, False),
            ("wrn", WARNING, False), ("dim", TEXT2,  False),
            ("bld", TEXT,    True),
        ]:
            font = ("Courier New", 10, "bold") if bold else ("Courier New", 10)
            self.log_box.tag_config(tag, foreground=fg, font=font)

        # Alt bar
        bf = tk.Frame(self, bg=BG, padx=26, pady=12)
        bf.pack(fill="x")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("R.Horizontal.TProgressbar",
                        troughcolor=BG3, background=ACCENT,
                        lightcolor=ACCENT, darkcolor=ACCENT,
                        bordercolor=BG3, thickness=5)
        self.prog = ttk.Progressbar(bf, mode="indeterminate", length=160,
                                    style="R.Horizontal.TProgressbar")
        self.prog.pack(side="left", padx=(0,12))
        self.stat = tk.Label(bf, text="Hazir.", font=("Courier New", 10),
                             fg=TEXT2, bg=BG)
        self.stat.pack(side="left")
        self.btn_stop = tk.Button(bf, text="  DURDUR  ",
                                  font=("Courier New", 11, "bold"),
                                  bg=BG3, fg=TEXT2, relief="flat",
                                  cursor="hand2", padx=14, pady=7,
                                  state="disabled", command=self._do_stop)
        self.btn_stop.pack(side="right", padx=(8,0))
        self.btn_start = tk.Button(bf, text="  BASLA  ",
                                   font=("Courier New", 11, "bold"),
                                   bg=ACCENT, fg="white",
                                   activebackground="#b0060d",
                                   activeforeground="white",
                                   relief="flat", cursor="hand2",
                                   padx=18, pady=7, command=self._do_start)
        self.btn_start.pack(side="right")

        self._log("Hazir. Secimlerini yap ve BASLA'ya bas.\n", "bld")

    # ── Yardimcilar ───────────────────────────────────────────────────────────
    def _slabel(self, p, t):
        tk.Label(p, text=t, font=("Courier New", 9, "bold"),
                 fg=TEXT2, bg=BG).pack(anchor="w", pady=(10,2))

    def _card(self, p):
        o = tk.Frame(p, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        o.pack(fill="x", pady=(0,2))
        i = tk.Frame(o, bg=BG2, padx=16, pady=12)
        i.pack(fill="x")
        return i

    def _browse(self):
        p = filedialog.asksaveasfilename(
            defaultextension=".m3u",
            filetypes=[("M3U Oynatma Listesi", "*.m3u"), ("Tum dosyalar", "*.*")],
            initialfile="sinewix.m3u")
        if p:
            self.out_var.set(p)

    def _log(self, msg, tag="dim"):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg, tag)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        self.update_idletasks()

    def _set_stat(self, msg, color=TEXT2):
        self.stat.configure(text=msg, fg=color)
        self.update_idletasks()

    # ── Butonlar ──────────────────────────────────────────────────────────────
    def _do_start(self):
        if not any([self.v_film.get(), self.v_dizi.get(), self.v_anime.get()]):
            messagebox.showwarning("Secim Yok", "En az bir tur secmelisin.")
            return
        self._stop.clear()
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.prog.start(12)
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        threading.Thread(target=self._run, daemon=True).start()

    def _do_stop(self):
        self._stop.set()
        self.after(0, self._log, "\nDurdurma istegi gonderildi...\n", "wrn")
        self.after(0, self._set_stat, "Durduruluyor...", WARNING)

    def _finish(self, total, path):
        self.prog.stop()
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        if total:
            self._set_stat(f"Tamamlandi — {total} stream", SUCCESS)
            self._log(f"\nTAMAMLANDI!  {total} stream  ->  {path}\n", "ok")
        else:
            self._set_stat("Stream bulunamadi", WARNING)

    # ── Is mantigi ────────────────────────────────────────────────────────────
    def _run(self):
        pval      = self.page_var.get()
        max_pages = 0 if pval == "Hepsi" else int(pval)
        delay     = self.delay_var.get()
        outfile   = self.out_var.get()
        entries   = []
        total     = 0

        def log(msg, tag="dim"):
            self.after(0, self._log, msg, tag)

        def stat(msg):
            self.after(0, self._set_stat, msg)

        # ── FILMLER ──────────────────────────────────────────────────────────
        if self.v_film.get() and not self._stop.is_set():
            log("\nFILMLER\n", "acc")
            items = get_pages(
                f"/genres/latestmovies/all/{API_KEY}",
                max_pages, log, self._stop)
            log(f"  Toplam {len(items)} film — stream URL'leri aliniyor...\n")
            for i, item in enumerate(items, 1):
                if self._stop.is_set():
                    break
                mid    = item.get("id") or item.get("media_id")
                title  = (item.get("title") or item.get("name") or
                          item.get("original_name") or f"Film-{mid}")
                poster = safe_url(item.get("poster_path") or item.get("poster"))
                if not mid:
                    continue
                stat(f"Film {i}/{len(items)}: {title[:38]}...")
                data = api_get(f"/media/detail/{mid}/{API_KEY}")
                cnt  = 0
                if data:
                    for v in (data.get("videos") or []):
                        link = safe_url(v.get("link"))
                        if link:
                            lang = v.get("lang") or v.get("name") or "TR"
                            entries.append(
                                m3u_entry(f"{title} [{lang}]",
                                          "SineWix - Filmler", poster, link))
                            total += 1
                            cnt   += 1
                if cnt:
                    log(f"  [{i}/{len(items)}] {title}  ({cnt} stream)\n")
                else:
                    log(f"  [{i}/{len(items)}] {title}  —  stream yok\n", "dim")
                time.sleep(delay)

        # ── DIZILER ──────────────────────────────────────────────────────────
        if self.v_dizi.get() and not self._stop.is_set():
            log("\nDIZILER\n", "acc")
            items = get_pages(
                f"/genres/latestseries/all/{API_KEY}",
                max_pages, log, self._stop)
            log(f"  Toplam {len(items)} dizi — bolumler aliniyor...\n")
            for i, item in enumerate(items, 1):
                if self._stop.is_set():
                    break
                sid   = item.get("id") or item.get("serie_id")
                sname = (item.get("name") or item.get("title") or
                         item.get("original_name") or f"Dizi-{sid}")
                poster = safe_url(item.get("poster_path") or item.get("poster"))
                if not sid:
                    continue
                stat(f"Dizi {i}/{len(items)}: {sname[:38]}...")
                data  = api_get(f"/series/show/{sid}/{API_KEY}")
                cnt   = 0
                if data:
                    for season in (data.get("seasons") or []):
                        snum = int(season.get("season_number", 1))
                        for ep in (season.get("episodes") or []):
                            if self._stop.is_set():
                                break
                            enum   = int(ep.get("episode_number", 1))
                            epname = ep.get("name") or f"{enum}. Bolum"
                            for v in (ep.get("videos") or []):
                                link = safe_url(v.get("link"))
                                if link:
                                    lang  = v.get("lang") or v.get("name") or "TR"
                                    label = (f"{sname} "
                                             f"S{snum:02d}E{enum:02d} "
                                             f"- {epname} [{lang}]")
                                    entries.append(
                                        m3u_entry(label, "SineWix - Diziler",
                                                  poster, link))
                                    total += 1
                                    cnt   += 1
                if cnt:
                    log(f"  [{i}/{len(items)}] {sname}  ({cnt} stream)\n")
                else:
                    log(f"  [{i}/{len(items)}] {sname}  —  stream yok\n", "dim")
                time.sleep(delay)

        # ── ANIMELER ─────────────────────────────────────────────────────────
        if self.v_anime.get() and not self._stop.is_set():
            log("\nANIMELER\n", "acc")
            items = get_pages(
                f"/genres/latestanimes/all/{API_KEY}",
                max_pages, log, self._stop)
            log(f"  Toplam {len(items)} anime — bolumler aliniyor...\n")
            for i, item in enumerate(items, 1):
                if self._stop.is_set():
                    break
                sid   = item.get("id") or item.get("serie_id")
                sname = (item.get("name") or item.get("title") or
                         item.get("original_name") or f"Anime-{sid}")
                poster = safe_url(item.get("poster_path") or item.get("poster"))
                if not sid:
                    continue
                stat(f"Anime {i}/{len(items)}: {sname[:38]}...")
                data  = api_get(f"/series/show/{sid}/{API_KEY}")
                cnt   = 0
                if data:
                    for season in (data.get("seasons") or []):
                        snum = int(season.get("season_number", 1))
                        for ep in (season.get("episodes") or []):
                            if self._stop.is_set():
                                break
                            enum   = int(ep.get("episode_number", 1))
                            epname = ep.get("name") or f"{enum}. Bolum"
                            for v in (ep.get("videos") or []):
                                link = safe_url(v.get("link"))
                                if link:
                                    lang  = v.get("lang") or v.get("name") or "TR"
                                    label = (f"{sname} "
                                             f"S{snum:02d}E{enum:02d} "
                                             f"- {epname} [{lang}]")
                                    entries.append(
                                        m3u_entry(label, "SineWix - Animeler",
                                                  poster, link))
                                    total += 1
                                    cnt   += 1
                if cnt:
                    log(f"  [{i}/{len(items)}] {sname}  ({cnt} stream)\n")
                else:
                    log(f"  [{i}/{len(items)}] {sname}  —  stream yok\n", "dim")
                time.sleep(delay)

        # ── KAYDET ───────────────────────────────────────────────────────────
        if entries:
            try:
                with open(outfile, "w", encoding="utf-8") as f:
                    f.write("#EXTM3U\n")
                    for e in entries:
                        f.write(e)
                self.after(0, self._finish, total, outfile)
            except Exception as ex:
                log(f"\nDosya hatasi: {ex}\n", "acc")
                self.after(0, self._finish, 0, "")
        else:
            log("\nHic stream bulunamadi.\n", "wrn")
            self.after(0, self._finish, 0, "")


if __name__ == "__main__":
    App().mainloop()
