import UIKit

/// Every candy picture: plain, striped both ways, bomb, fish and the colour bomb.
/// The striped and bomb versions are drawn once at startup, like load_candies() in the Python game.
struct Sprites {
    let plain: [UIImage]
    let rowStriped: [UIImage]
    let colStriped: [UIImage]
    let bomb: [UIImage]
    let fish: [UIImage]
    let colorBomb: UIImage

    static let shared = Sprites()

    private init() {
        plain = (0..<KINDS).map { UIImage(named: "candy_\($0)")! }
        fish = (0..<KINDS).map { UIImage(named: "fish_\($0)")! }
        colorBomb = UIImage(named: "color_bomb")!
        rowStriped = plain.map { Sprites.striped($0, horizontal: true) }
        colStriped = plain.map { Sprites.striped($0, horizontal: false) }
        bomb = plain.enumerated().map { Sprites.wrapped($1, color: CANDY_COLORS[$0]) }
    }

    func image(kind: Int, power: Power?) -> UIImage {
        if kind == COLOR_BOMB { return colorBomb }
        switch power {
        case .row: return rowStriped[kind]
        case .col: return colStriped[kind]
        case .bomb: return bomb[kind]
        case .fish: return fish[kind]
        default: return plain[kind]
        }
    }

    private static func renderer(_ size: CGSize, scale: CGFloat) -> UIGraphicsImageRenderer {
        let format = UIGraphicsImageRendererFormat()
        format.scale = scale
        format.opaque = false
        return UIGraphicsImageRenderer(size: size, format: format)
    }

    /// A candy with white stripes across it, kept inside the candy's shape.
    private static func striped(_ picture: UIImage, horizontal: Bool) -> UIImage {
        let size = picture.size
        let (w, h) = (size.width, size.height)
        let r = renderer(size, scale: picture.scale)
        // Keep only the part over the candy, a little inside its edge.
        // The mask only touches pixels inside its own rect, so clip to that rect first,
        // otherwise the stripe ends poke out past the candy at the sides.
        let inset = max(2, w / 40)
        let maskRect = CGRect(origin: .zero, size: size).insetBy(dx: inset, dy: inset)
        let stripes = r.image { ctx in
            ctx.cgContext.clip(to: maskRect)
            UIColor(white: 1, alpha: 0.88).setFill()
            for offset in [-0.22, 0, 0.22] {
                let rect = horizontal
                    ? CGRect(x: 0, y: h * (0.5 + offset) - h * 0.04, width: w, height: h * 0.08)
                    : CGRect(x: w * (0.5 + offset) - w * 0.04, y: 0, width: w * 0.08, height: h)
                UIRectFill(rect)
            }
            picture.draw(in: maskRect, blendMode: .destinationIn, alpha: 1)
        }
        return r.image { _ in
            picture.draw(at: .zero)
            stripes.draw(at: .zero)
        }
    }

    /// A bomb: the candy, a little smaller, inside a bright ring with sparkles.
    private static func wrapped(_ picture: UIImage, color: RGB) -> UIImage {
        let size = picture.size
        let w = size.width
        let c = w / 2, r = w * 0.46
        let ui = { (rgb: RGB) in UIColor(red: rgb.r, green: rgb.g, blue: rgb.b, alpha: 1) }
        let circle = { (radius: CGFloat) in
            UIBezierPath(ovalIn: CGRect(x: c - radius, y: c - radius, width: radius * 2, height: radius * 2))
        }
        return renderer(size, scale: picture.scale).image { _ in
            UIColor(red: 12 / 255, green: 12 / 255, blue: 24 / 255, alpha: 1).setFill()
            circle(r + w * 0.02).fill()
            ui(color.mix(.white, 0.25)).setFill()
            circle(r).fill()
            ui(color.mix(RGB(0, 0, 0), 0.35)).setFill()
            circle(r * 0.86).fill()
            UIColor.white.setStroke()
            let ring = circle(r)
            ring.lineWidth = max(2, w * 0.025)
            ring.stroke()
            let inner = w * 0.78
            picture.draw(in: CGRect(x: c - inner / 2, y: c - inner / 2, width: inner, height: inner))
            UIColor.white.setFill()
            for a in [45.0, 135, 225, 315] {   // four little sparkles on the ring
                let x = c + cos(a * .pi / 180) * r, y = c + sin(a * .pi / 180) * r
                let s = w * 0.07
                for (dx, dy) in [(0.3, 1.0), (1.0, 0.3)] {
                    let p = UIBezierPath()
                    p.move(to: CGPoint(x: x, y: y - s * dy))
                    p.addLine(to: CGPoint(x: x + s * dx, y: y))
                    p.addLine(to: CGPoint(x: x, y: y + s * dy))
                    p.addLine(to: CGPoint(x: x - s * dx, y: y))
                    p.close()
                    p.fill()
                }
            }
        }
    }
}
