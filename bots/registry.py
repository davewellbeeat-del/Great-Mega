"""Bot registry: the list of trading bots on the site.

Bots are created, edited and deleted from the website (Bot Management page) and saved
to data/bots.json, so they survive a restart. Whether a bot is running is NOT saved:
after a restart every bot starts as inactive, which is the safe default.

HOW TO GIVE A BOT REAL TRADING LOGIC
  1. Write a class that extends Bot and implement tick(). It is called every few
     seconds while the bot is active:

         class GreatFlipper2(Bot):
             def tick(self):
                 ...   # read prices, place orders using self.lot_size and self.magic

  2. Register it against the bot's id in BOT_CLASSES (see the bottom of this file).

Until then, every bot is a PLACEHOLDER: it can be activated and stopped, but it places no trades.
"""
import json
import os
import re
import threading
import time
import uuid
from collections import deque
from pathlib import Path

import paths

DATA_DIR = paths.DATA_DIR
BOTS_FILE = DATA_DIR / "bots.json"

MIN_LOT = 0.01
MAX_LOT = 10.0            # safety cap. Raise it on purpose, never by accident.
TICK_SECONDS = 5
INSTRUMENTS = ["Forex", "Gold / Metals", "Indices", "Multiple Instruments"]

DEFAULT_BOTS = [
    {"id": "great_m", "name": "GREAT M", "magic": 27893, "instrument": "Multiple Instruments",
     "description": "Moving average and Parabolic SAR strategy."},
    {"id": "fury_flipper_2", "name": "FURY FLIPPER 2", "magic": 22002, "instrument": "Gold / Metals",
     "description": "Automated trading strategy."},
    {"id": "fury_flipper_3", "name": "FURY FLIPPER 3", "magic": 22003, "instrument": "Multiple Instruments",
     "description": "Advanced trading and position management."},
    {"id": "fury_flipper_4", "name": "FURY FLIPPER 4", "magic": 22004, "instrument": "Multiple Instruments",
     "description": "Higher timeframe trend filter and fractals."},
    {"id": "fury_flipper_5", "name": "FURY FLIPPER 5", "magic": 27895, "instrument": "Multiple Instruments",
     "description": "Multiple entries with profit and equity protection."},
]


class ValidationError(ValueError):
    """The submitted values are not acceptable (HTTP 400)."""


class BotNotFound(LookupError):
    """No bot with that id (HTTP 404)."""


class BotBusy(RuntimeError):
    """The bot is running, so it can't be changed right now (HTTP 409)."""


_lock = threading.RLock()
_bots = []
_activity = deque(maxlen=50)


# ---------------------------------------------------------------------------
class Bot:
    FIELDS = ("id", "name", "description", "magic", "instrument", "file", "lot_size")

    def __init__(self, d: dict):
        self.id = d["id"]
        self.name = d["name"]
        self.description = d.get("description", "")
        self.magic = int(d["magic"])
        self.instrument = d.get("instrument", INSTRUMENTS[-1])
        self.file = d.get("file", "")
        self.lot_size = float(d.get("lot_size", MIN_LOT))
        self.running = False
        self.started_at = None
        self._stop_event = threading.Event()
        self._thread = None

    # ---- override in a real bot -------------------------------------------
    def tick(self) -> None:
        """Called every TICK_SECONDS while the bot is active. Placeholder: does nothing."""

    # ---- internals (always called with the registry lock held) -------------
    def _start(self) -> None:
        self._stop_event = threading.Event()      # fresh event so an old thread can't come back
        self.running = True
        self.started_at = time.time()
        self._thread = threading.Thread(target=self._loop, args=(self._stop_event,),
                                        daemon=True, name=self.id)
        self._thread.start()

    def _stop(self) -> None:
        self._stop_event.set()
        self.running = False
        self.started_at = None

    def _loop(self, stop_event) -> None:
        while not stop_event.wait(TICK_SECONDS):
            try:
                self.tick()
            except Exception as exc:              # a crashing bot must not take the site down
                with _lock:
                    if self.running:
                        self._stop()
                        log(f"{self.name} stopped after an error: {exc}")
                return

    def definition(self) -> dict:
        return {k: getattr(self, k) for k in self.FIELDS}

    def to_dict(self) -> dict:
        d = self.definition()
        d["running"] = self.running
        d["uptime_seconds"] = int(time.time() - self.started_at) if self.started_at else 0
        return d


# Put real strategies here:  BOT_CLASSES = {"fury_flipper_2": FuryFlipper2}
BOT_CLASSES = {}


# ---------------------------------------------------------------------------
def log(message: str) -> None:
    _activity.appendleft({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "message": message})


def _make(d: dict) -> Bot:
    return BOT_CLASSES.get(d["id"], Bot)(d)


def _save() -> None:
    BOTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = BOTS_FILE.with_name(BOTS_FILE.name + ".tmp")
    tmp.write_text(json.dumps([b.definition() for b in _bots], indent=2))
    os.replace(tmp, BOTS_FILE)               # atomic: a crash can't leave a half-written file


