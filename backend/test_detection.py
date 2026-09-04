"""
Smoke tests for plate detection and plate cleaning.
"""
import os
import sys

import cv2

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from detector.plate_detector import detect_plate
from utils.helpers import clean_plate


def test_plate_detection():
    print("Testing Plate Detection System")
    print("=" * 50)

    test_image_path = os.path.join(os.path.dirname(__file__), "test.jpg")

    if os.path.exists(test_image_path):
        print(f"Testing with image: {test_image_path}")
        image = cv2.imread(test_image_path)

        if image is not None:
            detected_text = detect_plate(image)
            print(f"Raw OCR result: {detected_text}")

            cleaned = clean_plate(detected_text)
            print(f"Cleaned plate: {cleaned}")
        else:
            print("Could not load test image")
    else:
        print("No test image found")

    print("\nTesting plate cleaning with sample data:")
    test_plates = [
        "RJ14CV0002",
        "MH01AB1234",
        "DL01CD5678",
        "KA01IJ7890",
        "UP01GH3456",
        "22BH6517A",
        "22BHE517A",
    ]

    for plate in test_plates:
        cleaned = clean_plate(plate)
        status = "OK" if cleaned else "FAIL"
        print(f"   {plate} -> {cleaned} {status}")

    print("\nTest completed")


if __name__ == "__main__":
    test_plate_detection()
