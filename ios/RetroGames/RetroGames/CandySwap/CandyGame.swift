import Foundation
import UIKit

// A port of candy_swap.py. Positions of effects are kept in cell units
// (1.0 = one cell), so the view can draw them at any screen size.

let SIZE = 8            // cells along each side
let KINDS = 6           // different candies
let COLOR_BOMB = KINDS  // the colour bomb is a candy of its own that never matches
let MOVES = 30
let POINTS = 10         // per candy popped, times the combo

let SWAP_TIME = 0.16
let POP_TIME = 0.26
let FALL_ACCEL = 60.0   // cells per second squared
let EFFECT_TIME = 0.4   // how long beams, blasts and bolts stay on screen
let SWIM_TIME = 0.26    // how long a fish takes to reach its target

struct Pos: Hashable {
    var x: Int
    var y: Int
    init(_ x: Int, _ y: Int) { self.x = x; self.y = y }
}

enum Power { case row, col, bomb, fish, color }

enum Shape { case row, col, square }

struct Run {
    var cells: [Pos]
    var shape: Shape
}

/// An 8 x 8 board of anything.
struct Grid<T> {
    var values: [T]
    init(_ value: T) { values = Array(repeating: value, count: SIZE * SIZE) }
    subscript(_ p: Pos) -> T {
        get { values[p.y * SIZE + p.x] }
        set { values[p.y * SIZE + p.x] = newValue }
    }
    func swapped(_ a: Pos, _ b: Pos) -> Grid {
        var copy = self
        copy[a] = self[b]
        copy[b] = self[a]
        return copy
    }
}

typealias Kinds = Grid<Int?>
typealias Powers = Grid<Power?>

let allCells: [Pos] = (0..<SIZE).flatMap { y in (0..<SIZE).map { x in Pos(x, y) } }

// MARK: - Board logic

/// Every straight line of three or more matching candies.
func findRuns(_ grid: Kinds) -> [Run] {
    var runs: [Run] = []
    for horizontal in [true, false] {
        for a in 0..<SIZE {
            var b = 0
            while b < SIZE {
                let at = { (i: Int) in horizontal ? Pos(i, a) : Pos(a, i) }
                let kind = grid[at(b)]
                var n = 1
                while b + n < SIZE, grid[at(b + n)] == kind { n += 1 }
                if let kind, kind < KINDS, n >= 3 {
                    runs.append(Run(cells: (0..<n).map { at(b + $0) }, shape: horizontal ? .row : .col))
                }
                b += n
            }
        }
    }
    return runs
}

/// Every 2 x 2 block of matching candies.
func findSquares(_ grid: Kinds) -> [Run] {
    var squares: [Run] = []
    for y in 0..<SIZE - 1 {
        for x in 0..<SIZE - 1 {
            guard let kind = grid[Pos(x, y)], kind < KINDS else { continue }
            if grid[Pos(x + 1, y)] == kind, grid[Pos(x, y + 1)] == kind, grid[Pos(x + 1, y + 1)] == kind {
                squares.append(Run(cells: [Pos(x, y), Pos(x + 1, y), Pos(x, y + 1), Pos(x + 1, y + 1)],
                                   shape: .square))
            }
        }
    }
    return squares
}

func hasMatch(_ grid: Kinds) -> Bool {
    !findRuns(grid).isEmpty || !findSquares(grid).isEmpty
}

/// Lines and squares that touch or cross are one match.
func findGroups(_ grid: Kinds) -> [(cells: Set<Pos>, shapes: [Run])] {
    var groups: [(cells: Set<Pos>, shapes: [Run])] = []
    for run in findRuns(grid) + findSquares(grid) {
        let runCells = Set(run.cells)
        var cells = runCells
        var shapes = [run]
        var rest: [(cells: Set<Pos>, shapes: [Run])] = []
        for other in groups {
            if other.cells.isDisjoint(with: runCells) {
                rest.append(other)
            } else {
                cells.formUnion(other.cells)
                shapes += other.shapes
            }
        }
        groups = rest + [(cells, shapes)]
    }
    return groups
}

