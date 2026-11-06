#!/usr/bin/env swift

/**
 * Live Text OCR Script
 * Uses Apple Vision framework for native OCR on macOS
 *
 * Usage: swift livetext_ocr.swift <image_path> [language_codes]
 * Example: swift livetext_ocr.swift page.png en,es
 */

import Vision
import Foundation
import AppKit

func performOCR(imagePath: String, languages: [String] = ["en"]) throws -> String {
    // Load image
    guard let image = NSImage(contentsOfFile: imagePath) else {
        throw NSError(domain: "OCRError", code: 1,
                     userInfo: [NSLocalizedDescriptionKey: "Failed to load image: \(imagePath)"])
    }

    guard let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        throw NSError(domain: "OCRError", code: 2,
                     userInfo: [NSLocalizedDescriptionKey: "Failed to convert image to CGImage"])
    }

    // Create OCR request
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true

    // Set recognition languages if supported (macOS 13+)
    if #available(macOS 13.0, *) {
        request.recognitionLanguages = languages
    }

    // Perform request
    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    try handler.perform([request])

    // Extract text from observations
    guard let observations = request.results else {
        return ""
    }

    let recognizedText = observations
        .compactMap { $0.topCandidates(1).first?.string }
        .joined(separator: "\n")

    return recognizedText
}

// Main execution
let arguments = CommandLine.arguments

if arguments.count < 2 {
    fputs("Usage: \(arguments[0]) <image_path> [language_codes]\n", stderr)
    fputs("Example: \(arguments[0]) page.png en,es\n", stderr)
    exit(1)
}

let imagePath = arguments[1]
let languages = arguments.count > 2 ? arguments[2].split(separator: ",").map(String.init) : ["en"]

do {
    let text = try performOCR(imagePath: imagePath, languages: languages)
    print(text)
    exit(0)
} catch {
    fputs("Error: \(error.localizedDescription)\n", stderr)
    exit(1)
}
