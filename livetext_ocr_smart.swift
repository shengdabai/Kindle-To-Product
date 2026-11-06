#!/usr/bin/env swift

/**
 * Smart-layout Live Text OCR for Kindle book pages.
 * One Vision pass per page, then geometry-based layout detection:
 *   - Two-column page  -> emit left column (top→bottom) then right column.
 *   - Single-column / centered page -> emit all lines top→bottom.
 * Detection: count text lines that cross the center gutter (x 0.47–0.53).
 *   Many crossing lines  = centered single column (epigraph, copyright, refs).
 *   Few (UI banner only) = two-column body/TOC.
 *
 * Usage: swift livetext_ocr_smart.swift <image_path> [langs]
 */

import Vision
import Foundation
import AppKit

func recognize(_ imagePath: String, _ languages: [String]) throws -> [VNRecognizedTextObservation] {
    guard let image = NSImage(contentsOfFile: imagePath) else {
        throw NSError(domain: "OCR", code: 1, userInfo: [NSLocalizedDescriptionKey: "load fail: \(imagePath)"])
    }
    guard let cg = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        throw NSError(domain: "OCR", code: 2, userInfo: [NSLocalizedDescriptionKey: "cgImage fail"])
    }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = true
    if #available(macOS 13.0, *) { req.recognitionLanguages = languages }
    try VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    return req.results ?? []
}

// Join observations in reading order (top→bottom, tie-break left→right).
func ordered(_ obs: [VNRecognizedTextObservation]) -> String {
    let sorted = obs.sorted { a, b in
        let ay = a.boundingBox.midY, by = b.boundingBox.midY
        if abs(ay - by) > 0.008 { return ay > by }
        return a.boundingBox.midX < b.boundingBox.midX
    }
    return sorted.compactMap { $0.topCandidates(1).first?.string }.joined(separator: "\n")
}

func smartLayout(_ obs: [VNRecognizedTextObservation]) -> String {
    let total = obs.count
    if total < 6 { return ordered(obs) }                 // sparse page (cover, part/chapter title) → single column

    // lines that span across the center gutter
    let crossing = obs.filter { $0.boundingBox.minX < 0.47 && $0.boundingBox.maxX > 0.53 }
    if crossing.count >= 4 {                              // many full-width lines → centered single column
        return ordered(obs)
    }

    // two-column: split by horizontal midpoint, each column top→bottom
    let left  = obs.filter { $0.boundingBox.midX <  0.5 }
    let right = obs.filter { $0.boundingBox.midX >= 0.5 }
    if left.isEmpty || right.isEmpty { return ordered(obs) }
    return ordered(left) + "\n" + ordered(right)
}

let args = CommandLine.arguments
if args.count < 2 {
    fputs("Usage: \(args[0]) <image_path> [langs]\n", stderr)
    exit(1)
}
let imagePath = args[1]
let languages = args.count > 2 ? args[2].split(separator: ",").map(String.init) : ["en"]

do {
    let obs = try recognize(imagePath, languages)
    print(smartLayout(obs))
    exit(0)
} catch {
    fputs("Error: \(error.localizedDescription)\n", stderr)
    exit(1)
}
