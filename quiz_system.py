# -*- coding: utf-8 -*-
"""Futbolcu tahmin oyunu: mod seçimi, soru motoru, oyun ekranı, 25'lik seri ödülü."""
import random
from collections import deque, namedtuple

from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout

from player_data import EASY_POOL, HARD_POOL
from save_system import save
from ui_system import (BarWidget, BaseScreen, GOLD_DARK, GREEN, GREEN_DARK, GOLD,
                       NAVY_LIGHT, Overlay, PlayerPhoto, RED, RoundedButton, TLabel,
                       WHITE, goto, photos, play_sound)
from kivy.app import App

STREAK_GOAL = 25
Question = namedtuple("Question", "player options correct")


class QuizEngine:
    """Soru üretir: havuzlar ayrı, yakın zamanda sorulanlar tekrarlanmaz."""

    def __init__(self, mode):
        self.mode = mode
        self.pool = EASY_POOL if mode == "easy" else HARD_POOL
        self.points = 1 if mode == "easy" else 2
        self.recent = deque(maxlen=min(15, max(1, len(self.pool) // 2)))

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


# ----------------------------------------------------------------------------
class QuizModeScreen(BaseScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        root = BoxLayout(orientation="vertical", padding=[dp(40), dp(70), dp(40), dp(24)],
                         spacing=dp(16))
        root.add_widget(TLabel(text="MOD SEÇ", halign="center", bold=True,
                               font_size=sp(30), size_hint_y=None, height=dp(44)))
        row = BoxLayout(orientation="horizontal", spacing=dp(22))
        easy = RoundedButton(
            text="KOLAY MOD\n[size=%d]Popüler yıldızlar  •  Doğru cevap +1 puan[/size]" % int(sp(14)),
            markup=True, bg=GREEN, font_size=sp(26))
        hard = RoundedButton(
            text="ZOR MOD\n[size=%d]Efsaneler ve az bilinenler  •  Doğru cevap +2 puan[/size]" % int(sp(14)),
            markup=True, bg=GOLD_DARK, font_size=sp(26))
        easy.bind(on_release=lambda *a: self.start("easy"))
        hard.bind(on_release=lambda *a: self.start("hard"))
        row.add_widget(easy)
        row.add_widget(hard)
        root.add_widget(row)
        back = RoundedButton(text="GERİ", bg=NAVY_LIGHT, size_hint=(None, None),
                             size=(dp(160), dp(48)), pos_hint={"center_x": 0.5})
        back.bind(on_release=lambda *a: goto("menu"))
        root.add_widget(back)
        self.add_widget(root)

    def start(self, mode):
        quiz = App.get_running_app().sm.get_screen("quiz")
        quiz.start(mode)
        goto("quiz")


# ----------------------------------------------------------------------------
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

        root = BoxLayout(orientation="horizontal",
                         padding=[dp(18), dp(70), dp(18), dp(14)], spacing=dp(18))
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
        right.add_widget(TLabel(text="Bu futbolcu kim?", bold=True, font_size=sp(21),
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

        back = RoundedButton(text="GERİ", bg=NAVY_LIGHT, size_hint=(None, None),
                             size=(dp(100), dp(44)), pos_hint={"right": 0.99, "top": 0.985})
        back.bind(on_release=lambda *a: self.on_back())
        self.add_widget(back)

    # -- yardımcılar ---------------------------------------------------
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

    # -- oyun akışı ----------------------------------------------------
    def start(self, mode):
        self._cancel_events()
        if self.overlay:
            self.overlay.dismiss()
            self.overlay = None
        save.begin_game()
        self.engine = QuizEngine(mode)
        self.queue = []
        self.streak = 0
        self.mode_lbl.text = "KOLAY MOD  •  +1" if mode == "easy" else "ZOR MOD  •  +2"
        self._update_streak()
        self._fill_queue()
        self._show_next()

    def _fill_queue(self):
        while len(self.queue) < 2:
            q = self.engine.next_question()
            self.queue.append(q)
            p = q.player
            photos.request(p.slug, p.wiki, lambda path: None, p.name)   # önceden yükle

    def _show_next(self, *a):
        if not self.engine:
            return
        self.current = self.queue.pop(0)
        self._fill_queue()
        self._token += 1
        tok = self._token
        self.locked = True
        for i, b in enumerate(self.buttons):
            b.text = self.current.options[i]
            b.bg = list(NAVY_LIGHT)
            b.disabled = True
        self.msg.text = ""
        self.photo.show_loading()
        p = self.current.player
        photos.request(p.slug, p.wiki, lambda path, tok=tok: self._photo_done(tok, path), p.name)
        self._schedule(8.0, lambda dt, tok=tok: self._photo_done(tok, None))

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
        self.locked = True                       # çift puan eklenmesini engeller
        q = self.current
        ok = (i == q.correct)
        self.buttons[q.correct].bg = list(GREEN)
        if ok:
            self.streak += 1
            save.record_answer(True, self.engine.points, self.streak, self.engine.mode)
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
