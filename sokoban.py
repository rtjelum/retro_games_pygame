"""Sokoban -- pygame port of the web game the ESP32 serves at /sokoban.

Same isometric look as sokoban_page.h, and the same 50 levels, read straight
from sokoban_levels.h (which must sit next to this file).

Controls: arrows / WASD move, U or Z undo, R restart level,
          N / P next / previous level, Esc quit.
"""
import re
import sys
from pathlib import Path

import pygame

WIDTH, HEIGHT = 900, 700
HUD_H = 56
MARGIN = 20
MAX_TILE = 44
FPS = 60
WIN_DELAY_MS = 800
LEVEL_FILE = Path(__file__).with_name("sokoban_levels.h")

# Palette lifted from the web version
SKY = [(0.0, (126, 87, 194)), (0.55, (240, 98, 146)), (1.0, (255, 183, 77))]
FLOOR_A, FLOOR_B, FLOOR_EDGE = (225, 245, 254), (179, 229, 252), (79, 195, 247)
CLIFF_L, CLIFF_R = (141, 110, 99), (93, 64, 55)
WALL = ((255, 224, 130), (255, 183, 77), (251, 140, 0), (93, 64, 55))
BOX = ((165, 214, 167), (102, 187, 106), (56, 142, 60), (27, 94, 32))
BOX_DONE = ((255, 215, 0), (255, 193, 7), (255, 143, 0), (78, 52, 46))
GOAL_FILL, GOAL_EDGE = (248, 187, 208), (233, 30, 99)
SPARKLE = (255, 245, 157)
PAWN, PAWN_EDGE = (38, 198, 218), (0, 96, 100)
SKIN, SKIN_EDGE, EYE = (255, 224, 178), (93, 64, 55), (62, 39, 35)
TEXT, TEXT_DIM = (255, 213, 79), (255, 243, 224)

MOVES = {
    pygame.K_UP: (0, -1), pygame.K_w: (0, -1),
    pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1),
    pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0),
    pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0),
}


def load_levels(path=LEVEL_FILE):
    """Pulls the R"(...)" raw-string blocks out of the C header, one per level."""
    text = path.read_text()
    text = text[text.index("ZK_LEVEL_DATA"):]
    return [block.split("\n") for block in re.findall(r'R"\((.*?)\)"', text, re.S)]


def make_backdrop():
    """Sunset gradient, built one pixel wide and stretched."""
    strip = pygame.Surface((1, HEIGHT))
    for y in range(HEIGHT):
        t = y / (HEIGHT - 1)
        for (t0, c0), (t1, c1) in zip(SKY, SKY[1:]):
            if t <= t1:
                k = (t - t0) / (t1 - t0)
                strip.set_at((0, y), [round(a + (b - a) * k) for a, b in zip(c0, c1)])
                break
    return pygame.transform.scale(strip, (WIDTH, HEIGHT))


