#!/usr/bin/env python3
import argparse
import logging
import os
import sys
import time
import traceback
from datetime import datetime, timedelta

import cv2

from ai.parser import InvalidOutputError, parse
from ai.qwen import (
    AIError,
    check_reachable,
    resolve_endpoint,
    send_bytes_with_retry,
    send_with_retry,
)
from camera.camera import Camera, CameraError
from config import Config
from processing.overlay import annotate
from processing.stitch import stitch_horizontal
from sound.playback import SoundPlayer
from storage.csv_logger import CsvLogger
from utils.format import capture_label, csv_timestamp, parse_datetime
from utils.preview import ascii_preview

logger = logging.getLogger("rain_logger")

STATUS_VALID = "VALID"
STATUS_CAMERA_FAILURE = "CAMERA_FAILURE"
STATUS_AI_FAILURE = "AI_FAILURE"
STATUS_INVALID_OUTPUT = "INVALID_OUTPUT"


_CONFIG_GUIDE = """\
Configuration:
  All settings live in config.yaml (same directory as this script).
  Every field is optional; omitted fields fall back to the defaults below.

  schedule:
    interval_minutes  capture interval in minutes (default: 30)
    start_at          "YYYY-MM-DD HH:MM:SS" local time; empty = start now
    stop_at           "YYYY-MM-DD HH:MM:SS" local time; empty = run until
                      interrupted

  ai:
    provider          "llama-cpp" (default), a built-in provider name
                      (openai, mistral, groq, together, openrouter,
                      fireworks, deepseek), or "custom" for any URL
    base_url          endpoint override; required for "custom"
    api_key_env       env var holding the API key; required for providers
                      that need authentication
    model             model identifier reported by the endpoint
    max_tokens        max tokens for the AI response (default: 1024)
    timeout_seconds   HTTP timeout per AI request (default: 120);
                      0 disables the timeout
    retry_attempts    AI retries before failing (default: 3)

  camera:
    device_index      OpenCV camera index, e.g. 0 = /dev/video0
    width / height    requested resolution (0 = camera default)

  sound:
    enabled           play shutter sound after each capture (default: true)
    volume            playback volume 0.0-1.0 (default: 0.8)
    playback_command  Linux WAV player, e.g. "aplay" or "paplay"

  paths:              file and directory locations (relative to config.yaml)

  See comments in config.yaml for the full list of settings.
"""


def main():
    parser = argparse.ArgumentParser(
        description="AI-powered unattended rain monitoring system.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_CONFIG_GUIDE,
    )
    parser.add_argument(
        "--start-at",
        metavar="'YYYY-MM-DD HH:MM:SS'",
        help="Override the scheduled start time (local time).",
    )
    parser.add_argument(
        "--stop-at",
        metavar="'YYYY-MM-DD HH:MM:SS'",
        help="Override the scheduled stop time (local time).",
    )
    parser.add_argument(
        "--debug-preview",
        action="store_true",
        help="Show ASCII previews of captured and stitched images.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run one capture immediately without scheduling or writing any "
        "files; print results to the terminal.",
    )
    args = parser.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    config = Config.load(
        os.path.join(here, "config.yaml"),
        start_at=args.start_at,
        stop_at=args.stop_at,
    )
    _setup_logging(config.path("log_file"), file_log=not args.dry_run)
    try:
        if args.dry_run:
            dry_run(config)
        else:
            run(config, debug=args.debug_preview)
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        sys.exit(0)


def _setup_logging(log_path, file_log=True):
    formatter = logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S")
    root = logging.getLogger("rain_logger")
    root.setLevel(logging.INFO)
    root.handlers = []
    if file_log:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)


def run(config, debug):
    system_message_path = config.path("system_message")
    if not os.path.exists(system_message_path):
        logger.error("AI system prompt file missing: %s", system_message_path)
        sys.exit(1)
    with open(system_message_path, "r", encoding="utf-8") as f:
        system_message = f.read()

    try:
        base_url, api_key = resolve_endpoint(config.ai)
    except AIError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    logger.info("Checking AI endpoint at %s ...", base_url)
    if not check_reachable(base_url, api_key=api_key):
        logger.error(
            "AI endpoint %s is unreachable. Start llama-server (or the "
            "configured provider) and retry.",
            base_url,
        )
        sys.exit(1)
    logger.info("AI endpoint reachable.")

    start = parse_datetime(config.schedule.get("start_at")) or datetime.now()
    stop = parse_datetime(config.schedule.get("stop_at"))
    interval_minutes = config.schedule["interval_minutes"]

    csv_logger = CsvLogger(config.path("csv_file"))
    csv_logger.backfill_power_off(start, interval_minutes, datetime.now())

    sound_player = SoundPlayer(
        config.path("shutter_sound"),
        enabled=config.sound["enabled"],
        volume=config.sound["volume"],
        command=config.sound.get("playback_command", "aplay"),
    )
    camera = Camera(config, sound_player)

    logger.info(
        "Rain logger started. Start: %s Stop: %s Interval: %d minutes.",
        start.strftime("%Y-%m-%d %H:%M:%S"),
        stop.strftime("%Y-%m-%d %H:%M:%S") if stop else "none",
        interval_minutes,
    )

    while True:
        now = datetime.now()
        if stop and now >= stop:
            logger.info("Stop time reached.")
            break
        slot = _next_slot(start, interval_minutes, now)
        if stop and slot > stop:
            logger.info("Stop time reached.")
            break
        _sleep_until(slot)
        logger.info("Scheduled capture time reached.")
        _perform_capture(
            slot, config, csv_logger, camera, system_message, base_url,
            api_key, debug,
        )


