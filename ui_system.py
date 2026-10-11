# -*- coding: utf-8 -*-
"""Ortak arayüz parçaları: tema, butonlar, üst bar, avatar, fotoğraf yöneticisi."""
import json
import os
import re
import ssl
import threading
import time
import urllib.parse
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import (Color, Ellipse, Line, Rectangle, RoundedRectangle,
                           StencilPop, StencilPush, StencilUnUse, StencilUse)
from kivy.graphics.texture import Texture
from kivy.metrics import dp, sp
from kivy.properties import ListProperty, NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget

from save_system import save

# ----------------------------------------------------------------------------
# TEMA
# ----------------------------------------------------------------------------
NAVY_DARK = (0.02, 0.05, 0.13, 1)
NAVY = (0.05, 0.11, 0.24, 1)
NAVY_LIGHT = (0.10, 0.19, 0.38, 1)
GREEN = (0.10, 0.70, 0.38, 1)
GREEN_DARK = (0.06, 0.48, 0.26, 1)
GOLD = (1.0, 0.78, 0.15, 1)
GOLD_DARK = (0.80, 0.52, 0.08, 1)
RED = (0.86, 0.22, 0.25, 1)
GREY = (0.35, 0.40, 0.50, 1)
WHITE = (1, 1, 1, 1)

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def asset_path(*parts):
    return os.path.join(ASSETS_DIR, *parts)


def goto(name):
    App.get_running_app().sm.current = name


# ----------------------------------------------------------------------------
# SES (dosya yoksa sessizce atlanır)
# ----------------------------------------------------------------------------
_sound_cache = {}
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Sesler/müzikler bu klasörlerden herhangi birine konabilir:
_SOUND_DIRS = [os.path.join(_BASE_DIR, "sounds"), asset_path("sounds"),
               os.path.join(_BASE_DIR, "music"), asset_path("music")]


_EFFECTS = ("buy", "correct", "goal", "save", "wrong", "taraftar")
_EXTS = (".mp3", ".ogg", ".wav")


def _audio_files():
    """Ses klasörlerindeki tüm ses dosyaları: [(klasör, dosya_adı), ...]"""
    out = []
    for d in _SOUND_DIRS:
        try:
            for f in sorted(os.listdir(d)):
                if f.lower().endswith(_EXTS):
                    out.append((d, f))
        except OSError:
            pass
    return out


def find_sound(name):
    for d in _SOUND_DIRS:
        for ext in ("mp3", "ogg", "wav"):
            p = os.path.join(d, "%s.%s" % (name, ext))
            if os.path.isfile(p):
                return p
    # büyük/küçük harf farkı (Music.MP3 gibi) için
    for d, f in _audio_files():
        if os.path.splitext(f)[0].lower() == name.lower():
            return os.path.join(d, f)
    return None


def _extra_music():
    """music.mp3 yoksa: efekt olmayan ilk ses dosyasını genel müzik say."""
    for d, f in _audio_files():
        stem = os.path.splitext(f)[0].lower()
        if stem not in _EFFECTS:
            return os.path.splitext(f)[0], os.path.join(d, f)
    return None


def play_sound(name):
    try:
        if name not in _sound_cache:
            found = find_sound(name)
            snd = None
            if found:
                from kivy.core.audio import SoundLoader
                snd = SoundLoader.load(found)
            _sound_cache[name] = snd
        snd = _sound_cache[name]
        if snd:
            snd.stop()
            snd.play()
    except Exception:
        pass


# -- arka plan müziği --------------------------------------------------------
_music = {"name": None, "snd": None, "status": "Müzik: henüz başlamadı"}
MUSIC_VOLUME = 0.45


def music_status():
    return _music["status"]


def stop_music():
    snd = _music["snd"]
    _music["name"] = None
    _music["snd"] = None
    if snd:
        try:
            snd.stop()
        except Exception:
            pass


