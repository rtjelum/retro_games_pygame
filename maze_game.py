"""Castle Maze -- guide the knight through the castle to slay the dragon.

Every maze is randomly generated and has exactly one route between any two
cells. A trail marks the path you've taken; step back along it to rub it out.

Controls: arrow keys / WASD to move (hold to keep going).
          1 / 2 / 3 difficulty, N or R new maze, H show the way, Esc quit.
"""
import math
import random
import sys
from collections import deque

import pygame

WIDTH, HEIGHT = 760, 700
FPS = 60
BOARD_W, BOARD_H = 640, 540
BOARD_TOP = 92
FRAME = 18   # thickness of the battlements around the board
SPEED = 9    # cells per second while walking

# (name, columns, rows)
DIFFICULTIES = [("Easy", 12, 9), ("Medium", 20, 15), ("Hard", 32, 24)]

SKY_TOP, SKY_BOTTOM = (24, 26, 54), (8, 8, 18)
STONE, MORTAR = (128, 120, 108), (44, 40, 38)
FLOOR, FLOOR_MORTAR = (62, 56, 52), (40, 36, 34)
TOWER_TOP = (88, 82, 76)
TRAIL, HINT = (170, 135, 75), (255, 214, 100)
OUTLINE = (24, 20, 26)
STEEL, STEEL_LIGHT, STEEL_DARK = (170, 178, 192), (208, 214, 224), (92, 98, 110)
BLUE, RED, GOLD, BROWN = (45, 85, 175), (180, 38, 45), (232, 190, 70), (88, 60, 42)
SCALES, SCALES_DARK, BELLY = (82, 160, 70), (40, 96, 46), (226, 206, 122)
WING, HORN = (58, 118, 62), (236, 226, 196)
TEXT, TEXT_DIM, WHITE = (240, 200, 100), (205, 195, 175), (255, 255, 255)

STEPS = {"N": (0, -1), "S": (0, 1), "W": (-1, 0), "E": (1, 0)}
KEYS = {pygame.K_UP: "N", pygame.K_w: "N", pygame.K_DOWN: "S", pygame.K_s: "S",
        pygame.K_LEFT: "W", pygame.K_a: "W", pygame.K_RIGHT: "E", pygame.K_d: "E"}
OPPOSITE = {"N": "S", "S": "N", "W": "E", "E": "W"}

FIRE_EVERY, FIRE_FOR = 3.0, 0.9  # seconds between the dragon's breaths, and their length


# ── Maze generation ─────────────────────────────────────────────────────────
def generate_maze(cols, rows):
    """Returns {cell: set of open directions}, carved by a randomised depth-first search."""
    open_sides = {(x, y): set() for x in range(cols) for y in range(rows)}
    stack, seen = [(0, 0)], {(0, 0)}
    while stack:
        x, y = stack[-1]
        options = [(d, (x + dx, y + dy)) for d, (dx, dy) in STEPS.items()
                   if (x + dx, y + dy) in open_sides and (x + dx, y + dy) not in seen]
        if not options:
            stack.pop()
            continue
        d, nxt = random.choice(options)
        open_sides[(x, y)].add(d)
        open_sides[nxt].add(OPPOSITE[d])
        seen.add(nxt)
        stack.append(nxt)
    return open_sides


def solve(maze, start, goal):
    """The cells from start to goal, found with a breadth-first search."""
    came_from = {start: None}
    queue = deque([start])
    while queue:
        cell = queue.popleft()
        if cell == goal:
            break
        for d in maze[cell]:
            dx, dy = STEPS[d]
            nxt = (cell[0] + dx, cell[1] + dy)
            if nxt not in came_from:
                came_from[nxt] = cell
                queue.append(nxt)
    path, cell = [], goal
    while cell is not None:
        path.append(cell)
        cell = came_from[cell]
    return path[::-1]


