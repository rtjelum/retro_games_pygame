import SwiftUI

// Navy and slate, matching the Python game
extension Color {
    init(_ c: RGB, opacity: Double = 1) { self.init(red: c.r, green: c.g, blue: c.b, opacity: opacity) }
    init(r: Double, g: Double, b: Double, a: Double = 255) {
        self.init(red: r / 255, green: g / 255, blue: b / 255, opacity: a / 255)
    }
    static let bgTop = Color(r: 40, g: 44, b: 78)
    static let bgBottom = Color(r: 10, g: 10, b: 20)
    static let spotlight = Color(r: 110, g: 130, b: 230)
    static let slateTop = Color(r: 58, g: 62, b: 92)
    static let slateBottom = Color(r: 30, g: 32, b: 52)
    static let tileA = Color(r: 18, g: 20, b: 36, a: 210)
    static let tileB = Color(r: 24, g: 26, b: 46, a: 210)
    static let edge = Color(r: 12, g: 12, b: 24)
    static let gold = Color(r: 255, g: 215, b: 120)
    static let textDim = Color(r: 170, g: 178, b: 215)
    static let goldTop = Color(r: 255, g: 240, b: 180)
    static let goldBottom = Color(r: 214, g: 140, b: 40)
    static let danger = Color(r: 255, g: 96, b: 110)
}

struct CandySwapView: View {
    @State private var game = CandyGame()

    var body: some View {
        // The timeline sits inside the GeometryReader so the whole screen is rebuilt every frame.
        GeometryReader { geo in
            TimelineView(.animation) { timeline in
                let _ = game.tick(timeline.date)
                let board = min(geo.size.width - 56, geo.size.height * 0.56, 600)
                VStack(spacing: 0) {
                    Spacer(minLength: 4)
                    OutlinedText(text: "CANDY SWAP", font: .custom("Georgia-Bold", size: 40),
                                 top: .goldTop, bottom: .goldBottom, thickness: 2)
                    Spacer(minLength: 8)
                    HStack(spacing: 10) {
                        Badge(label: "SCORE", value: game.score)
                        Badge(label: "MOVES", value: game.moves,
                              color: game.moves <= 5 && game.phase != .over ? .danger : .white)
                        Badge(label: "BEST", value: game.best)
                    }
                    .frame(width: board + 28)
                    Spacer(minLength: 14)
                    CandyBoardView(game: game, side: board, time: game.time)
                    Spacer(minLength: 14)
                    VStack(spacing: 4) {
                        Text("4 in a line = striped    2×2 = fish")
                        Text("L or T = bomb    5 in a line = colour bomb")
                    }
                    .font(.system(size: 13, weight: .medium, design: .rounded))
                    .foregroundStyle(Color.textDim)
                    Spacer(minLength: 10)
                    HStack(spacing: 12) {
                        Button("Hint") { game.showHint() }
                        Button("New Game") { game.newGame() }
                    }
                    .buttonStyle(SlateButtonStyle())
                    Spacer(minLength: 4)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .overlay {
                    if game.phase == .over {
                        GameOverCard(game: game)
                    }
                }
            }
        }
        .background(CandyBackdrop())
    }
}

// MARK: - Pieces of the screen

struct CandyBackdrop: View {
    var body: some View {
        ZStack {
            LinearGradient(colors: [.bgTop, .bgBottom], startPoint: .top, endPoint: .bottom)
            RadialGradient(colors: [.spotlight.opacity(0.18), .clear], center: UnitPoint(x: 0.5, y: 0.45),
                           startRadius: 0, endRadius: 420)
        }
        .ignoresSafeArea()
    }
}

/// A raised slate panel with a soft shadow and a lit rim.
struct SlatePanel: View {
    var radius: CGFloat
    var body: some View {
        RoundedRectangle(cornerRadius: radius)
            .fill(LinearGradient(colors: [.slateTop, .slateBottom], startPoint: .top, endPoint: .bottom))
            .overlay(RoundedRectangle(cornerRadius: radius).strokeBorder(.white.opacity(0.2), lineWidth: 1.5))
            .shadow(color: .black.opacity(0.55), radius: 8, y: 5)
    }
}

/// Text with a gradient fill, a thick outline and a drop shadow.
struct OutlinedText: View {
    let text: String
    let font: Font
    let top: Color
    let bottom: Color
    let thickness: CGFloat

