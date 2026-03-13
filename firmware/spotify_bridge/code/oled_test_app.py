"""Desktop OLED simulator for the macropad serial protocol.

Usage:
  oled_test_app.exe --demo
  oled_test_app.exe --port COM7
"""

import argparse
import sys
import os
import threading
import time
import tkinter as tk
from pathlib import Path

try:
    import serial
except ImportError:
    serial = None

try:
    from PIL import Image, ImageTk
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

SCALE     = 4
OLED_W    = 128
OLED_H    = 32
THRESHOLD = 190


# ---------------------------------------------------------------------------
# Resource path — works both from source and inside a PyInstaller one-file EXE
# ---------------------------------------------------------------------------

def _resource(filename: str) -> Path:
    """Return path to a bundled asset (extracted by PyInstaller to _MEIPASS)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / filename          # type: ignore[attr-defined]
    # Running from source — look next to the script
    return Path(__file__).parent / filename


DUCK_GIF_PATH: Path | None = None
_candidate = _resource("Duck.gif")
if _candidate.is_file():
    DUCK_GIF_PATH = _candidate
else:
    print("Duck.gif not found — idle animation will be unavailable.")


# ---------------------------------------------------------------------------
# Duck animation loader
# ---------------------------------------------------------------------------

_DUCK_BG  = (174, 217, 236)
_DUCK_TOL = 35


def _remove_bg(rgba_img):
    data = rgba_img.load()
    w, h = rgba_img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = data[x, y]
            if abs(r - _DUCK_BG[0]) < _DUCK_TOL and \
               abs(g - _DUCK_BG[1]) < _DUCK_TOL and \
               abs(b - _DUCK_BG[2]) < _DUCK_TOL:
                data[x, y] = (0, 0, 0, 0)
    return rgba_img


def _load_duck_frames(step: int = 3):
    if not _PIL_AVAILABLE or DUCK_GIF_PATH is None:
        return []
    try:
        gif = Image.open(DUCK_GIF_PATH)
        n   = gif.n_frames
    except Exception as e:
        print(f"Could not open Duck.gif: {e}")
        return []

    CW, CH = OLED_W * SCALE, OLED_H * SCALE
    frames = []
    print(f"Loading Duck.gif: {n} frames, step={step} → {len(range(0, n, step))} kept")

    for i in range(0, n, step):
        gif.seek(i)
        rgba   = _remove_bg(gif.convert("RGBA"))
        duck   = rgba.resize((32, 32), Image.NEAREST)
        canvas = Image.new("RGBA", (128, 32), (255, 255, 255, 255))
        canvas.paste(duck, ((128 - 32) // 2, 0), duck)
        gray   = canvas.convert("L")
        result = gray.point(lambda p: 0 if p < THRESHOLD else 255)
        big    = result.resize((CW, CH), Image.NEAREST).convert("RGB")
        frames.append(big)

    print(f"Duck frames ready: {len(frames)}")
    return frames


_DUCK_FRAMES    = _load_duck_frames(step=3)
_DUCK_FRAME_DUR = 0.050 * 3


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class OLEDState:
    def __init__(self):
        self.song     = ""
        self.artist   = ""
        self.position = 0
        self.duration = 0
        self.bpm      = 0
        self.mode     = "IDLE"
        self.cover    = None
        self.frame_index     = 0
        self.last_frame_time = 0.0

    def apply(self, msg: str) -> None:
        parts = msg.strip().split("|")
        if not parts:
            return
        if parts[0] == "SONG" and len(parts) >= 6:
            self.song     = parts[1]
            self.artist   = parts[2]
            self.position = _safe_int(parts[3])
            self.duration = max(0, _safe_int(parts[4]))
            self.bpm      = max(0, _safe_int(parts[5]))
            self.mode     = "SPOTIFY"
        elif parts[0] == "COVER" and len(parts) >= 2:
            raw = _decode_cover(parts[1])
            if raw is not None:
                self.cover = raw
        elif parts[0] == "IDLE":
            self.mode = "IDLE"


def _safe_int(v):
    try:    return int(v)
    except: return 0


def _decode_cover(hex_data):
    try:
        raw = bytes.fromhex(hex_data)
    except ValueError:
        return None
    return raw if len(raw) == 128 else None


def _fmt_time(total: int) -> str:
    return f"{total // 60}:{total % 60:02d}"


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

class OLEDTestUI:
    def __init__(self, state: OLEDState):
        self.state  = state
        self.scroll = 0

        self.root = tk.Tk()
        self.root.title("Spotify Macropad — OLED Preview")
        self.root.configure(bg="#1e1e1e")

        cw, ch = OLED_W * SCALE, OLED_H * SCALE
        self.canvas = tk.Canvas(
            self.root, width=cw, height=ch,
            bg="black", highlightthickness=1,
            highlightbackground="#404040",
        )
        self.canvas.pack(padx=16, pady=16)

        self.status = tk.StringVar(value="Ready")
        tk.Label(self.root, textvariable=self.status,
                 bg="#1e1e1e", fg="#d0d0d0").pack(pady=(0, 12))

        self._pil_bg = Image.new("RGB", (cw, ch), (0, 0, 0))
        self._tk_img = ImageTk.PhotoImage(self._pil_bg)
        self._img_id = self.canvas.create_image(0, 0, anchor="nw",
                                                image=self._tk_img)
        self.root.after(33, self._tick)

    def run(self) -> None:
        self.root.mainloop()

    def _tick(self) -> None:
        self.draw()
        self.root.after(33, self._tick)

    # ------------------------------------------------------------------

    def draw(self) -> None:
        self.canvas.delete("ui")
        if self.state.mode == "SPOTIFY":
            self._draw_spotify()
            bpm_s = f" | BPM: {self.state.bpm}" if self.state.bpm else ""
            self.status.set(f"Mode: Spotify{bpm_s}")
        else:
            self._draw_idle()
            self.status.set("Mode: Idle")

    def _draw_idle(self) -> None:
        if not _DUCK_FRAMES:
            self.canvas.create_text(
                OLED_W * SCALE // 2, OLED_H * SCALE // 2,
                text="Duck.gif not found", fill="#ffffff",
                font=("Courier", 8), tags="ui",
            )
            return

        now = time.monotonic()
        if now - self.state.last_frame_time >= _DUCK_FRAME_DUR:
            self.state.frame_index = (self.state.frame_index + 1) % len(_DUCK_FRAMES)
            self.state.last_frame_time = now

        self._blit_img(_DUCK_FRAMES[self.state.frame_index])

    def _draw_spotify(self) -> None:
        bg = Image.new("RGB", (OLED_W * SCALE, OLED_H * SCALE), (0, 0, 0))

        if self.state.cover:
            cover_img = self._decode_cover_pil(self.state.cover)
            if cover_img:
                bg.paste(cover_img, (96 * SCALE, 0))

        self._blit_img(bg)

        title_w = 14 if self.state.cover else 20
        self._text(0,  0,  "Spotify")
        self._text(0,  10, self._scroll_text(self.state.song or "Nothing playing",
                                             title_w))

        progress = 0.0
        if self.state.duration > 0:
            progress = max(0.0, min(self.state.position / self.state.duration, 1.0))
        bar = "█" * int(progress * 10) + "░" * (10 - int(progress * 10))
        self._text(0, 22, f"{_fmt_time(self.state.position)} {bar}")

    # ------------------------------------------------------------------

    def _blit_img(self, rgb_img) -> None:
        self._tk_img = ImageTk.PhotoImage(rgb_img)
        self.canvas.itemconfigure(self._img_id, image=self._tk_img)

    def _decode_cover_pil(self, raw: bytes):
        try:
            cover = Image.new("RGB", (32, 32), (0, 0, 0))
            for page in range(4):
                for x in range(32):
                    v = raw[page * 32 + x]
                    for bit in range(8):
                        if v & (1 << bit):
                            cover.putpixel((x, page * 8 + bit), (240, 240, 240))
            return cover.resize((32 * SCALE, 32 * SCALE), Image.NEAREST)
        except Exception:
            return None

    def _scroll_text(self, text: str, width: int) -> str:
        if len(text) <= width:
            return text
        tick = int(time.monotonic() * 4)
        if tick != self.scroll:
            self.scroll = tick
        idx = self.scroll % (len(text) + 3)
        return (text + "   " + text)[idx: idx + width]

    def _text(self, x: int, y: int, s: str) -> None:
        self.canvas.create_text(
            x * SCALE, y * SCALE,
            anchor="nw", text=s, fill="#ffffff",
            font=("Courier", 7 * SCALE // 2),
            tags="ui",
        )


# ---------------------------------------------------------------------------
# Feeds
# ---------------------------------------------------------------------------

def demo_feed(state: OLEDState) -> None:
    samples = [
        ("Blinding Lights",    "The Weeknd",   200, 171),
        ("As It Was",          "Harry Styles", 168, 174),
        ("Stairway to Heaven", "Led Zeppelin", 482,  82),
    ]
    i, pos = 0, 0
    while True:
        song, artist, dur, bpm = samples[i % len(samples)]
        state.apply(f"SONG|{song}|{artist}|{pos}|{dur}|{bpm}")
        pos += 1
        if pos > dur:
            pos = 0
            i  += 1
            if i % 2 == 1:
                state.apply("IDLE")
                time.sleep(1.5)
        time.sleep(0.35)


def serial_feed(state: OLEDState, port: str, baud: int) -> None:
    if serial is None:
        raise RuntimeError("pyserial is required for --port mode")
    with serial.Serial(port, baud, timeout=0.1) as ser:
        while True:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if line:
                state.apply(line)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Spotify Macropad OLED Preview")
    parser.add_argument("--demo", action="store_true",
                        help="Run with demo song data (no device needed)")
    parser.add_argument("--port", help="Serial port to read from (e.g. COM7)")
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()

    if not _PIL_AVAILABLE:
        print("Pillow is required:  pip install Pillow")
        return

    state = OLEDState()
    if args.demo:
        threading.Thread(target=demo_feed, args=(state,), daemon=True).start()
    elif args.port:
        threading.Thread(target=serial_feed,
                         args=(state, args.port, args.baud), daemon=True).start()
    else:
        parser.error("Provide --demo or --port COM#")

    OLEDTestUI(state).run()


if __name__ == "__main__":
    main()
