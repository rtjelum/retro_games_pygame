"""Snake Escape -- send every snake off the board, one at a time.

Click a snake and it slithers straight ahead, the way its arrow points. It
only gets out if nothing is in the way; bump into another snake and you lose
a life. Every puzzle is generated on the spot and has exactly one solution:
at any moment only one snake is free to go.

Controls: click a snake to send it off.
          1 / 2 / 3 size, N new puzzle, R restart (a new puzzle once
          solved), H hint, Esc quit.
"""
import math
import random
import sys

import pygame

WIDTH, HEIGHT = 620, 730
FPS = 60
BOARD = 540
BOARD_X, BOARD_Y = (WIDTH - BOARD) // 2, 88
LIVES = 3
EXIT_SPEED, EXIT_ACCEL = 10, 60   # cells per second, and per second squared
BUMP_TIME = 0.32                  # seconds for a blocked snake to lunge and return

# (name, cells along each side of the board)
DIFFICULTIES = [("Easy", 6), ("Medium", 9), ("Hard", 13)]
STRAIGHT_CHANCE = 0.6   # how often a snake's body carries straight on
TRIES = 60              # random attempts at fitting in one more snake
ATTEMPTS = 300          # boards built per puzzle; the one with most snakes is kept
ARM = 2                 # how far a new snake first reaches each way; short ones pack better

BG_TOP, BG_BOTTOM = (36, 44, 58), (16, 18, 26)
PANEL, DOT = (26, 30, 40), (52, 58, 72)
COLORS = [(239, 83, 80), (255, 167, 38), (255, 213, 79), (102, 187, 106),
          (38, 198, 218), (66, 133, 244), (171, 120, 235), (236, 112, 160),
          (156, 204, 101), (255, 138, 101)]
TEXT, TEXT_DIM, WHITE = (255, 213, 79), (200, 204, 212), (255, 255, 255)
HEART, HEART_LOST, BUMP = (239, 83, 80), (70, 74, 88), (255, 96, 96)

STEPS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


class Snake:
    def __init__(self, cells, color=None):
        self.cells = cells  # tail first, head last
        self.color = color

    @property
    def direction(self):
        (hx, hy), (nx, ny) = self.cells[-1], self.cells[-2]
        return hx - nx, hy - ny

    def ray(self, size):
        """The cells straight ahead of the head, out to the edge of the board."""
        (x, y), (dx, dy) = self.cells[-1], self.direction
        ahead = []
        x, y = x + dx, y + dy
        while 0 <= x < size and 0 <= y < size:
            ahead.append((x, y))
            x, y = x + dx, y + dy
        return ahead


# ── Puzzle generator ────────────────────────────────────────────────────────
def grow(walk, steps, free):
    """Extends a path from its last cell, wandering through free cells."""
    for _ in range(steps):
        x, y = walk[-1]
        options = [(x + dx, y + dy) for dx, dy in STEPS
                   if (x + dx, y + dy) in free and (x + dx, y + dy) not in walk]
        if not options:
            break
        step = random.choice(options)
        if len(walk) > 1 and random.random() < STRAIGHT_CHANCE:
            straight = (2 * x - walk[-2][0], 2 * y - walk[-2][1])
            if straight in options:
                step = straight
        walk.append(step)


def new_snake(size, free, crossing):
    """A snake lying across one of the `crossing` cells, with a clear way out.

    Returns None if a few random tries don't turn one up.
    """
    for _ in range(TRIES):
        walk = [random.choice(crossing)]
        grow(walk, random.randint(1, ARM), free)
        walk.reverse()
        grow(walk, random.randint(0, ARM), free)
        if len(walk) < 2:
            continue
        for cells in (walk, walk[::-1]):
            snake = Snake(cells)
            ray = snake.ray(size)
            if ray and free.issuperset(ray) and not set(ray) & set(cells):
                return snake
    return None


def chain(size):
    """Snakes that can only leave in one order, listed first to leave first.

    Built backwards from the last one out: each new snake is laid across the
    way out of the one before, so that one is stuck until the new one has
    gone, and its own way out is kept clear of everything already there.
    """
    free = {(x, y) for x in range(size) for y in range(size)}
    snakes = []
    crossing = sorted(free)
    while True:
        snake = new_snake(size, free, crossing)
        if snake is None:
            break
        free.difference_update(snake.cells)
        snakes.append(snake)
        crossing = snake.ray(size)
    snakes.reverse()

    # Lengthen the tails into the gaps. A tail must stay out of its own way
    # and out of the way of every snake that leaves earlier.
    ways_out = set()
    for snake in snakes:
        ways_out.update(snake.ray(size))
        while True:
            x, y = snake.cells[0]
            options = [(x + dx, y + dy) for dx, dy in STEPS
                       if (x + dx, y + dy) in free and (x + dx, y + dy) not in ways_out]
            if not options:
                break
            cell = random.choice(options)
            free.discard(cell)
            snake.cells.insert(0, cell)
    return snakes


