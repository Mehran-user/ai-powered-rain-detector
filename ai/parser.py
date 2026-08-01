import re
from dataclasses import dataclass

RAIN_TYPES = {"None", "Drizzle", "Light", "Moderate", "Heavy", "Unknown"}
_FIELD_PREFIXES = (
    "RainType",
    "RainConfidence",
    "RainTypeConfidence",
    "Message",
    "Warnings",
)
_CONFIDENCE_PATTERN = re.compile(r"^\d+\.\d$")
_THINK_BLOCKS = (
    (re.compile(r"<\|start_think\|>", re.IGNORECASE),
     re.compile(r"<\|end_think\|>", re.IGNORECASE)),
    (re.compile(r"<think>", re.IGNORECASE),
     re.compile(r"</think>", re.IGNORECASE)),
    (re.compile(r"\[think\]", re.IGNORECASE),
     re.compile(r"\[/think\]", re.IGNORECASE)),
)


def _strip_thinking(text):
    for open_pat, close_pat in _THINK_BLOCKS:
        while True:
            start = open_pat.search(text)
            if not start:
                break
            end = close_pat.search(text, start.end())
            if not end:
                break
            text = text[:start.start()] + text[end.end():]
    return text


class InvalidOutputError(Exception):
    pass


@dataclass
class AIResult:
    rain_type: str
    rain_confidence: float
    rain_type_confidence: float
    message: str
    warnings: str


def parse(text):
    if not text:
        raise InvalidOutputError("AI returned empty output.")
    fields = {}
    for raw_line in _strip_thinking(text).splitlines():
        stripped = raw_line.strip()
        for prefix in _FIELD_PREFIXES:
            if stripped.startswith(prefix + ":"):
                fields[prefix] = stripped[len(prefix) + 1:].strip()
                break

    rain_type = fields.get("RainType")
    if rain_type not in RAIN_TYPES:
        raise InvalidOutputError(
            f"Invalid RainType: {rain_type!r}. Must be one of "
            f"{sorted(RAIN_TYPES)}."
        )

    rain_confidence = _parse_confidence(
        fields.get("RainConfidence"), "RainConfidence"
    )
    rain_type_confidence = _parse_confidence(
        fields.get("RainTypeConfidence"), "RainTypeConfidence"
    )

    return AIResult(
        rain_type=rain_type,
        rain_confidence=rain_confidence,
        rain_type_confidence=rain_type_confidence,
        message=fields.get("Message", ""),
        warnings=fields.get("Warnings", ""),
    )


def _parse_confidence(value, name):
    if value is None:
        raise InvalidOutputError(f"Missing {name}.")
    raw = value.rstrip("%").strip()
    if not _CONFIDENCE_PATTERN.match(raw):
        raise InvalidOutputError(
            f"Invalid {name} format: {value!r}. Must be XX.X%."
        )
    number = float(raw)
    if not 50.0 <= number <= 100.0:
        raise InvalidOutputError(
            f"{name} {number} is outside the range 50.0-100.0%."
        )
    return number