def wall_runs(maze, cols, rows):
    """The walls as long straight runs, in cell units: (x0, y0, x1, y1)."""
    runs = []
    for y in range(rows + 1):  # horizontal grid lines
        start = None
        for x in range(cols + 1):
            wall = x < cols and ("N" not in maze[(x, y)] if y < rows
                                 else "S" not in maze[(x, y - 1)])
            if wall and start is None:
                start = x
            elif not wall and start is not None:
                runs.append((start, y, x, y))
                start = None
    for x in range(cols + 1):  # vertical grid lines
        start = None
        for y in range(rows + 1):
            wall = y < rows and ("W" not in maze[(x, y)] if x < cols
                                 else "E" not in maze[(x - 1, y)])
            if wall and start is None:
                start = y
            elif not wall and start is not None:
                runs.append((x, start, x, y))
                start = None
    return runs


# ── Stonework ───────────────────────────────────────────────────────────────
def shade(color, amount):
    return tuple(max(0, min(255, c + amount)) for c in color)


def draw_stone(surface, rect, rng, base=STONE):
    """One block of stone with a lit top-left edge and a shadowed bottom-right."""
    rect = pygame.Rect(rect)
    if rect.width < 2 or rect.height < 2:
        return
    v = rng.randint(-16, 16)
    color = (base[0] + v, base[1] + v, base[2] + v + rng.randint(-4, 4))
    pygame.draw.rect(surface, color, rect)
    pygame.draw.line(surface, shade(color, 34), rect.topleft, (rect.right - 1, rect.top))
    pygame.draw.line(surface, shade(color, 22), rect.topleft, (rect.left, rect.bottom - 1))
    pygame.draw.line(surface, shade(color, -42), (rect.left, rect.bottom - 1),
                     (rect.right - 1, rect.bottom - 1))
    pygame.draw.line(surface, shade(color, -30), (rect.right - 1, rect.top),
                     (rect.right - 1, rect.bottom - 1))
    for _ in range(rect.width * rect.height // 40):  # pits and speckles
        x = rng.randint(rect.left + 1, max(rect.left + 1, rect.right - 2))
        y = rng.randint(rect.top + 1, max(rect.top + 1, rect.bottom - 2))
        surface.set_at((x, y), shade(color, rng.choice((-26, -18, 14))))


def fill_bricks(surface, rect, rng, brick_h=8):
    """Courses of staggered bricks filling a rectangle."""
    rect = pygame.Rect(rect)
    pygame.draw.rect(surface, MORTAR, rect)
    clip = surface.get_clip()
    surface.set_clip(rect)
    for row, y in enumerate(range(rect.top, rect.bottom, brick_h)):
        x = rect.left - (rng.randint(4, 14) if row % 2 else 0)
        while x < rect.right:
            w = rng.randint(14, 26)
            draw_stone(surface, (x + 1, y + 1, w - 1, brick_h - 1), rng)
            x += w
    surface.set_clip(clip)


def blur(surface, amount):
    w, h = surface.get_size()
    small = pygame.transform.smoothscale(surface, (max(1, w // amount), max(1, h // amount)))
    return pygame.transform.smoothscale(small, (w, h))


# ── Sprites ─────────────────────────────────────────────────────────────────
class Pen:
    """Draws on a 100 x 100 grid, four times oversize, then shrinks for smooth edges."""
    SCALE = 4

    def __init__(self, size):
        self.size = size
        self.k = size * self.SCALE / 100
        self.surface = pygame.Surface((size * self.SCALE, size * self.SCALE), pygame.SRCALPHA)
        self.edge = max(1, round(self.k * 2.2))

    def p(self, x, y):
        return x * self.k, y * self.k

    def r(self, x, y, w, h):
        return pygame.Rect(round(x * self.k), round(y * self.k), round(w * self.k), round(h * self.k))

    def poly(self, color, points, outline=True):
        points = [self.p(*q) for q in points]
        pygame.draw.polygon(self.surface, color, points)
        if outline:
            pygame.draw.polygon(self.surface, OUTLINE, points, self.edge)

    def rect(self, color, x, y, w, h, radius=0, outline=True):
        r, rad = self.r(x, y, w, h), round(radius * self.k)
        pygame.draw.rect(self.surface, color, r, border_radius=rad)
        if outline:
            pygame.draw.rect(self.surface, OUTLINE, r, self.edge, border_radius=rad)

    def ellipse(self, color, x, y, w, h, outline=True):
        r = self.r(x, y, w, h)
        pygame.draw.ellipse(self.surface, color, r)
        if outline:
            pygame.draw.ellipse(self.surface, OUTLINE, r, self.edge)

    def circle(self, color, x, y, radius, outline=True):
        pygame.draw.circle(self.surface, color, self.p(x, y), radius * self.k)
        if outline:
            pygame.draw.circle(self.surface, OUTLINE, self.p(x, y), radius * self.k, self.edge)

    def stroke(self, color, points, width, outline=True):
        """A thick line with rounded joints."""
        for c, w in ([(OUTLINE, width * self.k + 2 * self.edge)] if outline else []) + [
                (color, width * self.k)]:
            pts = [self.p(*q) for q in points]
            pygame.draw.lines(self.surface, c, False, pts, round(w))
            for q in pts:
                pygame.draw.circle(self.surface, c, q, w / 2)

    def done(self):
        return pygame.transform.smoothscale(self.surface, (self.size, self.size))


def make_knight(size):
    """A knight facing right: plumed helm, blue tabard, red shield, sword held up."""
    pen = Pen(size)
    pen.ellipse((0, 0, 0, 80), 22, 84, 58, 12, outline=False)
    # Sword, held up behind the body
    pen.poly(STEEL_LIGHT, [(26, 58), (31, 58), (31, 14), (28.5, 8), (26, 14)])
    pen.rect(GOLD, 21, 55, 15, 4.5, 2)
    pen.rect(BROWN, 26.5, 59, 4, 8)
    pen.circle(GOLD, 28.5, 69, 2.8)
    # Legs and boots
    pen.rect(STEEL_DARK, 38, 70, 9, 16)
    pen.rect(STEEL_DARK, 53, 70, 9, 16)
    pen.rect(BROWN, 35, 83, 13, 6, 2)
    pen.rect(BROWN, 52, 83, 14, 6, 2)
    # Body, tabard and belt
    pen.rect(STEEL, 33, 42, 34, 32, 8)
    pen.poly(BLUE, [(40, 44), (60, 44), (62, 77), (38, 77)])
    pen.rect(GOLD, 48, 48, 4, 24, outline=False)
    pen.rect(GOLD, 43, 54, 14, 4, outline=False)
    pen.rect(BROWN, 35, 63, 30, 4.5)
    # Sword hand
    pen.circle(STEEL, 28.5, 61, 5)
    # Plume and helmet
    pen.circle(RED, 41, 12, 7)
    pen.circle(RED, 33, 14, 6)
    pen.circle(RED, 26, 19, 5)
    pen.rect(STEEL_LIGHT, 35, 14, 30, 30, 12)
    pen.rect((32, 32, 42), 50, 25, 14, 4.5, outline=False)
    pen.rect(WHITE, 39, 18, 4, 10, 2, outline=False)
    # Shield
    pen.poly(RED, [(55, 46), (80, 46), (80, 62), (67.5, 79), (55, 62)])
    pen.rect(GOLD, 65.5, 50, 4, 22, outline=False)
    pen.rect(GOLD, 59, 56, 17, 4, outline=False)
    return pen.done()


def make_dragon(size, flap):
    """A green dragon facing left; `flap` runs from wings up (0) to wings down (1)."""
    pen = Pen(size)
    pen.ellipse((0, 0, 0, 80), 14, 82, 76, 14, outline=False)

    def wing(sx, sy, color, shift=0):
        tips = [(sx + 8 + shift, 4 + 26 * flap), (sx + 30 + shift, 10 + 24 * flap),
                (sx + 42 + shift, 32 + 14 * flap)]
        pen.poly(color, [(sx, sy)] + tips + [(sx + 20, sy + 6)])
        for tip in tips:
            pen.stroke(SCALES_DARK, [(sx, sy), tip], 2.4, outline=False)

    wing(50, 47, SCALES_DARK, -8)                       # far wing, behind the body
    pen.stroke(SCALES, [(68, 70), (84, 74), (94, 62), (92, 47)], 7)  # tail
    pen.poly(SCALES, [(92, 48), (85, 41), (93, 32), (99, 43)])
    for x in (44, 53, 62, 71):                          # spikes along the back
        pen.poly(HORN, [(x, 49), (x + 4, 38), (x + 8, 49)])
    pen.rect(SCALES_DARK, 63, 68, 10, 16, 3)            # back leg
    pen.ellipse(SCALES, 34, 44, 46, 36)                 # body
    pen.ellipse(BELLY, 38, 58, 28, 20)
    for y in (63, 68, 73):
        pen.stroke(shade(BELLY, -40), [(43, y), (61, y)], 1.2, outline=False)
    pen.rect(SCALES, 42, 70, 10, 15, 3)                 # front leg
    for x in (42, 46, 50):
        pen.poly(HORN, [(x, 85), (x + 2, 89), (x + 4, 85)], outline=False)
    pen.poly(HORN, [(23, 27), (35, 11), (30, 28)])      # horns
    pen.poly(HORN, [(29, 28), (43, 17), (35, 31)])
    pen.poly(SCALES, [(40, 60), (49, 48), (30, 31), (19, 40)])  # neck
    pen.ellipse(SCALES, 7, 24, 30, 20)                  # head
    pen.ellipse(SCALES, 0, 30, 18, 12)                  # snout
    pen.circle(OUTLINE, 4.5, 34, 1.3, outline=False)
    pen.stroke(OUTLINE, [(2, 38.5), (15, 38.5)], 1, outline=False)
    pen.circle((255, 222, 60), 22, 31, 3.8)             # eye
    pen.rect(OUTLINE, 21.2, 28, 1.8, 6, outline=False)
    wing(56, 50, WING)                                  # near wing
    return pen.done()


# ── Game ────────────────────────────────────────────────────────────────────
def make_backdrop():
    strip = pygame.Surface((1, HEIGHT))
    for y in range(HEIGHT):
        t = y / (HEIGHT - 1)
        strip.set_at((0, y), [round(a + (b - a) * t) for a, b in zip(SKY_TOP, SKY_BOTTOM)])
    sky = pygame.transform.scale(strip, (WIDTH, HEIGHT))
    rng = random.Random(7)
    for _ in range(140):
        x, y = rng.randrange(WIDTH), rng.randrange(HEIGHT)
        level = rng.randint(70, 200) * (1 - y / HEIGHT * 0.7)
        sky.set_at((x, y), (level, level, min(255, level + 20)))
    return sky


def format_time(seconds):
    return f"{int(seconds // 60)}:{seconds % 60:04.1f}"


class MazeGame:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Castle Maze")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("georgia", 28, bold=True)
        self.small_font = pygame.font.Font(None, 22)
        self.big_font = pygame.font.SysFont("georgia", 64, bold=True)
        self.backdrop = make_backdrop()
        self.difficulty = 0
        self.best = {}  # difficulty -> best time this session
        self.held = []  # direction keys currently held, most recent last
        self.clock_time = 0.0
        self.new_maze()

    # ── Game state ──────────────────────────────────────────────────────────
    def new_maze(self):
        _, self.cols, self.rows = DIFFICULTIES[self.difficulty]
        self.cell = min(BOARD_W // self.cols, BOARD_H // self.rows)
        self.board_x = (WIDTH - self.cols * self.cell) // 2
        self.board_y = BOARD_TOP + (BOARD_H - self.rows * self.cell) // 2
        self.maze = generate_maze(self.cols, self.rows)
        self.goal = (self.cols - 1, self.rows - 1)
        self.player = (0, 0)
        self.target = None     # the cell being walked towards
        self.progress = 0.0    # 0..1 along the step
        self.queued = None     # a direction tapped mid-step
        self.facing = 1        # 1 = right, -1 = left
        self.trail = [(0, 0)]
        self.moves = 0
        self.elapsed = 0.0
        self.started = False
        self.hint = None
        self.fire = []         # [x, y, vx, vy, age, lifetime] flame puffs
        self.state = "playing"  # playing / won
        self.make_sprites()
        self.walls = self.render_castle()

    def make_sprites(self):
        knight = make_knight(round(self.cell * 1.15))
        self.knight = {1: knight, -1: pygame.transform.flip(knight, True, False)}
        size = round(self.cell * 1.55)
        self.dragon = [make_dragon(size, f) for f in (0, 0.33, 0.66, 1)]
        slain = pygame.transform.rotate(self.dragon[2], -100)
        slain.fill((150, 150, 150, 255), special_flags=pygame.BLEND_RGBA_MULT)
        self.dragon_slain = slain

    def try_move(self, d):
        if d not in self.maze[self.player]:
            return False
        dx, dy = STEPS[d]
        self.target = (self.player[0] + dx, self.player[1] + dy)
        self.progress = 0.0
        self.started = True
        if dx:
            self.facing = dx
        return True

    def arrive(self):
        self.player, self.target = self.target, None
        self.moves += 1
        if len(self.trail) > 1 and self.trail[-2] == self.player:
            self.trail.pop()  # stepping back rubs out the trail
        else:
            self.trail.append(self.player)
        if self.hint and self.player in self.hint:
            self.hint = self.hint[self.hint.index(self.player):]
        if self.player == self.goal:
            self.state = "won"
            name = DIFFICULTIES[self.difficulty][0]
            self.new_best = name not in self.best or self.elapsed < self.best[name]
            if self.new_best:
                self.best[name] = self.elapsed

    def update(self, dt):
        self.clock_time += dt
        self.update_fire(dt)
        if self.state != "playing":
            return
        if self.started:
            self.elapsed += dt
        if self.target:
            self.progress += SPEED * dt
            if self.progress >= 1:
                self.arrive()
        if self.target is None and self.state == "playing":
            # A tap during the step wins; otherwise keep going while a key is held
            for d in ([self.queued] if self.queued else []) + self.held[::-1]:
                if self.try_move(d):
                    break
            self.queued = None

    def update_fire(self, dt):
        for puff in self.fire:
            puff[0] += puff[2] * dt
            puff[1] += puff[3] * dt
            puff[4] += dt
        self.fire = [p for p in self.fire if p[4] < p[5]]
        if self.state == "playing" and self.clock_time % FIRE_EVERY < FIRE_FOR:
            mx, my = self.dragon_mouth()
            for _ in range(2):
                self.fire.append([mx, my, -random.uniform(2.2, 3.4) * self.cell,
                                  random.uniform(-0.5, 0.5) * self.cell,
                                  0.0, random.uniform(0.35, 0.6)])

    # ── Drawing ─────────────────────────────────────────────────────────────
    def center(self, cell):
        return (self.board_x + (cell[0] + 0.5) * self.cell,
                self.board_y + (cell[1] + 0.5) * self.cell)

    def dragon_rect(self):
        rect = self.dragon[0].get_rect()
        gx, _ = self.center(self.goal)
        rect.midbottom = (gx + self.cell * 0.05, self.board_y + self.rows * self.cell + self.cell * 0.05)
        return rect

    def dragon_mouth(self):
        rect = self.dragon_rect()
        return rect.left + rect.width * 0.02, rect.top + rect.height * 0.36

    def render_castle(self):
        """Draws the battlements, floor and stone walls once per maze; they never change."""
        rng = random.Random()
        surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        c = self.cell
        board = pygame.Rect(self.board_x, self.board_y, self.cols * c, self.rows * c)
        frame = board.inflate(2 * FRAME, 2 * FRAME)

        # Battlements, with a soft shadow beneath them
        shadow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 170), frame.inflate(16, 16).move(4, 8), border_radius=20)
        surface.blit(blur(shadow, 6), (0, 0))
        fill_bricks(surface, frame, rng)
        merlon = 12
        for x in range(frame.left + 30, frame.right - 40, merlon * 2):
            draw_stone(surface, (x, frame.top - 7, merlon, 8), rng)
            draw_stone(surface, (x, frame.bottom - 1, merlon, 8), rng)
        for y in range(frame.top + 30, frame.bottom - 40, merlon * 2):
            draw_stone(surface, (frame.left - 7, y, 8, merlon), rng)
            draw_stone(surface, (frame.right - 1, y, 8, merlon), rng)
        for corner, flag in ((frame.topleft, RED), (frame.topright, BLUE),
                             (frame.bottomleft, BLUE), (frame.bottomright, RED)):
            self.draw_tower(surface, corner, rng, flag)

        # Flagstone floor
        pygame.draw.rect(surface, FLOOR_MORTAR, board)
        for x in range(self.cols):
            for y in range(self.rows):
                x0, y0 = board.left + x * c, board.top + y * c
                slabs = [(x0, y0, c, c)]
                if c >= 40:
                    h = c // 2
                    slabs = ([(x0, y0, c, h), (x0, y0 + h, c, c - h)] if rng.random() < 0.5
                             else [(x0, y0, h, c), (x0 + h, y0, c - h, c)])
                for sx, sy, sw, sh in slabs:
                    v = rng.randint(-7, 7)
                    pygame.draw.rect(surface, shade(FLOOR, v), (sx + 1, sy + 1, sw - 1, sh - 1))

        # Stone walls: shadows first, then blocks along each run, then pillars where they meet
        runs = wall_runs(self.maze, self.cols, self.rows)
        t = max(6, round(c * 0.3))
        p = t + max(2, t // 4)
        pillars = self.pillar_points(runs)

        def run_rect(x0, y0, x1, y1):
            return pygame.Rect(board.left + x0 * c - t // 2, board.top + y0 * c - t // 2,
                               (x1 - x0) * c + t, (y1 - y0) * c + t)

        shadow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        offset = (round(t * 0.35), round(t * 0.55))
        for run in runs:
            pygame.draw.rect(shadow, (0, 0, 0, 150), run_rect(*run).move(offset))
        surface.blit(blur(shadow, 2), (0, 0))

        for x0, y0, x1, y1 in runs:
            rect = run_rect(x0, y0, x1, y1)
            pygame.draw.rect(surface, OUTLINE, rect.inflate(2, 2))
            pygame.draw.rect(surface, MORTAR, rect)
            horizontal = y0 == y1
            # Stones run straight on between pillars, cut to roughly even lengths
            if horizontal:
                anchors = [x for x in range(x0, x1 + 1) if (x, y0) in pillars]
            else:
                anchors = [y for y in range(y0, y1 + 1) if (x0, y) in pillars]
            for first, last in zip(anchors, anchors[1:]):
                a, b = first * c + p / 2 + 1, last * c - p / 2 - 1
                pieces = max(1, round((b - a) / (t * 1.6)))
                cuts = [a] + [a + (b - a) * (i + rng.uniform(-0.2, 0.2)) / pieces
                              for i in range(1, pieces)] + [b]
                for u, v in zip(cuts, cuts[1:]):
                    if horizontal:
                        stone = (board.left + u, rect.top + 1, v - u - 1, t - 2)
                    else:
                        stone = (rect.left + 1, board.top + u, t - 2, v - u - 1)
                    draw_stone(surface, [round(n) for n in stone], rng)
        for x, y in pillars:
            px, py = board.left + x * c - p // 2, board.top + y * c - p // 2
            pygame.draw.rect(surface, OUTLINE, (px - 1, py - 1, p + 2, p + 2))
            draw_stone(surface, (px, py, p, p), rng, shade(STONE, 6))
        return surface

    @staticmethod
    def pillar_points(runs):
        """Grid points where walls end, turn or meet; a straight pass-through needs none."""
        sides = {}
        for x0, y0, x1, y1 in runs:
            if y0 == y1:
                for x in range(x0, x1):
                    sides.setdefault((x, y0), set()).add("E")
                    sides.setdefault((x + 1, y0), set()).add("W")
            else:
                for y in range(y0, y1):
                    sides.setdefault((x0, y), set()).add("S")
                    sides.setdefault((x0, y + 1), set()).add("N")
        return {point for point, d in sides.items() if d not in ({"E", "W"}, {"N", "S"})}

    def draw_tower(self, surface, center, rng, flag):
        r = 28
        cx, cy = center
        pygame.draw.circle(surface, OUTLINE, center, r + 2)
        pygame.draw.circle(surface, shade(STONE, -38), center, r)      # gaps between merlons
        for i in range(10):
            angle = i * math.pi / 5
            x, y = cx + math.cos(angle) * (r - 5), cy + math.sin(angle) * (r - 5)
            draw_stone(surface, (round(x - 5), round(y - 5), 10, 10), rng, shade(STONE, 16))
        pygame.draw.circle(surface, OUTLINE, center, r - 10)
        pygame.draw.circle(surface, TOWER_TOP, center, r - 11)
        # A pennant on a pole
        pygame.draw.line(surface, OUTLINE, (cx, cy + 4), (cx, cy - 22), 3)
        pygame.draw.line(surface, GOLD, (cx, cy + 3), (cx, cy - 21), 1)
        pennant = [(cx + 1, cy - 22), (cx + 19, cy - 17), (cx + 1, cy - 11)]
        pygame.draw.polygon(surface, flag, pennant)
        pygame.draw.polygon(surface, OUTLINE, pennant, 1)
        pygame.draw.circle(surface, GOLD, (cx, cy - 23), 2)

    def draw_path(self, points, color, width):
        """Joins points (always in straight lines across or down) with rounded strips."""
        if len(points) == 1:
            points = points * 2
        half = width / 2
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            left, top = min(ax, bx) - half, min(ay, by) - half
            rect = (round(left), round(top), round(abs(bx - ax) + width), round(abs(by - ay) + width))
            pygame.draw.rect(self.screen, color, rect, border_radius=round(half))

    def draw_fire(self):
        for x, y, _, _, age, life in self.fire:
            t = age / life
            radius = self.cell * (0.07 + 0.2 * t)
            if t < 0.35:
                color = (255, 235, 140)
            elif t < 0.7:
                color = (255, 140, 40)
            else:
                color = (190, 50, 25)
            fade = 1 - t
            puff = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(puff, [round(ch * fade) for ch in color], (radius + 1, radius + 1), radius)
            self.screen.blit(puff, (x - radius - 1, y - radius - 1), special_flags=pygame.BLEND_RGB_ADD)

    def draw_board(self):
        self.screen.blit(self.walls, (0, 0))
        if self.hint:
            self.draw_path([self.center(c) for c in self.hint], HINT, max(2, self.cell // 9))

        # Trail, ending at wherever the knight is mid-step
        px, py = self.center(self.player)
        if self.target:
            tx, ty = self.center(self.target)
            t = min(self.progress, 1)
            px, py = px + (tx - px) * t, py + (ty - py) * t
        trail = [self.center(c) for c in self.trail] + [(px, py)]
        self.draw_path(trail, TRAIL, max(2, self.cell // 8))

        # The dragon, flapping in its lair
        rect = self.dragon_rect()
        if self.state == "won":
            slain = self.dragon_slain.get_rect(center=(rect.centerx, rect.centery + self.cell * 0.15))
            self.screen.blit(self.dragon_slain, slain)
        else:
            beat = (math.sin(self.clock_time * 6) + 1) / 2
            self.screen.blit(self.dragon[min(3, int(beat * 4))], rect)
        self.draw_fire()

        # The knight, bobbing while walking
        bob = abs(math.sin(self.progress * math.pi)) * self.cell * 0.08 if self.target else 0
        knight = self.knight[self.facing]
        self.screen.blit(knight, knight.get_rect(midbottom=(px, py + self.cell * 0.45 - bob)))

    def draw_text(self, text, font, color, shadow=0, **position):
        if shadow:
            surface = font.render(text, True, (0, 0, 0))
            self.screen.blit(surface, surface.get_rect(**position).move(shadow, shadow))
        surface = font.render(text, True, color)
        self.screen.blit(surface, surface.get_rect(**position))

    def draw_hud(self):
        name = DIFFICULTIES[self.difficulty][0]
        left = (WIDTH - BOARD_W) // 2 - FRAME
        self.draw_text(f"Castle Maze  -  {name}", self.font, TEXT, shadow=2, midleft=(left, 38))
        best = self.best.get(name)
        stats = f"Time {format_time(self.elapsed)}    Moves {self.moves}"
        if best is not None:
            stats += f"    Best {format_time(best)}"
        self.draw_text(stats, self.small_font, TEXT_DIM, midright=(WIDTH - left, 40))
        self.draw_text("Arrows / WASD move   1/2/3 difficulty   N new maze   H show the way   Esc quit",
                       self.small_font, TEXT_DIM, center=(WIDTH // 2, HEIGHT - 26))

        if self.state == "won":
            veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            veil.fill((8, 6, 14, 140))
            self.screen.blit(veil, (0, 0))
            cx, cy = WIDTH // 2, BOARD_TOP + BOARD_H // 2
            self.draw_text("Dragon slain!", self.big_font, TEXT, shadow=4, center=(cx, cy - 30))
            line = f"{format_time(self.elapsed)}  in  {self.moves} moves"
            if self.new_best:
                line += "  -  new best!"
            self.draw_text(line, self.font, WHITE, shadow=2, center=(cx, cy + 30))
            self.draw_text("Enter = new maze   1/2/3 = change difficulty", self.small_font,
                           TEXT_DIM, shadow=2, center=(cx, cy + 68))

    def draw(self):
        self.screen.blit(self.backdrop, (0, 0))
        self.draw_board()
        self.draw_hud()
        pygame.display.flip()

    # ── Main loop ───────────────────────────────────────────────────────────
    def handle_key(self, key):
        if key == pygame.K_ESCAPE:
            return False
        if key in (pygame.K_1, pygame.K_2, pygame.K_3):
            self.difficulty = key - pygame.K_1
            self.new_maze()
        elif key in (pygame.K_n, pygame.K_r) or (
                self.state == "won" and key in (pygame.K_RETURN, pygame.K_KP_ENTER)):
            self.new_maze()
        elif key == pygame.K_h and self.state == "playing":
            self.hint = None if self.hint else solve(self.maze, self.target or self.player, self.goal)
        elif key in KEYS:
            d = KEYS[key]
            if d in self.held:
                self.held.remove(d)
            self.held.append(d)
            if self.state == "playing":
                if self.target is None:
                    self.try_move(d)
                else:
                    self.queued = d
        return True

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            return self.handle_key(event.key)
        if event.type == pygame.KEYUP and event.key in KEYS and KEYS[event.key] in self.held:
            self.held.remove(KEYS[event.key])
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
    MazeGame().run()
