import pygame
import sys
import random
import math

# Initialize Pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 540, 600
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Sudoku Master - Generator Edition")

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (50, 120, 255)
TEXT_COLOR = (30, 30, 30)
GRAY = (200, 200, 200)
GREEN = (0, 150, 60)
CONFETTI_COLORS = [(225, 50, 50), (50, 190, 80), (50, 110, 235), (245, 205, 40),
                   (170, 70, 220), (40, 200, 215), (255, 170, 40)]

# Game Settings
CELL_SIZE = WIDTH // 9
CLEAR, CLOSE = 0, -1  # special buttons in the number picker

class SudokuGenerator:
    """Handles the generation of valid Sudoku boards."""
    def __init__(self):
        self.board = [[0 for _ in range(9)] for _ in range(9)]

    def is_valid(self, board, r, c, num):
        # Check row
        for i in range(9):
            if board[r][i] == num:
                return False
        # Check column
        for i in range(9):
            if board[i][c] == num:
                return False
        # Check 3x3 box
        start_row, start_col = 3 * (r // 3), 3 * (c // 3)
        for i in range(3):
            for j in range(3):
                if board[start_row + i][start_col + j] == num:
                    return False
        return True

    def solve(self, board):
        """Standard backtracking algorithm to solve/fill the board."""
        for r in range(9):
            for c in range(9):
                if board[r][c] == 0:
                    nums = list(range(1, 10))
                    random.shuffle(nums) # Shuffle to ensure a different board every time
                    for num in nums:
                        if self.is_valid(board, r, c, num):
                            board[r][c] = num
                            if self.solve(board):
                                return True
                            board[r][c] = 0
                    return False
        return True

    def generate_puzzle(self, difficulty=40):
        """
        1. Generates a full board.
        2. Removes 'difficulty' number of cells.
        """
        self.board = [[0 for _ in range(9)] for _ in range(9)]
        self.solve(self.board) # Fill the board completely
        
        # Digging holes (removing numbers)
        attempts = difficulty
        while attempts > 0:
            r = random.randint(0, 8)
            c = random.randint(0, 8)
            if self.board[r][c] != 0:
                self.board[r][c] = 0
                attempts -= 1
        return self.board

class SudokuGame:
    def __init__(self):
        self.generator = SudokuGenerator()
        # Generate initial board and keep track of which cells are "fixed"
        self.board = self.generator.generate_puzzle(difficulty=40)
        self.fixed_cells = [[(self.board[r][c] != 0) for c in range(9)] for r in range(9)]
        
        self.selected = None
        self.picker = None  # (row, col, frame, [(rect, value)]) while the number strip is open
        self.won = False
        self.confetti = []
        self.dt = 0
        self.font = pygame.font.SysFont("comicsans", 40)
        self.small_font = pygame.font.SysFont("comicsans", 20)
        self.picker_font = pygame.font.SysFont("comicsans", 52)

    def draw(self):
        SCREEN.fill(WHITE)
        
        # Draw Grid
        for i in range(10):
            thickness = 4 if i % 3 == 0 else 1
            pygame.draw.line(SCREEN, BLACK, (0, i * CELL_SIZE), (WIDTH, i * CELL_SIZE), thickness)
            pygame.draw.line(SCREEN, BLACK, (i * CELL_SIZE, 0), (i * CELL_SIZE, WIDTH), thickness)

        # Draw Numbers
        for r in range(9):
            for c in range(9):
                val = self.board[r][c]
                if val != 0:
                    # If it's a fixed cell, make it slightly darker/bolder
                    color = BLACK if self.fixed_cells[r][c] else (100, 100, 100)
                    text = self.font.render(str(val), True, color)
                    text_rect = text.get_rect(center=(c * CELL_SIZE + CELL_SIZE // 2, r * CELL_SIZE + CELL_SIZE // 2))
                    SCREEN.blit(text, text_rect)

        # Draw Selection
        if self.selected:
            r, c = self.selected
            pygame.draw.rect(SCREEN, BLUE, (c * CELL_SIZE, r * CELL_SIZE, CELL_SIZE, CELL_SIZE), 3)

        # UI
        if self.won:
            instr = self.small_font.render("Solved! Press 'R' for a new puzzle", True, GREEN)
            SCREEN.blit(instr, instr.get_rect(center=(WIDTH // 2, 570)))
        else:
            instr = self.small_font.render("R: new puzzle | Tap a square to pick a number", True, BLACK)
            SCREEN.blit(instr, (10, 550))

        self.draw_picker()
        self.draw_confetti()

    def candidates(self, r, c):
        """Numbers that don't clash with the cell's row, column or box."""
        used = set(self.board[r]) | {self.board[i][c] for i in range(9)}
        br, bc = 3 * (r // 3), 3 * (c // 3)
        used |= {self.board[br + i][bc + j] for i in range(3) for j in range(3)}
        used.discard(self.board[r][c])  # the cell's own value doesn't block itself
        return [n for n in range(1, 10) if n not in used]

    def open_picker(self, r, c):
        """Build a strip of big number buttons just above (or below) the cell."""
        values = self.candidates(r, c)
        if self.board[r][c] != 0:
            values.append(CLEAR)  # erase a number the player entered
        values.append(CLOSE)
        gap = 6
        # Big, finger-sized buttons, shrunk only if they wouldn't fit the width
        size = min(72, (WIDTH - 4 - gap * (len(values) + 1)) // len(values))
        width = len(values) * (size + gap) + gap
        height = size + gap * 2
        x = c * CELL_SIZE + CELL_SIZE // 2 - width // 2
        x = max(2, min(x, WIDTH - width - 2))
        y = r * CELL_SIZE - height - 4
        if y < 2:
            y = (r + 1) * CELL_SIZE + 4
        buttons = []
        for i, v in enumerate(values):
            rect = pygame.Rect(x + gap + i * (size + gap), y + gap, size, size)
            buttons.append((rect, v))
        self.picker = (r, c, pygame.Rect(x, y, width, height), buttons)

    def draw_picker(self):
        if not self.picker:
            return
        r, c, frame, buttons = self.picker
        pygame.draw.rect(SCREEN, (120, 120, 120), frame.move(3, 3), border_radius=12)
        pygame.draw.rect(SCREEN, (245, 248, 255), frame, border_radius=12)
        pygame.draw.rect(SCREEN, BLUE, frame, 2, border_radius=12)
        for rect, v in buttons:
            if v == CLOSE:
                pygame.draw.rect(SCREEN, (225, 225, 230), rect, border_radius=10)
                d = rect.width // 4
                for a, b in (((rect.left + d, rect.top + d), (rect.right - d, rect.bottom - d)),
                             ((rect.right - d, rect.top + d), (rect.left + d, rect.bottom - d))):
                    pygame.draw.line(SCREEN, (90, 90, 100), a, b, 5)
            elif v == CLEAR:
                pygame.draw.rect(SCREEN, (255, 225, 225), rect, border_radius=10)
                text = self.small_font.render("Clear", True, (200, 40, 40))
                SCREEN.blit(text, text.get_rect(center=rect.center))
            else:
                pygame.draw.rect(SCREEN, (220, 232, 255), rect, border_radius=10)
                text = self.picker_font.render(str(v), True, BLUE)
                SCREEN.blit(text, text.get_rect(center=rect.center))

    def set_cell(self, r, c, val):
        self.board[r][c] = val
        if self.is_solved():
            self.won = True
            self.selected = None
            self.spawn_confetti()

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
                "color": random.choice(CONFETTI_COLORS),
            })

    def draw_confetti(self):
        now = pygame.time.get_ticks()
        for p in self.confetti:
            p["x"] += p["vx"] * self.dt
            p["y"] += p["vy"] * self.dt
            # Flutter: squash the height as the piece "spins"
            h = max(2, int(p["h"] * abs(math.cos(math.radians(now * 0.5) + p["phase"]))))
            pygame.draw.rect(SCREEN, p["color"], (p["x"], p["y"], p["w"], h))
        self.confetti = [p for p in self.confetti if p["y"] < HEIGHT + 20]

    def is_solved(self):
        """True when every row, column and 3x3 box contains 1-9 exactly once."""
        target = set(range(1, 10))
        for i in range(9):
            row = set(self.board[i])
            col = set(self.board[r][i] for r in range(9))
            br, bc = 3 * (i // 3), 3 * (i % 3)
            box = set(self.board[br + r][bc + c] for r in range(3) for c in range(3))
            if row != target or col != target or box != target:
                return False
        return True

    def handle_click(self, pos):
        """Tap/click: pick a number from the strip, or select a cell."""
        if self.picker:
            r, c, frame, buttons = self.picker
            self.picker = None
            for rect, v in buttons:
                if rect.collidepoint(pos):
                    if v != CLOSE:
                        self.set_cell(r, c, v)
                    return
            if frame.collidepoint(pos):
                return  # tapped the strip's border, just close it
        x, y = pos
        col = x // CELL_SIZE
        row = y // CELL_SIZE
        if 0 <= row < 9 and 0 <= col < 9:
            self.selected = (row, col)
            if not self.won and not self.fixed_cells[row][col]:
                self.open_picker(row, col)

    def handle_key(self, key):
        if self.selected:
            r, c = self.selected
            if not self.fixed_cells[r][c]: # Only allow editing if not a starting number
                if key.isdigit():
                    val = int(key)
                    if val <= 9:
                        self.board[r][c] = val
                elif key in ['Backspace', 'Delete']:
                    self.board[r][c] = 0

    def reset_game(self):
        self.board = self.generator.generate_puzzle(difficulty=40)
        self.fixed_cells = [[(self.board[r][c] != 0) for c in range(9)] for r in range(9)]
        self.selected = None
        self.picker = None
        self.won = False
        self.confetti = []

def main():
    game = SudokuGame()
    clock = pygame.time.Clock()

    while True:
        game.draw()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                game.handle_click(event.pos)
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    game.reset_game()
                else:
                    # Handle number input
                    if game.selected and not game.won:
                        r, c = game.selected
                        if not game.fixed_cells[r][c]:
                            if event.unicode.isdigit():
                                game.picker = None
                                game.set_cell(r, c, int(event.unicode))
                            elif event.key in [pygame.K_BACKSPACE, pygame.K_DELETE]:
                                game.picker = None
                                game.set_cell(r, c, 0)
                            elif event.key == pygame.K_ESCAPE:
                                game.picker = None

        pygame.display.flip()
        game.dt = clock.tick(60) / 1000

if __name__ == "__main__":
    main()
