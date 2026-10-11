# -*- coding: utf-8 -*-
"""Futbol Arena - ana dosya (Kivy). Yatay mod, mobil dokunmatik."""
import os

os.environ.setdefault("KIVY_NO_ARGS", "1")

from kivy.config import Config

Config.set("graphics", "width", "1280")      # masaüstünde test için
Config.set("graphics", "height", "720")
Config.set("graphics", "resizable", "1")
Config.set("kivy", "exit_on_escape", "0")


# ============================================================================
# BÖLÜM: save_system
# ============================================================================
"""Kalıcı kayıt sistemi.

- JSON dosyası uygulamanın özel veri klasöründe saklanır (Android'de silinmez).
- Atomik yazma: önce geçici dosyaya yazılır, sonra yer değiştirilir.
- Her yazımdan önce eski kayıt .bak olarak yedeklenir; ana dosya bozulursa yedek okunur.
- Her değişiklik anında diske yazılır ve dinleyicilere (üst bar vb.) bildirilir.
"""
import copy
import json
import os
import shutil
import tempfile
import threading

DEFAULT_DATA = {
    "version": 1,
    "username": "",
    "points": 0,
    "owned": ["starter"],
    "selected_avatar": "starter",
    "starter": "",
    "special_penalty_rights": 0,
    "stats": {
        "correct": 0,
        "wrong": 0,
        "best_streak": 0,
        "easy_correct": 0,
        "hard_correct": 0,
        "games_played": 0,
        "penalty_shots": 0,
        "penalty_goals": 0,
        "penalty_saved": 0,
        "penalty_missed": 0,
        "special_goals": 0,
    },
}


def _merge(defaults, raw):
    """Eksik/bozuk alanları varsayılanlarla tamamlar, tipleri doğrular."""
    if not isinstance(raw, dict):
        raw = {}
    out = {}
    for key, dv in defaults.items():
        rv = raw.get(key, dv)
        if isinstance(dv, dict):
            out[key] = _merge(dv, rv)
        elif isinstance(dv, bool):
            out[key] = rv if isinstance(rv, bool) else dv
        elif isinstance(dv, int):
            ok = isinstance(rv, int) and not isinstance(rv, bool)
            out[key] = rv if ok else dv
        elif isinstance(dv, str):
            out[key] = rv if isinstance(rv, str) else dv
        elif isinstance(dv, list):
            out[key] = [str(i) for i in rv] if isinstance(rv, list) else list(dv)
        else:
            out[key] = rv
    return out


class SaveSystem:
    def __init__(self):
        self.data = copy.deepcopy(DEFAULT_DATA)
        self.path = None
        self.backup = None
        self._lock = threading.RLock()
        self._listeners = []

    # ------------------------------------------------------------ yükleme
    def init(self, directory):
        os.makedirs(directory, exist_ok=True)
        self.path = os.path.join(directory, "save.json")
        self.backup = self.path + ".bak"
        self.load()

    def load(self):
        for p in (self.path, self.backup):
            if not p or not os.path.isfile(p):
                continue
            try:
                with open(p, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                self.data = _merge(DEFAULT_DATA, raw)
                self._sanitize()
                return
            except Exception:
                continue
        self.data = copy.deepcopy(DEFAULT_DATA)

    def _sanitize(self):
        d = self.data
        d["points"] = max(0, d["points"])
        d["special_penalty_rights"] = max(0, d["special_penalty_rights"])
        if "starter" not in d["owned"]:
            d["owned"].insert(0, "starter")
        d["owned"] = list(dict.fromkeys(d["owned"]))
        if d["selected_avatar"] not in d["owned"]:
            d["selected_avatar"] = "starter"

    # ------------------------------------------------------------ yazma
    def flush(self):
        if not self.path:
            return False
        with self._lock:
            tmp = None
            try:
                payload = json.dumps(self.data, ensure_ascii=False, indent=2)
                fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path),
                                           prefix="save_", suffix=".tmp")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(payload)
                    f.flush()
                    os.fsync(f.fileno())
                if os.path.exists(self.path):
                    try:
                        shutil.copy2(self.path, self.backup)
                    except OSError:
                        pass
                os.replace(tmp, self.path)
                return True
            except Exception:
                if tmp and os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
                return False

    def _commit(self):
        self.flush()
        self._notify()

    # ------------------------------------------------------------ dinleyiciler
    def subscribe(self, fn):
        if fn not in self._listeners:
            self._listeners.append(fn)

    def unsubscribe(self, fn):
        if fn in self._listeners:
            self._listeners.remove(fn)

    def _notify(self):
        for fn in list(self._listeners):
            try:
                fn()
            except Exception:
                pass

    # ------------------------------------------------------------ okuma
    @property
    def username(self):
        return self.data["username"]

    @property
    def starter(self):
        """Açılışta seçilen başlangıç futbolcusunun adı ('' = henüz seçilmedi)."""
        return self.data["starter"]

    @property
    def points(self):
        return self.data["points"]

    @property
    def owned(self):
        return list(self.data["owned"])

    @property
    def selected_avatar(self):
        return self.data["selected_avatar"]

    @property
    def special_rights(self):
        return self.data["special_penalty_rights"]

    @property
    def stats(self):
        return self.data["stats"]

    def owns(self, pid):
        return pid in self.data["owned"]

    # ------------------------------------------------------------ işlemler
    def set_username(self, name):
        with self._lock:
            self.data["username"] = name.strip()
            self._commit()

    def set_starter(self, name):
        with self._lock:
            self.data["starter"] = name
            self._commit()

    def add_points(self, n):
        with self._lock:
            self.data["points"] = max(0, self.data["points"] + int(n))
            self._commit()

    def buy_player(self, pid, price):
        """(başarılı_mı, neden) döndürür. Puan düşme + koleksiyona ekleme tek adımda."""
        with self._lock:
            if pid in self.data["owned"]:
                return False, "owned"
            if self.data["points"] < price:
                return False, "points"
            self.data["points"] -= price
            self.data["owned"].append(pid)
            self.data["selected_avatar"] = pid      # yeni alınan futbolcu ana menüye geçer
            self._commit()
            return True, "ok"

    def select_avatar(self, pid):
        with self._lock:
            if pid not in self.data["owned"]:
                return False
            self.data["selected_avatar"] = pid
            self._commit()
            return True

    def begin_game(self):
        with self._lock:
            self.data["stats"]["games_played"] += 1
            self._commit()

    def record_answer(self, correct, points, streak, mode):
        with self._lock:
            s = self.data["stats"]
            if correct:
                self.data["points"] += int(points)
                s["correct"] += 1
                s[mode + "_correct"] = s.get(mode + "_correct", 0) + 1
                if streak > s["best_streak"]:
                    s["best_streak"] = streak
            else:
                s["wrong"] += 1
            self._commit()

    def grant_special_right(self, n=1):
        with self._lock:
            self.data["special_penalty_rights"] += n
            self._commit()

    def record_penalty(self, outcome, special=False):
        """outcome: 'goal' | 'saved' | 'miss'. Kazanılan puanı döndürür
        (kaleci kurtarırsa -1 döner ve 1 puan silinir; puan 0'ın altına inmez).
        Puan ekleme, hak tüketme ve istatistik tek kayıt işleminde yapılır."""
        gained = 0
        with self._lock:
            s = self.data["stats"]
            s["penalty_shots"] += 1
            if outcome == "goal":
                s["penalty_goals"] += 1
                if special and self.data["special_penalty_rights"] > 0:
                    gained = 25
                    self.data["special_penalty_rights"] -= 1
                    s["special_goals"] += 1
                else:
                    gained = 1
                self.data["points"] += gained
            elif outcome == "saved":
                s["penalty_saved"] += 1
                if self.data["points"] > 0:
                    self.data["points"] -= 1
                    gained = -1
            else:
                s["penalty_missed"] += 1
            self._commit()
        return gained


save = SaveSystem()


# ============================================================================
# BÖLÜM: player_data
# ============================================================================
"""Futbolcu veritabanı: mağaza listesi, fiyatlar ve quiz havuzları."""
import re
import unicodedata
from collections import namedtuple

Player = namedtuple("Player", "id name power price wiki")
QuizPlayer = namedtuple("QuizPlayer", "name wiki slug")


def slugify(text):
    text = text.replace("ı", "i").replace("İ", "I")
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "player"


# --------------------------------------------------------------------------
# MAĞAZA: (isim, güç)
# --------------------------------------------------------------------------
_SHOP_RAW = [
    ("Lionel Messi", 100), ("Cristiano Ronaldo", 100), ("Pelé", 99),
    ("Diego Maradona", 98), ("Kylian Mbappé", 97), ("Erling Haaland", 96),
    ("Johan Cruyff", 96), ("Neymar", 95), ("Zinedine Zidane", 95),
    ("Kevin De Bruyne", 94), ("Robert Lewandowski", 94),
    ("Ronaldo Nazário", 94), ("Franz Beckenbauer", 94),
    ("Mohamed Salah", 93), ("Vinícius Júnior", 93), ("Ronaldinho", 93),
    ("Jude Bellingham", 92), ("Harry Kane", 92), ("Karim Benzema", 92),
    ("Thierry Henry", 92), ("Andrés Iniesta", 92),
    ("Luka Modrić", 91), ("Xavi", 91), ("Zlatan Ibrahimović", 91),
    ("Paolo Maldini", 91),
    ("Gianluigi Buffon", 90), ("Lamine Yamal", 90), ("Rodri", 90),
    ("Virgil van Dijk", 90), ("Thibaut Courtois", 90), ("Toni Kroos", 90),
    ("Roberto Baggio", 90),
    ("Antoine Griezmann", 89), ("Son Heung-min", 89), ("Manuel Neuer", 89),
    ("Luis Suárez", 89), ("Kaká", 89), ("Andrea Pirlo", 89),
    ("Phil Foden", 89),
    ("Bukayo Saka", 88), ("Bruno Fernandes", 88), ("Jamal Musiala", 88),
    ("Rúben Dias", 88), ("Alisson", 88), ("Wayne Rooney", 88),
    ("Sergio Ramos", 88), ("Sergio Agüero", 88), ("Francesco Totti", 88),
    ("Alessandro Del Piero", 88), ("Dennis Bergkamp", 88),
    ("Pedri", 87), ("Florian Wirtz", 87), ("Federico Valverde", 87),
    ("Marc-André ter Stegen", 87), ("Martin Ødegaard", 87),
    ("Lautaro Martínez", 87), ("Joshua Kimmich", 87), ("Eden Hazard", 87),
    ("Iker Casillas", 87), ("Steven Gerrard", 87),
    ("Declan Rice", 86), ("Victor Osimhen", 86), ("Rafael Leão", 86),
    ("Gareth Bale", 86), ("Sadio Mané", 86), ("Ángel Di María", 86),
    ("Samuel Eto'o", 86), ("Didier Drogba", 86), ("Raúl", 86),
    ("Achraf Hakimi", 85), ("İlkay Gündoğan", 85), ("Paulo Dybala", 85),
    ("Mesut Özil", 85), ("N'Golo Kanté", 85), ("David Beckham", 85),
    ("Frank Lampard", 85), ("Roberto Carlos", 85),
    ("Hakan Çalhanoğlu", 84), ("Paul Pogba", 84), ("Casemiro", 84),
    ("Cesc Fàbregas", 84), ("Gheorghe Hagi", 84),
    ("Dani Alves", 83),
    ("Arda Güler", 82), ("Marcelo", 82), ("Petr Čech", 82),
    ("David de Gea", 82),
    ("Kenan Yıldız", 80), ("Hakan Şükür", 80),
    ("Arda Turan", 78),
    ("Burak Yılmaz", 76), ("Emre Belözoğlu", 76),
    ("Rüştü Reçber", 74),
]

