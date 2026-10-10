"""
Retro Games menu - pick one of the games and play it.
Each game runs as its own process; the menu comes back when you close it.

Controls:
  Arrow keys / WASD or the mouse = choose a game
  Enter / Space / click = play
  Esc = quit
"""

import pygame
import subprocess
import sys
from pathlib import Path

# -----------------------------
#  Constants
# -----------------------------
WIDTH, HEIGHT = 900, 640
FPS = 60

BG_TOP = (40, 44, 78)
BG_BOTTOM = (10, 10, 20)
GOLD = (255, 215, 120)
WHITE = (255, 255, 255)
GRAY = (150, 150, 150)
RED = (235, 90, 90)
CARD = (28, 30, 52)
CARD_SELECTED = (52, 56, 96)
THUMB_BG = (16, 17, 30)

# -----------------------------
#  Layout
# -----------------------------
COLS = 4
MARGIN = 30
GAP = 20
GRID_TOP = 110
CARD_W = (WIDTH - 2 * MARGIN - (COLS - 1) * GAP) // COLS
CARD_H = 220
THUMB_PAD = 10
THUMB_H = 150

BASE_DIR = Path(__file__).parent

# (title, script, screenshot, toolkit)
GAMES = [
    ("2048", "2048_game.py", "2048.png", "Tkinter"),
    ("Flabby Bird", "flabby_bird.py", "flabby_bird.png", "pygame"),
    ("Mastermind", "mastermind.py", "mastermind.png", "pygame"),
    ("Maze", "maze_game.py", "maze.png", "Tkinter"),
    ("Minesweeper", "minesweeper.py", "minesweeper.png", "pygame"),
    ("Sokoban", "sokoban.py", "sokoban.png", "pygame"),
    ("Sudoku", "sudoku.py", "sudoku.png", "pygame"),
    ("Tetris", "tetris_game.py", "tetris.png", "Tkinter"),
]


