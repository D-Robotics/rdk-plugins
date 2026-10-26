// Optional macOS-only, read-only OCR of hash-bound archived RGB PNG crops.
// Compile with xcrun swiftc; no camera, network, tuning or quality admission.
import Foundation
import Vision
import ImageIO
import CryptoKit

enum InputFailure: Error { case invalid(String) }
func fail(_ message: String) throws -> Never { throw InputFailure.invalid(message) }
func boundedData(_ url: URL, _ limit: Int) throws -> Data {
    let handle = try FileHandle(forReadingFrom: url)
    defer { try? handle.close() }
    let data = try handle.read(upToCount: limit + 1) ?? Data()
    guard data.count <= limit else { try fail("file_too_large") }
    return data
}
func run() throws {
    let args = CommandLine.arguments
    guard args.count == 6, args[2] == "--root", args[4] == "--output" else {
        try fail("usage: text-ocr manifest.json --root archive --output result.json")
    }
    let root = URL(fileURLWithPath: args[3], isDirectory: true).standardizedFileURL.resolvingSymlinksInPath()
    func contained(_ url: URL) -> Bool { url.path.hasPrefix(root.path + "/") }
    let manifest = URL(fileURLWithPath: args[1]).standardizedFileURL.resolvingSymlinksInPath()
    let output = URL(fileURLWithPath: args[5]).standardizedFileURL.resolvingSymlinksInPath()
    guard contained(manifest), contained(output), !FileManager.default.fileExists(atPath: output.path) else {
        try fail("contained_new_output_and_manifest_required")
    }
    let payload = try JSONSerialization.jsonObject(with: boundedData(manifest, 256 * 1024))
    guard let object = payload as? [String: Any], object["schema"] as? String == "camera-text-ocr-observation-v1",
          let frames = object["frames"] as? [[String: String]], (1...64).contains(frames.count) else {
        try fail("bounded_manifest_required")
    }
    var seen = Set<String>()
    // Validate all paths before invoking Vision. Metadata is not SDK authentication.
    for frame in frames {
        guard Set(frame.keys) == Set(["file", "sha256"]), let file = frame["file"], let digest = frame["sha256"],
              !file.hasPrefix("/"), digest.range(of: "^[a-f0-9]{64}$", options: .regularExpression) != nil,
              seen.insert(root.appendingPathComponent(file).standardizedFileURL.resolvingSymlinksInPath().path).inserted,
              contained(root.appendingPathComponent(file).standardizedFileURL.resolvingSymlinksInPath()) else {
            try fail("unique_contained_relative_image_and_sha256_required")
        }
    }
    var results: [[String: Any]] = []
    for frame in frames {
        let file = frame["file"]!
        let imageURL = root.appendingPathComponent(file).standardizedFileURL.resolvingSymlinksInPath()
        let data = try boundedData(imageURL, 32 * 1024 * 1024)
        let digest = SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
        guard digest == frame["sha256"], data.count >= 29,
              Array(data.prefix(8)) == [137, 80, 78, 71, 13, 10, 26, 10],
              Array(data[12..<16]) == [73, 72, 68, 82], data[24] == 8, data[25] == 2 else {
            try fail("bounded_hash_bound_RGB_PNG_required")
        }
        let width = data[16..<20].reduce(0) { $0 * 256 + Int($1) }
        let height = data[20..<24].reduce(0) { $0 * 256 + Int($1) }
        guard width > 0, height > 0, width <= 16_000_000 / height,
              let source = CGImageSourceCreateWithData(data as CFData, nil),
              let image = CGImageSourceCreateImageAtIndex(source, 0, nil), image.width == width, image.height == height else {
            try fail("bounded_hash_bound_RGB_PNG_required")
        }
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.recognitionLanguages = ["zh-Hans", "en-US"]
        request.usesLanguageCorrection = false
        request.customWords = []
        request.minimumTextHeight = 0
        var result: [String: Any] = ["file": file, "sha256": digest, "width": image.width, "height": image.height,
                                     "requestRevision": request.revision]
        do {
            try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
            let observations = (request.results ?? []).sorted { a, b in
                if abs(a.boundingBox.midY - b.boundingBox.midY) > 0.05 { return a.boundingBox.midY > b.boundingBox.midY }
                return a.boundingBox.minX < b.boundingBox.minX
            }
            result["status"] = "observed"
            result["lines"] = observations.map { observation -> [String: Any] in
                let candidate = observation.topCandidates(1).first
                let box = observation.boundingBox
                return ["text": candidate?.string ?? "", "confidence": candidate?.confidence ?? 0,
                        "box": [box.origin.x, box.origin.y, box.size.width, box.size.height]]
            }
        } catch { result["status"] = "failed"; result["error"] = String(describing: error) }
        results.append(result)
    }
    let result: [String: Any] = ["schema": "camera-text-ocr-observation-result-v1", "frames": results,
        "engine": "macOS Vision VNRecognizeTextRequest", "recognitionLanguages": ["zh-Hans", "en-US"],
        "languageCorrection": false, "customWords": [], "qualityAccepted": false, "mtfQualified": false,
        "sdkMetadataAuthenticated": false, "modelDrivenCameraDecisions": false,
        "scope": "Actual archived text recognition only; language-model priors remain. Not optical resolution, calibration or all-quality acceptance."]
    try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
        .write(to: output, options: [.withoutOverwriting])
    print("OCR observations written for \(results.count) image files")
}
do { try run() } catch {
    FileHandle.standardError.write(Data("OCR observation failed: \(error)\n".utf8))
    exit(1)
}
