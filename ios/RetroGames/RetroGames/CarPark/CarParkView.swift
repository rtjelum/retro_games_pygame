import SwiftUI

// MARK: - Colours (same as car_park.py)

private func rgb(_ r: Double, _ g: Double, _ b: Double) -> Color {
    Color(red: r / 255, green: g / 255, blue: b / 255)
}

private enum CP {
    static let bgTop = rgb(44, 48, 62), bgBottom = rgb(18, 19, 26)
    static let frame = rgb(112, 100, 92)
    static let asphalt = rgb(58, 61, 68), dot = rgb(84, 88, 96)
    static let glass = rgb(32, 44, 60)
    static let headlight = rgb(255, 244, 180), taillight = rgb(200, 30, 30)
    static let text = rgb(255, 213, 79), textDim = rgb(200, 204, 212)
    static let hint = rgb(96, 220, 120)
    static let red: [Double] = [228, 60, 60]
    static let colors: [[Double]] = [[66, 133, 244], [240, 240, 235], [38, 166, 154], [255, 179, 0],
                                     [126, 87, 194], [150, 155, 165], [121, 85, 72], [102, 187, 106],
                                     [236, 112, 160], [52, 60, 72], [0, 172, 193], [255, 138, 60],
                                     [175, 180, 43]]
}

// MARK: - Game state

@Observable
final class CarParkGame {
    var difficulty = 0
    var puzzle: CarPark.Puzzle?
    var masks: [[UInt64]] = []
    var colors: [[Double]] = []
    var state = CarPark.State([])
    var moves = 0
    var lastMoved: Int?
    var history: [(CarPark.State, Int, Int?)] = []
    var selected = 0
    var drag: (index: Int, offset: CGFloat, range: ClosedRange<CGFloat>)?   // in cells
    var dragPos: CGFloat = 0
    var hint: (index: Int, pos: Int)?
    var solved = false
    var exitDistance: CGFloat = 0   // how far the red car has driven out, in cells
    var generating = false

    init() {
        newPuzzle()
        #if DEBUG
        // Launch with -autoplay to watch the puzzle solve itself (handy for testing in the simulator)
        if ProcessInfo.processInfo.arguments.contains("-autoplay") {
            Task { @MainActor in
                while true {
                    try? await Task.sleep(for: .milliseconds(600))
                    if !solved, !generating, puzzle != nil, let step = CarPark.nextMove(masks, from: state) {
                        move(step.index, to: step.pos)
                    }
                }
            }
        }
        #endif
    }

    func newPuzzle() {
        guard !generating else { return }
        generating = true
        let difficulty = CarPark.difficulties[self.difficulty]
        // Hard puzzles can take a moment to find, so search off the main thread
        Task.detached(priority: .userInitiated) {
            let puzzle = CarPark.generate(difficulty)
            await MainActor.run {
                self.puzzle = puzzle
                self.masks = CarPark.masks(puzzle.vehicles)
                self.colors = [CP.red] + CP.colors.shuffled().prefix(puzzle.vehicles.count - 1)
                self.generating = false
                self.restart()
            }
        }
    }

    func setDifficulty(_ d: Int) {
        guard d != difficulty || puzzle == nil else { return }
        difficulty = d
        newPuzzle()
    }

    func restart() {
        guard let puzzle else { return }
        state = puzzle.start
        moves = 0
        lastMoved = nil
        history = []
        selected = 0
        drag = nil
        hint = nil
        solved = false
        exitDistance = 0
    }

    private func move(_ index: Int, to pos: Int) {
        guard pos != state[index] else { return }
        history.append((state, moves, lastMoved))
        state = state.with(index, at: pos)
        if index != lastMoved { moves += 1 }   // sliding the same vehicle again is still one move
        lastMoved = index
        hint = nil
        solved = state.isSolved
        if solved { driveOut() }
    }

    func undo() {
        guard !solved, drag == nil, let last = history.popLast() else { return }
        (state, moves, lastMoved) = last
        hint = nil
    }

