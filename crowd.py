# -*- coding: utf-8 -*-
"""Penaltı sahnesi için hareketli tribün + kullanıcı adı pankartı."""
import math
import random

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import (Color, Ellipse, Line, PopMatrix, PushMatrix, Rectangle,
                           Rotate, RoundedRectangle, Translate)
from kivy.metrics import dp, sp
from kivy.properties import NumericProperty
from kivy.uix.label import Label
from kivy.uix.widget import Widget

_HOME = [(0.85, 0.10, 0.15), (0.95, 0.95, 0.95), (0.70, 0.07, 0.12)]
_AWAY = [(0.12, 0.35, 0.85), (0.98, 0.80, 0.12), (0.10, 0.25, 0.60)]
_MIX = [(0.10, 0.10, 0.12), (0.15, 0.55, 0.30), (0.90, 0.50, 0.10),
        (0.55, 0.55, 0.60), (0.45, 0.15, 0.55)]
_SKINS = [(0.96, 0.80, 0.66), (0.88, 0.68, 0.52), (0.70, 0.50, 0.36), (0.45, 0.30, 0.22)]
_HAIRS = [(0.08, 0.06, 0.05), (0.30, 0.18, 0.08), (0.78, 0.62, 0.28), (0.04, 0.04, 0.04),
          (0.55, 0.30, 0.12)]
_ADS = [(0.80, 0.10, 0.15), (0.10, 0.45, 0.85), (0.95, 0.75, 0.10), (0.10, 0.60, 0.35),
        (0.95, 0.95, 0.95)]


def _shade(c, f):
    return (c[0] * f, c[1] * f, c[2] * f)