/// Which special candy a match makes, if any. Bigger specials win.
func specialFor(_ shapes: [Run]) -> Power? {
    let lines = shapes.filter { $0.shape != .square }
    if let longest = lines.max(by: { $0.cells.count < $1.cells.count }) {
        if longest.cells.count >= 5 { return .color }
        if Set(lines.map { $0.shape }).count == 2 { return .bomb }   // an L or T shape
        if longest.cells.count == 4 { return longest.shape == .row ? .row : .col }
    }
    if lines.count < shapes.count { return .fish }   // a 2 x 2 square
    return nil
}

/// True when a swap sets off specials without needing a match.
func powerSwap(_ grid: Kinds, _ special: Powers, _ a: Pos, _ b: Pos) -> Bool {
    grid[a] == COLOR_BOMB || grid[b] == COLOR_BOMB || (special[a] != nil && special[b] != nil)
}

/// A swap that does something, or nil if the board is stuck.
func findMove(_ grid: Kinds, _ special: Powers = Powers(nil)) -> (Pos, Pos)? {
    var moves: [(Pos, Pos)] = []
    for p in allCells {
        if p.x + 1 < SIZE { moves.append((p, Pos(p.x + 1, p.y))) }
        if p.y + 1 < SIZE { moves.append((p, Pos(p.x, p.y + 1))) }
    }
    for (a, b) in moves.shuffled() where powerSwap(grid, special, a, b) || hasMatch(grid.swapped(a, b)) {
        return (a, b)
    }
    return nil
}

/// A random board with no matches already on it, but at least one to make.
func newBoard() -> Kinds {
    while true {
        var grid = Kinds(nil)
        for y in 0..<SIZE {
            for x in 0..<SIZE {
                var banned = Set<Int?>()
                if x >= 2, grid[Pos(x - 1, y)] == grid[Pos(x - 2, y)] { banned.insert(grid[Pos(x - 1, y)]) }
                if y >= 2, grid[Pos(x, y - 1)] == grid[Pos(x, y - 2)] { banned.insert(grid[Pos(x, y - 1)]) }
                if x >= 1, y >= 1, grid[Pos(x - 1, y - 1)] == grid[Pos(x, y - 1)],
                   grid[Pos(x, y - 1)] == grid[Pos(x - 1, y)] {
                    banned.insert(grid[Pos(x - 1, y)])   // would finish a 2 x 2 square
                }
                grid[Pos(x, y)] = (0..<KINDS).filter { !banned.contains($0) }.randomElement()!
            }
        }
        if findMove(grid) != nil { return grid }
    }
}

func square(_ center: Pos, _ radius: Int) -> [Pos] {
    var cells: [Pos] = []
    for x in center.x - radius...center.x + radius {
        for y in center.y - radius...center.y + radius where 0 <= x && x < SIZE && 0 <= y && y < SIZE {
            cells.append(Pos(x, y))
        }
    }
    return cells
}

// MARK: - Colours (same as the Python game)

struct RGB: Equatable {
    var r: Double, g: Double, b: Double
    init(_ r: Double, _ g: Double, _ b: Double) { self.r = r / 255; self.g = g / 255; self.b = b / 255 }
    init(unit r: Double, _ g: Double, _ b: Double) { self.r = r; self.g = g; self.b = b }
    func mix(_ o: RGB, _ t: Double) -> RGB {
        RGB(unit: r + (o.r - r) * t, g + (o.g - g) * t, b + (o.b - b) * t)
    }
    static let white = RGB(255, 255, 255)
}

let CANDY_COLORS = [RGB(235, 60, 80), RGB(255, 146, 36), RGB(255, 212, 50),
                    RGB(80, 200, 90), RGB(55, 140, 245), RGB(175, 90, 235)]

func colorOf(_ kind: Int?) -> RGB {
    if let kind, kind < KINDS { return CANDY_COLORS[kind] }
    return .white
}

func center(_ p: Pos) -> CGPoint { CGPoint(x: Double(p.x) + 0.5, y: Double(p.y) + 0.5) }

// MARK: - Effects

