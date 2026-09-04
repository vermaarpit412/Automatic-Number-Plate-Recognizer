import time
import re
from datetime import datetime
from difflib import SequenceMatcher

# -------------------------------
# Plate Cleaning
# -------------------------------
def _only_plate_chars(text):
    return re.sub(r'[^A-Z0-9]', '', text.upper()).strip()


def _fix_common_ocr_confusions(text, pattern):
    """Correct OCR mistakes when a plate position is clearly letter or digit."""
    digit_map = str.maketrans({
        "O": "0", "Q": "0", "D": "0",
        "I": "1", "L": "1", "T": "1",
        "Z": "2", "S": "5", "G": "6", "E": "6", "B": "8",
    })
    letter_map = str.maketrans({
        "0": "O", "1": "I", "2": "Z", "5": "S", "6": "G", "8": "B",
    })

    corrected = []
    for char, expected in zip(text, pattern):
        if expected == "D":
            corrected.append(char.translate(digit_map))
        elif expected == "L":
            corrected.append(char.translate(letter_map))
        else:
            corrected.append(char)
    return "".join(corrected)


def clean_plate(text):
    """
    Clean and validate Indian license plate format
    Indian plates: XX00XX0000 or XX00XXX0000 format
    """
    if not text:
        return None

    text = _only_plate_chars(text)

    if len(text) < 8:
        return None

    candidates = []
    if len(text) <= 11:
        candidates.append(text)
    else:
        for size in range(11, 7, -1):
            for start in range(0, len(text) - size + 1):
                candidates.append(text[start:start + size])

    # Standard Indian state plates: RJ14CV0002, MH01AB1234, DL1CAB1234.
    expanded_candidates = list(candidates)
    for candidate in candidates:
        for pattern in ("LLDDLLDDDD", "LLDDLLLDDDD", "LLD LLLDDDD".replace(" ", "")):
            if len(candidate) == len(pattern):
                expanded_candidates.append(_fix_common_ocr_confusions(candidate, pattern))

    # Bharat series plates: 22BH6517A or 22BH6517AA.
    for candidate in candidates:
        for pattern in ("DDLLDDDDL", "DDLLDDDDLL"):
            if len(candidate) == len(pattern):
                corrected = _fix_common_ocr_confusions(candidate, pattern)
                if candidate[4:5] == "B":
                    expanded_candidates.append(corrected[:4] + "6" + corrected[5:])
                expanded_candidates.append(corrected)

    validators = (
        r'^[A-Z]{2}\d{2}[A-Z]{1,3}\d{4}$',
        r'^[A-Z]{2}\d[A-Z]{1,3}\d{4}$',
        r'^\d{2}BH\d{4}[A-Z]{1,2}$',
    )

    for candidate in expanded_candidates:
        if any(re.match(pattern, candidate) for pattern in validators):
            return candidate

    return None


# -------------------------------
# Duration Calculation
# -------------------------------
def calculate_duration(entry_time_str, exit_time_str):
    fmt = "%Y-%m-%d %H:%M:%S"

    entry_time = datetime.strptime(entry_time_str, fmt)
    exit_time = datetime.strptime(exit_time_str, fmt)

    duration = exit_time - entry_time
    total_seconds = int(duration.total_seconds())

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    return f"{hours}h {minutes}m"


# -------------------------------
# Buffer System
# -------------------------------
last_seen = {}
BUFFER_TIME = 10

def is_allowed(plate):
    current_time = time.time()

    if plate in last_seen:
        if current_time - last_seen[plate] < BUFFER_TIME:
            return False

    last_seen[plate] = current_time
    return True


# -------------------------------
# Similarity Matching
# -------------------------------
def is_similar(p1, p2, threshold=0.82):
    p1 = _only_plate_chars(p1 or "")
    p2 = _only_plate_chars(p2 or "")
    if not p1 or not p2:
        return False
    if p1 == p2:
        return True
    if abs(len(p1) - len(p2)) > 1:
        return False
    return SequenceMatcher(None, p1, p2).ratio() >= threshold
