import Foundation

// A port of the puzzle in snake_escape.py.
//
// The snakes lie on the surface of a box, their bodies bending round its edges
// from one face to the next. A snake leaves by slithering straight ahead across
// the face its head is on and off the edge, if nothing is in the way.
//
// A cell is the 3D point at its centre, counted in half cells from the box's
// corner: along the axis its face looks down it is 0 or twice the box's size
// there, along the other two it is odd. Directions are unit steps along an axis.

enum SnakeEscape {
    static let box = Vec(12, 12, 12)   // cells along x, y (up) and z
    static let lives = 3
    static let straightChance = 0.35   // how often a snake's body carries straight on
    static let tries = 60              // random attempts at fitting in one more snake
    static let chains = 10             // chains of snakes per box: each one is a snake free to go
    static let attempts = 40           // boxes built per puzzle; the one with most snakes is kept
    static let arm = 2                 // how far a new snake first reaches each way
    static let colors: [[Double]] = [[239, 83, 80], [255, 167, 38], [255, 213, 79], [102, 187, 106],
                                     [38, 198, 218], [66, 133, 244], [171, 120, 235], [236, 112, 160],
                                     [156, 204, 101], [255, 138, 101]]

    struct Vec: Hashable {
        var x, y, z: Int

        init(_ x: Int, _ y: Int, _ z: Int) {
            (self.x, self.y, self.z) = (x, y, z)
        }

        subscript(axis: Int) -> Int {
            get { axis == 0 ? x : axis == 1 ? y : z }
            set {
                switch axis {
                case 0: x = newValue
                case 1: y = newValue
                default: z = newValue
                }
            }
        }

        /// The axis a direction points along.
        var axis: Int { x != 0 ? 0 : y != 0 ? 1 : 2 }
        var double: SIMD3<Double> { SIMD3(Double(x), Double(y), Double(z)) }

        static func + (a: Vec, b: Vec) -> Vec { Vec(a.x + b.x, a.y + b.y, a.z + b.z) }
        static func - (a: Vec, b: Vec) -> Vec { Vec(a.x - b.x, a.y - b.y, a.z - b.z) }
        static func * (a: Vec, k: Int) -> Vec { Vec(a.x * k, a.y * k, a.z * k) }
        static prefix func - (a: Vec) -> Vec { Vec(-a.x, -a.y, -a.z) }

        static func unit(_ axis: Int, _ sign: Int) -> Vec {
            var v = Vec(0, 0, 0)
            v[axis] = sign
            return v
        }
    }

    // MARK: - Box surface

    /// The outward direction of the face a cell is on (also for points off the
    /// box in a face's plane, which keep that face's coordinate).
    static func normal(_ cell: Vec) -> Vec? {
        for i in 0..<3 {
            if cell[i] == 0 { return .unit(i, -1) }
            if cell[i] == 2 * box[i] { return .unit(i, 1) }
        }
        return nil
    }

    /// The next cell going `direction`, and the way on from there. Over the
    /// edge of a face the way on turns down the next face.
    static func step(_ cell: Vec, _ direction: Vec) -> (cell: Vec, direction: Vec) {
        let ahead = cell + direction * 2
        let i = direction.axis
        if ahead[i] > 0 && ahead[i] < 2 * box[i] { return (ahead, direction) }
        let out = normal(cell)!
        return (cell + direction - out, -out)
    }

    static func neighbours(_ cell: Vec) -> [Vec] {
        let out = normal(cell)!
        var cells: [Vec] = []
        for i in 0..<3 where out[i] == 0 {
            for sign in [1, -1] { cells.append(step(cell, .unit(i, sign)).cell) }
        }
        return cells
    }

    /// The way a snake goes on from b, having just come from a.
    static func heading(_ a: Vec, _ b: Vec) -> Vec {
        let out = normal(a)!
        if out == normal(b) {
            let d = b - a
            return Vec(d.x / 2, d.y / 2, d.z / 2)
        }
        return -out
    }

    /// Every cell of the box, face by face.
    static func surface() -> [Vec] {
        faces.flatMap { $0.cells }
    }

    struct Face {
        let out: Vec
        let corners: [Vec]
        let cells: [Vec]
    }

    static let faces: [Face] = {
        var faces: [Face] = []
        for i in 0..<3 {
            let a = (i + 1) % 3, b = (i + 2) % 3
            for side in [0, 2 * box[i]] {
                var corners: [Vec] = []
                for (u, v) in [(0, 0), (1, 0), (1, 1), (0, 1)] {
                    var corner = Vec(0, 0, 0)
                    corner[i] = side
                    corner[a] = 2 * box[a] * u
                    corner[b] = 2 * box[b] * v
                    corners.append(corner)
                }
                var cells: [Vec] = []
                for u in stride(from: 1, to: 2 * box[a], by: 2) {
                    for v in stride(from: 1, to: 2 * box[b], by: 2) {
                        var cell = Vec(0, 0, 0)
                        cell[i] = side
                        cell[a] = u
                        cell[b] = v
                        cells.append(cell)
                    }
                }
                faces.append(Face(out: .unit(i, side == 0 ? -1 : 1), corners: corners, cells: cells))
            }
        }
        return faces
    }()

    struct Snake {
        var cells: [Vec]   // tail first, head last
        var color = 0      // index into `colors`

        var direction: Vec { heading(cells[cells.count - 2], cells[cells.count - 1]) }

