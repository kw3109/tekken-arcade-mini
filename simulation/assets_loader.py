# =============================================================================
# assets_loader.py — Load fighter PNGs into pygame Surfaces (optional graphics).
# =============================================================================

import os

import pygame

from constants import ASSETS_FIGHTERS, PLAYER_HEIGHT, PLAYER_WIDTH

SPRITE_NAMES = (
    "idle",
    "walk_0",
    "walk_1",
    "jump",
    "crouch",
    "block",
    "light",
    "heavy",
    "kick",
    "ko",
)


def _scale(surf: pygame.Surface) -> pygame.Surface:
    if surf.get_width() == PLAYER_WIDTH and surf.get_height() == PLAYER_HEIGHT:
        return surf
    return pygame.transform.scale(surf, (PLAYER_WIDTH, PLAYER_HEIGHT))


def load_fighter_sprites(fighter_id: str) -> dict[str, pygame.Surface]:
    """
    Load assets/fighters/<fighter_id>/*.png into a dict.
    Missing files are omitted (renderer falls back to rectangles).
    """
    folder = os.path.join(ASSETS_FIGHTERS, fighter_id)
    out: dict[str, pygame.Surface] = {}
    if not os.path.isdir(folder):
        return out

    for name in SPRITE_NAMES:
        path = os.path.join(folder, f"{name}.png")
        if os.path.isfile(path):
            try:
                surf = pygame.image.load(path).convert_alpha()
                out[name] = _scale(surf)
            except pygame.error:
                pass
    return out
