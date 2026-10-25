import SwiftUI
import simd

// MARK: - Colours and feel (same as snake_escape.py)

private func rgb(_ r: Double, _ g: Double, _ b: Double) -> Color {
    Color(red: r / 255, green: g / 255, blue: b / 255)
}

private enum SE {
    static let bgTop = rgb(46, 62, 92), bgBottom = rgb(0, 0, 0)
    static let glow = rgb(60, 90, 160)
    static let text = rgb(255, 213, 79), textDim = rgb(200, 204, 212)
    static let heartRGB = SIMD3<Double>(239, 83, 80)
    static let heart = rgb(239, 83, 80), heartLost = rgb(70, 74, 88), bump = rgb(255, 96, 96)
    static let snakeColors = SnakeEscape.colors.map { rgb($0[0], $0[1], $0[2]) }

    static let fill = 0.53                 // the box's farthest corner, as a share of the drawing area
    static let camera = 5.0                // distance to the eye, in those reaches; nearer looks more 3D
    static let near = 0.2                  // closest to the eye a point is drawn as being, in eye distances
    static let exitSpeed = 10.0, exitAccel = 60.0   // cells per second, and per second squared
    static let bumpTime = 0.45             // seconds for a blocked snake to lunge and return
    static let turnPerPoint = 0.01         // radians the box turns per point dragged
    static let tilt = 0.45, spin = 0.6     // radians the box is tipped forward and turned at the start
    static let zoom: ClosedRange<Double> = 1...3
    static let body = 0.5                  // how wide a snake is, in half cells

    // Losing a life
    static let hurtTime = 0.7              // seconds the red flash takes to fade after a bump
    static let shake = 8.0                 // points the screen shakes at a bump, more on the last life
    static let sparks = 46                 // sparks thrown out where a blocked snake hits
    static let heartBreak = 0.9            // seconds for a lost heart to break and fall away
    static let slamTime = 0.28             // seconds for "Out of lives" to slam down

    // Winning
    static let winSpin = 0.35              // radians a second the box turns by itself once solved
    static let burstEvery = 0.55           // seconds between fireworks
    static let confetti = 120              // confetti pieces raining down
    static let shineEvery = 2.8            // seconds between shines sweeping across the title
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

// MARK: - The shader's table of snakes

// The box shader (SnakeEscapeBox.metal) finds the snakes lying still on the
// box in a table with a number for every cell: 0 where there is no snake,
// otherwise the snake's colour times 128 plus its shape there. The shape has
// a bit for each way the body goes on to a neighbouring cell (forwards and back
// along the face's first axis, then its second), then on the head a flag and
// the way its arrow points.
private enum CellTable {
    static let side = max(SnakeEscape.box.x, SnakeEscape.box.y, SnakeEscape.box.z)
    static let size = 6 * side * side

    /// The two axes across a cell's face, the way the shader takes them.
    static func across(_ axis: Int) -> (Int, Int) {
        (axis == 0 ? 1 : 0, axis == 2 ? 1 : 2)
    }

    static func slot(_ cell: SnakeEscape.Vec) -> Int {
        let out = SnakeEscape.normal(cell)!
        let i = out.axis
        let (a, b) = across(i)
        let face = 2 * i + (out[i] > 0 ? 1 : 0)
        return (face * side + cell[a] / 2) * side + cell[b] / 2
    }

    /// Which way `other` lies from a cell, across the cell's face.
    static func way(_ cell: SnakeEscape.Vec, _ other: SnakeEscape.Vec) -> Int {
        let (a, b) = across(SnakeEscape.normal(cell)!.axis)
        if other[a] != cell[a] { return other[a] > cell[a] ? 0 : 1 }
        return other[b] > cell[b] ? 2 : 3
    }

    /// A snake's entries in the table: (slot, number).
    static func entries(_ snake: SnakeEscape.Snake) -> [(Int, Float)] {
        let cells = snake.cells
        return cells.indices.map { k in
            var bits = 0
            if k > 0 { bits |= 1 << way(cells[k], cells[k - 1]) }
            if k + 1 < cells.count { bits |= 1 << way(cells[k], cells[k + 1]) }
            if k == cells.count - 1 { bits |= 16 | way(cells[k], cells[k] + snake.direction) << 5 }
            return (slot(cells[k]), Float(snake.color * 128 + bits))
        }
    }

