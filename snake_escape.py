"""Snake Escape -- send every snake off a box, one at a time.

The snakes lie on the faces of a box, their bodies bending round its edges
from one face to the next. Click a snake and it slithers straight ahead, the
way its arrow points, across the face its head is on and off the edge into
space. It only gets out if nothing is in the way; bump into another snake and
you lose a life, and three bumps end the round. Drag to turn the box and see
the faces round the back. Every puzzle is generated on the spot and can always
be cleared, though only a few snakes are free to go at any moment.

Controls: click a snake to send it off, drag to turn the box.
          N new puzzle, R restart (a new puzzle once solved), Esc quit.
"""
import math
import random
import sys

import pygame

WIDTH, HEIGHT = 860, 880
FPS = 60
CENTER = (WIDTH // 2, 440)        # where the middle of the box is drawn
REACH = 330                       # pixels from there to the box's farthest corner
CAMERA = 5 * REACH                # pixels from there to the eye; nearer looks more 3D
NEAR = 0.2 * CAMERA               # closest to the eye a point is drawn as being
EXIT_SPEED, EXIT_ACCEL = 10, 60   # cells per second, and per second squared
BUMP_TIME = 0.32                  # seconds for a blocked snake to lunge and return
DRAG = 0.008                      # radians the box turns per pixel dragged
CLICK_SLOP = 5                    # pixels the mouse may wander in a click
TILT, SPIN = 0.45, 0.6            # radians the box is tipped forward and turned at the start

BOX = (12, 12, 12)                # cells along x, y (up) and z
UNIT = REACH / math.hypot(*BOX)   # pixels per half cell
BODY = 0.4                        # how wide a snake is, in half cells
LIVES = 3

STRAIGHT_CHANCE = 0.35  # how often a snake's body carries straight on
TRIES = 60              # random attempts at fitting in one more snake
CHAINS = 10             # chains of snakes per box: each one is a snake free to go
ATTEMPTS = 40           # boxes built per puzzle; the one with most snakes is kept
ARM = 2                 # how far a new snake first reaches each way; short ones pack better

BG_TOP, BG_BOTTOM = (36, 44, 58), (16, 18, 26)
FACE_DARK, FACE_LIGHT, EDGE, DOT = (20, 24, 36), (36, 42, 60), (120, 130, 170), (62, 70, 92)
COLORS = [(239, 83, 80), (255, 167, 38), (255, 213, 79), (102, 187, 106),
          (38, 198, 218), (66, 133, 244), (171, 120, 235), (236, 112, 160),
          (156, 204, 101), (255, 138, 101)]
TEXT, TEXT_DIM, WHITE = (255, 213, 79), (200, 204, 212), (255, 255, 255)
HEART, HEART_LOST, BUMP = (239, 83, 80), (70, 74, 88), (255, 96, 96)


# ── Box surface ─────────────────────────────────────────────────────────────
# A cell is the 3D point at its centre, counted in half cells from the box's
# corner: along the axis its face looks down it is 0 or twice the box's size
# there, along the other two it is odd. Directions are unit steps along an axis.
def add(a, b):
    return a[0] + b[0], a[1] + b[1], a[2] + b[2]


def mul(a, k):
    return a[0] * k, a[1] * k, a[2] * k


def cross(a, b):
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def axis_of(direction):
    return next(i for i in range(3) if direction[i])


def normal(cell, box):
    """The outward direction of the face the cell is on."""
    for i in range(3):
        if cell[i] in (0, 2 * box[i]):
            return tuple((1 if cell[i] else -1) if j == i else 0 for j in range(3))
    return None


def step(cell, direction, box):
    """The next cell going `direction`, and the way on from there.

    Over the edge of a face the way on turns down the next face.
    """
    ahead = add(cell, mul(direction, 2))
    i = axis_of(direction)
    if 0 < ahead[i] < 2 * box[i]:
        return ahead, direction
    out = normal(cell, box)
    return add(add(cell, direction), mul(out, -1)), mul(out, -1)


def neighbours(cell, box):
    out = normal(cell, box)
    return [step(cell, tuple(sign if j == i else 0 for j in range(3)), box)[0]
            for i in range(3) if not out[i] for sign in (1, -1)]


def heading(a, b, box):
    """The way a snake goes on from b, having just come from a."""
    if normal(a, box) == normal(b, box):
        return tuple((y - x) // 2 for x, y in zip(a, b))
    return mul(normal(a, box), -1)


def surface(box):
    """Every cell of the box, face by face."""
    cells = []
    for i in range(3):
        a, b = (j for j in range(3) if j != i)
        for side in (0, 2 * box[i]):
            for u in range(1, 2 * box[a], 2):
                for v in range(1, 2 * box[b], 2):
                    cell = [0, 0, 0]
                    cell[i], cell[a], cell[b] = side, u, v
                    cells.append(tuple(cell))
    return cells


class Snake:
    def __init__(self, cells, color=None):
        self.cells = cells  # tail first, head last
        self.color = color

    def direction(self, box):
        return heading(self.cells[-2], self.cells[-1], box)

    def ray(self, box):
        """The cells straight ahead of the head, out to the edge of its face."""
        direction = self.direction(box)
        i = axis_of(direction)
        ahead = []
        cell = add(self.cells[-1], mul(direction, 2))
        while 0 < cell[i] < 2 * box[i]:
            ahead.append(cell)
            cell = add(cell, mul(direction, 2))
        return ahead

    def exit_length(self, box):
        """Cells a snake on its way out slithers before it is well clear of the window."""
        return len(self.cells) + len(self.ray(box)) + 2 * max(box) + 2


def track(snake, box):
    """The way a snake goes, from its tail all the way out: points half a cell
    apart, and the face each half-cell stretch between them lies on.

    The points are each cell, then the point between it and the next, which
    over an edge is on the edge. After its way out across its face the snake
    flies on off the edge, in that face's plane, and keeps that face's normal.
    """
    direction = snake.direction(box)
    path = snake.cells + snake.ray(box)
    end = path[-1]
    path += [add(end, mul(direction, 2 * i)) for i in range(1, snake.exit_length(box) + 3)]
    points, outs = [path[0]], []
    for a, b in zip(path, path[1:]):
        out_a, out_b = normal(a, box), normal(b, box)
        middle = tuple((p + q) / 2 for p, q in zip(a, b)) if out_a == out_b else add(b, out_a)
        points += [middle, b]
        outs += [out_a, out_b]
    return points, outs


# ── Puzzle generator ────────────────────────────────────────────────────────
def grow(walk, steps, free, box):
    """Extends a path from its last cell, wandering through free cells."""
    for _ in range(steps):
        options = [cell for cell in neighbours(walk[-1], box)
                   if cell in free and cell not in walk]
        if not options:
            break
        cell = random.choice(options)
        if len(walk) > 1 and random.random() < STRAIGHT_CHANCE:
            straight = step(walk[-1], heading(walk[-2], walk[-1], box), box)[0]
            if straight in options:
                cell = straight
        walk.append(cell)


def new_snake(box, free, crossing):
    """A snake lying across one of the `crossing` cells, with a clear way out.

    Returns None if a few random tries don't turn one up.
    """
    for _ in range(TRIES):
        walk = [random.choice(crossing)]
        grow(walk, random.randint(1, ARM), free, box)
        walk.reverse()
        grow(walk, random.randint(0, ARM), free, box)
        if len(walk) < 2:
            continue
        for cells in (walk, walk[::-1]):
            snake = Snake(cells)
            ray = snake.ray(box)
            if ray and free.issuperset(ray) and not set(ray) & set(cells):
                return snake
    return None


def build(box):
    """Snakes that can all leave, listed in an order they can leave in.

    Built backwards from the last one out, in chains: each new snake is laid
    across the way out of the one before, so that one is stuck until the new
    one has gone, and its own way out is kept clear of everything already
    there. When a chain runs out of room a fresh one starts anywhere; the last
    snake of each chain is free to go.
    """
    free = set(surface(box))
    snakes = []
    crossing = sorted(free)
    chains = 1
    while True:
        snake = new_snake(box, free, crossing)
        if snake is None:
            if chains == CHAINS:
                break
            crossing, chains = sorted(free), chains + 1
            continue
        free.difference_update(snake.cells)
        snakes.append(snake)
        crossing = snake.ray(box)
    snakes.reverse()

    # Lengthen the tails into the gaps. A tail must stay out of its own way
    # and out of the way of every snake that leaves earlier.
    ways_out = set()
    for snake in snakes:
        ways_out.update(snake.ray(box))
        while True:
            options = [cell for cell in neighbours(snake.cells[0], box)
                       if cell in free and cell not in ways_out]
            if not options:
                break
            cell = random.choice(options)
            free.discard(cell)
            snake.cells.insert(0, cell)
    return snakes


def paint(snakes, box):
    """Gives each snake a colour that none of the snakes touching it has."""
    owner = {cell: snake for snake in snakes for cell in snake.cells}
    for snake in snakes:
        touching = {owner.get(near) for cell in snake.cells for near in neighbours(cell, box)}
        used = {other.color for other in touching if other and other is not snake}
        snake.color = random.choice([c for c in COLORS if c not in used] or COLORS)


def generate(box):
    """A puzzle that can always be cleared: the busiest of many random boxes."""
    snakes = max((build(box) for _ in range(ATTEMPTS)), key=len)
    paint(snakes, box)
    random.shuffle(snakes)  # so no order can be read off the list
    return snakes


# ── Turning the box ─────────────────────────────────────────────────────────
# The view is a rotation matrix taking box space to screen space: x right,
# y down, and z away from the viewer.
def turn(axis, angle):
    """A rotation about the screen's x or y axis."""
    c, s = math.cos(angle), math.sin(angle)
    if axis == 0:
        return [[1, 0, 0], [0, c, -s], [0, s, c]]
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def straighten(m):
    """Squeezes the rounding errors out of a rotation matrix."""
    x, y = m[0], m[1]
    size = math.sqrt(sum(v * v for v in x))
    x = [v / size for v in x]
    dot = sum(a * b for a, b in zip(x, y))
    y = [b - dot * a for a, b in zip(x, y)]
    size = math.sqrt(sum(v * v for v in y))
    y = [v / size for v in y]
    return [x, y, list(cross(x, y))]


def make_backdrop():
    strip = pygame.Surface((1, HEIGHT))
    for y in range(HEIGHT):
        t = y / (HEIGHT - 1)
        strip.set_at((0, y), [round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)])
    return pygame.transform.scale(strip, (WIDTH, HEIGHT))


# ── Game ────────────────────────────────────────────────────────────────────
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
        self.press = None       # where the mouse went down, while it is held
        self.dragged = False    # whether that press has turned into a drag
        self.faces = {}         # outward direction: (corners, cells)
        for cell in surface(BOX):
            self.faces.setdefault(normal(cell, BOX), []).append(cell)
        for out, cells in self.faces.items():
            i = axis_of(out)
            a, b = (j for j in range(3) if j != i)
            corners = []
            for u, v in ((0, 0), (1, 0), (1, 1), (0, 1)):
                corner = [0, 0, 0]
                corner[i] = 2 * BOX[i] if out[i] > 0 else 0
                corner[a], corner[b] = 2 * BOX[a] * u, 2 * BOX[b] * v
                corners.append(tuple(corner))
            self.faces[out] = (corners, cells)
        self.new_puzzle()

    # ── Game state ──────────────────────────────────────────────────────────
    def new_puzzle(self):
        self.view = matmul(turn(0, TILT), turn(1, SPIN))
        self.puzzle = [(tuple(snake.cells), snake.color) for snake in generate(BOX)]
        self.restart()

    def restart(self):
        self.snakes = [Snake(list(cells), color) for cells, color in self.puzzle]
        self.grid = {cell: snake for snake in self.snakes for cell in snake.cells}
        self.tracks = {snake: track(snake, BOX) for snake in self.snakes}
        self.leaving = []   # [snake, cells travelled, speed] for snakes on their way out
        self.bumps = []     # [snake, seconds so far, free cells ahead] for blocked ones
        self.lives = LIVES
        self.state = "playing"  # playing / won / lost

    def send(self, snake):
        """Sets a snake off; it leaves if its way is clear and bumps if not."""
        if any(bump[0] is snake for bump in self.bumps):
            return
        ray = snake.ray(BOX)
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

    def update(self, dt):
        for item in self.leaving:
            item[2] += EXIT_ACCEL * dt
            item[1] += item[2] * dt
        # Gone once the tail is well clear of the window
        self.leaving = [item for item in self.leaving if item[1] < item[0].exit_length(BOX)]
        for item in self.bumps:
            item[1] += dt
        self.bumps = [item for item in self.bumps if item[1] < BUMP_TIME]

    def rotate(self, dx, dy):
        self.view = straighten(matmul(turn(0, dy * DRAG), matmul(turn(1, -dx * DRAG), self.view)))

    # ── Drawing ─────────────────────────────────────────────────────────────
    def project(self, point):
        """Screen position of a point in box space, seen in perspective."""
        (a, b, c), (d, e, f), (g, h, i) = self.view
        x, y, z = point[0] - BOX[0], point[1] - BOX[1], point[2] - BOX[2]
        depth = (g * x + h * y + i * z) * UNIT
        scale = UNIT * CAMERA / max(CAMERA + depth, NEAR)
        return (CENTER[0] + (a * x + b * y + c * z) * scale,
                CENTER[1] + (d * x + e * y + f * z) * scale)

    def shown(self, out):
        """How squarely a face looks at the eye: above 0 when it can be seen."""
        reach = BOX[axis_of(out)] * UNIT   # from the box's middle out to the face
        return -sum(r * c for r, c in zip(self.view[2], out)) - reach / CAMERA

    def snake_at(self, pos):
        """The snake under a screen position, on whichever face is in front there."""
        x, y = pos[0] - CENTER[0], pos[1] - CENTER[1]
        rows = self.view
        for out in self.faces:
            if self.shown(out) <= 0:
                continue
            i = axis_of(out)
            plane = ((2 * BOX[i] if out[i] > 0 else 0) - BOX[i]) * UNIT
            # Along the line of sight through (x, y), a point at `depth` sits at
            # (x, y) * (CAMERA + depth) / CAMERA in view space; box space is the
            # transposed view times that. Solve for the depth on this face's plane.
            slope = (rows[0][i] * x + rows[1][i] * y) / CAMERA
            if abs(slope + rows[2][i]) < 1e-9:
                continue
            depth = (plane - slope * CAMERA) / (slope + rows[2][i])
            stretch = (CAMERA + depth) / CAMERA
            seen = (x * stretch, y * stretch, depth)
            point = [sum(rows[j][k] * seen[j] for j in range(3)) / UNIT + BOX[k]
                     for k in range(3)]
            cell = [0, 0, 0]
            for k in range(3):
                if k == i:
                    cell[k] = 2 * BOX[i] if out[i] > 0 else 0
                elif 0 < point[k] < 2 * BOX[k]:
                    cell[k] = 2 * int(point[k] // 2) + 1
                else:
                    break
            else:
                return self.grid.get(tuple(cell))
        return None

    def draw_snake(self, snake, travelled=0.0, color=None):
        """Draws a snake that has slithered `travelled` cells ahead of its place.

        The snake is painted flat on the box. Only the parts on faces turned
        towards the viewer are drawn; a snake on its way out flies on off its
        face's edge, in that face's plane.
        """
        color = color or snake.color
        points, outs = self.tracks[snake]

        def at(s, piece):
            """The point `s` half cells along, on the stretch numbered `piece`."""
            a, b = points[piece], points[piece + 1]
            f = s - piece
            return tuple(p + (q - p) * f for p, q in zip(a, b))

        start, head_at = 2 * travelled, 2 * (travelled + len(snake.cells) - 1)
        stops = sorted({start, head_at, *range(int(start) + 1, math.ceil(head_at))})
        piece = 0
        for s, e in zip(stops, stops[1:]):
            piece = int((s + e) / 2)
            out = outs[piece]
            if self.facing[out] <= 0:
                continue
            along = tuple(q - p for p, q in zip(points[piece], points[piece + 1]))
            side = mul(cross(out, along), BODY / 2)
            # Square ends fill in the corner at a bend, but stop dead at the
            # box's edges so nothing sticks out into space
            a, b = at(s, piece), at(e, piece)
            if not (s == piece and piece and outs[piece - 1] != out):
                a = add(a, mul(along, -BODY / 2))
            if not (e == piece + 1 and piece + 1 < len(outs) and outs[piece + 1] != out):
                b = add(b, mul(along, BODY / 2))
            pygame.draw.polygon(self.screen, color, [self.project(p) for p in (
                add(a, side), add(b, side), add(b, mul(side, -1)), add(a, mul(side, -1)))])

        out = outs[piece]
        if self.facing[out] <= 0:
            return
        head = at(head_at, piece)
        ahead = tuple(q - p for p, q in zip(points[piece], points[piece + 1]))
        side = cross(out, ahead)
        reach, half, back = 0.66, 0.48, 0.16
        pygame.draw.polygon(self.screen, color, [self.project(p) for p in (
            add(head, mul(ahead, reach)),
            add(add(head, mul(ahead, -back)), mul(side, half)),
            add(add(head, mul(ahead, -back)), mul(side, -half)))])

    def draw_board(self):
        self.facing = {out: self.shown(out) for out in self.faces}
        for out, (corners, cells) in self.faces.items():
            shown = self.facing[out]
            if shown <= 0:
                continue
            outline = [self.project(corner) for corner in corners]
            pygame.draw.polygon(self.screen, [round(a + (b - a) * shown)
                                              for a, b in zip(FACE_DARK, FACE_LIGHT)], outline)
            pygame.draw.polygon(self.screen, EDGE, outline, 2)
            for cell in cells:
                pygame.draw.circle(self.screen, DOT, self.project(cell), 2)

        bumping = {id(item[0]): item for item in self.bumps}
        hovered = None
        if self.state == "playing" and not self.dragged:
            hovered = self.snake_at(pygame.mouse.get_pos())
        for snake in self.snakes:
            if id(snake) in bumping:
                _, t, free = bumping[id(snake)]
                lunge = (free + 0.25) * (1 - abs(2 * t / BUMP_TIME - 1))
                self.draw_snake(snake, lunge, BUMP)
                continue
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
        left, right = 40, WIDTH - 40
        self.draw_text(f"Snakes left: {len(self.snakes)}", self.font, TEXT, midleft=(left, 40))
        for i in range(LIVES):
            self.draw_heart(right - 16 - i * 34, 38, HEART if i < self.lives else HEART_LOST)
        self.draw_text("Drag to turn the box - click a snake to send it off its face",
                       self.small_font, TEXT_DIM, center=(WIDTH // 2, HEIGHT - 60))
        self.draw_text("N new puzzle   R restart   Esc quit",
                       self.small_font, TEXT_DIM, center=(WIDTH // 2, HEIGHT - 34))

        if self.state == "won":
            self.draw_text("All out!", self.big_font, TEXT, shadow=3, center=CENTER)
            self.draw_text("R = new puzzle", self.small_font, WHITE, shadow=2,
                           center=(CENTER[0], CENTER[1] + 50))
        elif self.state == "lost":
            self.draw_text("Out of lives", self.big_font, BUMP, shadow=3, center=CENTER)
            self.draw_text("R = try again   N = new puzzle", self.small_font, WHITE, shadow=2,
                           center=(CENTER[0], CENTER[1] + 50))

    def draw(self):
        self.screen.blit(self.backdrop, (0, 0))
        self.draw_board()
        self.draw_hud()
        pygame.display.flip()

    # ── Main loop ───────────────────────────────────────────────────────────
    def handle_key(self, key):
        if key == pygame.K_ESCAPE:
            return False
        if key == pygame.K_n or (self.state == "won" and key == pygame.K_r):
            self.new_puzzle()   # once solved, R moves on to a fresh puzzle
        elif key == pygame.K_r:
            self.restart()
        return True

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            return self.handle_key(event.key)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.press, self.dragged = event.pos, False
        elif event.type == pygame.MOUSEMOTION and self.press:
            if not self.dragged and math.dist(event.pos, self.press) > CLICK_SLOP:
                self.dragged = True
            if self.dragged:
                self.rotate(*event.rel)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.press:
            if not self.dragged and self.state == "playing":
                snake = self.snake_at(event.pos)
                if snake:
                    self.send(snake)
            self.press, self.dragged = None, False
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
