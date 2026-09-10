from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from .config import Settings


class TranscriptionError(RuntimeError):
    pass


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _text_from(item: dict[str, Any]) -> str:
    return str(item.get("sentence") or item.get("text") or "").strip()


class FunASRTranscriber:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model: Any = None
        self._lock = threading.Lock()

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            try:
                from funasr import AutoModel
            except ImportError as exc:
                raise TranscriptionError(
                    "未安装 FunASR。请运行 `python -m pip install -r requirements.txt`，"
                    "或在 .env 中临时设置 MOCK_TRANSCRIPTION=true 验收界面。"
                ) from exc

            try:
                if self.settings.funasr_device.startswith("cuda"):
                    try:
                        import torch
                    except ImportError as exc:
                        raise TranscriptionError(
                            "当前配置要求 CUDA，但当前 Python 环境没有安装 PyTorch。"
                        ) from exc
                    if not torch.cuda.is_available():
                        raise TranscriptionError(
                            f"当前配置要求 {self.settings.funasr_device}，"
                            "但当前 Python 环境检测不到可用 CUDA。"
                        )
                self._model = AutoModel(
                    model=self.settings.funasr_model,
                    vad_model=self.settings.funasr_vad_model,
                    vad_kwargs={
                        "max_single_segment_time": self.settings.vad_max_single_segment_time_ms
                    },
                    punc_model=self.settings.funasr_punc_model,
                    spk_model=self.settings.funasr_spk_model,
                    device=self.settings.funasr_device,
                    disable_update=True,
                )
            except Exception as exc:
                raise TranscriptionError(f"FunASR 模型初始化失败：{exc}") from exc
        return self._model

    def transcribe(self, audio_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        model = self._get_model()
        try:
            try:
                results = model.generate(
                    input=str(audio_path),
                    batch_size_s=self.settings.funasr_batch_size_s,
                    sentence_timestamp=True,
                )
            except TypeError:
                results = model.generate(
                    input=str(audio_path), batch_size_s=self.settings.funasr_batch_size_s
                )
        except Exception as exc:
            raise TranscriptionError(f"FunASR 转写失败：{exc}") from exc

        segments: list[dict[str, Any]] = []
        for result in results or []:
            if not isinstance(result, dict):
                continue
            sentence_info = result.get("sentence_info") or []
            if sentence_info:
                for item in sentence_info:
                    if not isinstance(item, dict):
                        continue
                    text = _text_from(item)
                    if not text:
                        continue
                    start_ms = _as_int(item.get("start"), 0)
                    end_ms = _as_int(item.get("end"), start_ms)
                    if end_ms < start_ms:
                        end_ms = start_ms
                    speaker_id = item.get("spk", item.get("speaker", 0))
                    segments.append(
                        {
                            "start_ms": start_ms,
                            "end_ms": end_ms,
                            "speaker": f"Speaker {speaker_id}",
                            "text": text,
                        }
                    )
                continue

            text = _text_from(result)
            if not text:
                continue
            timestamps = result.get("timestamp") or []
            start_ms = _as_int(result.get("start"), 0)
            end_ms = _as_int(result.get("end"), start_ms)
            if timestamps and isinstance(timestamps, list):
                try:
                    start_ms = _as_int(timestamps[0][0], start_ms)
                    end_ms = _as_int(timestamps[-1][1], end_ms)
                except (IndexError, TypeError):
                    pass
            segments.append(
                {
                    "start_ms": start_ms,
                    "end_ms": max(start_ms, end_ms),
                    "speaker": "Speaker 0",
                    "text": text,
                }
            )

        engine = {
            "backend": "funasr",
            "asr_model": self.settings.funasr_model,
            "vad_model": self.settings.funasr_vad_model,
            "punc_model": self.settings.funasr_punc_model,
            "spk_model": self.settings.funasr_spk_model,
            "device": self.settings.funasr_device,
        }
        return segments, engine


class MockTranscriber:
    def transcribe(self, audio_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        return [
            {
                "start_ms": 0,
                "end_ms": 2600,
                "speaker": "Speaker 0",
                "text": "大家好，今天我们开始本次项目例会。",
            },
            {
                "start_ms": 3000,
                "end_ms": 6800,
                "speaker": "Speaker 1",
                "text": "本周的核心功能已经完成，测试环境预计明天可以交付。",
            },
            {
                "start_ms": 7200,
                "end_ms": 9800,
                "speaker": "Speaker 0",
                "text": "好的，请把风险项和负责人一起更新到项目看板。",
            },
        ], {"backend": "mock", "asr_model": "mock"}