# ORTA SEVİYE futbolcular (güç ~35-48): fiyatlar 1500'den başlar.
_MID_RAW = [
    ("Gökhan Töre", 36), ("Colin Kazim-Richards", 37), ("Ravel Morrison", 38),
    ("Mevlüt Erdinç", 39), ("Wilfried Bony", 40), ("Adel Taarabt", 40),
    ("Gökhan Gönül", 41), ("Jesse Lingard", 42), ("Caner Erkin", 42),
    ("Tuncay Şanlı", 43), ("Hamit Altıntop", 44), ("Selçuk İnan", 44),
    ("Ricardo Quaresma", 45), ("Hatem Ben Arfa", 46), ("Volkan Demirel", 47),
    ("Mario Balotelli", 48),
]

# Wikipedia'da isim tek başına yanlış sayfaya gidiyorsa doğru başlık
_WIKI = {
    "Ronaldo Nazário": "Ronaldo (Brazilian footballer)",
    "Rodri": "Rodri (footballer, born 1996)",
    "Raúl": "Raúl González",
    "Alisson": "Alisson Becker",
    "Marcelo": "Marcelo (footballer, born 1988)",
    "Neymar": "Neymar",
    "Pelé": "Pelé",
    "Kaká": "Kaká",
    "Xavi": "Xavi",
    "Casemiro": "Casemiro",
    "Pedri": "Pedri",
    "Selçuk İnan": "Selçuk İnan",
    "Mario Balotelli": "Mario Balotelli",
}

# Güç aralığı -> fiyat aralığı (isteğe göre)
_BANDS = [
    (1, 20, 10, 300), (21, 34, 300, 1400), (36, 60, 1500, 2300),
    (61, 75, 1500, 2500), (76, 85, 2500, 3500), (86, 95, 3500, 4500),
    (96, 100, 4500, 5000),
]


def base_price(power):
    for lo, hi, pl, ph in _BANDS:
        if lo <= power <= hi:
            t = (power - lo) / float(hi - lo) if hi > lo else 0.0
            return int(round((pl + (ph - pl) * t) / 5.0) * 5)
    return 5000


# Başlangıç futbolcusu seçenekleri (açılışta bir kez seçilir, güç 10, ücretsiz)
STARTER_CHOICES = [
    ("Barış Alper Yılmaz", "Barış Alper Yılmaz"),
    ("Mason Greenwood", "Mason Greenwood"),
    ("Victor Osimhen", "Victor Osimhen"),
    ("Leandro Trossard", "Leandro Trossard"),
    ("Mohamed Salah", "Mohamed Salah"),
    ("Dušan Vlahović", "Dušan Vlahović"),
]
_current_starter = [STARTER_CHOICES[0][0]]


def set_starter(name):
    """Seçilen başlangıç futbolcusunu ayarlar ('starter' kimliği bunu gösterir)."""
    names = [n for n, _ in STARTER_CHOICES]
    _current_starter[0] = name if name in names else STARTER_CHOICES[0][0]
    PLAYERS_BY_ID["starter"] = _starter_player()
    # mağazadaki liste de güncel kalsın
    for i, p in enumerate(SHOP_PLAYERS):
        if p.id == "starter":
            SHOP_PLAYERS[i] = PLAYERS_BY_ID["starter"]


def _starter_player():
    name = _current_starter[0]
    wiki = dict(STARTER_CHOICES).get(name, name)
    return Player("starter", name, 10, 0, wiki)


def _build_shop():
    items = sorted(_SHOP_RAW + _MID_RAW, key=lambda r: (r[1], r[0]))
    out = []
    last = 0
    for name, power in items:
        if power >= 100:
            price = 5000                      # Messi & Ronaldo: 5000
        else:
            price = base_price(power)
            if price <= last:                 # her futbolcuya ayrı fiyat
                price = last + 5
            last = price
        out.append(Player(slugify(name), name, power, price, _WIKI.get(name, name)))
    starter = _starter_player()                       # ücretsiz başlangıç avatarı (güç 10)
    return [starter] + sorted(out, key=lambda p: (p.price, p.name))


SHOP_PLAYERS = _build_shop()
PLAYERS_BY_ID = {p.id: p for p in SHOP_PLAYERS}


def get_player(pid):
    return PLAYERS_BY_ID.get(pid) or PLAYERS_BY_ID["starter"]


def shot_success_chance(power):
    """Kaleciyle aynı bölgeye atılmayan şutun isabet olasılığı.
    Güç 1 -> ~%45, güç 100 -> %90 (asla garanti değil)."""
    power = max(1, min(100, int(power)))
    return 0.45 + 0.45 * (power / 100.0)


# --------------------------------------------------------------------------
# QUIZ HAVUZLARI: (isim, wikipedia başlığı veya None)
# --------------------------------------------------------------------------
_EASY_RAW = [
    ("Lionel Messi", None), ("Cristiano Ronaldo", None),
    ("Kylian Mbappé", None), ("Erling Haaland", None), ("Neymar", None),
    ("Kevin De Bruyne", None), ("Mohamed Salah", None),
    ("Vinícius Júnior", None), ("Jude Bellingham", None),
    ("Harry Kane", None), ("Luka Modrić", None),
    ("Robert Lewandowski", None), ("Karim Benzema", None),
    ("Antoine Griezmann", None), ("Son Heung-min", None),
    ("Ronaldinho", None), ("Zinedine Zidane", None),
    ("Thierry Henry", None), ("Andrés Iniesta", None),
    ("Wayne Rooney", None), ("Sergio Ramos", None), ("Manuel Neuer", None),
    ("Gianluigi Buffon", None), ("Zlatan Ibrahimović", None),
    ("Paul Pogba", None), ("Eden Hazard", None), ("David Beckham", None),
    ("Diego Maradona", None), ("Pelé", None), ("Luis Suárez", None),
    ("Iker Casillas", None), ("Toni Kroos", None), ("Mesut Özil", None),
    ("Sergio Agüero", None), ("Ángel Di María", None),
    ("Thibaut Courtois", None), ("Virgil van Dijk", None),
    ("Lamine Yamal", None), ("Arda Güler", None),
    ("Hakan Çalhanoğlu", None), ("Andrea Pirlo", None),
    ("Francesco Totti", None),
    ("Ronaldo Nazário", "Ronaldo (Brazilian footballer)"),
    ("Steven Gerrard", None), ("Frank Lampard", None), ("Kaká", None),
    ("Bruno Fernandes", None), ("Bukayo Saka", None), ("Phil Foden", None),
    ("Rodri", "Rodri (footballer, born 1996)"), ("Pedri", None),
    ("Gareth Bale", None), ("Xavi", None),
]

_HARD_RAW = [
    ("Hristo Stoichkov", None), ("Gheorghe Hagi", None),
    ("Roberto Baggio", None), ("Michael Laudrup", None),
    ("Jari Litmanen", None), ("Dennis Bergkamp", None),
    ("Matthias Sammer", None), ("Rivaldo", None), ("Roberto Carlos", None),
    ("Lothar Matthäus", None), ("Gabriel Batistuta", None),
    ("Fabio Cannavaro", None), ("Alessandro Nesta", None),
    ("Gianfranco Zola", None), ("Pavel Nedvěd", None),
    ("Andriy Shevchenko", None), ("Hernán Crespo", None),
    ("Juan Román Riquelme", None), ("Clarence Seedorf", None),
    ("Edgar Davids", None), ("Patrick Kluivert", None),
    ("Marc Overmars", None), ("Robert Pirès", None),
    ("Nicolas Anelka", None), ("Claude Makélélé", None),
    ("Fernando Redondo", None), ("Gaizka Mendieta", None),
    ("Rui Costa", None), ("Luís Figo", None), ("Michael Ballack", None),
    ("Miroslav Klose", None), ("Ole Gunnar Solskjær", None),
    ("Dwight Yorke", None), ("Peter Schmeichel", None),
    ("Jens Lehmann", None), ("Oliver Kahn", None),
    ("Jay-Jay Okocha", None), ("Nwankwo Kanu", None),
    ("George Weah", None), ("Roger Milla", None), ("Hakan Şükür", None),
    ("Tugay Kerimoğlu", None), ("Alex de Souza", None),
    ("Rüştü Reçber", None), ("Emre Belözoğlu", None),
    ("Hidetoshi Nakata", None), ("Ali Daei", None),
    ("Park Ji-sung", None), ("Carlos Valderrama", None),
    ("René Higuita", None), ("Franz Beckenbauer", None),
    ("Paolo Maldini", None), ("Raúl", "Raúl González"),
    ("Samuel Eto'o", None), ("Didier Drogba", None),
]


def _quiz(raw):
    return [QuizPlayer(n, w or n, slugify(n)) for n, w in raw]


EASY_POOL = _quiz(_EASY_RAW)
HARD_POOL = _quiz(_HARD_RAW)


def all_photo_items():
    """Açılışta önceden indirilecek tüm fotoğraflar: (slug, wiki_başlığı, isim).
    Başlangıç oyuncusu, mağaza ve quiz havuzları; aynı kişi tekrar eklenmez."""
    seen = {}
    for name, wiki in STARTER_CHOICES:
        seen.setdefault(slugify(name), (slugify(name), wiki, name))
    for p in SHOP_PLAYERS:
        if p.wiki:
            slug = slugify(p.name)
            seen.setdefault(slug, (slug, p.wiki, p.name))
    for q in EASY_POOL + HARD_POOL:
        seen.setdefault(q.slug, (q.slug, q.wiki, q.name))
    return list(seen.values())


# ============================================================================
# BÖLÜM: ui_system
# ============================================================================
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


def start_screen():
    """Açılışta gidilecek ekran: kullanıcı adı -> başlangıç futbolcusu -> ana menü."""
    if not save.username:
        return "username"
    if not save.starter:
        return "starter"
    return "menu"


# ----------------------------------------------------------------------------
# SES (dosya yoksa sessizce atlanır)
# ----------------------------------------------------------------------------
_sound_cache = {}
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Sesler/müzikler bu klasörlerden herhangi birine konabilir:
_SOUND_DIRS = [os.path.join(_BASE_DIR, "sounds"), asset_path("sounds"),
               os.path.join(_BASE_DIR, "music"), asset_path("music")]


_EFFECTS = ("buy", "correct", "goal", "save", "wrong")
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
_face_base_keep = {}      # kırpılan bölge asıl dokuya bağlı: asıl doku çöpe giderse bölge BOŞ olur


def _face_texture(path):
    """Fotoğrafın yüzün olduğu üst kare bölgesini kırpılmış doku olarak verir."""
    tex = _face_tex_cache.get(path)
    if tex is not None:
        return tex
    from kivy.core.image import Image as CoreImage
    base = CoreImage(path, nocache=True).texture
    tw, th = base.size
    side = min(tw, th)
    x0 = (tw - side) / 2.0
    y0 = th - side                       # portre: üst kare (yüz+omuz); manzara: orta
    if tw > th:
        y0 = 0
    tex = base.get_region(x0, y0, side, side)
    if len(_face_tex_cache) > 70:
        _face_tex_cache.clear()
        _face_base_keep.clear()
    _face_base_keep[path] = base
    _face_tex_cache[path] = tex
    return tex


