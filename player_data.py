# -*- coding: utf-8 -*-
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
    starter = Player("starter", "Barış Alper Yılmaz", 10, 0,
                     "Barış Alper Yılmaz")             # ücretsiz başlangıç avatarı (güç 10)
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
    for p in SHOP_PLAYERS:
        if p.wiki:
            slug = slugify(p.name)
            seen.setdefault(slug, (slug, p.wiki, p.name))
    for q in EASY_POOL + HARD_POOL:
        seen.setdefault(q.slug, (q.slug, q.wiki, q.name))
    return list(seen.values())