    var body: some View {
        let base = Text(text).font(font).lineLimit(1)
        let angles = (0..<16).map { Double($0) * .pi / 8 }
        ZStack {
            ZStack {
                ForEach(angles, id: \.self) { a in
                    base.offset(x: cos(a) * thickness, y: sin(a) * thickness + 4)
                }
            }
            .foregroundStyle(.black)
            .compositingGroup()
            .opacity(0.47)
            ForEach(angles, id: \.self) { a in
                base.foregroundStyle(Color.edge).offset(x: cos(a) * thickness, y: sin(a) * thickness)
            }
            base.foregroundStyle(LinearGradient(colors: [top, bottom], startPoint: .top, endPoint: .bottom))
        }
        .minimumScaleFactor(0.5)
    }
}

struct Badge: View {
    let label: String
    let value: Int
    var color: Color = .white

    var body: some View {
        VStack(spacing: 1) {
            Text(label)
                .font(.system(size: 11, weight: .bold, design: .rounded))
                .foregroundStyle(Color.textDim)
            Text(verbatim: String(value))
                .font(.system(size: 22, weight: .bold, design: .rounded))
                .foregroundStyle(color)
                .shadow(color: .black, radius: 0, x: 1.5, y: 1.5)
                .lineLimit(1)
                .minimumScaleFactor(0.6)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 7)
        .background(SlatePanel(radius: 14))
    }
}

struct SlateButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 17, weight: .bold, design: .rounded))
            .foregroundStyle(Color.gold)
            .padding(.horizontal, 22)
            .padding(.vertical, 10)
            .background(SlatePanel(radius: 14))
            .scaleEffect(configuration.isPressed ? 0.95 : 1)
    }
}

struct GameOverCard: View {
    let game: CandyGame

    var body: some View {
        ZStack {
            Color(r: 6, g: 6, b: 14, a: 130).ignoresSafeArea()
            VStack(spacing: 16) {
                OutlinedText(text: game.newBest ? "Sweet!" : "Out of moves",
                             font: .system(size: 40, weight: .heavy, design: .rounded),
                             top: .goldTop, bottom: .goldBottom, thickness: 3)
                Text("Score \(game.score)" + (game.newBest ? "  –  new best!" : "    Best \(game.best)"))
                    .font(.system(size: 20, weight: .bold, design: .rounded))
                    .foregroundStyle(.white)
                    .shadow(color: .black, radius: 0, x: 1.5, y: 1.5)
                Button("Play Again") { game.newGame() }
                    .buttonStyle(SlateButtonStyle())
            }
            .padding(.horizontal, 28)
            .padding(.vertical, 26)
            .background(SlatePanel(radius: 20))
            .padding(.horizontal, 24)
        }
    }
}

// MARK: - The board

struct CandyBoardView: View {
    let game: CandyGame
    let side: CGFloat
    let time: Double     // changes every frame, so the board redraws

    var body: some View {
        let cell = side / CGFloat(SIZE)
        let u = cell / 64            // one point in the Python game's layout
        let margin = cell * 1.2      // room for effects that spill past the board

        Color.clear
            .frame(width: side, height: side)
            .contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { drag in
                        game.touchMoved(CGPoint(x: drag.location.x / cell, y: drag.location.y / cell))
                    }
                    .onEnded { _ in game.touchEnded() }
            )
            .background(SlatePanel(radius: 24 * u).padding(-14 * u))
            .overlay {
                Canvas { [time] context, _ in
                    _ = time
                    BoardPainter(game: game, cell: cell, u: u, origin: margin).paint(&context)
                }
                .frame(width: side + 2 * margin, height: side + 2 * margin)
                .allowsHitTesting(false)
            }
            .overlay {
                if let message = game.message {
                    OutlinedText(text: message.text, font: .system(size: 22, weight: .bold, design: .rounded),
                                 top: .white, bottom: .white, thickness: 3)
                        .allowsHitTesting(false)
                }
            }
    }
}

