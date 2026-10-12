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
from player_data import get_player, shot_success_chance, starter_is_self
from save_system import save
from ui_system import (AvatarWidget, BaseScreen, GOLD, GOLD_DARK, GREEN, GREEN_DARK,
                       NAVY_LIGHT, Overlay, RED, RoundedButton, TLabel, asset_path,
                       goto, gradient_texture, play_sound, toast,
                       user_photo_path, RoundPhoto)

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
                Ellipse(pos=(px - s * 0.08, py - s * 0.08),
                        size=(s * 0.16, s * 0.16))
            Color(0, 0, 0, 0.3)
            Line(circle=(x + s / 2, y + s / 2, s / 2), width=dp(1))


class KeeperWidget(Widget):
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
                Color(0, 0, 0, 0.3)
                Ellipse(pos=(cx - 0.3 * w, y - 0.02 * h), size=(0.6 * w, 0.06 * h))
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
                Color(0.06, 0.06, 0.08, 1)
                RoundedRectangle(pos=(cx - 0.18 * w, y + 0.32 * h),
                                 size=(0.36 * w, 0.16 * h), radius=[dp(5)])
                Color(0.98, 0.80, 0.12, 1)
                RoundedRectangle(pos=(cx - 0.20 * w, y + 0.46 * h),
                                 size=(0.40 * w, 0.28 * h), radius=[dp(10)])
                sh_y = y + 0.70 * h
                for sign, ang in ((-1, self.arm_l), (1, self.arm_r)):
                    PushMatrix()
                    Rotate(angle=ang, origin=(cx + sign * 0.17 * w, sh_y))
                    Color(0.96, 0.80, 0.66, 1)
                    Line(points=[cx + sign * 0.17 * w, sh_y,
                                 cx + sign * 0.30 * w, sh_y - 0.10 * h],
                         width=dp(7), cap="round")
                    Color(0.25, 1.0, 0.45, 1)
                    g = 0.075 * w
                    Ellipse(pos=(cx + sign * 0.30 * w - g, sh_y - 0.10 * h - g),
                            size=(2 * g, 2 * g))
                    PopMatrix()
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

        self.crowd = CrowdWidget()
        self.goal_layer = Widget()
        self.keeper = KeeperWidget()
        self.ball = BallWidget()
        self.taker_round = RoundPhoto(ring=GREEN)
        self.taker_fallback = AvatarWidget("starter")
        self.add_widget(self.crowd)
        self.add_widget(self.goal_layer)
        self.add_widget(self.keeper)
        self.add_widget(self.ball)
        self.add_widget(self.taker_fallback)
        self.add_widget(self.taker_round)
        self.taker_round.opacity = 0

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
        self.bind(pos=self._relayout, size=self._relayout)

    def on_trail_alpha(self, inst, v):
        self._trail_c.a = v

    def on_drag_alpha(self, inst, v):
        self._drag_c.a = v

    def on_flash_alpha(self, inst, v):
        self._flash_c.a = v

    def setup(self, player):
        self.power = player.power
        self.crowd.set_username(save.username)
        if starter_is_self() and save.selected_avatar == "starter":
            up = user_photo_path()
            if up and self.taker_round.set_path(up):
                self.taker_round.opacity = 1
                self.taker_fallback.opacity = 0
                return
        self.taker_round.opacity = 0
        self.taker_fallback.opacity = 1
        self.taker_fallback.set_player(player.id)

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
        self.crowd.pos = (x, horizon)
        self.crowd.size = (w, max(0, y + h - horizon))
        c = self.canvas.before
        c.clear()
        with c:
            Color(1, 1, 1, 1)
            Rectangle(texture=gradient_texture((0.13, 0.25, 0.50),
                                               (0.03, 0.07, 0.18)),
                      pos=(x, y), size=(w, h))
            bands = 8
            gh_total = horizon - y
            for i in range(bands):
                shade = 0.50 if i % 2 == 0 else 0.44
                Color(0.05, shade * 0.62, 0.20, 1)
                Rectangle(pos=(x, y + gh_total * i / bands),
                          size=(w, gh_total / bands + 1))
            Color(1, 1, 1, 0.55)
            Line(points=[x, gy, x + w, gy], width=dp(2))
            Line(points=[gx - gw * 0.12, gy, x + w * 0.26, y + h * 0.30,
                         x + w * 0.74, y + h * 0.30, gx + gw * 1.12, gy],
                 width=dp(2))
            Color(1, 1, 1, 0.9)
            sx, sy = self.ball_start
            Ellipse(pos=(sx - dp(7), sy - self.ball_size * 0.55),
                    size=(dp(14), dp(7)))
        g = self.goal_layer.canvas
        g.clear()
        with g:
            Color(0, 0, 0, 0.38)
            Rectangle(pos=(gx, gy), size=(gw, gh))
            Color(1, 1, 1, 0.20)
            cols, rows = 16, 8
            for i in range(1, cols):
                Line(points=[gx + gw * i / cols, gy, gx + gw * i / cols, gy + gh],
                     width=dp(1))
            for j in range(1, rows):
                Line(points=[gx, gy + gh * j / rows, gx + gw, gy + gh * j / rows],
                     width=dp(1))
            Color(1, 1, 1, 1)
            Line(points=[gx, gy, gx, gy + gh, gx + gw, gy + gh, gx + gw, gy],
                 width=dp(4.5))

    def _place_children(self):
        kh = self.gh * 0.92
        self.keeper.size = (self.gh * 0.80, kh)
        self.keeper.angle = 0
        self.keeper.arm_l = self.keeper.arm_r = 0
        self.keeper.leg_l = self.keeper.leg_r = 0
        self.keeper.center = (self.gx + self.gw / 2.0, self.gy + kh / 2.0)
        bs = self.ball_size
        self.ball.size = (bs, bs)
        self.ball.pos = (self.ball_start[0] - bs / 2.0, self.ball_start[1] - bs / 2.0)
        self.ball.flame = 1.0 if self.special else 0
        self.ball.opacity = 1
        ah = self.height * 0.36
        self.taker_fallback.size = (ah * 0.6, ah)
        self.taker_fallback.pos = (self.ball_start[0] - self.width * 0.13 - ah * 0.3,
                                    self.y + self.height * 0.02)
        self.taker_fallback.bob = 0
        d = min(ah * 0.9, dp(140))
        self.taker_round.size = (d, d)
        self.taker_round.center = (self.ball_start[0] - self.width * 0.13 - ah * 0.3 + ah * 0.3,
                                    self.y + self.height * 0.02 + d / 2)

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
        for w in (self.keeper, self.ball, self.taker_fallback, self):
            Animation.cancel_all(w)
        self.trail_alpha = 0
        self.drag_alpha = 0
        self.flash_alpha = 0
        self._curve_c.a = 0
        if self._flame_ev:
            self._flame_ev.cancel()
            self._flame_ev = None

    def prepare_shot(self, special=False):
        self.cancel_all()
        self.state = "ready"
        self.special = special
        self.fake_used = False
        self.keeper_zone = random.choice(ZONE_LIST)
        self._relayout()
        self._place_children()
        if special:
            self.ball.spin = 0

            def _flame_tick(dt):
                self.ball.spin += dt
            self._flame_ev = Clock.schedule_interval(_flame_tick, 1 / 30.0)

    def trigger_fake(self):
        if self.state != "ready" or self.fake_used:
            return False
        self.fake_used = True
        self.state = "faking"
        self.keeper_zone = random.choice([z for z in ZONE_LIST if z != "C"])
        self._later(0.05, lambda dt: self._dive())

        def recover(dt):
            Animation(center_x=self.gx + self.gw / 2.0,
                      center_y=self.gy + self.gh * 0.46,
                      angle=0, arm_l=0, arm_r=0, leg_l=0, leg_r=0,
                      d=0.55, t="out_cubic").start(self.keeper)
            self.state = "ready"
        self._later(0.65, recover)
        self._later(1.1, lambda dt: setattr(self, "keeper_zone",
                                             random.choice(ZONE_LIST)))
        return True

    def on_touch_down(self, touch):
        if self.state != "ready" or not self.collide_point(*touch.pos):
            return False
        touch.grab(self)
        self._start_touch = touch.pos
        self._drag_l.points = [touch.x, touch.y, touch.x, touch.y]
        self.drag_alpha = 0.9
        self._curve_c.a = 0.7
        self._curve_l.points = [touch.x, touch.y, touch.x, touch.y]
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is self and self._start_touch:
            sx, sy = self._start_touch
            self._drag_l.points = [sx, sy, touch.x, touch.y]
            dx = touch.x - sx
            dy = touch.y - sy
            bend = max(-60, min(60, dx * 0.25))
            mx = (sx + touch.x) / 2.0
            my = (sy + touch.y) / 2.0
            cx = mx + bend
            cy = my
            pts = []
            for i in range(16):
                t = i / 15.0
                px = (1 - t) ** 2 * sx + 2 * (1 - t) * t * cx + t ** 2 * touch.x
                py = (1 - t) ** 2 * sy + 2 * (1 - t) * t * cy + t ** 2 * touch.y
                pts.extend([px, py])
            self._curve_l.points = pts
            return True
        return False

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return False
        touch.ungrab(self)
        self.drag_alpha = 0
        self._curve_c.a = 0
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
        ux = dx / length
        uy = dy / length
        bend = max(-60, min(60, dx * 0.25))
        self._shoot(ux, uy, bend)
        return True

    def _shoot(self, ux, uy, bend=0):
        self.state = "shooting"
        self.on_shot_start()
        bx, by = self.ball_start
        dist = math.hypot(self.gx + self.gw / 2.0 - bx,
                          self.gy + self.gh / 2.0 - by)
        tx = min(max(bx + ux * dist, self.gx + self.gw * 0.06),
                 self.gx + self.gw * 0.94)
        ty = min(max(by + uy * dist, self.gy + self.gh * 0.08),
                 self.gy + self.gh * 0.92)
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
                ty = self.gy + self.gh * 1.22
            else:
                tx = self.gx - self.gw * 0.10 if fx < 0.5 else self.gx + self.gw * 1.10

        cx = (bx + tx) / 2.0 + bend
        cy = (by + ty) / 2.0
        pts = []
        for i in range(24):
            t = i / 23.0
            px = (1 - t) ** 2 * bx + 2 * (1 - t) * t * cx + t ** 2 * tx
            py = (1 - t) ** 2 * by + 2 * (1 - t) * t * cy + t ** 2 * ty
            pts.extend([px, py])
        self._trail_l.points = pts
        self.trail_alpha = 0.9
        Animation(trail_alpha=0, d=1.0).start(self)

        (Animation(bob=1, d=0.12) + Animation(bob=0, d=0.18)).start(self.taker_fallback)

        es = self.ball_size * 0.62
        total_d = 0.55
        steps = 24
        for i in range(1, steps + 1):
            t = i / float(steps)
            px = (1 - t) ** 2 * bx + 2 * (1 - t) * t * cx + t ** 2 * tx
            py = (1 - t) ** 2 * by + 2 * (1 - t) * t * cy + t ** 2 * ty
            delay = total_d * t
            target = (px - es / 2.0, py - es / 2.0)
            self._later(delay, lambda dt, p=target: setattr(self.ball, "pos", p))
        self._later(total_d, lambda dt: setattr(self.ball, "size", (es, es)))
        self._later(total_d + 0.02, lambda dt: self._arrived(outcome, tx, ty))
        self._later(0.12, lambda dt: self._dive())

    def _dive(self):
        zx, zy = self.zone_point(self.keeper_zone)
        z = self.keeper_zone
        if z == "C":
            ang = arm_l = arm_r = leg_l = leg_r = 0
        else:
            sign = 1 if z.endswith("L") else -1
            ang = sign * (52 if z.startswith("T") else 78)
            arm_l = -sign * 60
            arm_r = -sign * 60
            leg_l = sign * 20
            leg_r = -sign * 20
        Animation(center_x=zx, center_y=zy, angle=ang,
                  arm_l=arm_l, arm_r=arm_r, leg_l=leg_l, leg_r=leg_r,
                  d=0.40, t="out_cubic").start(self.keeper)

    def _arrived(self, outcome, tx, ty):
        if outcome == "goal":
            self.flash_alpha = 0.40
            Animation(flash_alpha=0, d=0.6).start(self)
            Animation(y=ty - self.gh * 0.12, d=0.25, t="in_quad").start(self.ball)
        elif outcome == "saved":
            Animation(y=self.gy - self.gh * 0.05, d=0.3, t="in_quad").start(self.ball)
        self.state = "done"
        self._later(0.55, lambda dt: self.on_result(outcome))


class PenaltyScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(with_background=False, **kw)
        self.start_special = False
        self.special_mode = False
        self.player = get_player("starter")
        self.overlay = None
        self._auto = None
        self._shot_special = False

        self.scene = PenaltyScene(self._on_result, self._invalid,
                                  self._shot_started)
        self.add_widget(self.scene)

        self.mode_lbl = TLabel(text="", halign="center", bold=True, font_size=sp(17),
                               size_hint=(None, None), size=(dp(560), dp(34)),
                               pos_hint={"center_x": 0.5, "top": 0.985})
        self.info_lbl = TLabel(text="", font_size=sp(14), bold=True,
                               size_hint=(None, None), size=(dp(300), dp(52)),
                               pos_hint={"x": 0.015, "y": 0.02})
        self.hint_lbl = TLabel(text="Topun üzerinden kaleye doğru parmağınla KAVİSLİ çizgi çiz",
                               halign="center", font_size=sp(15),
                               color=(1, 1, 1, 0.9),
                               size_hint=(None, None), size=(dp(560), dp(30)),
                               pos_hint={"center_x": 0.5, "y": 0.012})
        box = BoxLayout(orientation="horizontal", spacing=dp(8),
                        size_hint=(None, None), size=(dp(430), dp(44)),
                        pos_hint={"right": 0.99, "top": 0.985})
        self.special_btn = RoundedButton(text="", bg=NAVY_LIGHT, font_size=sp(13),
                                         size_hint=(None, 1), width=dp(160))
        self.special_btn.bind(on_release=lambda *a: self._toggle_special())
        self.fake_btn = RoundedButton(text="FAKE  -5", bg=(0.55, 0.20, 0.65, 1),
                                      font_size=sp(13), size_hint=(None, 1),
                                      width=dp(130))
        self.fake_btn.bind(on_release=lambda *a: self._do_fake())
        menu = RoundedButton(text="MENÜ", bg=NAVY_LIGHT, font_size=sp(13),
                             size_hint=(None, 1), width=dp(100))
        menu.bind(on_release=lambda *a: self._to_menu())
        box.add_widget(self.special_btn)
        box.add_widget(self.fake_btn)
        box.add_widget(menu)
        for w in (self.mode_lbl, self.info_lbl, self.hint_lbl, box):
            self.add_widget(w)

    def on_pre_enter(self, *a):
        self.player = get_player(save.selected_avatar)
        self.scene.setup(self.player)
        self.special_mode = bool(self.start_special) and save.special_rights > 0
        self.start_special = False
        self.hint_lbl.opacity = 1
        self._refresh()
        self.scene.prepare_shot(special=self.special_mode)
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
            self.mode_lbl.text = "ÖZEL PENALTI  •  GOL = +25 PUAN  •  ALEVLİ TOP"
            self.mode_lbl.color = GOLD
        else:
            self.mode_lbl.text = "PENALTI  •  GOL = +1 PUAN  •  FAKE -5"
            self.mode_lbl.color = (1, 1, 1, 1)
        self.special_btn.opacity = 1 if rights > 0 else 0
        self.special_btn.disabled = rights <= 0
        self.special_btn.text = "ÖZEL HAK x%d" % rights
        self.special_btn.bg = list(GOLD_DARK if self.special_mode else NAVY_LIGHT)
        chance = int(round(shot_success_chance(self.player.power) * 100))
        self.info_lbl.text = "%s\nGÜÇ %d  •  İsabet %%%d" % (
            self.player.name, self.player.power, chance)
        can_fake = (save.points >= FAKE_COST) and not self.scene.fake_used
        self.fake_btn.disabled = not can_fake
        self.fake_btn.opacity = 1 if can_fake else 0.4

    def _toggle_special(self):
        if self.scene.state != "ready" or save.special_rights <= 0:
            return
        self.special_mode = not self.special_mode
        self._refresh()
        self.scene.prepare_shot(special=self.special_mode)

    def _do_fake(self):
        if self.scene.state != "ready":
            return
        if save.points < FAKE_COST:
            toast(self, "Yetersiz puan (FAKE için %d gerek)" % FAKE_COST, RED, 1.6)
            return
        if self.scene.fake_used:
            toast(self, "Bu turda zaten fake yaptın", RED, 1.4)
            return
        save.add_points(-FAKE_COST)
        ok = self.scene.trigger_fake()
        if ok:
            toast(self, "FAKE! Kaleci yanlış tarafa atladı  (-%d)" % FAKE_COST,
                  (0.55, 0.20, 0.65, 1), 1.6)
            play_sound("buy")
        self._refresh()

    def _invalid(self):
        toast(self, "Topun üzerinden kaleye doğru, kavisli çizgi çiz", RED, 1.4)

    def _shot_started(self):
        self.hint_lbl.opacity = 0
        self._shot_special = self.special_mode and save.special_rights > 0
        self.fake_btn.disabled = True
        self.fake_btn.opacity = 0.4

    def _on_result(self, outcome):
        if self.overlay:
            return
        special = self._shot_special
        gained = save.record_penalty(outcome, special)
        if outcome == "goal":
            self.scene.crowd.cheer()
            play_sound("goal")
            if special and gained == 25:
                self.overlay = Overlay(
                    "TEBRİKLER! MUHTEŞEM BİR PENALTI! +25 PUAN", "",
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
            sub = "Buffon doğru köşeyi seçti.  -1 PUAN"
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
        self.scene.prepare_shot(special=self.special_mode)

    def _to_menu(self):
        if self._auto:
            self._auto.cancel()
            self._auto = None
        if self.overlay:
            self.overlay.dismiss()
            self.overlay = None
        goto("menu")