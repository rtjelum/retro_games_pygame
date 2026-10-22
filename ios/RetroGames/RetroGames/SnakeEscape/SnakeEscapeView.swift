import SwiftUI
import simd

// MARK: - Colours and feel (same as snake_escape.py)

private func rgb(_ r: Double, _ g: Double, _ b: Double) -> Color {
    Color(red: r / 255, green: g / 255, blue: b / 255)
}

private enum SE {
    static let bgTop = rgb(36, 44, 58), bgBottom = rgb(16, 18, 26)
    static let faceDark = SIMD3<Double>(20, 24, 36), faceLight = SIMD3<Double>(36, 42, 60)
    static let edge = rgb(120, 130, 170), dot = rgb(62, 70, 92)
    static let text = rgb(255, 213, 79), textDim = rgb(200, 204, 212)
    static let heart = rgb(239, 83, 80), heartLost = rgb(70, 74, 88), bump = rgb(255, 96, 96)
    static let snakeColors = SnakeEscape.colors.map { rgb($0[0], $0[1], $0[2]) }

    static let fill = 0.47                 // the box's farthest corner, as a share of the drawing area
    static let camera = 5.0                // distance to the eye, in those reaches; nearer looks more 3D
    static let near = 0.2                  // closest to the eye a point is drawn as being, in eye distances
    static let exitSpeed = 10.0, exitAccel = 60.0   // cells per second, and per second squared
    static let bumpTime = 0.32             // seconds for a blocked snake to lunge and return
    static let turnPerPoint = 0.01         // radians the box turns per point dragged
    static let tilt = 0.45, spin = 0.6     // radians the box is tipped forward and turned at the start
    static let zoom: ClosedRange<Double> = 1...3
    static let body = 0.4                  // how wide a snake is, in half cells
}

// MARK: - Turning the box

// The view is a rotation taking box space to screen space: x right, y down,
// and z away from the viewer.
private func turn(_ axis: Int, _ angle: Double) -> simd_double3x3 {
    let c = cos(angle), s = sin(angle)
    if axis == 0 {
        return simd_double3x3(rows: [SIMD3(1, 0, 0), SIMD3(0, c, -s), SIMD3(0, s, c)])
    }
    return simd_double3x3(rows: [SIMD3(c, 0, s), SIMD3(0, 1, 0), SIMD3(-s, 0, c)])
}

/// Squeezes the rounding errors out of a rotation.
private func straighten(_ m: simd_double3x3) -> simd_double3x3 {
    let rows = m.transpose
    let x = simd_normalize(rows.columns.0)
    let y = simd_normalize(rows.columns.1 - simd_dot(x, rows.columns.1) * x)
    return simd_double3x3(rows: [x, y, simd_cross(x, y)])
}

private let startView = turn(0, SE.tilt) * turn(1, SE.spin)

// MARK: - Game state

@Observable
final class SnakeEscapeGame {
    enum State { case playing, won, lost }

    var puzzle: [SnakeEscape.Snake] = []
    var tracks: [SnakeEscape.Track] = []
    var onBox: [Int] = []                      // puzzle indices of the snakes still on the box
    var grid: [SnakeEscape.Vec: Int] = [:]     // cell: puzzle index
    var leaving: [(id: Int, travelled: Double, speed: Double)] = []
    var bumps: [(id: Int, time: Double, free: Int)] = []   // free cells ahead of a blocked snake
    var lives = SnakeEscape.lives
    var state = State.playing
    var view = startView
    var zoom = 1.0
    var generating = false
    private var animating = false

    init() {
        newPuzzle()
    }

    func newPuzzle() {
        guard !generating else { return }
        generating = true
        Task.detached(priority: .userInitiated) {
            let puzzle = SnakeEscape.generate()
            let tracks = puzzle.map(SnakeEscape.track)
            await MainActor.run {
                self.puzzle = puzzle
                self.tracks = tracks
                self.view = startView
                self.zoom = 1
                self.generating = false
                self.restart()
            }
        }
    }

    func restart() {
        onBox = Array(puzzle.indices)
        grid = [:]
        for (id, snake) in puzzle.enumerated() {
            for cell in snake.cells { grid[cell] = id }
        }
        leaving = []
        bumps = []
        lives = SnakeEscape.lives
        state = .playing
    }

    func isFree(_ id: Int) -> Bool {
        !puzzle[id].ray().contains { grid[$0] != nil }
    }

