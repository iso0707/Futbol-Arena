# -*- coding: utf-8 -*-
"""Futbolum - ana dosya (Kivy). Yatay mod, mobil dokunmatik."""
import os
import datetime

os.environ.setdefault("KIVY_NO_ARGS", "1")

from kivy.config import Config
Config.set("graphics", "width", "1280")
Config.set("graphics", "height", "720")
Config.set("graphics", "resizable", "1")
Config.set("kivy", "exit_on_escape", "0")

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import FadeTransition, ScreenManager
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from save_system import save, DAILY_REWARD
from player_data import (STARTER_CHOICES, all_photo_items, get_player,
                         set_starter, set_starter_from_user, slugify)
from ui_system import (AvatarWidget, Background, BarWidget, BaseScreen, FaceAvatar,
                       GOLD, GOLD_DARK, GREEN, GREEN_DARK, GREY, NAVY_DARK,
                       NAVY_LIGHT, PhotoPickerPopup, RED, RoundPhoto,
                       RoundedButton, SharePopup, TLabel, copy_user_photo, goto,
                       photos, play_music, start_screen, stop_music, toast,
                       user_photo_path, music_status, GAME_NAME)
from loading_screen import LoadingScreen
from quiz_system import QuizModeScreen, QuizScreen
from shop_system import ShopScreen
from penalty_system import PenaltyScreen

Window.softinput_mode = "below_target"
Window.clearcolor = NAVY_DARK

_SECRET_CODE = "10101010101010101020"


# ============================================================================
# KULLANICI ADI EKRANI
# ============================================================================
class UsernameScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        card = BoxLayout(orientation="vertical", size_hint=(None, None),
                         size=(dp(500), dp(290)), spacing=dp(12), padding=dp(22),
                         pos_hint={"center_x": 0.5, "center_y": 0.62})
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
            bd.rounded_rectangle = (card.x, card.y, card.width,
                                    card.height, dp(26))
        card.bind(pos=upd, size=upd)

        card.add_widget(TLabel(text=GAME_NAME.upper(), halign="center",
                               bold=True, font_size=sp(30), color=GREEN,
                               size_hint_y=None, height=dp(44)))
        card.add_widget(TLabel(text="Başlamadan önce kullanıcı adını seç",
                               halign="center", font_size=sp(16),
                               color=(1, 1, 1, 0.85),
                               size_hint_y=None, height=dp(28)))
        self.input = TextInput(multiline=False, hint_text="Kullanıcı adı",
                               font_size=sp(22), size_hint_y=None, height=dp(56),
                               padding=[dp(14), dp(14)],
                               background_normal="", background_active="",
                               background_color=(0.03, 0.07, 0.17, 1),
                               foreground_color=(1, 1, 1, 1),
                               cursor_color=GREEN,
                               hint_text_color=(1, 1, 1, 0.4),
                               write_tab=False)
        self.input.bind(text=self._limit,
                        on_text_validate=lambda *a: self.confirm())
        card.add_widget(self.input)
        self.err = TLabel(text="", halign="center", color=RED,
                          font_size=sp(14),
                          size_hint_y=None, height=dp(22))
        card.add_widget(self.err)
        btn = RoundedButton(text="BAŞLA", bg=GREEN, font_size=sp(20))
        btn.bind(on_release=lambda *a: self.confirm())
        card.add_widget(btn)
        self.add_widget(card)

    def _limit(self, inst, value):
        if len(value) > 20:
            inst.text = value[:20]

    def confirm(self):
        name = " ".join(self.input.text.split())
        if len(name) < 2:
            self.err.text = "Kullanıcı adı en az 2 karakter olmalı"
            return
        first_time = not save.username
        save.set_username(name)
        if first_time and name == _SECRET_CODE:
            save.add_points(10000)
        self.input.focus = False
        goto(start_screen())

    def on_back(self):
        pass


