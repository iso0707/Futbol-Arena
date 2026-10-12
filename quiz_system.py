# -*- coding: utf-8 -*-
"""Futbolcu tahmin oyunu: PAS joker, 1100 futbolcu, 25'lik seri ödülü."""
import random
from collections import deque, namedtuple

from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.app import App

from player_data import EASY_POOL, HARD_POOL
from save_system import save, PASS_DAILY_LIMIT, PASS_COST
from ui_system import (BarWidget, toast, BaseScreen, GOLD_DARK, GREEN, GREEN_DARK,
                       GOLD, NAVY_LIGHT, Overlay, PlayerPhoto, RED, RoundedButton,
                       TLabel, WHITE, goto, photos, play_sound)

STREAK_GOAL = 25
JOKERS_PER_GAME = 3
Question = namedtuple("Question", "player options correct")


class QuizEngine:
    """Soru üretir: 700+400 futbolcu havuzu."""

    def __init__(self, mode):
        self.mode = mode
        self.pool = EASY_POOL if mode == "easy" else HARD_POOL
        self.points = 1 if mode == "easy" else 2
        self.recent = deque(maxlen=min(20, max(1, len(self.pool) // 3)))

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


class QuizModeScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical",
                         padding=[dp(40), dp(70), dp(40), dp(24)],
                         spacing=dp(16))
        root.add_widget(TLabel(text="MOD SEÇ", halign="center", bold=True,
                               font_size=sp(30), size_hint_y=None, height=dp(44)))
        row = BoxLayout(orientation="horizontal", spacing=dp(22))
        easy = RoundedButton(
            text="KOLAY MOD\n[size=%d]700 popüler futbolcu  •  +1 puan[/size]" % int(sp(14)),
            markup=True, bg=GREEN, font_size=sp(24))
        hard = RoundedButton(
            text="ZOR MOD\n[size=%d]400 efsane futbolcu  •  +2 puan[/size]" % int(sp(14)),
            markup=True, bg=GOLD_DARK, font_size=sp(24))
        easy.bind(on_release=lambda *a: self.start("easy"))
        hard.bind(on_release=lambda *a: self.start("hard"))
        row.add_widget(easy)
        row.add_widget(hard)
        root.add_widget(row)
        back = RoundedButton(text="GERİ", bg=NAVY_LIGHT, size_hint=(None, None),
                             size=(dp(160), dp(48)),
                             pos_hint={"center_x": 0.5})
        back.bind(on_release=lambda *a: goto("menu"))
        root.add_widget(back)
        self.add_widget(root)

    def start(self, mode):
        quiz = App.get_running_app().sm.get_screen("quiz")
        quiz.start(mode)
        goto("quiz")


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
        self.pass_used_q = False

        root = BoxLayout(orientation="horizontal",
                         padding=[dp(18), dp(70), dp(18), dp(14)],
                         spacing=dp(18))
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
        right.add_widget(TLabel(text="Bu futbolcu kim?", bold=True,
                                font_size=sp(21),
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

        # Sağ üst: PAS + JOKER + GERİ
        topright = BoxLayout(orientation="horizontal", spacing=dp(8),
                             size_hint=(None, None), size=(dp(420), dp(44)),
                             pos_hint={"right": 0.99, "top": 0.985})
        self.pass_btn = RoundedButton(text="", bg=(0.10, 0.55, 0.85, 1),
                                      font_size=sp(13),
                                      size_hint=(None, 1), width=dp(150))
        self.pass_btn.bind(on_release=lambda *a: self.use_pass())
        self.joker_btn = RoundedButton(text="", bg=GOLD_DARK, font_size=sp(13),
                                       size_hint=(None, 1), width=dp(150))
        self.joker_btn.bind(on_release=lambda *a: self.use_joker())
        back = RoundedButton(text="GERİ", bg=NAVY_LIGHT, font_size=sp(13),
                             size_hint=(None, 1), width=dp(100))
        back.bind(on_release=lambda *a: self.on_back())
        topright.add_widget(self.pass_btn)
        topright.add_widget(self.joker_btn)
        topright.add_widget(back)
        self.add_widget(topright)
        self._update_buttons()

    def _update_buttons(self):
        self.joker_btn.text = "JOKER x%d" % self.jokers
        self.joker_btn.bg = list(GOLD_DARK if self.jokers > 0
                                 else (0.35, 0.40, 0.50, 1))
        left = save.pass_left
        self.pass_btn.text = "PAS x%d" % left
        can = (left > 0) and (save.points >= PASS_COST)
        self.pass_btn.bg = list((0.10, 0.55, 0.85, 1) if can
                                else (0.35, 0.40, 0.50, 1))

    def use_joker(self):
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
        self._update_buttons()
        self.msg.text = "JOKER: 2 yanlış şık elendi  •  Kalan: %d" % self.jokers
        self.msg.color = GOLD
        play_sound("buy")

    def use_pass(self):
        """PAS joker: -1 puan, soruyu atla, seri BOZULMAZ."""
        if self.locked or not self.current:
            return
        if self.pass_used_q:
            toast(self, "Bu soruda zaten pas kullandın", RED, 1.4)
            return
        if save.pass_left <= 0:
            toast(self, "Bugünlük pas hakkın bitti (max %d)" % PASS_DAILY_LIMIT,
                  RED, 1.6)
            return
        if save.points < PASS_COST:
            toast(self, "Yetersiz puan (pas için %d gerek)" % PASS_COST,
                  RED, 1.6)
            return
        if not save.use_pass():
            return
        self.pass_used_q = True
        self.locked = True
        self.msg.text = "PAS! Soru atlandı  (-%d puan, seri korundu)" % PASS_COST
        self.msg.color = (0.10, 0.55, 0.85, 1)
        play_sound("buy")
        self._update_buttons()
        q = self.current
        self.buttons[q.correct].bg = list(GREEN)
        self._schedule(1.2, self._show_next)

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
        self._update_buttons()
        self.mode_lbl.text = ("KOLAY MOD  •  +1" if mode == "easy"
                              else "ZOR MOD  •  +2")
        self._update_streak()
        self._fill_queue()
        self._show_next()

    def _fill_queue(self):
        while len(self.queue) < 2:
            q = self.engine.next_question()
            self.queue.append(q)
            p = q.player
            photos.request(p.slug, p.wiki, lambda path: None, p.name)

    def _show_next(self, *a):
        if not self.engine:
            return
        self.current = self.queue.pop(0)
        self._fill_queue()
        self._token += 1
        tok = self._token
        self.locked = True
        self.joker_used_q = False
        self.pass_used_q = False
        for i, b in enumerate(self.buttons):
            b.text = self.current.options[i]
            b.bg = list(NAVY_LIGHT)
            b.opacity = 1
            b.disabled = True
        self.msg.text = ""
        self.photo.show_loading()
        p = self.current.player
        photos.request(p.slug, p.wiki,
                       lambda path, tok=tok: self._photo_done(tok, path),
                       p.name)
        self._schedule(8.0, lambda dt, tok=tok: self._photo_done(tok, None))
        self._update_buttons()

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
        self.locked = True
        q = self.current
        ok = (i == q.correct)
        self.buttons[q.correct].bg = list(GREEN)
        if ok:
            self.streak += 1
            save.record_answer(True, self.engine.points, self.streak,
                               self.engine.mode)
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