    func showHint() {
        guard !solved, drag == nil, puzzle != nil else { return }
        hint = CarPark.nextMove(masks, from: state)
        if let hint { selected = hint.index }
    }

    private func driveOut() {
        Task { @MainActor in
            while solved && exitDistance < 12 {
                try? await Task.sleep(for: .milliseconds(16))
                exitDistance += 11.25 * 0.016
            }
        }
    }

    // MARK: Touch (points in cell units from the board's top-left corner)

    private func vehicle(at p: CGPoint) -> Int? {
        guard let puzzle else { return nil }
        let x = Int(floor(p.x)), y = Int(floor(p.y))
        return puzzle.vehicles.indices.first { i in
            puzzle.vehicles[i].cells(at: state[i]).contains { $0.x == x && $0.y == y }
        }
    }

    private func along(_ index: Int, _ p: CGPoint) -> CGFloat {
        puzzle!.vehicles[index].horizontal ? p.x : p.y
    }

    func touchMoved(_ p: CGPoint) {
        guard !solved, !generating else { return }
        if let drag {
            dragPos = min(max(along(drag.index, p) - drag.offset, drag.range.lowerBound), drag.range.upperBound)
        } else if let index = vehicle(at: p) {
            selected = index
            let range = CarPark.slideRange(masks, state, index)
            dragPos = CGFloat(state[index])
            drag = (index, along(index, p) - dragPos, CGFloat(range.lowerBound)...CGFloat(range.upperBound))
        }
    }

    func touchEnded() {
        guard let drag else { return }
        self.drag = nil
        move(drag.index, to: Int(dragPos.rounded()))
    }
}

// MARK: - Screen

struct CarParkView: View {
    @State private var game = CarParkGame()

    var body: some View {
        GeometryReader { geo in
            let board = min(geo.size.width - 64, geo.size.height * 0.62, 560)
            VStack(spacing: 16) {
                Picker("Difficulty", selection: Binding(get: { game.difficulty },
                                                        set: { game.setDifficulty($0) })) {
                    ForEach(CarPark.difficulties.indices, id: \.self) { i in
                        Text(CarPark.difficulties[i].name).tag(i)
                    }
                }
                .pickerStyle(.segmented)
                .frame(width: board)
                .disabled(game.generating)

                HStack(spacing: 28) {
                    Text("Moves: \(game.moves)")
                    Text("Best: \(game.puzzle.map { String($0.best) } ?? "–")")
                }
                .font(.system(size: 22, weight: .bold, design: .rounded))
                .foregroundStyle(CP.text)

                CarParkBoard(game: game, side: board)

                Text("Drag the cars and trucks to get the red car out")
                    .font(.system(size: 14, weight: .medium, design: .rounded))
                    .foregroundStyle(CP.textDim)
                    .multilineTextAlignment(.center)

                HStack(spacing: 10) {
                    Button("Undo") { game.undo() }
                    Button("Hint") { game.showHint() }
                    Button("Restart") { game.restart() }
                    Button("New") { game.newPuzzle() }
                }
                .buttonStyle(CarParkButtonStyle())
                .disabled(game.generating)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .background(LinearGradient(colors: [CP.bgTop, CP.bgBottom], startPoint: .top, endPoint: .bottom)
            .ignoresSafeArea())
    }
}

struct CarParkButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 16, weight: .bold, design: .rounded))
            .foregroundStyle(CP.text)
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(RoundedRectangle(cornerRadius: 10).fill(rgb(64, 68, 84)))
            .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(.white.opacity(0.15)))
            .opacity(isEnabled ? (configuration.isPressed ? 0.7 : 1) : 0.4)
    }
}

struct CarParkBoard: View {
    let game: CarParkGame
    let side: CGFloat