struct Particle { var pos: CGPoint; var vel: CGVector; var age = 0.0; var color: RGB; var spin: Double }
struct Ring { var pos: CGPoint; var age = 0.0; var color: RGB }
struct Beam { var index: Int; var horizontal: Bool; var age = 0.0 }
struct Blast { var pos: CGPoint; var radius: Double; var age = 0.0; var color: RGB }
struct Bolt { var start: CGPoint; var end: CGPoint; var age = 0.0 }
struct Swim { var start: CGPoint; var end: CGPoint; var age = 0.0; var kind: Int? }
struct Popup { var text: String; var pos: CGPoint; var age: Double }

enum Phase { case idle, swap, pop, fall, over }

// MARK: - Game

final class CandyGame {
    var grid = Kinds(nil)
    var special = Powers(nil)
    var fall = Grid<Double>(0)      // cells above its place
    var speed = Grid<Double>(0)
    var score = 0
    var moves = MOVES
    var best = UserDefaults.standard.integer(forKey: "candyswap.best")
    var newBest = false
    var combo = 0
    var selected: Pos?
    var hint: (Pos, Pos)?
    var swap: (a: Pos, b: Pos, undo: Bool)?
    var popping = Set<Pos>()
    var creations: [(cell: Pos, kind: Int, power: Power)] = []
    var phase = Phase.idle
    var timer = 0.0
    var time = 0.0
    var particles: [Particle] = []
    var rings: [Ring] = []
    var beams: [Beam] = []
    var blasts: [Blast] = []
    var bolts: [Bolt] = []
    var swims: [Swim] = []
    var popups: [Popup] = []
    var message: (text: String, left: Double)?

    private var lastTick: Date?
    private var dragFrom: (cell: Pos, point: CGPoint)?
    private var touching = false
    private let haptic = UIImpactFeedbackGenerator(style: .light)

    init() { newGame() }

    func newGame() {
        grid = newBoard()
        special = Powers(nil)
        fall = Grid(0)
        speed = Grid(0)
        score = 0
        moves = MOVES
        combo = 0
        selected = nil
        hint = nil
        swap = nil
        popping = []
        creations = []
        phase = .idle
        timer = 0
        particles = []; rings = []; beams = []; blasts = []; bolts = []; swims = []; popups = []
        message = nil
    }

    func showHint() {
        if phase == .idle { hint = findMove(grid, special) }
    }

    func trySwap(_ a: Pos, _ b: Pos) {
        guard phase == .idle, abs(a.x - b.x) + abs(a.y - b.y) == 1 else { return }
        selected = nil
        hint = nil
        swap = (a, b, false)
        phase = .swap
        timer = 0
    }

    private func finishSwap() {
        guard let (a, b, undo) = swap else { return }
        grid = grid.swapped(a, b)
        special = special.swapped(a, b)
        swap = nil
        if undo {
            phase = .idle
            return
        }
        if powerSwap(grid, special, a, b) {
            moves -= 1
            combo = 0
            let (cells, used) = powerUp(a, b)
            startPop(extra: cells, used: used, moved: [a, b])
        } else if hasMatch(grid) {
            moves -= 1
            combo = 0
            startPop(moved: [a, b])
        } else {   // no match: slide back
            swap = (a, b, true)
            phase = .swap
            timer = 0
        }
    }

