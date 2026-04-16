# =============================================================================
# main.py — Entry point. Game loop + state machine + hit detection.
#
# Run:
#   cd simulation
#   python main.py
#
# Game states
# -----------
#   MENU          Press Enter → character select.
#   CHAR_SELECT   Pick fighters, lock both, Enter → countdown.
#   COUNTDOWN     "Round X" → "3" → "2" → "1" → "FIGHT!"
#   PLAYING       Active combat.
#   ROUND_END     KO displayed for ROUND_END_DELAY seconds, then advance.
#   GAME_OVER     Match winner shown; Enter → title menu.
# =============================================================================

import random
import sys

import pygame

from assets_loader import load_fighter_sprites
from character_data import ROSTER, FighterDef
from character_select import on_keydown_char_select, reset_char_select
from combat import resolve_hit
from constants import *
from input_handler import get_p1_actions, get_p2_actions
from player import Player
import renderer

STATE_MENU         = "MENU"
STATE_CHAR_SELECT  = "CHAR_SELECT"
STATE_COUNTDOWN    = "COUNTDOWN"
STATE_PLAYING      = "PLAYING"
STATE_ROUND_END    = "ROUND_END"
STATE_GAME_OVER    = "GAME_OVER"


class CountdownManager:
    """Steps through: ROUND X → 3 → 2 → 1 → FIGHT!"""

    STEPS = [
        ("{round}",  1.0),
        ("3",        0.75),
        ("2",        0.75),
        ("1",        0.75),
        ("FIGHT!",   0.55),
    ]

    def __init__(self, round_num):
        self.round_num    = round_num
        self.step         = 0
        self.timer        = self.STEPS[0][1]
        self.done         = False
        self.current_text = self._label(0)

    def update(self, dt):
        self.timer -= dt
        if self.timer <= 0:
            self.step += 1
            if self.step >= len(self.STEPS):
                self.done = True
            else:
                self.timer        = self.STEPS[self.step][1]
                self.current_text = self._label(self.step)

    def _label(self, step):
        text, _ = self.STEPS[step]
        return text.replace("{round}", f"ROUND  {self.round_num}")