def reload() -> None:
    """(Re)load bots from disk, seeding the five default bots on first run."""
    global _bots
    with _lock:
        for b in _bots:
            if b.running:
                b._stop()
        defs, first_run = [], not BOTS_FILE.exists()
        if not first_run:
            try:
                for d in json.loads(BOTS_FILE.read_text()):
                    if isinstance(d, dict) and "id" in d and "name" in d and "magic" in d:
                        defs.append(d)
            except (json.JSONDecodeError, OSError):
                first_run = True
        if first_run:
            defs = [dict(d) for d in DEFAULT_BOTS]
        _bots = [_make(d) for d in defs]
        if first_run:
            _save()


def _new_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "bot"
    return f"{slug}_{uuid.uuid4().hex[:4]}"


def _parse_lot(value) -> float:
    try:
        lot = float(value)
    except (TypeError, ValueError):
        raise ValidationError("Lot size must be a number.")
    if not (MIN_LOT <= lot <= MAX_LOT):
        raise ValidationError(f"Lot size must be between {MIN_LOT} and {MAX_LOT}.")
    return round(lot, 2)


def _clean(data: dict, exclude_id=None) -> dict:
    name = str(data.get("name") or "").strip()
    if not name:
        raise ValidationError("Bot name is required.")
    if len(name) > 40:
        raise ValidationError("Bot name must be 40 characters or fewer.")

    description = str(data.get("description") or "").strip()
    if len(description) > 200:
        raise ValidationError("Description must be 200 characters or fewer.")

    try:
        magic_f = float(data.get("magic"))
    except (TypeError, ValueError):
        raise ValidationError("Magic number must be a whole number.")
    if not magic_f.is_integer() or not (0 < magic_f <= 2_147_483_647):
        raise ValidationError("Magic number must be a positive whole number.")
    magic = int(magic_f)
    if any(b.magic == magic and b.id != exclude_id for b in _bots):
        raise ValidationError("That magic number is already used by another bot.")

    instrument = data.get("instrument") or INSTRUMENTS[-1]
    if instrument not in INSTRUMENTS:
        raise ValidationError("Choose one of the listed instruments.")

    file = str(data.get("file") or "").strip()
    if len(file) > 100:
        raise ValidationError("EA filename must be 100 characters or fewer.")

    lot = _parse_lot(data.get("lot_size", MIN_LOT))
    return dict(name=name, description=description, magic=magic,
                instrument=instrument, file=file, lot_size=lot)


# ---- public API used by app.py ------------------------------------------------
def all_bots() -> list:
    with _lock:
        return list(_bots)


def activity() -> list:
    return list(_activity)


def get_bot(bot_id: str):
    with _lock:
        return next((b for b in _bots if b.id == bot_id), None)


def _need(bot_id: str) -> Bot:
    bot = get_bot(bot_id)
    if bot is None:
        raise BotNotFound(f"Unknown bot '{bot_id}'.")
    return bot


def create_bot(data: dict) -> Bot:
    with _lock:
        clean = _clean(data)
        clean["id"] = _new_id(clean["name"])
        bot = _make(clean)
        _bots.append(bot)
        _save()
        log(f"Added bot: {bot.name}")
        return bot


def update_bot(bot_id: str, data: dict) -> Bot:
    with _lock:
        bot = _need(bot_id)
        if bot.running:
            raise BotBusy("Stop the bot before editing it.")
        clean = _clean(data, exclude_id=bot.id)
        for key, value in clean.items():
            setattr(bot, key, value)
        _save()
        log(f"Updated bot: {bot.name}")
        return bot


def delete_bot(bot_id: str) -> None:
    with _lock:
        bot = _need(bot_id)
        if bot.running:
            raise BotBusy("Deactivate this bot before deleting it.")
        _bots.remove(bot)
        _save()
        log(f"Deleted bot: {bot.name}")


def set_lot(bot_id: str, value) -> Bot:
    with _lock:
        bot = _need(bot_id)
        if bot.running:
            raise BotBusy("Stop the bot before changing its lot size.")
        bot.lot_size = _parse_lot(value)
        _save()
        log(f"{bot.name}: lot size set to {bot.lot_size:.2f}")
        return bot


def start_bot(bot_id: str) -> Bot:
    with _lock:
        bot = _need(bot_id)
        if not bot.running:
            bot._start()
            log(f"Activated: {bot.name} (lot {bot.lot_size:.2f})")
        return bot


def stop_bot(bot_id: str) -> Bot:
    with _lock:
        bot = _need(bot_id)
        if bot.running:
            bot._stop()
            log(f"Deactivated: {bot.name}")
        return bot


def start_all() -> int:
    """Activate every bot that is not running. Returns how many were started."""
    with _lock:
        todo = [b for b in _bots if not b.running]
        for b in todo:
            b._start()
        if todo:
            log(f"Activated all bots ({len(todo)})")
        return len(todo)


def stop_all() -> int:
    """Deactivate every running bot. Returns how many were stopped."""
    with _lock:
        todo = [b for b in _bots if b.running]
        for b in todo:
            b._stop()
        if todo:
            log(f"Deactivated all bots ({len(todo)})")
        return len(todo)


reload()