    /// What swapping a colour bomb, or two specials, sets off.
    private func powerUp(_ a: Pos, _ b: Pos) -> ([Pos], Set<Pos>) {
        if grid[a] == COLOR_BOMB || grid[b] == COLOR_BOMB {
            let (bomb, other) = grid[a] == COLOR_BOMB ? (a, b) : (b, a)
            let kind = grid[other], power = special[other]
            if kind == COLOR_BOMB {   // two colour bombs: clear the lot
                addPopup("Sweet storm!", center(b))
                blasts.append(Blast(pos: center(b), radius: Double(SIZE), color: .white))
                return (allCells, [a, b])
            }
            let targets = allCells.filter { grid[$0] == kind }
            for t in targets {
                bolts.append(Bolt(start: center(bomb), end: center(t)))
                if power == .row || power == .col {   // every candy of that colour turns striped and fires
                    special[t] = Bool.random() ? .row : .col
                } else if power == .bomb || power == .fish {
                    special[t] = power
                }
            }
            addPopup("Colour bomb!", center(bomb))
            return (targets + [bomb], [bomb])
        }

        let pair: Set<Power> = [special[a]!, special[b]!]
        if pair.contains(.fish) {
            let other = pair.count > 1 ? pair.subtracting([.fish]).first! : .fish
            let kind = special[b] == .fish ? grid[b] : grid[a]
            if other == .fish {   // two fish: six targets
                addPopup("School of fish!", center(b))
                return (sendFish(b, 6, [a, b], kind) + [a, b], [a, b])
            }
            // The fish carries the other special to a random spot, where it goes off
            let targets = sendFish(b, 1, [a, b], kind)
            for t in targets {
                special[t] = (other == .row || other == .col) ? (Bool.random() ? .row : .col) : other
            }
            addPopup("Special delivery!", center(b))
            return (targets + [a, b], [a, b])
        }
        var cells: [Pos] = []
        if pair == [.bomb] {
            cells = square(b, 2)
            blasts.append(Blast(pos: center(b), radius: 2.5, color: colorOf(grid[b])))
            addPopup("Mega blast!", center(b))
        } else if pair.contains(.bomb) {   // striped + bomb: three rows and three columns
            for d in -1...1 {
                cells += line(b.y + d, horizontal: true) + line(b.x + d, horizontal: false)
            }
            addPopup("Big cross!", center(b))
        } else {                           // two striped: a row and a column
            cells = line(b.y, horizontal: true) + line(b.x, horizontal: false)
            addPopup("Cross!", center(b))
        }
        return (cells + [a, b], [a, b])
    }

    /// A whole row or column, with a beam across it.
    private func line(_ index: Int, horizontal: Bool) -> [Pos] {
        guard 0 <= index && index < SIZE else { return [] }
        beams.append(Beam(index: index, horizontal: horizontal))
        return (0..<SIZE).map { horizontal ? Pos($0, index) : Pos(index, $0) }
    }

    /// Picks random candies for fish to eat, and starts them swimming there.
    private func sendFish(_ start: Pos, _ count: Int, _ avoid: Set<Pos>, _ kind: Int?) -> [Pos] {
        let options = allCells.filter { !avoid.contains($0) && grid[$0] != nil }
        let targets = Array(options.shuffled().prefix(count))
        for t in targets {
            swims.append(Swim(start: center(start), end: center(t), kind: kind))
        }
        return targets
    }

    /// The cells a special candy clears when it goes off.
    private func fire(_ cell: Pos, _ power: Power, avoid: Set<Pos>) -> [Pos] {
        switch power {
        case .fish:
            return sendFish(cell, 3, avoid.union([cell]), grid[cell])
        case .row:
            return line(cell.y, horizontal: true)
        case .col:
            return line(cell.x, horizontal: false)
        case .bomb:
            blasts.append(Blast(pos: center(cell), radius: 1.5, color: colorOf(grid[cell])))
            return square(cell, 1)
        case .color:
            // A colour bomb caught in a blast takes out the most common candy
            var counts: [Int: Int] = [:]
            for case let kind? in grid.values where kind < KINDS { counts[kind, default: 0] += 1 }
            guard let kind = counts.max(by: { $0.value < $1.value })?.key else { return [] }
            let targets = allCells.filter { grid[$0] == kind }
            for t in targets { bolts.append(Bolt(start: center(cell), end: center(t))) }
            return targets
        }
    }

