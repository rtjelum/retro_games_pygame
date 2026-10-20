import SwiftUI

// Same colors as 2048_game.py
extension Color {
    init(hex: UInt32) {
        self.init(red: Double((hex >> 16) & 0xff) / 255,
                  green: Double((hex >> 8) & 0xff) / 255,
                  blue: Double(hex & 0xff) / 255)
    }

    static let pageBackground = Color(hex: 0xfaf8ef)
    static let boardBackground = Color(hex: 0xbbada0)
    static let emptyTile = Color(hex: 0xcdc1b4)
    static let darkText = Color(hex: 0x776e65)

    static func tile(_ value: Int) -> Color {
        switch value {
        case 2:    return Color(hex: 0xeee4da)
        case 4:    return Color(hex: 0xede0c9)
        case 8:    return Color(hex: 0xf2b179)
        case 16:   return Color(hex: 0xf59563)
        case 32:   return Color(hex: 0xf67c5f)
        case 64:   return Color(hex: 0xf65e3b)
        case 128:  return Color(hex: 0xedcf72)
        case 256:  return Color(hex: 0xedc265)
        case 512:  return Color(hex: 0xedb54e)
        case 1024: return Color(hex: 0xeda53c)
        case 2048: return Color(hex: 0xed922e)
        default:   return Color(hex: 0x3c3a32)
        }
    }
}

struct Game2048View: View {
    @State private var game = Game2048Model()

    var body: some View {
        VStack(spacing: 20) {
            header
            Board2048View(game: game)
                .padding(.horizontal)
            Text("Swipe to slide the tiles. Join equal numbers to reach **2048**!")
                .font(.subheadline)
                .foregroundStyle(Color.darkText)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
            Spacer()
        }
        .padding(.top, 24)
        .frame(maxWidth: 500)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.pageBackground)
    }

    private var header: some View {
        HStack(alignment: .center) {
            Text("2048")
                .font(.system(size: 56, weight: .heavy, design: .rounded))
                .foregroundStyle(Color.darkText)
                .lineLimit(1)
                .minimumScaleFactor(0.5)
                .layoutPriority(1)
            Spacer(minLength: 8)
            VStack(alignment: .trailing, spacing: 8) {
                HStack(spacing: 8) {
                    ScoreBox(title: "SCORE", value: game.score)
                    ScoreBox(title: "BEST", value: game.best)
                }
                Button("New Game") {
                    withAnimation { game.newGame() }
                }
                .buttonStyle(GameButtonStyle())
            }
        }
        .padding(.horizontal)
    }
}

struct ScoreBox: View {
    let title: String
    let value: Int

    var body: some View {
        VStack(spacing: 2) {
            Text(title)
                .font(.caption.bold())
                .foregroundStyle(Color.emptyTile)
            Text("\(value)")
                .font(.system(.title3, design: .rounded).bold())
                .foregroundStyle(.white)
                .lineLimit(1)
                .minimumScaleFactor(0.6)
                .contentTransition(.numericText())
                .animation(.default, value: value)
        }
        .frame(minWidth: 64)
        .padding(.vertical, 6)
        .padding(.horizontal, 8)
        .background(Color.boardBackground, in: RoundedRectangle(cornerRadius: 6))
    }
}

struct GameButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundStyle(.white)
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
            .background(Color(hex: 0x8f7a66), in: RoundedRectangle(cornerRadius: 6))
            .opacity(configuration.isPressed ? 0.7 : 1)
    }
}

struct Board2048View: View {
    let game: Game2048Model
    private let spacing: CGFloat = 10

    var body: some View {
        GeometryReader { geo in
            let side = geo.size.width
            let cell = (side - spacing * CGFloat(Game2048Model.size + 1)) / CGFloat(Game2048Model.size)

            ZStack(alignment: .topLeading) {
                // Empty slots
                ForEach(0..<Game2048Model.size * Game2048Model.size, id: \.self) { i in
                    RoundedRectangle(cornerRadius: 6)
                        .fill(Color.emptyTile)
                        .frame(width: cell, height: cell)
                        .offset(offset(row: i / Game2048Model.size, col: i % Game2048Model.size, cell: cell))
                }

                // Numbered tiles
                ForEach(game.tiles) { tile in
                    TileView(value: tile.value, size: cell)
                        .offset(offset(row: tile.row, col: tile.col, cell: cell))
                        .transition(.scale(scale: 0.1).combined(with: .opacity))
                }

                if game.isGameOver {
                    overlay(title: "Game over!") {
                        Button("Try Again") { withAnimation { game.newGame() } }
                            .buttonStyle(GameButtonStyle())
                    }
                } else if game.showWinMessage {
                    overlay(title: "You win!") {
                        HStack {
                            Button("Keep Going") { game.keepPlaying() }
                                .buttonStyle(GameButtonStyle())
                            Button("New Game") { withAnimation { game.newGame() } }
                                .buttonStyle(GameButtonStyle())
                        }
                    }
                }
            }
            .frame(width: side, height: side, alignment: .topLeading)
            .background(Color.boardBackground, in: RoundedRectangle(cornerRadius: 10))
            .animation(.easeInOut(duration: 0.12), value: game.tiles)
            .contentShape(Rectangle())
            .gesture(swipe)
        }
        .aspectRatio(1, contentMode: .fit)
    }

    private func offset(row: Int, col: Int, cell: CGFloat) -> CGSize {
        CGSize(width: spacing + CGFloat(col) * (cell + spacing),
               height: spacing + CGFloat(row) * (cell + spacing))
    }

    private var swipe: some Gesture {
        DragGesture(minimumDistance: 20)
            .onEnded { drag in
                let dx = drag.translation.width
                let dy = drag.translation.height
                if abs(dx) > abs(dy) {
                    game.move(dx > 0 ? .right : .left)
                } else {
                    game.move(dy > 0 ? .down : .up)
                }
            }
    }

    private func overlay<Content: View>(title: String, @ViewBuilder buttons: () -> Content) -> some View {
        VStack(spacing: 20) {
            Text(title)
                .font(.system(size: 44, weight: .heavy, design: .rounded))
                .foregroundStyle(Color.darkText)
            buttons()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.pageBackground.opacity(0.75), in: RoundedRectangle(cornerRadius: 10))
        .transition(.opacity)
    }
}

struct TileView: View {
    let value: Int
    let size: CGFloat

    var body: some View {
        Text("\(value)")
            .font(.system(size: fontSize, weight: .bold, design: .rounded))
            .minimumScaleFactor(0.5)
            .lineLimit(1)
            .foregroundStyle(value <= 4 ? Color.darkText : .white)
            .frame(width: size, height: size)
            .background(Color.tile(value), in: RoundedRectangle(cornerRadius: 6))
    }

    private var fontSize: CGFloat {
        switch value {
        case ..<100:  return size * 0.5
        case ..<1000: return size * 0.42
        default:      return size * 0.32
        }
    }
}

#Preview {
    Game2048View()
}
