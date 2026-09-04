import argparse
import os
import sys
from collections import Counter, deque
from datetime import datetime
import time

import cv2

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.db import create_table, find_matching_record, insert_entry, update_exit
from detector.plate_detector import detect_plate_details, scan_box
from utils.helpers import calculate_duration, clean_plate, is_allowed

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
IMAGE_DIR = os.path.join(BASE_DIR, "frontend", "static", "images")
DEFAULT_CAMERA_ID = 0
DEFAULT_MIN_EXIT_DELAY = 120
DEFAULT_ACTION_COOLDOWN = 60
DEFAULT_DETECT_EVERY = 5
MIN_VOTES = 1

plate_buffer = deque(maxlen=10)
last_action_at = {}


def parse_args():
    parser = argparse.ArgumentParser(description="Campus vehicle number plate camera")
    parser.add_argument("--camera", default=str(DEFAULT_CAMERA_ID), help="OpenCV camera id or stream URL")
    parser.add_argument(
        "--gate",
        choices=("auto", "entry", "exit"),
        default="auto",
        help="Use entry/exit when you have dedicated cameras. Auto toggles open records.",
    )
    parser.add_argument(
        "--min-exit-delay",
        type=int,
        default=DEFAULT_MIN_EXIT_DELAY,
        help="Minimum seconds between entry and exit for the same plate.",
    )
    parser.add_argument(
        "--cooldown",
        type=int,
        default=DEFAULT_ACTION_COOLDOWN,
        help="Seconds to ignore the same plate after saving an entry or exit.",
    )
    parser.add_argument(
        "--detect-every",
        type=int,
        default=DEFAULT_DETECT_EVERY,
        help="Run OCR once every N frames so the live camera feed stays responsive.",
    )
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Disable the OpenCV preview window when running without a desktop.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print every OCR result attempt for camera troubleshooting.",
    )
    return parser.parse_args()


