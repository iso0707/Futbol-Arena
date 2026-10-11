# -*- coding: utf-8 -*-
"""Kalıcı kayıt sistemi.

- JSON dosyası uygulamanın özel veri klasöründe saklanır (Android'de silinmez).
- Atomik yazma: önce geçici dosyaya yazılır, sonra yer değiştirilir.
- Her yazımdan önce eski kayıt .bak olarak yedeklenir; ana dosya bozulursa yedek okunur.
- Her değişiklik anında diske yazılır ve dinleyicilere (üst bar vb.) bildirilir.
"""
import copy
import json
import os
import shutil
import tempfile
import threading

DEFAULT_DATA = {
    "version": 1,
    "username": "",
    "points": 0,
    "owned": ["starter"],
    "selected_avatar": "starter",
    "special_penalty_rights": 0,
    "stats": {
        "correct": 0,
        "wrong": 0,
        "best_streak": 0,
        "easy_correct": 0,
        "hard_correct": 0,
        "games_played": 0,
        "penalty_shots": 0,
        "penalty_goals": 0,
        "penalty_saved": 0,
        "penalty_missed": 0,
        "special_goals": 0,
    },
}


def _merge(defaults, raw):
    """Eksik/bozuk alanları varsayılanlarla tamamlar, tipleri doğrular."""
    if not isinstance(raw, dict):
        raw = {}
    out = {}
    for key, dv in defaults.items():
        rv = raw.get(key, dv)
        if isinstance(dv, dict):
            out[key] = _merge(dv, rv)
        elif isinstance(dv, bool):
            out[key] = rv if isinstance(rv, bool) else dv
        elif isinstance(dv, int):
            ok = isinstance(rv, int) and not isinstance(rv, bool)
            out[key] = rv if ok else dv
        elif isinstance(dv, str):
            out[key] = rv if isinstance(rv, str) else dv
        elif isinstance(dv, list):
            out[key] = [str(i) for i in rv] if isinstance(rv, list) else list(dv)
        else:
            out[key] = rv
    return out


class SaveSystem:
    def __init__(self):
        self.data = copy.deepcopy(DEFAULT_DATA)
        self.path = None
        self.backup = None
        self._lock = threading.RLock()
        self._listeners = []

    # ------------------------------------------------------------ yükleme
    def init(self, directory):
        os.makedirs(directory, exist_ok=True)
        self.path = os.path.join(directory, "save.json")
        self.backup = self.path + ".bak"
        self.load()

    def load(self):
        for p in (self.path, self.backup):
            if not p or not os.path.isfile(p):
                continue
            try:
                with open(p, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                self.data = _merge(DEFAULT_DATA, raw)
                self._sanitize()
                return
            except Exception:
                continue
        self.data = copy.deepcopy(DEFAULT_DATA)

    def _sanitize(self):
        d = self.data
        d["points"] = max(0, d["points"])
        d["special_penalty_rights"] = max(0, d["special_penalty_rights"])
        if "starter" not in d["owned"]:
            d["owned"].insert(0, "starter")
        d["owned"] = list(dict.fromkeys(d["owned"]))
        if d["selected_avatar"] not in d["owned"]:
            d["selected_avatar"] = "starter"

    # ------------------------------------------------------------ yazma
    def flush(self):
        if not self.path:
            return False
        with self._lock:
            tmp = None
            try:
                payload = json.dumps(self.data, ensure_ascii=False, indent=2)
                fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path),
                                           prefix="save_", suffix=".tmp")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(payload)
                    f.flush()
                    os.fsync(f.fileno())
                if os.path.exists(self.path):
                    try:
                        shutil.copy2(self.path, self.backup)
                    except OSError:
                        pass
                os.replace(tmp, self.path)
                return True
            except Exception:
                if tmp and os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
                return False

    def _commit(self):
        self.flush()
        self._notify()

    # ------------------------------------------------------------ dinleyiciler
    def subscribe(self, fn):
        if fn not in self._listeners:
            self._listeners.append(fn)

    def unsubscribe(self, fn):
        if fn in self._listeners:
            self._listeners.remove(fn)

    def _notify(self):
        for fn in list(self._listeners):
            try:
                fn()
            except Exception:
                pass

    # ------------------------------------------------------------ okuma
    @property
    def username(self):
        return self.data["username"]

    @property
    def points(self):
        return self.data["points"]

    @property
    def owned(self):
        return list(self.data["owned"])

    @property
    def selected_avatar(self):
        return self.data["selected_avatar"]

    @property
    def special_rights(self):
        return self.data["special_penalty_rights"]

    @property
    def stats(self):
        return self.data["stats"]

    def owns(self, pid):
        return pid in self.data["owned"]

    # ------------------------------------------------------------ işlemler
    def set_username(self, name):
        with self._lock:
            self.data["username"] = name.strip()
            self._commit()

    def add_points(self, n):
        with self._lock:
            self.data["points"] = max(0, self.data["points"] + int(n))
            self._commit()

    def buy_player(self, pid, price):
        """(başarılı_mı, neden) döndürür. Puan düşme + koleksiyona ekleme tek adımda."""
        with self._lock:
            if pid in self.data["owned"]:
                return False, "owned"
            if self.data["points"] < price:
                return False, "points"
            self.data["points"] -= price
            self.data["owned"].append(pid)
            self._commit()
            return True, "ok"

    def select_avatar(self, pid):
        with self._lock:
            if pid not in self.data["owned"]:
                return False
            self.data["selected_avatar"] = pid
            self._commit()
            return True

    def begin_game(self):
        with self._lock:
            self.data["stats"]["games_played"] += 1
            self._commit()

    def record_answer(self, correct, points, streak, mode):
        with self._lock:
            s = self.data["stats"]
            if correct:
                self.data["points"] += int(points)
                s["correct"] += 1
                s[mode + "_correct"] = s.get(mode + "_correct", 0) + 1
                if streak > s["best_streak"]:
                    s["best_streak"] = streak
            else:
                s["wrong"] += 1
            self._commit()

    def grant_special_right(self, n=1):
        with self._lock:
            self.data["special_penalty_rights"] += n
            self._commit()

    def record_penalty(self, outcome, special=False):
        """outcome: 'goal' | 'saved' | 'miss'. Verilen puanı döndürür.
        Puan ekleme, hak tüketme ve istatistik tek kayıt işleminde yapılır."""
        gained = 0
        with self._lock:
            s = self.data["stats"]
            s["penalty_shots"] += 1
            if outcome == "goal":
                s["penalty_goals"] += 1
                if special and self.data["special_penalty_rights"] > 0:
                    gained = 25
                    self.data["special_penalty_rights"] -= 1
                    s["special_goals"] += 1
                else:
                    gained = 1
                self.data["points"] += gained
            elif outcome == "saved":
                s["penalty_saved"] += 1
            else:
                s["penalty_missed"] += 1
            self._commit()
        return gained


save = SaveSystem()
