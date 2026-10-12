# Retro Games

Ten small retro games in Python, one file each. Seven are built with
[pygame-ce](https://pyga.me/); three use Tkinter and need nothing beyond the
standard library.

| Game | File | Toolkit |
| --- | --- | --- |
| [2048](#2048) | `2048_game.py` | Tkinter |
| [Car Park](#car-park) | `car_park.py` | pygame |
| [Flabby Bird](#flabby-bird) | `flabby_bird.py` | pygame |
| [Mastermind](#mastermind) | `mastermind.py` | pygame |
| [Maze](#maze) | `maze_game.py` | Tkinter |
| [Minesweeper](#minesweeper) | `minesweeper.py` | pygame |
| [Snake Escape](#snake-escape) | `snake_escape.py` | pygame |
| [Sokoban](#sokoban) | `sokoban.py` | pygame |
| [Sudoku](#sudoku) | `sudoku.py` | pygame |
| [Tetris](#tetris) | `tetris_game.py` | Tkinter |

## Setup

```bash
./setupenv.sh
```

This sets everything up and starts the game menu.

<img src="screenshots/menu.png" width="560" alt="Game menu">

## The games

### 2048

<img src="screenshots/2048.png" width="320" alt="2048">

Slide the tiles and merge matching numbers to reach 2048.

- **Arrow keys** — slide tiles
- **R** — restart

### Car Park

<img src="screenshots/car_park.png" width="320" alt="Car Park">

A car jam puzzle: slide the cars and trucks out of the way and get the red car
to the exit. Vehicles only move along their own length. Every puzzle is
generated on the spot, and the header shows the fewest moves it can be solved
in.

- **Drag** a vehicle, or pick it with a **click** or **Tab** and use the
  **arrow keys** (**Shift+Tab** goes back)
- **1** / **2** / **3** — easy / medium / hard
- **N** — new puzzle
- **R** — restart the puzzle
- **U** / **Z** — undo
- **H** — hint
- **Esc** — quit

### Flabby Bird

<img src="screenshots/flabby_bird.png" width="260" alt="Flabby Bird">

Keep the bird in the air and thread it through the gaps in the pipes.

- **Space** — flap (and restart after a crash)

### Mastermind

<img src="screenshots/mastermind.png" width="320" alt="Mastermind">

Crack the secret code of 4 colours in 6 attempts. After each guess a black peg
means right colour in the right position, a white peg means right colour in
the wrong position.

- **Click a colour** or **1–6** — place a peg
- **Click a placed peg** / **Backspace** — remove a peg
- **Enter** or the **Submit** button — submit the guess
- **R** — new game (once the round is over)
- **Esc** — quit

### Maze

<img src="screenshots/maze.png" width="560" alt="Maze">

Find your way from the top-left corner to the exit. Every maze is randomly
generated.

- **Arrow keys** / **WASD** — move
- **R** / **Enter** — new maze

### Minesweeper

<img src="screenshots/minesweeper.png" width="320" alt="Minesweeper">

A 10×10 board hiding 15 mines.

- **Left click** — reveal a cell
- **Right click** — flag / unflag a cell
- **R** — restart

### Snake Escape

<img src="screenshots/snake_escape.png" width="320" alt="Snake Escape">

Clear the board by sending the snakes off it one at a time. A snake slithers
straight ahead, the way its arrow points, and only gets out if nothing is in
its way; bump into another snake three times and the round is over. Every
puzzle is generated on the spot and has exactly one solution: at any moment
only one snake is free to go.

- **Click** a snake — send it off
- **1** / **2** / **3** — easy / medium / hard (board size)
- **N** — new puzzle
- **R** — restart the puzzle
- **H** — hint
- **Esc** — quit

### Sokoban

<img src="screenshots/sokoban.png" width="560" alt="Sokoban">

Push every box onto a goal, in isometric view. The 50 levels are read from
`sokoban_levels.h`, which must sit next to `sokoban.py`.

- **Arrow keys** / **WASD** — move
- **U** / **Z** — undo
- **R** — restart the level
- **N** / **P** — next / previous level
- **Esc** — quit

### Sudoku

<img src="screenshots/sudoku.png" width="320" alt="Sudoku">

A freshly generated puzzle every time. Your own entries are shown in grey.

- **Click** — select a cell
- **1–9** — fill the selected cell
- **Backspace** / **Delete** — clear it
- **R** — generate a new puzzle

### Tetris

<img src="screenshots/tetris.png" width="300" alt="Tetris">

Classic falling blocks, with a score multiplier for clearing lines with
consecutive pieces.

- **←** / **→** or **A** / **D** — move
- **↑** / **W** — rotate
- **↓** / **S** — soft drop
- **Space** — hard drop
- **P** — pause
- **R** — restart (after game over)