class FaceDisc(Widget):
    """Yuvarlak kırpılmış futbolcu fotoğrafı + yeşil çerçeve.
    Stencil kullanmaz (ScrollView içinde / Android'de fotoğrafı yutabiliyordu):
    doku doğrudan Ellipse'e kaplanır."""

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
        if self.tex is None or self.width <= 0 or self.height <= 0:
            return
        d = min(self.width, self.height)
        x = self.center_x - d / 2.0
        y = self.center_y - d / 2.0
        with self.canvas:
            Color(0, 0, 0, 0.35)
            Ellipse(pos=(x, y - dp(3)), size=(d, d))
            Color(1, 1, 1, 1)
            Ellipse(texture=self.tex, pos=(x, y), size=(d, d))
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

    def set_player_by_name(self, name):
        """Mağaza kimliği olmayan bir isim için (başlangıç seçim ekranı)."""
        self._token += 1
        self._name = name
        self._wiki = dict(STARTER_CHOICES).get(name, name)
        self._loaded = False
        self._retry_at = 0
        self.disc.set_texture(None)
        self.fallback.opacity = 1
        self.fallback.set_player(slugify(name))

    def ensure_loaded(self):
        """Fotoğrafı (yerel / önbellek / internet) yükle. Birden çok çağrı güvenli."""
        if self._loaded or not self._wiki or time.time() < self._retry_at:
            return
        self._loaded = True
        tok = self._token
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
            self._retry_at = time.time() + 30


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


# ============================================================================
# BÖLÜM: crowd
# ============================================================================
"""Penaltı sahnesi için hareketli tribün: zıplayan taraftarlar, atkılar, sallanan
bayraklar, kamera flaşları. Tek bir Widget; Clock ile ~20 FPS güncellenir."""
import math
import random

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import (Color, Ellipse, Line, PopMatrix, PushMatrix, Rectangle,
                           Rotate, RoundedRectangle, Translate)
from kivy.metrics import dp
from kivy.properties import NumericProperty
from kivy.uix.widget import Widget

# Sol blok kırmızı-beyaz, sağ blok mavi-sarı taraftar; arada karışık.
_HOME = [(0.85, 0.10, 0.15), (0.95, 0.95, 0.95), (0.70, 0.07, 0.12)]
_AWAY = [(0.12, 0.35, 0.85), (0.98, 0.80, 0.12), (0.10, 0.25, 0.60)]
_MIX = [(0.10, 0.10, 0.12), (0.15, 0.55, 0.30), (0.90, 0.50, 0.10),
        (0.55, 0.55, 0.60), (0.45, 0.15, 0.55)]
_CROWD_SKINS = [(0.96, 0.80, 0.66), (0.88, 0.68, 0.52), (0.70, 0.50, 0.36), (0.45, 0.30, 0.22)]
_CROWD_HAIRS = [(0.08, 0.06, 0.05), (0.30, 0.18, 0.08), (0.78, 0.62, 0.28), (0.04, 0.04, 0.04),
          (0.55, 0.30, 0.12)]
_ADS = [(0.80, 0.10, 0.15), (0.10, 0.45, 0.85), (0.95, 0.75, 0.10), (0.10, 0.60, 0.35),
        (0.95, 0.95, 0.95)]


def _shade(c, f):
    return (c[0] * f, c[1] * f, c[2] * f)


class CrowdWidget(Widget):
    excite = NumericProperty(0.35)       # 0 sakin ... 1 çılgın

    def __init__(self, **kw):
        super().__init__(**kw)
        self._blocks = []                # [translate, phase, speed, col]
        self._flags = []                 # [rotate, phase]
        self._flashes = []               # [color, ellipse]
        self._t = 0.0
        self._ev = None
        self._seed = 7
        self.bind(pos=self._rebuild, size=self._rebuild)

    # -- yaşam döngüsü -------------------------------------------------------
    def start(self):
        if self._ev is None:
            self._ev = Clock.schedule_interval(self._tick, 1 / 20.0)

    def stop(self):
        if self._ev is not None:
            self._ev.cancel()
            self._ev = None
        Animation.cancel_all(self, "excite")

    def cheer(self):
        """Gol: tribün çıldırır, sonra yavaşça sakinleşir."""
        Animation.cancel_all(self, "excite")
        (Animation(excite=1.0, d=0.25) + Animation(excite=1.0, d=2.8) +
         Animation(excite=0.35, d=2.0)).start(self)

    def groan(self):
        """Kurtarış / kaçan şut: kısa süreli hayal kırıklığı."""
        Animation.cancel_all(self, "excite")
        (Animation(excite=0.08, d=0.3) + Animation(excite=0.08, d=1.2) +
         Animation(excite=0.35, d=1.5)).start(self)

    # -- çizim ---------------------------------------------------------------
    def _rebuild(self, *a):
        x, y, w, h = self.x, self.y, self.width, self.height
        self.canvas.clear()
        self._blocks, self._flags, self._flashes = [], [], []
        if w <= 0 or h <= 0:
            return
        rnd = random.Random(self._seed)            # her çizimde aynı kalabalık
        fs = max(dp(22), w / 38.0)                 # taraftar boyu
        ad_h = max(dp(14), h * 0.075)              # reklam panosu şeridi
        rows = max(5, int((h - ad_h) / (fs * 0.72)))
        step = (h - ad_h) / float(rows)
        cols = int(w / (fs * 0.80)) + 3
        BLOCK = 3

        with self.canvas:
            # tribün zemini
            Color(0.03, 0.05, 0.10, 1)
            Rectangle(pos=(x, y), size=(w, h))
            # üstte projektör ışığı hissi
            for fx in (0.18, 0.5, 0.82):
                Color(1, 0.97, 0.85, 0.07)
                Ellipse(pos=(x + w * fx - w * 0.14, y + h * 0.80), size=(w * 0.28, h * 0.45))

            # arka sıradan öne doğru çiz (öndekiler arkadakileri örter)
            for r in range(rows):
                depth = r / float(max(1, rows - 1))        # 0 = en arka, 1 = ön
                light = 0.50 + 0.50 * depth
                base_y = y + ad_h + (rows - 1 - r) * step
                # basamak çizgisi
                Color(0.10, 0.13, 0.22, 1)
                Rectangle(pos=(x, base_y - step * 0.12), size=(w, step * 0.18))
                stagger = (fs * 0.40) if r % 2 else 0
                size_f = fs * (0.86 + 0.18 * depth)
                c = 0
                while c < cols:
                    PushMatrix()
                    tr = Translate(0, 0)
                    first_col = c
                    for _ in range(BLOCK):
                        if c >= cols:
                            break
                        fx = x + c * fs * 0.80 - fs * 0.4 + stagger + rnd.uniform(-fs * 0.06, fs * 0.06)
                        sec = fx / float(w)
                        roll = rnd.random()
                        if roll < 0.70:
                            pal = _HOME if sec < 0.5 else _AWAY
                        elif roll < 0.82:
                            pal = _AWAY if sec < 0.5 else _HOME
                        else:
                            pal = _MIX
                        shirt = _shade(rnd.choice(pal), light)
                        skin = _shade(rnd.choice(_CROWD_SKINS), light)
                        hair = _shade(rnd.choice(_CROWD_HAIRS), light)
                        fy = base_y + rnd.uniform(0, step * 0.10)
                        bw, bh = size_f * 0.74, size_f * 0.62
                        arms_up = rnd.random() < 0.38
                        scarf = arms_up and rnd.random() < 0.28
                        if arms_up:
                            Color(*skin)
                            aw = size_f * 0.11
                            ah = size_f * 0.62
                            Rectangle(pos=(fx - aw * 0.4, fy + bh * 0.45), size=(aw, ah))
                            Rectangle(pos=(fx + bw - aw * 0.6, fy + bh * 0.45), size=(aw, ah))
                        if scarf:
                            Color(*_shade(rnd.choice(_HOME + _AWAY), light))
                            Rectangle(pos=(fx - size_f * 0.12, fy + bh * 0.45 + size_f * 0.60),
                                      size=(bw + size_f * 0.24, size_f * 0.13))
                        Color(*shirt)
                        RoundedRectangle(pos=(fx, fy), size=(bw, bh), radius=[size_f * 0.2])
                        Color(*skin)
                        hs = size_f * 0.44
                        hx = fx + (bw - hs) / 2.0
                        hy = fy + bh - hs * 0.12
                        Ellipse(pos=(hx, hy), size=(hs, hs * 1.08))
                        Color(*hair)
                        Ellipse(pos=(hx - hs * 0.02, hy + hs * 0.55), size=(hs * 1.04, hs * 0.58))
                        c += 1
                    PopMatrix()
                    self._blocks.append([tr, rnd.uniform(0, 6.28), rnd.uniform(3.2, 6.5),
                                         first_col / float(cols)])

            # sallanan bayraklar
            for i in range(7):
                fx = x + w * (0.06 + 0.88 * (i + rnd.uniform(0, 0.6)) / 7.0)
                fy = y + ad_h + h * rnd.uniform(0.10, 0.45)
                pole = fs * 1.5
                PushMatrix()
                rot = Rotate(angle=0, origin=(fx, fy))
                Color(0.85, 0.85, 0.85, 1)
                Line(points=[fx, fy, fx, fy + pole], width=dp(1.4))
                Color(*rnd.choice(_HOME + _AWAY))
                Rectangle(pos=(fx, fy + pole * 0.55), size=(pole * 0.75, pole * 0.45))
                PopMatrix()
                self._flags.append([rot, rnd.uniform(0, 6.28)])

            # reklam panoları
            Color(0.02, 0.03, 0.06, 1)
            Rectangle(pos=(x, y), size=(w, ad_h))
            seg = max(dp(60), w / 12.0)
            n = int(w / seg) + 1
            for i in range(n):
                Color(*_ADS[i % len(_ADS)])
                Rectangle(pos=(x + i * seg + dp(3), y + ad_h * 0.15),
                          size=(seg - dp(6), ad_h * 0.70))
            Color(1, 1, 1, 0.35)
            Rectangle(pos=(x, y + ad_h - dp(1.5)), size=(w, dp(1.5)))

            # kamera flaşları (ömürleri kısa, rastgele yanar)
            for _ in range(16):
                fx = x + rnd.uniform(0.03, 0.97) * w
                fy = y + ad_h + rnd.uniform(0.05, 0.92) * (h - ad_h)
                col = Color(1, 1, 0.9, 0)
                el = Ellipse(pos=(fx - dp(4), fy - dp(4)), size=(dp(8), dp(8)))
                self._flashes.append([col, el])

    # -- animasyon -----------------------------------------------------------
    def _tick(self, dt):
        self._t += dt
        t = self._t
        amp = (0.15 + 1.0 * self.excite) * max(dp(3), self.height * 0.018)
        wave = 1.0 if self.excite < 0.6 else 1.6
        for blk in self._blocks:
            tr, ph, sp_, col = blk
            s = math.sin(t * sp_ * (0.7 + self.excite * 0.9) + ph + col * 5.0 * wave)
            tr.y = amp * (s if s > 0 else s * 0.15)      # yukarı zıpla, aşağıda bekle
        for fl in self._flags:
            fl[0].angle = math.sin(t * 2.4 + fl[1]) * (6 + 10 * self.excite)
        for col, el in self._flashes:
            if col.a > 0.02:
                col.a *= 0.55
            elif random.random() < 0.012 + 0.03 * self.excite:
                col.a = 1.0


# ============================================================================
# BÖLÜM: quiz_system
# ============================================================================
"""Futbolcu tahmin oyunu: mod seçimi, soru motoru, oyun ekranı, 25'lik seri ödülü."""
import random
from collections import deque, namedtuple

from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout

from kivy.app import App