/// Draws the board, candies and effects, following draw_board() in the Python game.
struct BoardPainter {
    let game: CandyGame
    let cell: CGFloat
    let u: CGFloat
    let origin: CGFloat

    func point(_ p: CGPoint) -> CGPoint {
        CGPoint(x: origin + p.x * cell, y: origin + p.y * cell)
    }

    func paint(_ context: inout GraphicsContext) {
        let sprites = Sprites.shared
        var resolved: [ObjectIdentifier: GraphicsContext.ResolvedImage] = [:]
        func image(_ ui: UIImage) -> GraphicsContext.ResolvedImage {
            let key = ObjectIdentifier(ui)
            if let r = resolved[key] { return r }
            let r = context.resolve(Image(uiImage: ui))
            resolved[key] = r
            return r
        }
        func drawCandy(_ ui: UIImage, at p: CGPoint, scale: CGFloat = 1, in ctx: GraphicsContext? = nil) {
            let s = (cell - 2 * u) * scale
            (ctx ?? context).draw(image(ui), in: CGRect(x: p.x - s / 2, y: p.y - s / 2, width: s, height: s))
        }

        // Slots
        let gap = 2 * u
        for p in allCells {
            let slot = CGRect(x: origin + CGFloat(p.x) * cell + gap, y: origin + CGFloat(p.y) * cell + gap,
                              width: cell - 2 * gap, height: cell - 2 * gap)
            context.fill(Path(roundedRect: slot, cornerRadius: 12 * u),
                         with: .color((p.x + p.y) % 2 == 1 ? .tileA : .tileB))
            var line = Path()
            line.move(to: CGPoint(x: slot.minX + 10 * u, y: slot.maxY - 0.5))
            line.addLine(to: CGPoint(x: slot.maxX - 10 * u, y: slot.maxY - 0.5))
            context.stroke(line, with: .color(.white.opacity(0.12)), lineWidth: max(0.5, u))
        }

        // Hint and selection glows
        let hinted: [Pos] = game.phase == .idle ? (game.hint.map { [$0.0, $0.1] } ?? []) : []
        let pulse = (sin(game.time * 7) + 1) / 2
        for p in hinted { glow(&context, p, color: .gold, alpha: (120 + 135 * pulse) / 255) }
        if let s = game.selected { glow(&context, s, color: .white, alpha: 230 / 255) }

        // Two candies trading places
        var moving: [Pos: CGPoint] = [:]
        if let swap = game.swap {
            var t = min(1, game.timer / SWAP_TIME)
            t = t * t * (3 - 2 * t)
            let a = center(swap.a), b = center(swap.b)
            moving[swap.a] = CGPoint(x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t)
            moving[swap.b] = CGPoint(x: b.x + (a.x - b.x) * t, y: b.y + (a.y - b.y) * t)
        }

        // Candies, clipped so new ones slide in from the top edge
        var candies = context
        let board = CGFloat(SIZE) * cell
        candies.clip(to: Path(CGRect(x: origin - 14 * u, y: origin, width: board + 28 * u, height: board + 14 * u)))
        for p in allCells {
            guard let kind = game.grid[p] else { continue }
            let power = game.special[p]
            var c = moving[p] ?? center(p)
            c.y -= game.fall[p]
            var scale = 1.0
            if game.popping.contains(p) {
                let t = game.timer / POP_TIME
                scale = t > 0.15 ? max(0, 1.2 - 1.2 * t * t) : 1 + t * 1.3
            } else if p == game.selected {
                scale = 1.07 + 0.04 * sin(game.time * 8)
            } else if hinted.contains(p) {
                scale = 1 + 0.05 * sin(game.time * 7)
            } else if power == .bomb || kind == COLOR_BOMB {
                scale = 1 + 0.035 * sin(game.time * 5 + Double(p.x + p.y))   // specials breathe
            }
            if scale > 0 {
                drawCandy(sprites.image(kind: kind, power: power), at: point(c), scale: scale, in: candies)
            }
        }

        // Fish leap in an arc to their target
        for swim in game.swims {
            let t = swim.age / SWIM_TIME
            let x = swim.start.x + (swim.end.x - swim.start.x) * t
            let y = swim.start.y + (swim.end.y - swim.start.y) * t - sin(.pi * t) * 1.2
            let kind = swim.kind.flatMap { $0 < KINDS ? $0 : nil } ?? 0
            var fishContext = context
            fishContext.translateBy(x: point(CGPoint(x: x, y: y)).x, y: point(CGPoint(x: x, y: y)).y)
            if swim.end.x < swim.start.x { fishContext.scaleBy(x: -1, y: 1) }
            drawCandy(sprites.fish[kind], at: .zero, scale: 0.7, in: fishContext)
        }

        drawBeams(&context, board: board)

        for blast in game.blasts {
            let t = blast.age / EFFECT_TIME
            let r = cell * blast.radius * (0.4 + 0.6 * t)
            let fade = 200 / 255 * (1 - t)
            let p = point(blast.pos)
            let circle = Path(ellipseIn: CGRect(x: p.x - r, y: p.y - r, width: 2 * r, height: 2 * r))
            context.fill(circle, with: .color(Color(blast.color.mix(.white, 0.5), opacity: fade / 2)))
            context.stroke(circle, with: .color(.white.opacity(fade)), lineWidth: max(2, 6 * u * (1 - t)))
        }

        var rng = SeededRandom(seed: UInt64(game.time * 30))
        for bolt in game.bolts {
            let fade = 1 - bolt.age / EFFECT_TIME
            var path = Path()
            path.move(to: point(bolt.start))
            for i in 1..<6 {   // a jagged lightning bolt
                let t = Double(i) / 6
                path.addLine(to: point(CGPoint(
                    x: bolt.start.x + (bolt.end.x - bolt.start.x) * t + rng.next(in: -0.125...0.125),
                    y: bolt.start.y + (bolt.end.y - bolt.start.y) * t + rng.next(in: -0.125...0.125))))
            }
            path.addLine(to: point(bolt.end))
            context.stroke(path, with: .color(Color(r: 255, g: 230, b: 140).opacity(fade)),
                           style: StrokeStyle(lineWidth: max(2, 3 * u), lineJoin: .round))
            context.stroke(path, with: .color(.white.opacity(fade)), lineWidth: max(1, u))
        }

        for ring in game.rings {
            let t = ring.age / 0.35
            let r = cell * (0.25 + 0.45 * t)
            let p = point(ring.pos)
            context.stroke(Path(ellipseIn: CGRect(x: p.x - r, y: p.y - r, width: 2 * r, height: 2 * r)),
                           with: .color(Color(ring.color.mix(.white, 0.5), opacity: 220 / 255 * (1 - t))),
                           lineWidth: max(1, 5 * u * (1 - t)))
        }

        for p in game.particles {
            sparkle(&context, at: point(p.pos), radius: (7 * (1 - p.age / 0.6) + 1) * u,
                    color: Color(p.color), spin: p.spin + p.age * 6)
        }

        for popup in game.popups where popup.age >= 0 {
            let alpha = popup.age < 0.5 ? 1 : 1 - (popup.age - 0.5) / 0.4
            outlinedText(&context, popup.text, at: point(popup.pos), alpha: alpha)
        }
    }