def dry_run(config):
    system_message_path = config.path("system_message")
    if not os.path.exists(system_message_path):
        logger.error("AI system prompt file missing: %s", system_message_path)
        sys.exit(1)
    with open(system_message_path, "r", encoding="utf-8") as f:
        system_message = f.read()

    try:
        base_url, api_key = resolve_endpoint(config.ai)
    except AIError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    logger.info("Checking AI endpoint at %s ...", base_url)
    if not check_reachable(base_url, api_key=api_key):
        logger.error("AI endpoint %s is unreachable.", base_url)
        sys.exit(1)
    logger.info("AI endpoint reachable.")

    sound_player = SoundPlayer(
        config.path("shutter_sound"),
        enabled=config.sound["enabled"],
        volume=config.sound["volume"],
        command=config.sound.get("playback_command", "aplay"),
    )
    camera = Camera(config, sound_player)

    slot = datetime.now()
    label = capture_label(slot)
    print(f"\n=== DRY RUN capture at {csv_timestamp(slot)} ===")

    try:
        frames = camera.capture_sequence()
    except CameraError as exc:
        logger.error("Camera failure: %s", exc)
        sys.exit(1)
    for index, frame in enumerate(frames, 1):
        print(f"--- ASCII preview: captured image {index}/3 ---")
        print(ascii_preview(frame))

    stitched = stitch_horizontal(
        frames, separator_width=config.camera["separator_width"]
    )
    print("--- ASCII preview: stitched image ---")
    print(ascii_preview(stitched))

    ok, encoded = cv2.imencode(".png", stitched)
    if not ok:
        logger.error("Failed to encode stitched image.")
        sys.exit(1)

    try:
        text = send_bytes_with_retry(
            base_url,
            config.ai["model"],
            encoded.tobytes(),
            system_message,
            attempts=config.ai["retry_attempts"],
            backoff_seconds=config.ai["backoff_seconds"],
            max_backoff_seconds=config.ai["max_backoff_seconds"],
            timeout=config.ai["timeout_seconds"],
            api_key=api_key,
            max_tokens=config.ai.get("max_tokens", 1024),
        )
        logger.info("AI response received.")
        result = parse(text)
        logger.info("AI output parsed and validated.")
    except InvalidOutputError as exc:
        logger.error("Invalid AI output: %s", exc)
        sys.exit(1)
    except AIError as exc:
        logger.error("AI failure: %s", exc)
        sys.exit(1)

    print("\n--- AI response ---")
    print(text)
    print("\n--- Parsed result ---")
    print(f"  Rain Type:            {result.rain_type}")
    print(f"  Rain Confidence:      {result.rain_confidence:.1f}%")
    print(f"  Rain Type Confidence: {result.rain_type_confidence:.1f}%")
    print(f"  Message:              {result.message or '-'}")
    print(f"  Warnings:             {result.warnings or '-'}")

    record = {
        "timestamp": csv_timestamp(slot),
        "status": STATUS_VALID,
        "rain_type": result.rain_type,
        "rain_confidence": f"{result.rain_confidence:.1f}",
        "rain_type_confidence": f"{result.rain_type_confidence:.1f}",
        "message": result.message,
        "warnings": result.warnings,
        "image_path": f"Database/images/annotated/{label}.png",
        "raw_image_path": f"Database/images/raw/{label}.png",
    }

    annotated = annotate(
        stitched,
        _annotation_lines(label, record, result),
        font_size_pt=config.image["annotated_font_size_pt"],
        dpi=config.image["dpi"],
        margin=config.image["margin"],
    )
    print("--- ASCII preview: annotated image ---")
    print(ascii_preview(annotated))

    print("\n--- Would-be CSV record (not written) ---")
    for key, value in record.items():
        print(f"  {key}: {value}")
    print("\nDry run complete. No files were written.")