STREAK_GOAL = 25
JOKERS_PER_GAME = 3
Question = namedtuple("Question", "player options correct")


class QuizEngine:
    """Soru üretir: havuzlar ayrı, yakın zamanda sorulanlar tekrarlanmaz."""

    def __init__(self, mode):
        self.mode = mode
        self.pool = EASY_POOL if mode == "easy" else HARD_POOL
        self.points = 1 if mode == "easy" else 2
        self.recent = deque(maxlen=min(15, max(1, len(self.pool) // 2)))

    def next_question(self):
        candidates = [p for p in self.pool if p.slug not in self.recent]
        if not candidates:
            candidates = list(self.pool)
        target = random.choice(candidates)
        self.recent.append(target.slug)
        others = [p for p in self.pool if p.name != target.name]
        options = random.sample(others, 3) + [target]
        random.shuffle(options)
        return Question(target, [o.name for o in options], options.index(target))


# ----------------------------------------------------------------------------
class QuizModeScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical", padding=[dp(40), dp(70), dp(40), dp(24)],
                         spacing=dp(16))
        root.add_widget(TLabel(text="MOD SEÇ", halign="center", bold=True,
                               font_size=sp(30), size_hint_y=None, height=dp(44)))
        row = BoxLayout(orientation="horizontal", spacing=dp(22))
        easy = RoundedButton(
            text="KOLAY MOD\n[size=%d]Popüler yıldızlar  •  Doğru cevap +1 puan[/size]" % int(sp(14)),
            markup=True, bg=GREEN, font_size=sp(26))
        hard = RoundedButton(
            text="ZOR MOD\n[size=%d]Efsaneler ve az bilinenler  •  Doğru cevap +2 puan[/size]" % int(sp(14)),
            markup=True, bg=GOLD_DARK, font_size=sp(26))
        easy.bind(on_release=lambda *a: self.start("easy"))
        hard.bind(on_release=lambda *a: self.start("hard"))
        row.add_widget(easy)
        row.add_widget(hard)
        root.add_widget(row)
        back = RoundedButton(text="GERİ", bg=NAVY_LIGHT, size_hint=(None, None),
                             size=(dp(160), dp(48)), pos_hint={"center_x": 0.5})
        back.bind(on_release=lambda *a: goto("menu"))
        root.add_widget(back)
        self.add_widget(root)

    def start(self, mode):
        quiz = App.get_running_app().sm.get_screen("quiz")
        quiz.start(mode)
        goto("quiz")


# ----------------------------------------------------------------------------
class QuizScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.engine = None
        self.queue = []
        self.current = None
        self.locked = True
        self.streak = 0
        self._token = 0
        self._ready_token = -1
        self._events = []
        self.overlay = None
        self.jokers = JOKERS_PER_GAME
        self.joker_used_q = False

        root = BoxLayout(orientation="horizontal",
                         padding=[dp(18), dp(70), dp(18), dp(14)], spacing=dp(18))
        self.photo = PlayerPhoto(size_hint_x=0.46)
        right = BoxLayout(orientation="vertical", spacing=dp(8))

        top = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(30))
        self.mode_lbl = TLabel(text="", bold=True, font_size=sp(16), color=GOLD)
        self.streak_lbl = TLabel(text="SERİ 0/25", bold=True, font_size=sp(16),
                                 halign="right")
        top.add_widget(self.mode_lbl)
        top.add_widget(self.streak_lbl)
        self.bar = BarWidget(maximum=STREAK_GOAL, size_hint_y=None, height=dp(10))
        right.add_widget(top)
        right.add_widget(self.bar)
        right.add_widget(TLabel(text="Bu futbolcu kim?", bold=True, font_size=sp(21),
                                size_hint_y=None, height=dp(36)))
        self.buttons = []
        for i in range(4):
            b = RoundedButton(text="", bg=NAVY_LIGHT, font_size=sp(18))
            b.bind(on_release=lambda inst, i=i: self.answer(i))
            self.buttons.append(b)
            right.add_widget(b)
        self.msg = TLabel(text="", halign="center", bold=True, font_size=sp(16),
                          size_hint_y=None, height=dp(28))
        right.add_widget(self.msg)
        root.add_widget(self.photo)
        root.add_widget(right)
        self.add_widget(root)

        topright = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint=(None, None),
                             size=(dp(270), dp(44)),
                             pos_hint={"right": 0.99, "top": 0.985})
        self.joker_btn = RoundedButton(text="", bg=GOLD_DARK, font_size=sp(15),
                                       size_hint=(None, 1), width=dp(160))
        self.joker_btn.bind(on_release=lambda *a: self.use_joker())
        back = RoundedButton(text="GERİ", bg=NAVY_LIGHT, size_hint=(None, 1), width=dp(100))
        back.bind(on_release=lambda *a: self.on_back())
        topright.add_widget(self.joker_btn)
        topright.add_widget(back)
        self.add_widget(topright)
        self._update_joker()

    # -- joker ---------------------------------------------------------
    def _update_joker(self):
        self.joker_btn.text = "JOKER  x%d" % self.jokers
        self.joker_btn.bg = list(GOLD_DARK if self.jokers > 0 else (0.35, 0.40, 0.50, 1))

    def use_joker(self):
        """İpucu: yanlış iki şıkkı eler. Oyun başına 3 hak, soru başına 1 kullanım."""
        if self.locked or not self.current:
            return
        if self.jokers <= 0:
            toast(self, "Bu oyunda joker hakkın kalmadı", RED, 1.4)
            return
        if self.joker_used_q:
            toast(self, "Bu soruda zaten joker kullandın", RED, 1.4)
            return
        wrong = [i for i in range(4) if i != self.current.correct]
        for i in random.sample(wrong, 2):
            self.buttons[i].disabled = True
            self.buttons[i].opacity = 0.28
        self.jokers -= 1
        self.joker_used_q = True
        self._update_joker()
        self.msg.text = "JOKER: 2 yanlış şık elendi  •  Kalan: %d" % self.jokers
        self.msg.color = GOLD
        play_sound("buy")

    # -- yardımcılar ---------------------------------------------------
    def _schedule(self, delay, fn):
        ev = Clock.schedule_once(fn, delay)
        self._events.append(ev)
        return ev

    def _cancel_events(self):
        for ev in self._events:
            ev.cancel()
        self._events = []

    def _update_streak(self):
        self.streak_lbl.text = "SERİ %d/%d" % (self.streak, STREAK_GOAL)
        self.bar.value = self.streak

    # -- oyun akışı ----------------------------------------------------
    def start(self, mode):
        self._cancel_events()
        if self.overlay:
            self.overlay.dismiss()
            self.overlay = None
        save.begin_game()
        self.engine = QuizEngine(mode)
        self.queue = []
        self.streak = 0
        self.jokers = JOKERS_PER_GAME
        self._update_joker()
        self.mode_lbl.text = "KOLAY MOD  •  +1" if mode == "easy" else "ZOR MOD  •  +2"
        self._update_streak()
        self._fill_queue()
        self._show_next()

    def _fill_queue(self):
        while len(self.queue) < 2:
            q = self.engine.next_question()
            self.queue.append(q)
            p = q.player
            photos.request(p.slug, p.wiki, lambda path: None, p.name)   # önceden yükle

    def _show_next(self, *a):
        if not self.engine:
            return
        self.current = self.queue.pop(0)
        self._fill_queue()
        self._token += 1
        tok = self._token
        self.locked = True
        self.joker_used_q = False
        for i, b in enumerate(self.buttons):
            b.text = self.current.options[i]
            b.bg = list(NAVY_LIGHT)
            b.opacity = 1
            b.disabled = True
        self.msg.text = ""
        self.photo.show_loading()
        p = self.current.player
        photos.request(p.slug, p.wiki, lambda path, tok=tok: self._photo_done(tok, path), p.name)
        self._schedule(8.0, lambda dt, tok=tok: self._photo_done(tok, None))

    def _photo_done(self, tok, path):
        if tok != self._token or self._ready_token == tok:
            return
        self._ready_token = tok
        if path:
            self.photo.show_image(path)
        else:
            self.photo.show_default("Fotoğraf bulunamadı")
        for b in self.buttons:
            b.disabled = False
        self.locked = False

    def answer(self, i):
        if self.locked or not self.current:
            return
        self.locked = True                       # çift puan eklenmesini engeller
        q = self.current
        ok = (i == q.correct)
        self.buttons[q.correct].bg = list(GREEN)
        if ok:
            self.streak += 1
            save.record_answer(True, self.engine.points, self.streak, self.engine.mode)
            self.msg.text = "DOĞRU!  +%d PUAN" % self.engine.points
            self.msg.color = GREEN
            play_sound("correct")
        else:
            self.buttons[i].bg = list(RED)
            save.record_answer(False, 0, 0, self.engine.mode)
            self.streak = 0
            self.msg.text = "YANLIŞ  •  Doğru cevap: %s" % q.options[q.correct]
            self.msg.color = RED
            play_sound("wrong")
        self._update_streak()
        if ok and self.streak >= STREAK_GOAL:
            save.grant_special_right()
            self._schedule(0.9, self._celebrate)
        else:
            self._schedule(1.0 if ok else 2.2, self._show_next)

    def _celebrate(self, *a):
        play_sound("goal")
        self.overlay = Overlay(
            "25 DOĞRU CEVAP!",
            "Tebrikler! Avatarın özel penaltı hakkı kazandı.\nÖzel penaltıda gol = +25 puan",
            [("DEVAM ET", self._continue, GREEN_DARK),
             ("PENALTIYA GİT", self._to_penalty, GOLD_DARK)],
            title_color=GOLD)
        self.overlay.show(self)

    def _continue(self):
        if self.overlay:
            self.overlay.dismiss()
            self.overlay = None
        self.streak = 0
        self._update_streak()
        self._show_next()

    def _to_penalty(self):
        if self.overlay:
            self.overlay.dismiss()
            self.overlay = None
        self.streak = 0
        pen = App.get_running_app().sm.get_screen("penalty")
        pen.start_special = True
        goto("penalty")

    def on_leave(self, *a):
        self._cancel_events()
        self._token += 1
        if self.overlay:
            self.overlay.dismiss()
            self.overlay = None

    def on_back(self):
        goto("mode")


# ============================================================================
# BÖLÜM: shop_system
# ============================================================================
"""Futbolcu mağazası: satın alma ve avatar seçimi."""
from kivy.clock import Clock
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window