    static let palette: [Float] = SnakeEscape.colors.flatMap { $0.map(Float.init) }
}

// MARK: - Game state

@Observable
final class SnakeEscapeGame {
    enum State { case playing, won, lost }

    /// A spark from an impact, flying off from a point on the box.
    struct Spark {
        var origin: SIMD3<Double>      // where on the box it started
        var x = 0.0, y = 0.0           // points it has flown from there
        var vx: Double, vy: Double
        var life: Double               // seconds left
        var color: Color
    }

    var puzzle: [SnakeEscape.Snake] = []
    var tracks: [SnakeEscape.Track] = []
    var entries: [[(Int, Float)]] = []         // each snake's entries in the shader's table
    var onBox: [Int] = []                      // puzzle indices of the snakes still on the box
    var grid: [SnakeEscape.Vec: Int] = [:]     // cell: puzzle index
    var leaving: [(id: Int, travelled: Double, speed: Double)] = []
    // free cells ahead of a blocked snake, and whether it has hit yet
    var bumps: [(id: Int, time: Double, free: Int, hit: Bool)] = []
    var lives = SnakeEscape.lives
    var state = State.playing
    var view = startView
    var zoom = 1.0
    var generating = false

    // Losing a life
    var hurt = 0.0                             // 1 at a bump, fading to 0: the red flash
    var shake = 0.0                            // how hard the screen shakes, fading to 0
    var shakeOffset = CGSize.zero
    var sparks: [Spark] = []
    var rings: [(origin: SIMD3<Double>, time: Double)] = []   // shock waves at impacts
    var breaking: [(heart: Int, time: Double)] = []          // hearts just lost
    var lostTime = 0.0                         // seconds since the last life went

    // Winning
    var wonTime = 0.0                          // seconds since the last snake got out
    var playTime = 0.0                         // seconds the puzzle took
    var winSeed: UInt64 = 0                    // picks where the confetti and fireworks go
    private var startTime = Date()
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
            let entries = puzzle.map(CellTable.entries)
            await MainActor.run {
                self.puzzle = puzzle
                self.tracks = tracks
                self.entries = entries
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
        hurt = 0
        shake = 0
        shakeOffset = .zero
        sparks = []
        rings = []
        breaking = []
        lostTime = 0
        wonTime = 0
        startTime = Date()
    }

    func isFree(_ id: Int) -> Bool {
        !puzzle[id].ray().contains { grid[$0] != nil }
    }

    /// The shader's table of the snakes lying still on the box.
    var cellTable: [Float] {
        var table = [Float](repeating: 0, count: CellTable.size)
        let bumping = Set(bumps.map(\.id))
        for id in onBox where !bumping.contains(id) && id < entries.count {
            for (slot, value) in entries[id] { table[slot] = value }
        }
        return table
    }

    /// Sets a snake off; it leaves if its way is clear and bumps if not.
    func send(_ id: Int) {
        guard state == .playing, !bumps.contains(where: { $0.id == id }) else { return }
        let ray = puzzle[id].ray()
        if let blocked = ray.firstIndex(where: { grid[$0] != nil }) {
            // The life goes when the snake hits, halfway through its lunge;
            // until then don't let more bumps than there are lives start
            guard bumps.filter({ !$0.hit }).count < lives else { return }
            bumps.append((id, 0, blocked, false))
        } else {
            for cell in puzzle[id].cells { grid[cell] = nil }
            onBox.removeAll { $0 == id }
            leaving.append((id, 0, SE.exitSpeed))
            if onBox.isEmpty {
                state = .won
                wonTime = 0
                playTime = Date().timeIntervalSince(startTime)
                winSeed = .random(in: .min ... .max)
            }
        }
        animate()
    }

    /// A blocked snake hits the one in its way: a life goes, with a bang.
    private func impact(_ id: Int, free: Int) {
        lives -= 1
        let last = lives == 0
        if last {
            state = .lost
            lostTime = 0
        }
        hurt = 1
        shake = last ? 1.6 : 1
        breaking.append((lives, 0))
        let snake = puzzle[id]
        let origin = (snake.ray()[free] - snake.direction).double
        rings.append((origin, 0))
        let colors = [Color.white, SE.text, SE.bump, SE.snakeColors[snake.color]]
        for _ in 0..<(SE.sparks * (last ? 2 : 1)) {
            let angle = Double.random(in: 0..<(2 * .pi))
            let speed = Double.random(in: 60...350) * (last ? 1.3 : 1)
            sparks.append(Spark(origin: origin, vx: cos(angle) * speed, vy: sin(angle) * speed - 75,
                                life: Double.random(in: 0.35...0.8), color: colors.randomElement()!))
        }
    }

