"""Draws the Candy Swap candies at 124 px (one Retina cell), supersampled 4x.

Usage: python tools/make_candy.py assets/candy
"""
import math
import os
import random
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

S = 124          # final size
K = 4            # supersampling
N = S * K
OUT = Path(sys.argv[1])
EDGE = (12, 12, 24)
WHITE = (255, 255, 255)
CLEAR = (0, 0, 0, 0)


def p(*v):
    return [x * K for x in v]


def mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def surf(rgb=(0, 0, 0)):
    """A clear layer. Its hidden colour is rgb, so blurring it doesn't leave grey fringes."""
    layer = pygame.Surface((N, N), pygame.SRCALPHA)
    layer.fill((*rgb, 0))
    return layer


def blur(s, amount):
    w, h = s.get_size()
    small = pygame.transform.smoothscale(s, (max(1, w // amount), max(1, h // amount)))
    return pygame.transform.smoothscale(small, (w, h))


def mask_of(shape):
    return pygame.mask.from_surface(shape, 1)


def paint(mask, colour):
    return mask.to_surface(setcolor=colour, unsetcolor=(*colour[:3], 0))


def clip(layer, shape):
    """Keep only the part of layer that lies inside shape."""
    keep = mask_of(shape).to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(255, 255, 255, 0))
    out = layer.copy()
    out.blit(keep, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return out


def dilate(mask, r):
    disk = pygame.mask.Mask((2 * r + 1, 2 * r + 1))
    for y in range(2 * r + 1):
        for x in range(2 * r + 1):
            if (x - r) ** 2 + (y - r) ** 2 <= r * r:
                disk.set_at((x, y))
    out = pygame.mask.Mask((N, N))
    out.draw(mask.convolve(disk), (-r, -r))
    return out


def erode(mask, r):
    outside = mask.copy()
    outside.invert()
    inner = dilate(outside, r)
    inner.invert()
    return inner


def radial(colour_in, colour_out, centre, reach, power=1.0):
    """An opaque radial gradient from centre outwards."""
    layer = surf()
    layer.fill((*colour_out, 255))
    for i in range(90, -1, -1):
        t = i / 90
        pygame.draw.circle(layer, mix(colour_in, colour_out, t ** power), p(*centre), max(1, reach * K * t))
    return layer


def rotated(layer, angle):
    turned = pygame.transform.rotate(layer, angle)
    out = surf()
    out.blit(turned, turned.get_rect(center=(N // 2, N // 2)))
    return out


def gloss(layer, rect, alpha=220, angle=0):
    """A glossy reflection: bright at the top, fading out towards the bottom."""
    w, h = round(rect[2] * K), round(rect[3] * K)
    spot = pygame.Surface((w, h), pygame.SRCALPHA)
    spot.fill((255, 255, 255, 0))
    pygame.draw.ellipse(spot, (255, 255, 255, 255), spot.get_rect())
    fade = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        a = round(alpha * (1 - 0.9 * (y / max(1, h - 1)) ** 1.6))
        pygame.draw.line(fade, (255, 255, 255, a), (0, y), (w, y))
    spot.blit(fade, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    pad = pygame.Surface((w + 8 * K, h + 8 * K), pygame.SRCALPHA)
    pad.fill((255, 255, 255, 0))
    pad.blit(spot, (4 * K, 4 * K))
    if angle:
        pad = pygame.transform.rotate(pad, angle)
    layer.blit(pad, pad.get_rect(center=((rect[0] + rect[2] / 2) * K, (rect[1] + rect[3] / 2) * K)))


def glint(layer, x, y, r):
    """A four-pointed sparkle with a soft glow."""
    glow = surf(WHITE)
    pygame.draw.circle(glow, (255, 255, 255, 120), p(x, y), r * 0.8 * K)
    layer.blit(blur(glow, 6), (0, 0))
    t = r * 0.18
    for dx, dy in ((1, 0), (0, 1)):
        a, b = (x - dx * r, y - dy * r), (x + dx * r, y + dy * r)
        side1, side2 = (x - dy * t, y - dx * t), (x + dy * t, y + dx * t)
        pygame.draw.polygon(layer, (255, 255, 255, 245), [p(*a), p(*side1), p(*b), p(*side2)])
    pygame.draw.circle(layer, WHITE, p(x, y), r * 0.22 * K)


def shading(shape, dark=120, cx=0.36, cy=0.30):
    """A light layer to multiply over flat colour: bright at top-left, darker away from it."""
    rect = mask_of(shape).get_bounding_rects()[0]
    light = pygame.Surface((N, N))
    light.fill((dark, dark, dark))
    lx, ly = rect.x + rect.w * cx, rect.y + rect.h * cy
    reach = max(rect.w, rect.h) * 1.05
    for i in range(90, -1, -1):
        t = i / 90
        v = round(255 - (255 - dark) * t ** 1.6)
        pygame.draw.circle(light, (v, v, v), (lx, ly), max(1, reach * t))
    return light


def add_beads(top, shape, base, count, seed):
    """Little drops of moisture sitting on the surface."""
    rng = random.Random(seed)
    inner = erode(mask_of(shape), 9 * K)
    beads, tries = [], 0
    while len(beads) < count and tries < 5000:
        tries += 1
        x, y, r = rng.uniform(10, 114), rng.uniform(10, 114), rng.uniform(1.8, 3.2)
        if inner.get_at((int(x * K), int(y * K))) and all((x - a) ** 2 + (y - b) ** 2 > 220 for a, b, _ in beads):
            beads.append((x, y, r))
    for x, y, r in beads:
        shadow = surf(mix(base, EDGE, 0.6))
        pygame.draw.circle(shadow, (*mix(base, EDGE, 0.6), 110), p(x + 0.5, y + 0.8), r * K)
        top.blit(blur(shadow, 2), (0, 0))
        pygame.draw.circle(top, (*mix(base, WHITE, 0.35), 130), p(x, y), r * K)          # clear water
        pygame.draw.circle(top, (*mix(base, WHITE, 0.75), 150), p(x + r * 0.2, y + r * 0.25), r * 0.55 * K)
        pygame.draw.circle(top, (255, 255, 255, 255), p(x - r * 0.38, y - r * 0.38), r * 0.3 * K)


def finish(shape, colour, base, top=None, glints=(), dark=120, rim_light=0.55, outline_mix=0.72,
           beads=4, seed=1):
    """Shadow and outline behind; a glassy shaded body with bubbles, reflections and gloss on top."""
    top = top or surf(WHITE)
    add_beads(top, shape, base, beads, seed)
    mask = mask_of(shape)
    out = surf()
    edge = dilate(mask, 3 * K)
    ring = edge.copy()
    ring.erase(mask, (0, 0))   # outline only around the candy, so the glass can be see-through
    out.blit(blur(paint(edge, (0, 0, 0, 95)), 8), (0, 4 * K))
    out.blit(paint(ring, (*mix(base, EDGE, outline_mix), 255)), (0, 0))
    rect = mask.get_bounding_rects()[0]

    def at(fx, fy):
        return rect.x + rect.w * fx, rect.y + rect.h * fy

    body = colour.copy()
    body.blit(shading(shape, dark), (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    # glass is deeper in colour at its edges than in the middle
    deep = mask.copy()
    deep.erase(erode(mask, 7 * K), (0, 0))
    body.blit(clip(blur(paint(deep, (*mix(base, EDGE, 0.55), 105)), 10), shape), (0, 0))
    # soft glow from the light at the top left
    glow = surf()
    for i in range(40, -1, -1):
        t = i / 40
        v = round(60 * (1 - t) ** 2)
        pygame.draw.circle(glow, (v, v, v, 255), at(0.34, 0.28), max(1, rect.w * 0.5 * t))
    body.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    # light passing through the glass shines out on the far side (bottom right)
    caustic = surf()
    tint = mix(base, WHITE, 0.35)
    for i in range(40, -1, -1):
        t = i / 40
        f = (1 - t) ** 1.8
        pygame.draw.circle(caustic, (round(tint[0] * f * 0.75), round(tint[1] * f * 0.75),
                                     round(tint[2] * f * 0.75), 255), at(0.66, 0.74), max(1, rect.w * 0.34 * t))
    body.blit(clip(caustic, shape), (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    # a crisp bright line of reflected light just inside the bottom right edge
    band = erode(mask, round(2 * K))
    band.erase(mask, (round(-2 * K), round(-2.5 * K)))
    body.blit(clip(paint(band, (*mix(base, WHITE, max(rim_light, 0.7)), 210)), shape), (0, 0))
    # and a sharp white edge reflection along the top left
    wet = erode(mask, K)
    wet.erase(mask, (round(2 * K), round(2.5 * K)))
    body.blit(clip(paint(wet, (255, 255, 255, 220)), shape), (0, 0))
    body = clip(body, shape)
    body.set_alpha(246)        # a hint of the board showing through the glass
    out.blit(body, (0, 0))
    out.blit(clip(top, shape), (0, 0))
    for g in glints:
        glint(out, *g)
    return pygame.transform.smoothscale(out, (S, S))


# ── The candies ─────────────────────────────────────────────────────────────
def red_sweet():
    red, pink = (232, 36, 58), (255, 128, 148)
    deep = mix(red, EDGE, 0.35)
    wings = surf()
    for side in (1, -1):
        pts = [(62 - side * 27, 53), (62 - side * 57, 30), (62 - side * 49, 62),
               (62 - side * 57, 94), (62 - side * 27, 71)]
        pygame.draw.polygon(wings, WHITE, [p(*q) for q in pts])
    body = surf()
    pygame.draw.ellipse(body, WHITE, p(30, 35, 64, 54))
    shape = wings.copy()
    shape.blit(body, (0, 0))

    colour = surf()
    colour.fill((*pink, 255))
    for side in (1, -1):
        cx = 62 - side * 30
        # wrapper is darker where it's twisted into the knot
        knot = surf(deep)
        pygame.draw.ellipse(knot, (*deep, 160), p(cx - 10, 50, 20, 24))
        colour.blit(blur(knot, 8), (0, 0))
        for dy in (-20, -7, 7, 20):  # folds: a dark crease with a light ridge beside it
            end = (62 - side * 54, 62 + dy * 1.05)
            pygame.draw.line(colour, mix(red, EDGE, 0.15), p(cx, 62), p(*end), round(2.5 * K))
            pygame.draw.line(colour, mix(pink, WHITE, 0.6), p(cx, 63.5), p(end[0], end[1] + 2.2), round(1.3 * K))
        pygame.draw.ellipse(colour, deep, p(cx - 4, 53, 8, 18))  # the twist itself
        pygame.draw.line(colour, mix(pink, WHITE, 0.4), p(cx - side * 1, 55), p(cx - side * 1, 69), round(1.2 * K))
    pygame.draw.ellipse(colour, mix(red, EDGE, 0.6), p(28, 33, 68, 58))  # dark ring round the sweet
    candy = surf()
    candy.fill((*red, 255))
    stripes = surf()
    for u in (-0.62, 0, 0.62):  # stripes bend round the sweet like it's a ball
        left, right = [], []
        for i in range(31):
            y = 33 + i * 58 / 30
            f = math.sqrt(max(0.02, 1 - ((y - 62) / 29) ** 2))
            tilt = 0.32 * (y - 62)
            left.append((62 + (u - 0.15) * 34 * f + tilt, y))
            right.append((62 + (u + 0.15) * 34 * f + tilt, y))
        pygame.draw.polygon(stripes, WHITE, [p(*q) for q in left + right[::-1]])
    candy.blit(stripes, (0, 0))
    colour.blit(clip(candy, body), (0, 0))
    top = surf(WHITE)
    gloss(top, (38, 39, 32, 14), 255, angle=12)
    gloss(top, (64, 76, 18, 6), 90, angle=12)
    return finish(shape, colour, red, top, glints=[(44, 43, 5)], rim_light=0.5, seed=2)


def orange_gumdrop():
    orange = (255, 136, 20)
    shape = surf()
    pygame.draw.ellipse(shape, WHITE, p(24, 12, 76, 76))
    pygame.draw.polygon(shape, WHITE, [p(24, 50), p(100, 50), p(108, 98), p(16, 98)])
    pygame.draw.ellipse(shape, WHITE, p(16, 88, 92, 20))
    # glows from inside like a jelly
    colour = radial((255, 200, 90), orange, (56, 52), 52, power=1.3)
    pygame.draw.ellipse(colour, mix(orange, EDGE, 0.3), p(14, 84, 96, 26))      # base ridge
    pygame.draw.ellipse(colour, orange, p(16, 76, 92, 22))
    ridge = surf((255, 210, 140))
    pygame.draw.ellipse(ridge, (255, 210, 140, 150), p(22, 96, 60, 6))
    colour.blit(blur(ridge, 4), (0, 0))
    rng = random.Random(7)
    inner = erode(mask_of(shape), 8 * K)
    specks, tries = [], 0
    while len(specks) < 30 and tries < 8000:
        tries += 1
        x, y = rng.uniform(24, 100), rng.uniform(14, 88)
        if inner.get_at((int(x * K), int(y * K))) and all((x - a) ** 2 + (y - b) ** 2 > 80 for a, b in specks):
            specks.append((x, y))
    for x, y in specks:  # sugar crystals: shadow, body and a tiny shine each
        r = rng.uniform(1.7, 2.6)
        pygame.draw.circle(colour, mix(orange, EDGE, 0.35), p(x + 0.6, y + 0.9), r * K)
        pygame.draw.circle(colour, (255, 232, 180), p(x, y), r * K)
        pygame.draw.circle(colour, WHITE, p(x - r * 0.35, y - r * 0.35), r * 0.45 * K)
    top = surf(WHITE)
    gloss(top, (30, 18, 34, 24), 255, angle=22)
    gloss(top, (78, 52, 8, 22), 90, angle=-8)
    return finish(shape, colour, orange, top, glints=[(40, 28, 6)], beads=3, seed=3)


def yellow_star():
    yellow, light, dark = (255, 210, 40), (255, 246, 150), (220, 150, 0)
    c = (62, 66)
    pts = []
    for i in range(10):
        a = math.radians(-90 + i * 36)
        r = 54 if i % 2 == 0 else 24
        pts.append((c[0] + math.cos(a) * r, c[1] + math.sin(a) * r))
    shape = surf()
    pygame.draw.polygon(shape, WHITE, [p(*q) for q in pts])
    colour = surf()
    colour.fill((*yellow, 255))
    for i in range(10):  # bevelled facets lit from the top left
        a, b = pts[i], pts[(i + 1) % 10]
        mx, my = (a[0] + b[0]) / 2 - c[0], (a[1] + b[1]) / 2 - c[1]
        lit = (-mx * 0.6 - my * 0.8) / math.hypot(mx, my)
        pygame.draw.polygon(colour, mix(dark, light, (lit + 1) / 2), [p(*c), p(*a), p(*b)])
    ridges = surf()
    for i, q in enumerate(pts):  # shiny ridges out to the tips, soft creases to the dips
        if i % 2 == 0:
            pygame.draw.line(ridges, (255, 255, 230, 200), p(*c), p(*q), round(1.4 * K))
        else:
            pygame.draw.line(ridges, (*mix(dark, EDGE, 0.2), 120), p(*c), p(*q), round(1.2 * K))
    colour.blit(ridges, (0, 0))
    pygame.draw.circle(colour, (255, 250, 210), p(*c), 2.2 * K)
    top = surf(WHITE)
    gloss(top, (44, 28, 16, 10), 200, angle=-30)
    gloss(top, (24, 52, 18, 7), 150, angle=-10)
    return finish(shape, colour, dark, top, glints=[(62, 18, 7), (101, 51, 4)], dark=205, rim_light=0.75, beads=3, seed=4)


def green_bean():
    green = (66, 196, 76)
    shape = surf()
    pygame.draw.ellipse(shape, WHITE, p(14, 33, 96, 58))
    shape = rotated(shape, 28)
    flat = radial((130, 230, 120), green, (52, 52), 48, power=1.2)
    flat = clip(flat, shape)
    spots = surf(green)
    rng = random.Random(5)
    for _ in range(9):  # a few tiny bubbles in the jelly
        a, r = rng.uniform(0, math.tau), rng.uniform(0.3, 0.9)
        x, y = 66 + math.cos(a) * 34 * r, 60 + math.sin(a) * 18 * r
        pygame.draw.circle(spots, (215, 255, 205, 130), p(x, y), rng.uniform(1.0, 1.6) * K)
    seam = surf(mix(green, EDGE, 0.45))  # the little dent along the inside curve of the bean
    pygame.draw.arc(seam, (*mix(green, EDGE, 0.45), 150), p(30, 64, 64, 22), math.pi * 1.15, math.pi * 1.85,
                    round(2.5 * K))
    seam = blur(seam, 3)
    spots.blit(seam, (0, 0))
    spots = rotated(spots, 28)
    colour = surf()
    colour.fill((*green, 255))
    colour.blit(flat, (0, 0))
    colour.blit(clip(spots, shape), (0, 0))
    top = surf(WHITE)
    gloss(top, (26, 36, 46, 15), 255, angle=28)
    gloss(top, (70, 74, 22, 6), 90, angle=28)
    return finish(shape, colour, green, top, glints=[(38, 50, 5)], seed=5)


def blue_swirl():
    blue = (36, 116, 240)
    shape = surf()
    pygame.draw.circle(shape, WHITE, p(62, 62), 51 * K)
    colour = surf()
    colour.fill((248, 250, 255, 255))
    arms = surf()
    for k in range(6):
        a0 = k * math.tau / 6
        edge1, edge2 = [], []
        for i in range(41):
            t = i / 40
            r = t * 60
            edge1.append((62 + math.cos(a0 + t * 2.0) * r, 62 + math.sin(a0 + t * 2.0) * r))
            b = a0 + t * 2.0 + math.tau / 12 * (0.4 + 0.6 * t)
            edge2.append((62 + math.cos(b) * r, 62 + math.sin(b) * r))
        pygame.draw.polygon(arms, (*blue, 255), [p(*q) for q in edge1 + edge2[::-1]])
        # a lighter blue line on one side of each arm makes it look raised
        pygame.draw.lines(arms, (*mix(blue, WHITE, 0.45), 255), False, [p(*q) for q in edge2[8:]], round(1.6 * K))
    colour.blit(arms, (0, 0))
    pygame.draw.circle(colour, mix(blue, EDGE, 0.2), p(62, 62), 7 * K)
    pygame.draw.circle(colour, blue, p(61, 61), 5.5 * K)
    pygame.draw.circle(colour, WHITE, p(59.5, 59.5), 1.6 * K)
    # a thin glassy coat: a slightly brighter ring just inside the edge
    coat = surf(WHITE)
    pygame.draw.circle(coat, (255, 255, 255, 60), p(62, 62), 49 * K, round(2 * K))
    colour.blit(blur(coat, 3), (0, 0))
    top = surf(WHITE)
    gloss(top, (24, 18, 40, 22), 250, angle=28)
    gloss(top, (72, 88, 22, 8), 100, angle=28)
    return finish(shape, colour, blue, top, glints=[(36, 34, 6)], dark=135, rim_light=0.6, beads=5, seed=6)


def purple_heart():
    purple = (166, 74, 232)
    shape = surf()
    for x in (42, 82):
        pygame.draw.circle(shape, WHITE, p(x, 44), 27 * K)
    pygame.draw.polygon(shape, WHITE, [p(17, 54), p(107, 54), p(62, 110)])
    pygame.draw.polygon(shape, WHITE, [p(40, 40), p(84, 40), p(62, 60)])
    colour = surf()
    colour.fill((*mix(purple, EDGE, 0.15), 255))
    # a raised, pillowy middle
    pillow = paint(erode(mask_of(shape), 7 * K), (*mix(purple, WHITE, 0.18), 255))
    colour.blit(blur(pillow, 10), (0, 0))
    crease = surf(mix(purple, EDGE, 0.5))  # the dip between the two lobes
    pygame.draw.line(crease, (*mix(purple, EDGE, 0.5), 150), p(62, 28), p(62, 50), round(3 * K))
    colour.blit(blur(crease, 8), (0, 0))
    top = surf(WHITE)
    gloss(top, (24, 24, 28, 16), 255, angle=28)
    gloss(top, (78, 28, 14, 8), 170, angle=-20)
    gloss(top, (54, 82, 22, 6), 80, angle=-38)
    return finish(shape, colour, purple, top, glints=[(34, 32, 6), (88, 30, 3.5)], seed=7)


def color_bomb():
    choc = (104, 58, 34)
    shape = surf()
    pygame.draw.circle(shape, WHITE, p(62, 62), 51 * K)
    colour = radial((150, 90, 55), choc, (52, 48), 54, power=1.1)
    hues = [(255, 90, 130), (255, 220, 60), (70, 170, 255), (90, 220, 110), (255, 255, 255), (255, 150, 40),
            (190, 110, 255)]
    rng = random.Random(3)
    placed, tries = [], 0
    while len(placed) < 28 and tries < 20000:
        tries += 1
        a, r = rng.uniform(0, math.tau), 42 * math.sqrt(rng.random())
        x, y = 62 + math.cos(a) * r, 62 + math.sin(a) * r
        if all((x - u) ** 2 + (y - v) ** 2 > 130 for u, v in placed):
            placed.append((x, y))
    for i, (x, y) in enumerate(placed):
        a = rng.uniform(0, math.pi)
        dx, dy = math.cos(a) * 5.5, math.sin(a) * 5.5
        hue = hues[i % len(hues)]
        for colour_, off, width in ((mix(choc, EDGE, 0.5), (0.7, 1.0), 4.4),   # shadow
                                    (hue, (0, 0), 4.0),
                                    (mix(hue, WHITE, 0.65), (-0.6, -0.8), 1.4)):  # shine
            start, end = p(x - dx + off[0], y - dy + off[1]), p(x + dx + off[0], y + dy + off[1])
            pygame.draw.line(colour, colour_, start, end, round(width * K))
            for q in (start, end):
                pygame.draw.circle(colour, colour_, q, width / 2 * K)
    top = surf(WHITE)
    gloss(top, (24, 18, 40, 22), 210, angle=28)
    gloss(top, (74, 88, 20, 7), 80, angle=28)
    return finish(shape, colour, choc, top, glints=[(36, 34, 6), (86, 30, 3.5)], dark=110, rim_light=0.45, beads=3, seed=8,
                  outline_mix=0.6)


pygame.init()
pygame.display.set_mode((1, 1))
OUT.mkdir(parents=True, exist_ok=True)
for name, make in [("candy_0_red", red_sweet), ("candy_1_orange", orange_gumdrop),
                   ("candy_2_yellow", yellow_star), ("candy_3_green", green_bean),
                   ("candy_4_blue", blue_swirl), ("candy_5_purple", purple_heart),
                   ("color_bomb", color_bomb)]:
    pygame.image.save(make(), str(OUT / f"{name}.png"))
    print("saved", name)