class ShopCard(BoxLayout):
    def __init__(self, player, on_action, **kw):
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(128),
                         padding=dp(10), spacing=dp(10), **kw)
        self.player = player
        self.on_action = on_action
        with self.canvas.before:
            Color(0, 0, 0, 0.3)
            self._sh = RoundedRectangle(radius=[dp(16)])
            Color(0.07, 0.14, 0.30, 1)
            self._bg = RoundedRectangle(radius=[dp(16)])
            self._bc = Color(1, 1, 1, 0.12)
            self._bd = Line(rounded_rectangle=(0, 0, 1, 1, dp(16)), width=dp(1.8))
        self.bind(pos=self._upd, size=self._upd)

        self.avatar = FaceAvatar(player.id, lazy=True, size_hint=(None, 1), width=dp(92))
        info = BoxLayout(orientation="vertical", spacing=dp(2))
        self.name_lbl = TLabel(text=player.name, bold=True, font_size=sp(15),
                               shorten=True, shorten_from="right", size_hint_y=0.25)
        prow = BoxLayout(orientation="horizontal", spacing=dp(6), size_hint_y=0.2)
        prow.add_widget(TLabel(text="GÜÇ %d" % player.power, font_size=sp(13), bold=True,
                               color=GOLD, size_hint_x=None, width=dp(62)))
        bar = BarWidget(value=player.power, maximum=100, fill=GREEN, size_hint_y=None,
                        height=dp(8), pos_hint={"center_y": 0.5})
        prow.add_widget(bar)
        self.price_lbl = TLabel(text="", font_size=sp(13), bold=True, size_hint_y=0.2)
        self.btn = RoundedButton(text="", font_size=sp(14), size_hint_y=0.35)
        self.btn.bind(on_release=lambda *a: self.on_action(self))
        info.add_widget(self.name_lbl)
        info.add_widget(prow)
        info.add_widget(self.price_lbl)
        info.add_widget(self.btn)
        self.add_widget(self.avatar)
        self.add_widget(info)
        self.refresh()

    def _upd(self, *a):
        self._sh.pos = (self.x, self.y - dp(3))
        self._sh.size = self.size
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._bd.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(16))

    def sync_starter(self):
        """Başlangıç kartı, açılışta seçilen futbolcuyu göstersin."""
        if self.player.id != "starter":
            return
        p = get_player("starter")
        if p.name != self.player.name:
            self.player = p
            self.name_lbl.text = p.name
            self.avatar.set_player("starter", lazy=True)

    def refresh(self):
        p = self.player
        owned = save.owns(p.id)
        selected = save.selected_avatar == p.id
        if owned:
            self.price_lbl.text = "SAHİPLENİLDİ"
            self.price_lbl.color = GREEN
            if selected:
                self.btn.text = "SEÇİLİ"
                self.btn.bg = list(GREEN_DARK)
            else:
                self.btn.text = "SEÇ"
                self.btn.bg = list(GREEN)
        else:
            self.price_lbl.text = "FİYAT: %d PUAN" % p.price
            self.price_lbl.color = GOLD
            self.btn.text = "SATIN AL"
            self.btn.bg = list(GOLD_DARK if save.points >= p.price else GREY)
        self._bc.rgba = (GREEN[0], GREEN[1], GREEN[2], 1) if selected else (1, 1, 1, 0.12)


class ShopScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical", padding=[dp(14), dp(66), dp(14), dp(8)],
                         spacing=dp(6))
        self.scroll = ScrollView(do_scroll_x=False, bar_width=dp(4))
        self.grid = GridLayout(cols=3, spacing=dp(12), padding=[0, 0, 0, dp(10)],
                               size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter("height"))
        self.cards = []
        for p in SHOP_PLAYERS:
            c = ShopCard(p, self._action)
            self.cards.append(c)
            self.grid.add_widget(c)
        self.scroll.add_widget(self.grid)
        root.add_widget(self.scroll)
        self.add_widget(root)

        from kivy.uix.label import Label
        title = Label(text="MAĞAZA", bold=True, font_size=sp(26), size_hint=(None, None),
                      size=(dp(200), dp(46)), pos_hint={"center_x": 0.5, "top": 0.985})
        self.add_widget(title)
        back = RoundedButton(text="GERİ", bg=NAVY_LIGHT, size_hint=(None, None),
                             size=(dp(100), dp(44)), pos_hint={"right": 0.99, "top": 0.985})
        back.bind(on_release=lambda *a: goto("menu"))
        self.add_widget(back)

    def on_pre_enter(self, *a):
        for c in self.cards:
            c.sync_starter()
        self.grid.cols = max(2, min(4, int(Window.width / dp(330))))
        self.refresh_all()
        save.subscribe(self.refresh_all)
        self._lazy_ev = Clock.schedule_interval(self._load_visible, 0.35)

    def on_leave(self, *a):
        save.unsubscribe(self.refresh_all)
        ev = getattr(self, "_lazy_ev", None)
        if ev:
            ev.cancel()
            self._lazy_ev = None

    def _load_visible(self, dt):
        """Ekranda (veya hemen altında/üstünde) görünen kartların yüzünü yükle.
        Her turda en fazla 8 kart; görünürlük ScrollView'in kendi alanına göre ölçülür."""
        sc = self.scroll
        margin = dp(300)
        lo, hi = sc.y - margin, sc.top + margin
        started = 0
        for c in self.cards:
            if started >= 8:
                break
            if c.avatar._loaded or not c.player.wiki:
                continue
            if c.top >= lo and c.y <= hi:
                c.avatar.ensure_loaded()
                started += 1

    def refresh_all(self, *a):
        for c in self.cards:
            c.refresh()

    def _action(self, card):
        p = card.player
        if save.owns(p.id):
            if save.selected_avatar == p.id:
                return
            save.select_avatar(p.id)
            toast(self, "Avatar seçildi: %s" % p.name)
            return
        ok, why = save.buy_player(p.id, p.price)       # tek adımda puan düş + ekle
        if ok:
            play_sound("buy")
            toast(self, "Satın alındı: %s" % p.name, GREEN_DARK)
        elif why == "points":
            toast(self, "Yetersiz puan! Gereken: %d" % p.price, RED)
        else:
            toast(self, "Bu futbolcuya zaten sahipsin", GREY)

    def on_back(self):
        goto("menu")


# ============================================================================
# BÖLÜM: loading_screen
# ============================================================================
"""Açılış yükleme ekranı: tüm futbolcu fotoğrafları önceden indirilir, hepsi
bitince oyun açılır. "BEKLEMEDEN GEÇ" ile istenirse beklemeden girilebilir."""
from kivy.clock import Clock
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout



class Preloader:
    """Fotoğrafları en fazla 4'er 4'er indirir (geri kalan havuz oyun içi istekler için
    boş kalır). İnternet yoksa ilk denemelerden sonra bekletmeden bırakır."""
    MAX_ACTIVE = 4
    OFFLINE_STREAK = 6

    def __init__(self, items, on_progress, on_done):
        self.items = list(items)
        self.total = len(self.items)
        self.on_progress = on_progress
        self.on_done = on_done
        self.done = 0
        self.ok = 0
        self.fail_streak = 0
        self.idx = 0
        self.active = 0
        self.cancelled = False
        self.finished = False
        self.offline = False

    def start(self):
        if not self.items:
            self._finish()
            return
        self._pump()

    def cancel(self):
        self.cancelled = True            # sıradakiler indirilmez, yoldakiler biter

    def _pump(self):
        while (not self.cancelled and not self.finished and self.active < self.MAX_ACTIVE
               and self.idx < self.total):
            slug, wiki, name = self.items[self.idx]
            self.idx += 1
            self.active += 1
            photos.request(slug, wiki, self._cb, name)

    def _cb(self, path):
        self.active -= 1
        self.done += 1
        if path:
            self.ok += 1
            self.fail_streak = 0
        else:
            self.fail_streak += 1
        if self.cancelled or self.finished:
            return
        self.on_progress(self.done, self.total)
        if self.ok == 0 and self.fail_streak >= self.OFFLINE_STREAK:
            self.offline = True
            self._finish()
        elif self.done >= self.total:
            self._finish()
        else:
            self._pump()

    def _finish(self):
        if self.finished:
            return
        self.finished = True
        self.on_done(self.offline)


# ----------------------------------------------------------------------------
class LoadingScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.pre = None
        self._left = False
        self._dots = 0
        self._dot_ev = None

        card = BoxLayout(orientation="vertical", size_hint=(None, None),
                         size=(dp(560), dp(330)), spacing=dp(10), padding=dp(24),
                         pos_hint={"center_x": 0.5, "center_y": 0.5})
        with card.canvas.before:
            Color(0, 0, 0, 0.35)
            sh = RoundedRectangle(radius=[dp(26)])
            Color(*NAVY_LIGHT)
            bg = RoundedRectangle(radius=[dp(26)])
            Color(*GREEN)
            bd = Line(rounded_rectangle=(0, 0, 1, 1, dp(26)), width=dp(2))

        def upd(*a):
            sh.pos = (card.x, card.y - dp(4))
            sh.size = card.size
            bg.pos = card.pos
            bg.size = card.size
            bd.rounded_rectangle = (card.x, card.y, card.width, card.height, dp(26))
        card.bind(pos=upd, size=upd)

        card.add_widget(TLabel(text="FUTBOL ARENA", halign="center", bold=True,
                               font_size=sp(32), color=GREEN, size_hint_y=None, height=dp(48)))
        self.status = TLabel(text="Futbolcu fotoğrafları yükleniyor", halign="center",
                             font_size=sp(17), color=(1, 1, 1, 0.9),
                             size_hint_y=None, height=dp(32))
        card.add_widget(self.status)
        self.bar = BarWidget(maximum=1, size_hint=(0.9, None), height=dp(14),
                             pos_hint={"center_x": 0.5})
        card.add_widget(self.bar)
        self.count = TLabel(text="", halign="center", bold=True, font_size=sp(18),
                            size_hint_y=None, height=dp(30))
        card.add_widget(self.count)
        card.add_widget(TLabel(text="Hepsi inince oyun açılır. Beklemek istemezsen aşağıdaki "
                                    "butonla geçebilirsin.", halign="center",
                               font_size=sp(13), color=(1, 1, 1, 0.6)))
        skip = RoundedButton(text="BEKLEMEDEN GEÇ", bg=GOLD_DARK, font_size=sp(18),
                             size_hint_y=None, height=dp(54))
        skip.bind(on_release=lambda *a: self.skip())
        card.add_widget(skip)
        self.add_widget(card)

    # -- akış ----------------------------------------------------------------
    def begin(self, items):
        self._left = False
        self.bar.maximum = max(1, len(items))
        self.bar.value = 0
        self.count.text = "0 / %d" % len(items)
        self._dot_ev = Clock.schedule_interval(self._animate_dots, 0.5)
        self.pre = Preloader(items, self._progress, self._done)
        self.pre.start()

    def _animate_dots(self, dt):
        self._dots = (self._dots + 1) % 4
        if not self.status.text.startswith("İnternet"):
            self.status.text = "Futbolcu fotoğrafları yükleniyor" + "." * self._dots

    def _progress(self, done, total):
        self.bar.maximum = max(1, total)
        self.bar.value = done
        self.count.text = "%d / %d" % (done, total)

    def _done(self, offline):
        if offline:
            self.status.text = "İnternet yok gibi görünüyor, fotoğraflar sonra yüklenecek"
            Clock.schedule_once(lambda dt: self._proceed(), 1.8)
        else:
            self.bar.value = self.bar.maximum
            Clock.schedule_once(lambda dt: self._proceed(), 0.35)

    def skip(self):
        if self.pre:
            self.pre.cancel()
        self._proceed()

    def _proceed(self):
        if self._left:
            return
        self._left = True
        if self._dot_ev:
            self._dot_ev.cancel()
            self._dot_ev = None
        goto(start_screen())

    def on_back(self):
        self.skip()


# ============================================================================
# BÖLÜM: penalty_system
# ============================================================================
"""Penaltı modu: 2D sahne, parmakla şut yönü, Buffon kaleci, güç tabanlı gol ihtimali."""
import math
import os
import random

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import (Color, Ellipse, Line, PopMatrix, PushMatrix, Rectangle,
                           Rotate, RoundedRectangle)
from kivy.metrics import dp, sp
from kivy.properties import NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.widget import Widget


# Kale içi bölgeler: (x oranı, y oranı)
ZONES = {"TL": (0.17, 0.74), "BL": (0.17, 0.26), "TR": (0.83, 0.74),
         "BR": (0.83, 0.26), "C": (0.5, 0.5)}
ZONE_LIST = list(ZONES)


