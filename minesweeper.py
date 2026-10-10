import pygame
import random

# --- Configuration & Colors ---
WIDTH, HEIGHT = 600, 600
GRID_SIZE = 10  # 10x10 grid
CELL_SIZE = WIDTH // GRID_SIZE
FPS = 30

WHITE = (255, 255, 255)
GRAY = (220, 220, 220)
DARK_GRAY = (100, 100, 100)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
GREEN = (0, 255, 0)

class Cell:
    def __init__(self, r, c):
        self.r = r
        self.c = c
        self.is_mine = False
        self.is_revealed = False
        self.is_flagged = False
        self.neighbor_mines = 0

    def draw(self, screen, font):
        rect = pygame.Rect(self.c * CELL_SIZE, self.r * CELL_SIZE, CELL_SIZE, CELL_SIZE)
        
        # Draw background
        if self.is_revealed:
            pygame.draw.rect(screen, GRAY, rect)
            if self.is_mine:
                pygame.draw.circle(screen, BLACK, rect.center, CELL_SIZE // 3)
            elif self.neighbor_mines > 0:
                text = font.render(str(self.neighbor_mines), True, BLUE)
                text_rect = text.get_rect(center=rect.center)
                screen.blit(text, text_rect)
        else:
            pygame.draw.rect(screen, DARK_GRAY, rect)
            if self.is_flagged:
                # Draw a simple red flag (X)
                pygame.draw.line(screen, RED, (rect.x+10, rect.y+10), (rect.right-10, rect.bottom-10), 3)
                pygame.draw.line(screen, RED, (rect.right-10, rect.y+10), (rect.x+10, rect.bottom-10), 3)

        pygame.draw.rect(screen, BLACK, rect, 1) # Draw border

class Minesweeper:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Minesweeper")
        self.font = pygame.font.SysFont("Arial", 24)
        self.clock = pygame.time.Clock()
        self.reset_game()

    def reset_game(self):
        self.grid = [[Cell(r, c) for c in range(GRID_SIZE)] for r in range(GRID_SIZE)]
        self.mines_count = 15
        self.game_over = False
        self.won = False
        self.generate_mines()

    def generate_mines(self):
        mines_placed = 0
        while mines_placed < self.mines_count:
            r = random.randint(0, GRID_SIZE - 1)
            c = random.randint(0, GRID_SIZE - 1)
            if not self.grid[r][c].is_mine:
                self.grid[r][c].is_mine = True
                mines_placed += 1
        
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if not self.grid[r][c].is_mine:
                    count = 0
                    for dr in [-1, 0, 1]:
                        for dc in [-1, 0, 1]:
                            nr, nc = r + dr, c + dc
                            if 0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE:
                                if self.grid[nr][nc].is_mine:
                                    count += 1
                    self.grid[r][c].neighbor_mines = count

    def reveal(self, r, c):
        if self.game_over or self.won or self.grid[r][c].is_flagged or self.grid[r][c].is_revealed:
            return

        self.grid[r][c].is_revealed = True

        if self.grid[r][c].is_mine:
            self.game_over = True
            # Reveal all mines
            for row in self.grid:
                for cell in row:
                    if cell.is_mine:
                        cell.is_revealed = True
            return

        if self.grid[r][c].neighbor_mines == 0:
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE:
                        if not self.grid[nr][nc].is_revealed:
                            self.reveal(nr, nc)

        # Check win condition
        revealed_count = sum(cell.is_revealed for row in self.grid for cell in row if not cell.is_mine)
        if revealed_count == (GRID_SIZE * GRID_SIZE) - self.mines_count:
            self.won = True

    def run(self):
        running = True
        while running:
            self.screen.fill(WHITE)
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                if event.type == pygame.MOUSEBUTTONDOWN and not self.game_over and not self.won:
                    x, y = pygame.mouse.get_pos()
                    c, r = x // CELL_SIZE, y // CELL_SIZE
                    
                    if 0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE:
                        if event.button == 1: # Left Click
                            self.reveal(r, c)
                        elif event.button == 3: # Right Click
                            self.grid[r][c].is_flagged = not self.grid[r][c].is_flagged

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r: # Press R to restart
                        self.reset_game()

            # Draw Grid
            for row in self.grid:
                for cell in row:
                    cell.draw(self.screen, self.font)

            # Draw Overlay Text
            if self.game_over:
                msg = self.font.render("GAME OVER! Press R to Restart", True, RED)
                self.screen.blit(msg, (WIDTH//2 - msg.get_width()//2, HEIGHT//2))
            elif self.won:
                msg = self.font.render("YOU WIN! Press R to Restart", True, GREEN)
                self.screen.blit(msg, (WIDTH//2 - msg.get_width()//2, HEIGHT//2))

            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()

if __name__ == "__main__":
    game = Minesweeper()
    game.run()
