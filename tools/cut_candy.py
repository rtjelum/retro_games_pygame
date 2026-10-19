"""Cuts the Candy Swap sprites out of a sheet of candies on a white background.

Usage: python tools/cut_candy.py assets/candy/candy.png assets/candy

The sheet holds seven candies. The six coloured ones become candy_0..5 and the
chocolate one with sprinkles becomes the colour bomb.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

S = 124          # sprite size, one Retina cell
FILL = 112       # longest side of the candy inside the sprite
WIDE = 122       # wide candies may stretch further across
LOOSE = 34       # colour distance from white that still counts as background: keeps white stripes
STRICT = 110     # stricter version: finds the coloured body of a candy without its shadow
GROW = 3         # how far the candy may reach past its coloured body
TRIM = 2         # pixels shaved off the outline to drop the white fringe

# Roughly where each candy sits on the sheet, used to tell them apart, and how
# wide a gap in its coloured body gets filled in (the striped ones have wide white stripes).
NAMES = {
    "candy_0_red.png": ((220, 190), 16),
    "candy_1_orange.png": ((560, 150), 6),
    "candy_2_yellow.png": ((850, 170), 6),
    "candy_3_green.png": ((360, 375), 6),
    "candy_4_blue.png": ((195, 600), 24),
    "candy_5_purple.png": ((515, 610), 6),
    "color_bomb.png": ((845, 590), 6),
}


def offsets(amount):
    return [(dx, dy) for dx in range(-amount, amount + 1) for dy in range(-amount, amount + 1)
            if dx * dx + dy * dy <= amount * amount]


def shrink(mask, amount):
    """The mask with `amount` pixels taken off every edge."""
    inner = mask.copy()
    for d in offsets(amount):
        shifted = pygame.mask.Mask(mask.get_size())
        shifted.draw(mask, d)
        inner = inner.overlap_mask(shifted, (0, 0))
    return inner


def grow(mask, amount):
    """The mask with `amount` pixels added to every edge."""
    outer = mask.copy()
    for d in offsets(amount):
        outer.draw(mask, d)
    return outer


def fill_holes(mask):
    """The mask with every hole inside it filled in."""
    outside = mask.copy()
    outside.invert()
    filled = outside.connected_component((0, 0))
    filled.invert()
    return filled


def candy_mask(sheet, light):
    """Everything that isn't background: the light area touching the sheet's corner.
    Light areas inside a candy, like white stripes, stay part of it."""
    near_white = pygame.mask.from_threshold(sheet, (255, 255, 255, 255), (light, light, light, 255))
    candy = near_white.connected_component((0, 0))
    candy.invert()
    return candy


def soften(mask, size):
    """An alpha layer from the mask with a slightly blurred edge."""
    layer = mask.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(255, 255, 255, 0))
    w, h = size
    small = pygame.transform.smoothscale(layer, (w // 2, h // 2))
    return pygame.transform.smoothscale(small, (w, h))


def cut(sheet, part):
    """One candy as a square sprite with a clear background."""
    part = part.connected_component()
    rect = part.get_bounding_rects()[0]
    shape = shrink(part, TRIM)
    picture = pygame.Surface(sheet.get_size(), pygame.SRCALPHA)
    picture.blit(sheet, (0, 0))
    picture.blit(soften(shape, sheet.get_size()), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    picture = picture.subsurface(rect).copy()
    k = min(WIDE / rect.w, FILL / rect.h)
    picture = pygame.transform.smoothscale(picture, (round(rect.w * k), round(rect.h * k)))
    out = pygame.Surface((S, S), pygame.SRCALPHA)
    out.blit(picture, picture.get_rect(center=(S / 2, S / 2)))
    return out


def main():
    sheet = pygame.image.load(sys.argv[1])
    out_dir = Path(sys.argv[2])
    loose = candy_mask(sheet, LOOSE)    # whole candies, but with their soft shadows
    strict = candy_mask(sheet, STRICT)  # just the coloured bodies
    parts = sorted(loose.connected_components(500), key=lambda m: m.count(), reverse=True)[:len(NAMES)]
    for name, ((x, y), gap) in NAMES.items():
        part = min(parts, key=lambda m: (m.centroid()[0] - x) ** 2 + (m.centroid()[1] - y) ** 2)
        body = grow(shrink(grow(strict.overlap_mask(part, (0, 0)), gap), gap), GROW)
        pygame.image.save(cut(sheet, fill_holes(part.overlap_mask(body, (0, 0)))), str(out_dir / name))
        print("saved", out_dir / name)


main()
