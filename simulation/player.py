# =============================================================================
# player.py — Player class: physics, state, attacks, health.
#
# Arduino mapping:
#   - This class becomes a C struct + set of update functions.
#   - Floats become int16_t (fixed-point or scaled pixel coords).
#   - Timers become uint32_t counters using millis() deltas.
# =============================================================================

import pygame

from character_data import CharacterProfile
from constants import *


# --- Action states ------------------------------------------------------------
class Action:
    IDLE         = "idle"
    WALKING      = "walking"
    JUMPING      = "jumping"
    CROUCHING    = "crouching"
    LIGHT_ATTACK = "light_attack"
    HEAVY_ATTACK = "heavy_attack"
    BLOCKING     = "blocking"
    KO           = "ko"


# =============================================================================
class Player:
    """
    Represents one fighter. Owns physics, health, cooldowns, and state.
    Input is passed in as an 'actions' dict (see input_handler.py), so
    the class itself has no knowledge of which keys are pressed.
    """

    def __init__(
        self,
        x,
        y,
        color,
        attack_color,
        profile: CharacterProfile,
        facing_right=True,
    ):
        self.profile = profile

        # ── Spatial state ──────────────────────────────────────────────────
        self.x = float(x)
        self.y = float(y)
        self.width  = PLAYER_WIDTH
        self.height = PLAYER_HEIGHT

        self.vel_x     = 0.0
        self.vel_y     = 0.0
        self.on_ground = True
        self.facing_right = facing_right

        # ── Visual / identity ──────────────────────────────────────────────
        self.color        = color
        self.attack_color = attack_color

        # ── Health & score ─────────────────────────────────────────────────
        self.health      = MAX_HEALTH
        self.round_wins  = 0
        self.is_ko       = False

        # ── Action / animation state ───────────────────────────────────────
        self.action = Action.IDLE
        self.anim_key = "idle"
        self.walk_phase = 0
        self.walk_anim_timer = 0.0

        # ── Attack timers ──────────────────────────────────────────────────
        self.light_cooldown  = 0.0
        self.heavy_cooldown  = 0.0

        self.attack_timer    = 0.0
        self.attack_windup   = 0.0
        self.attack_active   = False
        self.current_attack  = None  # "light" or "heavy"
        self.hit_registered  = False
        self.recovery_timer  = 0.0
        self.attack_low      = False  # True if attack started from crouch

        # ── Hitstun ────────────────────────────────────────────────────────
        self.hitstun_timer = 0.0

        # ── Visual feedback ────────────────────────────────────────────────
        self.hit_flash_timer = 0.0

        # ── Visual-only animation (no gameplay / hitbox effect) ---------------
        # Arduino equivalent: separate struct VizState updated after physics step
        self.viz_frame = 0
        self.viz_breath_phase = 0
        self.viz_walk_phase = 0
        self.viz_jump_squat = 0
        self.viz_land_squat = 0
        self.viz_prev_on_ground = True
        self.viz_ko_frame = 0
        self.viz_light_step = 0
        self.viz_heavy_mode = 0
        self.viz_heavy_phase = 0
        self.viz_heavy_recover = 0
        self._viz_prev_in_heavy_attack = False

    # =========================================================================
    # Public API
    # =========================================================================

    def update(self, dt, actions, opponent):
        if self.is_ko:
            self._apply_physics(dt)
            self._update_visual_animation(dt)
            self.anim_key = "ko"
            return

        self._update_cooldowns(dt)
        self._update_hitstun(dt)
        self._update_recovery(dt)
        self._update_attack_window(dt)
        self._update_hit_flash(dt)
        self._handle_input(actions, dt)
        self._apply_physics(dt)
        self._clamp_to_screen()
        self._auto_face(opponent)
        self._update_visual_animation(dt)

    def take_damage(self, damage, knockback_dir, knockback_speed, hitstun_duration):
        """Apply damage, flash, knockback, hitstun, and KO if needed."""
        self.health = max(0, self.health - int(damage))
        self.hit_flash_timer = HIT_FLASH_DURATION
        self.hitstun_timer = max(self.hitstun_timer, hitstun_duration)

        self.vel_x = knockback_dir * knockback_speed

        if self.health <= 0:
            self.is_ko    = True
            self.action   = Action.KO
            self.vel_x    = 0
            self.vel_y    = -200
            self.hitstun_timer = 0.0
            self.recovery_timer = 0.0

        return damage

    def get_attack_hitbox(self):
        if not self.attack_active:
            return None

        reach = self.profile.light_range if self.current_attack == "light" else self.profile.heavy_range

        top_inset = 10
        rect_h = self.height - 20

        if self.current_attack == "heavy":
            top_inset += KICK_HITBOX_TOP_OFFSET
            rect_h = max(14, int(rect_h * KICK_HITBOX_HEIGHT_SCALE))

        if self.attack_low:
            top_inset += CROUCH_ATTACK_TOP_INSET
            rect_h = max(12, rect_h - CROUCH_ATTACK_TOP_INSET // 2)

        if not self.on_ground:
            rect_h = max(10, int(rect_h * AIR_ATTACK_HEIGHT_MULT))

        rect_y = int(self.y + top_inset)

        if self.facing_right:
            hx = int(self.x + self.width)
        else:
            hx = int(self.x - reach)

        return pygame.Rect(hx, rect_y, reach, rect_h)

    def get_rect(self):
        if self.action == Action.CROUCHING:
            offset = self.height - PLAYER_CROUCH_HEIGHT
            return pygame.Rect(int(self.x), int(self.y) + offset,
                               self.width, PLAYER_CROUCH_HEIGHT)
        return pygame.Rect(int(self.x), int(self.y), self.width, self.height)

    def get_center_x(self):
        return self.x + self.width / 2

    def is_flashing(self):
        return self.hit_flash_timer > 0

    def reset_for_round(self):
        self.health          = MAX_HEALTH
        self.is_ko           = False
        self.vel_x           = 0.0
        self.vel_y           = 0.0
        self.on_ground       = True
        self.action          = Action.IDLE
        self.anim_key        = "idle"
        self.walk_phase      = 0
        self.walk_anim_timer = 0.0
        self.light_cooldown  = 0.0
        self.heavy_cooldown  = 0.0
        self.attack_timer    = 0.0
        self.attack_windup   = 0.0
        self.attack_active   = False
        self.current_attack  = None
        self.hit_registered  = False
        self.recovery_timer  = 0.0
        self.attack_low      = False
        self.hitstun_timer   = 0.0
        self.hit_flash_timer  = 0.0
        self.viz_frame = 0
        self.viz_breath_phase = 0
        self.viz_walk_phase = 0
        self.viz_jump_squat = 0
        self.viz_land_squat = 0
        self.viz_prev_on_ground = True
        self.viz_ko_frame = 0
        self.viz_light_step = 0
        self.viz_heavy_mode = 0
        self.viz_heavy_phase = 0
        self.viz_heavy_recover = 0
        self._viz_prev_in_heavy_attack = False

    # =========================================================================
    # Private helpers
    # =========================================================================

    def _update_cooldowns(self, dt):
        if self.light_cooldown > 0:
            self.light_cooldown = max(0.0, self.light_cooldown - dt)
        if self.heavy_cooldown > 0:
            self.heavy_cooldown = max(0.0, self.heavy_cooldown - dt)

    def _update_hitstun(self, dt):
        if self.hitstun_timer > 0:
            self.hitstun_timer = max(0.0, self.hitstun_timer - dt)

    def _update_recovery(self, dt):
        if self.recovery_timer > 0:
            self.recovery_timer = max(0.0, self.recovery_timer - dt)

    def _update_attack_window(self, dt):
        if self.action not in (Action.LIGHT_ATTACK, Action.HEAVY_ATTACK):
            return

        self.attack_timer -= dt

        if self.attack_windup > 0:
            self.attack_windup -= dt
            if self.attack_windup <= 0:
                self.attack_windup   = 0.0
                self.attack_active   = True
                self.hit_registered  = False

        if self.attack_timer <= 0:
            self.attack_timer   = 0.0
            self.attack_active  = False
            atk = self.current_attack
            self.current_attack = None
            self.action = Action.IDLE
            self.attack_low = False
            if atk == "light":
                self.recovery_timer = max(self.recovery_timer, self.profile.light_endlag)
            elif atk == "heavy":
                self.recovery_timer = max(self.recovery_timer, self.profile.heavy_endlag)

    def _update_hit_flash(self, dt):
        if self.hit_flash_timer > 0:
            self.hit_flash_timer = max(0.0, self.hit_flash_timer - dt)

    def _handle_input(self, actions, dt):
        if self.hitstun_timer > 0:
            if actions.get("block") and self.on_ground:
                self.vel_x = 0.0
                self.action = Action.BLOCKING
            else:
                if self.on_ground:
                    self.vel_x *= 0.85
                self.action = Action.IDLE if self.on_ground else Action.JUMPING
            return

        in_attack = self.action in (Action.LIGHT_ATTACK, Action.HEAVY_ATTACK)
        recovering = self.recovery_timer > 0

        if recovering:
            self.vel_x = 0.0
            if self.on_ground and actions.get("left"):
                self.vel_x = -self.profile.move_speed * 0.35
            elif self.on_ground and actions.get("right"):
                self.vel_x = self.profile.move_speed * 0.35
            return

        if not in_attack:
            ms = self.profile.move_speed
            if actions.get("left"):
                self.vel_x = -ms
            elif actions.get("right"):
                self.vel_x = ms
            else:
                self.vel_x = 0

            if actions.get("jump") and self.on_ground:
                self.vel_y = self.profile.jump_velocity
                self.on_ground = False
                self.action = Action.JUMPING

            if actions.get("crouch") and self.on_ground:
                self.vel_x = 0.0
                self.action = Action.CROUCHING
            elif not actions.get("crouch") and self.action == Action.CROUCHING:
                self.action = Action.IDLE

            if actions.get("block") and self.on_ground:
                self.vel_x = 0.0
                self.action = Action.BLOCKING
            elif not actions.get("block") and self.action == Action.BLOCKING:
                self.action = Action.IDLE

            if actions.get("light") and self.light_cooldown <= 0:
                self._start_attack("light")
            elif actions.get("heavy") and self.heavy_cooldown <= 0:
                self._start_attack("heavy")

        if self.on_ground and self.action not in (
            Action.CROUCHING, Action.BLOCKING,
            Action.LIGHT_ATTACK, Action.HEAVY_ATTACK, Action.KO
        ):
            self.action = Action.WALKING if self.vel_x != 0 else Action.IDLE

        if not self.on_ground and self.action not in (
            Action.LIGHT_ATTACK, Action.HEAVY_ATTACK, Action.KO
        ):
            self.action = Action.JUMPING

    def _start_attack(self, attack_type):
        self.vel_x = 0.0
        self.attack_low = self.action == Action.CROUCHING
        p = self.profile

        if attack_type == "light":
            self.action = Action.LIGHT_ATTACK
            self.attack_timer = p.light_active_frames
            self.attack_windup = 0.0
            self.attack_active = True
            self.light_cooldown = p.light_cooldown
            self.current_attack = "light"
        else:
            self.action = Action.HEAVY_ATTACK
            self.attack_timer = p.heavy_windup + p.heavy_active_frames
            self.attack_windup = p.heavy_windup
            self.attack_active = False
            self.heavy_cooldown = p.heavy_cooldown
            self.current_attack = "heavy"

        self.hit_registered = False

    def _apply_physics(self, dt):
        gy = GRAVITY * self.profile.gravity_scale
        if not self.on_ground:
            self.vel_y += gy * dt

        self.x += self.vel_x * dt
        self.y += self.vel_y * dt

        floor_surface = float(FLOOR_Y - self.height)
        if self.y >= floor_surface:
            self.y = floor_surface
            self.vel_y = 0.0
            if not self.on_ground:
                self.on_ground = True
                if self.action == Action.JUMPING:
                    self.action = Action.IDLE

    def _clamp_to_screen(self):
        self.x = max(0.0, min(self.x, float(SCREEN_WIDTH - self.width)))

    def _auto_face(self, opponent):
        self.facing_right = opponent.get_center_x() > self.get_center_x()

    def _update_visual_animation(self, dt):
        # Arduino equivalent: one pass over millis(); fixed-point phase accumulators
        self.viz_frame += 1

        self.viz_breath_phase = (self.viz_breath_phase + int(dt * ANIM_BREATH_PHASE_PER_SEC)) & 255

        if self.action == Action.WALKING and self.on_ground:
            self.viz_walk_phase = (self.viz_walk_phase + int(dt * ANIM_WALK_PHASE_PER_SEC)) & 255

        if self.on_ground and not self.viz_prev_on_ground and self.vel_y >= 0:
            self.viz_land_squat = ANIM_JUMP_SQUASH_FRAMES
        if not self.on_ground and self.viz_prev_on_ground:
            self.viz_jump_squat = ANIM_JUMP_SQUASH_FRAMES
        if self.viz_jump_squat > 0:
            self.viz_jump_squat -= 1
        if self.viz_land_squat > 0:
            self.viz_land_squat -= 1
        self.viz_prev_on_ground = self.on_ground

        in_heavy = self.action == Action.HEAVY_ATTACK and self.current_attack == "heavy"
        if self._viz_prev_in_heavy_attack and not in_heavy and self.recovery_timer > 0:
            self.viz_heavy_recover = ANIM_HEAVY_RECOVER_STEPS
        self._viz_prev_in_heavy_attack = in_heavy

        if self.is_ko:
            self.viz_ko_frame = min(ANIM_KO_FRAMES, self.viz_ko_frame + 1)

        if self.action == Action.LIGHT_ATTACK and self.current_attack == "light":
            total = self.profile.light_active_frames
            if total > 0:
                u = 1.0 - (self.attack_timer / total)
                self.viz_light_step = min(
                    ANIM_LIGHT_EXTEND_STEPS + ANIM_LIGHT_RETURN_STEPS - 1,
                    int(u * (ANIM_LIGHT_EXTEND_STEPS + ANIM_LIGHT_RETURN_STEPS)),
                )
        else:
            self.viz_light_step = 0

        if in_heavy:
            W = self.profile.heavy_windup
            A = self.profile.heavy_active_frames
            if self.attack_windup > 0 and W > 0:
                self.viz_heavy_mode = 0
                self.viz_heavy_phase = int(256 * (1.0 - self.attack_windup / W)) & 255
            elif self.attack_active and A > 0:
                self.viz_heavy_mode = 1
                tw = self.attack_timer - self.attack_windup
                if tw < 0:
                    tw = self.attack_timer
                self.viz_heavy_phase = int(256 * (1.0 - min(A, max(0.0, tw)) / A)) & 255
            else:
                self.viz_heavy_mode = 0
                self.viz_heavy_phase = 0
        elif self.viz_heavy_recover > 0:
            self.viz_heavy_mode = 2
            self.viz_heavy_phase = int(256 * (self.viz_heavy_recover / ANIM_HEAVY_RECOVER_STEPS)) & 255
            self.viz_heavy_recover -= 1
        else:
            self.viz_heavy_mode = 0
            self.viz_heavy_phase = 0

        if self.is_ko:
            self.anim_key = "ko"
            return
        if self.action == Action.LIGHT_ATTACK:
            self.anim_key = "light"
            return
        if self.action == Action.HEAVY_ATTACK:
            self.anim_key = "heavy" if self.attack_windup > 0 else "kick"
            return
        if self.action == Action.BLOCKING:
            self.anim_key = "block"
            return
        if self.action == Action.CROUCHING:
            self.anim_key = "crouch"
            return
        if not self.on_ground:
            self.anim_key = "jump"
            return
        if self.action == Action.WALKING:
            self.walk_anim_timer += dt
            if self.walk_anim_timer >= WALK_ANIM_PERIOD:
                self.walk_anim_timer = 0.0
                self.walk_phase = 1 - self.walk_phase
            self.anim_key = "walk_0" if self.walk_phase == 0 else "walk_1"
            return
        self.anim_key = "idle"