    private func glow(_ context: inout GraphicsContext, _ p: Pos, color: Color, alpha: Double) {
        let slot = CGRect(x: origin + CGFloat(p.x) * cell, y: origin + CGFloat(p.y) * cell, width: cell, height: cell)
        let shape = Path(roundedRect: slot, cornerRadius: 14 * u)
        context.drawLayer { layer in
            layer.addFilter(.blur(radius: 3 * u))
            layer.fill(shape, with: .color(color.opacity(alpha / 3)))
            layer.stroke(shape, with: .color(color.opacity(alpha)), lineWidth: 3 * u)
        }
        context.fill(shape, with: .color(color.opacity(alpha / 3)))
        context.stroke(shape, with: .color(color.opacity(alpha)), lineWidth: 3 * u)
    }

    private func drawBeams(_ context: inout GraphicsContext, board: CGFloat) {
        for beam in game.beams {
            let t = beam.age / EFFECT_TIME
            let thick = cell * (0.7 - 0.5 * t)
            let mid = origin + (CGFloat(beam.index) + 0.5) * cell
            let rect, core: CGRect
            if beam.horizontal {
                rect = CGRect(x: origin, y: mid - thick / 2, width: board, height: thick)
                core = CGRect(x: origin, y: mid - thick / 6, width: board, height: thick / 3)
            } else {
                rect = CGRect(x: mid - thick / 2, y: origin, width: thick, height: board)
                core = CGRect(x: mid - thick / 6, y: origin, width: thick / 3, height: board)
            }
            let fade = 1 - t
            context.fill(Path(roundedRect: rect, cornerRadius: thick / 2),
                         with: .color(Color(r: 150, g: 190, b: 255).opacity(fade / 2)))
            context.fill(Path(roundedRect: core, cornerRadius: thick / 6), with: .color(.white.opacity(fade)))
        }
    }

