from __future__ import annotations

import json
from typing import Any

from .models import Transcript, format_timestamp


def transcript_to_json(transcript: Transcript) -> str:
    return json.dumps(transcript.model_dump(), ensure_ascii=False, indent=2)


def transcript_to_markdown(transcript: Transcript) -> str:
    lines = [
        f"# 会议转写：{transcript.filename}",
        "",
        f"- 生成时间：{transcript.created_at}",
        f"- 引擎：{engine_label(transcript.engine)}",
        "",
        "## 逐句记录",
        "",
    ]
    for segment in transcript.segments:
        lines.append(
            f"- **{segment.start} – {segment.end} | {segment.speaker}**  "
            f"\n  {segment.text}"
        )
    return "\n".join(lines).rstrip() + "\n"


def transcript_to_txt(transcript: Transcript) -> str:
    lines = [f"会议转写：{transcript.filename}", ""]
    for segment in transcript.segments:
        lines.append(
            f"[{segment.start} - {segment.end}] {segment.speaker}: {segment.text}"
        )
    return "\n".join(lines).rstrip() + "\n"


def transcript_to_srt(transcript: Transcript) -> str:
    blocks = []
    for index, segment in enumerate(transcript.segments, start=1):
        start = format_timestamp(segment.start_ms, separator=",")
        end = format_timestamp(segment.end_ms, separator=",")
        blocks.append(f"{index}\n{start} --> {end}\n{segment.speaker}: {segment.text}")
    return "\n\n".join(blocks).rstrip() + ("\n" if blocks else "")


def engine_label(engine: dict[str, Any]) -> str:
    if engine.get("backend") == "mock":
        return "Mock（验收模式）"
    parts = [engine.get("asr_model"), engine.get("vad_model"), engine.get("punc_model")]
    if engine.get("spk_model"):
        parts.append(engine["spk_model"])
    return " + ".join(str(part) for part in parts if part)
