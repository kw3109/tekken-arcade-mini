# =============================================================================
# renderer.py — All drawing code. No game logic lives here.
#
# Arduino mapping:
#   These functions become TFT drawing calls (tft.fillRect, tft.drawString,
#   tft.drawLine, etc.). The same separation of logic vs. rendering applies.
# =============================================================================

from __future__ import annotations

import random

import pygame

from constants import *
from player import Action

# Module-level font cache; populated by init_fonts()
_fonts: dict = {}

# Optional: set by Game after loading sprites
_player1_sprites: dict | None = None
_player2_sprites: dict | None = None

# --- Screen shake (visual hitstop); separate from Game's decaying shake magnitude
# Arduino equivalent: int8_t shakeFrames; apply random offset to tft.setOrigin
shake_frames = 0
shake_intensity = 0
_shake_dx = 0
_shake_dy = 0

# --- HUD ghost / flash (smooth damage bar)
# Arduino equivalent: static HUDGhostState { uint8_t ghostHp, flash, phase; }
_hud_last_hp1 = MAX_HEALTH
_hud_last_hp2 = MAX_HEALTH
_hud_ghost_t1 = 0.0
_hud_ghost_t2 = 0.0
_hud_ghost_from1 = MAX_HEALTH
_hud_ghost_from2 = MAX_HEALTH
_hud_flash1 = 0
_hud_flash2 = 0
_hud_pulse_phase = 0

# --- Countdown / round-end text animation
# Arduino equivalent: uint8_t countdownAnimFrame; char lastText[32]
_countdown_prev_text: str | None = None
_countdown_anim_frame = 0
_round_end_anim_frame = 0

# Global particle system instance (main may also reference)
particles = None  # set in init_fonts or first use


def init_fonts():
    """Call once after pygame.init() to populate the font cache."""
    global particles
    _fonts["large"] = pygame.font.Font(None, FONT_LARGE)
    _fonts["medium"] = pygame.font.Font(None, FONT_MEDIUM)
    _fonts["small"] = pygame.font.Font(None, FONT_SMALL)
    if particles is None:
        particles = ParticleSystem()


def set_sprite_sets(p1sprites: dict | None, p2sprites: dict | None):
    """Register loaded fighter surfaces (may be empty dicts)."""
    global _player1_sprites, _player2_sprites
    _player1_sprites = p1sprites if p1sprites else None
    _player2_sprites = p2sprites if p2sprites else None


def trigger_shake(intensity: int, frames: int) -> None:
    """Queue screen shake for heavy hits. Arduino equivalent: shakeFrames = N; shakeAmp = k."""
    global shake_frames, shake_intensity
    shake_frames = max(shake_frames, int(frames))
    shake_intensity = max(shake_intensity, int(intensity))


def reset_hud_visual_state() -> None:
    """Call on round reset. Arduino equivalent: memset(&hudGhost, 0, sizeof)."""
    global _hud_last_hp1, _hud_last_hp2, _hud_ghost_t1, _hud_ghost_t2
    global _hud_ghost_from1, _hud_ghost_from2, _hud_flash1, _hud_flash2, _hud_pulse_phase
    _hud_last_hp1 = MAX_HEALTH
    _hud_last_hp2 = MAX_HEALTH
    _hud_ghost_t1 = 1.0
    _hud_ghost_t2 = 1.0
    _hud_ghost_from1 = MAX_HEALTH
    _hud_ghost_from2 = MAX_HEALTH
    _hud_flash1 = 0
    _hud_flash2 = 0
    _hud_pulse_phase = 0


def reset_round_end_animation() -> None:
    """Arduino equivalent: roundEndFrame = 0."""
    global _round_end_anim_frame
    _round_end_anim_frame = 0


def advance_round_end_frame() -> None:
    """Call once per frame during ROUND_END. Arduino equivalent: roundEndFrame++."""
    global _round_end_anim_frame
    _round_end_anim_frame += 1