    /// Sets a snake off; it leaves if its way is clear and bumps if not.
    func send(_ id: Int) {
        guard state == .playing, !bumps.contains(where: { $0.id == id }) else { return }
        let ray = puzzle[id].ray()
        if let blocked = ray.firstIndex(where: { grid[$0] != nil }) {
            bumps.append((id, 0, blocked))
            lives -= 1
            if lives == 0 { state = .lost }
        } else {
            for cell in puzzle[id].cells { grid[cell] = nil }
            onBox.removeAll { $0 == id }
            leaving.append((id, 0, SE.exitSpeed))
            if onBox.isEmpty { state = .won }
        }
        animate()
    }

    private func animate() {
        guard !animating else { return }
        animating = true
        Task { @MainActor in
            var last = Date()
            while !leaving.isEmpty || !bumps.isEmpty {
                try? await Task.sleep(for: .milliseconds(16))
                let now = Date()
                update(min(now.timeIntervalSince(last), 0.05))
                last = now
            }
            animating = false
        }
    }

    private func update(_ dt: Double) {
        for i in leaving.indices {
            leaving[i].speed += SE.exitAccel * dt
            leaving[i].travelled += leaving[i].speed * dt
        }
        // Gone once the tail is well clear of the screen
        leaving.removeAll { $0.travelled >= Double(puzzle[$0.id].exitLength) }
        for i in bumps.indices { bumps[i].time += dt }
        bumps.removeAll { $0.time >= SE.bumpTime }
    }

    func rotate(by drag: CGSize) {
        let k = SE.turnPerPoint / zoom   // turn less when zoomed in, so the box follows the finger
        view = straighten(turn(0, drag.height * k) * turn(1, -drag.width * k) * view)
    }
}

// MARK: - Projection

/// Where things on the box land on screen, seen in perspective.
private struct Projector {
    let view: simd_double3x3
    let zoom: Double
    let center: CGPoint
    let unit: Double     // points per half cell
    let camera: Double   // points from the box's middle to the eye

    init(view: simd_double3x3, zoom: Double, size: CGSize) {
        self.view = view
        self.zoom = zoom
        center = CGPoint(x: size.width / 2, y: size.height / 2)
        let reach = SE.fill * min(size.width, size.height)
        let box = SnakeEscape.box
        unit = reach / sqrt(Double(box.x * box.x + box.y * box.y + box.z * box.z))
        camera = SE.camera * reach
    }

    private var half: SIMD3<Double> { SnakeEscape.box.double }

    func project(_ point: SIMD3<Double>) -> CGPoint {
        let v = view * (point - half) * unit
        let scale = zoom * camera / max(camera + v.z, SE.near * camera)
        return CGPoint(x: center.x + v.x * scale, y: center.y + v.y * scale)
    }

    /// How squarely a face looks at the eye: above 0 when it can be seen.
    func shown(_ out: SnakeEscape.Vec) -> Double {
        -(view * out.double).z - Double(SnakeEscape.box[out.axis]) * unit / camera
    }

    /// The cell under a screen point, on whichever face is in front there.
    func cell(at point: CGPoint) -> SnakeEscape.Vec? {
        let x = (point.x - center.x) / zoom, y = (point.y - center.y) / zoom
        let rows = view.transpose
        let box = SnakeEscape.box
        for face in SnakeEscape.faces where shown(face.out) > 0 {
            let i = face.out.axis
            let plane = Double((face.out[i] > 0 ? 2 * box[i] : 0) - box[i]) * unit
            // Along the line of sight through (x, y), a point at `depth` sits at
            // (x, y) * (camera + depth) / camera in view space; box space is the
            // transposed view times that. Solve for the depth on this face's plane.
            let slope = (rows.columns.0[i] * x + rows.columns.1[i] * y) / camera
            let along = slope + rows.columns.2[i]
            guard abs(along) > 1e-9 else { continue }
            let depth = (plane - slope * camera) / along
            let stretch = (camera + depth) / camera
            let point = view.transpose * SIMD3(x * stretch, y * stretch, depth) / unit + half
            var cell = SnakeEscape.Vec(0, 0, 0)
            var inside = true
            for k in 0..<3 {
                if k == i {
                    cell[k] = face.out[i] > 0 ? 2 * box[i] : 0
                } else if point[k] > 0 && point[k] < Double(2 * box[k]) {
                    cell[k] = 2 * Int(point[k] / 2) + 1
                } else {
                    inside = false
                }
            }
            if inside { return cell }
        }
        return nil
    }
}

// MARK: - Screen

struct SnakeEscapeView: View {
    @State private var game = SnakeEscapeGame()
    @State private var lastDrag = CGSize.zero
    @State private var pinchStart: Double?   // zoom when the pinch began, while pinching
    @State private var boxArea = CGSize.zero  // size of the area the box is drawn in

