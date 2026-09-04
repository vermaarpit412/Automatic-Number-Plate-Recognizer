import os

import cv2
import pytesseract

from utils.helpers import clean_plate


tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(tesseract_path):
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
else:
    print(f"Tesseract not found at {tesseract_path}")
    print("Install Tesseract OCR or update tesseract_path in detector/plate_detector.py")


OCR_CONFIGS = [
    "--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
]
OCR_TIMEOUT_SECONDS = 0.8
MAX_DETECTION_WIDTH = 900
MAX_CONTOURS_TO_OCR = 2


def preprocess_image(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.bilateralFilter(gray, 11, 17, 17)
    blur = cv2.GaussianBlur(blur, (5, 5), 0)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(blur)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    return cv2.morphologyEx(enhanced, cv2.MORPH_CLOSE, kernel)


def build_ocr_variants(gray_image):
    variants = []
    height, width = gray_image.shape[:2]
    scale = 2.2 if max(height, width) < 500 else 1.5
    resized = cv2.resize(gray_image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    variants.append(resized)

    _, otsu = cv2.threshold(resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(otsu)
    return variants


def _safe_conf(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return -1.0


def ocr_plate_region(region):
    best_text = None
    best_confidence = 0.0
    best_raw = None

    if len(region.shape) == 3:
        bases = [preprocess_image(region)]
    else:
        bases = [region]

    for base in bases:
        for variant in build_ocr_variants(base):
            for config in OCR_CONFIGS:
                try:
                    raw_text = pytesseract.image_to_string(
                        variant,
                        config=config,
                        timeout=OCR_TIMEOUT_SECONDS,
                    ).strip()
                except RuntimeError:
                    continue

                if raw_text and not best_raw:
                    best_raw = raw_text

                cleaned = clean_plate(raw_text)
                if cleaned:
                    best_text = cleaned
                    best_confidence = 50.0
                    return best_text, best_confidence, best_raw

    return best_text, best_confidence, best_raw


def find_plate_contours(image):
    edges = cv2.Canny(image, 100, 200)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated = cv2.dilate(edges, kernel, iterations=1)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    valid_contours = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = cv2.contourArea(cnt)
        if area < 700 or area > 90000:
            continue

        aspect_ratio = w / float(h)
        if 1.6 < aspect_ratio < 8.0:
            perimeter = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * perimeter, True)
            if 4 <= len(approx) <= 10:
                valid_contours.append((cnt, area))

    valid_contours.sort(key=lambda item: item[1], reverse=True)
    return [cnt for cnt, _ in valid_contours[:MAX_CONTOURS_TO_OCR]]


def _resize_for_detection(frame):
    height, width = frame.shape[:2]
    if width <= MAX_DETECTION_WIDTH:
        return frame, 1.0
    scale = MAX_DETECTION_WIDTH / float(width)
    resized = cv2.resize(frame, (MAX_DETECTION_WIDTH, int(height * scale)), interpolation=cv2.INTER_AREA)
    return resized, scale


def scan_box(frame):
    height, width = frame.shape[:2]
    return (
        int(width * 0.08),
        int(height * 0.28),
        int(width * 0.92),
        int(height * 0.78),
    )


def _fallback_crops(frame):
    height, width = frame.shape[:2]
    boxes = [
        scan_box(frame),
        (0, int(height * 0.12), width, int(height * 0.94)),
        (int(width * 0.05), int(height * 0.42), int(width * 0.95), int(height * 0.88)),
    ]
    for x1, y1, x2, y2 in boxes:
        crop = frame[y1:y2, x1:x2]
        if crop.size:
            yield crop


def detect_plate_details(frame):
    try:
        best_raw = None
        for crop in _fallback_crops(frame):
            text, confidence, raw = ocr_plate_region(crop)
            if raw and not best_raw:
                best_raw = raw
            if text and confidence >= 35:
                return {
                    "plate": text,
                    "confidence": confidence,
                    "raw": raw or text,
                    "source": "scan-box",
                    "contours": 0,
                }

        work_frame, scale = _resize_for_detection(frame)
        processed = preprocess_image(work_frame)
        contours = find_plate_contours(processed)

        best_text = None
        best_confidence = 0.0

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            padding = 10
            x1 = max(0, int((x - padding) / scale))
            y1 = max(0, int((y - padding) / scale))
            x2 = min(frame.shape[1], int((x + w + padding) / scale))
            y2 = min(frame.shape[0], int((y + h + padding) / scale))

            text, confidence, raw = ocr_plate_region(frame[y1:y2, x1:x2])
            if raw and not best_raw:
                best_raw = raw
            if text and confidence > best_confidence:
                best_text = text
                best_confidence = confidence

        if best_text and best_confidence >= 35:
            return {
                "plate": best_text,
                "confidence": best_confidence,
                "raw": best_raw or best_text,
                "source": "contour",
                "contours": len(contours),
            }

        return {
            "plate": None,
            "confidence": best_confidence,
            "raw": best_raw,
            "source": "none",
            "contours": len(contours),
        }
    except Exception as exc:
        print(f"Plate detection error: {exc}")
        return {
            "plate": None,
            "confidence": 0.0,
            "raw": None,
            "source": "error",
            "contours": 0,
        }


def detect_plate(frame):
    return detect_plate_details(frame).get("plate")