class ParticleSystem:
    """Lightweight hit particles."""

    def __init__(self):
        # Arduino equivalent: Particle particles[MAX_PART]; uint8_t particleCount;
        self.particles: list[dict] = []

    def clear(self) -> None:
        # Arduino equivalent: particleCount = 0;
        self.particles.clear()

    def spawn_hit_burst(self, cx: int, cy: int, kind: str) -> None:
        # Arduino equivalent: push N particles with rng vx,vy,life,color into ring buffer
        if kind == "light":
            n = random.randint(ANIM_PARTICLE_LIGHT_COUNT[0], ANIM_PARTICLE_LIGHT_COUNT[1])
            life_r = ANIM_PARTICLE_LIGHT_LIFE
            spd = ANIM_PARTICLE_LIGHT_SPEED
            colors = (SPARK_LINE_LIGHT, WHITE, YELLOW)
        elif kind == "heavy":
            n = random.randint(ANIM_PARTICLE_HEAVY_COUNT[0], ANIM_PARTICLE_HEAVY_COUNT[1])
            life_r = ANIM_PARTICLE_HEAVY_LIFE
            spd = ANIM_PARTICLE_HEAVY_SPEED
            colors = ((255, 200, 80), ORANGE, YELLOW, (255, 140, 40))
        else:  # block
            n = random.randint(ANIM_PARTICLE_BLOCK_COUNT[0], ANIM_PARTICLE_BLOCK_COUNT[1])
            life_r = ANIM_PARTICLE_LIGHT_LIFE
            spd = 2
            colors = (WHITE, (180, 210, 255), CYAN)

        for _ in range(n):
            life = random.randint(life_r[0], life_r[1])
            self.particles.append(
                {
                    "x": float(cx),
                    "y": float(cy),
                    "vx": float(random.randint(-spd, spd)),
                    "vy": float(random.randint(-spd, spd)),
                    "life": life,
                    "max_life": life,
                    "color": random.choice(colors),
                    "kind": kind,
                }
            )

    def update(self, dt: float) -> None:
        # Arduino equivalent: for each p: p.x+=vx; p.y+=vy; p.life--; cull if life==0
        alive = []
        for p in self.particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["life"] -= 1
            if p["life"] > 0:
                alive.append(p)
        self.particles = alive

    def draw(self, surface: pygame.Surface, offset=(0, 0)) -> None:
        # Arduino equivalent: for each p: alpha = life*255/max; tft.fillCircle
        ox, oy = int(offset[0]), int(offset[1])
        for p in self.particles:
            mx = int(p["x"]) + ox
            my = int(p["y"]) + oy
            ml = max(1, p["max_life"])
            a = int(255 * p["life"] // ml)
            col = p["color"]
            if len(col) == 3:
                c = (*col, a)
            else:
                c = col
            s = pygame.Surface((10, 10), pygame.SRCALPHA)
            r = 3 if p["kind"] == "heavy" else 2
            pygame.draw.circle(s, c, (5, 5), r)
            surface.blit(s, (mx - 5, my - 5))


def update_visual_systems(dt: float, p1, p2) -> None:
    """Particles, shake tick, HUD ghost drain, flash decay. Arduino equivalent: one vsync tick."""
    global shake_frames, shake_intensity, _shake_dx, _shake_dy
    global _hud_last_hp1, _hud_last_hp2, _hud_ghost_t1, _hud_ghost_t2
    global _hud_ghost_from1, _hud_ghost_from2, _hud_flash1, _hud_flash2, _hud_pulse_phase

    _shake_dx = _shake_dy = 0
    if shake_frames > 0 and shake_intensity > 0:
        _shake_dx = random.randint(-shake_intensity, shake_intensity)
        _shake_dy = random.randint(-shake_intensity, shake_intensity)
        shake_frames -= 1
        if shake_frames <= 0:
            shake_intensity = 0

    if p1.health < _hud_last_hp1:
        _hud_ghost_from1 = float(_hud_last_hp1)
        _hud_ghost_t1 = 0.0
        _hud_flash1 = ANIM_HUD_BAR_FLASH_FRAMES
    if p2.health < _hud_last_hp2:
        _hud_ghost_from2 = float(_hud_last_hp2)
        _hud_ghost_t2 = 0.0
        _hud_flash2 = ANIM_HUD_BAR_FLASH_FRAMES

    _hud_ghost_t1 += dt
    _hud_ghost_t2 += dt
    _hud_last_hp1 = p1.health
    _hud_last_hp2 = p2.health

    if _hud_flash1 > 0:
        _hud_flash1 -= 1
    if _hud_flash2 > 0:
        _hud_flash2 -= 1

    _hud_pulse_phase = (_hud_pulse_phase + int(dt * 256 / ANIM_HUD_LOW_PULSE_SEC)) & 255


def get_visual_shake_offset() -> tuple[int, int]:
    """Arduino equivalent: return (dx,dy) from shake state for this frame."""
    return _shake_dx, _shake_dy


def combine_offset(base, extra) -> tuple[int, int]:
    """Arduino equivalent: int16_t ox = baseX + shakeX."""
    return (int(base[0]) + int(extra[0]), int(base[1]) + int(extra[1]))


# =============================================================================
# Primitive helpers
# =============================================================================

def draw_text(surface, text, size, color, x, y, center=True):
    """Render a text string. size is 'large' | 'medium' | 'small'."""
    font = _fonts.get(size, _fonts["medium"])
    surf = font.render(str(text), True, color)
    rect = surf.get_rect(center=(x, y)) if center else surf.get_rect(topleft=(x, y))
    surface.blit(surf, rect)


def draw_text_scaled(
    surface,
    text,
    size,
    color,
    x,
    y,
    scale: float,
    center=True,
    glow_color=None,
    glow_offsets=((-2, 0), (2, 0), (0, -2), (0, 2)),
):
    # Arduino equivalent: tft.setTextSize(scale); drawString + offset duplicates for glow
    base = int(max(8, FONT_LARGE * scale)) if size == "large" else int(max(6, FONT_MEDIUM * scale))
    f = pygame.font.Font(None, base)
    if glow_color:
        for dx, dy in glow_offsets:
            gs = f.render(str(text), True, glow_color)
            gr = gs.get_rect(center=(x + dx, y + dy)) if center else gs.get_rect(topleft=(x + dx, y + dy))
            surface.blit(gs, gr)
    surf = f.render(str(text), True, color)
    rect = surf.get_rect(center=(x, y)) if center else surf.get_rect(topleft=(x, y))
    surface.blit(surf, rect)


# =============================================================================
# Hit VFX (legacy radial streaks — optional overlay)
# =============================================================================

def draw_hit_sparks(surface, sparks, offset=(0, 0)):
    """Radial streaks at impact points; sparks are dicts: x, y, t, kind."""
    import math

    ox, oy = int(offset[0]), int(offset[1])
    for s in sparks:
        cx = int(s["x"]) + ox
        cy = int(s["y"]) + oy
        life = max(0.0, min(1.0, s["t"] / HIT_SPARK_DURATION))
        if s["kind"] == "block":
            base = SPARK_LINE_BLOCK
        elif s["kind"] == "heavy":
            base = SPARK_LINE_HEAVY
        else:
            base = SPARK_LINE_LIGHT
        n = 12
        for i in range(n):
            ang = (i / n) * 2 * math.pi + (1.0 - life) * 0.8
            L = 10 + 22 * life + (i % 4) * 2
            ex = cx + int(math.cos(ang) * L)
            ey = cy + int(math.sin(ang) * L)
            w = 3 if i % 3 == 0 else 2
            pygame.draw.line(surface, base, (cx, cy), (ex, ey), w)
            pygame.draw.line(surface, SPARK_CORE, (cx, cy), (ex, ey), 1)
        r = max(2, int(5 * life))
        pygame.draw.circle(surface, SPARK_CORE, (cx, cy), r)


# =============================================================================
# Scene elements
# =============================================================================

def draw_background(surface, offset=(0, 0), p1=None, p2=None):
    """
    Twilight sky + neoclassical library facade + plaza floor.
    Optional parallax crowd bands from player midpoint.
    """
    ox, oy = int(offset[0]), int(offset[1])
    floor_y = FLOOR_Y

    parallax_x = 0
    if p1 is not None and p2 is not None:
        mid = (p1.get_center_x() + p2.get_center_x()) * 0.5
        disp = mid - (SCREEN_WIDTH // 2)
        parallax_x = -(disp * ANIM_PARALLAX_FACTOR_NUM) // ANIM_PARALLAX_FACTOR_DEN

    # --- Sky gradient --------------------------------------------------------
    for y in range(floor_y):
        t = y / max(floor_y, 1)
        r = int(SKY_TOP[0] * (1 - t) + SKY_BOTTOM[0] * t)
        g = int(SKY_TOP[1] * (1 - t) + SKY_BOTTOM[1] * t)
        b = int(SKY_TOP[2] * (1 - t) + SKY_BOTTOM[2] * t)
        pygame.draw.line(surface, (r, g, b), (ox, oy + y), (ox + SCREEN_WIDTH, oy + y))

    # --- Parallax crowd (two silhouette bands) -------------------------------
    band_h = 18
    y1 = floor_y - 42
    y2 = floor_y - 22
    for row_y, col, dx_scale in ((y1, CROWD_BAND_A, 1), (y2, CROWD_BAND_B, -1)):
        bx = ox + parallax_x * dx_scale
        w = 28
        for i in range(-2, SCREEN_WIDTH // w + 3):
            rx = bx + i * w + (i * 17) % 9
            h = band_h + (i * 13) % 7
            pygame.draw.rect(
                surface,
                col,
                pygame.Rect(int(rx), oy + row_y - h + band_h, w - 6, h),
            )

    # --- Building mass (facade) ---------------------------------------------
    b_top = 55
    facade = pygame.Rect(ox, oy + b_top, SCREEN_WIDTH, floor_y - b_top - 8)
    pygame.draw.rect(surface, BUILDING_FACE, facade)

    # Cornice / roof line
    pygame.draw.rect(surface, BUILDING_DARK, pygame.Rect(ox, oy + b_top - 12, SCREEN_WIDTH, 14))
    pygame.draw.line(
        surface,
        COLUMN_HIGHLIGHT,
        (ox, oy + b_top - 12),
        (ox + SCREEN_WIDTH, oy + b_top - 12),
        2,
    )

    # Column pilasters (vertical bands)
    col_w = 44
    for cx in range(ox - (ox % col_w), ox + SCREEN_WIDTH + col_w, col_w):
        pygame.draw.line(surface, BUILDING_DARK, (cx, oy + b_top), (cx, oy + floor_y - 8), 3)
        pygame.draw.line(surface, COLUMN_HIGHLIGHT, (cx + 2, oy + b_top), (cx + 2, oy + floor_y - 8), 1)

    # Window grid (glowing rectangles)
    win_w, win_h = 28, 36
    row_y = [b_top + 28, b_top + 88, b_top + 148]
    for ry in row_y:
        for wx in range(ox + 36, ox + SCREEN_WIDTH - 36, 62):
            wr = pygame.Rect(wx, oy + ry, win_w, win_h)
            pygame.draw.rect(surface, WINDOW_FRAME, wr)
            inner = wr.inflate(-6, -8)
            pygame.draw.rect(surface, WINDOW_GLOW_SOFT, inner)
            pygame.draw.rect(surface, WINDOW_GLOW, inner.inflate(-4, -6))

    # --- Street lamps (silhouette + glow) -----------------------------------
    for lx in (120, SCREEN_WIDTH // 2, SCREEN_WIDTH - 120):
        pole_top = oy + floor_y - 95
        pygame.draw.line(surface, LAMP_POST, (ox + lx, oy + floor_y - 5), (ox + lx, pole_top), 4)
        pygame.draw.circle(surface, LAMP_GLOW, (ox + lx, pole_top - 2), 14)
        pygame.draw.circle(surface, WHITE, (ox + lx, pole_top - 2), 14, 1)

    # --- Ground plane --------------------------------------------------------
    pygame.draw.rect(surface, FLOOR_COLOR, pygame.Rect(ox, oy + floor_y, SCREEN_WIDTH, SCREEN_HEIGHT - floor_y))
    pygame.draw.line(
        surface,
        FLOOR_LINE_COLOR,
        (ox, oy + floor_y),
        (ox + SCREEN_WIDTH, oy + floor_y),
        3,
    )


def draw_floor_shadow(surface, player, offset=(0, 0)) -> None:
    """Oval shadow under fighter; scales with jump height. Arduino equivalent: tft.fillEllipse alpha."""
    ox, oy = int(offset[0]), int(offset[1])
    floor_surface = float(FLOOR_Y - player.height)
    air = max(0.0, floor_surface - float(player.y))
    scale = 256 - int(min(180.0, air * 1.2))
    if scale < 64:
        scale = 64
    bw = (ANIM_SHADOW_BASE_W * scale) >> 8
    bh = (ANIM_SHADOW_BASE_H * scale) >> 8
    cx = int(player.x + player.width // 2) + ox
    cy = FLOOR_Y - 4 + oy
    ell = pygame.Surface((bw * 2 + 4, bh * 2 + 4), pygame.SRCALPHA)
    pygame.draw.ellipse(ell, (0, 0, 0, 90), (0, 0, bw * 2 + 4, bh * 2 + 4))
    surface.blit(ell, (cx - bw - 2, cy - bh - 2))


def _sprite_for_player(player, p1):
    if p1 and _player1_sprites:
        return _player1_sprites
    if not p1 and _player2_sprites:
        return _player2_sprites
    return None


def _ease_out_cubic(t: float) -> float:
    # Arduino equivalent: uint8_t easeOutCubic(uint8_t x) lookup
    u = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - u) ** 3


def _limb_poly(
    surface: pygame.Surface,
    color,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    th: int,
) -> None:
    # Arduino equivalent: compute perpendicular offsets with integer trig
    dx = x1 - x0
    dy = y1 - y0
    if dx == 0 and dy == 0:
        return
    length = max(1, int((dx * dx + dy * dy) ** 0.5))
    px = (-dy * th) // (2 * length)
    py = (dx * th) // (2 * length)
    pts = [
        (x0 + px, y0 + py),
        (x1 + px, y1 + py),
        (x1 - px, y1 - py),
        (x0 - px, y0 - py),
    ]
    pygame.draw.polygon(surface, color, pts)
    pygame.draw.polygon(surface, WHITE, pts, 1)


def _draw_torso_capsule(
    surface: pygame.Surface, color: tuple, cx: int, top: int, w: int, h: int, lean: int
) -> None:
    # Arduino equivalent: tft.fillRoundRect or two ellipses + center rect — no sharp box
    r = pygame.Rect(cx - w // 2 + lean, top, w, h)
    pygame.draw.ellipse(surface, color, r)
    pygame.draw.ellipse(surface, WHITE, r, 2)


def draw_procedural_fighter(surface: pygame.Surface, player, ox: int, oy: int) -> None:
    """Articulated body from primitives. Arduino equivalent: drawRosterSpriteProcedural()."""
    rect = player.get_rect()
    base_x = rect.left + ox
    base_y = rect.top + oy
    w, h = rect.width, rect.height
    flip = 1 if player.facing_right else -1

    crouching = player.action == Action.CROUCHING and player.on_ground

    breath = sin_scaled(player.viz_breath_phase, 2) if not player.is_ko else 0
    torso_y_off = breath
    if player.viz_jump_squat > 0 or player.viz_land_squat > 0:
        torso_y_off += 3

    # Jump stretch / squash (visual)
    stretch_y = 0
    if not player.on_ground and not player.is_ko:
        if abs(player.vel_y) < 120:
            stretch_y = -4
        elif player.vel_y < ANIM_JUMP_STRETCH_PEAK_VY:
            stretch_y = 2

    cx = base_x + w // 2

    # KO ragdoll tilt
    tilt = 0
    if player.is_ko:
        t = player.viz_ko_frame
        tilt = sin_scaled(min(255, t * 12), 40)

    head_cy = base_y + 12 + torso_y_off + stretch_y // 2
    head_cx = cx + (tilt * flip) // 3
    pygame.draw.circle(surface, SKIN_TONE, (head_cx, head_cy), 11)
    pygame.draw.circle(surface, WHITE, (head_cx, head_cy), 11, 2)

    # Torso: rounded capsule (no sharp rectangle)
    torso_w = 24 if crouching else 26
    torso_h = max(22, min(32, h - 28))
    torso_top = base_y + 22 + torso_y_off + stretch_y
    if crouching:
        torso_top += 6
    lean = 0
    if player.action == Action.BLOCKING:
        lean = -8 * flip
    if player.is_ko:
        lean += tilt

    _draw_torso_capsule(surface, player.color, cx, torso_top, torso_w, torso_h, lean)

    # Phase 64 = "down" in sin256 ring; knee_delta = shin_angle - thigh_angle (bent knee forward in side view)
    thigh_len = 21
    shin_len = 19
    hip_y = torso_top + torso_h - 2
    hip_lx = cx - 9 + lean
    hip_rx = cx + 9 + lean

    heavy_pose = player.viz_heavy_recover > 0 or (
        player.action == Action.HEAVY_ATTACK and player.current_attack == "heavy"
    )
    kick_side = 0 if flip == 1 else 1

    # Walk: opposite leg swing; arms use same phase
    walk_phase = player.viz_walk_phase
    walk_swing = sin_scaled(walk_phase, 18) if player.action == Action.WALKING and player.on_ground else 0
    idle_sway = sin_scaled(player.viz_breath_phase, 3) if player.action == Action.IDLE and player.on_ground else 0
    air_phase = (player.viz_frame * 14) & 255

    def leg(side: int, phase_off: int):
        tlen = thigh_len
        slen = shin_len
        # knee_delta: extra angle from thigh → shin (0 = straight leg same line as thigh)
        ang = 64
        knee_delta = 0

        if heavy_pose and not player.is_ko:
            ph = player.viz_heavy_phase
            if side == kick_side:
                if player.viz_heavy_mode == 0:
                    ang = 36 - ph // 14
                    knee_delta = 8 + ph // 20
                    tlen = thigh_len + (ph >> 3)
                elif player.viz_heavy_mode == 1:
                    ang = 6 + ph // 40
                    knee_delta = 4
                    tlen = thigh_len + 14
                    slen = shin_len + 12
                else:
                    ang = 52 + ph // 18
                    knee_delta = 24 + ph // 22
            else:
                ang = 88 + sin_scaled(ph & 255, 6)
                knee_delta = 38
        elif player.is_ko:
            ang = 96 + sin_scaled((player.viz_ko_frame * 19 + phase_off * 40) & 255, 40)
            knee_delta = 36 + sin_scaled((player.viz_walk_phase + 64) & 255, 14)
        elif not player.on_ground:
            # Jump: thighs slightly forward, knees bent — legs stay apart (no X)
            lift = sin_scaled(air_phase + phase_off * 2, 12)
            ang = 58 + lift
            knee_delta = 52 + min(24, int(abs(player.vel_y)) >> 4)
        elif crouching:
            # Crouch: thighs angled down-forward, strong knee bend, feet under hips
            ang = 86 + (8 if side == 0 else -8)
            knee_delta = 58
        elif player.action == Action.WALKING:
            # Alternating stride: one leg forward, one back (phase_off 128° out of phase)
            swing = sin_scaled((walk_phase + phase_off) & 255, 20)
            ang = 64 + swing
            # More knee bend when foot passes under body (lift)
            knee_delta = 42 + abs(sin_scaled((walk_phase + phase_off + 64) & 255, 14))
        else:
            # Idle / blocking / recovery on feet: straight legs; tiny thigh sway only
            ang = 64 + idle_sway + sin_scaled((walk_phase + phase_off) & 255, 4)
            knee_delta = 0

        lx = hip_lx if side == 0 else hip_rx
        kx = lx + cos_scaled(ang, tlen) * flip
        ky = hip_y + sin_scaled(ang, tlen)
        _limb_poly(surface, player.color, lx, hip_y, kx, ky, 9)
        shin_ang = ang + knee_delta
        if player.is_ko:
            shin_ang += sin_scaled(player.viz_ko_frame * 23, 50)
        ax, ay = kx, ky
        fx = ax + cos_scaled(shin_ang, slen) * flip
        fy = ay + sin_scaled(shin_ang, slen)
        kick_col = player.attack_color if heavy_pose and side == kick_side and not player.is_ko else player.color
        shin_col = SKIN_TONE if player.is_ko else kick_col
        _limb_poly(surface, shin_col, ax, ay, fx, fy, 7)
        pygame.draw.circle(surface, SKIN_TONE, (fx, fy), 4)

    leg(0, 0)
    leg(1, 128)

    # Arms
    shoulder_y = torso_top + max(4, torso_h // 5)
    shoulder_lx = cx - torso_w // 2 + lean
    shoulder_rx = cx + torso_w // 2 + lean

    arm_swing = -walk_swing if player.action == Action.WALKING else 0

    def arm(side: int, phase_off: int):
        sx = shoulder_lx if side == 0 else shoulder_rx
        uang = 32 + arm_swing + sin_scaled((walk_phase + phase_off) & 255, 18)
        if crouching:
            uang = 22 + (12 if side == 0 else -12)
        elif not player.on_ground:
            uang = 30 + sin_scaled(air_phase + phase_off * 2, 14)
        elif player.action == Action.BLOCKING:
            uang = 8 + (16 if side == 0 else -16)
        if player.action == Action.LIGHT_ATTACK and player.current_attack == "light":
            step = player.viz_light_step
            ext = 26 if step < ANIM_LIGHT_EXTEND_STEPS else 8
            punch = (step < ANIM_LIGHT_EXTEND_STEPS) * (ext * (step + 1) // ANIM_LIGHT_EXTEND_STEPS)
            uang = 16 - punch // 3
        if heavy_pose:
            # Heavy = kick: arms guard / counterbalance, not a punch (Arduino: armAnglesKickPose[])
            ph = player.viz_heavy_phase
            if player.viz_heavy_mode == 0:
                uang = 40 - ph // 16
            elif player.viz_heavy_mode == 1:
                uang = 52 + (16 if side == 0 else -16)
            else:
                uang = 32 + ph // 20
        if player.is_ko:
            uang = 64 + sin_scaled((player.viz_ko_frame * 17 + side * 50) & 255, 50)

        ex = sx + cos_scaled(uang, 18) * flip
        ey = shoulder_y + sin_scaled(uang, 18)
        _limb_poly(surface, SKIN_TONE, sx, shoulder_y, ex, ey, 8)
        fang = uang - 16
        if player.action == Action.LIGHT_ATTACK and player.current_attack == "light":
            fang = max(4, uang - 40)
        fx = ex + cos_scaled(fang, 22) * flip
        fy = ey + sin_scaled(fang, 22)
        atk_col = (
            player.attack_color
            if (player.action in (Action.LIGHT_ATTACK, Action.HEAVY_ATTACK) or heavy_pose)
            else player.color
        )
        _limb_poly(surface, atk_col, ex, ey, fx, fy, 7)
        pygame.draw.circle(surface, SKIN_TONE, (fx, fy), 4)

    arm(0, 128)
    arm(1, 0)

    # Eye
    eye_x = head_cx + (6 * flip)
    eye_y = head_cy - 2
    pygame.draw.circle(surface, WHITE, (eye_x, eye_y), 4)
    pygame.draw.circle(surface, BLACK, (eye_x + (1 * flip), eye_y), 2)


def draw_player(surface, player, sprite_dict=None, p1=True, offset=(0, 0)):
    # Arduino equivalent: blitSpriteChain() or drawFighterParts() with shared shake origin
    """Draw the fighter using procedural geometry or sprites when allowed."""
    ox, oy = int(offset[0]), int(offset[1])
    rect = player.get_rect()
    draw_rect = rect.move(ox, oy)

    use_proc = USE_PROCEDURAL_FIGHTER
    sprites = sprite_dict if sprite_dict is not None else _sprite_for_player(player, p1)
    if use_proc:
        draw_floor_shadow(surface, player, (ox, oy))
        draw_procedural_fighter(surface, player, ox, oy)
    elif sprites:
        key = player.anim_key
        surf = sprites.get(key)
        if surf is None and key == "kick":
            surf = sprites.get("heavy")
        if surf is None:
            surf = sprites.get("idle")
        if surf is not None:
            img = surf
            if not player.facing_right:
                img = pygame.transform.flip(surf, True, False)
            pos = (int(player.x) + ox, int(player.y) + oy)
            if player.attack_active and player.anim_key in ("light", "kick"):
                sg = 1 if player.facing_right else -1
                for da, alpha in ((10, 45), (20, 30), (30, 18)):
                    ghost = img.copy()
                    ghost.set_alpha(alpha)
                    surface.blit(ghost, (pos[0] - sg * da, pos[1]))
            surface.blit(img, pos)
            if player.is_flashing() and int(player.hit_flash_timer * 22) % 2 == 0:
                flash = pygame.Surface(img.get_size(), pygame.SRCALPHA)
                flash.fill((255, 255, 255, 130))
                surface.blit(flash, pos)
    else:
        if player.is_flashing() and int(player.hit_flash_timer * 22) % 2 == 0:
            fill_color = WHITE
        elif player.action in (Action.LIGHT_ATTACK, Action.HEAVY_ATTACK):
            fill_color = player.attack_color
        elif player.action == Action.BLOCKING:
            fill_color = GRAY
        elif player.action == Action.KO:
            fill_color = DARK_GRAY
        else:
            fill_color = player.color

        pygame.draw.rect(surface, fill_color, draw_rect)
        pygame.draw.rect(surface, WHITE, draw_rect, 2)

        eye_offset = draw_rect.width - 10 if player.facing_right else 10
        eye_x = draw_rect.left + eye_offset
        eye_y = draw_rect.top + 16
        pygame.draw.circle(surface, WHITE, (eye_x, eye_y), 6)
        pupil_offset = 2 if player.facing_right else -2
        pygame.draw.circle(surface, BLACK, (eye_x + pupil_offset, eye_y), 3)

    if player.action == Action.BLOCKING:
        shield_x = draw_rect.right if player.facing_right else draw_rect.left - 8
        pygame.draw.rect(surface, CYAN, pygame.Rect(shield_x, draw_rect.top + 10, 8, draw_rect.height - 20))

    atk_rect = player.get_attack_hitbox()
    if atk_rect and DRAW_ATTACK_HITBOXES:
        r = atk_rect.move(ox, oy)
        pygame.draw.rect(surface, YELLOW, r, 2)

    hw = player.profile.heavy_windup
    if player.action == Action.HEAVY_ATTACK and player.attack_windup > 0 and hw > 0:
        ratio = player.attack_windup / hw
        bar_w = int(player.width * ratio)
        pygame.draw.rect(
            surface,
            ORANGE,
            pygame.Rect(int(player.x) + ox, int(player.y) + oy - 12, bar_w, 6),
        )


def draw_cooldown_bars(surface, p1, p2, offset=(0, 0)):
    """Small bars above each player showing cooldown remaining."""
    ox, oy = int(offset[0]), int(offset[1])
    for player in (p1, p2):
        base_y = int(player.y) + oy - 10
        lc = player.profile.light_cooldown
        hc = player.profile.heavy_cooldown

        if player.light_cooldown > 0 and lc > 0:
            ready_ratio = 1.0 - (player.light_cooldown / lc)
            bar_w = int(player.width * ready_ratio)
            pygame.draw.rect(surface, DARK_GRAY, pygame.Rect(int(player.x) + ox, base_y - 14, player.width, 5))
            pygame.draw.rect(surface, CYAN, pygame.Rect(int(player.x) + ox, base_y - 14, bar_w, 5))

        if player.heavy_cooldown > 0 and hc > 0:
            ready_ratio = 1.0 - (player.heavy_cooldown / hc)
            bar_w = int(player.width * ready_ratio)
            pygame.draw.rect(surface, DARK_GRAY, pygame.Rect(int(player.x) + ox, base_y - 22, player.width, 5))
            pygame.draw.rect(surface, ORANGE, pygame.Rect(int(player.x) + ox, base_y - 22, bar_w, 5))


def draw_action_label(surface, p1, p2, offset=(0, 0)):
    """Tiny state label beneath each fighter — helpful during development."""
    ox, oy = int(offset[0]), int(offset[1])
    for player in (p1, p2):
        rect = player.get_rect().move(ox, oy)
        label = player.action.upper()
        if player.hitstun_timer > 0:
            label += f"  STUN {player.hitstun_timer:.2f}"
        draw_text(surface, label, "small", LIGHT_GRAY, rect.centerx, rect.bottom + 14)


# =============================================================================
# HUD
# =============================================================================

def draw_hud(surface, p1, p2, round_num, p1_wins, p2_wins, hitstop_hint=False):
    """Health bars, win pips, and round number."""
    bar_w = 310
    bar_h = 26
    bar_y = 12
    padding = 18

    _draw_health_bar(
        surface,
        x=padding,
        y=bar_y,
        w=bar_w,
        h=bar_h,
        health=p1.health,
        max_health=MAX_HEALTH,
        label="P1",
        flip=False,
        ghost_from=_hud_ghost_from1,
        ghost_t=_hud_ghost_t1,
        flash=_hud_flash1,
        pulse_phase=_hud_pulse_phase,
    )

    _draw_health_bar(
        surface,
        x=SCREEN_WIDTH - padding - bar_w,
        y=bar_y,
        w=bar_w,
        h=bar_h,
        health=p2.health,
        max_health=MAX_HEALTH,
        label="P2",
        flip=True,
        ghost_from=_hud_ghost_from2,
        ghost_t=_hud_ghost_t2,
        flash=_hud_flash2,
        pulse_phase=_hud_pulse_phase,
    )

    draw_text(surface, f"ROUND {round_num}", "small", WHITE, SCREEN_WIDTH // 2, bar_y + bar_h // 2)

    if hitstop_hint:
        draw_text(surface, "!", "small", YELLOW, SCREEN_WIDTH // 2, bar_y + bar_h + 36)

    pip_y = bar_y + bar_h + 10
    pip_r = 7
    pip_gap = 20

    for i in range(ROUNDS_TO_WIN):
        cx = padding + pip_r + i * pip_gap
        color = YELLOW if i < p1_wins else DARK_GRAY
        pygame.draw.circle(surface, color, (cx, pip_y), pip_r)
        pygame.draw.circle(surface, WHITE, (cx, pip_y), pip_r, 1)

        cx = SCREEN_WIDTH - padding - pip_r - i * pip_gap
        color = YELLOW if i < p2_wins else DARK_GRAY
        pygame.draw.circle(surface, color, (cx, pip_y), pip_r)
        pygame.draw.circle(surface, WHITE, (cx, pip_y), pip_r, 1)


def _draw_health_bar(surface, x, y, w, h, health, max_health, label, flip, ghost_from, ghost_t, flash, pulse_phase):
    """Ghost yellow bar + immediate red/green fill. Arduino equivalent: drawHpBarGhost()."""
    ratio = health / max_health
    fill_w = max(0, int(w * ratio))

    u = min(1.0, ghost_t / ANIM_HUD_GHOST_DRAIN_SEC)
    ghost_hp = ghost_from + (float(health) - ghost_from) * u
    ghost_ratio = max(0.0, min(1.0, ghost_hp / max_health))
    ghost_w = max(0, int(w * ghost_ratio))

    low = ratio < 0.25
    if low:
        # Arduino equivalent: uint8_t t = (SIN256[phase]*128>>8)+128; lerp RGB by t>>8
        blend = sin_scaled(pulse_phase, 128) + 128
        bar_color = (
            (RED[0] * blend + DARK_RED[0] * (256 - blend)) >> 8,
            (RED[1] * blend + DARK_RED[1] * (256 - blend)) >> 8,
            (RED[2] * blend + DARK_RED[2] * (256 - blend)) >> 8,
        )
    else:
        bar_color = HP_BAR_LOW if ratio < 0.30 else HP_BAR_FG

    if flash > 0:
        bar_color = WHITE

    pygame.draw.rect(surface, HP_BAR_BG, (x, y, w, h))

    if flip:
        if ghost_w > 0:
            pygame.draw.rect(surface, HP_GHOST, (x + w - ghost_w, y, ghost_w, h))
        if fill_w > 0:
            pygame.draw.rect(surface, bar_color, (x + w - fill_w, y, fill_w, h))
    else:
        if ghost_w > 0:
            pygame.draw.rect(surface, HP_GHOST, (x, y, ghost_w, h))
        if fill_w > 0:
            pygame.draw.rect(surface, bar_color, (x, y, fill_w, h))

    pygame.draw.rect(surface, HP_BORDER, (x, y, w, h), 2)

    draw_text(surface, f"{label}  {health}", "small", WHITE, x + w // 2, y + h // 2)


# =============================================================================
# Game state screens
# =============================================================================

def draw_character_select(surface, roster, p1_idx, p2_idx, p1_locked, p2_locked, preview_by_id):
    """Roster pick screen: two columns with idle previews."""
    surface.fill(BG_COLOR)

    draw_text(surface, "SELECT  FIGHTER", "large", YELLOW, SCREEN_WIDTH // 2, 72)
    draw_text(surface, "K / HEAVY = KICK", "small", LIGHT_GRAY, SCREEN_WIDTH // 2, 118)

    cx1 = SCREEN_WIDTH // 4
    cx2 = (SCREEN_WIDTH * 3) // 4
    panel_w, panel_h = 200, 260
    y0 = 150

    for cx, idx, locked, label in (
        (cx1, p1_idx, p1_locked, "PLAYER 1"),
        (cx2, p2_idx, p2_locked, "PLAYER 2"),
    ):
        f = roster[idx]
        border = YELLOW if locked else LIGHT_GRAY
        rect = pygame.Rect(0, 0, panel_w, panel_h)
        rect.center = (cx, y0 + panel_h // 2)
        pygame.draw.rect(surface, DARK_GRAY, rect)
        pygame.draw.rect(surface, border, rect, 4)

        pv = preview_by_id.get(f.id)
        if pv is not None:
            pr = pv.get_rect(center=(cx, y0 + 95))
            surface.blit(pv, pr)

        draw_text(surface, label, "small", WHITE, cx, y0 + 18)
        draw_text(surface, f.display_name, "medium", f.body_color, cx, y0 + 168)
        st = "LOCKED" if locked else "Choose…"
        draw_text(surface, st, "small", GRAY, cx, y0 + 200)

    draw_text(surface, "P1:  A / D  cycle     J or SPACE  lock", "small", P1_COLOR, SCREEN_WIDTH // 2, SCREEN_HEIGHT - 120)
    draw_text(surface, "P2:  ← / →  cycle     ,  lock", "small", P2_COLOR, SCREEN_WIDTH // 2, SCREEN_HEIGHT - 88)
    if p1_locked and p2_locked:
        draw_text(surface, "Press  ENTER  to  fight", "medium", WHITE, SCREEN_WIDTH // 2, SCREEN_HEIGHT - 48)
    else:
        draw_text(surface, "Lock both fighters  →  ENTER", "small", GRAY, SCREEN_WIDTH // 2, SCREEN_HEIGHT - 48)
    draw_text(surface, "ESC  —  back to title", "small", GRAY, SCREEN_WIDTH // 2, SCREEN_HEIGHT - 18)


def draw_menu(surface):
    surface.fill(BG_COLOR)

    draw_text(surface, "TEKKEN  MINI", "large", YELLOW, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3 - 10)
    draw_text(surface, "2-PLAYER ARCADE FIGHTER", "medium", LIGHT_GRAY, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3 + 52)

    draw_text(surface, "Press  ENTER  to  select  fighters", "medium", WHITE, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 30)

    ctrl_y = SCREEN_HEIGHT * 3 // 4
    draw_text(
        surface,
        "P1:  A/D  Move    W  Jump    S  Crouch    J  Light    K  Kick    L  Block",
        "small",
        P1_COLOR,
        SCREEN_WIDTH // 2,
        ctrl_y,
    )
    draw_text(
        surface,
        "P2:  ←/→  Move    ↑  Jump    ↓  Crouch    ,  Light    .  Kick    /  Block",
        "small",
        P2_COLOR,
        SCREEN_WIDTH // 2,
        ctrl_y + 28,
    )
    draw_text(surface, "ESC  Pause / Quit", "small", GRAY, SCREEN_WIDTH // 2, ctrl_y + 60)


def draw_countdown(surface, text):
    """Animated countdown overlay: ROUND scales 12f, FIGHT 8f + glow, numeric bounce."""
    global _countdown_prev_text, _countdown_anim_frame
    if text != _countdown_prev_text:
        _countdown_prev_text = text
        _countdown_anim_frame = 0
    else:
        _countdown_anim_frame += 1

    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 110))
    surface.blit(overlay, (0, 0))

    cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
    t_round = text.upper().startswith("ROUND")
    t_fight = text.strip().upper().startswith("FIGHT")

    if t_round:
        n = max(1, ANIM_COUNTDOWN_ROUND_SCALE_FRAMES)
        u = min(1.0, _countdown_anim_frame / float(n))
        sc = _ease_out_cubic(u)
        draw_text_scaled(surface, text, "large", WHITE, cx, cy, max(0.15, sc), glow_color=None)
    elif t_fight:
        n = max(1, ANIM_COUNTDOWN_FIGHT_SCALE_FRAMES)
        u = min(1.0, _countdown_anim_frame / float(n))
        sc = _ease_out_cubic(u)
        draw_text_scaled(surface, text, "large", WHITE, cx, cy, max(0.2, sc), glow_color=YELLOW)
    else:
        draw_text(surface, text, "large", WHITE, cx, cy)


def draw_round_end(surface, round_win_text):
    """KO overlay with slam-in K.O. Arduino equivalent: drawRoundEndOverlay()."""
    global _round_end_anim_frame
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 150))
    surface.blit(overlay, (0, 0))

    n = max(1, ANIM_ROUNDEND_KO_SLAM_FRAMES)
    u = min(1.0, _round_end_anim_frame / float(n))
    # overshoot: 3 -> 0.9 -> 1.0
    if u < 0.85:
        sc = 3.0 - (3.0 - 0.9) * (u / 0.85)
    else:
        sc = 0.9 + 0.1 * ((u - 0.85) / 0.15)

    draw_text_scaled(surface, "K.O.", "large", RED, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 40, sc, glow_color=None)
    draw_text(surface, round_win_text, "medium", YELLOW, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 30)


def draw_paused(surface):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    surface.blit(overlay, (0, 0))
    draw_text(surface, "PAUSED", "large", WHITE, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
    draw_text(surface, "ESC to resume", "small", LIGHT_GRAY, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 55)


def draw_game_over(surface, winner_text):
    surface.fill(BG_COLOR)
    draw_text(surface, "GAME  OVER", "large", RED, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3)
    draw_text(surface, winner_text, "medium", YELLOW, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
    draw_text(surface, "ENTER — Play Again     ESC — Quit", "small", LIGHT_GRAY, SCREEN_WIDTH // 2, SCREEN_HEIGHT * 2 // 3 + 10)


# Initialize HUD state on import
reset_hud_visual_state()