class CrowdWidget(Widget):
    excite = NumericProperty(0.35)

    def __init__(self, username="", **kw):
        super().__init__(**kw)
        self.username = username or ""
        self._blocks = []
        self._flags = []
        self._flashes = []
        self._banner_lbl = None
        self._t = 0.0
        self._ev = None
        self._seed = 7
        self._rebuild_pending = False
        self.bind(pos=self._rebuild, size=self._rebuild)

    def set_username(self, name):
        self.username = name or ""
        if self._banner_lbl is not None:
            self._banner_lbl.text = self.username.upper()
        # pankart yoksa ama isim geldiyse yeniden çiz
        if self._banner_lbl is None and self.username and \
                self.width > 0 and self.height > 0:
            self._rebuild()

    def start(self):
        if self._ev is None:
            self._ev = Clock.schedule_interval(self._tick, 1 / 20.0)

    def stop(self):
        if self._ev is not None:
            self._ev.cancel()
            self._ev = None
        Animation.cancel_all(self, "excite")

    def cheer(self):
        Animation.cancel_all(self, "excite")
        (Animation(excite=1.0, d=0.25) + Animation(excite=1.0, d=2.8) +
         Animation(excite=0.35, d=2.0)).start(self)

    def groan(self):
        Animation.cancel_all(self, "excite")
        (Animation(excite=0.08, d=0.3) + Animation(excite=0.08, d=1.2) +
         Animation(excite=0.35, d=1.5)).start(self)

    def _rebuild(self, *a):
        x, y, w, h = self.x, self.y, self.width, self.height
        self.canvas.clear()
        self._blocks, self._flags, self._flashes = [], [], []
        # eski pankart label'ını kaldır
        if self._banner_lbl is not None:
            try:
                self.remove_widget(self._banner_lbl)
            except Exception:
                pass
            self._banner_lbl = None
        if w <= 0 or h <= 0:
            return
        rnd = random.Random(self._seed)
        fs = max(dp(22), w / 38.0)
        ad_h = max(dp(14), h * 0.075)
        rows = max(5, int((h - ad_h) / (fs * 0.72)))
        step = (h - ad_h) / float(rows)
        cols = int(w / (fs * 0.80)) + 3
        BLOCK = 3

        with self.canvas:
            Color(0.03, 0.05, 0.10, 1)
            Rectangle(pos=(x, y), size=(w, h))
            for fx in (0.18, 0.5, 0.82):
                Color(1, 0.97, 0.85, 0.07)
                Ellipse(pos=(x + w * fx - w * 0.14, y + h * 0.80),
                        size=(w * 0.28, h * 0.45))

            for r in range(rows):
                depth = r / float(max(1, rows - 1))
                light = 0.50 + 0.50 * depth
                base_y = y + ad_h + (rows - 1 - r) * step
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
                        fx = (x + c * fs * 0.80 - fs * 0.4 + stagger +
                              rnd.uniform(-fs * 0.06, fs * 0.06))
                        sec = fx / float(w)
                        roll = rnd.random()
                        if roll < 0.70:
                            pal = _HOME if sec < 0.5 else _AWAY
                        elif roll < 0.82:
                            pal = _AWAY if sec < 0.5 else _HOME
                        else:
                            pal = _MIX
                        shirt = _shade(rnd.choice(pal), light)
                        skin = _shade(rnd.choice(_SKINS), light)
                        hair = _shade(rnd.choice(_HAIRS), light)
                        fy = base_y + rnd.uniform(0, step * 0.10)
                        bw, bh = size_f * 0.74, size_f * 0.62
                        arms_up = rnd.random() < 0.38
                        scarf = arms_up and rnd.random() < 0.28
                        if arms_up:
                            Color(*skin)
                            aw = size_f * 0.11
                            ah = size_f * 0.62
                            Rectangle(pos=(fx - aw * 0.4, fy + bh * 0.45),
                                      size=(aw, ah))
                            Rectangle(pos=(fx + bw - aw * 0.6, fy + bh * 0.45),
                                      size=(aw, ah))
                        if scarf:
                            Color(*_shade(rnd.choice(_HOME + _AWAY), light))
                            Rectangle(pos=(fx - size_f * 0.12,
                                           fy + bh * 0.45 + size_f * 0.60),
                                      size=(bw + size_f * 0.24, size_f * 0.13))
                        Color(*shirt)
                        RoundedRectangle(pos=(fx, fy), size=(bw, bh),
                                         radius=[size_f * 0.2])
                        Color(*skin)
                        hs = size_f * 0.44
                        hx = fx + (bw - hs) / 2.0
                        hy = fy + bh - hs * 0.12
                        Ellipse(pos=(hx, hy), size=(hs, hs * 1.08))
                        Color(*hair)
                        Ellipse(pos=(hx - hs * 0.02, hy + hs * 0.55),
                                size=(hs * 1.04, hs * 0.58))
                        c += 1
                    PopMatrix()
                    self._blocks.append([tr, rnd.uniform(0, 6.28),
                                         rnd.uniform(3.2, 6.5),
                                         first_col / float(cols)])

            for i in range(7):
                fx = x + w * (0.06 + 0.88 * (i + rnd.uniform(0, 0.6)) / 7.0)
                fy = y + ad_h + h * rnd.uniform(0.10, 0.45)
                pole = fs * 1.5
                PushMatrix()
                rot = Rotate(angle=0, origin=(fx, fy))
                Color(0.85, 0.85, 0.85, 1)
                Line(points=[fx, fy, fx, fy + pole], width=dp(1.4))
                Color(*rnd.choice(_HOME + _AWAY))
                Rectangle(pos=(fx, fy + pole * 0.55),
                          size=(pole * 0.75, pole * 0.45))
                PopMatrix()
                self._flags.append([rot, rnd.uniform(0, 6.28)])

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

            for _ in range(16):
                fx = x + rnd.uniform(0.03, 0.97) * w
                fy = y + ad_h + rnd.uniform(0.05, 0.92) * (h - ad_h)
                col = Color(1, 1, 0.9, 0)
                el = Ellipse(pos=(fx - dp(4), fy - dp(4)),
                             size=(dp(8), dp(8)))
                self._flashes.append([col, el])

            # KULLANICI ADI PANKARTI
            if self.username:
                bw_p = min(w * 0.36, dp(340))
                bh_p = max(dp(40), h * 0.085)
                bx_p = x + w * 0.5 - bw_p / 2.0
                by_p = y + ad_h + (h - ad_h) * 0.60
                Color(0, 0, 0, 0.4)
                Rectangle(pos=(bx_p + dp(3), by_p - dp(3)),
                          size=(bw_p, bh_p))
                Color(0.97, 0.97, 0.97, 1)
                Rectangle(pos=(bx_p, by_p), size=(bw_p, bh_p))
                Color(0.85, 0.10, 0.15, 1)
                Rectangle(pos=(bx_p, by_p + bh_p - bh_p * 0.16),
                          size=(bw_p, bh_p * 0.16))
                Rectangle(pos=(bx_p, by_p), size=(bw_p, bh_p * 0.16))
                Color(0.85, 0.10, 0.15, 1)
                # iki küçük bayrak kenarı
                Rectangle(pos=(bx_p - dp(6), by_p),
                          size=(dp(4), bh_p))
                Rectangle(pos=(bx_p + bw_p + dp(2), by_p),
                          size=(dp(4), bh_p))

        # Label widget olarak ekle (canvas'ta text çizemeyiz)
        if self.username:
            bw_p = min(w * 0.36, dp(340))
            bh_p = max(dp(40), h * 0.085)
            bx_p = x + w * 0.5 - bw_p / 2.0
            by_p = y + ad_h + (h - ad_h) * 0.60
            self._banner_lbl = Label(
                text=self.username.upper(),
                bold=True,
                color=(0.05, 0.05, 0.10, 1),
                font_size=max(sp(14), bh_p * 0.50),
                halign="center", valign="middle",
                size_hint=(None, None),
                size=(bw_p, bh_p),
                pos=(bx_p, by_p))
            self._banner_lbl.text_size = (bw_p, bh_p)
            self.add_widget(self._banner_lbl)

    def _tick(self, dt):
        self._t += dt
        t = self._t
        amp = (0.15 + 1.0 * self.excite) * max(dp(3), self.height * 0.018)
        wave = 1.0 if self.excite < 0.6 else 1.6
        for blk in self._blocks:
            tr, ph, sp_, col = blk
            s = math.sin(t * sp_ * (0.7 + self.excite * 0.9) + ph +
                         col * 5.0 * wave)
            tr.y = amp * (s if s > 0 else s * 0.15)
        for fl in self._flags:
            fl[0].angle = math.sin(t * 2.4 + fl[1]) * (6 + 10 * self.excite)
        for col, el in self._flashes:
            if col.a > 0.02:
                col.a *= 0.55
            elif random.random() < 0.012 + 0.03 * self.excite:
                col.a = 1.0
        if self._banner_lbl:
            base_y = self._banner_lbl.y
            self._banner_lbl.y += math.sin(t * 2.2) * 0.08