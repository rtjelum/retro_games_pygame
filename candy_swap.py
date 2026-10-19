"""Candy Swap -- swap neighbouring candies to line up three or more of a kind.

Matched candies pop, the ones above fall into the gaps, and new candies drop
in from the top. Bigger matches make special candies:

  4 in a line      striped candy: clears its whole row or column
  2 x 2 square     fish: swims off and eats 3 random candies
  L or T shape     bomb: blows up the 3 x 3 square around it
  5 in a line      colour bomb: swap it with a candy to clear all of that colour

Swap two specials together for a bigger blast. A chain reaction scores a
growing combo bonus. You have a limited number of moves to get the best score.

Controls: click a candy and then a neighbour (or drag it) to swap them.
          Keyboard: arrows move the cursor, Space picks up a candy, then an
          arrow swaps it. H hint, R new game, Esc quit.
"""
import math
import random
import sys
from pathlib import Path

import pygame

WIDTH, HEIGHT = 620, 770   # window size in screen points
FPS = 60
SIZE = 8            # cells along each side
KINDS = 6           # different candies
COLOR_BOMB = KINDS  # the colour bomb is a candy of its own that never matches
MOVES = 30
POINTS = 10         # per candy popped, times the combo

SWAP_TIME = 0.16
POP_TIME = 0.26
FALL_ACCEL = 60     # cells per second squared
EFFECT_TIME = 0.4   # how long beams, blasts and bolts stay on screen
SWIM_TIME = 0.26    # how long a fish takes to reach its target

# Navy and slate, matching the Mastermind game
BG_TOP, BG_BOTTOM = (40, 44, 78), (10, 10, 20)
SPOTLIGHT = (110, 130, 230)
SLATE_TOP, SLATE_BOTTOM = (58, 62, 92), (30, 32, 52)
TILE_A, TILE_B = (18, 20, 36, 210), (24, 26, 46, 210)
EDGE = (12, 12, 24)
TEXT, TEXT_DIM, WHITE = (255, 215, 120), (170, 178, 215), (255, 255, 255)
GOLD_TOP, GOLD_BOTTOM = (255, 240, 180), (214, 140, 40)
DANGER = (255, 96, 110)

# Each candy is its own picture in assets/candy (wrapped sweet, gumdrop, star,
# jelly bean, peppermint swirl, heart, plus the colour bomb). These colours
# match them, for the sparkles and blasts.
CANDY_DIR = Path(__file__).parent / "assets" / "candy"
COLORS = [(235, 60, 80), (255, 146, 36), (255, 212, 50),
          (80, 200, 90), (55, 140, 245), (175, 90, 235)]
STEPS = {pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1),
         pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0)}


# ── Screen scale ────────────────────────────────────────────────────────────
# Everything is drawn in real pixels so it stays sharp on high-resolution
# (Retina) screens. U is pixels per screen point: 2 on a Retina Mac, else 1.
def set_scale(u):
    global U, W, H, CELL, BOARD, BOARD_X, BOARD_Y
    U = u
    W, H = round(WIDTH * u), round(HEIGHT * u)
    CELL = round(64 * u)
    BOARD = SIZE * CELL
    BOARD_X, BOARD_Y = (W - BOARD) // 2, round(168 * u)


set_scale(1)


# ── Board logic ─────────────────────────────────────────────────────────────
def find_runs(grid):
    """Every straight line of three or more matching candies: (cells, horizontal)."""
    runs = []
    for horizontal in (True, False):
        for a in range(SIZE):
            b = 0
            while b < SIZE:
                x, y = (b, a) if horizontal else (a, b)
                kind = grid[y][x]
                n = 1
                while b + n < SIZE:
                    nx, ny = (b + n, a) if horizontal else (a, b + n)
                    if grid[ny][nx] != kind:
                        break
                    n += 1
                if kind is not None and kind < KINDS and n >= 3:
                    runs.append(([(b + i, a) if horizontal else (a, b + i) for i in range(n)], horizontal))
                b += n
    return runs


def find_squares(grid):
    """Every 2 x 2 block of matching candies."""
    squares = []
    for y in range(SIZE - 1):
        for x in range(SIZE - 1):
            kind = grid[y][x]
            if (kind is not None and kind < KINDS
                    and grid[y][x + 1] == grid[y + 1][x] == grid[y + 1][x + 1] == kind):
                squares.append(([(x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)], "square"))
    return squares


def has_match(grid):
    return bool(find_runs(grid) or find_squares(grid))


def find_groups(grid):
    """Lines and squares that touch or cross are one match. Returns [(cells, shapes)].

    Each shape is (cells, kind of shape): True for a row, False for a column,
    or "square" for a 2 x 2 block.
    """
    groups = []
    for run in find_runs(grid) + find_squares(grid):
        cells, runs = set(run[0]), [run]
        for other in [g for g in groups if g[0] & cells]:
            groups.remove(other)
            cells |= other[0]
            runs += other[1]
        groups.append((cells, runs))
    return groups


def special_for(shapes):
    """Which special candy a match makes, if any. Bigger specials win."""
    lines = [shape for shape in shapes if shape[1] != "square"]
    if lines:
        longest = max(lines, key=lambda line: len(line[0]))
        if len(longest[0]) >= 5:
            return "color"
        if len({horizontal for _, horizontal in lines}) == 2:
            return "bomb"   # an L or T shape
        if len(longest[0]) == 4:
            return "row" if longest[1] else "col"
    if len(lines) < len(shapes):
        return "fish"       # a 2 x 2 square
    return None


def swapped(grid, a, b):
    copy = [row[:] for row in grid]
    (ax, ay), (bx, by) = a, b
    copy[ay][ax], copy[by][bx] = copy[by][bx], copy[ay][ax]
    return copy


