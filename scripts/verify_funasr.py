from __future__ import annotations

import json
import math
import struct
import sys
import wave
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import Settings
from app.transcription import FunASRTranscriber


def create_probe_wav(path: Path) -> None:
    sample_rate = 16_000
    duration_seconds = 1
    frames = bytearray()
    for index in range(sample_rate * duration_seconds):
        value = int(500 * math.sin(2 * math.pi * 440 * index / sample_rate))
        frames.extend(struct.pack("<h", value))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(frames)


def main() -> None:
    settings = Settings.from_env()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    probe = settings.data_dir / ".funasr-model-check.wav"
    try:
        create_probe_wav(probe)
        segments, engine = FunASRTranscriber(settings).transcribe(probe)
        print(json.dumps({"ok": True, "engine": engine, "segments": segments}, ensure_ascii=False, indent=2))
    finally:
        probe.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