def play_music(*names):
    """Verilen isimlerden dosyası olan İLK müziği döngüde çalar.
    Zaten o müzik çalıyorsa yeniden başlatmaz. Hiçbiri yoksa sessiz kalır."""
    try:
        cand = None
        for n in names:
            path = find_sound(n)
            if path:
                cand = (n, path)
                break
        if cand is None and "music" in names:
            cand = _extra_music()
        if cand is None:
            stop_music()
            files = [f for _, f in _audio_files()]
            _music["status"] = ("Müzik dosyası yok. sounds klasöründe: " +
                                (", ".join(files) if files else "ses dosyası yok"))
            return
        n, path = cand
        if _music["name"] == n and _music["snd"]:
            return
        stop_music()
        from kivy.core.audio import SoundLoader
        snd = SoundLoader.load(path)
        if not snd:
            _music["status"] = "Müzik yüklenemedi (format?): " + os.path.basename(path)
            return
        snd.loop = True
        snd.volume = MUSIC_VOLUME
        snd.play()
        _music["name"] = n
        _music["snd"] = snd
        _music["status"] = "Müzik çalıyor: " + os.path.basename(path)
    except Exception as e:
        _music["status"] = "Müzik hata: %s" % (str(e)[:60],)


# ----------------------------------------------------------------------------
# GRADYAN
# ----------------------------------------------------------------------------
_grad_cache = {}


def gradient_texture(top, bottom, steps=64):
    key = (tuple(top[:3]), tuple(bottom[:3]))
    if key in _grad_cache:
        return _grad_cache[key]
    tex = Texture.create(size=(1, steps), colorfmt="rgba")
    buf = bytearray()
    for i in range(steps):
        t = i / float(steps - 1)          # satır 0 = alt
        for k in range(3):
            v = bottom[k] + (top[k] - bottom[k]) * t
            buf.append(max(0, min(255, int(v * 255))))
        buf.append(255)
    tex.blit_buffer(bytes(buf), colorfmt="rgba", bufferfmt="ubyte")
    tex.wrap = "clamp_to_edge"
    tex.mag_filter = "linear"
    _grad_cache[key] = tex
    return tex


class Background(Widget):
    """Lacivert gradyan + silik saha çizgileri."""

    def __init__(self, top=NAVY, bottom=NAVY_DARK, **kw):
        super().__init__(**kw)
        with self.canvas:
            Color(1, 1, 1, 1)
            self._grad = Rectangle(texture=gradient_texture(top, bottom))
            Color(GREEN[0], GREEN[1], GREEN[2], 0.10)
            self._circle = Line(circle=(0, 0, 1), width=dp(2))
            self._mid = Line(points=[0, 0, 0, 0], width=dp(2))
            self._box = Line(rectangle=(0, 0, 1, 1), width=dp(2))
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *a):
        x, y = self.pos
        w, h = self.size
        self._grad.pos = self.pos
        self._grad.size = self.size
        self._circle.circle = (x + w * 0.5, y + h * 0.5, h * 0.26)
        self._mid.points = [x + w * 0.5, y, x + w * 0.5, y + h]
        self._box.rectangle = (x - dp(4), y + h * 0.5 - h * 0.28, w * 0.14, h * 0.56)


# ----------------------------------------------------------------------------
# TEMEL BİLEŞENLER
# ----------------------------------------------------------------------------
class TLabel(Label):
    """Metni kendi boyutuna göre hizalayan etiket."""

    def __init__(self, **kw):
        kw.setdefault("halign", "left")
        kw.setdefault("valign", "middle")
        kw.setdefault("color", WHITE)
        super().__init__(**kw)
        self.bind(size=self._ts)
        self._ts()

    def _ts(self, *a):
        self.text_size = self.size