def paint(snakes):
    """Gives each snake a colour that none of the snakes touching it has."""
    owner = {cell: snake for snake in snakes for cell in snake.cells}
    for snake in snakes:
        touching = {owner.get((x + dx, y + dy)) for x, y in snake.cells for dx, dy in STEPS}
        used = {other.color for other in touching if other and other is not snake}
        snake.color = random.choice([c for c in COLORS if c not in used] or COLORS)


def generate(size):
    """A puzzle with exactly one solution: the busiest of many random boards."""
    snakes = max((chain(size) for _ in range(ATTEMPTS)), key=len)
    paint(snakes)
    random.shuffle(snakes)  # so the hint can't just read off the order
    return snakes


# ── Game ────────────────────────────────────────────────────────────────────
def make_backdrop():
    strip = pygame.Surface((1, HEIGHT))
    for y in range(HEIGHT):
        t = y / (HEIGHT - 1)
        strip.set_at((0, y), [round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)])
    return pygame.transform.scale(strip, (WIDTH, HEIGHT))


class SnakeEscape:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Snake Escape")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 34)
        self.small_font = pygame.font.Font(None, 22)
        self.big_font = pygame.font.Font(None, 76)
        self.backdrop = make_backdrop()
        self.difficulty = 0
        self.new_puzzle()

    # ── Game state ──────────────────────────────────────────────────────────
    def new_puzzle(self):
        self.size = DIFFICULTIES[self.difficulty][1]
        self.cell = BOARD // self.size
        self.puzzle = [(tuple(snake.cells), snake.color) for snake in generate(self.size)]
        self.restart()

    def restart(self):
        self.snakes = [Snake(list(cells), color) for cells, color in self.puzzle]
        self.grid = {cell: snake for snake in self.snakes for cell in snake.cells}
        self.leaving = []   # [snake, cells travelled, speed] for snakes on their way out
        self.bumps = []     # [snake, seconds so far, free cells ahead] for blocked ones
        self.lives = LIVES
        self.hint = None
        self.state = "playing"  # playing / won / lost

    def send(self, snake):
        """Sets a snake off; it leaves if its way is clear and bumps if not."""
        if any(bump[0] is snake for bump in self.bumps):
            return
        self.hint = None
        ray = snake.ray(self.size)
        blocked = [i for i, cell in enumerate(ray) if cell in self.grid]
        if blocked:
            self.bumps.append([snake, 0.0, blocked[0]])
            self.lives -= 1
            if self.lives == 0:
                self.state = "lost"
            return
        for cell in snake.cells:
            del self.grid[cell]
        self.snakes.remove(snake)
        self.leaving.append([snake, 0.0, EXIT_SPEED])
        if not self.snakes:
            self.state = "won"

    def show_hint(self):
        for snake in self.snakes:
            if not any(cell in self.grid for cell in snake.ray(self.size)):
                self.hint = snake
                return

    def update(self, dt):
        for item in self.leaving:
            item[2] += EXIT_ACCEL * dt
            item[1] += item[2] * dt
        # Gone once the tail is well clear of the window
        self.leaving = [item for item in self.leaving
                        if item[1] < self.size + len(item[0].cells) + 2]
        for item in self.bumps:
            item[1] += dt
        self.bumps = [item for item in self.bumps if item[1] < BUMP_TIME]

    # ── Drawing ─────────────────────────────────────────────────────────────
    def center(self, cell):
        return (BOARD_X + (cell[0] + 0.5) * self.cell, BOARD_Y + (cell[1] + 0.5) * self.cell)

    def snake_at(self, pos):
        cell = ((pos[0] - BOARD_X) // self.cell, (pos[1] - BOARD_Y) // self.cell)
        return self.grid.get(cell)

    def draw_snake(self, snake, travelled=0.0, color=None, extra=0):
        """Draws a snake that has slithered `travelled` cells ahead of its place."""
        color = color or snake.color
        width = max(round(self.cell * 0.3), 4) + extra
        dx, dy = snake.direction
        hx, hy = snake.cells[-1]
        # The body follows its own cells, then the straight line ahead of the head
        path = snake.cells + [(hx + dx * i, hy + dy * i)
                              for i in range(1, math.ceil(travelled) + 2)]

        def along(t):
            i = int(t)
            (ax, ay), (bx, by) = self.center(path[i]), self.center(path[i + 1])
            return ax + (bx - ax) * (t - i), ay + (by - ay) * (t - i)

        head_at = travelled + len(snake.cells) - 1
        points = ([along(travelled)]
                  + [self.center(path[i])
                     for i in range(int(travelled) + 1, math.ceil(head_at))]
                  + [along(head_at)])
        for a, b in zip(points, points[1:]):
            pygame.draw.line(self.screen, color, a, b, width)
        for point in points[:-1]:
            pygame.draw.circle(self.screen, color, point, width / 2)

        x, y = points[-1]
        reach, half = self.cell * 0.42 + extra, self.cell * 0.34 + extra
        back = self.cell * 0.1 + extra
        pygame.draw.polygon(self.screen, color, [
            (x + dx * reach, y + dy * reach),
            (x - dx * back - dy * half, y - dy * back + dx * half),
            (x - dx * back + dy * half, y - dy * back - dx * half)])

    def draw_board(self):
        side = self.size * self.cell
        pygame.draw.rect(self.screen, PANEL, (BOARD_X - 10, BOARD_Y - 10, side + 20, side + 20),
                         border_radius=14)
        for x in range(self.size):
            for y in range(self.size):
                pygame.draw.circle(self.screen, DOT, self.center((x, y)), 2)

        bumping = {id(item[0]): item for item in self.bumps}
        hovered = self.snake_at(pygame.mouse.get_pos()) if self.state == "playing" else None
        for snake in self.snakes:
            if id(snake) in bumping:
                _, t, free = bumping[id(snake)]
                lunge = (free + 0.25) * (1 - abs(2 * t / BUMP_TIME - 1))
                self.draw_snake(snake, lunge, BUMP)
                continue
            if snake is self.hint:
                self.draw_snake(snake, color=WHITE, extra=6)
            color = None
            if snake is hovered:
                color = [min(255, c + 45) for c in snake.color]
            self.draw_snake(snake, color=color)
        for snake, travelled, _ in self.leaving:
            self.draw_snake(snake, travelled)

    def draw_heart(self, x, y, color):
        pygame.draw.circle(self.screen, color, (x - 6, y - 4), 7)
        pygame.draw.circle(self.screen, color, (x + 6, y - 4), 7)
        pygame.draw.polygon(self.screen, color, [(x - 12, y - 1), (x + 12, y - 1), (x, y + 13)])

    def draw_text(self, text, font, color, shadow=0, **position):
        if shadow:
            surface = font.render(text, True, (0, 0, 0))
            self.screen.blit(surface, surface.get_rect(**position).move(shadow, shadow))
        surface = font.render(text, True, color)
        self.screen.blit(surface, surface.get_rect(**position))

    def draw_hud(self):
        name = DIFFICULTIES[self.difficulty][0]
        self.draw_text(f"{name}    Snakes left: {len(self.snakes)}", self.font, TEXT,
                       midleft=(BOARD_X, 40))
        for i in range(LIVES):
            self.draw_heart(BOARD_X + BOARD - 16 - i * 34, 38,
                            HEART if i < self.lives else HEART_LOST)
        self.draw_text("Click a snake to send it off - its way out must be clear",
                       self.small_font, TEXT_DIM, center=(WIDTH // 2, HEIGHT - 60))
        self.draw_text("1/2/3 size   N new   R restart   H hint   Esc quit",
                       self.small_font, TEXT_DIM, center=(WIDTH // 2, HEIGHT - 34))

        center = (WIDTH // 2, BOARD_Y + BOARD // 2)
        if self.state == "won":
            self.draw_text("All out!", self.big_font, TEXT, shadow=3, center=center)
            self.draw_text("R = new puzzle", self.small_font, WHITE, shadow=2,
                           center=(center[0], center[1] + 50))
        elif self.state == "lost":
            self.draw_text("Out of lives", self.big_font, BUMP, shadow=3, center=center)
            self.draw_text("R = try again   N = new puzzle", self.small_font, WHITE, shadow=2,
                           center=(center[0], center[1] + 50))

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
            self.new_puzzle()
        elif key == pygame.K_n or (self.state == "won" and key == pygame.K_r):
            self.new_puzzle()   # once solved, R moves on to a fresh puzzle
        elif key == pygame.K_r:
            self.restart()
        elif key == pygame.K_h and self.state == "playing":
            self.show_hint()
        return True

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            return self.handle_key(event.key)
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.state == "playing"):
            snake = self.snake_at(event.pos)
            if snake:
                self.send(snake)
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
    SnakeEscape().run()
