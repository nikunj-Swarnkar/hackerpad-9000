"""Spotify ↔ Macropad bridge.

First run:  creates config.json interactively and registers itself in the
            Windows startup registry so it launches automatically at login.
            The device does NOT need to be plugged in yet — the bridge sits
            in the background and connects the moment the macropad appears.

Subsequent runs:  loads config, connects to Spotify, waits for the macropad.
"""

import json
import sys
import time
import winreg
from io import BytesIO
from pathlib import Path
from urllib.request import urlopen

import serial
import serial.tools.list_ports
import spotipy
from PIL import Image
from spotipy.oauth2 import SpotifyOAuth

BAUD_RATE         = 115200
POLL_INTERVAL_S   = 0.35
RECONNECT_DELAY_S = 2.0

APP_NAME = "SpotifyMacropad"


# ---------------------------------------------------------------------------
# Path helpers — work both as a .py script and as a PyInstaller one-file EXE
# ---------------------------------------------------------------------------

def _exe_dir() -> Path:
    """Folder that contains the EXE (or the script when running from source)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def _resource(filename: str) -> Path:
    """Bundled read-only assets (e.g. Duck.gif) extracted by PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / filename          # type: ignore[attr-defined]
    return Path(__file__).parent / filename


def _config_path() -> Path:
    return _exe_dir() / "config.json"


# ---------------------------------------------------------------------------
# First-run config wizard
# ---------------------------------------------------------------------------

def _create_config() -> dict:
    print()
    print("╔══════════════════════════════════════════╗")
    print("║   Spotify Macropad — First-Run Setup     ║")
    print("╚══════════════════════════════════════════╝")
    print()
    print("You need a Spotify developer app to continue.")
    print("  1. Go to  https://developer.spotify.com/dashboard")
    print("  2. Create an app (any name/description)")
    print("  3. Add   http://127.0.0.1:8888/callback   as a Redirect URI")
    print("  4. Copy the Client ID and Client Secret below")
    print()

    client_id     = input("  CLIENT_ID     : ").strip()
    client_secret = input("  CLIENT_SECRET : ").strip()
    redirect_uri  = (
        input("  REDIRECT_URI  [http://127.0.0.1:8888/callback]: ").strip()
        or "http://127.0.0.1:8888/callback"
    )

    config = {
        "CLIENT_ID":     client_id,
        "CLIENT_SECRET": client_secret,
        "REDIRECT_URI":  redirect_uri,
    }

    path = _config_path()
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"\n  ✓ Config saved to {path}")
    return config


def load_config() -> dict:
    path = _config_path()
    if not path.exists():
        config = _create_config()
        _register_startup()   # register only on first run
        return config

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Windows startup registry — bridge auto-launches at login
# ---------------------------------------------------------------------------

def _startup_exe() -> str:
    if getattr(sys, "frozen", False):
        return str(sys.executable)
    # Running from source: tell Windows to call python with this script
    return f'"{sys.executable}" "{Path(__file__).resolve()}"'


def _register_startup() -> None:
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _startup_exe())
        winreg.CloseKey(key)
        print("  ✓ Bridge registered in Windows startup")
        print("    (it will launch automatically at login and wait for the macropad)")
    except Exception as exc:
        print(f"  ! Could not register startup entry: {exc}")


def _unregister_startup() -> None:
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
        print("Removed from Windows startup.")
    except FileNotFoundError:
        print("Not registered — nothing to remove.")
    except Exception as exc:
        print(f"Could not remove startup entry: {exc}")


# ---------------------------------------------------------------------------
# Spotify client
# ---------------------------------------------------------------------------

def build_spotify_client(config: dict) -> spotipy.Spotify:
    cache_path = _exe_dir() / ".spotify_cache"
    return spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=config["CLIENT_ID"],
            client_secret=config["CLIENT_SECRET"],
            redirect_uri=config["REDIRECT_URI"],
            scope=" ".join([
                "user-read-playback-state",
                "user-modify-playback-state",
            ]),
            cache_path=str(cache_path),
            open_browser=True,
        )
    )


# ---------------------------------------------------------------------------
# Serial port helpers
# ---------------------------------------------------------------------------

def find_port() -> str | None:
    ports = list(serial.tools.list_ports.comports())
    preferred = ("XIAO", "RP2040", "CIRCUITPYTHON", "USB")
    for p in ports:
        if any(t in (p.description or "").upper() for t in preferred):
            return p.device
    return ports[0].device if ports else None


def open_serial_with_retry(forced_port: str | None = None) -> serial.Serial:
    while True:
        port = forced_port or find_port()
        if port:
            try:
                print(f"Connecting → {port} …")
                return serial.Serial(port, BAUD_RATE, timeout=0.02)
            except Exception as exc:
                print(f"  Failed: {exc}")
        else:
            print("Macropad not found — waiting …")
        time.sleep(RECONNECT_DELAY_S)


# ---------------------------------------------------------------------------
# Album art
# ---------------------------------------------------------------------------