class RoundedButton(Button):
    """Yuvarlatılmış, gölgeli, basma efektli buton."""
    bg = ListProperty(list(GREEN))

    def __init__(self, **kw):
        bg = kw.pop("bg", None)
        kw.setdefault("background_normal", "")
        kw.setdefault("background_down", "")
        kw.setdefault("background_disabled_normal", "")
        kw["background_color"] = (0, 0, 0, 0)
        kw.setdefault("bold", True)
        kw.setdefault("font_size", sp(18))
        kw.setdefault("halign", "center")
        super().__init__(**kw)
        if bg:
            self.bg = list(bg)
        self.disabled_color = (1, 1, 1, 0.5)
        r = dp(16)
        with self.canvas.before:
            self._sc = Color(0, 0, 0, 0.35)
            self._shadow = RoundedRectangle(radius=[r])
            self._bc = Color(*self.bg)
            self._body = RoundedRectangle(radius=[r])
            self._hc = Color(1, 1, 1, 0.10)
            self._shine = RoundedRectangle(radius=[r, r, 0, 0])
        self.bind(pos=self._upd, size=self._upd, state=self._upd,
                  bg=self._upd, disabled=self._upd)
        self._upd()

    def _upd(self, *a):
        off = dp(2) if self.state == "down" else 0
        x, y = self.pos
        w, h = self.size
        self._shadow.pos = (x, y - dp(3) + off)
        self._shadow.size = (w, h)
        self._body.pos = (x, y - off)
        self._body.size = (w, h)
        self._shine.pos = (x, y + h * 0.5 - off)
        self._shine.size = (w, h * 0.5)
        if self.disabled:
            self._bc.rgba = (0.22, 0.27, 0.36, 1)
        else:
            f = 0.78 if self.state == "down" else 1.0
            c = self.bg
            self._bc.rgba = (c[0] * f, c[1] * f, c[2] * f, c[3])