    var body: some View {
        VStack(spacing: 12) {
            HStack {
                Text("Snakes left: \(game.onBox.count)")
                    .font(.system(size: 22, weight: .bold, design: .rounded))
                    .foregroundStyle(SE.text)
                Spacer()
                HStack(spacing: 6) {
                    ForEach(0..<SnakeEscape.lives, id: \.self) { i in
                        Image(systemName: "heart.fill")
                            .foregroundStyle(i < game.lives ? SE.heart : SE.heartLost)
                    }
                }
                .font(.system(size: 22))
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("\(game.lives) lives left")
            }
            .padding(.horizontal, 20)

            GeometryReader { geo in
                let projector = Projector(view: game.view, zoom: game.zoom, size: geo.size)
                let painter = BoxPainter(game: game, projector: projector)
                Canvas { context, _ in painter.paint(&context) }
                    .contentShape(Rectangle())
                    .gesture(turning)
                    .simultaneousGesture(zooming)
                    .onTapGesture(coordinateSpace: .local) { tap($0, projector) }
                    .overlay { banners }
                    .onGeometryChange(for: CGSize.self) { $0.size } action: { boxArea = $0 }
            }
            .clipped()

            Text("Drag to turn the cube, pinch to zoom, tap a snake to send it off its face")
                .font(.system(size: 14, weight: .medium, design: .rounded))
                .foregroundStyle(SE.textDim)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 20)

            HStack(spacing: 10) {
                Button("Restart") { game.restart() }
                Button("New") { game.newPuzzle() }
            }
            .buttonStyle(CarParkButtonStyle())
            .disabled(game.generating)
            .padding(.bottom, 8)
        }
        .background(LinearGradient(colors: [SE.bgTop, SE.bgBottom], startPoint: .top, endPoint: .bottom)
            .ignoresSafeArea())
        #if DEBUG
        .task { await autoplay() }
        #endif
    }

    private func tap(_ point: CGPoint, _ projector: Projector) {
        if let cell = projector.cell(at: point), let id = game.grid[cell] { game.send(id) }
    }

    #if DEBUG
    /// Launch with -autoplay to watch the box clear itself (handy for testing in
    /// the simulator). It turns the box and taps the screen where a free snake
    /// is drawn, the same way a finger would.
    private func autoplay() async {
        guard ProcessInfo.processInfo.arguments.contains("-autoplay") else { return }
        var steps = 0.0
        while !Task.isCancelled {
            try? await Task.sleep(for: .milliseconds(250))
            guard game.state == .playing, !game.generating, boxArea != .zero else { continue }
            // Rock the tilt as it spins, so every face comes round to the front
            steps += 1
            game.rotate(by: CGSize(width: 9, height: 12 * sin(steps / 8)))
            let projector = Projector(view: game.view, zoom: game.zoom, size: boxArea)
            let target = game.onBox.lazy.filter(game.isFree).compactMap { id in
                game.puzzle[id].cells.first { projector.shown(SnakeEscape.normal($0)!) > 0.3 }
            }.first
            if let target { tap(projector.project(target.double), projector) }
        }
    }
    #endif

    private var turning: some Gesture {
        DragGesture(minimumDistance: 6)
            .onChanged { value in
                let step = CGSize(width: value.translation.width - lastDrag.width,
                                  height: value.translation.height - lastDrag.height)
                lastDrag = value.translation
                if pinchStart == nil { game.rotate(by: step) }   // two fingers zoom, they don't turn
            }
            .onEnded { _ in lastDrag = .zero }
    }

    private var zooming: some Gesture {
        MagnifyGesture()
            .onChanged { value in
                let start = pinchStart ?? game.zoom
                pinchStart = start
                game.zoom = min(max(start * value.magnification, SE.zoom.lowerBound), SE.zoom.upperBound)
            }
            .onEnded { _ in pinchStart = nil }
    }

    @ViewBuilder private var banners: some View {
        if game.generating {
            banner("Generating…", color: SE.text)
        } else if game.state == .won {
            VStack(spacing: 14) {
                banner("All out!", color: SE.text)
                Button("New Puzzle") { game.newPuzzle() }.buttonStyle(CarParkButtonStyle())
            }
        } else if game.state == .lost {
            VStack(spacing: 14) {
                banner("Out of lives", color: SE.bump)
                HStack(spacing: 10) {
                    Button("Try Again") { game.restart() }
                    Button("New Puzzle") { game.newPuzzle() }
                }
                .buttonStyle(CarParkButtonStyle())
            }
        }
    }

    private func banner(_ text: String, color: Color) -> some View {
        Text(text)
            .font(.system(size: 48, weight: .heavy, design: .rounded))
            .foregroundStyle(color)
            .shadow(color: .black, radius: 0, x: 3, y: 3)
    }
}

