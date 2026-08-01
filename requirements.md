# AI-Powered Rain Logger - Software Requirements

## 1. Overview

Build an unattended AI-powered rain monitoring system using Python.

The system uses a fixed outdoor camera and a vision-language model (Qwen3-VL through llama.cpp) to detect active rainfall, classify intensity, and create a scientific observation dataset.

The application must prioritize reliability, recoverability, and human-reviewable data.

# 2. Technology Requirements

## Programming Language

Python.

## Camera

USB webcam, captured through OpenCV.

## AI Backend

The model is accessed through any OpenAI-compatible HTTP endpoint.

Two backend modes are supported, selected in `config.yaml`:

1. `llama-cpp`:

   - llama.cpp `llama-server` serving a Qwen3-VL 4B GGUF model.
   - The `llama-server` process is started and managed by the operator, not by the application.
   - Default base URL: `http://127.0.0.1:8080`.

2. `openai-compatible`:

   - Any OpenAI-compatible provider (for example from models.dev) or a custom URL.
   - The provider name maps to a default base URL (for example `openai`, `groq`, `together`, `openrouter`, `mistral`, `deepseek`).
   - A custom URL is supported via `provider: custom` with an explicit `base_url`.
   - API keys are read from an environment variable named in `ai.api_key_env`; providers that require authentication must fail at startup with a clear error if no key is available.

The application connects using the resolved base URL, model name, and optional API key from the configuration file.

The AI system prompt must be loaded from:

```
`assets/system-message.md`
```

Do not hardcode the AI system prompt in Python files.

At startup, the application must verify that the AI endpoint is reachable.

If the endpoint is unreachable, the application must exit with a clear error message.

## Configuration

All settings must be defined in a YAML configuration file:

```
`config.yaml`
```

Loaded by:

```
`config.py`
```

Settings include: schedule, AI endpoint, capture interval, storage paths, AI retry settings, and audio settings.

CLI flags override configuration values when provided.

## Dependencies

Python dependencies must be declared in:

```
`requirements.txt`
```

Core dependencies include: OpenCV (camera), Pillow (image processing and annotation), PyYAML (configuration), requests (AI HTTP communication), and a WAV playback library.

# 3. Project Structure

Recommended structure:

```
`rain_logger/`

`├── main.py`

`├── config.py`

`├── config.yaml`

`├── requirements.txt`

`├── camera/`

`│   └── camera.py`

`├── ai/`

`│   ├── qwen.py`

`│   └── parser.py`

`├── processing/`

`│   ├── stitch.py`

`│   └── overlay.py`

`├── storage/`

`│   └── csv_logger.py`

`├── assets/`

`│   ├── system-message.md`

`│   └── camera_snap.wav`

`├── Database/`

`│   ├── rain_log.csv`

`│   └── images/`

`│       ├── raw/`

`│       └── annotated/`

`└── logs/`

`    └── system.log`
```

# 4. CLI Requirements

The application must support:

```
`--start-at`

`--stop-at`

`--debug-preview`

`--dry-run`
```

Example:

```
`python main.py \`

`--start-at "2026-08-02 00:00:00" \`

`--stop-at "2026-08-09 00:00:00"`
```

Behavior:

- `--start-at` and `--stop-at` override the schedule defined in `config.yaml`.
- Times are parsed in the machine's local system time.
- If `--start-at` is omitted, the capture schedule starts immediately.
- If `--stop-at` is omitted, the application runs until interrupted.

## Dry Run

When `--dry-run` is enabled:

- Perform a single capture immediately, ignoring start/stop times.
- Run the full pipeline: capture sequence, stitching, AI analysis, annotation.
- Do not write any files (no images, CSV, or log file).
- Print to the terminal: ASCII previews, the AI response, the parsed result, and the would-be CSV record.

# 5. Scheduling Requirements

The system must:

- Use the machine's local system time.
- Wait until the configured start time.
- Capture every 30 minutes.
- Stop automatically at the configured stop time.

Do not use fixed sleep intervals.

The next capture time must be calculated from:

```
`start_time + (capture_number × 30 minutes)`
```

This prevents schedule drift caused by:

- AI inference time.
- Camera delays.
- Processing time.

# 6. Camera Requirements

## Camera API

The camera is a USB webcam captured through OpenCV.

## Capture Sequence

For every scheduled capture:

1. Initialize camera.
2. Turn camera LED on.
3. Wait 5 seconds.
4. Capture image 1.
5. Play shutter sound.
6. Wait 1 second.
7. Capture image 2.
8. Play shutter sound.
9. Wait 1 second.
10. Capture image 3.
11. Play shutter sound.
12. Turn LED off.
13. Release camera.

Note:

- The LED refers to the camera's built-in LED.
- Control it through the camera driver's native controls when supported.
- If the webcam does not expose LED control, log a warning and continue.
- LED control failure must not abort the capture.

# 7. Capture Sound Requirements

A short WAV file must be played after successful image capture.

Location:

```
`assets/camera_snap.wav`
```

Purpose:

- Confirm capture happened.
- Allow nearby human observation.

Requirements:

- Low volume.
- Short duration.
- Not a notification/alarm sound.
- Not intended to wake sleeping people.