    private func sparkle(_ context: inout GraphicsContext, at c: CGPoint, radius: CGFloat, color: Color, spin: Double) {
        var path = Path()
        for i in 0..<8 {
            let r = i % 2 == 0 ? radius : radius * 0.35
            let a = spin + Double(i) * .pi / 4
            let p = CGPoint(x: c.x + cos(a) * r, y: c.y + sin(a) * r)
            if i == 0 { path.move(to: p) } else { path.addLine(to: p) }
        }
        path.closeSubpath()
        context.fill(path, with: .color(color))
    }

    private func outlinedText(_ context: inout GraphicsContext, _ text: String, at p: CGPoint, alpha: Double) {
        let font = Font.system(size: 26 * u, weight: .bold, design: .rounded)
        let edge = context.resolve(Text(text).font(font).foregroundColor(.edge))
        let shadow = context.resolve(Text(text).font(font).foregroundColor(.black.opacity(0.4)))
        let face = context.resolve(Text(text).font(font).foregroundColor(Color(r: 255, g: 246, b: 215)))
        let thickness = 3 * u
        var ctx = context
        ctx.opacity = alpha
        ctx.draw(shadow, at: CGPoint(x: p.x, y: p.y + 4 * u))
        for i in 0..<12 {
            let a = Double(i) * .pi / 6
            ctx.draw(edge, at: CGPoint(x: p.x + cos(a) * thickness, y: p.y + sin(a) * thickness))
        }
        ctx.draw(face, at: p)
    }
}

/// Small repeatable random numbers, so the lightning flickers at a steady rate.
struct SeededRandom {
    var state: UInt64
    init(seed: UInt64) { state = seed &+ 0x9E3779B97F4A7C15 }
    mutating func next(in range: ClosedRange<Double>) -> Double {
        state = state &* 6364136223846793005 &+ 1442695040888963407
        let unit = Double(state >> 11) / Double(1 << 53)
        return range.lowerBound + (range.upperBound - range.lowerBound) * unit
    }
}

#Preview {
    CandySwapView()
}