def power_swap(grid, special, a, b):
    """True when a swap sets off specials without needing a match."""
    (ax, ay), (bx, by) = a, b
    return (COLOR_BOMB in (grid[ay][ax], grid[by][bx])
            or bool(special[ay][ax] and special[by][bx]))


def find_move(grid, special=None):
    """A swap that does something, or None if the board is stuck."""
    special = special or [[None] * SIZE for _ in range(SIZE)]
    moves = [((x, y), (x + dx, y + dy)) for y in range(SIZE) for x in range(SIZE)
             for dx, dy in ((1, 0), (0, 1)) if x + dx < SIZE and y + dy < SIZE]
    random.shuffle(moves)
    for a, b in moves:
        if power_swap(grid, special, a, b) or has_match(swapped(grid, a, b)):
            return a, b
    return None


def new_board():
    """A random board with no matches already on it, but at least one to make."""
    while True:
        grid = [[None] * SIZE for _ in range(SIZE)]
        for y in range(SIZE):
            for x in range(SIZE):
                banned = set()
                if x >= 2 and grid[y][x - 1] == grid[y][x - 2]:
                    banned.add(grid[y][x - 1])
                if y >= 2 and grid[y - 1][x] == grid[y - 2][x]:
                    banned.add(grid[y - 1][x])
                if x >= 1 and y >= 1 and grid[y - 1][x - 1] == grid[y - 1][x] == grid[y][x - 1]:
                    banned.add(grid[y][x - 1])   # would finish a 2 x 2 square
                grid[y][x] = random.choice([k for k in range(KINDS) if k not in banned])
        if find_move(grid):
            return grid


def square(center, radius):
    cx, cy = center
    return [(x, y) for x in range(cx - radius, cx + radius + 1)
            for y in range(cy - radius, cy + radius + 1) if 0 <= x < SIZE and 0 <= y < SIZE]


def color_of(kind):
    return COLORS[kind] if kind is not None and kind < KINDS else WHITE


