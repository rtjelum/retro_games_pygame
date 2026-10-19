"""
Tetris — a simple GUI Tetris game using Tkinter.
Runs on macOS (Apple Silicon) with Python 3. No external dependencies.
"""

import random
import tkinter as tk

# ----------------------------- Game constants -----------------------------
COLS = 10
ROWS = 20
CELL = 28                 # pixel size of one cell
BG = "#101010"
FALL_MS = 500             # gravity step
LINE_SCORE = 100
COMBO_MULT = 1.5           # multiplier applied per consecutive cleared line

# Piece definitions: (color, list of (row, col) offsets)
PIECES = {
    "I": ("#00e5ff", [(0, 0), (0, 1), (0, 2), (0, 3)]),
    "O": ("#ffeb3b", [(0, 0), (0, 1), (1, 0), (1, 1)]),
    "T": ("#ff9800", [(0, 1), (1, 0), (1, 1), (1, 2)]),
    "S": ("#4caf50", [(0, 1), (0, 2), (1, 0), (1, 1)]),
    "Z": ("#f44336", [(0, 0), (0, 1), (1, 1), (1, 2)]),
    "J": ("#2196f3", [(0, 0), (1, 0), (1, 1), (1, 2)]),
    "L": ("#9c27b0", [(0, 2), (1, 0), (1, 1), (1, 2)]),
}