# ----------------------------------------------------------------------------
class BallWidget(Widget):
    def __init__(self, **kw):
        super().__init__(size_hint=(None, None), **kw)
        self.bind(pos=self._d, size=self._d)

    def _d(self, *a):
        self.canvas.clear()
        s = self.width
        if s <= 0:
            return
        x, y = self.pos
        with self.canvas:
            Color(1, 1, 1, 1)
            Ellipse(pos=(x, y), size=(s, s))
            Color(0.08, 0.08, 0.10, 1)
            Ellipse(pos=(x + s * 0.35, y + s * 0.35), size=(s * 0.30, s * 0.30))
            for ang in range(5):
                a = math.radians(90 + ang * 72)
                px = x + s / 2 + math.cos(a) * s * 0.40
                py = y + s / 2 + math.sin(a) * s * 0.40
                Ellipse(pos=(px - s * 0.08, py - s * 0.08), size=(s * 0.16, s * 0.16))
            Color(0, 0, 0, 0.3)
            Line(circle=(x + s / 2, y + s / 2, s / 2), width=dp(1))


class KeeperWidget(Widget):
    """Buffon. assets/goalkeeper/buffon.png varsa o kullanılır, yoksa çizilir."""
    angle = NumericProperty(0)

    def __init__(self, **kw):
        super().__init__(size_hint=(None, None), **kw)
        self.img = None
        path = asset_path("goalkeeper", "buffon.png")
        if os.path.isfile(path):
            try:
                self.img = Image(source=path, size_hint=(None, None))
                try:
                    self.img.fit_mode = "contain"
                except Exception:
                    self.img.allow_stretch = True
                    self.img.keep_ratio = True
                self.add_widget(self.img)
            except Exception:
                self.img = None
        if self.img is None:
            self.num = Label(text="1", bold=True, color=(0.05, 0.05, 0.05, 1),
                             size_hint=(None, None), size=(dp(30), dp(30)))
            self.add_widget(self.num)
        with self.canvas.after:
            PopMatrix()
        self.bind(pos=self._d, size=self._d, angle=self._d)

    def _d(self, *a):
        x, y, w, h = self.x, self.y, self.width, self.height
        if w <= 0 or h <= 0:
            return
        cx = self.center_x
        c = self.canvas.before
        c.clear()
        with c:
            PushMatrix()
            Rotate(angle=self.angle, origin=self.center)
            if self.img is None:
                Color(0, 0, 0, 0.3)
                Ellipse(pos=(cx - 0.3 * w, y - 0.02 * h), size=(0.6 * w, 0.06 * h))
                Color(0.06, 0.06, 0.08, 1)
                Line(points=[cx - 0.10 * w, y + 0.38 * h, cx - 0.20 * w, y + 0.04 * h], width=dp(7))
                Line(points=[cx + 0.10 * w, y + 0.38 * h, cx + 0.20 * w, y + 0.04 * h], width=dp(7))
                RoundedRectangle(pos=(cx - 0.18 * w, y + 0.33 * h), size=(0.36 * w, 0.16 * h),
                                 radius=[dp(5)])
                Color(0.98, 0.80, 0.12, 1)
                Line(points=[cx - 0.17 * w, y + 0.70 * h, x + 0.06 * w, y + 0.86 * h], width=dp(8))
                Line(points=[cx + 0.17 * w, y + 0.70 * h, x + 0.94 * w, y + 0.86 * h], width=dp(8))
                RoundedRectangle(pos=(cx - 0.20 * w, y + 0.46 * h), size=(0.40 * w, 0.28 * h),
                                 radius=[dp(10)])
                Color(0.25, 1.0, 0.45, 1)
                g = 0.075 * w
                Ellipse(pos=(x + 0.06 * w - g, y + 0.86 * h - g), size=(2 * g, 2 * g))
                Ellipse(pos=(x + 0.94 * w - g, y + 0.86 * h - g), size=(2 * g, 2 * g))
                Color(0.96, 0.80, 0.66, 1)
                Ellipse(pos=(cx - 0.09 * w, y + 0.76 * h), size=(0.18 * w, 0.19 * h))
                Color(0.12, 0.09, 0.07, 1)
                Ellipse(pos=(cx - 0.095 * w, y + 0.86 * h), size=(0.19 * w, 0.09 * h))
        if self.img is None:
            self.num.font_size = max(sp(8), h * 0.13)
            self.num.center = (cx, y + 0.60 * h)
        else:
            self.img.size = self.size
            self.img.pos = self.pos


# ----------------------------------------------------------------------------
class PenaltyScene(Widget):
    trail_alpha = NumericProperty(0)
    drag_alpha = NumericProperty(0)
    flash_alpha = NumericProperty(0)

    def __init__(self, on_result, on_invalid, on_shot_start, **kw):
        super().__init__(**kw)
        self.on_result = on_result
        self.on_invalid = on_invalid
        self.on_shot_start = on_shot_start
        self.state = "ready"
        self.keeper_zone = "C"
        self.power = 10
        self.gx = self.gy = self.gw = self.gh = 0.0
        self.ball_start = (0, 0)
        self.ball_size = dp(30)
        self._events = []
        self._start_touch = None

        self.crowd = CrowdWidget()
        self.goal_layer = Widget()
        self.keeper = KeeperWidget()
        self.ball = BallWidget()
        self.taker = AvatarWidget("starter")
        self.add_widget(self.crowd)          # en arkada hareketli tribün
        self.add_widget(self.goal_layer)     # kale çerçevesi + ağ (tribünün önünde)
        self.add_widget(self.keeper)
        self.add_widget(self.ball)
        self.add_widget(self.taker)

        with self.canvas.after:
            self._flash_c = Color(0.3, 1, 0.5, 0)
            self._flash_r = Rectangle(pos=(0, 0), size=(0, 0))
            self._trail_c = Color(0.35, 0.9, 1, 0)
            self._trail_l = Line(points=[0, 0, 0, 0], width=dp(3), dash_length=dp(9),
                                 dash_offset=dp(6))
            self._drag_c = Color(0.35, 0.9, 1, 0)
            self._drag_l = Line(points=[0, 0, 0, 0], width=dp(4))
        self.bind(pos=self._relayout, size=self._relayout)

    # -- özellik tepkileri ------------------------------------------------
    def on_trail_alpha(self, inst, v):
        self._trail_c.a = v

    def on_drag_alpha(self, inst, v):
        self._drag_c.a = v

    def on_flash_alpha(self, inst, v):
        self._flash_c.a = v

    # -- geometri / çizim -------------------------------------------------
    def setup(self, player):
        self.power = player.power
        self.taker.set_player(player.id)

    def _relayout(self, *a):
        x, y, w, h = self.x, self.y, self.width, self.height
        if w <= 0 or h <= 0:
            return
        self.gw = w * 0.42
        self.gh = h * 0.30
        self.gx = x + (w - self.gw) / 2.0
        self.gy = y + h * 0.50
        self.ball_size = max(dp(26), h * 0.055)
        self.ball_start = (x + w * 0.5, y + h * 0.17)
        self._flash_r.pos = (self.gx, self.gy)
        self._flash_r.size = (self.gw, self.gh)
        self._draw_scenery()
        if self.state == "ready":
            self._place_children()

    def _draw_scenery(self):
        x, y, w, h = self.x, self.y, self.width, self.height
        gx, gy, gw, gh = self.gx, self.gy, self.gw, self.gh
        horizon = gy + gh * 0.06
        # hareketli tribün: ufuktan ekranın üstüne kadar
        self.crowd.pos = (x, horizon)
        self.crowd.size = (w, max(0, y + h - horizon))
        c = self.canvas.before
        c.clear()
        with c:
            Color(1, 1, 1, 1)
            Rectangle(texture=gradient_texture((0.13, 0.25, 0.50), (0.03, 0.07, 0.18)),
                      pos=(x, y), size=(w, h))
            # çim şeritleri
            bands = 8
            gh_total = horizon - y
            for i in range(bands):
                shade = 0.50 if i % 2 == 0 else 0.44
                Color(0.05, shade * 0.62, 0.20, 1)
                Rectangle(pos=(x, y + gh_total * i / bands),
                          size=(w, gh_total / bands + 1))
            # çizgiler
            Color(1, 1, 1, 0.55)
            Line(points=[x, gy, x + w, gy], width=dp(2))
            Line(points=[gx - gw * 0.12, gy, x + w * 0.26, y + h * 0.30,
                         x + w * 0.74, y + h * 0.30, gx + gw * 1.12, gy], width=dp(2))
            Color(1, 1, 1, 0.9)
            sx, sy = self.ball_start
            Ellipse(pos=(sx - dp(7), sy - self.ball_size * 0.55), size=(dp(14), dp(7)))
        # kale arkası + ağ + direkler (tribünün ÜSTÜNDE görünsün diye ayrı katman)
        g = self.goal_layer.canvas
        g.clear()
        with g:
            Color(0, 0, 0, 0.38)
            Rectangle(pos=(gx, gy), size=(gw, gh))
            Color(1, 1, 1, 0.20)
            cols, rows = 16, 8
            for i in range(1, cols):
                Line(points=[gx + gw * i / cols, gy, gx + gw * i / cols, gy + gh], width=dp(1))
            for j in range(1, rows):
                Line(points=[gx, gy + gh * j / rows, gx + gw, gy + gh * j / rows], width=dp(1))
            Color(1, 1, 1, 1)
            Line(points=[gx, gy, gx, gy + gh, gx + gw, gy + gh, gx + gw, gy], width=dp(4.5))

    def _place_children(self):
        kh = self.gh * 0.92
        self.keeper.size = (self.gh * 0.80, kh)
        self.keeper.angle = 0
        self.keeper.center = (self.gx + self.gw / 2.0, self.gy + kh / 2.0)
        bs = self.ball_size
        self.ball.size = (bs, bs)
        self.ball.pos = (self.ball_start[0] - bs / 2.0, self.ball_start[1] - bs / 2.0)
        ah = self.height * 0.36
        self.taker.size = (ah * 0.6, ah)
        self.taker.pos = (self.ball_start[0] - self.width * 0.13 - ah * 0.3, self.y + self.height * 0.02)
        self.taker.bob = 0

    # -- yardımcılar ------------------------------------------------------
    def zone_point(self, zone):
        fx, fy = ZONES[zone]
        return self.gx + self.gw * fx, self.gy + self.gh * fy

    def classify(self, tx, ty):
        fx = (tx - self.gx) / self.gw
        fy = (ty - self.gy) / self.gh
        if abs(fx - 0.5) < 0.17 and abs(fy - 0.5) < 0.22:
            return "C"
        return ("T" if fy >= 0.5 else "B") + ("L" if fx < 0.5 else "R")

    def _later(self, delay, fn):
        ev = Clock.schedule_once(fn, delay)
        self._events.append(ev)

    def cancel_all(self):
        for ev in self._events:
            ev.cancel()
        self._events = []
        for w in (self.keeper, self.ball, self.taker, self):
            Animation.cancel_all(w)
        self.trail_alpha = 0
        self.drag_alpha = 0
        self.flash_alpha = 0

    def prepare_shot(self):
        """Yeni tur: kaleci şuttan ÖNCE rastgele bir bölge seçer."""
        self.cancel_all()
        self.state = "ready"
        self.keeper_zone = random.choice(ZONE_LIST)
        self._relayout()
        self._place_children()

    # -- dokunmatik -------------------------------------------------------
    def on_touch_down(self, touch):
        if self.state != "ready" or not self.collide_point(*touch.pos):
            return False
        touch.grab(self)
        self._start_touch = touch.pos
        self._drag_l.points = [touch.x, touch.y, touch.x, touch.y]
        self.drag_alpha = 0.9
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is self and self._start_touch:
            sx, sy = self._start_touch
            self._drag_l.points = [sx, sy, touch.x, touch.y]
            return True
        return False

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return False
        touch.ungrab(self)
        self.drag_alpha = 0
        if not self._start_touch:
            return True
        sx, sy = self._start_touch
        self._start_touch = None
        dx, dy = touch.x - sx, touch.y - sy
        length = math.hypot(dx, dy)
        if self.state != "ready":
            return True
        if length < dp(45) or dy < length * 0.2:
            self.on_invalid()
            return True
        self._shoot(dx / length, dy / length)
        return True

    # -- şut --------------------------------------------------------------
    def _shoot(self, ux, uy):
        self.state = "shooting"
        self.on_shot_start()
        bx, by = self.ball_start
        # Çizginin yönü boyunca, topun kale merkezine uzaklığı kadar gidilir
        dist = math.hypot(self.gx + self.gw / 2.0 - bx, self.gy + self.gh / 2.0 - by)
        tx = min(max(bx + ux * dist, self.gx + self.gw * 0.06), self.gx + self.gw * 0.94)
        ty = min(max(by + uy * dist, self.gy + self.gh * 0.08), self.gy + self.gh * 0.92)
        zone = self.classify(tx, ty)

        if zone == self.keeper_zone:
            outcome = "saved"
        elif random.random() < shot_success_chance(self.power):
            outcome = "goal"
        else:
            outcome = "miss"
            fx = (tx - self.gx) / self.gw
            fy = (ty - self.gy) / self.gh
            if fy > 0.62 or random.random() < 0.5:
                ty = self.gy + self.gh * 1.22               # üstten dışarı
            else:
                tx = self.gx - self.gw * 0.10 if fx < 0.5 else self.gx + self.gw * 1.10

        # şut yönü görseli (kesik çizgi iz)
        self._trail_l.points = [bx, by, tx, ty]
        self.trail_alpha = 0.9
        Animation(trail_alpha=0, d=1.0).start(self)

        # oyuncu sıçrama animasyonu
        (Animation(bob=1, d=0.12) + Animation(bob=0, d=0.18)).start(self.taker)

        # top
        es = self.ball_size * 0.62
        a = Animation(pos=(tx - es / 2.0, ty - es / 2.0), size=(es, es), d=0.55, t="out_quad")
        a.bind(on_complete=lambda *x: self._arrived(outcome, tx, ty))
        a.start(self.ball)

        # kaleci atlayışı
        self._later(0.12, lambda dt: self._dive())

    def _dive(self):
        zx, zy = self.zone_point(self.keeper_zone)
        z = self.keeper_zone
        if z == "C":
            ang = 0
        else:
            sign = 1 if z.endswith("L") else -1          # + = sola devrilir
            ang = sign * (52 if z.startswith("T") else 78)
        Animation(center_x=zx, center_y=zy, angle=ang, d=0.40, t="out_cubic").start(self.keeper)

    def _arrived(self, outcome, tx, ty):
        if outcome == "goal":
            self.flash_alpha = 0.40
            Animation(flash_alpha=0, d=0.6).start(self)
            Animation(y=ty - self.gh * 0.12, d=0.25, t="in_quad").start(self.ball)
        elif outcome == "saved":
            Animation(y=self.gy - self.gh * 0.05, d=0.3, t="in_quad").start(self.ball)
        self.state = "done"
        self._later(0.55, lambda dt: self.on_result(outcome))


