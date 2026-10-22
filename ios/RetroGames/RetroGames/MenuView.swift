import SwiftUI

enum GameChoice: String, CaseIterable, Identifiable {
    case game2048, candySwap, carPark, snakeEscape
    var id: String { rawValue }

    var title: String {
        switch self {
        case .game2048: return "2048"
        case .candySwap: return "Candy Swap"
        case .carPark: return "Car Park"
        case .snakeEscape: return "Snake Escape"
        }
    }

    var subtitle: String {
        switch self {
        case .game2048: return "Slide and merge the tiles to reach 2048"
        case .candySwap: return "Swap candies to line up three or more"
        case .carPark: return "Clear the way for the red car"
        case .snakeEscape: return "Turn the cube and send every snake off it"
        }
    }

    var thumbnail: String {
        switch self {
        case .game2048: return "thumb_2048"
        case .candySwap: return "thumb_candy"
        case .carPark: return "thumb_carpark"
        case .snakeEscape: return "thumb_snake"
        }
    }
}

// Same colours as menu.py
private let menuGold = Color(red: 255 / 255, green: 215 / 255, blue: 120 / 255)
private let menuCard = Color(red: 28 / 255, green: 30 / 255, blue: 52 / 255)
private let menuThumbBG = Color(red: 16 / 255, green: 17 / 255, blue: 30 / 255)

struct MenuView: View {
    @State private var path: [GameChoice] = []

    var body: some View {
        NavigationStack(path: $path) {
            ScrollView {
                VStack(spacing: 18) {
                    Text("Retro Games")
                        .font(.custom("Georgia-Bold", size: 42))
                        .foregroundStyle(menuGold)
                        .padding(.top, 24)
                        .padding(.bottom, 8)
                    ForEach(GameChoice.allCases) { game in
                        NavigationLink(value: game) {
                            GameCard(game: game)
                        }
                        .buttonStyle(CardButtonStyle())
                    }
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 24)
                .frame(maxWidth: 560)
                .frame(maxWidth: .infinity)
            }
            .background(LinearGradient(colors: [Color(red: 40 / 255, green: 44 / 255, blue: 78 / 255),
                                                Color(red: 10 / 255, green: 10 / 255, blue: 20 / 255)],
                                       startPoint: .top, endPoint: .bottom).ignoresSafeArea())
            .navigationTitle("Games")
            .toolbar(.hidden, for: .navigationBar)
            .navigationDestination(for: GameChoice.self) { game in
                Group {
                    switch game {
                    case .game2048:
                        Game2048View()
                            .tint(Color.darkText)
                            .toolbarBackground(Color.pageBackground, for: .navigationBar)
                            .toolbarBackground(.visible, for: .navigationBar)
                    case .candySwap:
                        CandySwapView()
                            .toolbarBackground(.hidden, for: .navigationBar)
                    case .carPark:
                        CarParkView()
                            .toolbarBackground(.hidden, for: .navigationBar)
                    case .snakeEscape:
                        SnakeEscapeView()
                            .toolbarBackground(.hidden, for: .navigationBar)
                    }
                }
                // Our own back arrow instead of the system one. Hiding the system back button
                // also turns off the swipe-from-the-edge gesture, so a swipe in a game
                // never drops you back to the menu by accident.
                .navigationBarBackButtonHidden(true)
                .toolbar {
                    ToolbarItem(placement: .topBarLeading) {
                        Button {
                            path.removeAll()
                        } label: {
                            Image(systemName: "chevron.left")
                                .font(.system(size: 17, weight: .semibold))
                        }
                        .tint(game == .game2048 ? Color.darkText : menuGold)
                        .accessibilityLabel("Back to menu")
                    }
                }
            }
        }
        .tint(menuGold)
        // 2048 has a light page, so it needs dark status bar text; the rest are dark
        .preferredColorScheme(path.last == .game2048 ? .light : .dark)
        .onAppear {
            #if DEBUG
            // Launch with -open candySwap (or game2048 / carPark / snakeEscape) to jump straight into a game
            let args = ProcessInfo.processInfo.arguments
            if let i = args.firstIndex(of: "-open"), i + 1 < args.count, let game = GameChoice(rawValue: args[i + 1]) {
                path = [game]
                if args.contains("-thenBack") {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 3) { path = [] }
                }
            }
            #endif
        }
    }
}

struct GameCard: View {
    let game: GameChoice

    var body: some View {
        HStack(spacing: 16) {
            Image(game.thumbnail)
                .resizable()
                .aspectRatio(contentMode: .fit)
                .frame(width: 96, height: 110)
                .padding(8)
                .background(menuThumbBG, in: RoundedRectangle(cornerRadius: 8))
            VStack(alignment: .leading, spacing: 6) {
                Text(game.title)
                    .font(.system(size: 24, weight: .bold, design: .rounded))
                    .foregroundStyle(.white)
                Text(game.subtitle)
                    .font(.system(size: 14, weight: .medium, design: .rounded))
                    .foregroundStyle(Color(white: 0.65))
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 0)
            Image(systemName: "chevron.right")
                .font(.headline)
                .foregroundStyle(menuGold)
        }
        .padding(12)
        .background(menuCard, in: RoundedRectangle(cornerRadius: 12))
    }
}

struct CardButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .overlay(RoundedRectangle(cornerRadius: 12)
                .strokeBorder(menuGold, lineWidth: configuration.isPressed ? 3 : 0))
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
    }
}

#Preview {
    MenuView()
}
