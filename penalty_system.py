# -*- coding: utf-8 -*-
"""Penaltı: kavisli/falsolu şut, gerçekçi kaleci, alevli özel penaltı, FAKE butonu."""
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

from crowd import CrowdWidget
from player_data import get_player, shot_success_chance
from save_system import save
from ui_system import (AvatarWidget, BaseScreen, GOLD, GOLD_DARK, GREEN, GREEN_DARK,
                       NAVY_LIGHT, Overlay, RED, RoundedButton, TLabel, asset_path,
                       goto, gradient_texture, play_sound, toast)

ZONES = {"TL": (0.17, 0.74), "BL": (0.17, 0.26), "TR": (0.83, 0.74),
         "BR": (0.83, 0.26), "C": (0.5, 0.5)}
ZONE_LIST = list(ZONES)
FAKE_COST = 5


class BallWidget(Widget):
    flame = NumericProperty(0)
    spin = NumericProperty(0)

    def __init__(self, **kw):
        super().__init__(size_hint=(None, None), **kw)
        self.bind(pos=self._d, size=self._d, flame=self._d, spin=self._d)

    def _d(self, *a):
        self.canvas.clear()
        s = self.width
        if s <= 0:
            return
        x, y = self.pos
        with self.canvas:
            if self.flame > 0.02:
                f = self.flame
                for i in range(8):
                    ph = self.spin * 3.0 + i * 0.9
                    wob = math.sin(ph) * s * 0.22
                    h_f = s * (0.7 + 1.1 * f) * (0.5 + 0.5 * math.sin(ph * 1.3))
                    wid = s * (0.40 - i * 0.03)
                    fy = y - h_f * 0.5
                    Color(1.0, 0.25, 0.02, 0.55 * f)
                    Ellipse(pos=(x + s / 2 - wid / 2 + wob * 0.6, fy),
                            size=(wid, h_f))
                    Color(1.0, 0.65, 0.10, 0.75 * f)
                    Ellipse(pos=(x + s / 2 - wid * 0.35, fy + h_f * 0.25),
                            size=(wid * 0.7, h_f * 0.7))
                    Color(1.0, 0.95, 0.55, 0.9 * f)
                    Ellipse(pos=(x + s / 2 - wid * 0.18, fy + h_f * 0.45),
                            size=(wid * 0.36, h_f * 0.45))
            Color(1, 1, 1, 1)
            Ellipse(pos=(x, y), size=(s, s))
            Color(0.08, 0.08, 0.10, 1)
            Ellipse(pos=(x + s * 0.35, y + s * 0.35), size=(s * 0.30, s * 0.30))
            for ang in range(5):
                a = math.radians(90 + ang * 72 + self.spin * 40)
                px = x + s / 2 + math.cos(a) * s * 0.40
                py = y + s / 2 + math.sin(a) * s * 0.40
                Ellipse(pos=(px - s * 0.08, py - s * 0.08), size=(s * 0.16, s * 0.16))
            Color(0, 0, 0, 0.3)
            Line(circle=(x + s / 2, y + s / 2, s / 2), width=dp(1))


class KeeperWidget(Widget):
    """Gerçekçi kaleci: kol ve bacaklar omuz/kalça noktasından ayrı döner."""
    angle = NumericProperty(0)
    arm_l = NumericProperty(0)
    arm_r = NumericProperty(0)
    leg_l = NumericProperty(0)
    leg_r = NumericProperty(0)

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
        self.bind(pos=self._d, size=self._d, angle=self._d,
                  arm_l=self._d, arm_r=self._d, leg_l=self._d, leg_r=self._d)

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
                # gölge
                Color(0, 0, 0, 0.3)
                Ellipse(pos=(cx - 0.3 * w, y - 0.02 * h), size=(0.6 * w, 0.06 * h))
                # BACAKLAR
                hip_y = y + 0.36 * h
                for sign, ang in ((-1, self.leg_l), (1, self.leg_r)):
                    PushMatrix()
                    Rotate(angle=ang, origin=(cx + sign * 0.08 * w, hip_y))
                    Color(0.06, 0.06, 0.08, 1)
                    Line(points=[cx + sign * 0.08 * w, hip_y,
                                 cx + sign * 0.14 * w, y + 0.05 * h],
                         width=dp(8), cap="round")
                    Color(0.95, 0.85, 0.20, 1)
                    Ellipse(pos=(cx + sign * 0.14 * w - 0.06 * w, y + 0.02 * h),
                            size=(0.12 * w, 0.06 * h))
                    PopMatrix()
                # ŞORT
                Color(0.06, 0.06, 0.08, 1)
                RoundedRectangle(pos=(cx - 0.18 * w, y + 0.32 * h),
                                 size=(0.36 * w, 0.16 * h), radius=[dp(5)])
                # GÖVDE
                Color(0.98, 0.80, 0.12, 1)
                RoundedRectangle(pos=(cx - 0.20 * w, y + 0.46 * h),
                                 size=(0.40 * w, 0.28 * h), radius=[dp(10)])
                # KOLLAR
                sh_y = y + 0.70 * h
                for sign, ang in ((-1, self.arm_l), (1, self.arm_r)):
                    PushMatrix()
                    Rotate(angle=ang, origin=(cx + sign * 0.17 * w, sh_y))
                    Color(0.96, 0.80, 0.66, 1)
                    Line(points=[cx + sign * 0.17 * w, sh_y,
                                 cx + sign * 0.30 * w, sh_y - 0.10 * h],
                         width=dp(7), cap="round")
                    # eldiven
                    Color(0.25, 1.0, 0.45, 1)
                    g = 0.075 * w
                    Ellipse(pos=(cx + sign * 0.30 * w - g,
                                 sh_y - 0.10 * h - g),
                            size=(2 * g, 2 * g))
                    PopMatrix()
                # KAFA
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
        self.special = False
        self.fake_used = False
        self._flame_ev = None
        self._curve_pts = []

        self.crowd = CrowdWidget()
        self.goal_layer = Widget()
        self.keeper = KeeperWidget()
        self.ball = BallWidget()
        self.taker = AvatarWidget("starter")
        self.add_widget(self.crowd)
        self.add_widget(self.goal_layer)
        self.add_widget(self.keeper)
        self.add_widget(self.ball)
        self.add_widget(self.taker)

        with self.canvas.after:
            self._flash_c = Color(0.3, 1, 0.5, 0)
            self._flash_r = Rectangle(pos=(0, 0), size=(0, 0))
            self._trail_c = Color(0.35, 0.9, 1, 0)
            self._trail_l = Line(points=[0, 0, 0, 0], width=dp(3),
                                 dash_length=dp(9), dash_offset=dp(6))
            self._drag_c = Color(0.35, 0.9, 1, 0)
            self._drag_l = Line(points=[0, 0, 0, 0], width=dp(4))
            self._curve_c = Color(0.95, 0.55, 0.10, 0)
            self._curve_l = Line(points=[0, 0], width=dp(3))
       