class Sokoban:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Sokoban")
        pygame.key.set_repeat(200, 90)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 22)
        self.big_font = pygame.font.Font(None, 72)
        self.backdrop = make_backdrop()
        self.levels = load_levels()
        self.cur = 0
        self.load(0)

    # ── Game state ──────────────────────────────────────────────────────────
    def load(self, index):
        self.cur = index % len(self.levels)
        self.map = [list(row) for row in self.levels[self.cur]]
        self.moves = 0
        self.history = []
        self.won_at = None
        for y, row in enumerate(self.map):
            for x, v in enumerate(row):
                if v in "@+":
                    self.px, self.py = x, y
                    row[x] = " " if v == "@" else "."
        self.mesa = self.find_mesa()
        self.fit()

    def cell(self, x, y):
        """Tile at (x, y), or None off the (ragged) grid."""
        if 0 <= y < len(self.map) and 0 <= x < len(self.map[y]):
            return self.map[y][x]
        return None

    def find_mesa(self):
        """Cells that get a floor tile: everything reachable from the player,
        plus interior walls. Perimeter walls and outside space are left out."""
        reach, stack = set(), [(self.px, self.py)]
        while stack:
            x, y = stack.pop()
            if (x, y) in reach or self.cell(x, y) in (None, "#"):
                continue
            reach.add((x, y))
            stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        mesa = set(reach)
        for y, row in enumerate(self.map):
            for x, v in enumerate(row):
                if v == "#" and all(
                    self.cell(nx, ny) == "#" or (nx, ny) in reach
                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                ):
                    mesa.add((x, y))
        return mesa

    def move(self, dx, dy):
        nx, ny = self.px + dx, self.py + dy
        t = self.cell(nx, ny)
        if t in ("$", "*"):
            bx, by = nx + dx, ny + dy
            bt = self.cell(bx, by)
            if bt not in (" ", "."):
                return
            self.snapshot()
            self.map[ny][nx] = " " if t == "$" else "."
            self.map[by][bx] = "$" if bt == " " else "*"
        elif t in (" ", "."):
            self.snapshot()
        else:
            return
        self.px, self.py = nx, ny
        self.moves += 1
        if not any("." in row for row in self.map):
            self.won_at = pygame.time.get_ticks()

    def snapshot(self):
        self.history.append(([row[:] for row in self.map], self.px, self.py))

    def undo(self):
        if self.history:
            self.map, self.px, self.py = self.history.pop()
            self.moves -= 1

    # ── Isometric rendering ─────────────────────────────────────────────────
    def fit(self):
        """Picks the tile size and origin so the level fills the window."""
        h = len(self.map)
        n = max(len(row) for row in self.map) + h
        avail_w, avail_h = WIDTH - 2 * MARGIN, HEIGHT - HUD_H - 2 * MARGIN
        # board height in tile-widths: n*0.58 floor + 1.2 headroom + 1.8 cliff
        self.tw = max(8, min(MAX_TILE, avail_w // n, int(avail_h / (n * 0.58 + 3))))
        self.th = round(self.tw * 0.58)
        self.wall_h = round(self.tw * 0.55)
        self.box_h = round(self.tw * 0.75)
        self.cliff_h = round(self.tw * 1.8)
        top_pad = round(self.tw * 1.2)
        board_w = n * self.tw
        board_h = n * self.th + top_pad + self.cliff_h
        self.off_x = (WIDTH - board_w) // 2 + h * self.tw
        self.off_y = HUD_H + MARGIN + (avail_h - board_h) // 2 + top_pad

    def iso(self, x, y):
        """Screen position of the top corner of tile (x, y)."""
        return (x - y) * self.tw + self.off_x, (x + y) * self.th + self.off_y

    def poly(self, points, fill, edge=None):
        pygame.draw.polygon(self.screen, fill, points)
        if edge:
            pygame.draw.polygon(self.screen, edge, points, 1)

    def draw_cube(self, x, y, ht, colors):
        top, left, right, edge = colors
        cx, cy = self.iso(x, y)
        tw, th = self.tw, self.th
        self.poly([(cx + tw, cy + th), (cx, cy + 2 * th),
                   (cx, cy + 2 * th - ht), (cx + tw, cy + th - ht)], right, edge)
        self.poly([(cx - tw, cy + th), (cx, cy + 2 * th),
                   (cx, cy + 2 * th - ht), (cx - tw, cy + th - ht)], left, edge)
        self.poly([(cx, cy - ht), (cx + tw, cy + th - ht),
                   (cx, cy + 2 * th - ht), (cx - tw, cy + th - ht)], top, edge)

    def draw_floor(self, x, y):
        cx, cy = self.iso(x, y)
        tw, th, ph = self.tw, self.th, self.cliff_h
        if (x + 1, y) not in self.mesa:
            self.poly([(cx + tw, cy + th), (cx, cy + 2 * th),
                       (cx, cy + 2 * th + ph), (cx + tw, cy + th + ph)], CLIFF_R)
        if (x, y + 1) not in self.mesa:
            self.poly([(cx - tw, cy + th), (cx, cy + 2 * th),
                       (cx, cy + 2 * th + ph), (cx - tw, cy + th + ph)], CLIFF_L)
        self.poly([(cx, cy), (cx + tw, cy + th), (cx, cy + 2 * th), (cx - tw, cy + th)],
                  FLOOR_A if (x + y) % 2 == 0 else FLOOR_B, FLOOR_EDGE)

    def ellipse(self, color, cx, cy, rx, ry, width=0):
        pygame.draw.ellipse(self.screen, color,
                            pygame.Rect(cx - rx, cy - ry, 2 * rx, 2 * ry), width)

    def draw_goal(self, x, y):
        cx, cy = self.iso(x, y)
        cy += self.th
        self.ellipse(GOAL_FILL, cx, cy, self.tw * 0.42, self.th * 0.62)
        self.ellipse(GOAL_EDGE, cx, cy, self.tw * 0.42, self.th * 0.62, 2)
        self.ellipse(GOAL_EDGE, cx, cy, self.tw * 0.16, self.th * 0.24)

    def draw_sparkle(self, x, y):
        cx, cy = self.iso(x, y)
        cy += self.th - self.box_h
        dx, dy = self.tw * 0.25, self.th * 0.4
        pygame.draw.line(self.screen, SPARKLE, (cx - dx, cy), (cx + dx, cy), 2)
        pygame.draw.line(self.screen, SPARKLE, (cx, cy - dy), (cx, cy + dy), 2)

    def draw_pawn(self, x, y):
        cx, cy = self.iso(x, y)
        cy += self.th
        tw, th = self.tw, self.th
        shadow = pygame.Surface((tw, th), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 90), shadow.get_rect())
        self.screen.blit(shadow, shadow.get_rect(center=(cx, cy + th * 0.6)))
        body_h = max(tw * 0.95, 18)
        self.ellipse(PAWN, cx, cy - body_h * 0.35, tw * 0.38, body_h * 0.55)
        self.ellipse(PAWN_EDGE, cx, cy - body_h * 0.35, tw * 0.38, body_h * 0.55, 2)
        hr = max(tw * 0.28, 5)
        head_y = cy - body_h * 0.95
        pygame.draw.circle(self.screen, SKIN, (cx, head_y), hr)
        pygame.draw.circle(self.screen, SKIN_EDGE, (cx, head_y), hr, 1)
        for side in (-1, 1):
            pygame.draw.circle(self.screen, EYE, (cx + side * hr * 0.4, head_y),
                               max(hr * 0.18, 1))

    def draw(self):
        self.screen.blit(self.backdrop, (0, 0))
        # Row-major order is back-to-front for this projection
        for y, row in enumerate(self.map):
            for x, v in enumerate(row):
                if (x, y) not in self.mesa:
                    continue
                self.draw_floor(x, y)
                if v == "#":
                    self.draw_cube(x, y, self.wall_h, WALL)
                elif v == ".":
                    self.draw_goal(x, y)
                elif v == "$":
                    self.draw_cube(x, y, self.box_h, BOX)
                elif v == "*":
                    self.draw_cube(x, y, self.box_h, BOX_DONE)
                    self.draw_sparkle(x, y)
                if (x, y) == (self.px, self.py):
                    self.draw_pawn(x, y)
        self.draw_hud()
        pygame.display.flip()

    def draw_hud(self):
        status = f"Level {self.cur + 1}/{len(self.levels)}    Moves: {self.moves}"
        self.screen.blit(self.font.render(status, True, TEXT), (MARGIN, 16))
        tips = self.small_font.render(
            "Arrows/WASD move   U undo   R restart   N/P level   Esc quit", True, TEXT_DIM)
        self.screen.blit(tips, tips.get_rect(topright=(WIDTH - MARGIN, 22)))
        if self.won_at is not None:
            last = self.cur == len(self.levels) - 1
            msg = "All levels cleared!" if last else "Level cleared!"
            for color, offset in (((62, 39, 35), 3), (TEXT, 0)):
                text = self.big_font.render(msg, True, color)
                self.screen.blit(text, text.get_rect(
                    center=(WIDTH // 2 + offset, HEIGHT // 2 + offset)))

    # ── Main loop ───────────────────────────────────────────────────────────
    def handle_key(self, key):
        if key == pygame.K_ESCAPE:
            return False
        if self.won_at is not None:
            return True
        if key in MOVES:
            self.move(*MOVES[key])
        elif key in (pygame.K_u, pygame.K_z):
            self.undo()
        elif key == pygame.K_r:
            self.load(self.cur)
        elif key == pygame.K_n:
            self.load(self.cur + 1)
        elif key == pygame.K_p:
            self.load(self.cur - 1)
        return True

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    running = self.handle_key(event.key) and running
            if (self.won_at is not None
                    and pygame.time.get_ticks() - self.won_at >= WIN_DELAY_MS):
                self.load(self.cur + 1)  # wraps back to level 1 after the last
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    Sokoban().run()
