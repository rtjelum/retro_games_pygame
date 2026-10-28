import SwiftUI

// MARK: - Colours

private func rgb(_ r: Double, _ g: Double, _ b: Double) -> Color {
    Color(red: r / 255, green: g / 255, blue: b / 255)
}

private enum SD {
    static let bgTop = rgb(40, 44, 78), bgBottom = rgb(10, 10, 20)
    static let gold = rgb(255, 215, 120)
    static let paper = rgb(252, 251, 246)
    static let tint = rgb(232, 238, 252)          // row / column / box of the selected cell
    static let selected = rgb(200, 218, 255)
    static let line = rgb(30, 30, 40)
    static let given = rgb(30, 30, 30)
    static let entered = rgb(50, 110, 235)
    static let clash = rgb(220, 50, 50)
    static let pickerBG = rgb(245, 248, 255)
    static let pickerButton = rgb(220, 232, 255)
    static let confetti: [Color] = [rgb(225, 50, 50), rgb(50, 190, 80), rgb(50, 110, 235), rgb(245, 205, 40),
                                    rgb(170, 70, 220), rgb(40, 200, 215), rgb(255, 170, 40)]
}

// MARK: - Game state

@Observable
final class SudokuGame {
    var board: Sudoku.Board = []
    var fixed: [[Bool]] = []
    var selected: (r: Int, c: Int)?
    var pickerOpen = false
    var won = false
    var wonAt = Date()

    init() {
        newGame()
        #if DEBUG
        // Launch with -showPicker to open the number picker on an empty square (for screenshots)
        if ProcessInfo.processInfo.arguments.contains("-showPicker"),
           let i = (36..<81).first(where: { board[$0 / 9][$0 % 9] == 0 }) {
            tap(i / 9, i % 9)
        }
        #endif
    }

    func newGame() {
        board = Sudoku.generate()
        fixed = board.map { $0.map { $0 != 0 } }
        selected = nil
        pickerOpen = false
        won = false
    }

    func tap(_ r: Int, _ c: Int) {
        guard !won else { return }
        selected = (r, c)
        pickerOpen = !fixed[r][c]
    }

    /// Picker choices for the selected cell: possible numbers, then 0 = clear if it has a number.
    var choices: [Int] {
        guard let s = selected else { return [] }
        var list = Sudoku.candidates(board, s.r, s.c)
        if board[s.r][s.c] != 0 { list.append(0) }
        return list
    }

    func place(_ n: Int) {
        guard let s = selected else { return }
        board[s.r][s.c] = n
        pickerOpen = false
        if Sudoku.isSolved(board) {
            won = true
            wonAt = Date()
            selected = nil
        }
    }
}

// MARK: - Views

struct SudokuView: View {
    @State private var game = SudokuGame()

    var body: some View {
        VStack(spacing: 18) {
            HStack {
                Text("Sudoku")
                    .font(.custom("Georgia-Bold", size: 40))
                    .foregroundStyle(SD.gold)
                Spacer()
                Button("New Game") { withAnimation { game.newGame() } }
                    .font(.system(size: 17, weight: .bold, design: .rounded))
                    .foregroundStyle(SD.bgBottom)
                    .padding(.horizontal, 16).padding(.vertical, 10)
                    .background(SD.gold, in: Capsule())
            }
            .padding(.horizontal)

            SudokuBoardView(game: game)
                .padding(.horizontal, 8)
                .zIndex(1)   // keep the number picker above the hint text

            Text(game.won ? "Solved! 🎉" : "Tap an empty square to see the numbers that fit")
                .font(.system(size: game.won ? 28 : 16, weight: .semibold, design: .rounded))
                .foregroundStyle(game.won ? SD.gold : Color(white: 0.75))
                .multilineTextAlignment(.center)
                .padding(.horizontal)
            Spacer()
        }
        .padding(.top, 8)
        .frame(maxWidth: 560)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background {
            LinearGradient(colors: [SD.bgTop, SD.bgBottom], startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea()
                .onTapGesture { game.pickerOpen = false }
        }
        .overlay {
            if game.won { ConfettiView(start: game.wonAt).allowsHitTesting(false).ignoresSafeArea() }
        }
    }
}

struct SudokuBoardView: View {
    let game: SudokuGame

    var body: some View {
        GeometryReader { geo in
            let side = geo.size.width
            let cell = side / 9
            ZStack(alignment: .topLeading) {
                grid(cell: cell)
                lines(side: side, cell: cell)
                if game.pickerOpen, let s = game.selected {
                    NumberPicker(choices: game.choices, boardWidth: side, cell: cell, row: s.r, col: s.c,
                                 pick: { game.place($0) },
                                 close: { game.pickerOpen = false })
                }
            }
        }
        .aspectRatio(1, contentMode: .fit)
    }

    private func grid(cell: CGFloat) -> some View {
        VStack(spacing: 0) {
            ForEach(0..<9, id: \.self) { r in
                HStack(spacing: 0) {
                    ForEach(0..<9, id: \.self) { c in
                        cellView(r, c, size: cell)
                    }
                }
            }
        }
    }