    /// Whether anything is still moving, so the clock must keep running.
    private var busy: Bool {
        !leaving.isEmpty || !bumps.isEmpty || hurt > 0 || shake > 0 || !sparks.isEmpty
            || !rings.isEmpty || !breaking.isEmpty || (state == .lost && lostTime < 0.6)
            || state == .won   // the celebration keeps going until the next puzzle
    }

    private func animate() {
        guard !animating else { return }
        animating = true
        Task { @MainActor in
            var last = Date()
            while busy {
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
        for i in bumps.indices {
            bumps[i].time += dt
            if !bumps[i].hit && bumps[i].time >= SE.bumpTime / 2 {
                bumps[i].hit = true
                impact(bumps[i].id, free: bumps[i].free)
            }
        }
        bumps.removeAll { $0.time >= SE.bumpTime }

        hurt = max(0, hurt - dt / SE.hurtTime)
        shake = max(0, shake - dt * 2.2)
        let size = SE.shake * shake * shake
        shakeOffset = size > 0 ? CGSize(width: .random(in: -size...size), height: .random(in: -size...size)) : .zero
        for i in sparks.indices {
            sparks[i].vx *= 1 - 2.5 * dt           // air drag
            sparks[i].vy += 700 * dt               // gravity
            sparks[i].x += sparks[i].vx * dt
            sparks[i].y += sparks[i].vy * dt
            sparks[i].life -= dt
        }
        sparks.removeAll { $0.life <= 0 }
        for i in rings.indices { rings[i].time += dt }
        rings.removeAll { $0.time >= 0.4 }
        for i in breaking.indices { breaking[i].time += dt }
        breaking.removeAll { $0.time >= SE.heartBreak }
        if state == .lost { lostTime += dt }
        if state == .won {
            wonTime += dt
            view = straighten(turn(1, -SE.winSpin * dt) * view)
        }
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

    /// The shader that ray traces the box, seen the way this projector sees it.
    func shader(cells: [Float], hurt: Double, displayScale: Double) -> Shader {
        let rows = view.transpose   // its columns are the view's rows
        func row(_ r: SIMD3<Double>) -> Shader.Argument { .float3(r.x, r.y, r.z) }
        let box = SnakeEscape.box.double
        return ShaderLibrary.snakeBox(
            .float4(center.x, center.y, zoom, displayScale),
            .float3(unit, camera, hurt),
            row(rows.columns.0), row(rows.columns.1), row(rows.columns.2),
            .float3(box.x, box.y, box.z),
            .floatArray(cells),
            .floatArray(CellTable.palette))
    }
}

// MARK: - Screen

struct SnakeEscapeView: View {
    @State private var game = SnakeEscapeGame()
    @State private var lastDrag = CGSize.zero
    @State private var pinchStart: Double?   // zoom when the pinch began, while pinching
    @State private var boxArea = CGSize.zero  // size of the area the box is drawn in
    @Environment(\.displayScale) private var displayScale

    var body: some View {
        ZStack {
            backdrop
            // The box fills the whole screen, behind the words and buttons
            GeometryReader { geo in
                let projector = Projector(view: game.view, zoom: game.zoom, size: geo.size)
                let painter = BoxPainter(game: game, projector: projector)
                ZStack {
                    Rectangle()
                        .fill(.black)
                        .colorEffect(projector.shader(cells: game.cellTable, hurt: game.hurt * game.hurt,
                                                      displayScale: displayScale))
                    Canvas { context, _ in painter.paint(&context) }
                    Canvas { context, _ in painter.paintEffects(&context) }
                }
                .offset(game.shakeOffset)
                .contentShape(Rectangle())
                .gesture(turning)
                .simultaneousGesture(zooming)
                .onTapGesture(coordinateSpace: .local) { tap($0, projector) }
                .onGeometryChange(for: CGSize.self) { $0.size } action: { boxArea = $0 }
            }
            flash
            hud
            banners
        }
        #if DEBUG
        .task { await autoplay() }
        #endif
    }

    /// Blue at the top fading to black at the bottom, with a soft glow behind the box.
    private var backdrop: some View {
        ZStack {
            LinearGradient(colors: [SE.bgTop, SE.bgBottom], startPoint: .top, endPoint: .bottom)
            RadialGradient(colors: [SE.glow.opacity(0.35), .clear], center: .center,
                           startRadius: 0, endRadius: 380)
                .mask(LinearGradient(colors: [.white, .clear], startPoint: .top, endPoint: .bottom))
        }
        .ignoresSafeArea()
    }

    /// The red flash after a bump: a quick wash of red and a red rim round the screen.
    @ViewBuilder private var flash: some View {
        if game.hurt > 0 {
            ZStack {
                Color(red: 0.6, green: 0, blue: 0)
                    .opacity(pow(game.hurt, 3) * 0.45)
                    .blendMode(.plusLighter)
                RadialGradient(colors: [.clear, Color(red: 0.86, green: 0.08, blue: 0.08).opacity(0.8)],
                               center: .center, startRadius: 200, endRadius: 600)
                    .opacity(game.hurt)
            }
            .ignoresSafeArea()
            .allowsHitTesting(false)
        }
    }

    private var hud: some View {
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
                            .overlay {
                                if let lost = game.breaking.last(where: { $0.heart == i }) {
                                    BreakingHeart(time: lost.time)
                                }
                            }
                    }
                }
                .font(.system(size: 22))
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("\(game.lives) lives left")
            }
            .padding(.horizontal, 20)

            Spacer()

            Text("Drag to turn the cube, pinch to zoom, tap a snake to send it off its face")
                .font(.system(size: 14, weight: .medium, design: .rounded))
                .foregroundStyle(SE.textDim)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 20)
                .allowsHitTesting(false)

