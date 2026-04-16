# =============================================================================
# character_select.py — Helpers for roster navigation (keyboard).
# =============================================================================

import pygame

from character_data import ROSTER


def roster_len() -> int:
    return len(ROSTER)


def on_keydown_char_select(
    key: int,
    p1_idx: int,
    p2_idx: int,
    p1_locked: bool,
    p2_locked: bool,
) -> tuple[int, int, bool, bool, bool]:
    """
    Handle one key in character select.
    Returns (p1_idx, p2_idx, p1_locked, p2_locked, should_advance).
    should_advance True when both locked and user pressed Enter to start.
    """
    n = len(ROSTER)
    advance = False
    if key == pygame.K_a:
        if not p1_locked:
            p1_idx = (p1_idx - 1) % n
    elif key == pygame.K_d:
        if not p1_locked:
            p1_idx = (p1_idx + 1) % n
    elif key in (pygame.K_j, pygame.K_SPACE):
        p1_locked = not p1_locked
    elif key == pygame.K_LEFT:
        if not p2_locked:
            p2_idx = (p2_idx - 1) % n
    elif key == pygame.K_RIGHT:
        if not p2_locked:
            p2_idx = (p2_idx + 1) % n
    elif key == pygame.K_COMMA:
        p2_locked = not p2_locked
    elif key == pygame.K_RETURN:
        if p1_locked and p2_locked:
            advance = True

    return (p1_idx, p2_idx, p1_locked, p2_locked, advance)


def reset_char_select() -> tuple[int, int, bool, bool]:
    """Default indices and unlocked."""
    return 0, min(1, len(ROSTER) - 1), False, False