class Menu:
    def __init__(self):
        pygame.init()
        self.window = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Retro Games")
        self.clock = pygame.time.Clock()

        self.font_title = pygame.font.SysFont("Georgia", 42, bold=True)
        self.font_normal = pygame.font.SysFont("Arial", 20, bold=True)
        self.font_small = pygame.font.SysFont("Arial", 15, bold=True)

        self.background = self.make_background()
        self.thumbs = [self.load_thumb(game[2]) for game in GAMES]
        self.cards = [self.card_rect(i) for i in range(len(GAMES))]

        self.selected = 0
        self.process = None      # the running game, if any
        self.playing = None      # index of the running game
        self.message = ""        # error from the last game, shown in the footer

    # -----------------------------
    #  Setup helpers
    # -----------------------------
    def make_background(self):
        surface = pygame.Surface((WIDTH, HEIGHT))
        for y in range(HEIGHT):
            t = y / HEIGHT
            color = [round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)]
            pygame.draw.line(surface, color, (0, y), (WIDTH, y))
        return surface

    def load_thumb(self, filename):
        """Screenshot scaled to fit the card, or None if it can't be loaded."""
        try:
            image = pygame.image.load(BASE_DIR / "screenshots" / filename).convert()
        except (pygame.error, FileNotFoundError):
            return None
        max_w, max_h = CARD_W - 2 * THUMB_PAD, THUMB_H
        scale = min(max_w / image.get_width(), max_h / image.get_height())
        size = (round(image.get_width() * scale), round(image.get_height() * scale))
        return pygame.transform.smoothscale(image, size)

    def card_rect(self, index):
        row, col = divmod(index, COLS)
        x = MARGIN + col * (CARD_W + GAP)
        y = GRID_TOP + row * (CARD_H + GAP)
        return pygame.Rect(x, y, CARD_W, CARD_H)

    # -----------------------------
    #  Launching games
    # -----------------------------
    def launch(self, index):
        script = GAMES[index][1]
        self.message = ""
        self.process = subprocess.Popen([sys.executable, script], cwd=BASE_DIR)
        self.playing = index

    def check_process(self):
        """Take the menu back once the running game has exited."""
        if self.process is None or self.process.poll() is None:
            return
        if self.process.returncode != 0:
            title = GAMES[self.playing][0]
            self.message = f"{title} exited with an error - see the terminal"
        self.process = None
        self.playing = None
        pygame.event.clear()  # drop input that piled up while the game ran

    def quit(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
        pygame.quit()
        sys.exit()

    # -----------------------------
    #  Input
    # -----------------------------
    def move(self, dx, dy):
        row, col = divmod(self.selected, COLS)
        rows = (len(GAMES) + COLS - 1) // COLS
        col = (col + dx) % COLS
        row = (row + dy) % rows
        self.selected = min(row * COLS + col, len(GAMES) - 1)

    def card_at(self, pos):
        for i, rect in enumerate(self.cards):
            if rect.collidepoint(pos):
                return i
        return None

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.quit()
        if self.process is not None:
            return  # a game is running; ignore everything else

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.quit()
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                self.move(-1, 0)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.move(1, 0)
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.move(0, -1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.move(0, 1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.launch(self.selected)
        elif event.type == pygame.MOUSEMOTION:
            hovered = self.card_at(event.pos)
            if hovered is not None:
                self.selected = hovered
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            clicked = self.card_at(event.pos)
            if clicked is not None:
                self.selected = clicked
                self.launch(clicked)

    # -----------------------------
    #  Drawing
    # -----------------------------
    def draw_text(self, text, font, color, **position):
        surface = font.render(text, True, color)
        self.window.blit(surface, surface.get_rect(**position))

    def draw_card(self, index):
        title, _, _, toolkit = GAMES[index]
        rect = self.cards[index]
        selected = index == self.selected

        pygame.draw.rect(self.window, CARD_SELECTED if selected else CARD, rect, border_radius=12)
        if selected:
            pygame.draw.rect(self.window, GOLD, rect, 3, border_radius=12)

        thumb_area = pygame.Rect(rect.x + THUMB_PAD, rect.y + THUMB_PAD,
                                 CARD_W - 2 * THUMB_PAD, THUMB_H)
        pygame.draw.rect(self.window, THUMB_BG, thumb_area, border_radius=8)
        thumb = self.thumbs[index]
        if thumb is not None:
            self.window.blit(thumb, thumb.get_rect(center=thumb_area.center))

        self.draw_text(title, self.font_normal, GOLD if selected else WHITE,
                       midtop=(rect.centerx, thumb_area.bottom + 8))
        self.draw_text(toolkit, self.font_small, GRAY,
                       midtop=(rect.centerx, thumb_area.bottom + 32))

    def draw(self):
        self.window.blit(self.background, (0, 0))
        self.draw_text("Retro Games", self.font_title, GOLD, center=(WIDTH // 2, 58))

        for i in range(len(GAMES)):
            self.draw_card(i)

        footer_y = HEIGHT - 32
        if self.message:
            self.draw_text(self.message, self.font_small, RED, center=(WIDTH // 2, footer_y))
        else:
            self.draw_text("Arrows / mouse = choose     Enter / click = play     Esc = quit",
                           self.font_small, GRAY, center=(WIDTH // 2, footer_y))

        if self.process is not None:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 190))
            self.window.blit(overlay, (0, 0))
            self.draw_text(f"Playing {GAMES[self.playing][0]}", self.font_title, GOLD,
                           center=(WIDTH // 2, HEIGHT // 2 - 20))
            self.draw_text("Close the game to return to the menu", self.font_normal, WHITE,
                           center=(WIDTH // 2, HEIGHT // 2 + 30))

        pygame.display.flip()

    # -----------------------------
    #  Main loop
    # -----------------------------
    def run(self):
        while True:
            for event in pygame.event.get():
                self.handle_event(event)
            self.check_process()
            self.draw()
            self.clock.tick(FPS)


if __name__ == "__main__":
    Menu().run()