# ----------------------------- Game logic -----------------------------
class Tetris:
    def __init__(self, root):
        self.root = root
        self.root.title("Tetris")
        self.root.resizable(False, False)

        self.board = [[None] * COLS for _ in range(ROWS)]
        self.score = 0
        self.lines = 0
        self.combo = 0
        self.game_over = False
        self.paused = False

        self._build_ui()
        self._new_piece()
        self._tick()

    # ---------- UI ----------
    def _build_ui(self):
        self.canvas = tk.Canvas(self.root, width=COLS * CELL, height=ROWS * CELL,
                                bg=BG, highlightthickness=0)
        self.canvas.pack(side="left", padx=(8, 0), pady=8)

        # The grid and one rectangle per cell are created once; _draw() only
        # recolors / hides the cells that changed since the last frame.
        for r in range(ROWS + 1):
            self.canvas.create_line(0, r * CELL, COLS * CELL, r * CELL, fill="#222")
        for c in range(COLS + 1):
            self.canvas.create_line(c * CELL, 0, c * CELL, ROWS * CELL, fill="#222")
        self.rects = [[self.canvas.create_rectangle(c * CELL + 1, r * CELL + 1,
                                                    (c + 1) * CELL - 1, (r + 1) * CELL - 1,
                                                    outline="#000", state="hidden")
                       for c in range(COLS)] for r in range(ROWS)]
        self.shown = [[None] * COLS for _ in range(ROWS)]

        # Right-hand panel
        panel = tk.Frame(self.root, bg="#1e1e1e")
        panel.pack(side="right", padx=(0, 8), pady=8, fill="y")

        self.score_label = self._stat(panel, "Score", 0)
        self.lines_label = self._stat(panel, "Lines", 0)
        self.combo_label = self._stat(panel, "Combo", 0)

        tk.Label(panel, text="Controls", bg="#1e1e1e", fg="#ccc",
                 font=("Helvetica", 9, "bold")).pack(anchor="w", pady=(12, 4))
        for key, action in [
            ("← / A", "Move left"), ("→ / D", "Move right"),
            ("↓ / S", "Soft drop"), ("↑ / W", "Rotate"),
            ("Space", "Hard drop"), ("P", "Pause"), ("R", "Restart"),
        ]:
            tk.Label(panel, text=f"{key}  {action}", bg="#1e1e1e",
                     fg="#aaa", font=("Helvetica", 9)).pack(anchor="w")

        self.status_label = tk.Label(panel, text="Press a key to start",
                                     bg="#1e1e1e", fg="#888",
                                     font=("Helvetica", 9))
        self.status_label.pack(anchor="w", pady=(12, 0))

        self.root.bind("<Key>", self._on_key)
        self.root.focus_set()

    def _stat(self, parent, title, value):
        frame = tk.Frame(parent, bg="#1e1e1e")
        frame.pack(fill="x", pady=4)
        tk.Label(frame, text=title, bg="#1e1e1e", fg="#888",
                 font=("Helvetica", 9)).pack(anchor="w", padx=8)
        lbl = tk.Label(frame, text=str(value), bg="#1e1e1e", fg="#fff",
                       font=("Helvetica", 16, "bold"))
        lbl.pack(anchor="w", padx=8)
        return lbl

    # ---------- Drawing ----------
    def _draw(self):
        colors = [row[:] for row in self.board]  # locked blocks
        if self.piece:                           # + active piece
            for dr, dc in self.piece:
                r, c = self.pr + dr, self.pc + dc
                if 0 <= r < ROWS and 0 <= c < COLS:
                    colors[r][c] = self.piece_color
        for r in range(ROWS):
            for c in range(COLS):
                color = colors[r][c]
                if color != self.shown[r][c]:
                    if color:
                        self.canvas.itemconfig(self.rects[r][c], fill=color, state="normal")
                    else:
                        self.canvas.itemconfig(self.rects[r][c], state="hidden")
                    self.shown[r][c] = color

    # ---------- Game flow ----------
    def _new_piece(self):
        name = random.choice(list(PIECES))
        color, cells = PIECES[name]
        self.piece = [(dr, dc) for dr, dc in cells]
        self.piece_color = color
        self.pr, self.pc = 0, (COLS - len(cells[0])) // 2
        if self._collides():
            self._game_over()

    def _collides(self):
        for dr, dc in self.piece:
            r, c = self.pr + dr, self.pc + dc
            if c < 0 or c >= COLS or r >= ROWS:
                return True
            if r >= 0 and self.board[r][c]:
                return True
        return False

    def _lock(self):
        for dr, dc in self.piece:
            r, c = self.pr + dr, self.pc + dc
            if 0 <= r < ROWS and 0 <= c < COLS:
                self.board[r][c] = self.piece_color
        self.piece = None
        self._clear_lines()
        self._new_piece()

    def _clear_lines(self):
        full = [r for r in range(ROWS) if all(self.board[r])]
        if not full:
            self.combo = 0  # the combo only counts consecutive clearing pieces
            self._update_stats()
            return
        for r in full:
            del self.board[r]
            self.board.insert(0, [None] * COLS)
        self.lines += len(full)
        self.combo += 1
        mult = COMBO_MULT ** (self.combo - 1)
        self.score += int(round(LINE_SCORE * len(full) * mult))
        self._update_stats()

    def _game_over(self):
        self.game_over = True
        self.status_label.config(text="GAME OVER — press R to restart",
                                 fg="#f44336")

    def _update_stats(self):
        self.score_label.config(text=str(self.score))
        self.lines_label.config(text=str(self.lines))
        self.combo_label.config(text=str(self.combo))

    # ---------- Input ----------
    def _on_key(self, event):
        if event.keysym in ("r", "R"):
            self._restart()
            return
        if self.game_over:
            return
        if event.keysym == "p" or event.keysym == "P":
            self._toggle_pause()
            return

        if self.paused:
            return

        if self.piece is None:
            return

        k = event.keysym
        if k in ("Left", "a", "A"):
            self._move(-1)
        elif k in ("Right", "d", "D"):
            self._move(1)
        elif k in ("Down", "s", "S"):
            self._soft_drop()
        elif k in ("Up", "w", "W"):
            self._rotate()
        elif k == "space":
            self._hard_drop()
        self._draw()  # show the move now, not at the next gravity step

    def _move(self, dc):
        if not self._collides_at(self.pr, self.pc + dc):
            self.pc += dc

    def _collides_at(self, pr, pc):
        for dr, dc in self.piece:
            r, c = pr + dr, pc + dc
            if c < 0 or c >= COLS or r >= ROWS:
                return True
            if r >= 0 and self.board[r][c]:
                return True
        return False

    def _soft_drop(self):
        if not self._collides_at(self.pr + 1, self.pc):
            self.pr += 1
            self.score += 1
            self._update_stats()
        else:
            self._lock()

    def _hard_drop(self):
        while not self._collides_at(self.pr + 1, self.pc):
            self.pr += 1
        self.score += 2 * (ROWS - self.pr)
        self._lock()
        self._update_stats()

    def _rotate(self):
        # rotate 90° clockwise around the piece's center
        pts = [(dr, dc) for dr, dc in self.piece]
        rotated = [(-dc, dr) for dr, dc in pts]
        # normalize so the top-left is at (0,0)
        min_r = min(r for r, c in rotated)
        min_c = min(c for r, c in rotated)
        rotated = [(r - min_r, c - min_c) for r, c in rotated]
        old = self.piece
        self.piece = rotated
        for kick in (0, -1, 1, -2, 2):  # nudge sideways off a wall or block if needed
            if not self._collides_at(self.pr, self.pc + kick):
                self.pc += kick
                return
        self.piece = old

    def _toggle_pause(self):
        self.paused = not self.paused
        self.status_label.config(
            text="Paused — press P to resume" if self.paused else "Press a key to start",
            fg="#ffeb3b" if self.paused else "#888")

    def _restart(self):
        self.board = [[None] * COLS for _ in range(ROWS)]
        self.score = 0
        self.lines = 0
        self.combo = 0
        self.game_over = False
        self.paused = False
        self._update_stats()
        self.status_label.config(text="Press a key to start", fg="#888")
        self._new_piece()
        self._draw()

    # ---------- Main loop ----------
    def _tick(self):
        if not self.game_over and not self.paused and self.piece:
            if not self._collides_at(self.pr + 1, self.pc):
                self.pr += 1
            else:
                self._lock()
        self._draw()
        self.root.after(FALL_MS, self._tick)


def center_window(window):
    """Move the window to the middle of the screen, like the pygame games."""
    window.withdraw()           # keep it hidden so it doesn't flash in the corner first
    window.update_idletasks()   # lay out the widgets so the window knows its size
    w, h = window.winfo_reqwidth(), window.winfo_reqheight()
    x = (window.winfo_screenwidth() - w) // 2
    y = (window.winfo_screenheight() - h) // 2
    window.geometry(f"+{x}+{y}")
    window.deiconify()


# ----------------------------- Entry point -----------------------------
if __name__ == "__main__":
    root = tk.Tk()
    Tetris(root)
    center_window(root)
    root.mainloop()
