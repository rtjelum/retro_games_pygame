import Foundation

/// Puzzle generation and rules, same approach as sudoku.py:
/// fill a full board with shuffled backtracking, then dig holes.
enum Sudoku {
    typealias Board = [[Int]]   // 9x9, 0 = empty

    static func isValid(_ b: Board, _ r: Int, _ c: Int, _ n: Int) -> Bool {
        for i in 0..<9 where b[r][i] == n || b[i][c] == n { return false }
        let br = 3 * (r / 3), bc = 3 * (c / 3)
        for i in 0..<3 { for j in 0..<3 where b[br + i][bc + j] == n { return false } }
        return true
    }

    private static func fill(_ b: inout Board) -> Bool {
        for r in 0..<9 {
            for c in 0..<9 where b[r][c] == 0 {
                for n in (1...9).shuffled() where isValid(b, r, c, n) {
                    b[r][c] = n
                    if fill(&b) { return true }
                    b[r][c] = 0
                }
                return false
            }
        }
        return true
    }

    static func generate(holes: Int = 40) -> Board {
        var b = Board(repeating: Array(repeating: 0, count: 9), count: 9)
        _ = fill(&b)
        for i in Array(0..<81).shuffled().prefix(holes) { b[i / 9][i % 9] = 0 }
        return b
    }

    /// Numbers that don't clash with the cell's row, column or box (ignoring the cell itself).
    static func candidates(_ b: Board, _ r: Int, _ c: Int) -> [Int] {
        var used = Set<Int>()
        let br = 3 * (r / 3), bc = 3 * (c / 3)
        for i in 0..<9 {
            if i != c { used.insert(b[r][i]) }
            if i != r { used.insert(b[i][c]) }
        }
        for i in 0..<3 { for j in 0..<3 where (br + i, bc + j) != (r, c) { used.insert(b[br + i][bc + j]) } }
        return (1...9).filter { !used.contains($0) }
    }

    /// True if the cell's number appears again in its row, column or box.
    static func clashes(_ b: Board, _ r: Int, _ c: Int) -> Bool {
        let n = b[r][c]
        return n != 0 && !candidates(b, r, c).contains(n)
    }

    static func isSolved(_ b: Board) -> Bool {
        for r in 0..<9 { for c in 0..<9 where b[r][c] == 0 || clashes(b, r, c) { return false } }
        return true
    }
}
