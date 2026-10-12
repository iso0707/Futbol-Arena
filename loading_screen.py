# -*- coding: utf-8 -*-
"""Açılış yükleme ekranı: logo + hareketli bar + hafif animasyonlar."""
import math
import os

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.properties import NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from save_system import save
from ui_system import (BaseScreen, GOLD_DARK, GREEN, NAVY_DARK, NAVY_LIGHT,
                       RoundedButton, TLabel, asset_path, goto, photos,
                       start_screen)


# ============================================================================
# HAREKETLİ YÜKLEME ÇUBUĞU
# ============================================================================
class AnimatedLoadingBar(Widget):
    """Hareketli yükleme çubuğu: yeşil dolgu + üstünde kayan beyaz ışık."""
    value = NumericProperty(0)
    maximum = NumericProperty(100)
    _phase = NumericProperty(0)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.bind(pos=self._draw, size=self._draw,
                  value=self._draw, maximum=self._draw,
                  _phase=self._draw)
        self._ev = None
        self._draw()

    def start(self):
        if self._ev is None:
            self._ev = Clock.schedule_interval(self._tick, 1 / 30.0)

    def stop(self):
        if self._ev:
            self._ev.cancel()
            self._ev = None

    def _tick(self, dt):
        self._phase = (self._phase + dt * 1.6) % 1.0

    def _draw(self, *a):
        self.canvas.clear()
        x, y = self.pos
        w, h = self.size
        if w <= 0 or h <= 0:
            return
        r = h / 2.0
        frac = max(0.0, min(1.0, self.value / float(self.maximum or 1)))
        with self.canvas:
            # arka plan (koyu)
            Color(1, 1, 1, 0.12)
            RoundedRectangle(pos=(x, y), size=(w, h), radius=[r])
            # dolgu (yeşil)
            if frac > 0:
                Color(*GREEN)
                RoundedRectangle(pos=(x, y), size=(max(h, w * frac), h),
                                 radius=[r])
                # dolgunun üstünde kayan beyaz ışık
                shine_w = w * 0.12
                shine_x = x + (w * frac - shine_w) * self._phase
                Color(1, 1, 1, 0.30)
                RoundedRectangle(pos=(shine_x, y + h * 0.30),
                                 size=(shine_w, h * 0.40),
                                 radius=[h * 0.20])
            # kenar çizgisi
            Color(1, 1, 1, 0.25)
            Line(rounded_rectangle=(x, y, w, h, r), width=dp(1))


# ============================================================================
# PRELOADER (mevcut haliyle aynı, fotoğrafları indirir)
# ============================================================================
class Preloader:
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
        self.cancelled = True

    def _pump(self):
        while (not self.cancelled and not self.finished and
               self.active < self.MAX_ACTIVE and self.idx < self.total):
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


