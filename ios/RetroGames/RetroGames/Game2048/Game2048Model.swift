import Foundation
import Observation

enum Direction {
    case up, down, left, right
}

/// One numbered tile on the board. The id stays the same as the tile slides,
/// so SwiftUI can animate it from its old spot to its new one.
struct Tile: Identifiable, Equatable, Codable {
    var id = UUID()
    var value: Int
    var row: Int
    var col: Int
}

@Observable
final class Game2048Model {
    static let size = 4

    private(set) var tiles: [Tile] = []
    private(set) var score = 0
    private(set) var best = 0
    private(set) var isGameOver = false
    private(set) var hasWon = false        // reached 2048 at least once
    var showWinMessage = false

    private let saveKey = "game2048.state"
    private let bestKey = "game2048.best"

    init() {
        best = UserDefaults.standard.integer(forKey: bestKey)
        if !load() {
            newGame()
        }
    }

    func newGame() {
        tiles = []
        score = 0
        isGameOver = false
        hasWon = false
        showWinMessage = false
        addRandomTile()
        addRandomTile()
        save()
    }

    func move(_ direction: Direction) {
        guard !isGameOver, !showWinMessage else { return }

        var moved = false
        var newTiles: [Tile] = []

        for line in 0..<Self.size {
            // Board spots along this line, starting at the edge the tiles move toward.
            let spots: [(row: Int, col: Int)] = (0..<Self.size).map { i in
                switch direction {
                case .left:  return (line, i)
                case .right: return (line, Self.size - 1 - i)
                case .up:    return (i, line)
                case .down:  return (Self.size - 1 - i, line)
                }
            }
            let lineTiles = spots.compactMap { spot in
                tiles.first { $0.row == spot.row && $0.col == spot.col }
            }

            var i = 0
            var target = 0
            while i < lineTiles.count {
                var tile = lineTiles[i]
                if i + 1 < lineTiles.count, lineTiles[i + 1].value == tile.value {
                    // Two equal neighbours merge into one tile worth double.
                    tile.value *= 2
                    score += tile.value
                    moved = true
                    if tile.value == 2048 && !hasWon {
                        hasWon = true
                        showWinMessage = true
                    }
                    i += 2
                } else {
                    i += 1
                }
                let spot = spots[target]
                if tile.row != spot.row || tile.col != spot.col {
                    moved = true
                }
                tile.row = spot.row
                tile.col = spot.col
                newTiles.append(tile)
                target += 1
            }
        }

        guard moved else { return }
        tiles = newTiles
        addRandomTile()
        if score > best {
            best = score
            UserDefaults.standard.set(best, forKey: bestKey)
        }
        isGameOver = !canMove()
        save()
    }

    func keepPlaying() {
        showWinMessage = false
        save()
    }

    // MARK: - Helpers

    private func tile(atRow row: Int, col: Int) -> Tile? {
        tiles.first { $0.row == row && $0.col == col }
    }

    private func addRandomTile() {
        var empty: [(Int, Int)] = []
        for r in 0..<Self.size {
            for c in 0..<Self.size where tile(atRow: r, col: c) == nil {
                empty.append((r, c))
            }
        }
        guard let (r, c) = empty.randomElement() else { return }
        let value = Double.random(in: 0..<1) < 0.9 ? 2 : 4
        tiles.append(Tile(value: value, row: r, col: c))
    }

    private func canMove() -> Bool {
        if tiles.count < Self.size * Self.size { return true }
        for t in tiles {
            if let right = tile(atRow: t.row, col: t.col + 1), right.value == t.value { return true }
            if let below = tile(atRow: t.row + 1, col: t.col), below.value == t.value { return true }
        }
        return false
    }

    // MARK: - Saving, so a game survives closing the app

    private struct SavedState: Codable {
        var tiles: [Tile]
        var score: Int
        var hasWon: Bool
        var showWinMessage: Bool
    }

    private func save() {
        let state = SavedState(tiles: tiles, score: score, hasWon: hasWon, showWinMessage: showWinMessage)
        if let data = try? JSONEncoder().encode(state) {
            UserDefaults.standard.set(data, forKey: saveKey)
        }
    }

    private func load() -> Bool {
        guard let data = UserDefaults.standard.data(forKey: saveKey),
              let state = try? JSONDecoder().decode(SavedState.self, from: data),
              !state.tiles.isEmpty else { return false }
        tiles = state.tiles
        score = state.score
        hasWon = state.hasWon
        showWinMessage = state.showWinMessage
        isGameOver = !canMove()
        return true
    }
}