# ============================================================================
# BAŞLANGIÇ FUTBOLCUSU SEÇİM KARTI (YUVARLAK FOTO + FOTO EKLE)
# ============================================================================
class StarterCard(BoxLayout):
    def __init__(self, name, on_pick, on_upload=None, **kw):
        super().__init__(orientation="vertical", padding=dp(8),
                         spacing=dp(4), **kw)
        self.pname = name
        self.on_pick = on_pick
        self.on_upload = on_upload
        self.is_custom = (name == "__self__")
        with self.canvas.before:
            Color(0.07, 0.14, 0.30, 1)
            self._bg = RoundedRectangle(radius=[dp(18)])
            self._bc = Color(1, 1, 1, 0.15)
            self._bd = Line(rounded_rectangle=(0, 0, 1, 1, dp(18)), width=dp(2))
        self.bind(pos=self._upd, size=self._upd)

        self.round = RoundPhoto(ring=GREEN, size_hint=(1, 0.70))
        self.round.pos_hint = {"center_x": 0.5}
        self.lbl = TLabel(text=name if name != "__self__" else "KENDİM",
                          halign="center", bold=True, font_size=sp(14),
                          shorten=True, shorten_from="right",
                          size_hint=(1, 0.14))
        self.add_widget(self.round)
        self.add_widget(self.lbl)
        if on_upload is not None:
            self.upload_btn = RoundedButton(text="FOTO EKLE",
                                            bg=(0.10, 0.55, 0.85, 1),
                                            font_size=sp(11),
                                            size_hint=(1, 0.16))
            self.upload_btn.bind(on_release=lambda *a: self.on_upload(self))
            self.add_widget(self.upload_btn)
        else:
            self.upload_btn = None

        if name == "__self__":
            p = user_photo_path()
            if p:
                self.round.set_path(p)
            else:
                self.lbl.text = "FOTO EKLE →"
        else:
            self._load_photo_for(name)

    def _load_photo_for(self, name):
        from player_data import STARTER_CHOICES
        slug = slugify(name)
        wiki = dict(STARTER_CHOICES).get(name, name)
        photos.request(slug, wiki, self._photo_ready, name)

    def _photo_ready(self, path):
        if path:
            self.round.set_path(path)

    def _upd(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._bd.rounded_rectangle = (self.x, self.y, self.width,
                                      self.height, dp(18))

    def set_selected(self, on):
        self._bc.rgba = (GREEN[0], GREEN[1], GREEN[2], 1) if on else (1, 1, 1, 0.15)

    def refresh_user_photo(self):
        if self.is_custom:
            p = user_photo_path()
            if p:
                self.round.set_path(p)
                self.lbl.text = "KENDİM"
            else:
                self.lbl.text = "FOTO EKLE →"

    def on_touch_up(self, touch):
        if touch.grab_current is None and self.collide_point(*touch.pos) \
                and not touch.is_mouse_scrolling:
            if self.upload_btn is not None and \
                    self.upload_btn.collide_point(*touch.pos):
                return super().on_touch_up(touch)
            self.on_pick(self)
        return super().on_touch_up(touch)


# ============================================================================
# BAŞLANGIÇ EKRANI
# ============================================================================
class StarterScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.choice = None
        root = BoxLayout(orientation="vertical",
                         padding=[dp(26), dp(22), dp(26), dp(18)],
                         spacing=dp(10))
        root.add_widget(TLabel(text="BAŞLANGIÇ FUTBOLCUNU SEÇ",
                               halign="center", bold=True, font_size=sp(24),
                               color=GREEN, size_hint_y=None, height=dp(40)))
        root.add_widget(TLabel(
            text="Bir yıldız seç ya da kendi fotoğrafını ekle (o zaman sen olursun)",
            halign="center", font_size=sp(13), color=(1, 1, 1, 0.75),
            size_hint_y=None, height=dp(22)))

        grid = GridLayout(cols=4, rows=2, spacing=dp(10))
        self.cards = []
        all_cards = list(STARTER_CHOICES) + [("__self__", "__self__")]
        for name, _wiki in all_cards:
            is_self = (name == "__self__")
            c = StarterCard(name, self._pick,
                            on_upload=(self._upload_photo if is_self else None))
            self.cards.append(c)
            grid.add_widget(c)
        root.add_widget(grid)

        self.btn = RoundedButton(text="BİR FUTBOLCU SEÇ", bg=GREEN,
                                 font_size=sp(20), size_hint_y=None,
                                 height=dp(56), disabled=True)
        self.btn.bind(on_release=lambda *a: self.confirm())
        root.add_widget(self.btn)
        self.add_widget(root)

    def on_pre_enter(self, *a):
        self.choice = None
        self.btn.disabled = True
        self.btn.text = "BİR FUTBOLCU SEÇ"
        for c in self.cards:
            c.set_selected(False)
        self._ev = Clock.schedule_interval(self._retry_photos, 2.0)

    def on_leave(self, *a):
        ev = getattr(self, "_ev", None)
        if ev:
            ev.cancel()
            self._ev = None

    def _retry_photos(self, dt):
        for c in self.cards:
            if c.is_custom:
                c.refresh_user_photo()

    def _pick(self, card):
        self.choice = card.pname
        for c in self.cards:
            c.set_selected(c is card)
        self.btn.disabled = False
        if card.pname == "__self__":
            if user_photo_path():
                self.btn.text = "KENDİM İLE BAŞLA"
            else:
                self.btn.text = "ÖNCE FOTO EKLE"
                self.btn.disabled = True
        else:
            self.btn.text = "%s İLE BAŞLA" % card.pname.upper()

    def _upload_photo(self, card):
        picker = PhotoPickerPopup(self._photo_chosen)
        picker.show(self)

    def _photo_chosen(self, path):
        saved = copy_user_photo(path)
        if not saved:
            toast(self, "Fotoğraf kopyalanamadı", RED, 1.6)
            return
        for c in self.cards:
            if c.is_custom:
                c.refresh_user_photo()
                self._pick(c)
        toast(self, "Fotoğraf eklendi!", GREEN_DARK, 1.4)

    def confirm(self):
        if not self.choice:
            return
        if self.choice == "__self__":
            save.set_starter("__self__", is_self=True)
            set_starter_from_user()
            save.select_avatar("starter")
        else:
            save.set_starter(self.choice, is_self=False)
            set_starter(self.choice)
            save.select_avatar("starter")
        goto("menu")

    def on_back(self):
        pass


# ============================================================================
# ANA MENÜ
# ============================================================================
class MenuScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(**kw)

        # Sağ üst: AYARLAR + ÇIK
        top_right = BoxLayout(orientation="horizontal", spacing=dp(8),
                              size_hint=(None, None),
                              size=(dp(240), dp(44)),
                              pos_hint={"right": 0.985, "top": 0.985})
        settings_btn = RoundedButton(text="AYARLAR", bg=NAVY_LIGHT,
                                     font_size=sp(13),
                                     size_hint=(None, 1), width=dp(140))
        exit_btn = RoundedButton(text="ÇIK", bg=(0.75, 0.15, 0.15, 1),
                                 font_size=sp(13),
                                 size_hint=(None, 1), width=dp(80))
        settings_btn.bind(on_release=lambda *a: goto("settings"))
        exit_btn.bind(on_release=lambda *a: App.get_running_app().stop())
        top_right.add_widget(settings_btn)
        top_right.add_widget(exit_btn)
        self.add_widget(top_right)

        root = BoxLayout(orientation="horizontal",
                         padding=[dp(26), dp(62), dp(26), dp(18)],
                         spacing=dp(26))
        left = BoxLayout(orientation="vertical", spacing=dp(6),
                         size_hint_x=0.45)

        # Yuvarlak küçük avatar
        avatar_box = FloatLayout(size_hint_y=0.55)
        self.avatar = RoundPhoto(ring=GREEN, size_hint=(None, None),
                                 size=(dp(170), dp(170)),
                                 pos_hint={"center_x": 0.5, "center_y": 0.55})
        avatar_box.add_widget(self.avatar)
        self.name_lbl = TLabel(text="", halign="center", bold=True,
                               font_size=sp(22), size_hint_y=0.13)
        self.power_lbl = TLabel(text="", halign="center", bold=True,
                                font_size=sp(15), color=GOLD,
                                size_hint_y=0.10)
        self.power_bar = BarWidget(maximum=100, size_hint=(0.7, None),
                                   height=dp(10),
                                   pos_hint={"center_x": 0.5})

        # PAYLAŞ butonu
        self.share_btn = RoundedButton(
            text="📤  PAYLAŞ",
            bg=(0.20, 0.55, 0.85, 1),
            font_size=sp(15),
            size_hint=(0.75, None), height=dp(44),
            pos_hint={"center_x": 0.5})
        self.share_btn.bind(on_release=lambda *a: self._open_share())

        left.add_widget(avatar_box)
        left.add_widget(self.name_lbl)
        left.add_widget(self.power_lbl)
        left.add_widget(self.power_bar)
        left.add_widget(Widget(size_hint_y=0.06))
        left.add_widget(self.share_btn)

        right = BoxLayout(orientation="vertical", spacing=dp(14))
        right.add_widget(TLabel(text=GAME_NAME.upper(), halign="center",
                                bold=True, font_size=sp(30), color=GREEN,
                                size_hint_y=None, height=dp(46)))
        b1 = RoundedButton(text="OYUNA BAŞLA", bg=GREEN, font_size=sp(24))
        b2 = RoundedButton(text="MAĞAZA", bg=NAVY_LIGHT, font_size=sp(24))
        b3 = RoundedButton(text="PENALTI", bg=(0.80, 0.52, 0.08, 1),
                           font_size=sp(24))
        b1.bind(on_release=lambda *a: goto("mode"))
        b2.bind(on_release=lambda *a: goto("shop"))
        b3.bind(on_release=lambda *a: goto("penalty"))
        for b in (b1, b2, b3):
            right.add_widget(b)
        self.stats_lbl = TLabel(text="", halign="center", font_size=sp(13),
                                color=(1, 1, 1, 0.75),
                                size_hint_y=None, height=dp(28))
        right.add_widget(self.stats_lbl)
        self.music_lbl = TLabel(text="", halign="center", font_size=sp(11),
                                color=(1, 1, 1, 0.45),
                                size_hint_y=None, height=dp(20))
        right.add_widget(self.music_lbl)
        root.add_widget(left)
        root.add_widget(right)
        self.add_widget(root)

    def on_pre_enter(self, *a):
        p = get_player(save.selected_avatar)
        if save.selected_avatar == "starter" and save.starter_is_self:
            up = user_photo_path()
            if up:
                self.avatar.set_path(up)
            else:
                self.avatar.set_texture(None)
        else:
            self.avatar.set_texture(None)
            if p.wiki:
                photos.request(slugify(p.name), p.wiki,
                               self._menu_photo, p.name)
        self.name_lbl.text = p.name
        self.power_lbl.text = "GÜÇ SEVİYESİ %d" % p.power
        self.power_bar.value = p.power
        s = save.stats
        self.stats_lbl.text = ("Doğru: %d   Yanlış: %d   En iyi seri: %d   "
                               "Özel penaltı hakkı: %d"
                               % (s["correct"], s["wrong"],
                                  s["best_streak"], save.special_rights))

    def _menu_photo(self, path):
        if path:
            self.avatar.set_path(path)

    def _open_share(self):
        """Paylaşım kartını aç. Avatarı da yuvarlak olarak içine koy."""
        # Avatarı kopyala
        def make_avatar():
            av = RoundPhoto(ring=GOLD, size_hint=(None, None),
                            size=(dp(140), dp(140)),
                            pos_hint={"center_x": 0.5, "center_y": 0.5})
            # Aynı fotoğrafı göster
            if save.selected_avatar == "starter" and save.starter_is_self:
                up = user_photo_path()
                if up:
                    av.set_path(up)
            else:
                p = get_player(save.selected_avatar)
                if p.wiki:
                    def cb(path):
                        if path:
                            av.set_path(path)
                    photos.request(slugify(p.name), p.wiki, cb, p.name)
            return av

        popup = SharePopup(avatar_widget_factory=make_avatar)
        popup.show(self)

    def on_enter(self, *a):
        pass

    def on_leave(self, *a):
        pass

    def on_back(self):
        pass


# ============================================================================
# AYARLAR
# ============================================================================
class SettingsScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        card = BoxLayout(orientation="vertical", size_hint=(None, None),
                         size=(dp(560), dp(440)), spacing=dp(10), padding=dp(24),
                         pos_hint={"center_x": 0.5, "center_y": 0.5})
        with card.canvas.before:
            Color(0, 0, 0, 0.35)
            sh = RoundedRectangle(radius=[dp(24)])
            Color(*NAVY_LIGHT)
            bg = RoundedRectangle(radius=[dp(24)])
            Color(*GREEN)
            bd = Line(rounded_rectangle=(0, 0, 1, 1, dp(24)), width=dp(2))

        def upd(*a):
            sh.pos = (card.x, card.y - dp(4))
            sh.size = card.size
            bg.pos = card.pos
            bg.size = card.size
            bd.rounded_rectangle = (card.x, card.y, card.width,
                                    card.height, dp(24))
        card.bind(pos=upd, size=upd)

        card.add_widget(TLabel(text="AYARLAR", halign="center", bold=True,
                               font_size=sp(26), color=GREEN,
                               size_hint_y=None, height=dp(44)))
        card.add_widget(Widget(size_hint_y=None, height=dp(4)))

        self.user_lbl = TLabel(text="", halign="left", bold=True,
                               font_size=sp(16),
                               size_hint_y=None, height=dp(30))
        self.date_lbl = TLabel(text="", halign="left", font_size=sp(14),
                               color=(1, 1, 1, 0.85),
                               size_hint_y=None, height=dp(26))
        self.pts_lbl = TLabel(text="", halign="left", bold=True,
                              font_size=sp(14), color=GOLD,
                              size_hint_y=None, height=dp(26))
        self.streak_lbl = TLabel(text="", halign="left", font_size=sp(14),
                                 color=(1, 1, 1, 0.85),
                                 size_hint_y=None, height=dp(26))
        self.daily_lbl = TLabel(text="", halign="left", font_size=sp(14),
                                color=(1, 1, 1, 0.85),
                                size_hint_y=None, height=dp(26))
        self.avatar_lbl = TLabel(text="", halign="left", font_size=sp(14),
                                 color=(1, 1, 1, 0.85),
                                 size_hint_y=None, height=dp(26))
        card.add_widget(self.user_lbl)
        card.add_widget(self.date_lbl)
        card.add_widget(self.pts_lbl)
        card.add_widget(self.streak_lbl)
        card.add_widget(self.daily_lbl)
        card.add_widget(self.avatar_lbl)
        card.add_widget(Widget())

        back = RoundedButton(text="GERİ", bg=NAVY_LIGHT, font_size=sp(16),
                             size_hint_y=None, height=dp(50))
        back.bind(on_release=lambda *a: goto("menu"))
        card.add_widget(back)
        self.add_widget(card)

    def on_pre_enter(self, *a):
        self.user_lbl.text = "Kullanıcı Adı:  %s" % (save.username or "-")
        ts = save.created_at
        if ts:
            dt = datetime.datetime.fromtimestamp(ts)
            self.date_lbl.text = ("Hesap Açma Tarihi:  %s"
                                  % dt.strftime("%d.%m.%Y  %H:%M"))
        else:
            self.date_lbl.text = "Hesap Açma Tarihi:  -"
        self.pts_lbl.text = "Toplam Puan:  %d" % save.points
        self.streak_lbl.text = "Günlük Giriş Serisi:  %d gün" % save.login_streak
        self.daily_lbl.text = ("Günlükten Kazanılan:  %d puan (her gün +%d)"
                               % (save.daily_reward_total, DAILY_REWARD))
        p = get_player(save.selected_avatar)
        self.avatar_lbl.text = "Seçili Avatar:  %s" % p.name

    def on_back(self):
        goto("menu")


# ============================================================================
# ANA UYGULAMA
# ============================================================================
class FootballApp(App):
    title = GAME_NAME

    def build(self):
        save.init(self.user_data_dir)
        if save.starter_is_self:
            set_starter_from_user()
        elif save.starter:
            set_starter(save.starter)
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
        self.sm.add_widget(SettingsScreen(name="settings"))
        root.add_widget(self.sm)

        from ui_system import HeaderBar
        self.header = HeaderBar(pos_hint={"x": 0.012, "top": 0.985})
        root.add_widget(self.header)

        self.sm.bind(current=self._on_screen)

        # Günlük giriş ödülü (kullanıcı adı girilmişse kontrol et)
        self._check_daily_reward_on_menu = False

        # Yükleme ekranı: indirilmemiş fotoğraflar varsa
        pending = [it for it in all_photo_items()
                   if not photos.find_local(it[0])]
        if pending:
            self.sm.current = "loading"
            self._on_screen(self.sm, "loading")
            self.loading.begin(pending)
        else:
            # Yükleme yok → doğrudan başla
            self.sm.current = start_screen()
            self._on_screen(self.sm, self.sm.current)
            Clock.schedule_once(lambda dt: self._daily_reward_check(), 0.6)

        Window.bind(on_keyboard=self._on_keyboard)
        return root

    _MUSIC = {
        "menu": ("music_menu", "music"),
        "mode": ("music_menu", "music"),
        "shop": ("music_menu", "music"),
        "username": ("music_menu", "music"),
        "starter": ("music_menu", "music"),
        "settings": ("music_menu", "music"),
        "quiz": ("music_quiz", "music"),
        "penalty": ("taraftar", "music_penalty", "music"),
    }

    def _on_screen(self, sm, name):
        self.header.opacity = 0 if name in ("username", "loading",
                                            "starter") else 1
        self._update_music(name)
        # Menüye her girildiğinde günlük ödül kontrolü (bir kere)
        if name == "menu" and save.username and not \
                self._check_daily_reward_on_menu:
            self._check_daily_reward_on_menu = True
            Clock.schedule_once(lambda dt: self._daily_reward_check(), 0.5)

    def _daily_reward_check(self):
        """Günlük giriş ödülünü kontrol et, alındıysa göster."""
        if not save.username:
            return
        got, amount, streak = save.check_daily_login()
        if got:
            from ui_system import Overlay, GOLD as _GOLD, GOLD_DARK as _GOLD_DARK
            overlay = Overlay(
                "GÜNLÜK GİRİŞ ÖDÜLÜ!",
                "+%d PUAN\n\nGün serisi: %d 🔥\nHer gün gir, ödülünü kaçırma!" % (
                    amount, streak),
                [("HARİKA!", lambda: overlay.dismiss(), _GOLD_DARK)],
                title_color=_GOLD)
            overlay.show(self.sm.current_screen)

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
        if key == 27:
            cur = self.sm.current
            if cur in ("menu", "username", "starter", "settings"):
                return False
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