/// What the box looks like right now, and how to draw it (following snake_escape.py).
private struct BoxPainter {
    let puzzle: [SnakeEscape.Snake]
    let tracks: [SnakeEscape.Track]
    let onBox: [Int]
    let leaving: [(id: Int, travelled: Double, speed: Double)]
    let bumps: [(id: Int, time: Double, free: Int)]
    let projector: Projector

    // Read everything the drawing needs here, so SwiftUI redraws when it changes
    init(game: SnakeEscapeGame, projector: Projector) {
        puzzle = game.puzzle
        tracks = game.tracks
        onBox = game.onBox
        leaving = game.leaving
        bumps = game.bumps
        self.projector = projector
    }

    func paint(_ context: inout GraphicsContext) {
        var facing: [SnakeEscape.Vec: Double] = [:]
        let dotSize = max(1.5, projector.unit * projector.zoom * 0.15)
        var dots = Path()
        for face in SnakeEscape.faces {
            let shown = projector.shown(face.out)
            facing[face.out] = shown
            guard shown > 0 else { continue }
            var outline = Path()
            outline.addLines(face.corners.map { projector.project($0.double) })
            outline.closeSubpath()
            let c = SE.faceDark + (SE.faceLight - SE.faceDark) * min(shown, 1)
            context.fill(outline, with: .color(rgb(c.x, c.y, c.z)))
            context.stroke(outline, with: .color(SE.edge), lineWidth: 1.5)
            for cell in face.cells {
                let p = projector.project(cell.double)
                dots.addEllipse(in: CGRect(x: p.x - dotSize / 2, y: p.y - dotSize / 2, width: dotSize, height: dotSize))
            }
        }
        context.fill(dots, with: .color(SE.dot))
        guard tracks.count == puzzle.count else { return }

        let bumping = Dictionary(uniqueKeysWithValues: bumps.map { ($0.id, $0) })
        for id in onBox {
            if let bump = bumping[id] {
                let lunge = (Double(bump.free) + 0.25) * (1 - abs(2 * bump.time / SE.bumpTime - 1))
                drawSnake(&context, id, travelled: lunge, color: SE.bump, facing: facing)
            } else {
                drawSnake(&context, id, travelled: 0, color: SE.snakeColors[puzzle[id].color], facing: facing)
            }
        }
        for item in leaving {
            drawSnake(&context, item.id, travelled: item.travelled,
                      color: SE.snakeColors[puzzle[item.id].color], facing: facing)
        }
    }

    /// Draws a snake that has slithered `travelled` cells ahead of its place,
    /// painted flat on the box. Only the parts on faces turned towards the
    /// viewer are drawn.
    private func drawSnake(_ context: inout GraphicsContext, _ id: Int, travelled: Double, color: Color,
                           facing: [SnakeEscape.Vec: Double]) {
        let points = tracks[id].points, outs = tracks[id].outs
        func at(_ s: Double, _ piece: Int) -> SIMD3<Double> {
            points[piece] + (points[piece + 1] - points[piece]) * (s - Double(piece))
        }

        let start = 2 * travelled, headAt = 2 * (travelled + Double(puzzle[id].cells.count - 1))
        let first = Int(start) + 1, last = Int(headAt.rounded(.up))
        let stops = [start] + (first < last ? (first..<last).map(Double.init) : []) + [headAt]
        let half = SE.body / 2
        var shape = Path()
        func add(_ corners: [SIMD3<Double>]) {
            shape.addLines(corners.map(projector.project))
            shape.closeSubpath()
        }

        var piece = 0
        for (s, e) in zip(stops, stops.dropFirst()) {
            piece = Int((s + e) / 2)
            let out = outs[piece]
            guard facing[out, default: 0] > 0 else { continue }
            let along = points[piece + 1] - points[piece]
            let side = simd_cross(out.double, along) * half
            // Square ends fill in the corner at a bend, but stop dead at the
            // box's edges so nothing sticks out into space
            var a = at(s, piece), b = at(e, piece)
            if !(s == Double(piece) && piece > 0 && outs[piece - 1] != out) { a -= along * half }
            if !(e == Double(piece + 1) && piece + 1 < outs.count && outs[piece + 1] != out) { b += along * half }
            add([a + side, b + side, b - side, a - side])
        }

        let out = outs[piece]
        if facing[out, default: 0] > 0 {
            let head = at(headAt, piece)
            let ahead = points[piece + 1] - points[piece]
            let side = simd_cross(out.double, ahead)
            let back = head - ahead * 0.16
            // Wound the same way as the body's quads, so the overlap fills in
            add([head + ahead * 0.66, back - side * 0.48, back + side * 0.48])
        }
        context.fill(shape, with: .color(color))
    }
}

#Preview {
    SnakeEscapeView()
}
