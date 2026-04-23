# tekken-arcade-mini

A two-player arcade fighting game — built first as a Python/Pygame desktop prototype, then ported to Arduino hardware with a TFT screen, joysticks, buttons, LEDs, and optional audio.

---

## Project structure

```
tekken-arcade-mini/
├── simulation/          # Python/Pygame desktop prototype
│   ├── main.py            # Game loop, state machine, hit detection
│   ├── player.py          # Player class: physics, attacks, health
│   ├── character_data.py  # Roster + `CharacterProfile`
│   ├── character_select.py# Roster key handling
│   ├── combat.py          # Hit resolution
│   ├── assets_loader.py   # Sprite PNG loading
│   ├── constants.py       # All tunable gameplay values
│   ├── input_handler.py   # Keyboard → actions mapping
│   ├── renderer.py        # All drawing/UI code
│   └── requirements.txt
├── arduino/             # Arduino firmware (future)
├── assets/fighters/     # Per-fighter PNGs (`greb`, `splint`, `citron`, `brick`)
└── docs/                # Design notes and wiring diagrams (future)
```

---

## Simulation (Python/Pygame)

### Requirements

- Python 3.9+
- pygame 2.1+

```bash
cd simulation
pip install -r requirements.txt
python3 main.py
```

### Controls

| Action | Player 1 | Player 2 |
|---|---|---|
| Move | `A` / `D` | `←` / `→` |
| Jump | `W` | `↑` |
| Crouch | `S` | `↓` |
| Light attack | `J` | `,` |
| Kick (heavy) | `K` | `.` |
| Block | `L` | `/` |
| Pause / Quit | `ESC` | `ESC` |
| Start (title) | `Enter` | |
| Character select | P1: `A`/`D` cycle, `J`/`Space` lock — P2: arrows, `,` lock — both locked then `Enter` to fight | |
| After match | `Enter` returns to title | |

### Game states

`MENU` → `CHAR_SELECT` → `COUNTDOWN` → `PLAYING` → `ROUND_END` → `GAME_OVER` → (`Enter` → `MENU`)

Regenerate placeholder sprites from the repo root: `python3 assets/generate_placeholder_sprites.py`

First player to win **2 rounds** wins the match.

### Gameplay defaults

| Parameter | Value |
|---|---|
| Max health | 100 |
| Move speed | 230 px/s |
| Jump velocity | −620 px/s |
| Gravity | 1500 px/s² |
| Light attack damage / cooldown | 8 / 0.40 s |
| Heavy attack damage / cooldown | 22 / 1.05 s |
| Block damage reduction | 80% |
| Knockback speed | 190 px/s |

All values live in `simulation/constants.py` and are easy to tweak.

The match **stage** draws a twilight sky, neoclassical **library facade** (columns + warm glowing windows), plaza ground, and street lamps—colors tuned for a night-campus mood. Fighter sprites are generated as **humanoid** placeholders (skin, shirt, arms, legs, shoes); run `python3 assets/generate_placeholder_sprites.py` after editing the script.

### Architecture

The code is intentionally separated so the core logic can be ported to Arduino:

| File | Responsibility |
|---|---|
| `constants.py` | Tunable numbers and colors only — maps to `#define` / `const` on Arduino |
| `character_data.py` | Roster + per-fighter stats |
| `combat.py` | Hit overlap and damage resolution |
| `player.py` | Fighter state machine and physics — maps to a C `struct` + update functions |
| `input_handler.py` | Keyboard → action dict — maps to `digitalRead()` GPIO reads |
| `renderer.py` | All drawing — maps to TFT library calls (`fillRect`, `drawString`, etc.) |
| `main.py` | Game loop and state machine — maps to Arduino `loop()` |

---

## Arduino sketch (`arduino/tekken_mini/`)

Full port of the simulation to the Adafruit Metro RP2040 with a 1.8" ST7735R TFT display.

### Hardware