# ── Pictures ────────────────────────────────────────────────────────────────
def mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def blur(surface, amount):
    w, h = surface.get_size()
    small = pygame.transform.smoothscale(surface, (max(1, w // amount), max(1, h // amount)))
    return pygame.transform.smoothscale(small, (w, h))


def body_mask(picture, inset):
    """The solid part of a candy picture, shrunk by `inset` pixels."""
    mask = pygame.mask.from_surface(picture, 200)  # glass candies are slightly see-through
    inner = mask.copy()
    for a in range(0, 360, 45):
        shifted = pygame.mask.Mask(mask.get_size())
        shifted.draw(mask, (round(math.cos(math.radians(a)) * inset),
                            round(math.sin(math.radians(a)) * inset)))
        inner = inner.overlap_mask(shifted, (0, 0))
    return inner


def striped(picture, horizontal):
    """A candy with white stripes across it."""
    out = picture.copy()
    w, h = out.get_size()
    stripes = pygame.Surface((w, h), pygame.SRCALPHA)
    for offset in (-0.22, 0, 0.22):
        if horizontal:
            pygame.draw.rect(stripes, (255, 255, 255, 225), (0, h * (0.5 + offset) - h * 0.04, w, h * 0.08))
        else:
            pygame.draw.rect(stripes, (255, 255, 255, 225), (w * (0.5 + offset) - w * 0.04, 0, w * 0.08, h))
    keep = body_mask(picture, max(2, w // 40)).to_surface(setcolor=(255, 255, 255, 255),
                                                          unsetcolor=(0, 0, 0, 0))
    stripes.blit(keep, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    out.blit(stripes, (0, 0))
    return out


def wrapped(picture, color):
    """A bomb: the candy, a little smaller, inside a bright ring with sparkles."""
    w, h = picture.get_size()
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    c, r = w / 2, w * 0.46
    pygame.draw.circle(out, EDGE, (c, c), r + w * 0.02)
    pygame.draw.circle(out, mix(color, WHITE, 0.25), (c, c), r)
    pygame.draw.circle(out, mix(color, (0, 0, 0), 0.35), (c, c), r * 0.86)
    pygame.draw.circle(out, WHITE, (c, c), r, max(2, round(w * 0.025)))
    inner = pygame.transform.smoothscale(picture, (round(w * 0.78), round(h * 0.78)))
    out.blit(inner, inner.get_rect(center=(c, c)))
    for a in (45, 135, 225, 315):  # four little sparkles on the ring
        x, y = c + math.cos(math.radians(a)) * r, c + math.sin(math.radians(a)) * r
        s = w * 0.07
        pygame.draw.polygon(out, WHITE, [(x, y - s), (x + s * 0.3, y), (x, y + s), (x - s * 0.3, y)])
        pygame.draw.polygon(out, WHITE, [(x - s, y), (x, y + s * 0.3), (x + s, y), (x, y - s * 0.3)])
    return out


def make_fish(color, size=256):
    """A jelly fish-shaped candy with a big eye, drawn oversize for smooth edges."""
    n = size * 4
    k = n / 1024
    body = pygame.Surface((n, n), pygame.SRCALPHA)
    pygame.draw.polygon(body, mix(color, (0, 0, 0), 0.15),
                        [(330 * k, 512 * k), (110 * k, 300 * k), (170 * k, 512 * k), (110 * k, 724 * k)])
    pygame.draw.polygon(body, mix(color, (0, 0, 0), 0.15),
                        [(480 * k, 330 * k), (600 * k, 210 * k), (690 * k, 330 * k)])
    pygame.draw.ellipse(body, color, (250 * k, 300 * k, 650 * k, 430 * k))
    mask = pygame.mask.from_surface(body)
    out = pygame.Surface((n, n), pygame.SRCALPHA)
    out.blit(mask.to_surface(setcolor=(0, 0, 0, 70), unsetcolor=(0, 0, 0, 0)), (0, round(34 * k)))
    edge = mask.to_surface(setcolor=mix(color, (0, 0, 0), 0.6), unsetcolor=(0, 0, 0, 0))
    for a in range(0, 360, 15):
        out.blit(edge, (round(math.cos(math.radians(a)) * 22 * k), round(math.sin(math.radians(a)) * 22 * k)))
    out.blit(body, (0, 0))
    pygame.draw.ellipse(out, mix(color, WHITE, 0.45), (380 * k, 560 * k, 440 * k, 130 * k))  # belly
    pygame.draw.ellipse(out, (255, 255, 255, 210), (430 * k, 350 * k, 230 * k, 70 * k))      # shine
    pygame.draw.circle(out, WHITE, (735 * k, 460 * k), 74 * k)                                # eye
    pygame.draw.circle(out, EDGE, (735 * k, 460 * k), 74 * k, round(12 * k))
    pygame.draw.circle(out, EDGE, (752 * k, 466 * k), 38 * k)
    pygame.draw.circle(out, WHITE, (764 * k, 452 * k), 13 * k)
    pygame.draw.arc(out, EDGE, (760 * k, 520 * k, 110 * k, 90 * k), math.pi * 1.1, math.pi * 1.9,
                    round(14 * k))                                                            # smile
    return pygame.transform.smoothscale(out, (size, size))


def load_candies(size):
    """Every candy picture, sized to fit a cell: plain, striped both ways, bomb, colour bomb."""
    # convert_alpha matches the screen's pixel layout, which makes drawing ~6x faster
    plain = [pygame.image.load(str(f)).convert_alpha() for f in sorted(CANDY_DIR.glob("candy_*.png"))]

    def fit(picture):
        return pygame.transform.smoothscale(picture, (size, size))

    return {
        None: [fit(p) for p in plain],
        "row": [fit(striped(p, True)) for p in plain],
        "col": [fit(striped(p, False)) for p in plain],
        "bomb": [fit(wrapped(p, COLORS[k])) for k, p in enumerate(plain)],
        "fish": [fit(make_fish(color)) for color in COLORS],
        "color": fit(pygame.image.load(str(CANDY_DIR / "color_bomb.png")).convert_alpha()),
    }


def make_backdrop():
    """A navy-to-black gradient with a soft blue spotlight behind the board."""
    strip = pygame.Surface((1, H))
    for y in range(H):
        strip.set_at((0, y), mix(BG_TOP, BG_BOTTOM, y / (H - 1)))
    backdrop = pygame.transform.scale(strip, (W, H))
    glow = pygame.Surface((W, H), pygame.SRCALPHA)
    for k in range(30):
        t = k / 29
        pygame.draw.circle(glow, (*SPOTLIGHT, round(46 * t * t)), (W // 2, BOARD_Y + BOARD // 2.4),
                           round(460 * U * (1 - 0.8 * t)))
    backdrop.blit(glow, (0, 0))
    return backdrop


def slate_panel(surface, rect, radius, alpha=255):
    """A raised slate panel with a soft shadow and a lit rim, like Mastermind's trays."""
    rect = pygame.Rect(rect)
    radius = round(radius * U)
    margin = round(16 * U)
    shadow = pygame.Surface((rect.w + 2 * margin, rect.h + 2 * margin), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 150),
                     pygame.Rect(margin, margin, rect.w, rect.h).inflate(4 * U, 4 * U).move(0, 6 * U),
                     border_radius=radius)
    surface.blit(blur(shadow, 6), (rect.x - margin, rect.y - margin))
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    for y in range(rect.h):
        pygame.draw.line(panel, mix(SLATE_TOP, SLATE_BOTTOM, y / max(1, rect.h - 1)), (0, y), (rect.w, y))
    mask = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, alpha), mask.get_rect(), border_radius=radius)
    panel.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    pygame.draw.rect(panel, (255, 255, 255, 50), panel.get_rect(), max(1, round(2 * U)),
                     border_radius=radius)
    surface.blit(panel, rect)


def outlined(font, text, fill_top, fill_bottom, edge, thickness):
    """Text with a gradient fill, a thick outline and a drop shadow."""
    face = font.render(text, True, WHITE)
    w, h = face.get_size()
    gradient = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        pygame.draw.line(gradient, mix(fill_top, fill_bottom, y / max(1, h - 1)), (0, y), (w, y))
    face.blit(gradient, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    thickness *= U
    pad = round(thickness + 4 * U)
    out = pygame.Surface((w + 2 * pad, h + 2 * pad), pygame.SRCALPHA)
    ring = font.render(text, True, edge)
    shadow = font.render(text, True, (0, 0, 0))
    shadow.set_alpha(120)
    for angle in range(0, 360, 20):
        dx = round(math.cos(math.radians(angle)) * thickness)
        dy = round(math.sin(math.radians(angle)) * thickness)
        out.blit(shadow, (pad + dx, pad + dy + round(4 * U)))
    for angle in range(0, 360, 20):
        dx = round(math.cos(math.radians(angle)) * thickness)
        dy = round(math.sin(math.radians(angle)) * thickness)
        out.blit(ring, (pad + dx, pad + dy))
    out.blit(face, (pad, pad))
    return out


def make_board():
    """A slate panel with dark rounded slots for the candies."""
    surface = pygame.Surface((W, H), pygame.SRCALPHA)
    board = pygame.Rect(BOARD_X, BOARD_Y, BOARD, BOARD)
    slate_panel(surface, board.inflate(round(28 * U), round(28 * U)), 24)
    gap = round(2 * U)
    for y in range(SIZE):
        for x in range(SIZE):
            slot = pygame.Rect(BOARD_X + x * CELL + gap, BOARD_Y + y * CELL + gap,
                               CELL - 2 * gap, CELL - 2 * gap)
            pygame.draw.rect(surface, TILE_A if (x + y) % 2 else TILE_B, slot,
                             border_radius=round(12 * U))
            pygame.draw.line(surface, (255, 255, 255, 30), (slot.left + 10 * U, slot.bottom - 1),
                             (slot.right - 10 * U, slot.bottom - 1), round(U))
    return surface


# ── Game ────────────────────────────────────────────────────────────────────
class CandySwap:
    def __init__(self):
        pygame.init()
        # allow_high_dpi gives a full-resolution surface on Retina screens
        self.window = pygame.Window("Candy Swap", (WIDTH, HEIGHT), allow_high_dpi=True)
        self.screen = self.window.get_surface()
        set_scale(self.screen.get_width() / WIDTH)
        self.clock = pygame.time.Clock()
        self.build_art()
        self.best = 0
        self.time = 0.0
        self.new_game()

    def build_art(self):
        """Fonts and pre-drawn pictures, sized for the current screen scale."""
        rounded = "arialrounded,sfnsrounded,verdana"

        def font(size, bold=True):
            return pygame.font.SysFont(rounded, round(size * U), bold=bold)

        self.title_font = pygame.font.SysFont("georgia", round(46 * U), bold=True)
        self.font = font(26)
        self.label_font = font(12)
        self.small_font = font(14, bold=False)
        self.big_font = font(50)
        self.pop_font = font(26)
        self.backdrop = make_backdrop()
        self.board_art = make_board()
        self.title = outlined(self.title_font, "CANDY SWAP", GOLD_TOP, GOLD_BOTTOM, EDGE, 2)
        self.candies = load_candies(round(CELL - 2 * U))
        # The badge panel never changes, so draw it (with its shadow) just once
        m = round(20 * U)
        self.badge = pygame.Surface((round(150 * U) + 2 * m, round(52 * U) + 2 * m), pygame.SRCALPHA)
        slate_panel(self.badge, (m, m, round(150 * U), round(52 * U)), 16)

    # ── Game state ──────────────────────────────────────────────────────────
    def new_game(self):
        self.grid = new_board()
        self.special = [[None] * SIZE for _ in range(SIZE)]   # None / row / col / bomb / color
        self.fall = [[0.0] * SIZE for _ in range(SIZE)]       # cells above its place
        self.speed = [[0.0] * SIZE for _ in range(SIZE)]
        self.score = 0
        self.moves = MOVES
        self.combo = 0
        self.selected = None
        self.cursor = (SIZE // 2, SIZE // 2)
        self.show_cursor = False
        self.drag_from = None
        self.hint = None
        self.swap = None        # (a, b, undo) while two candies trade places
        self.popping = set()
        self.creations = []     # (cell, kind, special) made by the matches popping now
        self.phase, self.timer = "idle", 0.0   # idle / swap / pop / fall / over
        self.particles = []     # [x, y, vx, vy, age, color, spin]
        self.rings = []         # [x, y, age, color] bursts where candies pop
        self.beams = []         # [index, horizontal, age, color] striped candies firing
        self.blasts = []        # [x, y, radius, age, color] bombs going off
        self.bolts = []         # [start, end, age] colour bomb lightning
        self.swims = []         # [start, end, age, kind] fish on their way to a target
        self.popups = []        # [text, x, y, age]
        self.message = None     # (text, seconds left)

    def try_swap(self, a, b):
        if self.phase != "idle" or abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1:
            return
        self.selected = None
        self.hint = None
        self.swap = (a, b, False)
        self.phase, self.timer = "swap", 0.0

    def finish_swap(self):
        a, b, undo = self.swap
        (ax, ay), (bx, by) = a, b
        self.grid = swapped(self.grid, a, b)
        self.special = swapped(self.special, a, b)
        self.swap = None
        if undo:
            self.phase = "idle"
            return
        if power_swap(self.grid, self.special, a, b):
            self.moves -= 1
            self.combo = 0
            self.start_pop(*self.power_up(a, b), moved=(a, b))
        elif has_match(self.grid):
            self.moves -= 1
            self.combo = 0
            self.start_pop(moved=(a, b))
        else:  # no match: slide back
            self.swap = (a, b, True)
            self.phase, self.timer = "swap", 0.0

    def power_up(self, a, b):
        """What swapping a colour bomb, or two specials, sets off. Returns (cells, used)."""
        (ax, ay), (bx, by) = a, b
        if COLOR_BOMB in (self.grid[ay][ax], self.grid[by][bx]):
            bomb, other = (a, b) if self.grid[ay][ax] == COLOR_BOMB else (b, a)
            kind, power = self.grid[other[1]][other[0]], self.special[other[1]][other[0]]
            if kind == COLOR_BOMB:   # two colour bombs: clear the lot
                self.add_popup("Sweet storm!", b)
                self.blasts.append([*self.center(b), SIZE, 0.0, WHITE])
                return [(x, y) for x in range(SIZE) for y in range(SIZE)], {a, b}
            targets = [(x, y) for x in range(SIZE) for y in range(SIZE) if self.grid[y][x] == kind]
            for x, y in targets:
                self.bolts.append([self.center(bomb), self.center((x, y)), 0.0])
                if power in ("row", "col"):  # every candy of that colour turns striped and fires
                    self.special[y][x] = random.choice(("row", "col"))
                elif power in ("bomb", "fish"):
                    self.special[y][x] = power
            self.add_popup("Colour bomb!", bomb)
            return targets + [bomb], {bomb}

        pair = {self.special[ay][ax], self.special[by][bx]}
        if "fish" in pair:
            other = (pair - {"fish"}).pop() if len(pair) > 1 else "fish"
            kind = self.grid[by][bx] if self.special[by][bx] == "fish" else self.grid[ay][ax]
            if other == "fish":   # two fish: six targets
                self.add_popup("School of fish!", b)
                return self.send_fish(b, 6, {a, b}, kind) + [a, b], {a, b}
            # The fish carries the other special to a random spot, where it goes off
            targets = self.send_fish(b, 1, {a, b}, kind)
            for x, y in targets:
                self.special[y][x] = random.choice(("row", "col")) if other in ("row", "col") else other
            self.add_popup("Special delivery!", b)
            return targets + [a, b], {a, b}
        if pair == {"bomb"}:
            cells = square(b, 2)
            self.blasts.append([*self.center(b), 2.5, 0.0, color_of(self.grid[by][bx])])
            self.add_popup("Mega blast!", b)
        elif "bomb" in pair:     # striped + bomb: three rows and three columns
            cells = []
            for d in (-1, 0, 1):
                cells += self.line(by + d, True) + self.line(bx + d, False)
            self.add_popup("Big cross!", b)
        else:                    # two striped: a row and a column
            cells = self.line(by, True) + self.line(bx, False)
            self.add_popup("Cross!", b)
        return cells + [a, b], {a, b}

    def line(self, index, horizontal):
        """A whole row or column, with a beam across it."""
        if not 0 <= index < SIZE:
            return []
        color = WHITE
        self.beams.append([index, horizontal, 0.0, color])
        return [(i, index) if horizontal else (index, i) for i in range(SIZE)]

    def send_fish(self, start, count, avoid, kind):
        """Picks random candies for fish to eat, and starts them swimming there."""
        options = [(x, y) for y in range(SIZE) for x in range(SIZE)
                   if (x, y) not in avoid and self.grid[y][x] is not None]
        targets = random.sample(options, min(count, len(options)))
        for target in targets:
            self.swims.append([self.center(start), self.center(target), 0.0, kind])
        return targets

    def fire(self, cell, power, avoid=()):
        """The cells a special candy clears when it goes off."""
        x, y = cell
        if power == "fish":
            return self.send_fish(cell, 3, set(avoid) | {cell}, self.grid[y][x])
        if power == "row":
            return self.line(y, True)
        if power == "col":
            return self.line(x, False)
        if power == "bomb":
            self.blasts.append([*self.center(cell), 1.5, 0.0, color_of(self.grid[y][x])])
            return square(cell, 1)
        # A colour bomb caught in a blast takes out the most common candy
        counts = {}
        for row in self.grid:
            for kind in row:
                if kind is not None and kind < KINDS:
                    counts[kind] = counts.get(kind, 0) + 1
        if not counts:
            return []
        kind = max(counts, key=counts.get)
        targets = [(i, j) for i in range(SIZE) for j in range(SIZE) if self.grid[j][i] == kind]
        for target in targets:
            self.bolts.append([self.center(cell), self.center(target), 0.0])
        return targets

    def start_pop(self, extra=(), used=(), moved=()):
        """Pops every match, sets off any specials caught up in it, and plans new specials."""
        seeds = set(extra)
        self.creations = []
        for cells, runs in find_groups(self.grid):
            seeds |= cells
            power = special_for(runs)
            if power is None:
                continue
            spot = next((c for c in reversed(moved) if c in cells), None)
            if spot is None and power == "bomb":   # where the lines cross
                lines = [set(run[0]) for run in runs if run[1] != "square"]
                spot = next(c for c in cells if sum(c in line for line in lines) > 1)
            if spot is None and power == "fish":
                spot = next(run[0][0] for run in runs if run[1] == "square")
            if spot is None:
                longest = max(runs, key=lambda run: len(run[0]))[0]
                spot = longest[len(longest) // 2]
            kind = COLOR_BOMB if power == "color" else self.grid[spot[1]][spot[0]]
            self.creations.append((spot, kind, power))
            self.add_popup({"row": "Striped!", "col": "Striped!", "bomb": "Bomb!", "fish": "Fish!",
                            "color": "Colour bomb!"}[power], spot, 0.45)

        # Clear everything, letting specials set each other off
        used, cleared, queue = set(used), set(), list(seeds)
        while queue:
            cell = queue.pop()
            if cell in cleared:
                continue
            cleared.add(cell)
            power = self.special[cell[1]][cell[0]]
            if self.grid[cell[1]][cell[0]] == COLOR_BOMB:
                power = "color"
            if power and cell not in used:
                used.add(cell)
                queue.extend(self.fire(cell, power, cleared | set(queue)))
        made = {spot for spot, _, _ in self.creations}
        self.popping = {c for c in cleared - made if self.grid[c[1]][c[0]] is not None}

        self.combo += 1
        gained = (len(self.popping) + 3 * len(self.creations)) * POINTS * self.combo
        self.score += gained
        if self.popping:
            cx = sum(x for x, _ in self.popping) / len(self.popping)
            cy = sum(y for _, y in self.popping) / len(self.popping)
            px, py = self.center((cx, cy))
            label = f"+{gained}" + (f"  x{self.combo}" if self.combo > 1 else "")
            self.popups.append([label, px, py, 0.0])
        for x, y in self.popping:
            ox, oy = self.center((x, y))
            color = color_of(self.grid[y][x])
            self.rings.append([ox, oy, 0.0, color])
            for _ in range(6):
                a, v = random.uniform(0, 2 * math.pi), random.uniform(80, 240) * U
                self.particles.append([ox, oy, math.cos(a) * v, math.sin(a) * v, 0.0,
                                       random.choice((color, mix(color, WHITE, 0.6))),
                                       random.uniform(0, math.pi)])
        self.phase, self.timer = "pop", 0.0

    def drop(self):
        """Clears popped candies, places new specials, lets the rest fall and fills from the top."""
        for x, y in self.popping:
            self.grid[y][x] = None
            self.special[y][x] = None
        for (x, y), kind, power in self.creations:
            self.grid[y][x] = kind
            self.special[y][x] = power
        self.popping = set()
        self.creations = []
        for x in range(SIZE):
            rows = [y for y in range(SIZE) if self.grid[y][x] is not None]
            column = [(self.grid[y][x], self.special[y][x]) for y in rows]
            missing = SIZE - len(column)
            for y in range(SIZE):
                self.speed[y][x] = 0.0
                if y < missing:
                    self.grid[y][x], self.special[y][x] = random.randrange(KINDS), None
                    self.fall[y][x] = missing
                else:
                    self.grid[y][x], self.special[y][x] = column[y - missing]
                    self.fall[y][x] = y - rows[y - missing]
        self.phase = "fall"

    def settle(self):
        """Called once everything has landed: chain on, or hand back to the player."""
        if has_match(self.grid):
            self.start_pop()
            return
        self.phase = "idle"
        if self.moves == 0:
            self.phase = "over"
            self.new_best = self.score > self.best
            self.best = max(self.best, self.score)
        elif not find_move(self.grid, self.special):
            self.grid = new_board()
            self.special = [[None] * SIZE for _ in range(SIZE)]
            self.message = ("No moves left - shuffled!", 1.6)

    def add_popup(self, text, cell, delay=0.0):
        x, y = self.center(cell)
        self.popups.append([text, x, y - CELL * 0.8, -delay])

    def update(self, dt):
        self.time += dt
        self.timer += dt
        if self.phase == "swap" and self.timer >= SWAP_TIME:
            self.finish_swap()
        elif self.phase == "pop" and self.timer >= POP_TIME:
            self.drop()
        elif self.phase == "fall":
            landed = True
            for y in range(SIZE):
                for x in range(SIZE):
                    if self.fall[y][x] > 0:
                        self.speed[y][x] += FALL_ACCEL * dt
                        self.fall[y][x] = max(0.0, self.fall[y][x] - self.speed[y][x] * dt)
                        landed = landed and self.fall[y][x] == 0
            if landed:
                self.settle()

        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 500 * U * dt
            p[4] += dt
        self.particles = [p for p in self.particles if p[4] < 0.6]
        for effects, age in ((self.rings, 2), (self.beams, 2), (self.blasts, 3), (self.bolts, 2)):
            for e in effects:
                e[age] += dt
        self.rings = [r for r in self.rings if r[2] < 0.35]
        self.beams = [b for b in self.beams if b[2] < EFFECT_TIME]
        self.blasts = [b for b in self.blasts if b[3] < EFFECT_TIME]
        self.bolts = [b for b in self.bolts if b[2] < EFFECT_TIME]
        for swim in self.swims:
            swim[2] += dt
        self.swims = [f for f in self.swims if f[2] < SWIM_TIME]
        for p in self.popups:
            if p[3] >= 0:
                p[2] -= 40 * U * dt
            p[3] += dt
        self.popups = [p for p in self.popups if p[3] < 0.9]
        if self.message:
            self.message = (self.message[0], self.message[1] - dt) if self.message[1] > dt else None

    # ── Drawing ─────────────────────────────────────────────────────────────
    def center(self, cell):
        return BOARD_X + (cell[0] + 0.5) * CELL, BOARD_Y + (cell[1] + 0.5) * CELL

    def cell_at(self, pos):
        """The cell under a mouse position, given in pixels."""
        x, y = int((pos[0] - BOARD_X) // CELL), int((pos[1] - BOARD_Y) // CELL)
        return (x, y) if 0 <= x < SIZE and 0 <= y < SIZE else None

    def sprite(self, kind, power):
        if kind == COLOR_BOMB:
            return self.candies["color"]
        return self.candies[power if power in ("row", "col", "bomb", "fish") else None][kind]

    def draw_candy(self, sprite, pos, scale=1.0):
        if scale != 1.0:
            size = max(1, round(sprite.get_width() * scale))
            sprite = pygame.transform.smoothscale(sprite, (size, size))
        self.screen.blit(sprite, sprite.get_rect(center=(round(pos[0]), round(pos[1]))))

    def glow_slot(self, cell, color, alpha, width):
        x, y = BOARD_X + cell[0] * CELL, BOARD_Y + cell[1] * CELL
        m = round(6 * U)
        layer = pygame.Surface((CELL + 2 * m, CELL + 2 * m), pygame.SRCALPHA)
        slot = pygame.Rect(m, m, CELL, CELL)
        radius = round(14 * U)
        pygame.draw.rect(layer, (*color, alpha // 3), slot, border_radius=radius)
        pygame.draw.rect(layer, (*color, alpha), slot, round(width * U), border_radius=radius)
        self.screen.blit(blur(layer, 2), (x - m, y - m))
        self.screen.blit(layer, (x - m, y - m))

    def draw_sparkle(self, x, y, radius, color, spin):
        points = []
        for i in range(8):
            r = radius if i % 2 == 0 else radius * 0.35
            a = spin + i * math.pi / 4
            points.append((x + math.cos(a) * r, y + math.sin(a) * r))
        pygame.draw.polygon(self.screen, color, points)

    def draw_effects(self):
        for (x0, y0), (x1, y1), age, kind in self.swims:  # fish leap in an arc to their target
            t = age / SWIM_TIME
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t - math.sin(math.pi * t) * CELL * 1.2
            fish = self.candies["fish"][kind if kind is not None and kind < KINDS else 0]
            if x1 < x0:
                fish = pygame.transform.flip(fish, True, False)
            self.draw_candy(fish, (x, y), 0.7)
        if not (self.beams or self.blasts or self.bolts):
            return
        layer = pygame.Surface((W, H), pygame.SRCALPHA)
        for index, horizontal, age, color in self.beams:
            t = age / EFFECT_TIME
            thick = CELL * (0.7 - 0.5 * t)
            if horizontal:
                y = BOARD_Y + (index + 0.5) * CELL
                rect = pygame.Rect(BOARD_X, y - thick / 2, BOARD, thick)
                core = pygame.Rect(BOARD_X, y - thick / 6, BOARD, thick / 3)
            else:
                x = BOARD_X + (index + 0.5) * CELL
                rect = pygame.Rect(x - thick / 2, BOARD_Y, thick, BOARD)
                core = pygame.Rect(x - thick / 6, BOARD_Y, thick / 3, BOARD)
            fade = round(255 * (1 - t))
            pygame.draw.rect(layer, (150, 190, 255, fade // 2), rect, border_radius=round(thick / 2))
            pygame.draw.rect(layer, (255, 255, 255, fade), core, border_radius=round(thick / 6))
        for x, y, radius, age, color in self.blasts:
            t = age / EFFECT_TIME
            r = CELL * radius * (0.4 + 0.6 * t)
            fade = round(200 * (1 - t))
            pygame.draw.circle(layer, (*mix(color, WHITE, 0.5), fade // 2), (x, y), r)
            pygame.draw.circle(layer, (255, 255, 255, fade), (x, y), r, max(2, round(6 * U * (1 - t))))
        rng = random.Random(int(self.time * 30))
        for (x0, y0), (x1, y1), age in self.bolts:
            fade = round(255 * (1 - age / EFFECT_TIME))
            points = [(x0, y0)]
            for i in range(1, 6):  # a jagged lightning bolt
                t = i / 6
                points.append((x0 + (x1 - x0) * t + rng.uniform(-8, 8) * U,
                               y0 + (y1 - y0) * t + rng.uniform(-8, 8) * U))
            points.append((x1, y1))
            pygame.draw.lines(layer, (255, 230, 140, fade), False, points, max(2, round(3 * U)))
            pygame.draw.lines(layer, (255, 255, 255, fade), False, points, max(1, round(U)))
        area = pygame.Rect(BOARD_X, BOARD_Y, BOARD, BOARD).inflate(CELL * 2, CELL * 2)
        self.screen.blit(layer, area, area)

    def draw_board(self):
        self.screen.blit(self.board_art, (0, 0))
        if self.hint and self.phase == "idle":
            pulse = (math.sin(self.time * 7) + 1) / 2
            for cell in self.hint:
                self.glow_slot(cell, TEXT, round(120 + 135 * pulse), 3)
        if self.selected:
            self.glow_slot(self.selected, WHITE, 230, 3)
        if self.show_cursor and self.phase != "over" and self.cursor != self.selected:
            self.glow_slot(self.cursor, TEXT, 170, 2)

        moving = {}
        if self.swap:
            a, b, undo = self.swap
            t = min(1.0, self.timer / SWAP_TIME)
            t = t * t * (3 - 2 * t)
            (ax, ay), (bx, by) = self.center(a), self.center(b)
            moving[a] = (ax + (bx - ax) * t, ay + (by - ay) * t)
            moving[b] = (bx + (ax - bx) * t, by + (ay - by) * t)

        self.screen.set_clip(pygame.Rect(BOARD_X - 14 * U, BOARD_Y, BOARD + 28 * U, BOARD + 14 * U))
        hinted = self.hint if self.hint and self.phase == "idle" else ()
        for y in range(SIZE):
            for x in range(SIZE):
                kind = self.grid[y][x]
                if kind is None:
                    continue
                power = self.special[y][x]
                cx, cy = moving.get((x, y), self.center((x, y)))
                cy -= self.fall[y][x] * CELL
                scale = 1.0
                if (x, y) in self.popping:
                    t = self.timer / POP_TIME
                    scale = max(0.0, 1.2 - 1.2 * t * t) if t > 0.15 else 1 + t * 1.3
                elif (x, y) == self.selected:
                    scale = 1.07 + 0.04 * math.sin(self.time * 8)
                elif (x, y) in hinted:
                    scale = 1.0 + 0.05 * math.sin(self.time * 7)
                elif power == "bomb" or kind == COLOR_BOMB:
                    scale = 1.0 + 0.035 * math.sin(self.time * 5 + x + y)  # specials breathe
                if scale > 0:
                    self.draw_candy(self.sprite(kind, power), (cx, cy), scale)
        self.screen.set_clip(None)

        self.draw_effects()
        for x, y, age, color in self.rings:
            t = age / 0.35
            r = CELL * (0.25 + 0.45 * t)
            layer = pygame.Surface((round(r * 2 + 4), round(r * 2 + 4)), pygame.SRCALPHA)
            pygame.draw.circle(layer, (*mix(color, WHITE, 0.5), round(220 * (1 - t))),
                               (r + 2, r + 2), r, max(1, round(5 * U * (1 - t))))
            self.screen.blit(layer, (x - r - 2, y - r - 2))
        for x, y, _, _, age, color, spin in self.particles:
            self.draw_sparkle(x, y, (7 * (1 - age / 0.6) + 1) * U, color, spin + age * 6)
        for text, x, y, age in self.popups:
            if age < 0:
                continue
            alpha = 255 if age < 0.5 else round(255 * (1 - (age - 0.5) / 0.4))
            label = outlined(self.pop_font, text, WHITE, (255, 236, 170), EDGE, 3)
            label.set_alpha(alpha)
            self.screen.blit(label, label.get_rect(center=(x, y)))

    def draw_text(self, text, font, color, shadow=0, **position):
        if shadow:
            surface = font.render(text, True, (0, 0, 0))
            offset = round(shadow * U)
            self.screen.blit(surface, surface.get_rect(**position).move(offset, offset))
        surface = font.render(text, True, color)
        self.screen.blit(surface, surface.get_rect(**position))

    def draw_badge(self, center, label, value, color=WHITE):
        rect = pygame.Rect(0, 0, round(150 * U), round(52 * U))
        rect.center = center
        self.screen.blit(self.badge, self.badge.get_rect(center=rect.center))
        self.draw_text(label, self.label_font, TEXT_DIM, center=(rect.centerx, rect.top + 14 * U))
        self.draw_text(str(value), self.font, color, shadow=2, center=(rect.centerx, rect.top + 34 * U))

    def draw_hud(self):
        self.screen.blit(self.title, self.title.get_rect(center=(W // 2, 50 * U)))
        low = self.moves <= 5 and self.phase != "over"
        self.draw_badge((W // 2 - 165 * U, 122 * U), "SCORE", self.score)
        self.draw_badge((W // 2, 122 * U), "MOVES", self.moves, DANGER if low else WHITE)
        self.draw_badge((W // 2 + 165 * U, 122 * U), "BEST", self.best)

        self.draw_text("4 in a line = striped    2x2 = fish    L or T = bomb    5 in a line = colour bomb",
                       self.small_font, TEXT_DIM, center=(W // 2, H - 52 * U))
        self.draw_text("Click or drag to swap    Arrows + Space    H hint    R new game    Esc quit",
                       self.small_font, TEXT_DIM, center=(W // 2, H - 28 * U))

        center = (W // 2, BOARD_Y + BOARD // 2)
        if self.message:
            label = outlined(self.font, self.message[0], WHITE, WHITE, EDGE, 3)
            self.screen.blit(label, label.get_rect(center=center))
        if self.phase == "over":
            veil = pygame.Surface((W, H), pygame.SRCALPHA)
            veil.fill((6, 6, 14, 130))
            self.screen.blit(veil, (0, 0))
            card = pygame.Rect(0, 0, round(380 * U), round(210 * U))
            card.center = center
            slate_panel(self.screen, card, 20)
            heading = outlined(self.big_font, "Sweet!" if self.new_best else "Out of moves",
                               GOLD_TOP, GOLD_BOTTOM, EDGE, 4)
            self.screen.blit(heading, heading.get_rect(center=(center[0], card.top + 56 * U)))
            line = f"Score {self.score}" + ("  -  new best!" if self.new_best else f"    Best {self.best}")
            self.draw_text(line, self.font, WHITE, shadow=2, center=(center[0], card.top + 118 * U))
            self.draw_text("Press R to play again", self.small_font, TEXT_DIM,
                           center=(center[0], card.top + 166 * U))

    def draw(self):
        self.screen.blit(self.backdrop, (0, 0))
        self.draw_board()
        self.draw_hud()
        self.window.flip()

    # ── Input ───────────────────────────────────────────────────────────────
    def click(self, cell):
        if self.phase != "idle":
            return
        if self.selected and abs(self.selected[0] - cell[0]) + abs(self.selected[1] - cell[1]) == 1:
            self.try_swap(self.selected, cell)
        else:
            self.selected = None if self.selected == cell else cell

    def handle_key(self, key):
        if key == pygame.K_ESCAPE:
            return False
        if key == pygame.K_r:
            self.new_game()
        elif key == pygame.K_h and self.phase == "idle":
            self.hint = find_move(self.grid, self.special)
        elif key in STEPS and self.phase != "over":
            dx, dy = STEPS[key]
            self.show_cursor = True
            x, y = self.cursor[0] + dx, self.cursor[1] + dy
            if not (0 <= x < SIZE and 0 <= y < SIZE):
                return True
            if self.selected == self.cursor:
                self.try_swap(self.cursor, (x, y))
            self.cursor = (x, y)
        elif key == pygame.K_SPACE:
            self.show_cursor = True
            self.click(self.cursor)
        return True

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            return self.handle_key(event.key)
        if hasattr(event, "pos"):
            pos = (event.pos[0] * U, event.pos[1] * U)  # screen points to pixels
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            cell = self.cell_at(pos)
            if cell and self.phase == "idle":
                self.show_cursor = False
                self.cursor = cell
                self.click(cell)
                self.drag_from = (cell, pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.drag_from = None
        elif event.type == pygame.MOUSEMOTION and self.drag_from:
            (cx, cy), (sx, sy) = self.drag_from
            dx, dy = pos[0] - sx, pos[1] - sy
            if max(abs(dx), abs(dy)) > CELL * 0.45:
                step = (1 if dx > 0 else -1, 0) if abs(dx) > abs(dy) else (0, 1 if dy > 0 else -1)
                target = (cx + step[0], cy + step[1])
                self.drag_from = None
                if 0 <= target[0] < SIZE and 0 <= target[1] < SIZE:
                    self.try_swap((cx, cy), target)
        return True

    def run(self):
        running = True
        while running:
            dt = min(self.clock.tick(FPS) / 1000, 0.05)
            for event in pygame.event.get():
                running = self.handle_event(event) and running
            self.update(dt)
            self.draw()
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    CandySwap().run()
