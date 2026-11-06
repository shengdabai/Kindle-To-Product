#!/usr/bin/env swift

/**
 * Live Text OCR with Region-Of-Interest (for two-column book pages)
 * Usage: swift livetext_ocr_roi.swift <image_path> <langs> [x y w h]
 *   x y w h = normalized ROI (origin bottom-left). Omit for full page.
 * Example (left column):  swift livetext_ocr_roi.swift page.png en 0 0 0.5 1
 * Example (right column): swift livetext_ocr_roi.swift page.png en 0.5 0 0.5 1
 */

import Vision
import Foundation
import AppKit

func performOCR(imagePath: String, languages: [String], roi: CGRect?) throws -> String {
    guard let image = NSImage(contentsOfFile: imagePath) else {
        throw NSError(domain: "OCRError", code: 1,
                     userInfo: [NSLocalizedDescriptionKey: "Failed to load image: \(imagePath)"])
    }
    guard let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        throw NSError(domain: "OCRError", code: 2,
                     userInfo: [NSLocalizedDescriptionKey: "Failed to convert image to CGImage"])
    }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    if #available(macOS 13.0, *) {
        request.recognitionLanguages = languages
    }
    if let roi = roi {
        request.regionOfInterest = roi
    }

    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    try handler.perform([request])

    guard let observations = request.results else { return "" }

    // Sort strictly top-to-bottom (Vision origin = bottom-left, so higher midY = higher on page),
    // tie-break left-to-right. Keeps single-column reading order within the ROI.
    let sorted = observations.sorted { a, b in
        let ay = a.boundingBox.midY, by = b.boundingBox.midY
        if abs(ay - by) > 0.008 { return ay > by }
        return a.boundingBox.midX < b.boundingBox.midX
    }

    return sorted.compactMap { $0.topCandidates(1).first?.string }.joined(separator: "\n")
}

let args = CommandLine.arguments
if args.count < 2 {
    fputs("Usage: \(args[0]) <image_path> <langs> [x y w h]\n", stderr)
    exit(1)
}
let imagePath = args[1]
let languages = args.count > 2 ? args[2].split(separator: ",").map(String.init) : ["en"]
var roi: CGRect? = nil
if args.count >= 7, let x = Double(args[3]), let y = Double(args[4]), let w = Double(args[5]), let h = Double(args[6]) {
    roi = CGRect(x: x, y: y, width: w, height: h)
}

do {
    let text = try performOCR(imagePath: imagePath, languages: languages, roi: roi)
    print(text)
    exit(0)
} catch {
    fputs("Error: \(error.localizedDescription)\n", stderr)
    exit(1)
}
