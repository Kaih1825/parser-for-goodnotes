import Foundation
import PDFKit
import AppKit

func renderPDFToPNG(pdfPath: String, pageIndex: Int, outputPath: String, dpi: CGFloat = 150.0) -> Bool {
    guard let pdfDoc = PDFDocument(url: URL(fileURLWithPath: pdfPath)) else { return false }
    let pageCount = pdfDoc.pageCount
    if pageCount == 0 { return false }
    
    let targetIndex = min(max(0, pageIndex), pageCount - 1)
    guard let page = pdfDoc.page(at: targetIndex) else { return false }
    
    let bounds = page.bounds(for: .mediaBox)
    let scale = dpi / 72.0
    let width = Int(bounds.width * scale)
    let height = Int(bounds.height * scale)
    
    guard let rep = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: width,
        pixelsHigh: height,
        bitsPerSample: 8,
        samplesPerPixel: 4,
        hasAlpha: true,
        isPlanar: false,
        colorSpaceName: .calibratedRGB,
        bytesPerRow: 0,
        bitsPerPixel: 0
    ) else { return false }
    
    rep.size = NSSize(width: bounds.width, height: bounds.height)
    
    NSGraphicsContext.saveGraphicsState()
    guard let context = NSGraphicsContext(bitmapImageRep: rep) else { return false }
    NSGraphicsContext.current = context
    
    // Fill white background first
    NSColor.white.set()
    NSRect(x: 0, y: 0, width: bounds.width, height: bounds.height).fill()
    
    page.draw(with: .mediaBox, to: context.cgContext)
    NSGraphicsContext.restoreGraphicsState()
    
    guard let pngData = rep.representation(using: .png, properties: [:]) else { return false }
    do {
        try pngData.write(to: URL(fileURLWithPath: outputPath))
        return true
    } catch {
        return false
    }
}

let args = CommandLine.arguments
if args.count < 4 {
    print("Usage: render_pdf <pdfPath> <pageIndex> <outputPath> [dpi]")
    exit(1)
}

let pdfPath = args[1]
let pageIndex = Int(args[2]) ?? 0
let outputPath = args[3]
let dpi = args.count > 4 ? (CGFloat(Double(args[4]) ?? 150.0)) : 150.0

if renderPDFToPNG(pdfPath: pdfPath, pageIndex: pageIndex, outputPath: outputPath, dpi: dpi) {
    print("SUCCESS")
} else {
    print("FAILED")
    exit(1)
}
