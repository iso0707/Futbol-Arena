# -*- coding: utf-8 -*-
"""Açılış yükleme ekranı: tüm futbolcu fotoğrafları önceden indirilir, hepsi
bitince oyun açılır. "BEKLEMEDEN GEÇ" ile istenirse beklemeden girilebilir."""
from kivy.clock import Clock
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout

from save_system import save
from ui_system import (BarWidget, BaseScreen, GOLD_DARK, GREEN, NAVY_LIGHT, RoundedButton,
                       TLabel, goto, photos)


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
        goto("menu" if save.username else "username")

    def on_back(self):
        self.skip()