| Component | Details |
|-----------|---------|
| MCU | Adafruit Metro RP2040 |
| Display | ST7735R 1.8" TFT (128×160, landscape → 160×128) |
| Controls | 2× analog joystick (X/Y + SEL) + 3 buttons per player |
| Feedback | Shared LED (pin 4) + PWM audio via PAM8302 amp |

### Pin map

| Signal | Pin |
|--------|-----|
| TFT CS / DC | 8 / 10 |
| TFT RST | — (tie to 3.3V) |
| P1 Joystick X / Y | A0 / A1 |
| P1 Joystick SEL | 2 |
| P1 Light / Heavy / Block | 6 / 7 / 12 |
| P2 Joystick X / Y | A2 / A3 |
| P2 Joystick SEL | 3 |
| P2 Light / Heavy / Block | 13 / 24 / 25 |
| LED | 4 |
| Audio PWM | **5** ← spec said 13 but that conflicts with P2 Light btn |

> **Pin 13 conflict:** original spec placed P2 Light attack and audio PWM on the same pin. The sketch moves audio to pin **5**. Update `PIN_AUDIO` in the sketch if you rewire.

### Libraries (Arduino Library Manager)

- `Adafruit ST7735 and ST7789 Library`
- `Adafruit GFX Library`

### How to compile

1. Install **Arduino IDE 2.x**
2. **Boards Manager** → search `Raspberry Pi RP2040` → install Earle Philhower core
3. Select **Adafruit Metro RP2040**
4. Open `arduino/tekken_mini/tekken_mini.ino` and upload

### WiFi display (optional second screen)

Stream live match state from the **Metro RP2040** to phones/tablets via an **ESP32** WiFi bridge.

| Piece | Path / notes |
|-------|----------------|
| RP2040 telemetry | [`arduino/tekken_mini/tekken_mini.ino`](arduino/tekken_mini/tekken_mini.ino) — set `WIFI_DISPLAY_ENABLE` to `1`, confirm `PIN_SERIAL1_TX` / `PIN_SERIAL1_RX` match free GPIOs on your board |
| ESP32 bridge | [`arduino/esp32_wifi_display/esp32_wifi_display.ino`](arduino/esp32_wifi_display/esp32_wifi_display.ino) — install **WebSockets** library; default **AP** SSID `TekkenMini` / password `tekken123` |

**Wiring:** RP2040 `TX` → ESP32 `RX` (e.g. GPIO16), RP2040 `RX` ← ESP32 `TX` (e.g. GPIO17) if you use bidirectional UART later, **GND** common, **3.3 V only**.

**Phone:** Join `TekkenMini` WiFi, open `http://192.168.4.1/` — canvas updates from WebSocket JSON frames (`~12/s` from the game).

To use your home router instead of AP, set `WIFI_USE_STA` to `1` in the ESP32 sketch and fill `STA_SSID` / `STA_PASSWORD`.

### Python → Arduino mapping

| Python / Pygame | Arduino sketch |
|-----------------|---------------|
| `Player` class | `Player` struct + free functions |
| `float` positions | `float` (RP2040 has FPU; use `int16_t` on AVR) |
| `pygame.time.Clock()` / `dt` | `millis()` deltas + absolute deadline timestamps |
| `pygame.key.get_pressed()` | `analogRead()` + `digitalRead()` in `read_input()` |
| `pygame.Rect.colliderect()` | `rects_overlap()` with `Rect16` structs |
| `pygame.draw.rect()` | `tft.fillRect()` + partial-erase to avoid flicker |
| `pygame.mixer` sound hooks | `tone()` on PIN_AUDIO |
| State strings | `GameState` typedef enum |
| Cooldown floats | Absolute `millis()` deadline `uint32_t` fields |

---

## What to build next

1. **Sound** — drop `.wav` files into `assets/sounds/` and fill in the `snd_*` hooks in `main.py`
2. **Animations** — the `Action` state machine already drives when each frame plays; swap rectangles for sprite sheets
3. **Special moves** — add input buffering to `input_handler.py` (e.g. down → forward + attack)
4. **CPU opponent** — replace one player's input call with a simple behavior tree
5. **Arduino port** — stub out Pygame in the Python code to validate logic headlessly before flashing
