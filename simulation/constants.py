# =============================================================================
# constants.py — All tunable gameplay values live here.
# Tweak these freely without touching game logic.
# On Arduino: these become #define or const int values at the top of your sketch.
# =============================================================================

# --- Screen -------------------------------------------------------------------
SCREEN_WIDTH  = 960
SCREEN_HEIGHT = 540
FPS           = 60
TITLE         = "TEKKEN MINI"

# --- Floor --------------------------------------------------------------------
FLOOR_Y = 430           # Y coordinate of the floor surface (pixels from top)

# --- Player dimensions --------------------------------------------------------
PLAYER_WIDTH         = 50
PLAYER_HEIGHT        = 80
PLAYER_CROUCH_HEIGHT = 48   # height when crouching

# --- Movement -----------------------------------------------------------------
MOVE_SPEED        = 230     # horizontal speed (pixels/second) — default profile
JUMP_VELOCITY     = -620    # initial upward velocity on jump (negative = up)
GRAVITY           = 1500    # downward acceleration (pixels/second²)
KNOCKBACK_SPEED   = 190     # baseline knockback; profiles override per attack

# --- Health -------------------------------------------------------------------
MAX_HEALTH = 100

# --- Light attack -------------------------------------------------------------
LIGHT_DAMAGE          = 8     # damage dealt — default profile
LIGHT_RANGE           = 75    # hitbox horizontal reach (pixels beyond player edge)
LIGHT_COOLDOWN        = 0.40  # seconds before can attack again
LIGHT_ACTIVE_FRAMES   = 0.12  # seconds the hitbox is active

# --- Heavy attack -------------------------------------------------------------
HEAVY_DAMAGE          = 22    # damage dealt — default profile
HEAVY_RANGE           = 95    # hitbox horizontal reach
HEAVY_COOLDOWN        = 1.05  # seconds before can attack again
HEAVY_WINDUP          = 0.16  # seconds of windup before hitbox activates
HEAVY_ACTIVE_FRAMES   = 0.20  # seconds the hitbox is active

# --- Block --------------------------------------------------------------------
BLOCK_DAMAGE_MULT     = 0.20  # multiplier on incoming damage while blocking
BLOCK_KNOCKBACK_MULT  = 0.35  # multiplier on knockback velocity while blocking

# --- Hitstun (seconds defender cannot act except block) -----------------------
HITSTUN_LIGHT  = 0.12
HITSTUN_HEAVY  = 0.28

# --- Counter-hit (defender was attacking) ------------------------------------
COUNTER_DAMAGE_MULT    = 1.25
COUNTER_KNOCKBACK_MULT = 1.4

# --- Hitstop (freeze gameplay; seconds) ----------------------------------------
HITSTOP_LIGHT = 0.045
HITSTOP_HEAVY = 0.075

# --- Screen shake (pixels offset; decays per second) ---------------------------
SHAKE_PER_HIT = 5.0
SHAKE_DECAY   = 420.0   # units/sec — magnitude decreases toward 0

# --- Attack hitbox pose tweaks -------------------------------------------------
CROUCH_ATTACK_TOP_INSET   = 18   # extra pixels from top of body for crouch hitbox
AIR_ATTACK_HEIGHT_MULT    = 0.75 # vertical size multiplier when attacker airborne

# Heavy attack = kick: hitbox lower on the body (leg height)
KICK_HITBOX_TOP_OFFSET    = 26   # added to top_inset for current_attack == heavy
KICK_HITBOX_HEIGHT_SCALE  = 0.62 # scales vertical hitbox height for kicks

# --- Walk animation ------------------------------------------------------------
WALK_ANIM_PERIOD = 0.14  # seconds per walk frame toggle

# --- Combat VFX (legacy radial streaks — optional overlay) --------------------
HIT_SPARK_DURATION = 0.22   # seconds
SPARK_LINE_LIGHT   = (255, 130, 200)
SPARK_LINE_HEAVY   = (120, 220, 255)
SPARK_LINE_BLOCK   = (100, 240, 255)
SPARK_CORE         = (255, 255, 245)

