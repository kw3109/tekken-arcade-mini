#!/usr/bin/env python3
"""
Humanoid fighters with dynamic attack poses: motion lines, chamber vs strike kicks.
Run: python3 assets/generate_placeholder_sprites.py
"""

import math
import os
import sys

try:
    import pygame
except ImportError:
    print("pygame required: pip install pygame", file=sys.stderr)
    sys.exit(1)

W, H = 50, 80
OUTLINE = (28, 28, 34)
SKIN = (235, 195, 170)

# VFX streak colors (Tekken-like contrast)
STREAK_HOT = (255, 210, 230)
STREAK_CORE = (255, 255, 255)
STREAK_CYAN = (160, 235, 255)
STREAK_PINK = (255, 100, 170)

FRAMES = (
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

FIGHTERS = (
    ("greb", (55, 115, 85), (40, 65, 50), (25, 25, 30), (130, 210, 155)),
    ("splint", (230, 195, 75), (55, 50, 45), (30, 28, 32), (255, 240, 180)),
    ("citron", (240, 150, 55), (45, 42, 52), (28, 26, 30), (255, 225, 140)),
    ("brick", (175, 55, 65), (42, 38, 48), (25, 22, 28), (255, 165, 155)),
)


def _limb(surf, rect, fill, o=1):
    pygame.draw.rect(surf, fill, rect)
    pygame.draw.rect(surf, OUTLINE, rect, o)


def _head(surf, cx, cy, r=9):
    pygame.draw.circle(surf, SKIN, (cx, cy), r)
    pygame.draw.circle(surf, OUTLINE, (cx, cy), r, 2)
    pygame.draw.circle(surf, (40, 40, 45), (cx + 3, cy - 1), 2)


def _line_vfx(surf, start, end, color, width=2):
    pygame.draw.line(surf, color, start, end, width)


def _burst_from_fist(surf, fx, fy):
    """Sharp speed lines from punch impact zone."""
    for i in range(7):
        ang = -0.5 + i * 0.22
        dx = int(14 * math.cos(ang))
        dy = int(14 * math.sin(ang))
        c = STREAK_PINK if i % 2 == 0 else STREAK_CORE
        _line_vfx(surf, (fx, fy), (fx + dx, fy + dy), c, 2 if i % 2 == 0 else 1)


def _burst_from_foot(surf, fx, fy):
    for i in range(10):
        ang = -1.0 + i * 0.22
        L = 18 + (i % 3) * 4
        dx = int(L * math.cos(ang))
        dy = int(L * math.sin(ang))
        c = STREAK_CYAN if i % 3 == 0 else (STREAK_HOT if i % 2 == 0 else STREAK_PINK)
        _line_vfx(surf, (fx, fy), (fx + dx, fy + dy), c, 2)


def draw_fighter(surf, shirt, pants, shoes, accent, pose):
    surf.fill((0, 0, 0, 0))

    if pose == "ko":
        pygame.draw.ellipse(surf, shirt, pygame.Rect(6, 52, 38, 22))
        pygame.draw.ellipse(surf, OUTLINE, pygame.Rect(6, 52, 38, 22), 2)
        _head(surf, 28, 44, 8)
        return

    if pose == "crouch":
        torso = pygame.Rect(13, 36, 24, 26)
        hy = 34
    else:
        torso = pygame.Rect(13, 26, 24, 22)
        hy = 15

    # --- Heavy = windup chamber (knee up, coiling) ---------------------------
    if pose == "heavy":
        _limb(surf, pygame.Rect(14, 30, 22, 20), shirt)
        _head(surf, 26, 14)
        _limb(surf, pygame.Rect(6, 28, 6, 14), shirt)
        _limb(surf, pygame.Rect(36, 26, 6, 12), shirt)
        _limb(surf, pygame.Rect(18, 48, 8, 14), pants)
        _limb(surf, pygame.Rect(28, 52, 6, 12), pants)
        _limb(surf, pygame.Rect(16, 62, 10, 6), shoes)
        _limb(surf, pygame.Rect(26, 64, 9, 6), shoes)
        pygame.draw.circle(surf, SKIN, (9, 42), 3)
        pygame.draw.circle(surf, SKIN, (39, 38), 3)
        _line_vfx(surf, (22, 40), (18, 34), STREAK_CYAN, 2)
        _line_vfx(surf, (30, 38), (34, 32), STREAK_CYAN, 2)
        return

    # --- Kick = full extension strike ----------------------------------------
    if pose == "kick":
        _limb(surf, pygame.Rect(12, 28, 22, 18), shirt)
        _head(surf, 24, 13)
        _limb(surf, pygame.Rect(5, 30, 7, 16), shirt)
        _limb(surf, pygame.Rect(30, 48, 20, 8), pants)
        _limb(surf, pygame.Rect(44, 50, 10, 7), shoes)
        _limb(surf, pygame.Rect(17, 54, 6, 16), pants)
        _limb(surf, pygame.Rect(14, 70, 9, 5), shoes)
        pygame.draw.circle(surf, SKIN, (8, 46), 3)
        _burst_from_foot(surf, 48, 54)
        _line_vfx(surf, (35, 52), (48, 50), STREAK_PINK, 3)
        _line_vfx(surf, (36, 54), (50, 52), STREAK_CORE, 2)
        return

    # --- Light = lunge jab + fist burst ---------------------------------------
    if pose == "light":
        _limb(surf, pygame.Rect(11, 27, 22, 20), shirt)
        _head(surf, 22, 13)
        _limb(surf, pygame.Rect(5, 32, 6, 14), shirt)
        _limb(surf, pygame.Rect(15, 54, 7, 14), pants)
        _limb(surf, pygame.Rect(28, 56, 7, 14), pants)
        _limb(surf, pygame.Rect(14, 68, 9, 5), shoes)
        _limb(surf, pygame.Rect(27, 68, 9, 5), shoes)
        _limb(surf, pygame.Rect(34, 28, 10, 9), accent)
        pygame.draw.rect(surf, OUTLINE, pygame.Rect(34, 28, 10, 9), 2)
        _limb(surf, pygame.Rect(38, 24, 14, 8), accent)
        pygame.draw.rect(surf, OUTLINE, pygame.Rect(38, 24, 14, 8), 2)
        pygame.draw.circle(surf, SKIN, (8, 46), 3)
        _burst_from_fist(surf, 48, 28)
        return

    if pose == "block":
        _limb(surf, pygame.Rect(12, 28, 22, 22), shirt)
        _head(surf, 25, 14)
        _limb(surf, pygame.Rect(15, 56, 7, 14), pants)
        _limb(surf, pygame.Rect(28, 56, 7, 14), pants)
        _limb(surf, pygame.Rect(14, 70, 9, 5), shoes)
        _limb(surf, pygame.Rect(27, 70, 9, 5), shoes)
        _limb(surf, pygame.Rect(10, 20, 8, 12), shirt)
        _limb(surf, pygame.Rect(32, 20, 8, 12), shirt)
        _limb(surf, pygame.Rect(14, 16, 22, 10), accent)
        pygame.draw.rect(surf, OUTLINE, pygame.Rect(14, 16, 22, 10), 2)
        _line_vfx(surf, (18, 18), (14, 14), STREAK_CYAN, 2)
        _line_vfx(surf, (32, 18), (36, 14), STREAK_CYAN, 2)
        pygame.draw.circle(surf, SKIN, (12, 32), 3)
        pygame.draw.circle(surf, SKIN, (38, 32), 3)
        return

    _limb(surf, torso, shirt)
    _head(surf, 25, hy)

    def legs_standing():
        _limb(surf, pygame.Rect(15, 56, 7, 14), pants)
        _limb(surf, pygame.Rect(28, 56, 7, 14), pants)
        _limb(surf, pygame.Rect(14, 70, 9, 5), shoes)
        _limb(surf, pygame.Rect(27, 70, 9, 5), shoes)

    if pose == "walk_0":
        _limb(surf, pygame.Rect(14, 56, 7, 14), pants)
        _limb(surf, pygame.Rect(13, 70, 9, 5), shoes)
        _limb(surf, pygame.Rect(29, 58, 7, 12), pants)
        _limb(surf, pygame.Rect(28, 70, 9, 5), shoes)
    elif pose == "walk_1":
        _limb(surf, pygame.Rect(14, 58, 7, 12), pants)
        _limb(surf, pygame.Rect(13, 70, 9, 5), shoes)
        _limb(surf, pygame.Rect(29, 56, 7, 14), pants)
        _limb(surf, pygame.Rect(28, 70, 9, 5), shoes)
    elif pose == "jump":
        _limb(surf, pygame.Rect(12, 50, 6, 12), pants)
        _limb(surf, pygame.Rect(30, 52, 6, 12), pants)
        _limb(surf, pygame.Rect(10, 62, 8, 5), shoes)
        _limb(surf, pygame.Rect(30, 62, 8, 5), shoes)
    elif pose == "crouch":
        _limb(surf, pygame.Rect(13, 60, 8, 10), pants)
        _limb(surf, pygame.Rect(27, 60, 8, 10), pants)
        _limb(surf, pygame.Rect(12, 70, 9, 5), shoes)
        _limb(surf, pygame.Rect(27, 70, 9, 5), shoes)
    else:
        legs_standing()

    if pose == "idle":
        _limb(surf, pygame.Rect(6, 28, 6, 18), shirt)
        _limb(surf, pygame.Rect(38, 28, 6, 18), shirt)
        pygame.draw.circle(surf, SKIN, (9, 46), 3)
        pygame.draw.circle(surf, SKIN, (41, 46), 3)
    elif pose == "walk_0":
        _limb(surf, pygame.Rect(4, 30, 6, 14), shirt)
        _limb(surf, pygame.Rect(40, 28, 6, 18), shirt)
        pygame.draw.circle(surf, SKIN, (7, 44), 3)
        pygame.draw.circle(surf, SKIN, (43, 46), 3)
    elif pose == "walk_1":
        _limb(surf, pygame.Rect(6, 28, 6, 18), shirt)
        _limb(surf, pygame.Rect(42, 30, 6, 14), shirt)
        pygame.draw.circle(surf, SKIN, (9, 46), 3)
        pygame.draw.circle(surf, SKIN, (45, 44), 3)
    elif pose == "jump":
        _limb(surf, pygame.Rect(4, 22, 6, 12), shirt)
        _limb(surf, pygame.Rect(40, 22, 6, 12), shirt)
        pygame.draw.circle(surf, SKIN, (7, 34), 3)
        pygame.draw.circle(surf, SKIN, (43, 34), 3)
    elif pose == "crouch":
        _limb(surf, pygame.Rect(5, 40, 6, 14), shirt)
        _limb(surf, pygame.Rect(39, 40, 6, 14), shirt)
        pygame.draw.circle(surf, SKIN, (8, 54), 3)
        pygame.draw.circle(surf, SKIN, (42, 54), 3)


def main():
    pygame.init()
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    for pid, shirt, pants, shoes, accent in FIGHTERS:
        out_dir = os.path.join(root, "assets", "fighters", pid)
        os.makedirs(out_dir, exist_ok=True)
        for name in FRAMES:
            surf = pygame.Surface((W, H), pygame.SRCALPHA)
            draw_fighter(surf, shirt, pants, shoes, accent, name)
            path = os.path.join(out_dir, f"{name}.png")
            pygame.image.save(surf, path)
            print("wrote", path)
    pygame.quit()


if __name__ == "__main__":
    main()