def build_cover_hex(url: str | None) -> str | None:
    if not url:
        return None

    with urlopen(url, timeout=10) as resp:
        image_bytes = resp.read()

    img = Image.open(BytesIO(image_bytes)).convert("L").resize((32, 32))
    bw  = img.point(lambda p: 255 if p > 127 else 0, mode="1")

    pixels = bw.load()
    packed = bytearray(128)
    for page in range(4):
        for x in range(32):
            value = 0
            for bit in range(8):
                if pixels[x, page * 8 + bit] == 255:
                    value |= 1 << bit
            packed[page * 32 + x] = value

    return packed.hex()


# ---------------------------------------------------------------------------
# Serial I/O
# ---------------------------------------------------------------------------

def safe_write(ser: serial.Serial, text: str) -> None:
    ser.write((text + "\n").encode("utf-8"))


def handle_command(sp: spotipy.Spotify, playback: dict | None, cmd_line: str) -> None:
    parts = cmd_line.strip().split("|")
    if len(parts) < 2 or parts[0] != "CMD":
        return

    action = parts[1]

    if action == "NEXT":
        sp.next_track()
    elif action == "PREV":
        sp.previous_track()
    elif action == "PLAY_PAUSE":
        if playback and playback.get("is_playing"):
            sp.pause_playback()
        else:
            sp.start_playback()
    elif action == "SHUFFLE":
        sp.shuffle(not bool(playback and playback.get("shuffle_state")))
    elif action == "REPEAT":
        order   = ["off", "context", "track"]
        cur     = (playback or {}).get("repeat_state", "off")
        sp.repeat(order[(order.index(cur) + 1) % len(order)] if cur in order else "off")
    elif action == "MUTE":
        sp.volume(0)
    elif action == "VOL_REL" and len(parts) >= 3:
        delta   = int(parts[2])
        current = int((playback or {}).get("device", {}).get("volume_percent", 0))
        sp.volume(max(0, min(100, current + delta)))
    elif action == "SEEK_REL" and len(parts) >= 3:
        delta_s  = int(parts[2])
        progress = int((playback or {}).get("progress_ms", 0))
        duration = int((playback or {}).get("item", {}).get("duration_ms", 0))
        sp.seek_track(max(0, min(duration, progress + delta_s * 1000)))


def poll_commands(sp, ser, playback) -> None:
    while ser.in_waiting:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if line:
            try:
                handle_command(sp, playback, line)
            except Exception as exc:
                print(f"Command error [{line}]: {exc}")


def read_tempo(_sp, _track_id) -> int:
    # audio_features deprecated for new apps (returns 403) — return 0
    return 0


def send_playback_state(sp, ser, cache: dict) -> None:
    playback = sp.current_playback()
    poll_commands(sp, ser, playback)

    if playback and playback.get("item"):
        track       = playback["item"]
        song        = (track.get("name") or "").replace("|", "/")
        artists     = track.get("artists") or []
        artist_name = ((artists[0].get("name") if artists else "") or "").replace("|", "/")
        position    = int((playback.get("progress_ms") or 0) / 1000)
        duration    = int((track.get("duration_ms") or 0) / 1000)
        track_id    = track.get("id") or ""

        if track_id and track_id != cache["track_id"]:
            cache["track_id"] = track_id
            cache["tempo"]    = read_tempo(sp, track_id)
            images            = track.get("album", {}).get("images", [])
            image_url         = images[-1]["url"] if images else None
            try:
                cache["cover"] = build_cover_hex(image_url) if image_url else None
            except Exception as exc:
                print(f"Cover error: {exc}")
                cache["cover"] = None

        safe_write(ser, f"SONG|{song}|{artist_name}|{position}|{duration}|{cache['tempo']}")
        if cache["cover"]:
            safe_write(ser, f"COVER|{cache['cover']}")
    else:
        safe_write(ser, "IDLE")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Spotify Macropad Bridge")
    parser.add_argument("--port",      help="Force a specific COM port (e.g. COM6)")
    parser.add_argument("--uninstall", action="store_true",
                        help="Remove bridge from Windows startup and exit")
    args = parser.parse_args()

    if args.uninstall:
        _unregister_startup()
        return

    config = load_config()
    print("\nAuthenticating with Spotify …")
    sp = build_spotify_client(config)

    ser   = open_serial_with_retry(args.port)
    cache = {"track_id": "", "tempo": 0, "cover": None}

    print("Bridge running. Press Ctrl+C to stop.\n")

    while True:
        try:
            if not ser.is_open:
                ser = open_serial_with_retry(args.port)
            send_playback_state(sp, ser, cache)
            time.sleep(POLL_INTERVAL_S)
        except KeyboardInterrupt:
            print("\nStopping bridge.")
            break
        except Exception as exc:
            print(f"Bridge error: {exc}")
            try:
                ser.close()
            except Exception:
                pass
            time.sleep(RECONNECT_DELAY_S)
            ser = open_serial_with_retry(args.port)


if __name__ == "__main__":
    main()