def _next_slot(start, interval_minutes, now):
    interval = timedelta(minutes=interval_minutes)
    elapsed = (now - start).total_seconds()
    n = max(0, int(elapsed // (interval_minutes * 60)))
    slot = start + n * interval
    if slot < now:
        slot = start + (n + 1) * interval
    return slot


def _sleep_until(target):
    while True:
        remaining = (target - datetime.now()).total_seconds()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 5.0))


def _perform_capture(slot, config, csv_logger, camera, system_message,
                     base_url, api_key, debug):
    label = capture_label(slot)
    record = {
        "timestamp": csv_timestamp(slot),
        "status": STATUS_VALID,
        "rain_type": "",
        "rain_confidence": "",
        "rain_type_confidence": "",
        "message": "",
        "warnings": "",
        "image_path": "",
        "raw_image_path": "",
    }
    try:
        _capture(label, config, camera, system_message, base_url, api_key,
                 debug, record)
    except Exception:
        logger.error("Unexpected capture error:\n%s", traceback.format_exc())
        record["status"] = (
            STATUS_CAMERA_FAILURE if not record["raw_image_path"] else STATUS_AI_FAILURE
        )
    finally:
        csv_logger.append(record)


def _capture(label, config, camera, system_message, base_url, api_key, debug,
             record):
    frames = None
    try:
        frames = camera.capture_sequence()
        if debug:
            for index, frame in enumerate(frames, 1):
                print(f"--- ASCII preview: captured image {index}/3 ---")
                print(ascii_preview(frame))
    except CameraError as exc:
        record["status"] = STATUS_CAMERA_FAILURE
        logger.error("Camera failure: %s", exc)
        return

    stitched = stitch_horizontal(
        frames, separator_width=config.camera["separator_width"]
    )
    if debug:
        print("--- ASCII preview: stitched image ---")
        print(ascii_preview(stitched))

    raw_path = _save_image(config, "raw", label, stitched)
    record["raw_image_path"] = raw_path

    if not raw_path:
        record["status"] = STATUS_CAMERA_FAILURE
        return

    result = None
    try:
        text = send_with_retry(
            base_url,
            config.ai["model"],
            os.path.join(config.base_dir, raw_path),
            system_message,
            attempts=config.ai["retry_attempts"],
            backoff_seconds=config.ai["backoff_seconds"],
            max_backoff_seconds=config.ai["max_backoff_seconds"],
            timeout=config.ai["timeout_seconds"],
            api_key=api_key,
            max_tokens=config.ai.get("max_tokens", 1024),
        )
        logger.info("AI response received.")
        result = parse(text)
        logger.info("AI output parsed and validated.")
        record["status"] = STATUS_VALID
        record["rain_type"] = result.rain_type
        record["rain_confidence"] = f"{result.rain_confidence:.1f}"
        record["rain_type_confidence"] = f"{result.rain_type_confidence:.1f}"
        record["message"] = result.message
        record["warnings"] = result.warnings
    except InvalidOutputError as exc:
        record["status"] = STATUS_INVALID_OUTPUT
        logger.error("Invalid AI output: %s", exc)
    except AIError as exc:
        record["status"] = STATUS_AI_FAILURE
        logger.error("AI failure: %s", exc)

    annotated = annotate(
        stitched,
        _annotation_lines(label, record, result),
        font_size_pt=config.image["annotated_font_size_pt"],
        dpi=config.image["dpi"],
        margin=config.image["margin"],
    )
    annotated_path = _save_image(config, "annotated", label, annotated)
    record["image_path"] = annotated_path


def _save_image(config, kind, label, image):
    directory = config.path("annotated_images_dir" if kind == "annotated" else "raw_images_dir")
    filename = f"{label}.png"
    absolute = os.path.join(directory, filename)
    try:
        os.makedirs(directory, exist_ok=True)
        if not cv2.imwrite(absolute, image):
            raise OSError("cv2.imwrite returned False")
        relative = os.path.relpath(absolute, config.base_dir)
        logger.info("Saved %s image: %s", kind, relative)
        return relative
    except OSError as exc:
        logger.error("File write error while saving %s image: %s", kind, exc)
        return ""


def _annotation_lines(label, record, result):
    lines = [f"Date & Time: {label}"]
    if record["status"] != STATUS_VALID:
        lines.append(f"Status: {record['status']}")
        return lines
    lines.append(f"Rain Type: {result.rain_type}")
    lines.append(f"Rain Confidence: {record['rain_confidence']}%")
    lines.append(f"Rain Type Confidence: {record['rain_type_confidence']}%")
    if result.message:
        lines.append(f"Message: {result.message}")
    if result.warnings:
        lines.append(f"Warnings: {result.warnings}")
    return lines


if __name__ == "__main__":
    main()
