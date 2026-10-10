"""
Maze Game
A simple maze game built with Tkinter.
Controls: Arrow keys / WASD to move.
"""

import random
import tkinter as tk
from tkinter import messagebox

# -----------------------------
# Configuration
# -----------------------------
CELL_SIZE = 20          # pixels per cell
MAZE_WIDTH = 41        # must be odd for a proper maze
MAZE_HEIGHT = 25       # must be odd for a proper maze
BG_COLOR = "#1e1e2e"
WALL_COLOR = "#89b4fa"
PATH_COLOR = "#a6e3a1"
PLAYER_COLOR = "#f38ba8"
EXIT_COLOR = "#f1fa86"
GRID_COLOR = "#31324b"

# -----------------------------
# Maze generation (recursive backtracker)
# -----------------------------
def generate_maze(width, height):
    """
    Returns a 2D grid where 1 = wall, 0 = path.
    Uses the recursive backtracker algorithm.
    """
    # Initialize all as walls
    grid = [[1] * width for _ in range(height)]

    def carve(x, y):
        grid[y][x] = 0
        directions = [(0, -2), (0, 2), (-2, 0), (2, 0)]
        random.shuffle(directions)
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height and grid[ny][nx] == 1:
                grid[y + dy // 2][x + dx // 2] = 0  # remove wall between
                carve(nx, ny)

    # Start carving from (1, 1)
    carve(1, 1)
    return grid


# -----------------------------
# Game class
# -----------------------------
class MazeGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Maze Game")
        self.root.resizable(False, False)

        self.width = MAZE_WIDTH
        self.height = MAZE_HEIGHT
        self.grid = generate_maze(self.width, self.height)

        # Player starts at top-left (1, 1)
        self.player_x, self.player_y = 1, 1
        # Exit is bottom-right (width-2, height-2)
        self.exit_x, self.exit_y = self.width - 2, self.height - 2

        # Build UI
        self._create_canvas()
        self._create_status_bar()
        self._draw()

        # Bind keyboard
        self.root.bind("<Up>", self._move_up)
        self.root.bind("<Down>", self._move_down)
        self.root.bind("<Left>", self._move_left)
        self.root.bind("<Right>", self._move_right)
        self.root.bind("w", self._move_up)
        self.root.bind("s", self._move_down)
        self.root.bind("a", self._move_left)
        self.root.bind("d", self._move_right)
        self.root.bind("r", self._reset)
        self.root.bind("<Return>", self._reset)

        # Focus canvas so keys work immediately
        self.canvas.focus_set()

    def _create_canvas(self):
        self.canvas = tk.Canvas(
            self.root,
            width=self.width * CELL_SIZE,
            height=self.height * CELL_SIZE,
            bg=BG_COLOR,
            highlightthickness=0,
        )
        self.canvas.pack(padx=10, pady=(10, 0))

    def _create_status_bar(self):
        self.status_var = tk.StringVar(value="Use arrow keys / WASD to move. R to reset.")
        self.status_label = tk.Label(
            self.root,
            textvariable=self.status_var,
            bg=BG_COLOR,
            fg="#cdd6f4",
            font=("Helvetica", 11),
        )
        self.status_label.pack(pady=(0, 10))

    def _draw(self):
        self.canvas.delete("all")

        # Draw cells
        for y in range(self.height):
            for x in range(self.width):
                x0 = x * CELL_SIZE
                y0 = y * CELL_SIZE
                x1 = x0 + CELL_SIZE
                y1 = y0 + CELL_SIZE

                if self.grid[y][x] == 1:
                    # Wall
                    self.canvas.create_rectangle(x0, y0, x1, y1, fill=WALL_COLOR, outline="")
                else:
                    # Path
                    self.canvas.create_rectangle(x0, y0, x1, y1, fill=BG_COLOR, outline=GRID_COLOR, width=1)

        # Draw exit
        ex0 = self.exit_x * CELL_SIZE
        ey0 = self.exit_y * CELL_SIZE
        self.canvas.create_rectangle(
            ex0, ey0,
            ex0 + CELL_SIZE, ey0 + CELL_SIZE,
            fill=EXIT_COLOR,
            outline="#1e1e2e",
            width=2,
        )
        self.canvas.create_text(
            ex0 + CELL_SIZE // 2, ey0 + CELL_SIZE // 2,
            text="EXIT",
            fill="#1e1e2e",
            font=("Helvetica", 10, "bold"),
        )

        # Draw player
        px0 = self.player_x * CELL_SIZE
        py0 = self.player_y * CELL_SIZE
        cx = px0 + CELL_SIZE // 2
        cy = py0 + CELL_SIZE // 2
        self.canvas.create_oval(
            cx - 10, cy - 10, cx + 10, cy + 10,
            fill=PLAYER_COLOR,
            outline="#1e1e2e",
            width=2,
        )

    def _can_move(self, nx, ny):
        """Check if the target cell is in bounds and not a wall."""
        if 0 <= nx < self.width and 0 <= ny < self.height:
            return self.grid[ny][nx] == 0
        return False

    def _move(self, dx, dy):
        nx, ny = self.player_x + dx, self.player_y + dy
        if self._can_move(nx, ny):
            self.player_x, self.player_y = nx, ny
            self._draw()
            # Check win
            if self.player_x == self.exit_x and self.player_y == self.exit_y:
                self._on_win()

    def _move_up(self, event=None):
        self._move(0, -1)

    def _move_down(self, event=None):
        self._move(0, 1)

    def _move_left(self, event=None):
        self._move(-1, 0)

    def _move_right(self, event=None):
        self._move(1, 0)

    def _reset(self, event=None):
        self.grid = generate_maze(self.width, self.height)
        self.player_x, self.player_y = 1, 1
        self.exit_x, self.exit_y = self.width - 2, self.height - 2
        self.status_var.set("New maze generated! Use arrow keys / WASD to move.")
        self._draw()
        self.canvas.focus_set()

    def _on_win(self):
        self.status_var.set("🎉 You reached the exit! Press R for a new maze.")
        messagebox.showinfo("You Win!", "Congratulations! You solved the maze.\n\nPress R or Enter for a new maze.")
        self.canvas.focus_set()


# -----------------------------
# Entry point
# -----------------------------
if __name__ == "__main__":
    root = tk.Tk()
    game = MazeGame(root)
    root.mainloop()