# ----------------------------------------------------------------------------
class PenaltyScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(with_background=False, **kw)
        self.start_special = False
        self.special_mode = False
        self.player = get_player("starter")
        self.overlay = None
        self._auto = None
        self._shot_special = False

        self.scene = PenaltyScene(self._on_result, self._invalid, self._shot_started)
        self.add_widget(self.scene)

        self.mode_lbl = TLabel(text="", halign="center", bold=True, font_size=sp(17),
                               size_hint=(None, None), size=(dp(560), dp(34)),
                               pos_hint={"center_x": 0.5, "top": 0.985})
        self.info_lbl = TLabel(text="", font_size=sp(14), bold=True, size_hint=(None, None),
                               size=(dp(300), dp(52)), pos_hint={"x": 0.015, "y": 0.02})
        self.hint_lbl = TLabel(text="Topun üzerinden kaleye doğru parmağınla çizgi çiz",
                               halign="center", font_size=sp(15), color=(1, 1, 1, 0.9),
                               size_hint=(None, None), size=(dp(520), dp(30)),
                               pos_hint={"center_x": 0.5, "y": 0.012})
        box = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint=(None, None),
                        size=(dp(290), dp(44)), pos_hint={"right": 0.99, "top": 0.985})
        self.special_btn = RoundedButton(text="", bg=NAVY_LIGHT, font_size=sp(14),
                                         size_hint=(None, 1), width=dp(180))
        self.special_btn.bind(on_release=lambda *a: self._toggle_special())
        menu = RoundedButton(text="MENÜ", bg=NAVY_LIGHT, font_size=sp(15),
                             size_hint=(None, 1), width=dp(100))
        menu.bind(on_release=lambda *a: self._to_menu())
        box.add_widget(self.special_btn)
        box.add_widget(menu)
        for w in (self.mode_lbl, self.info_lbl, self.hint_lbl, box):
            self.add_widget(w)

    # -- yaşam döngüsü ----------------------------------------------------
    def on_pre_enter(self, *a):
        self.player = get_player(save.selected_avatar)
        self.scene.setup(self.player)
        self.special_mode = bool(self.start_special) and save.special_rights > 0
        self.start_special = False
        self.hint_lbl.opacity = 1
        self._refresh()
        self.scene.prepare_shot()
        self.scene.crowd.start()

    def on_leave(self, *a):
        self.scene.crowd.stop()
        if self._auto:
            self._auto.cancel()
            self._auto = None
        if self.overlay:
            self.overlay.dismiss()
            self.overlay = None
        self.scene.cancel_all()

    def on_back(self):
        self._to_menu()

    def _refresh(self):
        rights = save.special_rights
        if rights <= 0:
            self.special_mode = False
        if self.special_mode:
            self.mode_lbl.text = "ÖZEL PENALTI  •  GOL +25  •  KURTARIŞ -1 PUAN"
            self.mode_lbl.color = GOLD
        else:
            self.mode_lbl.text = "PENALTI  •  GOL +1  •  KURTARIŞ -1 PUAN"
            self.mode_lbl.color = (1, 1, 1, 1)
        self.special_btn.opacity = 1 if rights > 0 else 0
        self.special_btn.disabled = rights <= 0
        self.special_btn.text = "ÖZEL HAK x%d" % rights
        self.special_btn.bg = list(GOLD_DARK if self.special_mode else NAVY_LIGHT)
        chance = int(round(shot_success_chance(self.player.power) * 100))
        self.info_lbl.text = "%s\nGÜÇ %d  •  İsabet %%%d" % (self.player.name, self.player.power, chance)

    def _toggle_special(self):
        if self.scene.state != "ready" or save.special_rights <= 0:
            return
        self.special_mode = not self.special_mode
        self._refresh()

    # -- sahne geri çağrıları ---------------------------------------------
    def _invalid(self):
        toast(self, "Topun üzerinden yukarıya, kaleye doğru çizgi çiz", RED, 1.4)

    def _shot_started(self):
        self.hint_lbl.opacity = 0
        self._shot_special = self.special_mode and save.special_rights > 0

    def _on_result(self, outcome):
        if self.overlay:                      # puan ikinci kez eklenmesin
            return
        special = self._shot_special
        gained = save.record_penalty(outcome, special)
        if outcome == "goal":
            self.scene.crowd.cheer()
            play_sound("goal")
            if special and gained == 25:
                self.overlay = Overlay("TEBRİKLER! MUHTEŞEM BİR PENALTI! +25 PUAN", "",
                                       [("ANA MENÜ", self._to_menu, GOLD_DARK)],
                                       title_color=GOLD)
                self.overlay.show(self)
                self._auto = Clock.schedule_once(lambda dt: self._to_menu(), 4.0)
            else:
                self.overlay = Overlay("GOL!", "+1 PUAN",
                                       [("TEKRAR ŞUT", self._again, GREEN_DARK),
                                        ("ANA MENÜ", self._to_menu, NAVY_LIGHT)],
                                       title_color=GREEN)
                self.overlay.show(self)
        elif outcome == "saved":
            self.scene.crowd.groan()
            play_sound("save")
            sub = "Buffon doğru köşeyi seçti.  -1 PUAN" if gained < 0 else "Buffon doğru köşeyi seçti."
            if special:
                sub += "\nÖzel penaltı hakkın duruyor."
            self.overlay = Overlay("KURTARDI!", sub,
                                   [("TEKRAR DENE", self._again, GREEN_DARK),
                                    ("ANA MENÜ", self._to_menu, NAVY_LIGHT)],
                                   title_color=RED)
            self.overlay.show(self)
        else:
            self.scene.crowd.groan()
            play_sound("save")
            sub = "Şut isabetli çıkmadı."
            if special:
                sub += "\nÖzel penaltı hakkın duruyor."
            self.overlay = Overlay("ŞUT KAÇTI!", sub,
                                   [("TEKRAR DENE", self._again, GREEN_DARK),
                                    ("ANA MENÜ", self._to_menu, NAVY_LIGHT)],
                                   title_color=RED)
            self.overlay.show(self)

    def _again(self):
        if self.overlay:
            self.overlay.dismiss()
            self.overlay = None
        self._refresh()
        self.scene.prepare_shot()

    def _to_menu(self):
        if self._auto:
            self._auto.cancel()
            self._auto = None
        if self.overlay:
            self.overlay.dismiss()
            self.overlay = None
        goto("menu")


# ============================================================================
# ANA UYGULAMA
# ============================================================================
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.app import App
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import FadeTransition, ScreenManager
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget


Window.softinput_mode = "below_target"       # klavye açılınca giriş kutusu görünür kalsın
Window.clearcolor = NAVY_DARK


# ----------------------------------------------------------------------------
class UsernameScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        card = BoxLayout(orientation="vertical", size_hint=(None, None),
                         size=(dp(500), dp(290)), spacing=dp(12), padding=dp(22),
                         pos_hint={"center_x": 0.5, "center_y": 0.62})
        from kivy.graphics import Color, Line, RoundedRectangle
        with card.canvas.before:
            Color(0, 0, 0, 0.35)
            sh = RoundedRectangle(radius=[dp(26)])
            Color(*NAVY_LIGHT)
            bg = RoundedRectangle(radius=[dp(26)])
            Color(*GREEN)
            bd = Line(rounded_rectangle=(0, 0, 1, 1, dp(26)), width=dp(2))

        def upd(*a):
            sh.pos = (card.x, card.y - dp(4))
            sh.size = card.size
            bg.pos = card.pos
            bg.size = card.size
            bd.rounded_rectangle = (card.x, card.y, card.width, card.height, dp(26))
        card.bind(pos=upd, size=upd)

        card.add_widget(TLabel(text="FUTBOL ARENA", halign="center", bold=True,
                               font_size=sp(30), color=GREEN, size_hint_y=None, height=dp(44)))
        card.add_widget(TLabel(text="Başlamadan önce kullanıcı adını seç", halign="center",
                               font_size=sp(16), color=(1, 1, 1, 0.85),
                               size_hint_y=None, height=dp(28)))
        self.input = TextInput(multiline=False, hint_text="Kullanıcı adı", font_size=sp(22),
                               size_hint_y=None, height=dp(56), padding=[dp(14), dp(14)],
                               background_normal="", background_active="",
                               background_color=(0.03, 0.07, 0.17, 1),
                               foreground_color=(1, 1, 1, 1), cursor_color=GREEN,
                               hint_text_color=(1, 1, 1, 0.4), write_tab=False)
        self.input.bind(text=self._limit, on_text_validate=lambda *a: self.confirm())
        card.add_widget(self.input)
        self.err = TLabel(text="", halign="center", color=RED, font_size=sp(14),
                          size_hint_y=None, height=dp(22))
        card.add_widget(self.err)
        btn = RoundedButton(text="BAŞLA", bg=GREEN, font_size=sp(20))
        btn.bind(on_release=lambda *a: self.confirm())
        card.add_widget(btn)
        self.add_widget(card)

    def _limit(self, inst, value):
        if len(value) > 16:
            inst.text = value[:16]

    def confirm(self):
        name = " ".join(self.input.text.split())
        if len(name) < 2:
            self.err.text = "Kullanıcı adı en az 2 karakter olmalı"
            return
        save.set_username(name)
        self.input.focus = False
        goto(start_screen())

    def on_back(self):
        pass


