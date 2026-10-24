"""Snake Escape -- send every snake off a box, one at a time.

The snakes lie on the faces of a box, their bodies bending round its edges
from one face to the next. Click a snake and it slithers straight ahead, the
way its arrow points, across the face its head is on and off the edge into
space. It only gets out if nothing is in the way; bump into another snake and
you lose a life, and three bumps end the round. Drag to turn the box and see
the faces round the back. Every puzzle is generated on the spot and can always
be cleared, though only a few snakes are free to go at any moment.

Controls: click a snake to send it off, drag to turn the box.
          N new puzzle, R restart (a new puzzle once solved),
          G switch between Metal and plain pygame drawing, Esc quit.

On a Mac with pyobjc-framework-Metal installed, the box and the snakes on it
are ray traced by a Metal compute shader: a box of polished black glass with
rounded edges and shiny tube-shaped snakes.
Snakes on the move are drawn over that with pygame. Elsewhere everything is
drawn with pygame polygons. The snakes are always drawn with pygame.
"""
import math
import random
import struct
import sys

import pygame

try:
    import Metal    # pyobjc-framework-Metal, on macOS only
except ImportError:
    Metal = None

WIDTH, HEIGHT = 860, 880
FPS = 60
CENTER = (WIDTH // 2, 440)        # where the middle of the box is drawn
REACH = 330                       # pixels from there to the box's farthest corner
CAMERA = 5 * REACH                # pixels from there to the eye; nearer looks more 3D
NEAR = 0.2 * CAMERA               # closest to the eye a point is drawn as being
EXIT_SPEED, EXIT_ACCEL = 10, 60   # cells per second, and per second squared
BUMP_TIME = 0.45                  # seconds for a blocked snake to lunge and return
HURT_TIME = 0.7                   # seconds the red flash takes to fade after a bump
SHAKE = 11                        # pixels the screen shakes at a bump, more on the last life
SPARKS = 46                       # sparks thrown out where a blocked snake hits
HEART_BREAK = 0.9                 # seconds for a lost heart to break and fall away
SLAM_TIME = 0.28                  # seconds for "Out of lives" to slam down
DRAG = 0.008                      # radians the box turns per pixel dragged
CLICK_SLOP = 5                    # pixels the mouse may wander in a click
TILT, SPIN = 0.45, 0.6            # radians the box is tipped forward and turned at the start

BOX = (12, 12, 12)                # cells along x, y (up) and z
UNIT = REACH / math.hypot(*BOX)   # pixels per half cell
BODY = 0.5                        # how wide a snake is, in half cells
LIVES = 3

STRAIGHT_CHANCE = 0.35  # how often a snake's body carries straight on
TRIES = 60              # random attempts at fitting in one more snake
CHAINS = 10             # chains of snakes per box: each one is a snake free to go
ATTEMPTS = 40           # boxes built per puzzle; the one with most snakes is kept
ARM = 2                 # how far a new snake first reaches each way; short ones pack better

BG_TOP, BG_BOTTOM = (46, 62, 92), (0, 0, 0)
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


# ── Metal box ───────────────────────────────────────────────────────────────
# A small ray tracer on the GPU, one thread per pixel, four rays per pixel.
# The box is polished black glass with rounded edges, mirroring a bright photo
# studio, and the snakes lying on it are shiny raised tubes that cast little
# shadows, all in front of a blue gradient.
# The rays use the same perspective as SnakeEscape.project, so anything
# pygame draws on top still lines up.
#
# The world here is view space, in pixels: x right, y down, z away from the
# eye, the box's middle at the origin and the eye at (0, 0, -CAMERA). Box
# space is in half cells from the box's middle; the view rotation takes box
# space to view space.
SHADER = """
#include <metal_stdlib>
using namespace metal;

constant float3 BOX = float3(BOX_X, BOX_Y, BOX_Z);
constant float3 LIGHT = float3(LIGHT_X, LIGHT_Y, LIGHT_Z);   // towards the light

struct Scene {
    float3 r0, r1, r2;                 // rows of the view rotation
    device const uchar4 *cells;        // rgb, and the snake's shape there in a
    float hurt;                        // 1 just after a bump, fading to 0
};

float3 to_box(Scene s, float3 v) { return v.x * s.r0 + v.y * s.r1 + v.z * s.r2; }
float3 to_view(Scene s, float3 v) { return float3(dot(s.r0, v), dot(s.r1, v), dot(s.r2, v)); }
float comp(float3 v, int i) { return i == 0 ? v.x : (i == 1 ? v.y : v.z); }
float3 unit(int i) { return float3(i == 0, i == 1, i == 2); }
float3 linear(float3 c) { return pow(c / 255.0f, 2.2f); }

// Where a ray first goes into the box: the distance along it (-1 for a miss),
// and the axis of the face it goes in through.
float hit_box(Scene s, float3 origin, float3 dir, thread int &axis)
{
    float3 o = to_box(s, origin) / UNIT, d = to_box(s, dir) / UNIT;
    d = select(d, float3(1e-7f), fabs(d) < 1e-7f);
    float3 ta = (-BOX - o) / d, tb = (BOX - o) / d;
    float3 tn = min(ta, tb), tf = max(ta, tb);
    float near = max(max(tn.x, tn.y), tn.z), far = min(min(tf.x, tf.y), tf.z);
    if (near > far || near <= 0.0f)
        return -1.0f;
    axis = tn.x == near ? 0 : (tn.y == near ? 1 : 2);
    return near;
}

// A snake on a face, near the point (u, v) in half cells from the face's
// corner: how far the point is from the snake's middle line, which way that
// is, and the snake's colour. `arrow` says the point is on a head's arrow.
struct Body { float dist; float2 away; float3 color; bool arrow; };

Body snake_at(Scene s, int face, int a, int b, float u, float v)
{
    Body body = { 1e9f, float2(0.0f), float3(0.0f), false };
    int iu = clamp(int(u / 2.0f), 0, int(comp(BOX, a)) - 1);
    int iv = clamp(int(v / 2.0f), 0, int(comp(BOX, b)) - 1);
    uchar4 cell = s.cells[(face * SIDE + iu) * SIDE + iv];
    if (cell.a == 0)
        return body;
    body.color = float3(cell.rgb);
    float2 p = float2(u - (2 * iu + 1), v - (2 * iv + 1));
    const float2 ways[4] = { float2(1, 0), float2(-1, 0), float2(0, 1), float2(0, -1) };
    for (int k = 0; k < 4; k++) {
        if (!(cell.a & (1 << k)))
            continue;
        float2 near = ways[k] * clamp(dot(p, ways[k]), 0.0f, 1.0f);
        float d = length(p - near);
        if (d < body.dist) {
            body.dist = d;
            body.away = d > 1e-5f ? (p - near) / d : float2(0.0f);
        }
    }
    if (cell.a & 16) {
        float2 ahead = ways[(cell.a >> 5) & 3], side = float2(-ahead.y, ahead.x);
        float along = dot(p, ahead), across = dot(p, side);
        if (along > -0.16f && along < 0.66f && fabs(across) < 0.48f * (0.66f - along) / 0.82f) {
            body.arrow = true;
            body.dist = 0.0f;
            body.away = float2(0.0f);
        }
    }
    return body;
}

// A rectangular studio light seen in the direction `dir`: `centre` is the
// way to its middle, and `w` and `h` its half sizes, as tangents of angles.
float softbox(float3 dir, float3 centre, float w, float h)
{
    float facing = dot(dir, centre);
    if (facing <= 0.0f)
        return 0.0f;
    float3 across = normalize(cross(fabs(centre.y) > 0.9f ? float3(0, 0, 1) : float3(0, 1, 0), centre));
    float3 along = cross(centre, across);
    float x = fabs(dot(dir, across)) / facing, y = fabs(dot(dir, along)) / facing;
    return smoothstep(w, w * 0.8f, x) * smoothstep(h, h * 0.8f, y);
}

// The photo studio the box reflects: dark walls, a pale table underneath,
// and soft boxes overhead, behind and to the sides; just after a bump the
// whole studio flares red
float3 environment(float3 dir, float hurt)
{
    float3 color = mix(float3(0.03f), float3(0.3f), smoothstep(-0.1f, 0.9f, -dir.y));
    if (dir.y > 0.0f)
        color = mix(color, float3(0.7f), smoothstep(0.0f, 0.35f, dir.y));
    color += 9.0f * softbox(dir, float3(0.0f, -1.0f, 0.0f), 0.9f, 0.6f);
    color += 0.5f * softbox(dir, normalize(float3(0.0f, -0.45f, 0.9f)), 0.9f, 0.25f);
    color += 8.0f * softbox(dir, normalize(float3(-0.85f, -0.25f, -0.45f)), 0.14f, 0.6f);
    color += 4.0f * softbox(dir, normalize(float3(0.8f, -0.3f, 0.5f)), 0.12f, 0.55f);
    color += hurt * float3(2.5f, 0.15f, 0.1f) * (0.3f + 0.7f * smoothstep(-0.6f, 0.8f, -dir.y));
    return color;
}

float hash(float2 p) { return fract(sin(dot(p, float2(127.1f, 311.7f))) * 43758.5453f); }

// What the box looks like where a ray hits it: polished black glass, its
// edges rounded off, with the snakes lying on it as shiny coloured tubes
float3 shade_box(Scene s, float3 origin, float3 dir, float t, int axis)
{
    float3 p = to_box(s, origin + t * dir) / UNIT + BOX;   // half cells from the corner
    float side = comp(p, axis) > comp(BOX, axis) ? 1.0f : -1.0f;
    int face = 2 * axis + (side > 0.0f);
    int a = axis == 0 ? 1 : 0, b = axis == 2 ? 1 : 2;
    float u = comp(p, a), v = comp(p, b);
    float3 up = unit(axis) * side, ua = unit(a), ub = unit(b);
    float3 light = to_box(s, LIGHT);

    // Round the edges off: near one, the face turns towards the next face,
    // up to halfway at the edge itself, where the two meet
    float ea = clamp(1.0f - min(u, 2.0f * comp(BOX, a) - u) / RIM, 0.0f, 1.0f);
    float eb = clamp(1.0f - min(v, 2.0f * comp(BOX, b) - v) / RIM, 0.0f, 1.0f);
    float3 out_a = u < comp(BOX, a) ? -ua : ua, out_b = v < comp(BOX, b) ? -ub : ub;
    float3 normal = normalize(up + tan(ea * 0.785f) * out_a + tan(eb * 0.785f) * out_b);

    float3 albedo = linear(FACE_COLOR);
    float gloss = 1.0f, base = 0.03f, shadow = 1.0f;
    float glitter = 0.0f;

    // A snake on the cell: a raised tube, or the flat arrow on its head
    Body body = snake_at(s, face, a, b, u, v);
    float width = SNAKE_WIDTH;
    float pixel = t / UNIT;                // half cells across a pixel here
    float inside = smoothstep(width + pixel * 0.5f, width - pixel * 0.5f, body.dist);
    if (inside > 0.0f) {
        float h = clamp(body.dist / width, 0.0f, 0.95f);
        float3 tube = normalize(normal * sqrt(1.0f - h * h) + (body.away.x * ua + body.away.y * ub) * h);
        if (body.arrow)
            tube = normal;
        albedo = mix(albedo, linear(body.color), inside);
        normal = normalize(mix(normal, tube, inside));
        gloss = mix(gloss, 0.7f, inside);
    } else {
        if (dot(light, up) > 0.05f) {
            // The shadow of a nearby snake, which stands proud of the face
            float lift = width * 1.4f / dot(light, up);
            float su = u + dot(light, ua) * lift, sv = v + dot(light, ub) * lift;
            Body caster = snake_at(s, face, a, b, su, sv);
            shadow = 1.0f - 0.8f * smoothstep(width + 0.15f, width - 0.15f, caster.dist);
        }
        // Faint glitter in the glass
        float2 speck = floor(float2(u, v) * 7.0f) + face * 101.0f;
        if (hash(speck) > 0.997f)
            glitter = 0.08f * hash(speck + 7.0f) * (1.0f - smoothstep(0.1f, 0.3f, pixel));
    }

    // Light it, in view space
    float3 n = to_view(s, normal), eye = -normalize(dir);
    float diffuse = max(dot(n, LIGHT), 0.0f) * shadow;
    float fill = 0.3f * max(dot(n, eye), 0.0f);
    float spec = pow(max(dot(n, normalize(LIGHT + eye)), 0.0f), 90.0f) * inside;
    float fresnel = base + (1.0f - base) * pow(1.0f - max(dot(n, eye), 0.0f), 5.0f);
    float3 mirror = environment(reflect(-eye, n), s.hurt);
    float3 color = albedo * (0.1f + diffuse + fill + s.hurt * float3(0.25f, 0.0f, 0.0f));
    color += spec * 1.2f * shadow;
    color += mirror * fresnel * gloss * mix(1.0f, 0.4f + 0.6f * shadow, 1.0f - inside);
    return color + glitter;
}

// Blue at the top fading to black at the bottom, with a soft glow behind the box
float3 background(float2 pixel)
{
    float down = pixel.y / (HEIGHT - 1);
    float3 sky = mix(linear(BG_TOP), linear(BG_BOTTOM), down);
    float glow = exp(-length(pixel - float2(CENTER_X, CENTER_Y)) / 380.0f) * (1.0f - down) * (1.0f - down);
    return sky + glow * 0.05f * float3(0.35f, 0.5f, 1.0f);
}

float3 trace(Scene s, float2 pixel)
{
    float3 origin = float3(0.0f, 0.0f, -CAMERA);
    float3 dir = float3(pixel.x - CENTER_X, pixel.y - CENTER_Y, CAMERA);
    int axis;
    float t = hit_box(s, origin, dir, axis);
    return t > 0.0f ? shade_box(s, origin, dir, t, axis) : background(pixel);
}

kernel void draw_box(device uchar4 *out [[buffer(0)]],
                     constant float *view [[buffer(1)]],
                     device const uchar4 *cells [[buffer(2)]],
                     uint2 pos [[thread_position_in_grid]])
{
    if (pos.x >= WIDTH || pos.y >= HEIGHT)
        return;
    Scene s = { float3(view[0], view[1], view[2]), float3(view[3], view[4], view[5]),
                float3(view[6], view[7], view[8]), cells, view[9] };
    // Four rays in a rotated grid
    const float2 offsets[4] = { float2(0.375f, 0.125f), float2(0.875f, 0.375f),
                                float2(0.125f, 0.625f), float2(0.625f, 0.875f) };
    float3 sum = 0.0f;
    for (int i = 0; i < 4; i++)
        sum += trace(s, float2(pos) + offsets[i]);
    float3 color = sum / 4.0f;
    color = color / (1.0f + 0.25f * color);                 // soften bright highlights
    float2 q = float2(pos) / float2(WIDTH, HEIGHT) - 0.5f;
    color *= 1.0f - 0.35f * dot(q, q);                      // vignette
    color = pow(clamp(color, 0.0f, 1.0f), 1.0f / 2.2f) * 255.0f;
    out[pos.y * WIDTH + pos.x] = uchar4(uchar3(round(color)), 255);
}
"""

SIDE = max(BOX)  # cells along a face's side, as the shader's table of cells sees it


def cell_slot(cell, box):
    """Where a cell sits in the shader's table: its face, then row and column."""
    out = normal(cell, box)
    i = axis_of(out)
    a, b = (j for j in range(3) if j != i)
    return ((2 * i + (out[i] > 0)) * SIDE + cell[a] // 2) * SIDE + cell[b] // 2


def way(cell, other, box):
    """Which way `other` lies from a cell, across the cell's face: 0 to 3 for
    along the face's first axis forwards and back, then its second."""
    i = axis_of(normal(cell, box))
    a, b = (j for j in range(3) if j != i)
    if other[a] != cell[a]:
        return 0 if other[a] > cell[a] else 1
    return 2 if other[b] > cell[b] else 3


def snake_shape(snake, box):
    """For each of a snake's cells, its slot in the shader's table and a byte
    for its shape there: a bit for each way the body goes on to a
    neighbouring cell, then on the head a flag and the way the arrow points."""
    shape = []
    cells = snake.cells
    for k, cell in enumerate(cells):
        bits = 0
        for near in (cells[k - 1] if k else None, cells[k + 1] if k + 1 < len(cells) else None):
            if near:
                bits |= 1 << way(cell, near, box)
        if k == len(cells) - 1:
            bits |= 16 | way(cell, add(cell, snake.direction(box)), box) << 5
        shape.append((cell_slot(cell, box), bits))
    return shape


class MetalBox:
    """Ray traces the box, the snakes lying on it, and the scene round it, on
    the GPU with Metal."""

    def __init__(self):
        self.device = Metal.MTLCreateSystemDefaultDevice()
        if self.device is None:
            raise RuntimeError("no Metal device")

        def color(rgb):
            return "float3(%.1ff, %.1ff, %.1ff)" % tuple(rgb)

        light = (-0.45, -0.8, -0.4)
        size = math.sqrt(sum(v * v for v in light))
        defines = {
            "WIDTH": WIDTH, "HEIGHT": HEIGHT, "SIDE": SIDE,
            "CENTER_X": f"{CENTER[0]:.1f}f", "CENTER_Y": f"{CENTER[1]:.1f}f",
            "CAMERA": f"{CAMERA:.6f}f", "UNIT": f"{UNIT:.6f}f",
            "BOX_X": f"{BOX[0]:.1f}f", "BOX_Y": f"{BOX[1]:.1f}f", "BOX_Z": f"{BOX[2]:.1f}f",
            "LIGHT_X": f"{light[0] / size:.6f}f", "LIGHT_Y": f"{light[1] / size:.6f}f",
            "LIGHT_Z": f"{light[2] / size:.6f}f",
            "SNAKE_WIDTH": f"{BODY / 2:.3f}f", "RIM": "1.5f",
            "BG_TOP": color(BG_TOP), "BG_BOTTOM": color(BG_BOTTOM),
            "FACE_COLOR": color((6, 6, 8)),
        }
        header = "".join(f"#define {k} {v}\n" for k, v in defines.items())
        library, error = self.device.newLibraryWithSource_options_error_(header + SHADER, None, None)
        if library is None:
            raise RuntimeError(f"shader won't compile: {error}")
        self.pipeline, error = self.device.newComputePipelineStateWithFunction_error_(
            library.newFunctionWithName_("draw_box"), None)
        if self.pipeline is None:
            raise RuntimeError(f"no pipeline: {error}")
        self.queue = self.device.newCommandQueue()
        shared = Metal.MTLResourceStorageModeShared
        # The GPU writes the pixels into memory the CPU shares, and the surface
        # reads them straight from there, so nothing gets copied back
        size = WIDTH * HEIGHT * 4
        self.out = self.device.newBufferWithLength_options_(size, shared)
        self.surface = pygame.image.frombuffer(self.out.contents().as_buffer(size),
                                               (WIDTH, HEIGHT), "RGBX")
        self.table_size = 6 * SIDE * SIDE * 4
        self.cells = self.device.newBufferWithLength_options_(self.table_size, shared)
        self.table = self.cells.contents().as_buffer(self.table_size)
        width = self.pipeline.threadExecutionWidth()
        self.group = Metal.MTLSizeMake(width, self.pipeline.maxTotalThreadsPerThreadgroup() // width, 1)

    def draw(self, screen, view, snakes, hurt=0.0):
        """`snakes` lists (shape, colour) for the snakes lying still on the box;
        `hurt` (0 to 1) bathes the box in red light."""
        table = bytearray(self.table_size)
        for shape, (r, g, b) in snakes:
            for slot, bits in shape:
                table[4 * slot: 4 * slot + 4] = bytes((r, g, b, bits))
        self.table[:] = table
        rotation = struct.pack("10f", *(v for row in view for v in row), hurt)
        commands = self.queue.commandBuffer()
        encoder = commands.computeCommandEncoder()
        encoder.setComputePipelineState_(self.pipeline)
        encoder.setBuffer_offset_atIndex_(self.out, 0, 0)
        encoder.setBytes_length_atIndex_(rotation, len(rotation), 1)
        encoder.setBuffer_offset_atIndex_(self.cells, 0, 2)
        encoder.dispatchThreads_threadsPerThreadgroup_(Metal.MTLSizeMake(WIDTH, HEIGHT, 1), self.group)
        encoder.endEncoding()
        commands.commit()
        commands.waitUntilCompleted()
        screen.blit(self.surface, (0, 0))


def metal_box():
    """A MetalBox, or None if Metal can't be used here."""
    if Metal is None:
        return None
    try:
        return MetalBox()
    except Exception as error:  # no device, shader won't build...
        print(f"Metal unavailable, drawing with pygame: {error}", file=sys.stderr)
        return None


def heart_surface(color, scale=1.0):
    """A heart, drawn the size the HUD shows it times `scale`, on a clear surface."""
    size = round(30 * scale)
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    k = size / 30
    for x in (9, 21):
        pygame.draw.circle(surface, color, (x * k, 11 * k), 7 * k)
    pygame.draw.polygon(surface, color, [(3 * k, 14 * k), (27 * k, 14 * k), (15 * k, 28 * k)])
    return surface


def make_vignette():
    """Red that is clear in the middle of the window and thick round its edges."""
    surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    steps = 48
    for i in range(steps):
        f = 1 - i / steps                       # 1 at the edge, towards 0 in the middle
        rect = pygame.Rect(0, 0, WIDTH * (0.5 + f * 1.0), HEIGHT * (0.5 + f * 1.0))
        rect.center = (WIDTH // 2, HEIGHT // 2)
        pygame.draw.ellipse(surface, (220, 20, 20, round(230 * f ** 2.2)), rect)
    return surface


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
        self.vignette = make_vignette()
        self.gpu = metal_box()
        self.use_gpu = self.gpu is not None
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
        self.shapes = {snake: snake_shape(snake, BOX) for snake in self.snakes}
        self.leaving = []   # [snake, cells travelled, speed] for snakes on their way out
        self.bumps = []     # [snake, seconds so far, free cells ahead] for blocked ones
        self.lives = LIVES
        self.state = "playing"  # playing / won / lost
        self.hurt = 0.0         # 1 at a bump, fading to 0: the red flash
        self.shake = 0.0        # how hard the screen shakes, fading to 0
        self.sparks = []        # [x, y, vx, vy, seconds left, colour] in screen pixels
        self.rings = []         # [x, y, seconds so far]: shock waves at impacts
        self.breaking = []      # [heart number, seconds so far] for hearts just lost
        self.lost_time = 0.0    # seconds since the last life went

    def send(self, snake):
        """Sets a snake off; it leaves if its way is clear and bumps if not."""
        if any(bump[0] is snake for bump in self.bumps):
            return
        ray = snake.ray(BOX)
        blocked = [i for i, cell in enumerate(ray) if cell in self.grid]
        if blocked:
            # The life goes when the snake hits, halfway through its lunge;
            # until then don't let more bumps than there are lives start
            if sum(not bump[3] for bump in self.bumps) < self.lives:
                self.bumps.append([snake, 0.0, blocked[0], False])
            return
        for cell in snake.cells:
            del self.grid[cell]
        self.snakes.remove(snake)
        self.leaving.append([snake, 0.0, EXIT_SPEED])
        if not self.snakes:
            self.state = "won"

    def impact(self, snake, free):
        """A blocked snake hits the one in its way: a life goes, with a bang."""
        self.lives -= 1
        last = self.lives == 0
        if last:
            self.state, self.lost_time = "lost", 0.0
        self.hurt = 1.0
        self.shake = 1.6 if last else 1.0
        self.breaking.append([self.lives, 0.0])
        direction = snake.direction(BOX)
        x, y = self.project(add(snake.ray(BOX)[free], mul(direction, -1)))
        self.rings.append([x, y, 0.0])
        colors = [WHITE, TEXT, BUMP, snake.color]
        for _ in range(SPARKS * (2 if last else 1)):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(120, 700) * (1.3 if last else 1)
            self.sparks.append([x, y, math.cos(angle) * speed, math.sin(angle) * speed - 150,
                                random.uniform(0.35, 0.8), random.choice(colors)])

    def update(self, dt):
        for item in self.leaving:
            item[2] += EXIT_ACCEL * dt
            item[1] += item[2] * dt
        # Gone once the tail is well clear of the window
        self.leaving = [item for item in self.leaving if item[1] < item[0].exit_length(BOX)]
        for item in self.bumps:
            item[1] += dt
            if not item[3] and item[1] >= BUMP_TIME / 2:
                item[3] = True
                self.impact(item[0], item[2])
        self.bumps = [item for item in self.bumps if item[1] < BUMP_TIME]

        self.hurt = max(0.0, self.hurt - dt / HURT_TIME)
        self.shake = max(0.0, self.shake - dt * 2.2)
        for spark in self.sparks:
            spark[2] *= 1 - 2.5 * dt                # air drag
            spark[3] += 1400 * dt                   # gravity
            spark[0] += spark[2] * dt
            spark[1] += spark[3] * dt
            spark[4] -= dt
        self.sparks = [spark for spark in self.sparks if spark[4] > 0]
        for ring in self.rings:
            ring[2] += dt
        self.rings = [ring for ring in self.rings if ring[2] < 0.4]
        for item in self.breaking:
            item[1] += dt
        self.breaking = [item for item in self.breaking if item[1] < HEART_BREAK]
        if self.state == "lost":
            self.lost_time += dt

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
        bumping = {id(item[0]): item for item in self.bumps}
        hovered = None
        if self.state == "playing" and not self.dragged:
            hovered = self.snake_at(pygame.mouse.get_pos())

        def color(snake):
            if snake is hovered:
                return [min(255, c + 45) for c in snake.color]
            return snake.color

        if self.use_gpu:
            # The GPU draws the box and the snakes lying still on it
            self.gpu.draw(self.screen, self.view, [
                (self.shapes[snake], color(snake))
                for snake in self.snakes if id(snake) not in bumping], self.hurt ** 2)
        else:
            self.screen.blit(self.backdrop, (0, 0))
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
            for snake in self.snakes:
                if id(snake) not in bumping:
                    self.draw_snake(snake, color=color(snake))

        for snake, t, free, hit in bumping.values():
            lunge = (free + 0.25) * (1 - abs(2 * t / BUMP_TIME - 1))
            flicker = hit and int(t * 30) % 2
            self.draw_snake(snake, lunge, WHITE if flicker else BUMP)
        for snake, travelled, _ in self.leaving:
            self.draw_snake(snake, travelled)

    def draw_effects(self):
        """Sparks, shock waves and the red flash after a bump."""
        for x, y, t in self.rings:
            f = t / 0.4
            shade = [round(c * (1 - f)) for c in (255, 200, 160)]
            pygame.draw.circle(self.screen, shade, (x, y), 10 + 110 * f ** 0.6,
                               max(1, round(6 * (1 - f))))
        for x, y, vx, vy, left, color in self.sparks:
            fade = min(1.0, left / 0.3)
            shade = [round(c * fade) for c in color]
            pygame.draw.line(self.screen, shade, (x, y), (x - vx * 0.025, y - vy * 0.025),
                             2 if left > 0.2 else 1)
        if self.hurt > 0:
            flash = self.hurt ** 3
            self.screen.fill((round(70 * flash), 0, 0),
                             special_flags=pygame.BLEND_RGB_ADD)
            self.vignette.set_alpha(round(255 * self.hurt))
            self.screen.blit(self.vignette, (0, 0))

    def draw_heart(self, x, y, color):
        heart = heart_surface(color)
        self.screen.blit(heart, heart.get_rect(center=(x, y)))

    def draw_breaking_heart(self, x, y, t):
        """A just-lost heart: it swells white, then splits and falls away."""
        if t < 0.12:
            f = t / 0.12
            heart = heart_surface([round(a + (b - a) * f) for a, b in zip(HEART, WHITE)], 1 + 0.6 * f)
            self.screen.blit(heart, heart.get_rect(center=(x, y)))
            return
        t -= 0.12
        heart = heart_surface(HEART, 1.6)
        w, h = heart.get_size()
        alpha = round(255 * max(0.0, 1 - t / (HEART_BREAK - 0.12)))
        for side in (-1, 1):
            half = heart.subsurface((0 if side < 0 else w // 2, 0, w // 2, h)).copy()
            half = pygame.transform.rotate(half, -side * 260 * t)
            half.set_alpha(alpha)
            cx = x + side * (w // 4 + 70 * t)
            cy = y - 90 * t + 700 * t * t
            self.screen.blit(half, half.get_rect(center=(cx, cy)))

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
        for i, t in self.breaking:
            self.draw_breaking_heart(right - 16 - i * 34, 38, t)
        self.draw_text("Drag to turn the box - click a snake to send it off its face",
                       self.small_font, TEXT_DIM, center=(WIDTH // 2, HEIGHT - 60))
        keys = "N new puzzle   R restart   Esc quit"
        if self.gpu:
            keys = f"N new puzzle   R restart   G {'Metal' if self.use_gpu else 'pygame'} drawing   Esc quit"
        self.draw_text(keys, self.small_font, TEXT_DIM, center=(WIDTH // 2, HEIGHT - 34))

        if self.state == "won":
            self.draw_text("All out!", self.big_font, TEXT, shadow=3, center=CENTER)
            self.draw_text("R = new puzzle", self.small_font, WHITE, shadow=2,
                           center=(CENTER[0], CENTER[1] + 50))
        elif self.state == "lost":
            # The screen dims, then the words slam down from huge
            dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            dim.fill((0, 0, 0, round(130 * min(1.0, self.lost_time / 0.5))))
            self.screen.blit(dim, (0, 0))
            f = min(1.0, self.lost_time / SLAM_TIME)
            scale = 1 + 3 * (1 - f) ** 2
            for color, offset in (((0, 0, 0), 4), (BUMP, 0)):
                text = self.big_font.render("Out of lives", True, color)
                text = pygame.transform.smoothscale_by(text, scale)
                text.set_alpha(round(255 * min(1.0, 0.3 + f)))
                self.screen.blit(text, text.get_rect(center=(CENTER[0] + offset, CENTER[1] + offset)))
            if f == 1:
                self.draw_text("R = try again   N = new puzzle", self.small_font, WHITE, shadow=2,
                               center=(CENTER[0], CENTER[1] + 50))

    def draw(self):
        self.draw_board()
        if self.shake > 0:
            # Shift the whole picture; the gradient's top and bottom rows
            # smear into the gap, which can't be seen
            size = SHAKE * self.shake ** 2
            self.screen.scroll(round(random.uniform(-size, size)), round(random.uniform(-size, size)))
        self.draw_effects()
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
        elif key == pygame.K_g and self.gpu:
            self.use_gpu = not self.use_gpu
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
