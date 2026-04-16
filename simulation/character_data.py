# =============================================================================
# character_data.py — Per-fighter stats and roster (maps to tables on Arduino).
# =============================================================================

from dataclasses import dataclass

from constants import (
    HEAVY_ACTIVE_FRAMES,
    HEAVY_COOLDOWN,
    HEAVY_DAMAGE,
    HEAVY_RANGE,
    HEAVY_WINDUP,
    JUMP_VELOCITY,
    KNOCKBACK_SPEED,
    LIGHT_ACTIVE_FRAMES,
    LIGHT_COOLDOWN,
    LIGHT_DAMAGE,
    LIGHT_RANGE,
    MOVE_SPEED,
)


@dataclass(frozen=True)
class CharacterProfile:
    """Tunable combat parameters per fighter."""

    move_speed: float = MOVE_SPEED
    jump_velocity: float = JUMP_VELOCITY
    gravity_scale: float = 1.0

    light_damage: int = LIGHT_DAMAGE
    heavy_damage: int = HEAVY_DAMAGE
    light_range: int = LIGHT_RANGE
    heavy_range: int = HEAVY_RANGE

    light_cooldown: float = LIGHT_COOLDOWN
    heavy_cooldown: float = HEAVY_COOLDOWN
    light_active_frames: float = LIGHT_ACTIVE_FRAMES
    heavy_windup: float = HEAVY_WINDUP
    heavy_active_frames: float = HEAVY_ACTIVE_FRAMES

    light_endlag: float = 0.06
    heavy_endlag: float = 0.14

    knockback_light: float = KNOCKBACK_SPEED * 0.9
    knockback_heavy: float = KNOCKBACK_SPEED * 1.25
    knockback_received_mult: float = 1.0


@dataclass(frozen=True)
class FighterDef:
    """One selectable fighter: folder id, display name, stats, fallback colors."""

    id: str
    display_name: str
    profile: CharacterProfile
    body_color: tuple[int, int, int]
    attack_color: tuple[int, int, int]


# --- Legacy profile aliases (tests / imports) -----------------------------------
PROFILE_P1 = CharacterProfile(
    move_speed=255.0,
    jump_velocity=-640.0,
    gravity_scale=1.0,
    light_damage=7,
    heavy_damage=19,
    light_range=70,
    heavy_range=88,
    light_cooldown=0.36,
    heavy_cooldown=0.98,
    knockback_light=175.0,
    knockback_heavy=210.0,
    knockback_received_mult=1.05,
)

PROFILE_P2 = CharacterProfile(
    move_speed=200.0,
    jump_velocity=-580.0,
    gravity_scale=1.08,
    light_damage=9,
    heavy_damage=24,
    light_range=78,
    heavy_range=102,
    light_cooldown=0.44,
    heavy_cooldown=1.12,
    knockback_light=200.0,
    knockback_heavy=245.0,
    knockback_received_mult=0.95,
)


ROSTER: tuple[FighterDef, ...] = (
    FighterDef(
        id="greb",
        display_name="Greb",
        profile=CharacterProfile(
            move_speed=255.0,
            jump_velocity=-650.0,
            gravity_scale=0.98,
            light_damage=7,
            heavy_damage=18,
            light_range=70,
            heavy_range=86,
            light_cooldown=0.36,
            heavy_cooldown=0.95,
            knockback_light=172.0,
            knockback_heavy=208.0,
            knockback_received_mult=1.05,
        ),
        body_color=(55, 115, 85),
        attack_color=(130, 200, 150),
    ),
    FighterDef(
        id="splint",
        display_name="Splint",
        profile=CharacterProfile(
            move_speed=215.0,
            jump_velocity=-600.0,
            gravity_scale=1.05,
            light_damage=8,
            heavy_damage=21,
            light_range=74,
            heavy_range=94,
            light_cooldown=0.40,
            heavy_cooldown=1.02,
            knockback_light=185.0,
            knockback_heavy=228.0,
            knockback_received_mult=1.0,
        ),
        body_color=(230, 195, 75),
        attack_color=(255, 235, 170),
    ),
    FighterDef(
        id="citron",
        display_name="Citron",
        profile=CharacterProfile(
            move_speed=225.0,
            jump_velocity=-615.0,
            gravity_scale=1.02,
            light_damage=8,
            heavy_damage=22,
            light_range=76,
            heavy_range=98,
            light_cooldown=0.42,
            heavy_cooldown=1.08,
            knockback_light=192.0,
            knockback_heavy=235.0,
            knockback_received_mult=0.98,
        ),
        body_color=(240, 150, 55),
        attack_color=(255, 210, 130),
    ),
    FighterDef(
        id="brick",
        display_name="Brick",
        profile=CharacterProfile(
            move_speed=198.0,
            jump_velocity=-575.0,
            gravity_scale=1.10,
            light_damage=10,
            heavy_damage=25,
            light_range=80,
            heavy_range=104,
            light_cooldown=0.46,
            heavy_cooldown=1.14,
            knockback_light=205.0,
            knockback_heavy=248.0,
            knockback_received_mult=0.93,
        ),
        body_color=(175, 55, 65),
        attack_color=(255, 150, 140),
    ),
)


def get_fighter_by_id(fid: str) -> FighterDef | None:
    for f in ROSTER:
        if f.id == fid:
            return f
    return None


def roster_index_for_id(fid: str) -> int:
    for i, f in enumerate(ROSTER):
        if f.id == fid:
            return i
    return 0
