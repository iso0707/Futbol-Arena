# -*- coding: utf-8 -*-
"""Futbol Arena - ana dosya (Kivy). Yatay mod, mobil dokunmatik."""
import os

os.environ.setdefault("KIVY_NO_ARGS", "1")

from kivy.config import Config

Config.set("graphics", "width", "1280")      # masaüstünde test için
Config.set("graphics", "height", "720")
Config.set("graphics", "resizable", "1")
Config.set("kivy", "exit_on_escape", "0")

from kivy.animation import Animation
from kivy.app import App
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import FadeTransition, ScreenManager
from kivy.uix.textinput import TextInput

from player_data import get_player
from penalty_system import PenaltyScreen
from quiz_system import QuizModeScreen, QuizScreen
from save_system import save
from shop_system import ShopScreen
from ui_system import (AvatarWidget, BarWidget, BaseScreen, GOLD, GREEN, GREEN_DARK,
                       HeaderBar, NAVY_DARK, NAVY_LIGHT, RED, RoundedButton, TLabel,
                       goto, photos)

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
        goto("menu")

    def on_back(self):
        pass


# ----------------------------------------------------------------------------
class MenuScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="horizontal",
                         padding=[dp(26), dp(72), dp(26), dp(18)], spacing=dp(26))
        left = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_x=0.45)
        self.avatar = AvatarWidget("starter", size_hint_y=0.68)
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
        root.add_widget(left)
        root.add_widget(right)
        self.add_widget(root)
        self._anim = None

    def on_pre_enter(self, *a):
        p = get_player(save.selected_avatar)
        self.avatar.set_player(p.id)
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
        photos.init(os.path.join(self.user_data_dir, "photos"))

        root = FloatLayout()
        self.sm = ScreenManager(transition=FadeTransition(duration=0.18))
        self.sm.add_widget(UsernameScreen(name="username"))
        self.sm.add_widget(MenuScreen(name="menu"))
        self.sm.add_widget(QuizModeScreen(name="mode"))
        self.sm.add_widget(QuizScreen(name="quiz"))
        self.sm.add_widget(ShopScreen(name="shop"))
        self.sm.add_widget(PenaltyScreen(name="penalty"))
        root.add_widget(self.sm)

        self.header = HeaderBar(pos_hint={"x": 0.012, "top": 0.985})
        root.add_widget(self.header)

        self.sm.bind(current=self._on_screen)
        self.sm.current = "menu" if save.username else "username"
        self._on_screen(self.sm, self.sm.current)
        Window.bind(on_keyboard=self._on_keyboard)
        return root

    def _on_screen(self, sm, name):
        self.header.opacity = 0 if name == "username" else 1

    def _on_keyboard(self, window, key, *args):
        if key == 27:                          # Android geri tuşu / ESC
            cur = self.sm.current
            if cur in ("menu", "username"):
                return False                   # menüde: uygulamadan çık
            self.sm.current_screen.on_back()
            return True
        return False

    def on_pause(self):
        save.flush()
        return True

    def on_resume(self):
        pass

    def on_stop(self):
        save.flush()


if __name__ == "__main__":
    FootballApp().run()