    var body: some View {
        let cell = side / CGFloat(CarPark.size)
        let u = cell / 80                  // one pixel in the Python game's layout
        let frame = 12 * u
        let margin = frame + 30 * u        // room for the frame and the exit arrow
        // Read everything the drawing needs here, so SwiftUI redraws when it changes
        let snapshot = BoardSnapshot(vehicles: game.puzzle?.vehicles ?? [], colors: game.colors,
                                     state: game.state, drag: game.drag.map { ($0.index, game.dragPos) },
                                     selected: game.selected, hint: game.hint, solved: game.solved,
                                     exitDistance: game.exitDistance)

        Color.clear
            .frame(width: side, height: side)
            .contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { game.touchMoved(CGPoint(x: $0.location.x / cell, y: $0.location.y / cell)) }
                    .onEnded { _ in game.touchEnded() }
            )
            .overlay {
                Canvas { context, _ in
                    snapshot.paint(&context, cell: cell, u: u, origin: margin, frame: frame)
                }
                .frame(width: side + 2 * margin, height: side + 2 * margin)
                .allowsHitTesting(false)
            }
            .overlay {
                if game.generating {
                    banner("Generating…")
                } else if game.solved {
                    VStack(spacing: 10) {
                        banner("Solved!")
                        Text("\(game.moves) moves (best \(game.puzzle?.best ?? 0))")
                            .font(.system(size: 17, weight: .semibold, design: .rounded))
                            .foregroundStyle(.white)
                            .shadow(color: .black, radius: 0, x: 2, y: 2)
                        Button("Next Puzzle") { game.newPuzzle() }
                            .buttonStyle(CarParkButtonStyle())
                    }
                }
            }
            .padding(margin)
    }

    private func banner(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 48, weight: .heavy, design: .rounded))
            .foregroundStyle(CP.text)
            .shadow(color: .black, radius: 0, x: 3, y: 3)
    }
}

/// What the board looks like right now, and how to draw it (following car_park.py).
private struct BoardSnapshot {
    let vehicles: [CarPark.Vehicle]
    let colors: [[Double]]
    let state: CarPark.State
    let drag: (index: Int, pos: CGFloat)?
    let selected: Int
    let hint: (index: Int, pos: Int)?
    let solved: Bool
    let exitDistance: CGFloat

    func paint(_ context: inout GraphicsContext, cell: CGFloat, u: CGFloat, origin: CGFloat, frame: CGFloat) {
        let size = CGFloat(CarPark.size)
        let board = CGRect(x: origin, y: origin, width: size * cell, height: size * cell)
        context.fill(Path(roundedRect: board.insetBy(dx: -frame, dy: -frame), cornerRadius: 10 * u),
                     with: .color(CP.frame))
        context.fill(Path(board), with: .color(CP.asphalt))
        let exitY = origin + CGFloat(CarPark.exitRow) * cell
        context.fill(Path(CGRect(x: board.maxX, y: exitY, width: frame, height: cell)), with: .color(CP.asphalt))
        for x in 1..<CarPark.size {
            for y in 1..<CarPark.size {
                let c = CGPoint(x: origin + CGFloat(x) * cell, y: origin + CGFloat(y) * cell)
                context.fill(Path(ellipseIn: CGRect(x: c.x - 3 * u, y: c.y - 3 * u, width: 6 * u, height: 6 * u)),
                             with: .color(CP.dot))
            }
        }
        // Arrow pointing out of the exit
        let ax = board.maxX + frame + 8 * u, ay = exitY + cell / 2
        var arrow = Path()
        arrow.move(to: CGPoint(x: ax, y: ay - 12 * u))
        arrow.addLine(to: CGPoint(x: ax + 14 * u, y: ay))
        arrow.addLine(to: CGPoint(x: ax, y: ay + 12 * u))
        arrow.closeSubpath()
        context.fill(arrow, with: .color(CP.text))

        guard !vehicles.isEmpty, colors.count == vehicles.count else { return }
        let pad = 7 * u
        func rect(_ i: Int, _ pos: CGFloat) -> CGRect {
            let v = vehicles[i]
            let long = CGFloat(v.length) * cell - 2 * pad, short = cell - 2 * pad
            if v.horizontal {
                return CGRect(x: origin + pos * cell + pad, y: origin + CGFloat(v.line) * cell + pad,
                              width: long, height: short)
            }
            return CGRect(x: origin + CGFloat(v.line) * cell + pad, y: origin + pos * cell + pad,
                          width: short, height: long)
        }

        for i in vehicles.indices {
            var pos = CGFloat(state[i])
            if let drag, drag.index == i { pos = drag.pos }
            if i == 0 { pos += exitDistance }
            let r = rect(i, pos)
            drawVehicle(&context, vehicles[i], color: colors[i], in: r, u: u)
            if i == selected && !solved {
                context.stroke(Path(roundedRect: r, cornerRadius: 14 * u), with: .color(.white), lineWidth: 3 * u)
            }
        }
        if let hint {
            context.stroke(Path(roundedRect: rect(hint.index, CGFloat(state[hint.index])), cornerRadius: 14 * u),
                           with: .color(CP.hint), lineWidth: 4 * u)
            context.stroke(Path(roundedRect: rect(hint.index, CGFloat(hint.pos)), cornerRadius: 14 * u),
                           with: .color(CP.hint), lineWidth: 2 * u)
        }
    }