class Game:

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        renderer.init_fonts()
        renderer.set_sprite_sets({}, {})

        self._init_sounds()

        self.paused = False
        self.state  = STATE_MENU

        self.p1            = None
        self.p2            = None
        self.round_num     = 1
        self.countdown     = None
        self.round_end_timer = 0.0
        self.round_end_text  = ""

        self.hitstop_remaining = 0.0
        self.shake_magnitude   = 0.0
        self.shake_offset      = (0, 0)
        self.hit_sparks: list[dict] = []

        self.p1_idx = 0
        self.p2_idx = min(1, len(ROSTER) - 1)
        self.p1_locked = False
        self.p2_locked = False
        self._preview_cache: dict[str, pygame.Surface] = {}

    def _load_preview_cache(self):
        if self._preview_cache:
            return
        for f in ROSTER:
            s = load_fighter_sprites(f.id)
            if "idle" in s:
                surf = s["idle"]
                self._preview_cache[f.id] = pygame.transform.scale(surf, (100, 160))

    def _init_sounds(self):
        self.snd_light_hit = None
        self.snd_heavy_hit = None
        self.snd_block     = None
        self.snd_ko        = None
        self.snd_fight     = None

    def _play(self, snd):
        if snd:
            snd.play()

    def _create_players(self, f1: FighterDef, f2: FighterDef):
        self.p1 = Player(
            x=P1_START_X - PLAYER_WIDTH // 2,
            y=START_Y,
            color=f1.body_color,
            attack_color=f1.attack_color,
            profile=f1.profile,
            facing_right=True,
        )
        self.p2 = Player(
            x=P2_START_X - PLAYER_WIDTH // 2,
            y=START_Y,
            color=f2.body_color,
            attack_color=f2.attack_color,
            profile=f2.profile,
            facing_right=False,
        )

    def _begin_match_from_selection(self):
        f1 = ROSTER[self.p1_idx]
        f2 = ROSTER[self.p2_idx]
        self._create_players(f1, f2)
        self._p1_sprites = load_fighter_sprites(f1.id)
        self._p2_sprites = load_fighter_sprites(f2.id)
        renderer.set_sprite_sets(self._p1_sprites, self._p2_sprites)
        self._reset_round()
        self._enter_countdown()

    def _reset_round(self):
        if self.p1 is None or self.p2 is None:
            return
        self.p1.x = float(P1_START_X - PLAYER_WIDTH // 2)
        self.p1.y = float(START_Y)
        self.p2.x = float(P2_START_X - PLAYER_WIDTH // 2)
        self.p2.y = float(START_Y)
        self.p1.reset_for_round()
        self.p2.reset_for_round()
        self.hitstop_remaining = 0.0
        self.shake_magnitude = 0.0
        self.shake_offset = (0, 0)
        self.hit_sparks = []
        renderer.reset_hud_visual_state()

    def _return_to_menu(self):
        self.p1 = None
        self.p2 = None
        self.round_num = 1
        self.countdown = None
        self.state = STATE_MENU
        self.hit_sparks = []
        renderer.set_sprite_sets({}, {})

    def _enter_countdown(self):
        self.state     = STATE_COUNTDOWN
        self.countdown = CountdownManager(self.round_num)

    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)

            self._handle_events()
            self._update(dt)
            self._render()

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._quit()

            if event.type == pygame.KEYDOWN:
                self._on_keydown(event.key)

    def _on_keydown(self, key):
        if key == pygame.K_ESCAPE:
            if self.state == STATE_PLAYING:
                self.paused = not self.paused
            elif self.state == STATE_CHAR_SELECT:
                self.state = STATE_MENU
            else:
                self._quit()

        if key == pygame.K_RETURN:
            if self.state == STATE_MENU:
                self._load_preview_cache()
                self.p1_idx, self.p2_idx, self.p1_locked, self.p2_locked = reset_char_select()
                self.state = STATE_CHAR_SELECT
            elif self.state == STATE_GAME_OVER:
                self._return_to_menu()

        if self.state == STATE_CHAR_SELECT:
            (self.p1_idx, self.p2_idx, self.p1_locked, self.p2_locked, adv
             ) = on_keydown_char_select(
                key, self.p1_idx, self.p2_idx, self.p1_locked, self.p2_locked,
            )
            if adv:
                self._begin_match_from_selection()

    def _quit(self):
        pygame.quit()
        sys.exit()

    def _update(self, dt):
        if self.paused:
            return

        if self.p1 is not None and self.p2 is not None and renderer.particles:
            renderer.particles.update(dt)

        if self.state == STATE_MENU:
            pass

        elif self.state == STATE_CHAR_SELECT:
            pass

        elif self.state == STATE_COUNTDOWN:
            self._update_countdown(dt)

        elif self.state == STATE_PLAYING:
            self._update_hit_sparks(dt)
            self._update_playing(dt)

        elif self.state == STATE_ROUND_END:
            self._update_round_end(dt)

        elif self.state == STATE_GAME_OVER:
            pass

        if self.p1 is not None and self.p2 is not None and self.state in (
            STATE_COUNTDOWN,
            STATE_PLAYING,
            STATE_ROUND_END,
        ):
            renderer.update_visual_systems(dt, self.p1, self.p2)

        self._update_shake(dt)

    def _update_shake(self, dt):
        if self.shake_magnitude <= 0.1:
            self.shake_magnitude = 0.0
            self.shake_offset = (0, 0)
            return
        self.shake_magnitude = max(0.0, self.shake_magnitude - SHAKE_DECAY * dt)
        sm = self.shake_magnitude
        self.shake_offset = (
            random.uniform(-sm, sm),
            random.uniform(-sm, sm),
        )

    def _update_countdown(self, dt):
        self.countdown.update(dt)
        if self.countdown.done:
            self.state = STATE_PLAYING
            self._play(self.snd_fight)

    def _update_playing(self, dt):
        if self.hitstop_remaining > 0:
            self.hitstop_remaining = max(0.0, self.hitstop_remaining - dt)
            return

        keys = pygame.key.get_pressed()

        self.p1.update(dt, get_p1_actions(keys), self.p2)
        self.p2.update(dt, get_p2_actions(keys), self.p1)

        self._resolve_hit(self.p1, self.p2)
        self._resolve_hit(self.p2, self.p1)

        if self.p1.is_ko or self.p2.is_ko:
            self._handle_ko()

    def _update_round_end(self, dt):
        renderer.advance_round_end_frame()
        self.round_end_timer -= dt
        if self.round_end_timer <= 0:
            self._advance_round()

    def _update_hit_sparks(self, dt):
        alive = []
        for s in self.hit_sparks:
            s["t"] -= dt
            if s["t"] > 0:
                alive.append(s)
        self.hit_sparks = alive

    def _resolve_hit(self, attacker, defender):
        out = resolve_hit(attacker, defender)
        if out is None:
            return

        ar = attacker.get_attack_hitbox()
        dr = defender.get_rect()
        if ar:
            cx = (ar.centerx + dr.centerx) // 2
            cy = (ar.centery + dr.centery) // 2
        else:
            cx, cy = dr.centerx, dr.centery
        kind = "block" if out.blocked else (
            "heavy" if attacker.current_attack == "heavy" else "light"
        )
        self.hit_sparks.append(
            {"x": cx, "y": cy, "t": HIT_SPARK_DURATION, "kind": kind}
        )

        if renderer.particles:
            renderer.particles.spawn_hit_burst(cx, cy, kind)

        self.hitstop_remaining = max(self.hitstop_remaining, out.hitstop)
        if not out.blocked and attacker.current_attack == "heavy":
            renderer.trigger_shake(ANIM_SHAKE_HEAVY_INTENSITY, ANIM_SHAKE_HEAVY_FRAMES)
        elif not out.blocked:
            self.shake_magnitude = min(SHAKE_PER_HIT * 3.0, self.shake_magnitude + SHAKE_PER_HIT)

        if out.blocked:
            self._play(self.snd_block)
        else:
            snd = self.snd_heavy_hit if attacker.current_attack == "heavy" else self.snd_light_hit
            self._play(snd)

    def _handle_ko(self):
        both_ko = self.p1.is_ko and self.p2.is_ko

        if both_ko:
            self.round_end_text = "DRAW"
        elif self.p2.is_ko:
            self.p1.round_wins += 1
            self.round_end_text = "PLAYER 1 WINS!"
        else:
            self.p2.round_wins += 1
            self.round_end_text = "PLAYER 2 WINS!"

        self._play(self.snd_ko)
        self.state           = STATE_ROUND_END
        self.round_end_timer = ROUND_END_DELAY
        renderer.reset_round_end_animation()

    def _advance_round(self):
        if (self.p1.round_wins >= ROUNDS_TO_WIN
                or self.p2.round_wins >= ROUNDS_TO_WIN):
            self.state = STATE_GAME_OVER
        else:
            self.round_num += 1
            self._reset_round()
            self._enter_countdown()

    def _shake_xy(self):
        return (int(self.shake_offset[0]), int(self.shake_offset[1]))

    def _render_offset(self):
        base = self._shake_xy() if self.state == STATE_PLAYING else (0, 0)
        vx, vy = renderer.get_visual_shake_offset()
        return renderer.combine_offset(base, (vx, vy))

    def _render(self):
        shake = self._render_offset()
        hs = self.hitstop_remaining > 0 and self.state == STATE_PLAYING

        if self.state == STATE_MENU:
            renderer.draw_menu(self.screen)

        elif self.state == STATE_CHAR_SELECT:
            renderer.draw_character_select(
                self.screen, ROSTER,
                self.p1_idx, self.p2_idx, self.p1_locked, self.p2_locked,
                self._preview_cache,
            )

        elif self.state == STATE_COUNTDOWN:
            renderer.draw_background(self.screen, shake, self.p1, self.p2)
            renderer.draw_player(self.screen, self.p1, self._p1_sprites, True, shake)
            renderer.draw_player(self.screen, self.p2, self._p2_sprites, False, shake)
            if renderer.particles:
                renderer.particles.draw(self.screen, shake)
            renderer.draw_hud(self.screen, self.p1, self.p2,
                              self.round_num, self.p1.round_wins, self.p2.round_wins, False)
            renderer.draw_countdown(self.screen, self.countdown.current_text)

        elif self.state == STATE_PLAYING:
            renderer.draw_background(self.screen, shake, self.p1, self.p2)
            renderer.draw_player(self.screen, self.p1, self._p1_sprites, True, shake)
            renderer.draw_player(self.screen, self.p2, self._p2_sprites, False, shake)
            renderer.draw_hit_sparks(self.screen, self.hit_sparks, shake)
            if renderer.particles:
                renderer.particles.draw(self.screen, shake)
            renderer.draw_hud(self.screen, self.p1, self.p2,
                              self.round_num, self.p1.round_wins, self.p2.round_wins, hs)
            renderer.draw_cooldown_bars(self.screen, self.p1, self.p2, shake)
            renderer.draw_action_label(self.screen, self.p1, self.p2, shake)

            if self.paused:
                renderer.draw_paused(self.screen)

        elif self.state == STATE_ROUND_END:
            renderer.draw_background(self.screen, shake, self.p1, self.p2)
            renderer.draw_player(self.screen, self.p1, self._p1_sprites, True, shake)
            renderer.draw_player(self.screen, self.p2, self._p2_sprites, False, shake)
            if renderer.particles:
                renderer.particles.draw(self.screen, shake)
            renderer.draw_hud(self.screen, self.p1, self.p2,
                              self.round_num, self.p1.round_wins, self.p2.round_wins, False)
            renderer.draw_round_end(self.screen, self.round_end_text)

        elif self.state == STATE_GAME_OVER:
            if self.p1.round_wins >= ROUNDS_TO_WIN:
                winner = "PLAYER 1  WINS THE MATCH!"
            elif self.p2.round_wins >= ROUNDS_TO_WIN:
                winner = "PLAYER 2  WINS THE MATCH!"
            else:
                winner = "IT'S A DRAW!"
            renderer.draw_game_over(self.screen, winner)

        pygame.display.flip()


if __name__ == "__main__":
    game = Game()
    game.run()