    /// Pops every match, sets off any specials caught up in it, and plans new specials.
    private func startPop(extra: [Pos] = [], used: Set<Pos> = [], moved: [Pos] = []) {
        var seeds = Set(extra)
        creations = []
        for (cells, runs) in findGroups(grid) {
            seeds.formUnion(cells)
            guard let power = specialFor(runs) else { continue }
            var spot = moved.reversed().first { cells.contains($0) }
            if spot == nil && power == .bomb {   // where the lines cross
                let lines = runs.filter { $0.shape != .square }.map { Set($0.cells) }
                spot = cells.first { c in lines.filter { $0.contains(c) }.count > 1 }
            }
            if spot == nil && power == .fish {
                spot = runs.first { $0.shape == .square }?.cells.first
            }
            if spot == nil {
                let longest = runs.max { $0.cells.count < $1.cells.count }!.cells
                spot = longest[longest.count / 2]
            }
            let cell = spot!
            let kind = power == .color ? COLOR_BOMB : grid[cell]!
            creations.append((cell, kind, power))
            let label: String
            switch power {
            case .row, .col: label = "Striped!"
            case .bomb: label = "Bomb!"
            case .fish: label = "Fish!"
            case .color: label = "Colour bomb!"
            }
            addPopup(label, center(cell), delay: 0.45)
        }

        // Clear everything, letting specials set each other off
        var used = used, cleared = Set<Pos>(), queue = Array(seeds)
        while let cell = queue.popLast() {
            if cleared.contains(cell) { continue }
            cleared.insert(cell)
            var power = special[cell]
            if grid[cell] == COLOR_BOMB { power = .color }
            if let power, !used.contains(cell) {
                used.insert(cell)
                queue += fire(cell, power, avoid: cleared.union(queue))
            }
        }
        let made = Set(creations.map { $0.cell })
        popping = cleared.subtracting(made).filter { grid[$0] != nil }

        combo += 1
        let gained = (popping.count + 3 * creations.count) * POINTS * combo
        score += gained
        if !popping.isEmpty {
            let cx = popping.map { Double($0.x) }.reduce(0, +) / Double(popping.count)
            let cy = popping.map { Double($0.y) }.reduce(0, +) / Double(popping.count)
            let label = "+\(gained)" + (combo > 1 ? "  x\(combo)" : "")
            popups.append(Popup(text: label, pos: CGPoint(x: cx + 0.5, y: cy + 0.5), age: 0))
            haptic.impactOccurred(intensity: min(1, 0.5 + 0.15 * Double(combo)))
        }
        for p in popping {
            let o = center(p)
            let color = colorOf(grid[p])
            rings.append(Ring(pos: o, color: color))
            for _ in 0..<6 {
                let a = Double.random(in: 0..<2 * .pi), v = Double.random(in: 1.25...3.75)
                particles.append(Particle(pos: o, vel: CGVector(dx: cos(a) * v, dy: sin(a) * v),
                                          color: Bool.random() ? color : color.mix(.white, 0.6),
                                          spin: Double.random(in: 0..<Double.pi)))
            }
        }
        phase = .pop
        timer = 0
    }

    /// Clears popped candies, places new specials, lets the rest fall and fills from the top.
    private func drop() {
        for p in popping {
            grid[p] = nil
            special[p] = nil
        }
        for c in creations {
            grid[c.cell] = c.kind
            special[c.cell] = c.power
        }
        popping = []
        creations = []
        for x in 0..<SIZE {
            let rows = (0..<SIZE).filter { grid[Pos(x, $0)] != nil }
            let column = rows.map { (grid[Pos(x, $0)], special[Pos(x, $0)]) }
            let missing = SIZE - column.count
            for y in 0..<SIZE {
                let p = Pos(x, y)
                speed[p] = 0
                if y < missing {
                    grid[p] = Int.random(in: 0..<KINDS)
                    special[p] = nil
                    fall[p] = Double(missing)
                } else {
                    (grid[p], special[p]) = column[y - missing]
                    fall[p] = Double(y - rows[y - missing])
                }
            }
        }
        phase = .fall
    }

    /// Called once everything has landed: chain on, or hand back to the player.
    private func settle() {
        if hasMatch(grid) {
            startPop()
            return
        }
        phase = .idle
        if moves == 0 {
            phase = .over
            newBest = score > best
            if newBest {
                best = score
                UserDefaults.standard.set(best, forKey: "candyswap.best")
            }
        } else if findMove(grid, special) == nil {
            grid = newBoard()
            special = Powers(nil)
            message = ("No moves left - shuffled!", 1.6)
        }
    }

