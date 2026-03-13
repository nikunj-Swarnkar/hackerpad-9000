# Spotify Macropad with OLED Display

A custom **Spotify control macropad** built using the **Seeed XIAO RP2040**, running **KMK firmware** and powered by a **Python bridge application** that connects Spotify playback data to the keyboard over USB.

The device acts as a **hardware Spotify controller + display**, showing live song information, album art, and animations on a small OLED screen.

Made by [Nitin Swarnkar](https://github.com/Nitin-2468-dev)

---

## Installing and Firmware Setup

This section explains how to install the firmware on the macropad and run the Spotify bridge software.

---

### 1. Install CircuitPython

<img width="1200" height="732" alt="Image" src="https://github.com/user-attachments/assets/201587a3-0d87-4e92-9ec0-b6e304b6d9ee" />

1. Plug the **Seeed XIAO RP2040** into your computer.
2. Double-tap the **RESET** button on the board. A new drive called *RPI-RP2* will appear:

   <img width="161" height="61" alt="Image" src="https://github.com/user-attachments/assets/994778ac-d963-497e-9082-71802b4e43b6" />

3. Download the CircuitPython firmware for the board:
   https://circuitpython.org/board/seeeduino_xiao_rp2040/

4. Drag the downloaded `.uf2` file onto the **RPI-RP2** drive:

   <img width="328" height="104" alt="Image" src="https://github.com/user-attachments/assets/d8bd3687-5024-4369-b57f-6444f9b3762c" />

   The board will reboot and a new drive will appear named **CIRCUITPY**.

---

### 2. Copy Firmware Files

Open the `CIRCUITPY` drive and copy the following files. The folder should look like:

<img width="216" height="199" alt="Image" src="https://github.com/user-attachments/assets/5c5a90e5-b683-4de4-ab66-85b97c68adbe" />

---

### 3. Setup the Spotify Bridge

<img width="200" height="179" alt="Image" src="https://github.com/user-attachments/assets/a5ffc728-c5b6-4f41-a48e-1bc4f436cd6e" />

Navigate to the bridge folder:

```
spotify_bridge/
```

Run the bridge application:

```
spotify_bridge.exe
```

Or run the Python script directly at `firmware/spotify_bridge/code`:

```
python spotify_bridge.py
```

The bridge connects to the Spotify API and communicates with the keyboard via USB serial.

---

### 4. Configure Spotify API

<img width="1504" height="789" alt="Image" src="https://github.com/user-attachments/assets/d7ac8dd7-f009-4ba3-b774-0ef18fa8f9b8" />

1. Create a [Spotify Developer](https://developer.spotify.com/dashboard) application.

2. Copy your credentials:

   <img width="1824" height="499" alt="Image" src="https://github.com/user-attachments/assets/d1f8ab9a-eea6-405b-af02-bf458400aa09" />

3. Add the following redirect URI:

   ```
   http://localhost:8888/callback
   ```

4. Enable the following API:

   ```
   Web API
   ```

<img width="1494" height="776" alt="Image" src="https://github.com/user-attachments/assets/1de7d952-d734-4cfa-821f-702e2ade3822" />

---

### 5. Running the System

1. Plug the macropad into USB.
2. Launch `spotify_bridge.exe`.
3. Start Spotify.
4. The OLED display should begin showing track information.

You can now control Spotify using the macropad.

---

### Troubleshooting

**Spotify data not updating**

Make sure:

- Spotify is open
- The bridge application is running
- Authentication completed successfully

---

## Project Goals

This project aims to create a **dedicated hardware controller for Spotify** with the following capabilities:

- Control music playback
- Display currently playing song
- Show playback progress
- Adjust volume
- Scrub through the track
- Display album art
- Animate a BongoCat reacting to music
- Run a lightweight PC companion app

The final result behaves similarly to a **mini StreamDeck specifically for Spotify**.

---

## System Architecture

```
Spotify App
      ↓
Spotify Web API
      ↓
spotify_bridge.exe (Python)
      ↓
USB Serial
      ↓
KMK Firmware
      ↓
Macropad Hardware
      ↓
OLED Display + Controls
```

The bridge software connects Spotify playback data to the keyboard firmware through a serial protocol.

---

## Hardware Components

### Main Controller

- **Seeed XIAO RP2040**

### Input Devices

- 6 × MX-style mechanical switches
- 2 × EC11 rotary encoders

### Display

https://github.com/user-attachments/assets/8e71572c-191a-4422-8621-966e16f79e89

- **0.91" SSD1306 OLED display (128×32)**

### Lighting

- **16 × SK6812 MINI-E RGB LEDs**

### Other Components

- 20 × 1N4148 diodes
- Blank DSA keycaps
- Screws and heat-set inserts

---

## Firmware

Firmware is written using **KMK (Keyboard Module Kit)**, a Python-based keyboard firmware built on **CircuitPython**.

### Why KMK Was Chosen

- Python-based development
- Rapid iteration
- Easy display integration
- Native RP2040 support

### Firmware Responsibilities

- Scan key matrix
- Handle rotary encoders
- Communicate with PC bridge via USB serial
- Render OLED display UI
- Play animations

---

## PC Bridge Software

The PC companion application:

```
spotify_bridge.py
```

Or compiled version:

```
spotify_bridge.exe
```

### Responsibilities

- Connect to Spotify Web API
- Authenticate user
- Retrieve playback data
- Send updates to keyboard
- Receive control commands
- Execute Spotify API actions

The bridge can be packaged as a standalone executable so users **do not need Python installed**.

---

## Spotify Integration

Spotify integration uses the **Spotify Web API** with OAuth authentication.

### Required Permission

```
user-read-playback-state
```

This allows the bridge to read:

- Currently playing track
- Artist
- Playback progress
- Duration
- Album art
- Tempo (BPM)

> **Note:** Some features require **Spotify Premium**.

---

## Serial Protocol

Communication between the keyboard and bridge uses a simple text protocol.

Examples:

```
SONG|title|artist|position|duration|tempo
VOL|70
IDLE
COVER|bitmap_data
CMD|NEXT
CMD|PLAY
CMD|SEEK|120
```

This protocol allows **two-way communication**.

---

## OLED Display UI

The 128×32 OLED shows several screens.

### Spotify Screen

![Spotify screen](https://github.com/nikunj-Swarnkar/Spotify_marcro_pad_thingy/blob/8d25a37261554aaab6021cbf5d8dac0a1f67ea21/assets/show-case.png)

```
Spotify
Blinding Lights
████░░░░░░ 1:42
```

Displays:

- Song title
- Playback progress bar
- Current playback time
- Cover art

### Volume Screen

```
Volume
██████░░░░ 60%
```

Appears when adjusting volume.

### Idle Screen

![Idle screen](https://github.com/nikunj-Swarnkar/Spotify_marcro_pad_thingy/blob/8d25a37261554aaab6021cbf5d8dac0a1f67ea21/assets/Duck.png)

```
Duck animation
```

Displayed when nothing is playing.

---

## Album Art Rendering

![Cover](https://github.com/nikunj-Swarnkar/Spotify_marcro_pad_thingy/blob/8d25a37261554aaab6021cbf5d8dac0a1f67ea21/assets/image.png)

The bridge downloads album art from Spotify. The image is:

1. Downloaded
2. Resized to 32×32 pixels
3. Converted to monochrome
4. Sent to the keyboard as a bitmap

The OLED displays the album cover next to the song information.

---

## Macropad Controls

### Keys

| Key        | Action          |
| ---------- | --------------- |
| Play/Pause | Toggle playback |
| Next       | Next track      |
| Previous   | Previous track  |
| Shuffle    | Toggle shuffle  |
| Repeat     | Toggle repeat   |
| Mute       | Set volume to 0 |

### Encoder 1 — Volume

```
Rotate right → volume up
Rotate left  → volume down
```

### Encoder 2 — Track Scrubbing

```
Rotate right → seek forward
Rotate left  → seek backward
```

---

## Display Progress Bar

Playback progress is rendered as a 10-segment bar:

```
1:30  ████░░░░░░
```

Progress is calculated using:

```
progress = position / duration
```

---

## Features

### Core Features

- Spotify playback display
- Playback progress bar
- Hardware volume control
- Track scrubbing
- Shuffle toggle
- Repeat toggle

### UI Features

- OLED interface
- Scrolling song titles
- Album art display
- Duck animations

### System Features

- Two-way serial protocol
- PC companion application
- Standalone executable bridge
- Automatic Spotify authentication
- Token caching
- Auto reconnect USB

---

## Why This Design

This architecture was chosen because KMK firmware provides flexible keyboard development while Python allows quick UI development and API integration.

The bridge software separates Spotify integration from firmware, making the keyboard firmware lightweight and reusable. The result is a **modular system** where firmware handles hardware and the bridge handles network/API logic.

---

## Future Improvements

- Animated audio visualizer
- RGB LEDs reacting to music
- System tray bridge application
- Multi-service support (YouTube Music, Apple Music)
- Better OLED UI layouts

---

## Project Status

- Software architecture completed
- Firmware and bridge logic implemented
- Waiting for hardware components to assemble the physical macropad

---

*Firmware built by **Nitin Swarnkar***
