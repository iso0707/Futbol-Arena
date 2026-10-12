# -*- coding: utf-8 -*-
"""Kulüp logolarını Wikipedia'dan indirir. Bir kere çalıştır, logolar assets/clubs/ içine iner.

Kullanım:
    python club_logos.py

İnenler: assets/clubs/<slug>.png
İnmeyenler: inmezse elle koyabilirsin (aynı isimle).
"""
import os
import re
import ssl
import json
import time
import urllib.parse
import urllib.request

# quiz_data'dan kulüp listesini al
try:
    from quiz_data import EASY_CLUBS_150, HARD_CLUBS_100
except Exception as e:
    print("HATA: quiz_data.py bulunamadı:", e)
    EASY_CLUBS_150 = []
    HARD_CLUBS_100 = []


# ---------------------------------------------------------------------------
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(_BASE_DIR, "assets", "clubs")
os.makedirs(OUT_DIR, exist_ok=True)

UA = "FutbolArenaBot/1.0 (quiz game; educational)"


def _ssl_ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _slug(text):
    text = text.replace("ı", "i").replace("İ", "I")
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "club"


def _get(url, timeout=10):
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout,
                                context=_ssl_ctx()) as r:
        return r.read()


def _summary_thumb(title):
    """Wikipedia başlığından özet + thumbnail URL'sini al."""
    url = ("https://en.wikipedia.org/api/rest_v1/page/summary/" +
           urllib.parse.quote(title.replace(" ", "_"), safe=""))
    j = json.loads(_get(url).decode("utf-8"))
    if j.get("type") == "disambiguation":
        return None
    # Logo ya da amblem içeren thumbnail
    thumb = (j.get("thumbnail") or {}).get("source")
    if thumb:
        # 400px versiyonunu al
        thumb = re.sub(r"/(\d+)px-", "/400px-", thumb, count=1)
    return thumb


def _pageimages(title):
    """MediaWiki API ile sayfanın ana görselini (pageimage) al."""
    url = ("https://en.wikipedia.org/w/api.php?action=query&format=json"
           "&prop=pageimages&piprop=original|thumbnail&pithumbsize=400"
           "&titles=" + urllib.parse.quote(title))
    j = json.loads(_get(url).decode("utf-8"))
    pages = (j.get("query") or {}).get("pages") or {}
    for pid, page in pages.items():
        thumb = (page.get("thumbnail") or {}).get("source")
        orig = (page.get("original") or {}).get("source")
        return thumb or orig
    return None


def _search_club(name):
    """İsimle Wikipedia'da ara, ilk uygun kulüp sayfasını bul."""
    url = ("https://en.wikipedia.org/w/rest.php/v1/search/page?q=" +
           urllib.parse.quote(name + " football club") + "&limit=5")
    j = json.loads(_get(url).decode("utf-8"))
    for p in j.get("pages", []):
        key = p.get("key")
        desc = (p.get("description") or "").lower()
        if not key:
            continue
        if any(k in desc for k in ("football", "soccer", "club", "sports")):
            return key
    # bulamazsa ilk sonucu dene
    pages = j.get("pages", [])
    return pages[0]["key"] if pages else None


def download_logo(name, wiki_title):
    """Önce wiki_title, sonra arama. İlk bulduğu thumbnail'ı indir."""
    slug = _slug(name)
    out_path = None
    for ext in ("png", "jpg", "jpeg", "webp"):
        p = os.path.join(OUT_DIR, "%s.%s" % (slug, ext))
        if os.path.isfile(p) and os.path.getsize(p) > 500:
            print("  [atla] zaten var: %s" % os.path.basename(p))
            return p
    thumb = None
    # 1) doğrudan wiki başlığı
    try:
        thumb = _summary_thumb(wiki_title)
    except Exception:
        thumb = None
    # 2) pageimages
    if not thumb:
        try:
            thumb = _pageimages(wiki_title)
        except Exception:
            thumb = None
    # 3) arama
    if not thumb:
        try:
            found = _search_club(name)
            if found:
                thumb = _summary_thumb(found) or _pageimages(found)
        except Exception:
            thumb = None
    if not thumb:
        print("  [YOK] %s" % name)
        return None
    # indir
    try:
        data = _get(thumb, timeout=15)
        if len(data) < 800:
            print("  [KÜÇÜK] %s" % name)
            return None
        ext = "png"
        low = thumb.lower().split("?")[0]
        for cand in ("png", "jpg", "jpeg", "webp", "svg"):
            if low.endswith("." + cand):
                ext = "png" if cand == "svg" else cand
                break
        out_path = os.path.join(OUT_DIR, "%s.%s" % (slug, ext))
        tmp = out_path + ".part"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, out_path)
        print("  [OK] %s -> %s" % (name, os.path.basename(out_path)))
        return out_path
    except Exception as e:
        print("  [HATA] %s -> %s" % (name, str(e)[:80]))
        return None


def main():
    # Tüm kulüpleri birleştir, tekrarları çıkar
    all_clubs = []
    seen = set()
    for name, wiki in list(EASY_CLUBS_150) + list(HARD_CLUBS_100):
        slug = _slug(name)
        if slug in seen:
            continue
        seen.add(slug)
        all_clubs.append((name, wiki or name))
    print("Toplam kulüp: %d" % len(all_clubs))
    print("Kayıt yeri: %s" % OUT_DIR)
    print("-" * 60)
    ok = 0
    fail = 0
    for i, (name, wiki) in enumerate(all_clubs, 1):
        print("[%d/%d] %s" % (i, len(all_clubs), name))
        p = download_logo(name, wiki)
        if p:
            ok += 1
        else:
            fail += 1
        time.sleep(0.4)  # nazik ol
    print("-" * 60)
    print("BİTTİ. Başarılı: %d  Başarısız: %d" % (ok, fail))
    print("Klasör: %s" % OUT_DIR)
    if fail > 0:
        print("\nBaşarısız olanlar için:")
        print("- Wikipedia'da kulübün İngilizce sayfasına git")
        print("- Logoyu indir")
        print("- assets/clubs/<slug>.png olarak kaydet")
        print("- Örnek slug: galatasaray, fenerbahce, besiktas")


if __name__ == "__main__":
    main()