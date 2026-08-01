# AI-Powered Rain Logger

An unattended AI-powered rain monitoring system written in Python.

It uses a fixed outdoor USB webcam and a vision-language model to detect active
rainfall, classify its intensity, and build a human-reviewable scientific
observation dataset — all without human intervention.

## How it works

Every 30 minutes the system:

1. Turns on the camera LED and waits 5 seconds.
2. Captures **3 photographs** (~1 second apart), playing a short shutter sound after each.
3. Stitches them horizontally with visible black separators so the model can compare frames.
4. Sends the stitched image to a vision-language model (Qwen3-VL 4B) via any OpenAI-compatible endpoint.
5. Parses and validates the model's structured output.
6. Draws an annotated overlay onto the stitched image.
7. Stores the result as a row in a CSV database plus raw + annotated PNG images.

Because three frames are compared, the model distinguishes *active precipitation*
(rain streaks, splashes, changing visibility) from wet surfaces, puddles, clouds,
and other static cues.

## Features

- Drift-free scheduling — capture times are computed as `start + n × interval`, so AI/camera delays never push the schedule.
- Power-loss recovery — on startup, missing scheduled slots are backfilled as `POWER_OFF`.
- Any OpenAI-compatible AI backend — llama.cpp `llama-server` locally, or a cloud provider (OpenAI, Groq, Together, OpenRouter, Mistral, Fireworks, DeepSeek) or any custom URL.
- Structured, validated AI output with confidence values.
- Human-reviewable annotations (bold serif, white with black stroke, auto-wrapped).
- Robust failure handling — a camera/AI/validation failure is logged against its capture and the schedule continues.
- `--dry-run` to test the full pipeline in the terminal without writing any files.
- ASCII previews (`--debug-preview`) of captured and stitched images.

## Requirements

- Python 3.10+
- A USB webcam (device path `/dev/video0` by default)
- Audio output for the shutter sound (`aplay` or `paplay`)
- For the default backend: a running [`llama.cpp`](https://github.com/ggml-org/llama.cpp) `llama-server` with a Qwen3-VL 4B GGUF model (or an account/API key for a cloud provider)

## Installation

```bash
pip install -r requirements.txt
```

`requirements.txt`:

- `opencv-python` — camera capture and image processing
- `Pillow` — annotation overlay
- `PyYAML` — configuration
- `requests` — AI HTTP communication

## Configuration

All settings live in `config.yaml` (fully commented) in the project root. Every
field is optional; omitted fields fall back to defaults. Run
`python main.py --help` to see a summary.

Key settings:

| Section | Setting | Purpose |
|---|---|---|
| `schedule` | `interval_minutes`, `start_at`, `stop_at` | Capture interval and local-time window (empty start = now, empty stop = run forever) |
| `ai` | `provider`, `base_url`, `api_key_env`, `model` | AI backend: `llama-cpp`, a built-in provider, or `custom` + URL; API key read from an env var |
| `ai` | `max_tokens`, `timeout_seconds`, `retry_attempts`, `backoff_*` | AI request limits and retry policy |
| `camera` | `device_index`, `width`, `height` | OpenCV camera index and resolution |
| `sound` | `enabled`, `volume`, `playback_command` | Shutter sound control |
| `paths` | `system_message`, `csv_file`, `images/`, `log_file` | File and directory locations |

### AI backends

```yaml
# Local llama.cpp (default — no API key)
ai:
  provider: llama-cpp
  model: qwen3-vl-4b

# Cloud provider with a built-in base URL
ai:
  provider: groq
  api_key_env: GROQ_API_KEY
  model: qwen3-vl-4b

# Any OpenAI-compatible endpoint
ai:
  provider: custom
  base_url: "https://your-provider.example/v1"
  api_key_env: MY_API_KEY
  model: some-vision-model
```

The system prompt is loaded from `assets/system-message.md` and is never
hardcoded in Python. Edit that file to change how the model behaves.

## Usage

Start `llama-server` (if using the local backend):

```bash
llama-server -m qwen3-vl-4b-instruct-Q4_K_M.gguf --port 8080
```

Run the scheduled experiment:

```bash
python main.py
```

With explicit scheduling (overrides `config.yaml`):

```bash
python main.py --start-at "2026-08-02 00:00:00" --stop-at "2026-08-09 00:00:00"
```

Test the whole pipeline once, printing results to the terminal and writing **no files**:

```bash
python main.py --dry-run
```

Show ASCII previews of the captured, stitched, and annotated images:

```bash
python main.py --debug-preview
```

Use `Ctrl+C` to stop; the schedule is caught up on the next start.

## Output

### Database — `Database/rain_log.csv`

| Column | Description |
|---|---|
| `timestamp` | Scheduled capture time (local, `YYYY-MM-DD HH:MM:SS`) |
| `status` | `VALID`, `POWER_OFF`, `CAMERA_FAILURE`, `AI_FAILURE`, `INVALID_OUTPUT` |
| `rain_type` | `None`, `Drizzle`, `Light`, `Moderate`, `Heavy`, `Unknown` |
| `rain_confidence` | Confidence it is raining (50.0–100.0%) |
| `rain_type_confidence` | Confidence in the type classification (50.0–100.0%) |
| `message` | Optional model observation |
| `warnings` | Optional factors reducing confidence |
| `image_path` | Annotated image (relative path) |
| `raw_image_path` | Raw stitched image (relative path) |

### Images — `Database/images/`

```
Database/
├── rain_log.csv
└── images/
    ├── raw/        # stitched, unannotated
    └── annotated/  # with AI results overlaid
```

Files are named from the scheduled capture time, e.g.
`12th July 2026 11:30 AM.png`.

### Runtime log — `logs/system.log`

Separate from the database; records scheduled captures, camera/AI events,
stitching, saving, database updates, and errors.

## Power-loss recovery

On startup the system reads the existing CSV, finds the last recorded slot, and
adds a `POWER_OFF` row for every scheduled slot between then and now. Missing
data is never interpreted as "no rainfall."

## Project structure

```
.
├── main.py               # CLI, scheduling, capture orchestration, dry-run
├── config.py             # YAML config loader
├── config.yaml           # all settings (commented)
├── requirements.txt
├── ai/
│   ├── qwen.py           # OpenAI-compatible client, providers, retry
│   └── parser.py         # validates/parses model output (ignores thinking)
├── camera/
│   └── camera.py         # 3-shot capture sequence, LED control
├── processing/
│   ├── stitch.py         # horizontal stitch with separators
│   └── overlay.py        # text annotation
├── storage/
│   └── csv_logger.py     # CSV append + POWER_OFF backfill
├── sound/
│   └── playback.py       # WAV shutter sound
├── utils/
│   ├── format.py         # timestamp / filename formatting
│   └── preview.py        # ASCII previews
└── assets/
    ├── system-message.md # AI system prompt
    └── camera_snap.wav   # shutter sound
```

## Credits

Coded by **opencode** (an AI coding assistant), per the project's
specification in `requirements.md`.