    /// Top-down car or truck, facing right if horizontal and up otherwise.
    private func drawVehicle(_ context: inout GraphicsContext, _ vehicle: CarPark.Vehicle, color c: [Double],
                             in rect: CGRect, u: CGFloat) {
        var ctx = context
        let w = vehicle.horizontal ? rect.width : rect.height
        let h = vehicle.horizontal ? rect.height : rect.width
        ctx.translateBy(x: rect.midX, y: rect.midY)
        if !vehicle.horizontal { ctx.rotate(by: .degrees(-90)) }
        ctx.translateBy(x: -w / 2, y: -h / 2)

        let body = rgb(c[0], c[1], c[2])
        let shade = rgb(c[0] * 0.6, c[1] * 0.6, c[2] * 0.6)
        let light = rgb(min(255, c[0] * 1.15 + 12), min(255, c[1] * 1.15 + 12), min(255, c[2] * 1.15 + 12))
        func box(_ x: CGFloat, _ y: CGFloat, _ bw: CGFloat, _ bh: CGFloat, _ r: CGFloat) -> Path {
            Path(roundedRect: CGRect(x: x, y: y, width: bw, height: bh), cornerRadius: r)
        }

        ctx.fill(box(0, 0, w, h, 14 * u), with: .color(body))
        if vehicle.length == 2 {
            ctx.fill(box(w * 0.2, 8 * u, w * 0.56, h - 16 * u, 10 * u), with: .color(CP.glass))
            ctx.fill(box(w * 0.34, 11 * u, w * 0.26, h - 22 * u, 6 * u), with: .color(light))
        } else {
            // Truck: a load bed behind the cab
            let bed = box(8 * u, 7 * u, w * 0.66, h - 14 * u, 6 * u)
            ctx.fill(bed, with: .color(light))
            ctx.stroke(bed, with: .color(shade), lineWidth: 2 * u)
            ctx.fill(box(w * 0.78, 9 * u, w * 0.1, h - 18 * u, 4 * u), with: .color(CP.glass))
        }
        ctx.stroke(box(1.5 * u, 1.5 * u, w - 3 * u, h - 3 * u, 13 * u), with: .color(shade), lineWidth: 3 * u)
        for y in [9 * u, h - 21 * u] {
            ctx.fill(box(w - 8 * u, y, 5 * u, 12 * u, 2 * u), with: .color(CP.headlight))
            ctx.fill(box(3 * u, y, 4 * u, 12 * u, 2 * u), with: .color(CP.taillight))
        }
    }
}

#Preview {
    CarParkView()
}