        /// The cells straight ahead of the head, out to the edge of its face.
        func ray() -> [Vec] {
            let direction = self.direction
            let i = direction.axis
            var ahead: [Vec] = []
            var cell = cells[cells.count - 1] + direction * 2
            while cell[i] > 0 && cell[i] < 2 * box[i] {
                ahead.append(cell)
                cell = cell + direction * 2
            }
            return ahead
        }

        /// Cells a snake on its way out slithers before it is well clear of the screen.
        var exitLength: Int { cells.count + ray().count + 2 * max(box.x, box.y, box.z) + 2 }
    }

    // MARK: - Puzzle generator

    /// Extends a path from its last cell, wandering through free cells.
    private static func grow(_ walk: inout [Vec], _ steps: Int, _ free: Set<Vec>) {
        for _ in 0..<steps {
            let last = walk[walk.count - 1]
            let options = neighbours(last).filter { free.contains($0) && !walk.contains($0) }
            guard var cell = options.randomElement() else { break }
            if walk.count > 1 && Double.random(in: 0..<1) < straightChance {
                let straight = step(last, heading(walk[walk.count - 2], last)).cell
                if options.contains(straight) { cell = straight }
            }
            walk.append(cell)
        }
    }

    /// A snake lying across one of the `crossing` cells, with a clear way out,
    /// or nil if a few random tries don't turn one up.
    private static func newSnake(_ free: Set<Vec>, _ crossing: [Vec]) -> Snake? {
        for _ in 0..<tries {
            var walk = [crossing.randomElement()!]
            grow(&walk, Int.random(in: 1...arm), free)
            walk.reverse()
            grow(&walk, Int.random(in: 0...arm), free)
            if walk.count < 2 { continue }
            for cells in [walk, walk.reversed()] {
                let snake = Snake(cells: cells)
                let ray = snake.ray()
                if !ray.isEmpty && ray.allSatisfy(free.contains) && Set(ray).isDisjoint(with: cells) {
                    return snake
                }
            }
        }
        return nil
    }

    /// Snakes that can all leave, listed in an order they can leave in.
    ///
    /// Built backwards from the last one out, in chains: each new snake is laid
    /// across the way out of the one before, so that one is stuck until the new
    /// one has gone, and its own way out is kept clear of everything already
    /// there. When a chain runs out of room a fresh one starts anywhere; the
    /// last snake of each chain is free to go.
    static func build() -> [Snake] {
        var free = Set(surface())
        var snakes: [Snake] = []
        var crossing = Array(free)
        var started = 1
        while true {
            guard let snake = newSnake(free, crossing) else {
                if started == chains { break }
                crossing = Array(free)
                started += 1
                continue
            }
            free.subtract(snake.cells)
            snakes.append(snake)
            crossing = snake.ray()
        }
        snakes.reverse()

        // Lengthen the tails into the gaps. A tail must stay out of its own way
        // and out of the way of every snake that leaves earlier.
        var waysOut = Set<Vec>()
        for i in snakes.indices {
            waysOut.formUnion(snakes[i].ray())
            while let cell = neighbours(snakes[i].cells[0])
                .filter({ free.contains($0) && !waysOut.contains($0) }).randomElement() {
                free.remove(cell)
                snakes[i].cells.insert(cell, at: 0)
            }
        }
        return snakes
    }

    /// Gives each snake a colour that none of the snakes touching it has.
    private static func paint(_ snakes: inout [Snake]) {
        var owner: [Vec: Int] = [:]
        for (i, snake) in snakes.enumerated() {
            for cell in snake.cells { owner[cell] = i }
        }
        for i in snakes.indices {
            var used = Set<Int>()
            for cell in snakes[i].cells {
                for near in neighbours(cell) {
                    if let other = owner[near], other != i { used.insert(snakes[other].color) }
                }
            }
            let options = colors.indices.filter { !used.contains($0) }
            snakes[i].color = options.randomElement() ?? Int.random(in: colors.indices)
        }
    }

    /// A puzzle that can always be cleared: the busiest of many random boxes.
    static func generate() -> [Snake] {
        var snakes = (0..<attempts).map { _ in build() }.max { $0.count < $1.count }!
        paint(&snakes)
        snakes.shuffle()   // so no order can be read off the list
        return snakes
    }

    // MARK: - Drawing helpers

    /// The way a snake goes, from its tail all the way out: points half a cell
    /// apart, and the face each half-cell stretch between them lies on.
    ///
    /// The points are each cell, then the point between it and the next, which
    /// over an edge is on the edge. After its way out across its face the snake
    /// flies on off the edge, in that face's plane, and keeps that face's normal.
    struct Track {
        let points: [SIMD3<Double>]
        let outs: [Vec]
    }

    static func track(_ snake: Snake) -> Track {
        let direction = snake.direction
        var path = snake.cells + snake.ray()
        let end = path[path.count - 1]
        path += (1...(snake.exitLength + 2)).map { end + direction * (2 * $0) }
        var points = [path[0].double]
        var outs: [Vec] = []
        for (a, b) in zip(path, path.dropFirst()) {
            let outA = normal(a)!, outB = normal(b)!
            points.append(outA == outB ? (a.double + b.double) / 2 : (b + outA).double)
            points.append(b.double)
            outs += [outA, outB]
        }
        return Track(points: points, outs: outs)
    }
}