# ----------------------------------------------------------------------------
class StarterCard(BoxLayout):
    """Başlangıç futbolcusu seçim kartı (fotoğraf + isim)."""

    def __init__(self, name, on_pick, **kw):
        super().__init__(orientation="vertical", padding=dp(8), spacing=dp(4), **kw)
        from kivy.graphics import Color, Line, RoundedRectangle
        self.pname = name
        self.on_pick = on_pick
        with self.canvas.before:
            Color(0.07, 0.14, 0.30, 1)
            self._bg = RoundedRectangle(radius=[dp(18)])
            self._bc = Color(1, 1, 1, 0.15)
            self._bd = Line(rounded_rectangle=(0, 0, 1, 1, dp(18)), width=dp(2))
        self.bind(pos=self._upd, size=self._upd)
        pid = "starter"
        self.avatar = FaceAvatar(pid, lazy=True, size_hint=(1, 0.78))
        self.avatar.set_player_by_name(name)
        self.lbl = TLabel(text=name, halign="center", bold=True, font_size=sp(15),
                          shorten=True, shorten_from="right", size_hint=(1, 0.22))
        self.add_widget(self.avatar)
        self.add_widget(self.lbl)

    def _upd(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._bd.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(18))

    def set_selected(self, on):
        self._bc.rgba = (GREEN[0], GREEN[1], GREEN[2], 1) if on else (1, 1, 1, 0.15)

    def on_touch_up(self, touch):
        if touch.grab_current is None and self.collide_point(*touch.pos) and \
                not touch.is_mouse_scrolling:
            self.on_pick(self)
        return super().on_touch_up(touch)


class StarterScreen(BaseScreen):
    """Uygulama ilk açıldığında bir kez: başlangıç futbolcunu seç."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.choice = None
        root = BoxLayout(orientation="vertical", padding=[dp(26), dp(22), dp(26), dp(18)],
                         spacing=dp(10))
        root.add_widget(TLabel(text="BAŞLANGIÇ FUTBOLCUNU SEÇ", halign="center", bold=True,
                               font_size=sp(26), color=GREEN, size_hint_y=None,
                               height=dp(44)))
        root.add_widget(TLabel(text="Yeni bir futbolcu satın alana kadar ana menüde o olacak",
                               halign="center", font_size=sp(14), color=(1, 1, 1, 0.75),
                               size_hint_y=None, height=dp(24)))
        from kivy.uix.gridlayout import GridLayout
        grid = GridLayout(cols=3, rows=2, spacing=dp(12))
        self.cards = []
        for name, _wiki in STARTER_CHOICES:
            c = StarterCard(name, self._pick)
            self.cards.append(c)
            grid.add_widget(c)
        root.add_widget(grid)
        self.btn = RoundedButton(text="BİR FUTBOLCU SEÇ", bg=GREEN, font_size=sp(20),
                                 size_hint_y=None, height=dp(56), disabled=True)
        self.btn.bind(on_release=lambda *a: self.confirm())
        root.add_widget(self.btn)
        self.add_widget(root)

    def on_pre_enter(self, *a):
        self.choice = None
        self.btn.disabled = True
        self.btn.text = "BİR FUTBOLCU SEÇ"
        for c in self.cards:
            c.set_selected(False)
            c.avatar.ensure_loaded()
        self._ev = Clock.schedule_interval(self._retry_photos, 2.0)

    def on_leave(self, *a):
        ev = getattr(self, "_ev", None)
        if ev:
            ev.cancel()
            self._ev = None

    def _retry_photos(self, dt):
        for c in self.cards:
            c.avatar.ensure_loaded()          # internet sonradan gelirse fotoğraflar yüklenir

    def _pick(self, card):
        self.choice = card.pname
        for c in self.cards:
            c.set_selected(c is card)
        self.btn.disabled = False
        self.btn.text = "%s İLE BAŞLA" % card.pname.upper()

    def confirm(self):
        if not self.choice:
            return
        save.set_starter(self.choice)
        set_starter(self.choice)
        save.select_avatar("starter")
        goto("menu")

    def on_back(self):
        pass


# ----------------------------------------------------------------------------
class MenuScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="horizontal",
                         padding=[dp(26), dp(62), dp(26), dp(18)], spacing=dp(26))
        left = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_x=0.45)
        self.avatar = FaceAvatar("starter", size_hint_y=0.88)
        self.name_lbl = TLabel(text="", halign="center", bold=True, font_size=sp(22),
                               size_hint_y=0.13)
        self.power_lbl = TLabel(text="", halign="center", bold=True, font_size=sp(16),
                                color=GOLD, size_hint_y=0.10)
        self.power_bar = BarWidget(maximum=100, size_hint=(0.7, None), height=dp(10),
                                   pos_hint={"center_x": 0.5})
        left.add_widget(self.avatar)
        left.add_widget(self.name_lbl)
        left.add_widget(self.power_lbl)
        left.add_widget(self.power_bar)
        left.add_widget(Widget(size_hint_y=0.18))      # alttaki boşluk: avatarı yukarı iter

        right = BoxLayout(orientation="vertical", spacing=dp(14))
        right.add_widget(TLabel(text="FUTBOL ARENA", halign="center", bold=True,
                                font_size=sp(30), color=GREEN, size_hint_y=None,
                                height=dp(46)))
        b1 = RoundedButton(text="OYUNA BAŞLA", bg=GREEN, font_size=sp(24))
        b2 = RoundedButton(text="MAĞAZA", bg=NAVY_LIGHT, font_size=sp(24))
        b3 = RoundedButton(text="PENALTI", bg=(0.80, 0.52, 0.08, 1), font_size=sp(24))
        b1.bind(on_release=lambda *a: goto("mode"))
        b2.bind(on_release=lambda *a: goto("shop"))
        b3.bind(on_release=lambda *a: goto("penalty"))
        for b in (b1, b2, b3):
            right.add_widget(b)
        self.stats_lbl = TLabel(text="", halign="center", font_size=sp(13),
                                color=(1, 1, 1, 0.75), size_hint_y=None, height=dp(34))
        right.add_widget(self.stats_lbl)
        self.music_lbl = TLabel(text="", halign="center", font_size=sp(11),
                                color=(1, 1, 1, 0.45), size_hint_y=None, height=dp(20))
        right.add_widget(self.music_lbl)
        root.add_widget(left)
        root.add_widget(right)
        self.add_widget(root)
        self._anim = None

    def on_pre_enter(self, *a):
        p = get_player(save.selected_avatar)
        self.avatar.set_player(p.id)       # ismine göre gerçek yüz
        self.name_lbl.text = p.name
        self.power_lbl.text = "GÜÇ SEVİYESİ %d" % p.power
        self.power_bar.value = p.power
        s = save.stats
        self.stats_lbl.text = ("Doğru: %d   Yanlış: %d   En iyi seri: %d   Özel penaltı hakkı: %d"
                               % (s["correct"], s["wrong"], s["best_streak"], save.special_rights))

    def on_enter(self, *a):
        self.avatar.bob = 0
        self._anim = (Animation(bob=1, d=0.9, t="in_out_sine") +
                      Animation(bob=0, d=0.9, t="in_out_sine"))
        self._anim.repeat = True
        self._anim.start(self.avatar)

    def on_leave(self, *a):
        Animation.cancel_all(self.avatar)

    def on_back(self):
        pass


# ----------------------------------------------------------------------------
class FootballApp(App):
    title = "Futbol Arena"

    def build(self):
        save.init(self.user_data_dir)
        set_starter(save.starter)            # seçili başlangıç futbolcusu (yoksa varsayılan)
        photos.init(os.path.join(self.user_data_dir, "photos"))

        root = FloatLayout()
        self.sm = ScreenManager(transition=FadeTransition(duration=0.18))
        self.loading = LoadingScreen(name="loading")
        self.sm.add_widget(self.loading)
        self.sm.add_widget(UsernameScreen(name="username"))
        self.sm.add_widget(StarterScreen(name="starter"))
        self.sm.add_widget(MenuScreen(name="menu"))
        self.sm.add_widget(QuizModeScreen(name="mode"))
        self.sm.add_widget(QuizScreen(name="quiz"))
        self.sm.add_widget(ShopScreen(name="shop"))
        self.sm.add_widget(PenaltyScreen(name="penalty"))
        root.add_widget(self.sm)

        self.header = HeaderBar(pos_hint={"x": 0.012, "top": 0.985})
        root.add_widget(self.header)

        self.sm.bind(current=self._on_screen)
        # İndirilmemiş fotoğraf varsa önce yükleme ekranı; hepsi hazırsa direkt oyun.
        pending = [it for it in all_photo_items() if not photos.find_local(it[0])]
        if pending:
            self.sm.current = "loading"
            self._on_screen(self.sm, "loading")
            self.loading.begin(pending)
        else:
            self.sm.current = start_screen()
            self._on_screen(self.sm, self.sm.current)
        Window.bind(on_keyboard=self._on_keyboard)
        return root

    # Müzik dosyaları (hepsi isteğe bağlı): music.mp3 genel, music_menu / music_quiz /
    # music_penalty ekrana özel. Dosya yoksa o ekran sessiz kalır.
    _MUSIC = {"menu": ("music_menu", "music"), "mode": ("music_menu", "music"),
              "shop": ("music_menu", "music"), "username": ("music_menu", "music"),
              "starter": ("music_menu", "music"),
              "quiz": ("music_quiz", "music"), "penalty": ("music_penalty", "music")}

    def _on_screen(self, sm, name):
        self.header.opacity = 0 if name in ("username", "loading", "starter") else 1
        self._update_music(name)

    def _update_music(self, name):
        names = self._MUSIC.get(name)
        if names:
            play_music(*names)
        else:
            stop_music()
        try:
            self.sm.get_screen("menu").music_lbl.text = music_status()
        except Exception:
            pass

    def _on_keyboard(self, window, key, *args):
        if key == 27:                          # Android geri tuşu / ESC
            cur = self.sm.current
            if cur in ("menu", "username", "starter"):
                return False                   # menüde: uygulamadan çık
            self.sm.current_screen.on_back()
            return True
        return False

    def on_pause(self):
        save.flush()
        stop_music()
        return True

    def on_resume(self):
        self._update_music(self.sm.current)

    def on_stop(self):
        save.flush()
        stop_music()


if __name__ == "__main__":
    FootballApp().run()
