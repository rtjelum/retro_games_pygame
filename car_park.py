"""Car Park -- slide the cars out of the way and get the red one to the exit.

Cars and trucks only move along their own length. Every puzzle is generated
on the spot: a random jam is laid out, every position reachable from it is
searched, and one that needs the right number of moves is picked.

Controls: drag a vehicle, or pick it with a click or Tab and use the arrow
          keys (Shift+Tab goes back through them).
          1 / 2 / 3 difficulty, N new puzzle, R restart (a new puzzle once
          solved), U or Z undo, H hint, Esc quit.
"""
import random
import sys
from collections import deque, namedtuple

import pygame

WIDTH, HEIGHT = 600, 690
FPS = 60
SIZE = 6            # the car park is SIZE x SIZE cells
EXIT_ROW = 2
CELL = 80
PAD = 7             # gap between a vehicle and the edge of its cells
FRAME = 12
BOARD = SIZE * CELL
BOARD_X, BOARD_Y = (WIDTH - BOARD) // 2, 92
EXIT_SPEED = 900    # pixels per second, once solved

# (name, fewest moves needed to solve, vehicles besides the red car), as ranges
DIFFICULTIES = [("Easy", (5, 9), (7, 10)),
                ("Medium", (10, 14), (9, 12)),
                ("Hard", (15, 99), (11, 13))]
MIN_MOVABLE = 3     # vehicles that must be free to slide at the start
TRUCK_CHANCE = 0.3
MAX_STATES = 6000   # jams with more reachable positions than this are skipped

BG_TOP, BG_BOTTOM = (44, 48, 62), (18, 19, 26)
FRAME_COLOR = (112, 100, 92)
ASPHALT, DOT = (58, 61, 68), (84, 88, 96)
RED = (228, 60, 60)
COLORS = [(66, 133, 244), (240, 240, 235), (38, 166, 154), (255, 179, 0),
          (126, 87, 194), (150, 155, 165), (121, 85, 72), (102, 187, 106),
          (236, 112, 160), (52, 60, 72), (0, 172, 193), (255, 138, 60),
          (175, 180, 43)]
GLASS = (32, 44, 60)
HEADLIGHT, TAILLIGHT = (255, 244, 180), (200, 30, 30)
TEXT, TEXT_DIM = (255, 213, 79), (200, 204, 212)
SELECT, HINT = (255, 255, 255), (96, 220, 120)

# A vehicle slides along its row (horizontal) or column; `line` is which one.
# A board position is a tuple with each vehicle's distance along its line.
Vehicle = namedtuple("Vehicle", "horizontal line length")


# ── Puzzle logic ────────────────────────────────────────────────────────────
def cells(vehicle, pos):
    if vehicle.horizontal:
        return [(pos + i, vehicle.line) for i in range(vehicle.length)]
    return [(vehicle.line, pos + i) for i in range(vehicle.length)]


def make_masks(vehicles):
    """For each vehicle, the cells it covers at each position, as a bitmask.

    The search below looks at thousands of positions, and bitmasks make
    checking for a free cell cheap.
    """
    return [[sum(1 << (x + y * SIZE) for x, y in cells(vehicle, pos))
             for pos in range(SIZE - vehicle.length + 1)]
            for vehicle in vehicles]


def moves_from(masks, state):
    """Every (vehicle index, new position) reachable in one slide."""
    taken = 0
    for mask, pos in zip(masks, state):
        taken |= mask[pos]
    for i, mask in enumerate(masks):
        others = taken ^ mask[state[i]]
        for step in (-1, 1):
            pos = state[i] + step
            while 0 <= pos < len(mask) and not mask[pos] & others:
                yield i, pos
                pos += step


def slide_range(masks, state, index):
    """The lowest and highest positions vehicle `index` can slide to."""
    reach = [pos for i, pos in moves_from(masks, state) if i == index]
    return min(reach + [state[index]]), max(reach + [state[index]])


def movable(masks, state):
    """How many vehicles have room to slide."""
    return len({i for i, _ in moves_from(masks, state)})


def is_solved(state):
    return state[0] == SIZE - 2  # the red car is always vehicle 0


