# =============================================================================
# tests/test_combat.py — Combat resolution without a display window.
# =============================================================================

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from character_data import PROFILE_P1, PROFILE_P2
from combat import check_hit_overlap, resolve_hit
from constants import MAX_HEALTH, START_Y
from player import Action, Player


def _make_pair():
    """Place fighters close enough that P1's light hitbox reaches P2."""
    y = float(START_Y)
    p1 = Player(
        400.0,
        y,
        (50, 50, 200),
        (100, 100, 255),
        PROFILE_P1,
        facing_right=True,
    )
    p2 = Player(
        500.0,
        y,
        (200, 50, 50),
        (255, 100, 100),
        PROFILE_P2,
        facing_right=False,
    )
    return p1, p2


def test_no_overlap_returns_none():
    p1, p2 = _make_pair()
    p1.x = 10
    p2.x = 800
    p1.attack_active = True
    p1.current_attack = "light"
    p1.hit_registered = False
    assert resolve_hit(p1, p2) is None


def test_light_hit_applies_damage():
    p1, p2 = _make_pair()
    p1.attack_active = True
    p1.current_attack = "light"
    p1.hit_registered = False
    p2.action = Action.IDLE

    assert check_hit_overlap(p1, p2) is True
    before = p2.health
    out = resolve_hit(p1, p2)
    assert out is not None
    assert out.blocked is False
    assert p2.health < before
    assert p1.hit_registered is True


def test_block_reduces_damage():
    p1, p2 = _make_pair()
    p1.attack_active = True
    p1.current_attack = "light"
    p1.hit_registered = False
    p2.action = Action.BLOCKING

    out = resolve_hit(p1, p2)
    assert out is not None
    assert out.blocked is True
    assert p2.health == MAX_HEALTH - int(PROFILE_P1.light_damage * 0.20)


def test_kick_hitbox_lower_than_light():
    """Heavy uses kick hitbox tuning — rect sits lower than light punch."""
    p1, p2 = _make_pair()
    p1.attack_active = True
    p1.current_attack = "light"
    p1.hit_registered = False
    r_light = p1.get_attack_hitbox()
    p1.current_attack = "heavy"
    r_kick = p1.get_attack_hitbox()
    assert r_light is not None and r_kick is not None
    assert r_kick.y > r_light.y


def test_counter_increases_damage():
    p1, p2 = _make_pair()
    p1.attack_active = True
    p1.current_attack = "heavy"
    p1.hit_registered = False
    p2.action = Action.LIGHT_ATTACK

    expected = int(PROFILE_P1.heavy_damage * 1.25)
    resolve_hit(p1, p2)
    assert p2.health == MAX_HEALTH - expected