def camera_source(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def open_camera(source):
    if isinstance(source, int):
        backends = (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY)
        cap = None
        for backend in backends:
            trial = cv2.VideoCapture(source, backend)
            if trial.isOpened():
                cap = trial
                break
            trial.release()
        if cap is None:
            cap = cv2.VideoCapture(source)
    else:
        cap = cv2.VideoCapture(source)

    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def image_path_for(action, plate_text, timestamp):
    filename = f"{action}_{plate_text}_{timestamp}.jpg"
    return os.path.join(IMAGE_DIR, filename)


def stable_plate(buffer):
    if len(buffer) < MIN_VOTES:
        return None
    plate_text, votes = Counter(buffer).most_common(1)[0]
    if votes < MIN_VOTES:
        return None
    return plate_text


def recently_saved(plate_text, action, cooldown):
    key = (plate_text, action)
    now_ts = datetime.now().timestamp()
    previous = last_action_at.get(key)
    if previous and now_ts - previous < cooldown:
        return True
    last_action_at[key] = now_ts
    return False


def draw_status(frame, status, detected_plate=None):
    x1, y1, x2, y2 = scan_box(frame)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 255), 2)
    cv2.putText(
        frame,
        "Keep number plate inside this box",
        (x1, max(92, y1 - 12)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (0, 220, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 64), (20, 20, 20), -1)
    cv2.putText(
        frame,
        status,
        (16, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    if detected_plate:
        cv2.putText(
            frame,
            f"Plate: {detected_plate}",
            (16, 56),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )


def save_debug_snapshot(frame):
    os.makedirs(IMAGE_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    frame_path = os.path.join(IMAGE_DIR, f"debug_frame_{timestamp}.jpg")
    crop_path = os.path.join(IMAGE_DIR, f"debug_crop_{timestamp}.jpg")
    x1, y1, x2, y2 = scan_box(frame)
    cv2.imwrite(frame_path, frame)
    cv2.imwrite(crop_path, frame[y1:y2, x1:x2])
    print(f"Saved debug frame: {frame_path}")
    print(f"Saved debug crop: {crop_path}")


def save_entry(frame, plate_text, timestamp, now, cooldown):
    if recently_saved(plate_text, "entry", cooldown):
        print("Ignored: entry cooldown")
        return

    image_path = image_path_for("entry", plate_text, timestamp)
    cv2.imwrite(image_path, frame)
    insert_entry(plate_text, now.strftime("%Y-%m-%d %H:%M:%S"), image_path)
    print(f"ENTRY saved: {plate_text}")


def save_exit(frame, plate_text, record, timestamp, now, min_exit_delay, cooldown):
    entry_time = record[2]
    entry_dt = datetime.strptime(entry_time, "%Y-%m-%d %H:%M:%S")

    if (now - entry_dt).total_seconds() < min_exit_delay:
        print("Ignored: exit too soon after entry")
        return

    if recently_saved(plate_text, "exit", cooldown):
        print("Ignored: exit cooldown")
        return

    image_path = image_path_for("exit", plate_text, timestamp)
    cv2.imwrite(image_path, frame)

    exit_time = now.strftime("%Y-%m-%d %H:%M:%S")
    duration = calculate_duration(entry_time, exit_time)
    update_exit(record[0], exit_time, duration, image_path)
    print(f"EXIT saved: {plate_text}")


def main():
    os.makedirs(IMAGE_DIR, exist_ok=True)
    create_table()

    args = parse_args()
    source = camera_source(args.camera)
    cap = open_camera(source)

    if not cap.isOpened():
        print(f"Camera not accessible: {args.camera}")
        print("Try --camera 1, --camera 2, or close other apps that may be using the webcam.")
        return 1

    detect_every = max(1, args.detect_every)
    frame_count = 0
    empty_reads = 0
    last_plate = None
    last_status = "Waiting for plate"

    print(f"Smart Camera Started | camera={args.camera} gate={args.gate} detect_every={detect_every}")
    print(
        "Camera frame size: "
        f"{int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))} "
        f"fps={cap.get(cv2.CAP_PROP_FPS):.1f}"
    )
    print("Press q in the preview window to stop.")
    print("Press s in the preview window to save a debug frame and crop.")
    if not args.no_preview:
        cv2.namedWindow("Smart Camera", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Smart Camera", 960, 540)

    while True:
        ret, frame = cap.read()
        if not ret:
            empty_reads += 1
            if empty_reads > 30:
                print("Camera stopped returning frames")
                break
            time.sleep(0.05)
            continue

        empty_reads = 0
        frame_count += 1

        if frame_count % detect_every == 0:
            details = detect_plate_details(frame)
            raw_text = details.get("plate")
            cleaned = clean_plate(raw_text)
            if args.debug:
                print(
                    "OCR "
                    f"plate={raw_text!r} cleaned={cleaned!r} "
                    f"raw={details.get('raw')!r} "
                    f"source={details.get('source')} "
                    f"contours={details.get('contours')} "
                    f"conf={details.get('confidence'):.1f}",
                    flush=True,
                )

            if cleaned:
                plate_buffer.append(cleaned)
                plate_text = stable_plate(plate_buffer)
                last_plate = cleaned

                if plate_text and is_allowed(plate_text):
                    print(f"FINAL PLATE: {plate_text}")
                    record = find_matching_record(plate_text)
                    now = datetime.now()
                    timestamp = now.strftime("%Y%m%d_%H%M%S")

                    if args.gate == "entry":
                        save_entry(frame, plate_text, timestamp, now, args.cooldown)
                        last_status = f"Entry recorded: {plate_text}"
                    elif args.gate == "exit":
                        if record:
                            save_exit(
                                frame, plate_text, record, timestamp, now,
                                args.min_exit_delay, args.cooldown
                            )
                            last_status = f"Exit recorded: {plate_text}"
                        else:
                            last_status = "Exit ignored: no open entry found"
                            print("Ignored: no open entry found for this exit")
                    elif record:
                        save_exit(
                            frame, plate_text, record, timestamp, now,
                            args.min_exit_delay, args.cooldown
                        )
                        last_status = f"Exit recorded: {plate_text}"
                    else:
                        save_entry(frame, plate_text, timestamp, now, args.cooldown)
                        last_status = f"Entry recorded: {plate_text}"
                else:
                    last_status = f"Reading plate: {cleaned}"
            else:
                last_status = "Waiting for plate"

        if not args.no_preview:
            draw_status(frame, last_status, last_plate)
            cv2.imshow("Smart Camera", frame)

        if not args.no_preview:
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            if key == ord('s'):
                save_debug_snapshot(frame)

    cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