# =============================================================================
# ANIM_* — Visual-only timings (integer-friendly; sin LUT in constants)
# Arduino equivalent: constexpr + lookup tables in flash
# =============================================================================

# Breathing idle: phase increment per second on 0..255 ring (~1.5s loop)
ANIM_BREATH_PHASE_PER_SEC = 170

# Walk: limb swing phase increment per second (0..255)
ANIM_WALK_PHASE_PER_SEC = 280

# Jump squash: frames (game updates) to show pre-jump squash — driven by vel transition
ANIM_JUMP_SQUASH_FRAMES = 4
ANIM_JUMP_STRETCH_PEAK_VY = -350  # vel_y threshold for "peak" stretch (visual only)

# Light jab visual: 10 steps (6 extend + 4 return) mapped from attack progress
ANIM_LIGHT_EXTEND_STEPS = 6
ANIM_LIGHT_RETURN_STEPS = 4

# Heavy strike visual substeps (normalized phases, not gameplay)
ANIM_HEAVY_WINDUP_STEPS   = 2
ANIM_HEAVY_STRIKE_STEPS   = 4
ANIM_HEAVY_RECOVER_STEPS  = 6

# KO ragdoll: visual frames until pose settles
ANIM_KO_FRAMES = 20

# Particles (integer velocities px/s scaled per frame in renderer)
ANIM_PARTICLE_LIGHT_COUNT  = (3, 5)
ANIM_PARTICLE_LIGHT_LIFE   = (8, 12)   # frames
ANIM_PARTICLE_LIGHT_SPEED  = 3         # ± px/frame equivalent
ANIM_PARTICLE_HEAVY_COUNT  = (6, 10)
ANIM_PARTICLE_HEAVY_LIFE   = (10, 16)
ANIM_PARTICLE_HEAVY_SPEED  = 5
ANIM_PARTICLE_BLOCK_COUNT  = (2, 4)

# Renderer shake (module-level; additive to game shake)
ANIM_SHAKE_HEAVY_INTENSITY = 4   # px
ANIM_SHAKE_HEAVY_FRAMES      = 6

# HUD ghost bar
ANIM_HUD_GHOST_DRAIN_SEC = 0.4
ANIM_HUD_LOW_PULSE_SEC   = 0.5
ANIM_HUD_BAR_FLASH_FRAMES = 3

# Countdown / round text (steps at 60Hz nominal)
ANIM_COUNTDOWN_ROUND_SCALE_FRAMES = 12   # 0→1 ease
ANIM_COUNTDOWN_FIGHT_SCALE_FRAMES = 8
ANIM_ROUNDEND_KO_SLAM_FRAMES        = 10

# Parallax crowd
ANIM_PARALLAX_FACTOR_NUM = 5   # 0.05 = 5/100
ANIM_PARALLAX_FACTOR_DEN = 100

# Floor shadow
ANIM_SHADOW_BASE_W = 36
ANIM_SHADOW_BASE_H = 10

# Procedural fighter (no sprites)
USE_PROCEDURAL_FIGHTER = True
SKIN_TONE = (220, 180, 155)

# --- Debug ---------------------------------------------------------------------
DRAW_ATTACK_HITBOXES = False

# --- Asset paths (relative to repo root or simulation/) ------------------------
import os

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ASSETS_FIGHTERS = os.path.join(_REPO_ROOT, "assets", "fighters")

# --- Round rules --------------------------------------------------------------
ROUNDS_TO_WIN      = 2      # round wins needed to win the match
COUNTDOWN_DURATION = 1.0    # seconds per countdown step
ROUND_END_DELAY    = 2.8    # seconds to show KO screen before advancing