# 8. Image Processing Requirements

Three images must be stitched horizontally.

Format:

```
`IMAGE 1 | BLACK SEPARATOR | IMAGE 2 | BLACK SEPARATOR | IMAGE 3`
```

Requirements:

- Separators must be clearly visible.
- AI must be able to distinguish frames.
- Do not create a seamless panorama.

# 9. Image Storage Requirements

Image format:

PNG.

Store:

- Raw stitched image.
- Annotated image.

Structure:

```
`Database/`

`└── images/`

`    ├── raw/`

`    └── annotated/`
```

## Naming Convention

Filenames are based on the scheduled capture time, in the format:

```
`12th July 2026 11:30 AM.png`
```

Rules:

- Ordinal day, full month name, full year.
- 12-hour time with AM/PM.
- The scheduled capture time determines the filename, not the completion time.
- The same base filename is used in both `raw/` and `annotated/`.

# 10. Image Annotation Requirements

Annotated images must contain AI results.

Overlay:

- Top-left corner.
- Bold serif font.
- 72 pt font size.
- White text.
- Black stroke.
- 2 pt stroke width.
- No background box.
- Automatic wrapping.

Text order:

1. Date & Time
2. Rain Type
3. Rain Confidence
4. Rain Type Confidence
5. Message
6. Warnings

Failure annotations:

- Annotated images must be saved even when AI results are unavailable.
- In that case, show the failure status (for example `AI_FAILURE`) instead of the AI result fields.

# 11. AI Communication Requirements

The system must:

1. Send the stitched image to the Qwen3-VL model through the llama-server HTTP endpoint.
2. Receive model response.
3. Parse output.
4. Validate output.
5. Store result.

The AI output format is defined in:

```
`assets/system-message.md`
```

## Retry Policy

- AI communication is retried on failure with exponential backoff.
- The number of attempts and the backoff seconds are configurable in `config.yaml`.
- Default: 3 attempts.
- After all attempts fail, record the capture with `status = AI_FAILURE` and continue with the next scheduled capture.

## Startup Check

- At startup, the application verifies that the AI endpoint is reachable.
- If it is unreachable, the application exits with a clear error message.

# 12. CSV Database Requirements

The database format is CSV.

Location:

```
`Database/rain_log.csv`
```

The file must include a header row with the field names.

Required fields:

```
`timestamp`

`status`

`rain_type`

`rain_confidence`

`rain_type_confidence`

`message`

`warnings`

`image_path`

`raw_image_path`
```

## Timestamps

- Timestamps use the machine's local system time.
- Format: `YYYY-MM-DD HH:MM:SS`.
- The timestamp is the scheduled capture time.

## Failure Rows

- Rows with a failure status (`POWER_OFF`, `CAMERA_FAILURE`, `AI_FAILURE`, `INVALID_OUTPUT`) have empty `image_path` and `raw_image_path` unless an image was actually saved.
- `message` and `warnings` may be empty.
- Values containing commas or newlines must be CSV-escaped (quoted).

# 13. Status Values

Valid statuses:

```
`VALID`

`POWER_OFF`

`CAMERA_FAILURE`

`AI_FAILURE`

`INVALID_OUTPUT`
```

# 14. Power Loss Recovery

The system must resume cleanly after interruption.

On startup:

1. Read existing CSV.
2. Find the last recorded scheduled timestamp.
3. Calculate the missing scheduled timestamps between that point and the most recent scheduled slot at or before the current time.
4. Add missing records with `status = POWER_OFF`.

Missing captures must be logged as:

```
`status = POWER_OFF`
```

Rules:

- Existing rows must never be modified or duplicated.
- Backfilled rows must have empty `image_path` and `raw_image_path`.
- If no previous records exist, no backfill is performed.

Never interpret missing data as no rainfall.

# 15. Runtime Logging

Runtime logs must be separate from the rain database.

Location:

```
`logs/system.log`
```

Include:

- Scheduled capture events.
- Camera events.
- Image capture events.
- Stitching.
- AI communication.
- Parsing.
- Database updates.
- File saving.
- Errors.

Example:

```
`[23:30:00] Scheduled capture time reached.`

`[23:30:01] Camera initialized.`

`[23:30:07] Captured image 1/3.`

`[23:30:10] Images stitched.`

`[23:30:11] Sent image to AI.`

`[23:31:04] AI response received.`

`[23:31:05] Database entry added.`
```

# 16. Debug Mode

When:

```
`--debug-preview`
```

is enabled:

Show rough ASCII previews of:

- Captured images.
- Stitched image.

Normal operation should only log capture completion.

# 17. Error Handling

The system must handle:

- Camera unavailable.
- Failed image capture.
- AI unavailable.
- Invalid AI output.
- File write errors.
- Power interruption.

Behavior:

- AI communication is retried with exponential backoff before a failure is recorded.
- The AI endpoint is verified at startup; if unreachable, the application exits with a clear error.
- Failures must not crash the entire experiment. Each failure is recorded against its capture and the schedule continues.

# 18. Dataset Goal

The final dataset should contain:

- Camera evidence.
- AI decisions.
- Confidence values.
- Failure information.
- Human-reviewable images.

The result should be a reliable unattended rainfall observation system.