def random_jam(count):
    """The red car plus up to `count` vehicles dropped in at random."""
    vehicles = [Vehicle(True, EXIT_ROW, 2)]
    state = [random.randint(0, SIZE - 3)]
    taken = set(cells(vehicles[0], state[0]))
    for _ in range(count * 20):
        if len(vehicles) > count:
            break
        length = 3 if random.random() < TRUCK_CHANCE else 2
        vehicle = Vehicle(random.random() < 0.5, random.randrange(SIZE), length)
        if vehicle.horizontal and vehicle.line == EXIT_ROW:
            continue  # it could never get out of the red car's way
        pos = random.randint(0, SIZE - length)
        spot = cells(vehicle, pos)
        if taken.isdisjoint(spot):
            taken.update(spot)
            vehicles.append(vehicle)
            state.append(pos)
    return vehicles, tuple(state)


def distances(masks, start):
    """Fewest moves to solve, for every position reachable from `start`.

    Returns None if there are too many positions to search quickly.
    """
    links = {}
    queue = deque([start])
    while queue:
        state = queue.popleft()
        if state in links:
            continue
        if len(links) >= MAX_STATES:
            return None
        links[state] = [state[:i] + (pos,) + state[i + 1:]
                        for i, pos in moves_from(masks, state)]
        queue.extend(links[state])

    # Slides can be undone, so searching outwards from the solved positions
    # gives the distance back to them.
    dist = {state: 0 for state in links if is_solved(state)}
    queue = deque(dist)
    while queue:
        state = queue.popleft()
        for other in links[state]:
            if other not in dist:
                dist[other] = dist[state] + 1
                queue.append(other)
    return dist


def generate(moves, count):
    """A fresh puzzle as (vehicles, start position, fewest moves to solve).

    `moves` and `count` are (min, max) ranges for the solution length and the
    number of vehicles.
    """
    while True:
        vehicles, state = random_jam(random.randint(*count))
        masks = make_masks(vehicles)
        dist = distances(masks, state)
        if not dist:
            continue
        fits = [s for s, d in dist.items() if moves[0] <= d <= moves[1]]
        random.shuffle(fits)
        for start in fits[:50]:
            if movable(masks, start) >= MIN_MOVABLE:
                return vehicles, start, dist[start]


def next_move(masks, start):
    """The first move of a shortest solution, as (vehicle index, position)."""
    seen = {start}
    queue = deque((start[:i] + (pos,) + start[i + 1:], (i, pos))
                  for i, pos in moves_from(masks, start))
    while queue:
        state, first = queue.popleft()
        if is_solved(state):
            return first
        if state in seen:
            continue
        seen.add(state)
        for i, pos in moves_from(masks, state):
            queue.append((state[:i] + (pos,) + state[i + 1:], first))
    return None


# ── Drawing helpers ─────────────────────────────────────────────────────────
def make_backdrop():
    strip = pygame.Surface((1, HEIGHT))
    for y in range(HEIGHT):
        t = y / (HEIGHT - 1)
        strip.set_at((0, y), [round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)])
    return pygame.transform.scale(strip, (WIDTH, HEIGHT))


def make_sprite(vehicle, color):
    """Top-down car or truck, facing right if horizontal and up otherwise."""
    w, h = vehicle.length * CELL - 2 * PAD, CELL - 2 * PAD
    sprite = pygame.Surface((w, h), pygame.SRCALPHA)
    body = sprite.get_rect()
    shade = [c * 0.6 for c in color]
    light = [min(255, c * 1.15 + 12) for c in color]
    pygame.draw.rect(sprite, color, body, border_radius=14)
    if vehicle.length == 2:
        pygame.draw.rect(sprite, GLASS, (w * 0.2, 8, w * 0.56, h - 16), border_radius=10)
        pygame.draw.rect(sprite, light, (w * 0.34, 11, w * 0.26, h - 22), border_radius=6)
    else:
        # Truck: a load bed behind the cab
        pygame.draw.rect(sprite, light, (8, 7, w * 0.66, h - 14), border_radius=6)
        pygame.draw.rect(sprite, shade, (8, 7, w * 0.66, h - 14), 2, border_radius=6)
        pygame.draw.rect(sprite, GLASS, (w * 0.78, 9, w * 0.1, h - 18), border_radius=4)
    pygame.draw.rect(sprite, shade, body, 3, border_radius=14)
    for y in (9, h - 21):
        pygame.draw.rect(sprite, HEADLIGHT, (w - 8, y, 5, 12), border_radius=2)
        pygame.draw.rect(sprite, TAILLIGHT, (3, y, 4, 12), border_radius=2)
    return sprite if vehicle.horizontal else pygame.transform.rotate(sprite, 90)


