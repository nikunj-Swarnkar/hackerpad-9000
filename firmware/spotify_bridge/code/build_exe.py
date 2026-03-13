"""Build standalone Windows EXEs with PyInstaller.

Both executables are single-file (--onefile) and have Duck.gif bundled
inside them — no extra files need to be distributed.

Usage:
  python build_exe.py           # build both
  python build_exe.py --bridge  # bridge only
  python build_exe.py --oled    # OLED test app only
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT  = Path(__file__).resolve().parent
DIST  = ROOT / "dist"
BUILD = ROOT / "build"

# Duck.gif is next to this script; verify it exists before building.
DUCK_GIF = ROOT / "Duck.gif"

# On Windows PyInstaller uses ';' as the path separator in --add-data.
# Format:  source;dest_folder_inside_bundle
# We put Duck.gif in the root of the bundle so _resource("Duck.gif") finds it.
_ADD_DUCK = f"{DUCK_GIF};."

# ---------------------------------------------------------------------------
# Hidden imports
# ---------------------------------------------------------------------------

BRIDGE_HIDDEN = [
    "spotipy",
    "spotipy.oauth2",
    "spotipy.util",
    "serial",
    "serial.tools",
    "serial.tools.list_ports",
    "PIL",
    "PIL.Image",
    "winreg",
]

OLED_HIDDEN = [
    "serial",
    "serial.tools",
    "serial.tools.list_ports",
    "tkinter",
    "tkinter.ttk",
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hidden(imports: list[str]) -> list[str]:
    flags = []
    for imp in imports:
        flags += ["--hidden-import", imp]
    return flags


def run(cmd: list[str]) -> None:
    print("\n+", " ".join(cmd), "\n")
    subprocess.check_call(cmd, cwd=ROOT)


# ---------------------------------------------------------------------------
# Build targets
# ---------------------------------------------------------------------------

def build_bridge() -> None:
    if not DUCK_GIF.exists():
        print(f"WARNING: {DUCK_GIF} not found — bridge will be built without it.")
        add_data_flags: list[str] = []
    else:
        add_data_flags = ["--add-data", _ADD_DUCK]

    run(
        [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            # Keep console visible — OAuth needs it and it shows status messages.
            "--name", "spotify_bridge",
        ]
        + add_data_flags
        + _hidden(BRIDGE_HIDDEN)
        + ["spotify_bridge.py"]
    )


def build_oled_test() -> None:
    if not DUCK_GIF.exists():
        print(f"WARNING: {DUCK_GIF} not found — OLED app will be built without it.")
        add_data_flags: list[str] = []
    else:
        add_data_flags = ["--add-data", _ADD_DUCK]

    run(
        [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--noconsole",           # pure GUI app — no console window
            "--name", "oled_test_app",
        ]
        + add_data_flags
        + _hidden(OLED_HIDDEN)
        + ["oled_test_app.py"]
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Build Spotify Macropad EXEs")
    parser.add_argument("--bridge", action="store_true", help="Build bridge only")
    parser.add_argument("--oled",   action="store_true", help="Build OLED test app only")
    args = parser.parse_args()

    both = not args.bridge and not args.oled

    if args.bridge or both:
        build_bridge()
    if args.oled or both:
        build_oled_test()

    print("\n✓ Build complete.")
    if args.bridge or both:
        print(f"  Bridge EXE  →  {DIST / 'spotify_bridge.exe'}")
    if args.oled or both:
        print(f"  OLED Test   →  {DIST / 'oled_test_app.exe'}")
    print()
    print("First run of spotify_bridge.exe will:")
    print("  1. Ask for your Spotify credentials → create config.json")
    print("  2. Register itself in Windows startup (auto-launches at login)")
    print("  3. Connect to Spotify and wait for the macropad to be plugged in")


if __name__ == "__main__":
    main()