            HStack(spacing: 10) {
                Button("Restart") { game.restart() }
                Button("New") { game.newPuzzle() }
            }
            .buttonStyle(CarParkButtonStyle())
            .disabled(game.generating)
            .padding(.bottom, 8)
        }
    }

    private func tap(_ point: CGPoint, _ projector: Projector) {
        if let cell = projector.cell(at: point), let id = game.grid[cell] { game.send(id) }
    }

    #if DEBUG
    /// Launch with -autoplay to watch the box clear itself (handy for testing in
    /// the simulator). It turns the box and taps the screen where a free snake
    /// is drawn, the same way a finger would. With -autobump it taps blocked
    /// snakes instead, to show off losing.
    private func autoplay() async {
        let arguments = ProcessInfo.processInfo.arguments
        let bumping = arguments.contains("-autobump")
        guard arguments.contains("-autoplay") || bumping else { return }
        var steps = 0.0
        while !Task.isCancelled {
            try? await Task.sleep(for: .milliseconds(bumping ? 1200 : 250))
            guard game.state == .playing, !game.generating, boxArea != .zero else { continue }
            // Rock the tilt as it spins, so every face comes round to the front
            steps += 1
            game.rotate(by: CGSize(width: 9, height: 12 * sin(steps / 8)))
            let projector = Projector(view: game.view, zoom: game.zoom, size: boxArea)
            let target = game.onBox.lazy.filter { game.isFree($0) != bumping }.compactMap { id in
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
            WinScreen(game: game)
        } else if game.state == .lost {
            // The screen dims, then the words slam down from huge
            let landed = min(1, game.lostTime / SE.slamTime)
            ZStack {
                Color.black.opacity(0.5 * min(1, game.lostTime / 0.5))
                    .ignoresSafeArea()
                    .allowsHitTesting(false)
                VStack(spacing: 14) {
                    banner("Out of lives", color: SE.bump)
                        .scaleEffect(1 + 3 * (1 - landed) * (1 - landed))
                        .opacity(min(1, 0.3 + landed))
                    HStack(spacing: 10) {
                        Button("Try Again") { game.restart() }
                        Button("New Puzzle") { game.newPuzzle() }
                    }
                    .buttonStyle(CarParkButtonStyle())
                    .opacity(landed == 1 ? 1 : 0)
                }
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

/// A just-lost heart: it swells white, then splits in two and falls away.
private struct BreakingHeart: View {
    let time: Double

    var body: some View {
        if time < 0.12 {
            let f = time / 0.12
            let c = SE.heartRGB + (SIMD3(255, 255, 255) - SE.heartRGB) * f
            Image(systemName: "heart.fill")
                .foregroundStyle(rgb(c.x, c.y, c.z))
                .scaleEffect(1 + 0.6 * f)
        } else {
            let t = time - 0.12
            let fade = max(0, 1 - t / (SE.heartBreak - 0.12))
            ZStack {
                ForEach([-1.0, 1.0], id: \.self) { side in
                    Image(systemName: "heart.fill")
                        .foregroundStyle(SE.heart)
                        .scaleEffect(1.6)
                        .mask {
                            GeometryReader { geo in
                                Rectangle()
                                    .frame(width: geo.size.width / 2)
                                    .offset(x: side < 0 ? 0 : geo.size.width / 2)
                            }
                            .scaleEffect(1.6)
                        }
                        .rotationEffect(.degrees(side * 260 * t))
                        .offset(x: side * (6 + 35 * t), y: -45 * t + 350 * t * t)
                        .opacity(fade)
                }
            }
        }
    }
}

/// The snakes on the move, and the sparks, drawn over the ray traced box
/// (following snake_escape.py).
private struct BoxPainter {
    let puzzle: [SnakeEscape.Snake]
    let tracks: [SnakeEscape.Track]
    let leaving: [(id: Int, travelled: Double, speed: Double)]
    let bumps: [(id: Int, time: Double, free: Int, hit: Bool)]
    let sparks: [SnakeEscapeGame.Spark]
    let rings: [(origin: SIMD3<Double>, time: Double)]
    let projector: Projector

    // Read everything the drawing needs here, so SwiftUI redraws when it changes
    init(game: SnakeEscapeGame, projector: Projector) {
        puzzle = game.puzzle
        tracks = game.tracks
        leaving = game.leaving
        bumps = game.bumps
        sparks = game.sparks
        rings = game.rings
        self.projector = projector
    }

    func paint(_ context: inout GraphicsContext) {
        guard tracks.count == puzzle.count else { return }
        var facing: [SnakeEscape.Vec: Double] = [:]
        for face in SnakeEscape.faces { facing[face.out] = projector.shown(face.out) }
        for bump in bumps {
            let lunge = (Double(bump.free) + 0.25) * (1 - abs(2 * bump.time / SE.bumpTime - 1))
            let flicker = bump.hit && Int(bump.time * 30) % 2 == 1
            drawSnake(&context, bump.id, travelled: lunge, color: flicker ? .white : SE.bump, facing: facing)
        }
        for item in leaving {
            drawSnake(&context, item.id, travelled: item.travelled,
                      color: SE.snakeColors[puzzle[item.id].color], facing: facing)
        }
    }

    /// Shock waves and sparks where blocked snakes hit.
    func paintEffects(_ context: inout GraphicsContext) {
        for ring in rings {
            let f = ring.time / 0.4
            let at = projector.project(ring.origin)
            let r = 6 + 60 * pow(f, 0.6)
            context.stroke(Path(ellipseIn: CGRect(x: at.x - r, y: at.y - r, width: 2 * r, height: 2 * r)),
                           with: .color(rgb(255, 200, 160).opacity(1 - f)), lineWidth: max(1, 4 * (1 - f)))
        }
        for spark in sparks {
            let at = projector.project(spark.origin)
            let x = at.x + spark.x, y = at.y + spark.y
            var streak = Path()
            streak.move(to: CGPoint(x: x, y: y))
            streak.addLine(to: CGPoint(x: x - spark.vx * 0.025, y: y - spark.vy * 0.025))
            context.stroke(streak, with: .color(spark.color.opacity(min(1, spark.life / 0.3))),
                           lineWidth: spark.life > 0.2 ? 2 : 1)
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

// MARK: - Winning

/// 0 before `t` reaches 0, overshooting past 1 and settling there by `length`.
private func pop(_ t: Double, _ length: Double = 0.35) -> Double {
    guard t > 0 else { return 0 }
    let f = min(1, t / length) - 1
    return 1 + 2.70158 * f * f * f + 1.70158 * f * f
}

private func mix(_ a: SIMD3<Double>, _ b: SIMD3<Double>, _ f: Double) -> Color {
    let c = a + (b - a) * f
    return rgb(c.x, c.y, c.z)
}

/// Random numbers that come out the same every time from the same seed, so
/// the confetti and fireworks can be worked out afresh for any moment.
private struct Seeded {
    var state: UInt64
    init(_ seed: UInt64) { state = seed }

    mutating func next() -> Double {
        state &+= 0x9E37_79B9_7F4A_7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58_476D_1CE4_E5B9
        z = (z ^ (z >> 27)) &* 0x94D0_49BB_1331_11EB
        return Double((z ^ (z >> 31)) >> 11) / Double(1 << 53)
    }

    mutating func range(_ low: Double, _ high: Double) -> Double { low + (high - low) * next() }
}

/// One letter of the title as a shiny sweet: a gradient face with a wet
/// highlight and bevelled rims, pushed out into a solid block, inside a dark
/// outline (following glossy_letter in snake_escape.py). With `inside` it is
/// just a white mask of the face less its rims, where the sweeping shine goes.
private struct LetterArt: View {
    static let font = Font.system(size: 72, weight: .black, design: .rounded)
    static let depth = 9.0, slant = 0.35, outline = 3.5, pad = 6.0
    static let insets = EdgeInsets(top: pad, leading: pad, bottom: pad + depth + 6,
                                   trailing: pad + depth * slant + 6)

    let letter: String
    let color: SIMD3<Double>
    var inside = false

    var body: some View {
        let black = SIMD3<Double>(0, 0, 0), white = SIMD3<Double>(255, 255, 255)
        ZStack {
            if inside {
                shrunk(by: 2.5)
            } else {
                // A soft shadow on the scene behind, then the outline round the whole block
                text.foregroundStyle(.black.opacity(0.35))
                    .offset(x: Self.depth * Self.slant + 4, y: Self.depth + 5)
                    .blur(radius: 3)
                ForEach(Self.outlineSteps.indices, id: \.self) { i in
                    text.foregroundStyle(rgb(10, 8, 22)).offset(Self.outlineSteps[i])
                }
                // The block's sides: darker the further back, with a lit band
                // just behind the face like light catching a polished edge
                ForEach((1...Int(Self.depth)).reversed(), id: \.self) { d in
                    let f = Double(d) / Self.depth
                    text.foregroundStyle(d <= 1 ? mix(color, white, 0.25) : mix(color, black, 0.35 + 0.4 * f))
                        .offset(x: Double(d) * Self.slant, y: Double(d))
                }
                // The face: light at the top, deep at the bottom (the capitals
                // fill roughly the middle 60% of the line)
                text.foregroundStyle(LinearGradient(stops: [
                    .init(color: mix(color, white, 0.5), location: 0.22),
                    .init(color: mix(color, white, 0), location: 0.5),
                    .init(color: mix(color, black, 0.45), location: 0.8),
                ], startPoint: .top, endPoint: .bottom))
                // Bevels: bright rims facing up and left, dark ones facing down and right
                rim(dx: 1, dy: 1, .white).opacity(0.8)
                rim(dx: 2.5, dy: 2.5, .white).opacity(0.3)
                rim(dx: -1.5, dy: -1.5, .black).opacity(0.5)
                gloss
            }
        }
        .padding(Self.insets)
    }

    private var text: Text { Text(letter).font(Self.font) }

    static let outlineSteps: [CGSize] = stride(from: 0.0, through: depth, by: 1.5).flatMap { d in
        (0..<16).map { i in
            let a = 2 * Double.pi * Double(i) / 16
            return CGSize(width: d * slant + cos(a) * outline, height: d + sin(a) * outline)
        }
    }

    /// The rim of the letter on the side facing (-dx, -dy).
    private func rim(dx: Double, dy: Double, _ color: Color) -> some View {
        ZStack {
            text.foregroundStyle(color)
            text.foregroundStyle(.black).offset(x: dx, y: dy).blendMode(.destinationOut)
        }
        .compositingGroup()
    }

    /// The letter in white with `by` points eaten off all round.
    private func shrunk(by r: Double) -> some View {
        var shape = AnyView(text.foregroundStyle(.white))
        for i in 0..<8 {
            let a = 2 * Double.pi * Double(i) / 8
            shape = AnyView(shape.mask(text.offset(x: cos(a) * r, y: sin(a) * r)))
        }
        return shape
    }

    /// The wet highlight: a bright band over the top half with a curved lower
    /// edge, kept off the rims, and a little sharp glint near the top left.
    private var gloss: some View {
        text.foregroundStyle(.clear)
            .overlay {
                GeometryReader { geo in
                    let w = geo.size.width, h = geo.size.height
                    ZStack {
                        Ellipse()
                            .fill(LinearGradient(stops: [
                                .init(color: .white.opacity(0.85), location: 0.45),
                                .init(color: .white.opacity(0.15), location: 1),
                            ], startPoint: .top, endPoint: .bottom))
                            .frame(width: w * 1.8, height: h * 0.7)
                            .position(x: w / 2, y: h * 0.15)
                        Capsule()
                            .fill(.white.opacity(0.9))
                            .frame(width: w * 0.3, height: h * 0.045)
                            .position(x: w * 0.3, y: h * 0.3)
                    }
                }
            }
            .mask(shrunk(by: 2.5))
    }
}

/// The title's letters, drawn once into pictures.
@MainActor private enum WinTitle {
    struct Letter {
        let art: UIImage, inside: UIImage
        let advance: Double    // how far along the next letter's face starts
        let height: Double     // how tall the face is
    }

    static let letters: [Letter] = Array("ALL OUT!").enumerated().map { i, letter in
        let c = SnakeEscape.colors[i * 3 % SnakeEscape.colors.count]
        let color = SIMD3(c[0], c[1], c[2])
        let art = picture(LetterArt(letter: String(letter), color: color))
        let inside = picture(LetterArt(letter: String(letter), color: color, inside: true))
        let insets = LetterArt.insets
        return Letter(art: art, inside: inside,
                      // The outlines and blocks crowd the gap between the words, so widen it
                      advance: art.size.width - insets.leading - insets.trailing + (letter == " " ? 12 : 0),
                      height: art.size.height - insets.top - insets.bottom)
    }

    private static func picture(_ view: LetterArt) -> UIImage {
        let renderer = ImageRenderer(content: view)
        renderer.scale = 3
        return renderer.uiImage ?? UIImage()
    }
}

/// The celebration once every snake is out: confetti, fireworks, the title
/// dropping in a letter at a time and a card with how it went.
private struct WinScreen: View {
    let game: SnakeEscapeGame

    var body: some View {
        let t = game.wonTime
        ZStack {
            Color(red: 0, green: 0, blue: 0.04)
                .opacity(0.45 * min(1, t / 0.6))
                .ignoresSafeArea()
            Celebration(time: t, seed: game.winSeed)
                .ignoresSafeArea()
            GeometryReader { geo in
                VStack(spacing: 34) {
                    title(t, width: geo.size.width - 24)
                    card(t)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .allowsHitTesting(t > 1.2)
    }

    /// "ALL OUT!" drops in a letter at a time, then keeps bobbing, with a
    /// shine sweeping across it now and then.
    private func title(_ t: Double, width: Double) -> some View {
        let letters = WinTitle.letters
        let total = letters.map(\.advance).reduce(0, +)
        let height = letters.map(\.height).max() ?? 0
        let insets = LetterArt.insets
        let sweep = t > 1.2 ? (t - 1.2).truncatingRemainder(dividingBy: SE.shineEvery) * 450 - 100 : -1000
        var lefts: [Double] = [0]
        for letter in letters { lefts.append(lefts.last! + letter.advance) }

        return ZStack(alignment: .topLeading) {
            ForEach(letters.indices, id: \.self) { i in
                let letter = letters[i]
                let scale = pop(t - 0.15 - Double(i) * 0.07, 0.4)
                // Turn and grow about the middle of the face, not the block behind it
                let anchor = UnitPoint(x: (insets.leading + letter.advance / 2) / letter.art.size.width,
                                       y: (insets.top + letter.height / 2) / letter.art.size.height)
                Image(uiImage: letter.art)
                    .overlay {
                        Rectangle()
                            .fill(.white.opacity(0.65))
                            .frame(width: 20, height: letter.art.size.height * 1.5)
                            .rotationEffect(.degrees(20))
                            .position(x: insets.leading + sweep - lefts[i], y: letter.art.size.height / 2)
                            .mask(Image(uiImage: letter.inside))
                    }
                    .scaleEffect(scale, anchor: anchor)
                    .rotationEffect(.degrees(sin(t * 2.4 - Double(i) * 0.7) * 5), anchor: anchor)
                    .offset(x: lefts[i] - insets.leading,
                            y: sin(t * 3.2 - Double(i) * 0.55) * 4.5 - insets.top)
                    .opacity(scale > 0.02 ? 1 : 0)
            }
        }
        .frame(width: total, height: height, alignment: .topLeading)
        .scaleEffect(min(1, width / total))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("All out!")
    }

    /// How long it took and how many lives were kept, rising up under the title.
    private func card(_ t: Double) -> some View {
        let f = pop(t - 0.8, 0.45)
        let minutes = Int(game.playTime) / 60, seconds = Int(game.playTime) % 60
        let lost = SnakeEscape.lives - game.lives
        let settled = t > 1.1 + Double(SnakeEscape.lives) * 0.15
        return VStack(spacing: 14) {
            Text("Solved in \(minutes):\(String(format: "%02d", seconds))")
                .font(.system(size: 26, weight: .bold, design: .rounded))
                .foregroundStyle(.white)
                .shadow(color: .black, radius: 0, x: 2, y: 2)
            HStack(spacing: 18) {
                ForEach(0..<SnakeEscape.lives, id: \.self) { i in
                    Image(systemName: "heart.fill")
                        .font(.system(size: 38))
                        .foregroundStyle(i < game.lives ? SE.heart : SE.heartLost)
                        .scaleEffect(pop(t - 1.1 - Double(i) * 0.15, 0.3))
                }
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("\(game.lives) lives kept")
            Text(lost == 0 ? "Flawless!" : "\(lost) \(lost == 1 ? "life" : "lives") lost")
                .font(.system(size: 21, weight: .bold, design: .rounded))
                .foregroundStyle(lost == 0 ? SE.text : SE.textDim)
                .shadow(color: .black, radius: 0, x: 2, y: 2)
                .opacity(settled ? 1 : 0)
            Button("New Puzzle") { game.newPuzzle() }
                .buttonStyle(CarParkButtonStyle())
                .opacity(settled ? 1 : 0)
        }
        .padding(.vertical, 22)
        .frame(width: 290)
        .background(RoundedRectangle(cornerRadius: 24).fill(rgb(14, 16, 30).opacity(0.85)))
        .overlay(RoundedRectangle(cornerRadius: 24).strokeBorder(SE.text, lineWidth: 2.5))
        .opacity(min(1, f))
        .offset(y: 40 * (1 - min(1, f)))
    }
}

/// Confetti raining down and fireworks going off, worked out for the moment `time`.
private struct Celebration: View {
    let time: Double
    let seed: UInt64

    var body: some View {
        Canvas { context, size in
            var random = Seeded(seed)
            for _ in 0..<SE.confetti {
                let x0 = random.range(0, size.width), y0 = random.range(-size.height, -10)
                let vx = random.range(-20, 20), vy = random.range(70, 150)
                let phase = random.range(0, 2 * .pi), spin = random.range(-6, 6)
                let color = SE.snakeColors[Int(random.next() * Double(SE.snakeColors.count))]
                let y = y0 + vy * time
                guard y < size.height + 10 else { continue }
                // A small card turning over: its width swings as it spins
                var piece = context
                piece.translateBy(x: x0 + vx * time + 30 * sin(time * 2 + phase), y: y)
                piece.rotate(by: .radians(phase + spin * time * 0.7))
                let w = max(1, abs(6 * cos(phase + spin * time)))
                piece.fill(Path(CGRect(x: -w / 2, y: -1.75, width: w, height: 3.5)), with: .color(color))
            }

            var start = 0.15, burst: UInt64 = 0
            while start < time {
                burst += 1
                var random = Seeded(seed &+ burst &* 7919)
                let center = CGPoint(x: random.range(60, size.width - 60),
                                     y: random.range(size.height * 0.12, size.height * 0.45))
                let pick = { (r: Double) in SE.snakeColors[Int(r * Double(SE.snakeColors.count))] }
                let colors = [pick(random.next()), pick(random.next()), Color.white]
                let age = time - start
                if age < 1.6 {
                    for _ in 0..<60 {
                        let angle = random.range(0, 2 * .pi), speed = random.range(40, 190)
                        let life = random.range(0.8, 1.5)
                        let color = colors[Int(random.next() * 3)]
                        guard age < life else { continue }
                        // Slowed by the air, and falling a little
                        let gone = (1 - exp(-1.6 * age)) / 1.6
                        let now = speed * exp(-1.6 * age)
                        let p = CGPoint(x: center.x + cos(angle) * speed * gone,
                                        y: center.y + sin(angle) * speed * gone + 65 * age * age)
                        var trail = Path()
                        trail.move(to: p)
                        trail.addLine(to: CGPoint(x: p.x - cos(angle) * now * 0.05,
                                                  y: p.y - sin(angle) * now * 0.05 - 6 * age))
                        context.stroke(trail, with: .color(color.opacity(min(1, (life - age) / 0.5))),
                                       style: StrokeStyle(lineWidth: 2, lineCap: .round))
                    }
                }
                start += SE.burstEvery * random.range(0.6, 1.4)
            }
        }
        .allowsHitTesting(false)
    }
}