class CarPark:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Car Park")
        pygame.key.set_repeat(250, 110)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 34)
        self.small_font = pygame.font.Font(None, 22)
        self.big_font = pygame.font.Font(None, 76)
        self.backdrop = make_backdrop()
        self.difficulty = 0
        self.vehicles = []
        self.new_puzzle()

    # ── Game state ──────────────────────────────────────────────────────────
    def new_puzzle(self):
        # Hard puzzles can take a moment to find
        self.vehicles = []
        self.draw(banner="Generating...")
        self.vehicles, self.start, self.best = generate(*DIFFICULTIES[self.difficulty][1:])
        self.masks = make_masks(self.vehicles)
        colors = random.sample(COLORS, len(self.vehicles) - 1)
        self.sprites = [make_sprite(v, c) for v, c in zip(self.vehicles, [RED] + colors)]
        self.restart()
        pygame.event.clear()  # drop keys pressed while generating

    def restart(self):
        self.state = self.start
        self.moves = 0
        self.last_moved = None
        self.history = []
        self.selected = 0
        self.drag = None      # (vehicle index, grab offset, lowest px, highest px)
        self.drag_px = 0
        self.hint = None      # (vehicle index, position)
        self.solved = False
        self.exit_px = 0      # how far the red car has driven out

    def move_to(self, index, pos):
        if pos == self.state[index]:
            return
        self.history.append((self.state, self.moves, self.last_moved))
        self.state = self.state[:index] + (pos,) + self.state[index + 1:]
        if index != self.last_moved:
            self.moves += 1  # sliding the same vehicle again is still one move
        self.last_moved = index
        self.hint = None
        self.solved = is_solved(self.state)

    def undo(self):
        if self.history:
            self.state, self.moves, self.last_moved = self.history.pop()
            self.hint = None

    def nudge(self, dx, dy):
        """Slides the selected vehicle one cell, if it runs that way."""
        vehicle = self.vehicles[self.selected]
        step = dx if vehicle.horizontal else dy
        lo, hi = slide_range(self.masks, self.state, self.selected)
        pos = self.state[self.selected] + step
        if step and lo <= pos <= hi:
            self.move_to(self.selected, pos)

    def select_next(self, step):
        """Moves the selection to the next vehicle that has room to slide."""
        def reading_order(i):
            x, y = cells(self.vehicles[i], self.state[i])[0]
            return y, x, i
        free = {i for i, _ in moves_from(self.masks, self.state)} | {self.selected}
        order = sorted(free, key=reading_order)
        self.selected = order[(order.index(self.selected) + step) % len(order)]

    def vehicle_at(self, pos):
        cell = ((pos[0] - BOARD_X) // CELL, (pos[1] - BOARD_Y) // CELL)
        for i, (vehicle, where) in enumerate(zip(self.vehicles, self.state)):
            if cell in cells(vehicle, where):
                return i
        return None

    # ── Mouse ───────────────────────────────────────────────────────────────
    def along(self, index, pos):
        """Mouse position measured along the vehicle's line, from the board edge."""
        return pos[0] - BOARD_X if self.vehicles[index].horizontal else pos[1] - BOARD_Y

    def grab(self, pos):
        index = self.vehicle_at(pos)
        if index is None:
            return
        self.selected = index
        lo, hi = slide_range(self.masks, self.state, index)
        self.drag_px = self.state[index] * CELL
        self.drag = (index, self.along(index, pos) - self.drag_px, lo * CELL, hi * CELL)

    def pull(self, pos):
        index, offset, lo, hi = self.drag
        self.drag_px = max(lo, min(hi, self.along(index, pos) - offset))

    def release(self):
        index = self.drag[0]
        pos = round(self.drag_px / CELL)
        self.drag = None
        self.move_to(index, pos)

    # ── Drawing ─────────────────────────────────────────────────────────────
    def vehicle_rect(self, index, px):
        vehicle = self.vehicles[index]
        long, short = vehicle.length * CELL - 2 * PAD, CELL - 2 * PAD
        if vehicle.horizontal:
            return pygame.Rect(BOARD_X + px + PAD, BOARD_Y + vehicle.line * CELL + PAD,
                               long, short)
        return pygame.Rect(BOARD_X + vehicle.line * CELL + PAD, BOARD_Y + px + PAD,
                           short, long)

    def draw_board(self):
        board = pygame.Rect(BOARD_X, BOARD_Y, BOARD, BOARD)
        pygame.draw.rect(self.screen, FRAME_COLOR, board.inflate(2 * FRAME, 2 * FRAME),
                         border_radius=10)
        pygame.draw.rect(self.screen, ASPHALT, board)
        exit_y = BOARD_Y + EXIT_ROW * CELL
        pygame.draw.rect(self.screen, ASPHALT, (board.right, exit_y, FRAME, CELL))
        for x in range(1, SIZE):
            for y in range(1, SIZE):
                pygame.draw.circle(self.screen, DOT, (BOARD_X + x * CELL, BOARD_Y + y * CELL), 3)
        # Arrow pointing out of the exit
        ax, ay = board.right + FRAME + 8, exit_y + CELL // 2
        pygame.draw.polygon(self.screen, TEXT, [(ax, ay - 12), (ax + 14, ay), (ax, ay + 12)])

    def draw_vehicles(self):
        for i, sprite in enumerate(self.sprites):
            px = self.state[i] * CELL
            if self.drag and self.drag[0] == i:
                px = self.drag_px
            if i == 0:
                px += self.exit_px
            rect = self.vehicle_rect(i, px)
            self.screen.blit(sprite, rect)
            if i == self.selected and not self.solved:
                pygame.draw.rect(self.screen, SELECT, rect, 3, border_radius=14)
        if self.hint:
            index, pos = self.hint
            pygame.draw.rect(self.screen, HINT, self.vehicle_rect(index, self.state[index] * CELL),
                             4, border_radius=14)
            pygame.draw.rect(self.screen, HINT, self.vehicle_rect(index, pos * CELL),
                             2, border_radius=14)

    def draw_text(self, text, font, color, shadow=0, **position):
        if shadow:
            surface = font.render(text, True, (0, 0, 0))
            self.screen.blit(surface, surface.get_rect(**position).move(shadow, shadow))
        surface = font.render(text, True, color)
        self.screen.blit(surface, surface.get_rect(**position))

    def draw_hud(self):
        if self.vehicles:
            name = DIFFICULTIES[self.difficulty][0]
            self.draw_text(f"{name}    Moves: {self.moves}    Best: {self.best}",
                           self.font, TEXT, center=(WIDTH // 2, 40))
        self.draw_text("Drag a vehicle, or pick it with a click or Tab and use the arrow keys",
                       self.small_font, TEXT_DIM, center=(WIDTH // 2, HEIGHT - 60))
        self.draw_text("1/2/3 difficulty   N new   R restart   U undo   H hint   Esc quit",
                       self.small_font, TEXT_DIM, center=(WIDTH // 2, HEIGHT - 34))

    def draw(self, banner=""):
        self.screen.blit(self.backdrop, (0, 0))
        self.draw_board()
        if self.vehicles:
            self.draw_vehicles()
        self.draw_hud()
        center = (WIDTH // 2, BOARD_Y + BOARD // 2)
        if self.vehicles and self.solved:
            self.draw_text("Solved!", self.big_font, TEXT, shadow=3, center=center)
            self.draw_text(f"{self.moves} moves (best {self.best})   -   R = new puzzle",
                           self.small_font, SELECT, shadow=2,
                           center=(center[0], center[1] + 50))
        elif banner:
            self.draw_text(banner, self.big_font, TEXT, shadow=3, center=center)
        pygame.display.flip()

    # ── Main loop ───────────────────────────────────────────────────────────
    def handle_key(self, key):
        if key == pygame.K_ESCAPE:
            return False
        if key in (pygame.K_1, pygame.K_2, pygame.K_3):
            self.difficulty = key - pygame.K_1
            self.new_puzzle()
        elif key == pygame.K_n or (self.solved and key == pygame.K_r):
            self.new_puzzle()   # once solved, R moves on to a fresh puzzle
        elif key == pygame.K_r:
            self.restart()
        elif self.solved or self.drag:
            pass
        elif key in (pygame.K_u, pygame.K_z):
            self.undo()
        elif key == pygame.K_TAB:
            self.select_next(-1 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1)
        elif key == pygame.K_h:
            self.hint = next_move(self.masks, self.state)
            self.selected = self.hint[0]
        elif key == pygame.K_LEFT:
            self.nudge(-1, 0)
        elif key == pygame.K_RIGHT:
            self.nudge(1, 0)
        elif key == pygame.K_UP:
            self.nudge(0, -1)
        elif key == pygame.K_DOWN:
            self.nudge(0, 1)
        return True

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            return self.handle_key(event.key)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not self.solved:
            self.grab(event.pos)
        elif event.type == pygame.MOUSEMOTION and self.drag:
            self.pull(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.drag:
            self.release()
        return True

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000
            for event in pygame.event.get():
                running = self.handle_event(event) and running
            if self.solved:
                self.exit_px = min(self.exit_px + EXIT_SPEED * dt, WIDTH)
            self.draw()
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    CarPark().run()
