#!/usr/bin/env python3
import argparse
import base64
import json
import os
import re
import sys
import time
import unicodedata
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

API = "https://cdnlivetv.is"
PLAYER = "https://cdnlivetv.tv"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
REFERER = "https://cdnlivetv.is"

# Sadece Türkiye (tr) kanallarını hedefliyoruz
TURKISH_CODES = ("tr",)

LOGO_TREE_URL = "https://github.com"
LOGO_RAW = "https://githubusercontent.com"
LOGO_INDEX_FILE = "tv_logos_index.json"

# Türkiye için logo dizin eşlemeleri
CC_DIR = {"tr": "turkey"}
CC_SUF = {"tr": "tr"}
SKIP_DIRS = {"hd", "old", "screen-bug", "us-local", "utilities", "misc", "media", "vod"}

# Türkiye kanalları için gerekirse özel logo eşlemeleri ekleyebilirsiniz
OVERRIDES = {
    "TRT 1": "countries/turkey/trt-1-tr.png",
}

WIKI_COMMONS = {
    "TRT": "File:TRT_logo.svg",
}

WIKI_ENWIKI = {}


def http_get(url, referer=REFERER, tries=5):
    headers = {
        "User-Agent": UA,
        "Referer": referer,
        "Accept": "*/*",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if url.startswith("https://github.com") and token:
        headers["Authorization"] = f"token {token}"
    for attempt in range(tries):
        req = Request(url, headers=headers)
        try:
            with urlopen(req, timeout=45) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as e:
            code = getattr(e, "code", None)
            if code == 429:
                wait = min(60, (attempt + 1) * 5)
                print(f"  oran sınırlandı (rate limited), {wait}sn bekleniyor ...", file=sys.stderr)
                time.sleep(wait)
                continue
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Bağlantı hatası: {url}")


def b64dec(s):
    s = s + "=" * ((4 - len(s) % 4) % 4)
    return base64.b64decode(s).decode("utf-8", "replace")


def extract_stream_url(html):
    ch = re.search(r'var\s+_CH\s*=\s*"([0-9a-f]+)"', html)
    if not ch:
        return None
    chunks = re.findall(r"var\s+\w+\s*=\s*'([A-Za-z0-9+/=]+)'\s*;", html)
    full = "".join(b64dec(c) for c in chunks)
    m = re.search(
        r"https?://[^\"'`\s]+?/playlist\.m3u8\?token=[A-Za-z0-9+/=]+"
        r"|\?token=[A-Za-z0-9+/=]+",
        full,
    )
    if not m:
        return None
    url = m.group(0)
    if url.startswith("?"):
        url = f"https://cdnlivetv.tv{ch.group(1)}/playlist.m3u8" + url
    return url


def normalize(s):
    # Türkçe karakter desteği için genişletilmiş dönüşüm
    s = s.replace("ı", "i").replace("İ", "i").replace("ğ", "g").replace("Ğ", "g")
    s = s.replace("ü", "u").replace("Ü", "u").replace("ş", "s").replace("Ş", "s")
    s = s.replace("ö", "o").replace("Ö", "o").replace("ç", "c").replace("Ç", "c")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.replace("&", " and ").replace("+", " plus ")
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def load_logo_index():
    paths = []
    cached = None
    if os.path.exists(LOGO_INDEX_FILE):
        try:
            cached = json.load(open(LOGO_INDEX_FILE, encoding="utf-8"))
            paths = list(cached)
        except Exception:
            cached = None
    fresh = None
    try:
        data = json.loads(http_get(LOGO_TREE_URL))
        fresh = [t["path"] for t in data.get("tree", [])
                 if t.get("type") == "blob" and t["path"].endswith(".png")]
        if fresh:
            paths = fresh
            json.dump(paths, open(LOGO_INDEX_FILE, "w", encoding="utf-8"))
    except Exception as e:
        if not paths:
            raise SystemExit(f"Logo indeksi alınamadı: {e}")
        print(f"  Önbellekteki logolar kullanılıyor ({len(paths)} logo): {e}",
              file=sys.stderr)
    paths = [p for p in paths if p.startswith("countries/") and p.endswith(".png")]
    by_file = {}
    for p in paths:
        by_file.setdefault(p.rsplit("/", 1)[-1][:-4], []).append(p)
    return by_file, cached is not None and not fresh


def score(base_toks, name_toks):
    i = 0
    for t in name_toks:
        if i < len(base_toks) and base_toks[i] == t:
            i += 1
    if i == 0:
        return 0
    return i - max(0, len(name_toks) - len(base_toks)) * 0.15


def match_logo(name, code, by_file):
    base = normalize(name)
    cc = CC_SUF.get(code)
    dirc = CC_DIR.get(code)
    base_toks = base.split("-")

    for over in (name, base, base + "-" + cc):
        p = OVERRIDES.get(over)
        if p:
            fname = p.split("/")[-1][:-4]
            if fname in by_file and p in by_file[fname]:
                return p

    if cc:
        for cand in (base + "-" + cc, base):
            if cand in by_file:
                for p in by_file[cand]:
                    if p.split("/")[1] == dirc:
                        return p
        for cand in (base + "-" + cc, base):
            if cand in by_file:
                return by_file[cand][0]

    def best_in(include_subdirs, pfilter=None):
        best = (0, None)
        for fname, plist in by_file.items():
            for p in plist:
                if p.split("/")[1] != dirc:
                    continue
                depth = len(p.split("/"))
                if not include_subdirs and depth != 3:
                    continue
                if pfilter and not pfilter(p):
                    continue
                ft = fname.split("-")
                if cc and ft and ft[-1] == cc:
                    ft = ft[:-1]
                s = score(base_toks, ft)
                if s > best[0]:
                    best = (s, p)
        return best

    s, p = best_in(False)
    if s >= 2:
        return p

    best = (0, None)
    for fname, plist in by_file.items():
        for p in plist:
            parts = p.split("/")
            if len(parts) < 3:
                continue
            if parts[1] == dirc or any(seg in SKIP_DIRS for seg in parts[2:-1]):
                continue
            ft = fname.split("-")
            if cc and ft and ft[-1] == cc:
                ft = ft[:-1]
            sc = score(base_toks, ft)
            if sc > best[0]:
                best = (sc, p)
    if best[0] >= 2:
        return best[1]
    return None


def wiki_logo(name):
    if name in WIKI_COMMONS:
        f, host = WIKI_COMMONS[name], "https://wikimedia.org"
    elif name in WIKI_ENWIKI:
        f, host = WIKI_ENWIKI[name], "https://wikipedia.org"
    else:
        return None
    return f"{host}/wiki/Special:FilePath/{quote(f)}?width=512"


def build_playlist(limit=None, codes=TURKISH_CODES, delay=1.5):
    params = {"user": "cdnlivetv", "plan": "free"}
    url = API + "?" + urlencode(params)
    print("Kanal listesi çekiliyor ...", file=sys.stderr)
    data = json.loads(http_get(url))
    channels = [c for c in data.get("channels", []) if c.get("code") in codes]
    print(f"Toplam global kanal: {data.get('total_channels')}, Türkiye kanalları: {len(channels)}",
          file=sys.stderr)

    print("Tv-logos indeksi çekiliyor ...", file=sys.stderr)
    by_file, used_cache = load_logo_index()
    if used_cache:
        print("  (Önbelleğe alınmış logo indeksi kullanıldı)", file=sys.stderr)

    channels = channels if limit is None else channels[:limit]
    entries = []
    failed = 0
    matched = 0
    for i, ch in enumerate(channels, 1):
        name = ch["name"]
        q = urlencode({
            "name": name, "code": ch["code"],
            "user": "cdnlivetv", "plan": "free",
        })
        stream = None
        tries = 3
        while tries > 0:
            try:
                html = http_get(PLAYER + "?" + q)
                stream = extract_stream_url(html)
                break
            except Exception as e:
                tries -= 1
                print(f"  Hata {name}: {e}", file=sys.stderr)
                time.sleep(4)
        if stream:
            logo = match_logo(name, ch["code"], by_file)
            if not logo:
                logo = wiki_logo(name)
            ch = dict(ch)
            if logo:
                ch["image"] = (LOGO_RAW + logo) if logo.startswith("countries/") else logo
                matched += 1
            else:
                ch["image"] = ""
            entries.append((ch, stream))
        else:
            failed += 1
            print(f"  Atlandı: {name} (Yayın URL'i bulunamadı)", file=sys.stderr)
        print(f"  [{i}/{len(channels)}] {name}", file=sys.stderr)
        if delay:
            time.sleep(delay)

    print(f"Eşleşen Logolar: {matched}/{len(channels)}", file=sys.stderr)
    return entries, failed


def write_m3u(entries, out):
    with open(out, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ch, stream in entries:
            esc = lambda s: re.sub(r"[\s,]", "_", s)
            f.write(
                f'#EXTINF:-1 tvg-id="{esc(ch["name"])}" '
                f'tvg-logo="{ch.get("image", "")}" '
                f'group-title="{esc(ch["code"].upper())} TV",{ch["name"]}\n'
            )
            f.write(stream + "\n")


def main():
    ap = argparse.ArgumentParser(
        description="CDN Live TV üzerinden Türkiye kanalları için m3u listesi oluşturur.")
    ap.add_argument("-o", "--output", default="madueke.m3u8",
                    help="Çıktı m3u8 playlist dosyası")
    ap.add_argument("--codes", default=",".join(TURKISH_CODES),
                    help="Dahil edilecek ülke kodları (virgülle ayrılmış)")
    ap.add_argument("--limit", type=int, default=None,
                    help="Sadece ilk N kanalı işle (test etmek için)")
    ap.add_argument("--delay", type=float, default=1.5,
