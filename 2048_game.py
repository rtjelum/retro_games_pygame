import tkinter as tk
import random

# Constants for colors and game settings
BG_COLOR = "#bbada0"
EMPTY_TILE_COLOR = "#cdc1b4"
TILE_COLORS = {
    2: "#eee4da", 4: "#ede0c9", 8: "#f2b179", 16: "#f59563",
    32: "#f67c5f", 64: "#f65e3b", 128: "#edcf72", 256: "#edc265",
    512: "#edb54e", 1024: "#eda53c", 2048: "#ed922e"
}


def center_window(window):
    """Move the window to the middle of the screen, like the pygame games."""
    window.withdraw()           # keep it hidden so it doesn't flash in the corner first
    window.update_idletasks()   # lay out the widgets so the window knows its size
    w, h = window.winfo_reqwidth(), window.winfo_reqheight()
    x = (window.winfo_screenwidth() - w) // 2
    y = (window.winfo_screenheight() - h) // 2
    window.geometry(f"+{x}+{y}")
    window.deiconify()


class Game2048(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("2048 Python Edition")
        self.resizable(False, False)
        
        self.grid = [[0] * 4 for _ in range(4)]
        self.score = 0
        
        self.setup_ui()
        self.start_game()
        
        # Bind keyboard arrows
        self.bind("<Up>", lambda e: self.move("up"))
        self.bind("<Down>", lambda e: self.move("down"))
        self.bind("<Left>", lambda e: self.move("left"))
        self.bind("<Right>", lambda e: self.move("right"))

        # Press R to restart
        self.bind("<r>", lambda e: self.start_game())
        self.bind("<R>", lambda e: self.start_game())

    def setup_ui(self):
        """Creates the visual structure of the game."""
        self.main_frame = tk.Frame(self, bg=BG_COLOR, padx=10, pady=10)
        self.main_frame.pack()

        self.score_label = tk.Label(self.main_frame, text="Score: 0", font=("Arial", 16, "bold"), bg=BG_COLOR, fg="white")
        self.score_label.pack(pady=(0, 10))

        self.grid_frame = tk.Frame(self.main_frame, bg=BG_COLOR)
        self.grid_frame.pack()

        # Create 4x4 grid of labels
        self.cells = []
        for r in range(4):
            row_cells = []
            for c in range(4):
                cell = tk.Label(self.grid_frame, text="", font=("Arial", 32, "bold"),
                                width=4, height=2, fg="#776e65", bg=EMPTY_TILE_COLOR)
                cell.grid(row=r, column=c, padx=5, pady=5)
                row_cells.append(cell)
            self.cells.append(row_cells)

    def start_game(self):
        """Initializes the board with two random tiles."""
        self.grid = [[0] * 4 for _ in range(4)]
        self.score = 0
        self.add_new_tile()
        self.add_new_tile()
        self.update_ui()

    def add_new_tile(self):
        """Adds a 2 or 4 to a random empty spot."""
        empty_cells = [(r, c) for r in range(4) for c in range(4) if self.grid[r][c] == 0]
        if empty_cells:
            r, c = random.choice(empty_cells)
            self.grid[r][c] = 2 if random.random() < 0.9 else 4

    def update_ui(self):
        """Refreshes the colors and text on the screen."""
        self.score_label.config(text=f"Score: {self.score}")
        for r in range(4):
            for c in range(4):
                val = self.grid[r][c]
                self_cell = self.cells[r][c]
                
                # Update text
                self_cell.config(text=str(val) if val != 0 else "")
                
                # Update color based on tile value
                color = TILE_COLORS.get(val, "#3c3a32") # Dark color if value > 2048
                if val == 0:
                    color = EMPTY_TILE_COLOR
                
                self_cell.config(bg=color, fg="#776e65" if val <= 4 else "white")

    def _slide_and_merge(self, row):
        """Helper logic to slide numbers and merge identical neighbors."""
        # 1. Remove zeros
        new_row = [i for i in row if i != 0]
        # 2. Merge
        for i in range(len(new_row) - 1):
            if new_row[i] == new_row[i+1]:
                new_row[i] *= 2
                self.score += new_row[i]
                new_row[i+1] = 0
        # 3. Remove zeros again after merge
        new_row = [i for i in new_row if i != 0]
        # 4. Pad with zeros
        return new_row + [0] * (4 - len(new_row))

    def move(self, direction):
        """Handles the logic for all 4 directions."""
        old_grid = [row[:] for row in self.grid]

        if direction == "left":
            for r in range(4):
                self.grid[r] = self._slide_and_merge(self.grid[r])
        
        elif direction == "right":
            for r in range(4):
                self.grid[r] = self._slide_and_merge(self.grid[r][::-1])[::-1]
        
        elif direction == "up":
            for c in range(4):
                col = [self.grid[r][c] for r in range(4)]
                col = self._slide_and_merge(col)
                for r in range(4):
                    self.grid[r][c] = col[r]
        
        elif direction == "down":
            for c in range(4):
                col = [self.grid[r][c] for r in range(4)]
                col = self._slide_and_merge(col[::-1])[::-1]
                for r in range(4):
                    self.grid[r][c] = col[r]

        # Check if anything changed
        if old_grid != self.grid:
            self.add_new_tile()
            self.update_ui()
            if self.is_game_over():
                self.score_label.config(text=f"GAME OVER! Score: {self.score} (R to restart)")

    def is_game_over(self):
        """Checks if any moves are left."""
        for r in range(4):
            for c in range(4):
                if self.grid[r][c] == 0: return False
                if c < 3 and self.grid[r][c] == self.grid[r][c+1]: return False
                if r < 3 and self.grid[r][c] == self.grid[r+1][c]: return False
        return True

if __name__ == "__main__":
    game = Game2048()
    center_window(game)
    game.mainloop()
