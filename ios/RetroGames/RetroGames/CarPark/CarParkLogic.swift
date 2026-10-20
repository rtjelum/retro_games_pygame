import Foundation

// A port of the puzzle logic in car_park.py.
//
// A vehicle slides along its row (horizontal) or column; `line` is which one.
// A board position holds each vehicle's distance along its line. Positions are
// packed into one UInt64 (3 bits per vehicle) so the search can store
// thousands of them cheaply.

enum CarPark {
    static let size = 6            // the car park is size x size cells
    static let exitRow = 2

    struct Difficulty {
        let name: String
        let moves: ClosedRange<Int>      // fewest moves needed to solve
        let vehicles: ClosedRange<Int>   // vehicles besides the red car
    }

    static let difficulties = [
        Difficulty(name: "Easy", moves: 5...9, vehicles: 7...10),
        Difficulty(name: "Medium", moves: 10...14, vehicles: 9...12),
        Difficulty(name: "Hard", moves: 15...99, vehicles: 11...13),
    ]
    static let minMovable = 3      // vehicles that must be free to slide at the start
    static let truckChance = 0.3
    static let maxStates = 6000    // jams with more reachable positions than this are skipped

    struct Vehicle: Equatable {
        let horizontal: Bool
        let line: Int
        let length: Int

        func cells(at pos: Int) -> [(x: Int, y: Int)] {
            (0..<length).map { horizontal ? (pos + $0, line) : (line, pos + $0) }
        }
    }

    struct State: Hashable {
        var bits: UInt64
        let count: Int

        init(_ positions: [Int]) {
            bits = 0
            count = positions.count
            for (i, p) in positions.enumerated() { bits |= UInt64(p) << (3 * i) }
        }

        subscript(i: Int) -> Int {
            get { Int((bits >> (3 * i)) & 7) }
            set { bits = (bits & ~(7 << (3 * UInt64(i)))) | (UInt64(newValue) << (3 * i)) }
        }

        func with(_ i: Int, at pos: Int) -> State {
            var s = self
            s[i] = pos
            return s
        }

        var isSolved: Bool { self[0] == CarPark.size - 2 }   // the red car is always vehicle 0
    }

    struct Puzzle {
        let vehicles: [Vehicle]
        let start: State
        let best: Int     // fewest moves to solve
    }

    /// For each vehicle, the cells it covers at each position, as a bitmask.
    static func masks(_ vehicles: [Vehicle]) -> [[UInt64]] {
        vehicles.map { v in
            (0...(size - v.length)).map { pos in
                v.cells(at: pos).reduce(UInt64(0)) { $0 | (1 << UInt64($1.x + $1.y * size)) }
            }
        }
    }

    /// Every (vehicle index, new position) reachable in one slide.
    static func moves(_ masks: [[UInt64]], _ state: State) -> [(index: Int, pos: Int)] {
        var taken: UInt64 = 0
        for i in masks.indices { taken |= masks[i][state[i]] }
        var result: [(Int, Int)] = []
        for (i, mask) in masks.enumerated() {
            let others = taken ^ mask[state[i]]
            for step in [-1, 1] {
                var pos = state[i] + step
                while pos >= 0 && pos < mask.count && mask[pos] & others == 0 {
                    result.append((i, pos))
                    pos += step
                }
            }
        }
        return result
    }

    /// The lowest and highest positions vehicle `index` can slide to.
    static func slideRange(_ masks: [[UInt64]], _ state: State, _ index: Int) -> ClosedRange<Int> {
        let reach = moves(masks, state).filter { $0.index == index }.map { $0.pos } + [state[index]]
        return reach.min()!...reach.max()!
    }

    static func movable(_ masks: [[UInt64]], _ state: State) -> Int {
        Set(moves(masks, state).map { $0.index }).count
    }

    /// The red car plus up to `count` vehicles dropped in at random.
    static func randomJam(_ count: Int) -> ([Vehicle], State) {
        var vehicles = [Vehicle(horizontal: true, line: exitRow, length: 2)]
        var positions = [Int.random(in: 0...(size - 3))]
        var taken = Set(vehicles[0].cells(at: positions[0]).map { $0.y * size + $0.x })
        for _ in 0..<(count * 20) {
            if vehicles.count > count { break }
            let length = Double.random(in: 0..<1) < truckChance ? 3 : 2
            let v = Vehicle(horizontal: Bool.random(), line: Int.random(in: 0..<size), length: length)
            if v.horizontal && v.line == exitRow { continue }   // it could never get out of the red car's way
            let pos = Int.random(in: 0...(size - length))
            let spot = Set(v.cells(at: pos).map { $0.y * size + $0.x })
            if taken.isDisjoint(with: spot) {
                taken.formUnion(spot)
                vehicles.append(v)
                positions.append(pos)
            }
        }
        return (vehicles, State(positions))
    }

    /// Fewest moves to solve, for every position reachable from `start`.
    /// Returns nil if there are too many positions to search quickly.
    static func distances(_ masks: [[UInt64]], from start: State) -> [State: Int]? {
        var links: [State: [State]] = [:]
        var queue = [start]
        var head = 0
        while head < queue.count {
            let state = queue[head]
            head += 1
            if links[state] != nil { continue }
            if links.count >= maxStates { return nil }
            let next = moves(masks, state).map { state.with($0.index, at: $0.pos) }
            links[state] = next
            queue += next
        }
        // Slides can be undone, so searching outwards from the solved positions
        // gives the distance back to them.
        var dist: [State: Int] = [:]
        var frontier = links.keys.filter { $0.isSolved }
        for s in frontier { dist[s] = 0 }
        head = 0
        while head < frontier.count {
            let state = frontier[head]
            head += 1
            for other in links[state]! where dist[other] == nil {
                dist[other] = dist[state]! + 1
                frontier.append(other)
            }
        }
        return dist
    }

    /// A fresh puzzle for the given difficulty.
    static func generate(_ difficulty: Difficulty) -> Puzzle {
        while true {
            let (vehicles, state) = randomJam(Int.random(in: difficulty.vehicles))
            let m = masks(vehicles)
            guard let dist = distances(m, from: state), !dist.isEmpty else { continue }
            let fits = dist.filter { difficulty.moves.contains($0.value) }.map { $0.key }.shuffled()
            for start in fits.prefix(50) where movable(m, start) >= minMovable {
                return Puzzle(vehicles: vehicles, start: start, best: dist[start]!)
            }
        }
    }

    /// The first move of a shortest solution, as (vehicle index, position).
    static func nextMove(_ masks: [[UInt64]], from start: State) -> (index: Int, pos: Int)? {
        var seen: Set<State> = [start]
        var queue = moves(masks, start).map { (state: start.with($0.index, at: $0.pos), first: $0) }
        var head = 0
        while head < queue.count {
            let (state, first) = queue[head]
            head += 1
            if state.isSolved { return first }
            if seen.contains(state) { continue }
            seen.insert(state)
            for m in moves(masks, state) {
                queue.append((state.with(m.index, at: m.pos), first))
            }
        }
        return nil
    }
}