# --- Visual feedback ----------------------------------------------------------
HIT_FLASH_DURATION = 0.14   # seconds player flashes white after taking damage

# --- Player start positions ---------------------------------------------------
P1_START_X = SCREEN_WIDTH  // 4        # horizontal centre for P1
P2_START_X = (SCREEN_WIDTH * 3) // 4  # horizontal centre for P2
START_Y    = FLOOR_Y - PLAYER_HEIGHT   # vertical start (standing on floor)

# =============================================================================
# Trig LUT: sin/cos * 256 for phase 0..255 (integer math)
# Arduino equivalent: constexpr int8_t SIN256[256] in PROGMEM
# =============================================================================

def _build_sin256():
    import math
    return [int(round(256 * math.sin(2 * math.pi * i / 256))) for i in range(256)]


SIN256 = _build_sin256()
COS256 = [SIN256[(i + 64) % 256] for i in range(256)]


def sin_scaled(phase_256: int, amplitude: int) -> int:
    """Returns (amplitude * sin(phase)) using integer math. phase_256 in 0..255."""
    p = phase_256 & 255
    return (SIN256[p] * amplitude) >> 8


def cos_scaled(phase_256: int, amplitude: int) -> int:
    p = phase_256 & 255
    return (COS256[p] * amplitude) >> 8

# =============================================================================
# Colors
# =============================================================================
BLACK       = (  0,   0,   0)
WHITE       = (255, 255, 255)
DARK_GRAY   = ( 30,  30,  30)
GRAY        = ( 80,  80,  80)
LIGHT_GRAY  = (170, 170, 170)

RED         = (220,  50,  50)
DARK_RED    = (100,  15,  15)
GREEN       = ( 50, 195,  75)
BLUE        = ( 50, 110, 220)
DARK_BLUE   = ( 15,  35, 110)
YELLOW      = (255, 215,   0)
ORANGE      = (255, 145,   0)
CYAN        = (  0, 200, 215)

# Player colors
P1_COLOR        = ( 65, 130, 220)   # blue fighter
P1_ATTACK_COLOR = (140, 195, 255)   # lighter blue during attack
P2_COLOR        = (215,  65,  65)   # red fighter
P2_ATTACK_COLOR = (255, 155, 140)   # lighter red during attack

# Environment — title / pause screens (twilight)
BG_COLOR         = ( 22,  28,  52)   # deep indigo (matches stage sky bottom)

# Stage: twilight campus / library facade (Butler-inspired)
SKY_TOP          = ( 55,  40,  95)   # violet
SKY_BOTTOM       = ( 22,  28,  52)   # indigo night
BUILDING_FACE    = ( 72,  70,  78)   # limestone grey
BUILDING_DARK    = ( 48,  46,  54)   # shadow / cornice
WINDOW_FRAME     = ( 38,  38,  46)
WINDOW_GLOW      = (255, 145,  65)   # warm lamp from windows
WINDOW_GLOW_SOFT = (180,  95,  45)   # inner core
COLUMN_HIGHLIGHT = ( 92,  90, 100)
FLOOR_COLOR      = ( 38,  42,  55)   # plaza pavement
FLOOR_LINE_COLOR = ( 85,  90, 110)
LAMP_POST        = ( 30,  30,  36)
LAMP_GLOW        = (255, 230, 160)

# Crowd parallax (silhouette bands)
CROWD_BAND_A = (45, 40, 58)
CROWD_BAND_B = (35, 32, 48)

# HUD
HP_BAR_BG   = ( 55,  18,  18)
HP_BAR_FG   = ( 55, 185,  75)   # healthy
HP_BAR_LOW  = (215,  55,  55)   # below 30%
HP_BORDER   = (200, 200, 200)
HP_GHOST    = (200, 170,  60)   # yellow trailing damage

# Fonts (passed as strings to renderer)
FONT_LARGE  = 68
FONT_MEDIUM = 38
FONT_SMALL  = 24
