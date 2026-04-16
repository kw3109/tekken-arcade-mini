# =============================================================================
# combat.py — Hit overlap tests and hit resolution (damage, stun, knockback).
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass
import pygame

from constants import (
    BLOCK_DAMAGE_MULT,
    BLOCK_KNOCKBACK_MULT,
    COUNTER_DAMAGE_MULT,
    COUNTER_KNOCKBACK_MULT,
    HITSTOP_HEAVY,
    HITSTOP_LIGHT,
    HITSTUN_HEAVY,
    HITSTUN_LIGHT,
)
from player import Action, Player


@dataclass
class HitOutcome:
    """Returned to the game loop for sound, hitstop, and screen shake."""

    blocked: bool
    hitstop: float
    was_counter: bool


def _defender_in_attack(p: Player) -> bool:
    return p.action in (Action.LIGHT_ATTACK, Action.HEAVY_ATTACK)


def check_hit_overlap(attacker: Player, defender: Player) -> bool:
    """True if attack hitbox overlaps defender hurtbox this frame (no side effects)."""
    if not attacker.attack_active:
        return False
    if attacker.hit_registered:
        return False
    atk_rect = attacker.get_attack_hitbox()
    if atk_rect is None:
        return False
    return atk_rect.colliderect(defender.get_rect())


def resolve_hit(attacker: Player, defender: Player) -> HitOutcome | None:
    """
    If a new hit connects, apply damage and defender state. Returns outcome or None.
    """
    if not check_hit_overlap(attacker, defender):
        return None

    is_heavy = attacker.current_attack == "heavy"
    raw_damage = attacker.profile.heavy_damage if is_heavy else attacker.profile.light_damage

    blocked = defender.action == Action.BLOCKING
    counter = _defender_in_attack(defender) and not blocked

    if blocked:
        damage = int(raw_damage * BLOCK_DAMAGE_MULT)
    elif counter:
        damage = int(raw_damage * COUNTER_DAMAGE_MULT)
    else:
        damage = raw_damage

    k_dir = 1 if attacker.facing_right else -1
    base_kb = attacker.profile.knockback_heavy if is_heavy else attacker.profile.knockback_light
    if blocked:
        kb = base_kb * BLOCK_KNOCKBACK_MULT
    elif counter:
        kb = base_kb * COUNTER_KNOCKBACK_MULT
    else:
        kb = base_kb
    kb *= defender.profile.knockback_received_mult

    stun = HITSTUN_HEAVY if is_heavy else HITSTUN_LIGHT
    if blocked:
        stun *= 0.45

    hitstop = HITSTOP_HEAVY if is_heavy else HITSTOP_LIGHT
    if blocked:
        hitstop *= 0.65

    defender.take_damage(damage, k_dir, kb, stun)

    attacker.hit_registered = True

    return HitOutcome(blocked=blocked, hitstop=hitstop, was_counter=counter)
