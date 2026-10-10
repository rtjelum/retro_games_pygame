"""
Mastermind - a classic code-breaking game.
The computer picks a secret code of 4 colors. You guess it.
You get 6 attempts. After each guess, you get feedback:
  Black peg = correct color, correct position
  White peg = correct color, wrong position

Controls:
  Click a color (or press 1-6) to place it, click a placed peg to remove it
  Enter / Submit button = submit guess, Backspace = remove last peg
  R = new game (when finished), Esc = quit
"""

import pygame
import random
import sys

# -----------------------------
#  Constants
# -----------------------------
WIDTH, HEIGHT = 600, 790
FPS = 60

# Colors (RGB)
COLORS = [
    (225, 50, 50),    # Red
    (50, 190, 80),    # Green
    (50, 110, 235),   # Blue
    (245, 205, 40),   # Yellow
    (170, 70, 220),   # Purple
    (40, 200, 215),   # Cyan
]

BG_TOP = (40, 44, 78)
BG_BOTTOM = (10, 10, 20)
GOLD = (255, 215, 120)
WHITE = (255, 255, 255)
GRAY = (150, 150, 150)
BLACK = (0, 0, 0)
BLACK_PEG = (28, 28, 34)
WHITE_PEG = (240, 240, 240)

# -----------------------------
#  Game constants
# -----------------------------
CODE_LENGTH = 4
MAX_ATTEMPTS = 6
PEG_SIZE = 44
PEG_STEP = 62
FB_SIZE = 18
FB_STEP = 24
ROW_HEIGHT = 66
TRAY_H = 60

# -----------------------------
#  UI layout
# -----------------------------
# Top: title, then the shielded secret code
# Middle: guess rows (6 rows) with a 2x2 feedback block each
# Bottom: color picker tray + submit button

TITLE_Y = 18
TRAY_X, TRAY_W = 60, 480
SECRET_Y = 88
GUESS_START_Y = 160
PEG_X = 118
FB_X = 424
PICKER_TRAY = pygame.Rect(100, 590, 400, 68)
PICKER_X = (WIDTH - (len(COLORS) - 1) * PEG_STEP - PEG_SIZE) // 2
PICKER_Y = PICKER_TRAY.y + (PICKER_TRAY.h - PEG_SIZE) // 2
BUTTON = pygame.Rect(220, 684, 160, 46)
MESSAGE_Y = 762

FLY_MS = 420
POP_MS = 260
POP_STAGGER_MS = 130
REVEAL_MS = 600


