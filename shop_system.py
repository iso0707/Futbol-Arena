# -*- coding: utf-8 -*-
"""Futbolcu mağazası: yuvarlak fotoğraf + satın alma + avatar seçimi."""
from kivy.clock import Clock
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window

from player_data import SHOP_PLAYERS, slugify
from save_system import save
from ui_system import (BarWidget, BaseScreen, GOLD, GOLD_DARK, GREEN, GREEN_DARK,
                       GREY, NAVY_LIGHT, RED, RoundPhoto, RoundedButton, TLabel,
                       goto, photos, play_sound, toast)


class ShopCard(BoxLayout):
    def __init__(self, player, on_action, **kw):
        super().__init__(orientation="horizontal", size_hint_y=None,
                         height=dp(128), padding=dp(10), spacing=dp(10), **kw)
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

        # YUVARLAK fotoğraf
        self.avatar = RoundPhoto(ring=GREEN, size_hint=(None, 1), width=dp(92))
        self._loaded = False
        info = BoxLayout(orientation="vertical", spacing=dp(2))
        self.name_lbl = TLabel(text=player.name, bold=True, font_size=sp(15),
                               shorten=True, shorten_from="right",
                               size_hint_y=0.25)
        prow = BoxLayout(orientation="horizontal", spacing=dp(6),
                         size_hint_y=0.2)
        prow.add_widget(TLabel(text="GÜÇ %d" % player.power, font_size=sp(13),
                               bold=True, color=GOLD,
                               size_hint_x=None, width=dp(62)))
        bar = BarWidget(value=player.power, maximum=100, fill=GREEN,
                        size_hint_y=None, height=dp(8),
                        pos_hint={"center_y": 0.5})
        prow.add_widget(bar)
        self.price_lbl = TLabel(text="", font_size=sp(13), bold=True,
                                size_hint_y=0.2)
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
        self._bd.rounded_rectangle = (self.x, self.y, self.width,
                                      self.height, dp(16))

    def load_photo(self):
        """Fotoğrafı yükle (yerel/önbellek/Wikipedia)."""
        if self._loaded:
            return
        p = self.player
        if p.id == "starter" and not p.wiki:
            from ui_system import user_photo_path
            up = user_photo_path()
            if up:
                self.avatar.set_path(up)
                self._loaded = True
            return
        if not p.wiki:
            return
        self._loaded = True
        photos.request(slugify(p.name), p.wiki, self._photo_ready, p.name)

    def _photo_ready(self, path):
        if path:
            self.avatar.set_path(path)

    def unload_photo(self):
        self._loaded = False
        self.avatar.set_texture(None)

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
        self._bc.rgba = ((GREEN[0], GREEN[1], GREEN[2], 1) if selected
                         else (1, 1, 1, 0.12))


class ShopScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical",
                         padding=[dp(14), dp(66), dp(14), dp(8)],
                         spacing=dp(6))
        self.scroll = ScrollView(do_scroll_x=False, bar_width=dp(4))
        self.grid = GridLayout(cols=3, spacing=dp(12),
                               padding=[0, 0, 0, dp(10)],
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

        title = Label(text="MAĞAZA", bold=True, font_size=sp(26),
                      size_hint=(None, None),
                      size=(dp(200), dp(46)),
                      pos_hint={"center_x": 0.5, "top": 0.985})
        self.add_widget(title)
        back = RoundedButton(text="GERİ", bg=NAVY_LIGHT,
                             size_hint=(None, None),
                             size=(dp(100), dp(44)),
                             pos_hint={"right": 0.99, "top": 0.985})
        back.bind(on_release=lambda *a: goto("menu"))
        self.add_widget(back)

    def on_pre_enter(self, *a):
        self.grid.cols = max(2, min(4, int(Window.width / dp(330))))
        self.refresh_all()
        save.subscribe(self.refresh_all)
        # TÜM fotoğrafları hemen yükle (yükleme ekranında zaten indirildi)
        for c in self.cards:
            c.load_photo()
        self._lazy_ev = Clock.schedule_interval(self._load_visible, 0.35)

    def on_leave(self, *a):
        save.unsubscribe(self.refresh_all)
        ev = getattr(self, "_lazy_ev", None)
        if ev:
            ev.cancel()
            self._lazy_ev = None

    def _load_visible(self, dt):
        """Görünmeyen kartların fotoğraflarını boşalt, görünenleri yükle."""
        sc = self.scroll
        margin = dp(300)
        lo, hi = sc.y - margin, sc.top + margin
        for c in self.cards:
            near = c.top >= lo and c.y <= hi
            if c._loaded and not near and \
                    (c.top < lo - dp(600) or c.y > hi + dp(600)):
                c.unload_photo()
            elif near and not c._loaded:
                c.load_photo()

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
        ok, why = save.buy_player(p.id, p.price)
        if ok:
            play_sound("buy")
            toast(self, "Satın alındı: %s" % p.name, GREEN_DARK)
        elif why == "points":
            toast(self, "Yetersiz puan! Gereken: %d" % p.price, RED)
        else:
            toast(self, "Bu futbolcuya zaten sahipsin", GREY)

    def on_back(self):
        goto("menu")


from kivy.uix.label import Label