class CoinWidget(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.bind(pos=self._d, size=self._d)
        self._d()

    def _d(self, *a):
        self.canvas.clear()
        with self.canvas:
            s = min(self.width, self.height) * 0.9
            cx, cy = self.center
            Color(0.65, 0.42, 0.04, 1)
            Ellipse(pos=(cx - s / 2, cy - s / 2 - dp(1.5)), size=(s, s))
            Color(*GOLD)
            Ellipse(pos=(cx - s / 2, cy - s / 2), size=(s, s))
            Color(1, 0.92, 0.55, 1)
            Ellipse(pos=(cx - s * 0.33, cy - s * 0.33), size=(s * 0.66, s * 0.66))
            Color(0.88, 0.62, 0.10, 1)
            Ellipse(pos=(cx - s * 0.20, cy - s * 0.20), size=(s * 0.40, s * 0.40))


class BarWidget(Widget):
    value = NumericProperty(0)
    maximum = NumericProperty(100)

    def __init__(self, fill=GREEN, **kw):
        self.fill = fill
        super().__init__(**kw)
        self.bind(pos=self._d, size=self._d, value=self._d, maximum=self._d)
        self._d()

    def _d(self, *a):
        self.canvas.clear()
        x, y = self.pos
        w, h = self.size
        if w <= 0 or h <= 0:
            return
        with self.canvas:
            Color(1, 1, 1, 0.14)
            RoundedRectangle(pos=(x, y), size=(w, h), radius=[h / 2])
            frac = max(0.0, min(1.0, self.value / float(self.maximum or 1)))
            if frac > 0:
                Color(*self.fill)
                RoundedRectangle(pos=(x, y), size=(max(h, w * frac), h),
                                 radius=[h / 2])


# ----------------------------------------------------------------------------
# AVATAR (çizimle oluşturulan 2D/yarı-3D futbolcu)
# ----------------------------------------------------------------------------
_KITS = [
    ((0.86, 0.12, 0.18), (1.00, 1.00, 1.00)),
    ((0.15, 0.45, 0.90), (0.95, 0.95, 0.95)),
    ((0.98, 0.78, 0.10), (0.10, 0.20, 0.60)),
    ((0.95, 0.95, 0.95), (0.10, 0.10, 0.20)),
    ((0.10, 0.65, 0.35), (1.00, 1.00, 1.00)),
    ((0.55, 0.10, 0.35), (0.90, 0.90, 0.90)),
    ((0.06, 0.06, 0.12), (0.90, 0.20, 0.20)),
    ((0.95, 0.45, 0.10), (0.10, 0.10, 0.10)),
]
_SKINS = [(0.96, 0.80, 0.66), (0.86, 0.66, 0.50), (0.62, 0.42, 0.30), (0.42, 0.28, 0.20)]
_HAIRS = [(0.10, 0.07, 0.05), (0.35, 0.22, 0.10), (0.80, 0.65, 0.30), (0.04, 0.04, 0.04)]


def kit_for(key):
    h = zlib.crc32(key.encode("utf-8"))
    shirt, shorts = _KITS[h % len(_KITS)]
    skin = _SKINS[(h >> 8) % len(_SKINS)]
    hair = _HAIRS[(h >> 16) % len(_HAIRS)]
    return shirt, shorts, skin, hair


def jersey_number(key):
    return (zlib.crc32(key.encode("utf-8")) >> 4) % 30 + 1


class AvatarWidget(Widget):
    bob = NumericProperty(0)

    def __init__(self, key="starter", number=None, **kw):
        super().__init__(**kw)
        self.kit = kit_for(key)
        self.num = Label(text="", bold=True, color=(1, 1, 1, 0.95),
                         size_hint=(None, None), size=(dp(40), dp(40)))
        self.add_widget(self.num)
        self.set_player(key, number)
        self.bind(pos=self.redraw, size=self.redraw, bob=self.redraw)

    def set_player(self, key, number=None):
        self.kit = kit_for(key)
        self.num.text = str(number if number is not None else jersey_number(key))
        self.redraw()

    def redraw(self, *a):
        shirt, shorts, skin, hair = self.kit
        H = min(self.height, self.width * 1.8) * 0.95
        if H <= 0:
            return
        cx = self.center_x
        y0 = self.y + (self.height - H) / 2.0
        lift = self.bob * H * 0.05
        c = self.canvas.before
        c.clear()
        with c:
            Color(0, 0, 0, 0.35)
            Ellipse(pos=(cx - 0.28 * H, y0 - 0.015 * H), size=(0.56 * H, 0.07 * H))
            # bacaklar
            Color(*skin)
            for dx in (-0.12, 0.04):
                RoundedRectangle(pos=(cx + dx * H, y0 + lift + 0.05 * H),
                                 size=(0.08 * H, 0.28 * H), radius=[dp(3)])
            Color(*shirt)
            for dx in (-0.12, 0.04):
                RoundedRectangle(pos=(cx + dx * H, y0 + lift + 0.05 * H),
                                 size=(0.08 * H, 0.14 * H), radius=[dp(3)])
            Color(0.07, 0.07, 0.10, 1)
            for dx in (-0.14, 0.03):
                RoundedRectangle(pos=(cx + dx * H, y0 + lift),
                                 size=(0.11 * H, 0.06 * H), radius=[dp(4)])
            # şort
            Color(*shorts)
            RoundedRectangle(pos=(cx - 0.15 * H, y0 + lift + 0.28 * H),
                             size=(0.30 * H, 0.18 * H), radius=[dp(5)])
            # kollar
            Color(*skin)
            for dx in (-0.245, 0.175):
                RoundedRectangle(pos=(cx + dx * H, y0 + lift + 0.46 * H),
                                 size=(0.07 * H, 0.26 * H), radius=[dp(4)])
            # forma
            Color(*shirt)
            RoundedRectangle(pos=(cx - 0.17 * H, y0 + lift + 0.44 * H),
                             size=(0.34 * H, 0.31 * H), radius=[dp(10)])
            for dx in (-0.245, 0.175):
                RoundedRectangle(pos=(cx + dx * H, y0 + lift + 0.60 * H),
                                 size=(0.07 * H, 0.13 * H), radius=[dp(4)])
            Color(1, 1, 1, 0.14)
            RoundedRectangle(pos=(cx - 0.17 * H, y0 + lift + 0.60 * H),
                             size=(0.17 * H, 0.15 * H), radius=[dp(10), 0, 0, 0])
            # boyun + kafa
            Color(*skin)
            Rectangle(pos=(cx - 0.03 * H, y0 + lift + 0.73 * H), size=(0.06 * H, 0.05 * H))
            Ellipse(pos=(cx - 0.10 * H, y0 + lift + 0.76 * H), size=(0.20 * H, 0.21 * H))
            Color(*hair)
            Ellipse(pos=(cx - 0.105 * H, y0 + lift + 0.865 * H), size=(0.21 * H, 0.11 * H))
        self.num.font_size = max(sp(8), H * 0.12)
        self.num.center = (cx, y0 + lift + 0.60 * H)


# ----------------------------------------------------------------------------
# GERÇEK YÜZ (mağaza kartları + ana menü avatarı)
# ----------------------------------------------------------------------------
_face_tex_cache = {}


def _face_texture(path):
    """Fotoğrafın yüzün olduğu üst kare bölgesini kırpılmış doku olarak verir."""
    tex = _face_tex_cache.get(path)
    if tex is not None:
        return tex
    from kivy.core.image import Image as CoreImage
    base = CoreImage(path).texture
    tw, th = base.size
    side = min(tw, th)
    x0 = (tw - side) / 2.0
    y0 = th - side                       # portre: üst kare (yüz+omuz); manzara: orta
    if tw > th:
        y0 = 0
    tex = base.get_region(x0, y0, side, side)
    if len(_face_tex_cache) > 160:
        _face_tex_cache.clear()
    _face_tex_cache[path] = tex
    return tex


class FaceDisc(Widget):
    """Yuvarlak kırpılmış futbolcu fotoğrafı + yeşil çerçeve."""

    def __init__(self, ring=GREEN, **kw):
        super().__init__(**kw)
        self.ring = ring
        self.tex = None
        self.bind(pos=self.redraw, size=self.redraw)

    def set_texture(self, tex):
        self.tex = tex
        self.redraw()

    def redraw(self, *a):
        self.canvas.clear()
        if self.tex is None or self.width <= 0:
            return
        d = min(self.width, self.height)
        x = self.center_x - d / 2.0
        y = self.center_y - d / 2.0
        with self.canvas:
            Color(0, 0, 0, 0.35)
            Ellipse(pos=(x, y - dp(3)), size=(d, d))
            StencilPush()
            Ellipse(pos=(x, y), size=(d, d))
            StencilUse()
            Color(1, 1, 1, 1)
            Rectangle(texture=self.tex, pos=(x, y), size=(d, d))
            StencilUnUse()
            Ellipse(pos=(x, y), size=(d, d))
            StencilPop()
            Color(*self.ring)
            Line(circle=(self.center_x, self.center_y, d / 2.0), width=dp(2.2))


class FaceAvatar(FloatLayout):
    """Futbolcunun gerçek yüzünü gösterir. Fotoğraf inene / bulunamazsa çizimli
    avatar görünür. `bob` özelliği ana menüdeki hafif zıplama animasyonu içindir."""
    bob = NumericProperty(0)

    def __init__(self, pid="starter", lazy=False, **kw):
        super().__init__(**kw)
        self.pid = None
        self._token = 0
        self._loaded = False
        self._retry_at = 0
        self._wiki = None
        self._name = None
        self.fallback = AvatarWidget(pid, size_hint=(1, 1))
        self.disc = FaceDisc(size_hint=(1, 1))
        self.add_widget(self.fallback)
        self.add_widget(self.disc)
        self.bind(bob=self._on_bob)
        self.set_player(pid, lazy=lazy)

    def _on_bob(self, *a):
        self.disc.pos_hint = {"center_x": 0.5, "center_y": 0.5 + self.bob * 0.015}
        self.fallback.bob = self.bob
        self.do_layout()

    def set_player(self, pid, lazy=False):
        from player_data import get_player
        p = get_player(pid)
        self._token += 1
        self.pid = p.id
        self._wiki = p.wiki
        self._name = p.name
        self._loaded = False
        self.disc.set_texture(None)
        self.fallback.opacity = 1
        self.fallback.set_player(p.id)
        if p.wiki and not lazy:
            self.ensure_loaded()

    def ensure_loaded(self):
        """Fotoğrafı (yerel / önbellek / internet) yükle. Birden çok çağrı güvenli."""
        if self._loaded or not self._wiki or time.time() < self._retry_at:
            return
        self._loaded = True
        tok = self._token
        from player_data import slugify
        slug = slugify(self._name)
        photos.request(slug, self._wiki, lambda path, tok=tok: self._got(tok, path), self._name)

    def _got(self, tok, path):
        if tok != self._token:
            return
        if not path:
            self._loaded = False         # 30 sn sonra yeniden denensin
            self._retry_at = time.time() + 30
            return
        try:
            self.disc.set_texture(_face_texture(path))
            self.fallback.opacity = 0
        except Exception:
            self._loaded = False


# ----------------------------------------------------------------------------
# FOTOĞRAF YÖNETİCİSİ
# ----------------------------------------------------------------------------
_ssl_ctx = None


def _ssl_context():
    global _ssl_ctx
    if _ssl_ctx is None:
        try:
            import certifi
            _ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            _ssl_ctx = ssl.create_default_context()
    return _ssl_ctx


class PhotoManager:
    """Fotoğraf arama sırası:
    1) assets/players/<slug>.jpg|png  (kendi fotoğraflarınız)
    2) önbellek (daha önce indirilmiş)
    3) Wikipedia'dan indir (internet gerekir)
    4) başarısızsa None -> arayüz varsayılan görseli gösterir
    """
    UA = "FutbolArena/1.0 (mobile quiz game; Kivy)"

    def __init__(self):
        self.cache_dir = None
        self._pool = ThreadPoolExecutor(max_workers=5)
        self._waiting = {}
        self._failed = {}
        self._lock = threading.Lock()

    def init(self, cache_dir):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def find_local(self, slug):
        dirs = [asset_path("players")]
        if self.cache_dir:
            dirs.append(self.cache_dir)
        for d in dirs:
            for ext in ("jpg", "jpeg", "png", "webp"):
                p = os.path.join(d, "%s.%s" % (slug, ext))
                try:
                    if os.path.isfile(p) and os.path.getsize(p) > 500:
                        return p
                except OSError:
                    pass
        return None

    def request(self, slug, wiki, callback, name=None):
        """callback(path_or_None) ana iş parçacığında çağrılır."""
        path = self.find_local(slug)
        if path:
            Clock.schedule_once(lambda dt: callback(path), 0)
            return
        failed = False
        with self._lock:
            ft = self._failed.get(slug)
            if ft and time.time() - ft < 45:
                failed = True
            elif slug in self._waiting:
                self._waiting[slug].append(callback)
                return
            else:
                self._waiting[slug] = [callback]
        if failed:
            Clock.schedule_once(lambda dt: callback(None), 0)
            return
        self._pool.submit(self._worker, slug, wiki, name or wiki)

    def _worker(self, slug, wiki, name):
        path = None
        try:
            path = self._download(slug, wiki, name)
        except Exception:
            path = None
        with self._lock:
            cbs = self._waiting.pop(slug, [])
            if not path:
                self._failed[slug] = time.time()
        for cb in cbs:
            Clock.schedule_once(lambda dt, cb=cb: cb(path), 0)

    # -- ağ yardımcıları ------------------------------------------------
    def _get(self, url, timeout=8):
        req = urllib.request.Request(url, headers={"User-Agent": self.UA, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r:
            return r.read()

    @staticmethod
    def _thumb_from_summary(j):
        if j.get("type") == "disambiguation":
            return None
        txt = ((j.get("description") or "") + " " + (j.get("extract") or "")[:240]).lower()
        if not any(k in txt for k in ("footbal", "soccer", "goalkeeper")):
            return None
        return (j.get("thumbnail") or {}).get("source")

    def _thumb_from_title(self, title):
        url = ("https://en.wikipedia.org/api/rest_v1/page/summary/" +
               urllib.parse.quote(title.replace(" ", "_"), safe=""))
        j = json.loads(self._get(url).decode("utf-8"))
        return self._thumb_from_summary(j)

    def _thumb_from_search(self, name):
        url = ("https://en.wikipedia.org/w/rest.php/v1/search/page?q=" +
               urllib.parse.quote(name + " footballer") + "&limit=3")
        j = json.loads(self._get(url).decode("utf-8"))
        for p in j.get("pages", []):
            key = p.get("key")
            if not key:
                continue
            try:
                t = self._thumb_from_title(key)
            except Exception:
                t = None
            if t:
                return t
        return None

    def _download(self, slug, wiki, name):
        thumb = None
        try:
            thumb = self._thumb_from_title(wiki)
        except Exception:
            thumb = None
        if not thumb:
            thumb = self._thumb_from_search(name)
        if not thumb:
            return None
        bigger = re.sub(r"/(\d+)px-", "/500px-", thumb, count=1)
        for url in (bigger, thumb):
            try:
                data = self._get(url, timeout=12)
                if len(data) < 1500:
                    continue
                ext = "png" if url.lower().split("?")[0].endswith(".png") else "jpg"
                final = os.path.join(self.cache_dir, "%s.%s" % (slug, ext))
                tmp = final + ".part"
                with open(tmp, "wb") as f:
                    f.write(data)
                os.replace(tmp, final)
                return final
            except Exception:
                continue
        return None


photos = PhotoManager()


def _make_image():
    try:
        return Image(fit_mode="contain", nocache=True)
    except TypeError:
        return Image(allow_stretch=True, keep_ratio=True, nocache=True)


class PlayerPhoto(FloatLayout):
    """Büyük futbolcu fotoğrafı; yüklenemezse düzgün varsayılan görsel."""

    def __init__(self, **kw):
        super().__init__(**kw)
        r = dp(20)
        with self.canvas.before:
            Color(0, 0, 0, 0.35)
            self._sh = RoundedRectangle(radius=[r])
            Color(0.08, 0.16, 0.33, 1)
            self._bg = RoundedRectangle(radius=[r])
            Color(*GREEN)
            self._bd = Line(rounded_rectangle=(0, 0, 1, 1, r), width=dp(2))
        self.avatar = AvatarWidget("?", number="?", size_hint=(0.55, 0.88),
                                   pos_hint={"center_x": 0.5, "center_y": 0.52})
        self.img = _make_image()
        self.img.size_hint = (0.96, 0.96)
        self.img.pos_hint = {"center_x": 0.5, "center_y": 0.5}
        self.status = TLabel(text="", halign="center", font_size=sp(14),
                             color=(1, 1, 1, 0.85), size_hint=(1, 0.12),
                             pos_hint={"center_x": 0.5, "y": 0.02})
        self.add_widget(self.avatar)
        self.add_widget(self.img)
        self.add_widget(self.status)
        self.img.opacity = 0
        self.bind(pos=self._upd, size=self._upd)
        self._upd()

    def _upd(self, *a):
        x, y = self.pos
        w, h = self.size
        self._sh.pos = (x, y - dp(4))
        self._sh.size = (w, h)
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._bd.rounded_rectangle = (x, y, w, h, dp(20))

    def show_loading(self):
        self.img.opacity = 0
        self.avatar.opacity = 0.35
        self.status.text = "Fotoğraf yükleniyor..."

    def show_default(self, msg=""):
        self.img.opacity = 0
        self.avatar.opacity = 1
        self.status.text = msg

    def show_image(self, path):
        try:
            self.img.source = path
            self.img.opacity = 1
            self.avatar.opacity = 0
            self.status.text = ""
            Clock.schedule_once(lambda dt: self._verify(path), 0.4)
        except Exception:
            self.show_default("Fotoğraf okunamadı")

    def _verify(self, path):
        if self.img.source == path and self.img.texture is None:
            self.show_default("Fotoğraf okunamadı")


# ----------------------------------------------------------------------------
# ÜST BAR (kullanıcı adı + puan) - her ekranda sol üstte
# ----------------------------------------------------------------------------
class HeaderBar(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="horizontal", size_hint=(None, None),
                         size=(dp(310), dp(46)),
                         padding=[dp(14), dp(5), dp(10), dp(5)], spacing=dp(6), **kw)
        with self.canvas.before:
            Color(0.02, 0.05, 0.13, 0.82)
            self._bg = RoundedRectangle(radius=[dp(23)])
            Color(GREEN[0], GREEN[1], GREEN[2], 0.9)
            self._bd = Line(rounded_rectangle=(0, 0, 1, 1, dp(23)), width=dp(1.6))
        self.name_lbl = TLabel(text="", font_size=sp(15), bold=True, shorten=True,
                               shorten_from="right")
        self.coin = CoinWidget(size_hint=(None, 1), width=dp(30))
        self.pts_lbl = TLabel(text="0", font_size=sp(20), bold=True, color=GOLD,
                              size_hint=(None, 1), width=dp(84), halign="left")
        self.add_widget(self.name_lbl)
        self.add_widget(self.coin)
        self.add_widget(self.pts_lbl)
        self._last = None
        self.bind(pos=self._upd, size=self._upd)
        save.subscribe(self.refresh)
        self.refresh()

    def _upd(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._bd.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(23))

    def refresh(self, *a):
        self.name_lbl.text = save.username
        pts = save.points
        self.pts_lbl.text = str(pts)
        if self._last is not None and pts != self._last:
            Animation.cancel_all(self.pts_lbl, "font_size")
            (Animation(font_size=sp(27), d=0.08) +
             Animation(font_size=sp(20), d=0.14)).start(self.pts_lbl)
        self._last = pts


# ----------------------------------------------------------------------------
# OVERLAY (sonuç/kutlama ekranları) ve TOAST
# ----------------------------------------------------------------------------
class Overlay(FloatLayout):
    def __init__(self, title, subtitle="", buttons=(), title_color=WHITE, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(0, 0, 0, 0.74)
            self._dim = Rectangle()
        self.bind(pos=self._upd, size=self._upd)

        cw = min(dp(560), Window.width * 0.84)
        ch = min(dp(290), Window.height * 0.80)
        card = BoxLayout(orientation="vertical", size_hint=(None, None),
                         size=(cw, ch), pos_hint={"center_x": 0.5, "center_y": 0.5},
                         padding=dp(20), spacing=dp(10))
        with card.canvas.before:
            Color(0, 0, 0, 0.4)
            self._cs = RoundedRectangle(radius=[dp(24)])
            Color(*NAVY_LIGHT)
            self._cb = RoundedRectangle(radius=[dp(24)])
            Color(*title_color)
            self._cl = Line(rounded_rectangle=(0, 0, 1, 1, dp(24)), width=dp(2.2))

        def upd(*a):
            self._cs.pos = (card.x, card.y - dp(4))
            self._cs.size = card.size
            self._cb.pos = card.pos
            self._cb.size = card.size
            self._cl.rounded_rectangle = (card.x, card.y, card.width, card.height, dp(24))
        card.bind(pos=upd, size=upd)

        card.add_widget(TLabel(text=title, halign="center", bold=True,
                               font_size=sp(30 if len(title) < 22 else 24),
                               color=title_color, size_hint_y=0.42))
        if subtitle:
            card.add_widget(TLabel(text=subtitle, halign="center", font_size=sp(16),
                                   color=(1, 1, 1, 0.9), size_hint_y=0.28))
        row = BoxLayout(orientation="horizontal", spacing=dp(12), size_hint_y=None,
                        height=dp(52))
        for text, cb, color in buttons:
            b = RoundedButton(text=text, bg=color, font_size=sp(16))
            b.bind(on_release=lambda inst, cb=cb: cb())
            row.add_widget(b)
        card.add_widget(row)
        self.add_widget(card)

    def _upd(self, *a):
        self._dim.pos = self.pos
        self._dim.size = self.size

    def show(self, parent):
        self.opacity = 0
        parent.add_widget(self)
        Animation(opacity=1, d=0.2).start(self)

    def dismiss(self):
        if self.parent:
            self.parent.remove_widget(self)

    def on_touch_down(self, touch):
        super().on_touch_down(touch)
        return True

    def on_touch_move(self, touch):
        super().on_touch_move(touch)
        return True

    def on_touch_up(self, touch):
        super().on_touch_up(touch)
        return True


class Toast(Label):
    def __init__(self, text, color=GREEN_DARK, **kw):
        super().__init__(text=text, bold=True, font_size=sp(16),
                         size_hint=(None, None),
                         size=(min(dp(460), Window.width * 0.84), dp(44)),
                         pos_hint={"center_x": 0.5, "y": 0.05}, **kw)
        with self.canvas.before:
            Color(*color)
            self._r = RoundedRectangle(radius=[dp(22)])
        self.bind(pos=self._u, size=self._u)

    def _u(self, *a):
        self._r.pos = self.pos
        self._r.size = self.size


def toast(parent, text, color=GREEN_DARK, duration=1.6):
    t = Toast(text, color)
    t.opacity = 0
    parent.add_widget(t)

    def done(*a):
        if t.parent:
            t.parent.remove_widget(t)
    anim = (Animation(opacity=1, d=0.15) + Animation(opacity=1, d=duration) +
            Animation(opacity=0, d=0.3))
    anim.bind(on_complete=done)
    anim.start(t)


# ----------------------------------------------------------------------------
# TEMEL EKRAN
# ----------------------------------------------------------------------------
class BaseScreen(Screen):
    def __init__(self, with_background=True, **kw):
        super().__init__(**kw)
        if with_background:
            self.add_widget(Background())

    def on_back(self):
        goto("menu")