    private func cellView(_ r: Int, _ c: Int, size: CGFloat) -> some View {
        let n = game.board[r][c]
        let sel = game.selected
        let isSel = sel.map { $0.r == r && $0.c == c } ?? false
        let related = sel.map { $0.r == r || $0.c == c || ($0.r / 3 == r / 3 && $0.c / 3 == c / 3) } ?? false
        let color: Color = Sudoku.clashes(game.board, r, c) ? SD.clash : (game.fixed[r][c] ? SD.given : SD.entered)
        return ZStack {
            Rectangle().fill(isSel ? SD.selected : (related ? SD.tint : SD.paper))
            if n != 0 {
                Text("\(n)")
                    .font(.system(size: size * 0.62, weight: game.fixed[r][c] ? .bold : .semibold, design: .rounded))
                    .foregroundStyle(color)
            }
        }
        .frame(width: size, height: size)
        .contentShape(Rectangle())
        .onTapGesture { game.tap(r, c) }
    }

    private func lines(side: CGFloat, cell: CGFloat) -> some View {
        Canvas { ctx, _ in
            for i in 0...9 {
                let p = CGFloat(i) * cell
                let w: CGFloat = i % 3 == 0 ? 3 : 0.8
                var path = Path()
                path.move(to: CGPoint(x: p, y: 0)); path.addLine(to: CGPoint(x: p, y: side))
                path.move(to: CGPoint(x: 0, y: p)); path.addLine(to: CGPoint(x: side, y: p))
                ctx.stroke(path, with: .color(SD.line), lineWidth: w)
            }
        }
        .allowsHitTesting(false)
        .frame(width: side, height: side)
    }
}

/// A strip of big buttons with only the numbers that fit, plus clear and close.
struct NumberPicker: View {
    let choices: [Int]          // 1...9, or 0 for "clear"
    let boardWidth: CGFloat
    let cell: CGFloat
    let row: Int
    let col: Int
    let pick: (Int) -> Void
    let close: () -> Void

    private let gap: CGFloat = 6
    private var count: Int { choices.count + 1 }   // + close button
    // Finger-sized buttons; shrink only when there are many choices
    private var size: CGFloat { min(56, (boardWidth - gap * CGFloat(count + 1)) / CGFloat(count)) }
    private var width: CGFloat { CGFloat(count) * (size + gap) + gap }
    private var height: CGFloat { size + gap * 2 }

    var body: some View {
        let centerX = (CGFloat(col) + 0.5) * cell
        let x = min(max(centerX - width / 2, 0), boardWidth - width)
        // Above the cell, or below it when the cell is near the top
        let y = row >= 2 ? CGFloat(row) * cell - height - 4 : CGFloat(row + 1) * cell + 4

        HStack(spacing: gap) {
            ForEach(choices, id: \.self) { n in
                Button { pick(n) } label: {
                    Group {
                        if n == 0 {
                            Image(systemName: "eraser.fill").font(.system(size: size * 0.42))
                        } else {
                            Text("\(n)").font(.system(size: size * 0.66, weight: .bold, design: .rounded))
                        }
                    }
                    .foregroundStyle(n == 0 ? SD.clash : SD.entered)
                    .frame(width: size, height: size)
                    .background(n == 0 ? rgb(255, 225, 225) : SD.pickerButton, in: RoundedRectangle(cornerRadius: 10))
                }
                .accessibilityLabel(n == 0 ? "Clear" : "\(n)")
            }
            Button(action: close) {
                Image(systemName: "xmark")
                    .font(.system(size: size * 0.4, weight: .bold))
                    .foregroundStyle(Color(white: 0.35))
                    .frame(width: size, height: size)
                    .background(Color(white: 0.88), in: RoundedRectangle(cornerRadius: 10))
            }
            .accessibilityLabel("Close")
        }
        .padding(gap)
        .background(SD.pickerBG, in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(SD.entered, lineWidth: 2))
        .shadow(color: .black.opacity(0.45), radius: 8, y: 4)
        .offset(x: x, y: y)
        .transition(.scale(scale: 0.8).combined(with: .opacity))
    }
}

/// Falling confetti, like the pygame version's win screen.
private struct ConfettiView: View {
    let start: Date
    @State private var pieces: [(x: Double, y: Double, vx: Double, vy: Double, w: Double, h: Double, phase: Double, color: Color)] =
        (0..<160).map { _ in
            (Double.random(in: 0...1), Double.random(in: -0.6...0), Double.random(in: -0.08...0.08),
             Double.random(in: 0.18...0.45), Double.random(in: 6...11), Double.random(in: 9...16),
             Double.random(in: 0...6.28), SD.confetti.randomElement()!)
        }

    var body: some View {
        TimelineView(.animation) { tl in
            let t = tl.date.timeIntervalSince(start)
            Canvas { ctx, size in
                for p in pieces {
                    let x = (p.x + p.vx * t) * size.width
                    let y = (p.y + p.vy * t) * size.height
                    guard y < size.height + 20 else { continue }
                    let h = max(2, p.h * abs(cos(t * 9 + p.phase)))
                    ctx.fill(Path(CGRect(x: x, y: y, width: p.w, height: h)), with: .color(p.color))
                }
            }
        }
    }
}

#Preview {
    NavigationStack { SudokuView() }
}