    private func addPopup(_ text: String, _ pos: CGPoint, delay: Double = 0) {
        popups.append(Popup(text: text, pos: CGPoint(x: pos.x, y: pos.y - 0.8), age: -delay))
    }

    // MARK: - Time

    /// Moves the game on to `date`. Called once per screen frame.
    func tick(_ date: Date) {
        let dt = min(date.timeIntervalSince(lastTick ?? date), 0.05)
        lastTick = date
        guard dt > 0 else { return }
        update(dt)
    }

    private func update(_ dt: Double) {
        time += dt
        timer += dt
        #if DEBUG
        // Launch with -autoplay to watch the game play itself (handy for testing in the simulator)
        if phase == .idle, timer > 0.7, ProcessInfo.processInfo.arguments.contains("-autoplay"),
           let (a, b) = findMove(grid, special) {
            trySwap(a, b)
        }
        #endif
        if phase == .swap && timer >= SWAP_TIME {
            finishSwap()
        } else if phase == .pop && timer >= POP_TIME {
            drop()
        } else if phase == .fall {
            var landed = true
            for p in allCells where fall[p] > 0 {
                speed[p] += FALL_ACCEL * dt
                fall[p] = max(0, fall[p] - speed[p] * dt)
                landed = landed && fall[p] == 0
            }
            if landed { settle() }
        }

        for i in particles.indices {
            particles[i].pos.x += particles[i].vel.dx * dt
            particles[i].pos.y += particles[i].vel.dy * dt
            particles[i].vel.dy += 7.8 * dt
            particles[i].age += dt
        }
        particles.removeAll { $0.age >= 0.6 }
        for i in rings.indices { rings[i].age += dt }
        for i in beams.indices { beams[i].age += dt }
        for i in blasts.indices { blasts[i].age += dt }
        for i in bolts.indices { bolts[i].age += dt }
        for i in swims.indices { swims[i].age += dt }
        rings.removeAll { $0.age >= 0.35 }
        beams.removeAll { $0.age >= EFFECT_TIME }
        blasts.removeAll { $0.age >= EFFECT_TIME }
        bolts.removeAll { $0.age >= EFFECT_TIME }
        swims.removeAll { $0.age >= SWIM_TIME }
        for i in popups.indices {
            if popups[i].age >= 0 { popups[i].pos.y -= 0.625 * dt }
            popups[i].age += dt
        }
        popups.removeAll { $0.age >= 0.9 }
        if let m = message {
            message = m.left > dt ? (m.text, m.left - dt) : nil
        }
    }

    // MARK: - Touch (point is in cell units from the board's top-left corner)

    private func cellAt(_ point: CGPoint) -> Pos? {
        let x = Int(floor(point.x)), y = Int(floor(point.y))
        return (0 <= x && x < SIZE && 0 <= y && y < SIZE) ? Pos(x, y) : nil
    }

    private func tap(_ cell: Pos) {
        guard phase == .idle else { return }
        if let s = selected, abs(s.x - cell.x) + abs(s.y - cell.y) == 1 {
            trySwap(s, cell)
        } else {
            selected = selected == cell ? nil : cell
        }
    }

    func touchMoved(_ point: CGPoint) {
        if !touching {
            touching = true
            if let cell = cellAt(point), phase == .idle {
                tap(cell)
                dragFrom = (cell, point)
            }
            return
        }
        guard let (cell, start) = dragFrom else { return }
        let dx = point.x - start.x, dy = point.y - start.y
        if max(abs(dx), abs(dy)) > 0.45 {
            let step = abs(dx) > abs(dy) ? Pos(dx > 0 ? 1 : -1, 0) : Pos(0, dy > 0 ? 1 : -1)
            let target = Pos(cell.x + step.x, cell.y + step.y)
            dragFrom = nil
            if 0 <= target.x && target.x < SIZE && 0 <= target.y && target.y < SIZE {
                trySwap(cell, target)
            }
        }
    }

    func touchEnded() {
        touching = false
        dragFrom = nil
    }
}