# ============================================================================
# YÜKLEME EKRANI
# ============================================================================
class LoadingScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(with_background=True, **kw)
        self.pre = None
        self._left = False
        self._pulse_ev = None

        root = FloatLayout()

        # ÜSTTE "FUTBOLUM" — büyük beyaz yazı
        self.title = Label(
            text="FUTBOLUM",
            bold=True,
            font_size=sp(64),
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            size=(dp(700), dp(90)),
            pos_hint={"center_x": 0.5, "top": 0.92})
        root.add_widget(self.title)

        # Oyun logosu (logo.png ana klasörde olacak)
        logo_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "logo.png")
        self.logo = None
        if os.path.isfile(logo_path):
            self.logo = Image(source=logo_path, fit_mode="contain",
                              size_hint=(None, None),
                              size=(dp(240), dp(240)),
                              pos_hint={"center_x": 0.5, "center_y": 0.55})
            root.add_widget(self.logo)
        else:
            # logo yoksa yeşil daire içinde top çiz
            self.logo = _FallbackLogo(size_hint=(None, None),
                                      size=(dp(200), dp(200)),
                                      pos_hint={"center_x": 0.5,
                                                "center_y": 0.55})
            root.add_widget(self.logo)

        # Ortada hareketli bar
        self.bar = AnimatedLoadingBar(
            maximum=1,
            size_hint=(None, None),
            size=(dp(560), dp(20)),
            pos_hint={"center_x": 0.5, "center_y": 0.28})
        root.add_widget(self.bar)

        # Alt yazı (durum)
        self.status = TLabel(
            text="Fotoğraflar yükleniyor",
            halign="center",
            font_size=sp(15),
            color=(1, 1, 1, 0.75),
            size_hint=(None, None),
            size=(dp(560), dp(24)),
            pos_hint={"center_x": 0.5, "center_y": 0.22})
        root.add_widget(self.status)

        # Yüzde
        self.percent = TLabel(
            text="%0",
            halign="center",
            bold=True,
            font_size=sp(18),
            color=GREEN,
            size_hint=(None, None),
            size=(dp(200), dp(24)),
            pos_hint={"center_x": 0.5, "center_y": 0.18})
        root.add_widget(self.percent)

        # Beklemeden geç butonu
        self.skip_btn = RoundedButton(
            text="BEKLEMEDEN GEÇ",
            bg=GOLD_DARK,
            font_size=sp(15),
            size_hint=(None, None),
            size=(dp(220), dp(44)),
            pos_hint={"center_x": 0.5, "y": 0.05})
        self.skip_btn.bind(on_release=lambda *a: self.skip())
        root.add_widget(self.skip_btn)

        self.add_widget(root)

    # -- animasyon ---------------------------------------------------------
    def on_enter(self, *a):
        self.bar.start()
        # FUTBOLUM yazısı hafif nefes alır
        self._pulse_title()

    def on_leave(self, *a):
        self.bar.stop()
        if self._pulse_ev:
            self._pulse_ev.cancel()
            self._pulse_ev = None
        Animation.cancel_all(self.title, "font_size")

    def _pulse_title(self):
        anim = (Animation(font_size=sp(68), d=0.9, t="in_out_sine") +
                Animation(font_size=sp(64), d=0.9, t="in_out_sine"))
        anim.repeat = True
        anim.start(self.title)

    # -- akış --------------------------------------------------------------
    def begin(self, items):
        self._left = False
        self.bar.maximum = max(1, len(items))
        self.bar.value = 0
        self.percent.text = "%0"
        self.pre = Preloader(items, self._progress, self._done)
        self.pre.start()

    def _progress(self, done, total):
        self.bar.maximum = max(1, total)
        self.bar.value = done
        pct = int(round(100.0 * done / max(1, total)))
        self.percent.text = "%%%d" % pct
        self.status.text = "Fotoğraflar yükleniyor  (%d / %d)" % (done, total)

    def _done(self, offline):
        if offline:
            self.status.text = "İnternet yok — fotoğraflar sonra yüklenecek"
            Clock.schedule_once(lambda dt: self._proceed(), 1.8)
        else:
            self.bar.value = self.bar.maximum
            self.percent.text = "%100"
            self.status.text = "Hazır! Oyun açılıyor..."
            Clock.schedule_once(lambda dt: self._proceed(), 0.5)

    def skip(self):
        if self.pre:
            self.pre.cancel()
        self._proceed()

    def _proceed(self):
        if self._left:
            return
        self._left = True
        goto(start_screen())

    def on_back(self):
        self.skip()


# ============================================================================
# YEDEK LOGO (logo.png yoksa) — top çizimi
# ============================================================================
class _FallbackLogo(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.bind(pos=self._draw, size=self._draw)
        self._draw()

    def _draw(self, *a):
        self.canvas.clear()
        w = min(self.width, self.height)
        if w <= 0:
            return
        cx, cy = self.center
        with self.canvas:
            # yeşil disk
            Color(*GREEN)
            Ellipse(pos=(cx - w / 2, cy - w / 2), size=(w, w))
            # beyaz top
            s = w * 0.7
            Color(1, 1, 1, 1)
            Ellipse(pos=(cx - s / 2, cy - s / 2), size=(s, s))
            # siyah beşgen (merkez)
            Color(0.08, 0.08, 0.10, 1)
            Ellipse(pos=(cx - s * 0.15, cy - s * 0.15),
                    size=(s * 0.30, s * 0.30))
            # kenar noktaları
            for ang in range(5):
                a = math.radians(90 + ang * 72)
                px = cx + math.cos(a) * s * 0.36
                py = cy + math.sin(a) * s * 0.36
                Ellipse(pos=(px - s * 0.08, py - s * 0.08),
                        size=(s * 0.16, s * 0.16))