# -----------------------------
#  Drawing helpers
# -----------------------------
def lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def ease_out_back(t):
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def gradient_rect(w, h, top, bottom, radius=0):
    """Vertical gradient, optionally clipped to a rounded rectangle."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        pygame.draw.line(surf, lerp(top, bottom, y / max(1, h - 1)), (0, y), (w, y))
    if radius:
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(mask, WHITE, (0, 0, w, h), border_radius=radius)
        surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return surf


def make_sphere(color, size):
    """Glossy ball lit from the top-left, rendered 4x and scaled down for smooth edges."""
    big = size * 4
    r = big / 2
    surf = pygame.Surface((big, big), pygame.SRCALPHA)
    dark = lerp(color, BLACK, 0.68)
    steps = 48
    for k in range(steps):
        t = k / (steps - 1)
        col = lerp(dark, color, t * 1.7)
        if t > 0.72:
            col = lerp(color, WHITE, (t - 0.72) / 0.28 * 0.45)
        off = r * 0.36 * t
        pygame.draw.circle(surf, col, (r - off, r - off), r * (1 - 0.93 * t))

    # Soft specular highlight
    gloss = pygame.Surface((big, big), pygame.SRCALPHA)
    for k in range(8):
        t = k / 7
        w, h = r * 0.62 * (1 - 0.7 * t), r * 0.4 * (1 - 0.7 * t)
        rect = pygame.Rect(0, 0, w, h)
        rect.center = (r * 0.66, r * 0.5)
        pygame.draw.ellipse(gloss, (255, 255, 255, int(20 + 190 * t)), rect)
    surf.blit(gloss, (0, 0))
    return pygame.transform.smoothscale(surf, (size, size))


def make_shadow(size):
    """Soft round drop shadow."""
    s = int(size * 1.6)
    surf = pygame.Surface((s, s), pygame.SRCALPHA)
    steps = 16
    for k in range(steps):
        t = k / (steps - 1)
        pygame.draw.circle(surf, (0, 0, 0, int(120 * t * t)), (s // 2, s // 2),
                           int(s / 2 * (1 - 0.55 * t)))
    return surf


def make_hole(size):
    """Drilled hole: bright lower-right rim, dark recess shaded from the top-left."""
    big = size * 4
    r = big / 2
    surf = pygame.Surface((big, big), pygame.SRCALPHA)
    pygame.draw.circle(surf, (120, 128, 170), (r, r), r)
    pygame.draw.circle(surf, (12, 13, 24), (r - r * 0.05, r - r * 0.05), r * 0.94)
    steps = 12
    for k in range(steps):
        t = k / (steps - 1)
        off = r * 0.12 * t
        pygame.draw.circle(surf, lerp((8, 9, 18), (40, 44, 70), t), (r + off, r + off),
                           r * (0.9 - 0.2 * t))
    return pygame.transform.smoothscale(surf, (size, size))


class Mastermind:
    def __init__(self):
        pygame.init()
        self.window = pygame.display.set_mode((WIDTH, HEIGHT))
        # Draw on an opaque canvas: alpha blits straight onto the display surface
        # come out as black boxes on drivers that give it an alpha channel (macOS)
        self.screen = pygame.Surface((WIDTH, HEIGHT), 0, 24)
        pygame.display.set_caption("Mastermind")
        self.clock = pygame.time.Clock()
        self.dt = 0
        self.hand_cursor = False

        self.font_title = pygame.font.SysFont("Georgia", 42, bold=True)
        self.font_normal = pygame.font.SysFont("Arial", 20, bold=True)
        self.font_small = pygame.font.SysFont("Arial", 15, bold=True)

        self.sprites = {}
        self.shadow = make_shadow(PEG_SIZE)
        self.fb_shadow = make_shadow(FB_SIZE)
        self.background = self.build_background()
        self.shield = self.build_shield()

        self.reset_game()

    def reset_game(self):
        self.secret_code = [random.choice(COLORS) for _ in range(CODE_LENGTH)]
        self.guesses = []
        self.feedback = []
        self.current_guess = [None] * CODE_LENGTH
        self.attempt = 0
        self.game_over = False
        self.won = False
        self.message = ""
        # Animation state
        self.flights = {}         # (row, slot) -> (tick the peg was picked, picker position it left)
        self.feedback_times = []  # tick each row's feedback was revealed
        self.game_over_time = 0
        self.confetti = []

    # -----------------------------
    #  Layout
    # -----------------------------
    def peg_pos(self, row, i):
        return PEG_X + i * PEG_STEP, GUESS_START_Y + row * ROW_HEIGHT + (TRAY_H - PEG_SIZE) // 2

    def secret_pos(self, i):
        return PEG_X + i * PEG_STEP, SECRET_Y + (TRAY_H - PEG_SIZE) // 2

    def picker_pos(self, i):
        return PICKER_X + i * PEG_STEP, PICKER_Y

    def feedback_pos(self, row, k):
        y = GUESS_START_Y + row * ROW_HEIGHT + (TRAY_H - FB_STEP - FB_SIZE) // 2
        return FB_X + (k % 2) * FB_STEP, y + (k // 2) * FB_STEP

    def can_submit(self):
        return not self.game_over and None not in self.current_guess

    # -----------------------------
    #  Game logic
    # -----------------------------
    def generate_feedback(self, guess, secret):
        """Return (black_count, white_count)"""
        black = 0
        white = 0
        for i in range(CODE_LENGTH):
            if guess[i] == secret[i]:
                black += 1
        # Count total matching colors (regardless of position)
        total_match = 0
        for color in set(secret):  # each colour once, or repeats are counted twice
            total_match += min(guess.count(color), secret.count(color))
        white = total_match - black
        return black, white

    def place_color(self, color):
        if self.game_over or None not in self.current_guess:
            return
        slot = self.current_guess.index(None)
        self.current_guess[slot] = color
        self.flights[(len(self.guesses), slot)] = (pygame.time.get_ticks(),
                                                   self.picker_pos(COLORS.index(color)))

    def submit_guess(self):
        if self.game_over:
            return
        if None in self.current_guess:
            return

        black, white = self.generate_feedback(self.current_guess, self.secret_code)
        self.guesses.append(self.current_guess[:])
        self.feedback.append((black, white))
        self.feedback_times.append(pygame.time.get_ticks())
        self.attempt += 1

        if self.current_guess == self.secret_code:
            self.won = True
            self.game_over = True
            self.message = f"You cracked it in {self.attempt} attempt(s)!  Press R to play again"
            self.spawn_confetti()
        elif self.attempt >= MAX_ATTEMPTS:
            self.game_over = True
            self.message = "Out of attempts!  Press R to play again"
        else:
            self.current_guess = [None] * CODE_LENGTH

        if self.game_over:
            self.game_over_time = pygame.time.get_ticks()

    def spawn_confetti(self):
        for _ in range(160):
            self.confetti.append({
                "x": random.uniform(0, WIDTH),
                "y": random.uniform(-HEIGHT * 0.6, 0),
                "vx": random.uniform(-60, 60),
                "vy": random.uniform(120, 320),
                "w": random.randint(5, 10),
                "h": random.randint(8, 14),
                "phase": random.uniform(0, 6.28),
                "color": random.choice(COLORS + [GOLD, WHITE]),
            })

    # -----------------------------
    #  Static artwork
    # -----------------------------
    def sprite(self, color, size=PEG_SIZE):
        key = (color, size)
        if key not in self.sprites:
            self.sprites[key] = make_sphere(color, size)
        return self.sprites[key]

    def draw_tray(self, surface, rect, radius=16):
        """Raised slate panel with a soft shadow and a lit rim."""
        shadow = pygame.Surface((rect.w + 16, rect.h + 16), pygame.SRCALPHA)
        for k in range(8):
            pygame.draw.rect(shadow, (0, 0, 0, 8 + k * 9),
                             (k, k, rect.w + 16 - k * 2, rect.h + 16 - k * 2), border_radius=radius + 8 - k)
        surface.blit(shadow, (rect.x - 8, rect.y - 3))
        panel = gradient_rect(rect.w, rect.h, (58, 62, 92), (30, 32, 52), radius=radius)
        pygame.draw.rect(panel, (255, 255, 255, 50), panel.get_rect(), 2, border_radius=radius)
        surface.blit(panel, rect.topleft)

    def build_background(self):
        bg = pygame.Surface((WIDTH, HEIGHT), 0, 24)
        bg.blit(gradient_rect(WIDTH, HEIGHT, BG_TOP, BG_BOTTOM), (0, 0))

        # Spotlight glow behind the rows
        glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for k in range(30):
            t = k / 29
            pygame.draw.circle(glow, (110, 130, 230, int(46 * t * t)), (WIDTH // 2, 300),
                               int(460 * (1 - 0.8 * t)))
        bg.blit(glow, (0, 0))

        # Secret row
        self.draw_tray(bg, pygame.Rect(TRAY_X, SECRET_Y, TRAY_W, TRAY_H))
        hole = make_hole(PEG_SIZE + 4)
        for i in range(CODE_LENGTH):
            x, y = self.secret_pos(i)
            bg.blit(hole, (x - 2, y - 2))
        label = self.font_small.render("SECRET", True, (170, 178, 215))
        bg.blit(label, (FB_X + (FB_STEP + FB_SIZE) // 2 - label.get_width() // 2,
                        SECRET_Y + TRAY_H // 2 - label.get_height() // 2))

        # Guess rows
        small_hole = make_hole(FB_SIZE + 2)
        for row in range(MAX_ATTEMPTS):
            tray = pygame.Rect(TRAY_X, GUESS_START_Y + row * ROW_HEIGHT, TRAY_W, TRAY_H)
            self.draw_tray(bg, tray)
            num = self.font_normal.render(str(row + 1), True, (170, 178, 215))
            bg.blit(num, (TRAY_X + 26 - num.get_width() // 2, tray.centery - num.get_height() // 2))
            for i in range(CODE_LENGTH):
                x, y = self.peg_pos(row, i)
                bg.blit(hole, (x - 2, y - 2))
            for k in range(CODE_LENGTH):
                x, y = self.feedback_pos(row, k)
                bg.blit(small_hole, (x - 1, y - 1))

        # Color picker tray
        self.draw_tray(bg, PICKER_TRAY, radius=20)

        # Title: gold gradient text with a drop shadow
        text = self.font_title.render("MASTERMIND", True, WHITE)
        text.blit(gradient_rect(*text.get_size(), (255, 240, 180), (214, 140, 40)), (0, 0),
                  special_flags=pygame.BLEND_RGB_MULT)
        tx = WIDTH // 2 - text.get_width() // 2
        bg.blit(self.font_title.render("MASTERMIND", True, (0, 0, 0)), (tx + 2, TITLE_Y + 4))
        bg.blit(text, (tx, TITLE_Y))
        return bg

    def build_shield(self):
        """Metal cover hiding the secret code."""
        w, h = (CODE_LENGTH - 1) * PEG_STEP + PEG_SIZE + 24, TRAY_H - 6
        shield = gradient_rect(w, h, (112, 118, 140), (44, 48, 66), radius=14)
        pygame.draw.rect(shield, (255, 255, 255, 90), (0, 0, w, h - 2), 2, border_radius=14)
        pygame.draw.rect(shield, (0, 0, 0, 120), (0, 0, w, h), 2, border_radius=14)
        gloss = pygame.Surface((w - 12, h // 2 - 4), pygame.SRCALPHA)
        pygame.draw.rect(gloss, (255, 255, 255, 34), gloss.get_rect(), border_radius=10)
        shield.blit(gloss, (6, 5))
        for i in range(CODE_LENGTH):
            mark = self.font_normal.render("?", True, (226, 230, 244))
            shield.blit(mark, (12 + i * PEG_STEP + PEG_SIZE // 2 - mark.get_width() // 2,
                               h // 2 - mark.get_height() // 2))
        return shield

    # -----------------------------
    #  Per-frame drawing
    # -----------------------------
    def draw_peg(self, surface, x, y, color, size=PEG_SIZE, lift=0, scale=1.0):
        """Ball at (x, y) floating `lift` pixels above its shadow."""
        shadow = self.shadow if size == PEG_SIZE else self.fb_shadow
        cx, cy = x + size // 2, y + size // 2
        offset = size * 0.1 + lift * 0.35
        surface.blit(shadow, (cx - shadow.get_width() // 2 + offset,
                              cy - shadow.get_height() // 2 + offset * 1.4))
        ball = self.sprite(color, size)
        if scale != 1.0:
            s = max(1, int(size * scale))
            ball = pygame.transform.smoothscale(ball, (s, s))
        surface.blit(ball, (cx - ball.get_width() // 2, cy - ball.get_height() // 2 - lift))

    def draw_feedback(self, surface, row, black, white, now):
        """Small pegs in the 2x2 block: black ones first, then white, popping in one by one."""
        for k in range(black + white):
            t = (now - self.feedback_times[row] - k * POP_STAGGER_MS) / POP_MS
            if t <= 0:
                continue
            x, y = self.feedback_pos(row, k)
            self.draw_peg(surface, x, y, BLACK_PEG if k < black else WHITE_PEG, FB_SIZE,
                          scale=ease_out_back(min(1.0, t)))

    def draw_button(self, mouse, pressed):
        enabled = self.can_submit() or self.game_over
        hover = enabled and BUTTON.collidepoint(mouse)
        down = hover and pressed
        if not enabled:
            top, bottom, base = (96, 100, 112), (66, 70, 82), (38, 40, 50)
        elif hover:
            top, bottom, base = (96, 226, 122), (30, 150, 62), (12, 78, 30)
        else:
            top, bottom, base = (74, 204, 102), (22, 132, 52), (12, 78, 30)

        depth = 5
        pygame.draw.rect(self.screen, base, BUTTON.move(0, depth), border_radius=12)
        face = gradient_rect(BUTTON.w, BUTTON.h, top, bottom, radius=12)
        gloss = pygame.Surface((BUTTON.w - 10, BUTTON.h // 2 - 4), pygame.SRCALPHA)
        pygame.draw.rect(gloss, (255, 255, 255, 50), gloss.get_rect(), border_radius=9)
        face.blit(gloss, (5, 4))
        text = self.font_normal.render("New Game" if self.game_over else "Submit", True,
                                       WHITE if enabled else (170, 172, 180))
        shade = self.font_normal.render("New Game" if self.game_over else "Submit", True, (0, 0, 0))
        tx, ty = BUTTON.w // 2 - text.get_width() // 2, BUTTON.h // 2 - text.get_height() // 2
        shade.set_alpha(110)
        face.blit(shade, (tx + 1, ty + 2))
        face.blit(text, (tx, ty))
        self.screen.blit(face, BUTTON.move(0, depth - 1 if down else 0))

    def draw_confetti(self, now):
        for p in self.confetti:
            p["x"] += p["vx"] * self.dt
            p["y"] += p["vy"] * self.dt
            # Flutter: squash the height as the piece "spins"
            h = max(2, int(p["h"] * abs(pygame.math.Vector2(1, 0).rotate(now * 0.5 + p["phase"] * 57).x)))
            pygame.draw.rect(self.screen, p["color"], (p["x"], p["y"], p["w"], h))
        self.confetti = [p for p in self.confetti if p["y"] < HEIGHT + 20]

    def draw(self):
        now = pygame.time.get_ticks()
        mouse = pygame.mouse.get_pos()
        pressed = pygame.mouse.get_pressed()[0]
        pulse = 0.5 + 0.5 * pygame.math.Vector2(1, 0).rotate(now * 0.25).x
        self.screen.blit(self.background, (0, 0))

        # Highlight the active row and the next empty slot
        active = len(self.guesses)
        if not self.game_over:
            glow = pygame.Surface((TRAY_W + 8, TRAY_H + 8), pygame.SRCALPHA)
            pygame.draw.rect(glow, (*GOLD, int(70 + 110 * pulse)), glow.get_rect(), 3, border_radius=17)
            self.screen.blit(glow, (TRAY_X - 4, GUESS_START_Y + active * ROW_HEIGHT - 4))
            if None in self.current_guess:
                x, y = self.peg_pos(active, self.current_guess.index(None))
                ring = pygame.Surface((PEG_SIZE + 12, PEG_SIZE + 12), pygame.SRCALPHA)
                pygame.draw.circle(ring, (255, 255, 255, int(50 + 120 * pulse)),
                                   ring.get_rect().center, PEG_SIZE // 2 + 4, 2)
                self.screen.blit(ring, (x - 6, y - 6))

        # Secret code: revealed pegs under a shield that lifts away at game over
        reveal = min(1.0, (now - self.game_over_time) / REVEAL_MS) if self.game_over else 0.0
        if self.game_over:
            for i in range(CODE_LENGTH):
                x, y = self.secret_pos(i)
                self.draw_peg(self.screen, x, y, self.secret_code[i])
        if reveal < 1.0:
            self.shield.set_alpha(int(255 * (1 - reveal)))
            self.screen.blit(self.shield, (PEG_X - 12, SECRET_Y + 3 - int(46 * reveal * reveal)))

        # Guess rows
        flying = []
        for row in range(MAX_ATTEMPTS):
            for i in range(CODE_LENGTH):
                if row < len(self.guesses):
                    color = self.guesses[row][i]
                elif row == len(self.guesses) and not self.game_over:
                    color = self.current_guess[i]
                else:
                    color = None
                if color is None:
                    continue
                x, y = self.peg_pos(row, i)
                start, source = self.flights.get((row, i), (0, (x, y)))
                t = (now - start) / FLY_MS
                if t < 1.0:
                    flying.append((t, source, (x, y), color))  # drawn last, above everything
                else:
                    self.draw_peg(self.screen, x, y, color)

            # Feedback pegs
            if row < len(self.feedback):
                black, white = self.feedback[row]
                self.draw_feedback(self.screen, row, black, white, now)

        # Color picker: pegs rise towards the cursor on hover
        hand = False
        for i, color in enumerate(COLORS):
            x, y = self.picker_pos(i)
            hover = (not self.game_over and None in self.current_guess
                     and pygame.Rect(x, y, PEG_SIZE, PEG_SIZE).collidepoint(mouse))
            hand = hand or hover
            self.draw_peg(self.screen, x, y, color, lift=3 if hover and pressed else 9 if hover else 0)
            key = self.font_small.render(str(i + 1), True, (150, 156, 190))
            self.screen.blit(key, (x + PEG_SIZE // 2 - key.get_width() // 2, PICKER_TRAY.bottom + 1))

        # Submit button
        self.draw_button(mouse, pressed)

        # Balls travelling from the picker to their hole: rise, arc across, sink in
        for t, (sx, sy), (x, y), color in flying:
            e = t * t * (3 - 2 * t)
            arc = 4 * e * (1 - e)
            self.draw_peg(self.screen, sx + (x - sx) * e, sy + (y - sy) * e, color,
                          lift=int(24 * arc), scale=1 + 0.22 * arc)
        hand = hand or ((self.can_submit() or self.game_over) and BUTTON.collidepoint(mouse))
        if hand != self.hand_cursor:
            self.hand_cursor = hand
            try:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND if hand else pygame.SYSTEM_CURSOR_ARROW)
            except pygame.error:
                pass  # no system cursors on this video driver

        # Message
        if self.message:
            msg = self.font_normal.render(self.message, True, GOLD if self.won else (255, 150, 140))
            banner = pygame.Surface((msg.get_width() + 36, msg.get_height() + 14), pygame.SRCALPHA)
            pygame.draw.rect(banner, (0, 0, 0, 150), banner.get_rect(), border_radius=14)
            self.screen.blit(banner, banner.get_rect(center=(WIDTH // 2, MESSAGE_Y)))
            self.screen.blit(msg, msg.get_rect(center=(WIDTH // 2, MESSAGE_Y)))

        # Attempt counter
        attempt_text = self.font_small.render(
            f"Attempt {self.attempt if self.game_over else self.attempt + 1}/{MAX_ATTEMPTS}", True, (170, 178, 215))
        self.screen.blit(attempt_text, (WIDTH - attempt_text.get_width() - 20, 14))

        self.draw_confetti(now)
        self.window.blit(self.screen, (0, 0))
        pygame.display.flip()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos

                # Check color picker
                for i, color in enumerate(COLORS):
                    x, y = self.picker_pos(i)
                    if x <= mx <= x + PEG_SIZE and y <= my <= y + PEG_SIZE:
                        self.place_color(color)
                        return

                # Check submit button (doubles as "New Game" once the game is over)
                if BUTTON.collidepoint(mx, my):
                    if self.game_over:
                        self.reset_game()
                    else:
                        self.submit_guess()
                    return

                # Check guess pegs (for editing)
                if not self.game_over:
                    row = len(self.guesses)
                    for i in range(CODE_LENGTH):
                        x, y = self.peg_pos(row, i)
                        if x <= mx <= x + PEG_SIZE and y <= my <= y + PEG_SIZE:
                            self.current_guess[i] = None  # clear the clicked slot
                            return

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if event.key == pygame.K_r and self.game_over:
                    self.reset_game()
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.submit_guess()
                if pygame.K_1 <= event.key < pygame.K_1 + len(COLORS):
                    self.place_color(COLORS[event.key - pygame.K_1])
                if event.key == pygame.K_BACKSPACE:
                    # Clear last non-None guess
                    for i in range(CODE_LENGTH - 1, -1, -1):
                        if self.current_guess[i] is not None:
                            self.current_guess[i] = None
                            break

    def run(self):
        while True:
            self.handle_events()
            self.draw()
            self.dt = self.clock.tick(FPS) / 1000


if __name__ == "__main__":
    game = Mastermind()
    game.run()
