from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class AudioConversionError(RuntimeError):
    pass


def _find_ffmpeg(ffmpeg_binary: str) -> str | None:
    system_binary = shutil.which(ffmpeg_binary)
    if system_binary:
        return system_binary
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError, OSError):
        return None


def prepare_wav(input_path: Path, output_path: Path, ffmpeg_binary: str) -> Path:
    """Convert compressed media to mono 16 kHz PCM WAV for FunASR."""
    if input_path.suffix.lower() == ".wav" and not shutil.which(ffmpeg_binary):
        return input_path

    ffmpeg_path = _find_ffmpeg(ffmpeg_binary)
    if ffmpeg_path is None:
        raise AudioConversionError(
            "未找到 ffmpeg。请安装系统 ffmpeg，或先执行 `python -m pip install imageio-ffmpeg`；WAV 文件可直接使用。"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg_path,
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-sample_fmt",
        "s16",
        str(output_path),
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=60 * 60 * 4,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "未知 ffmpeg 错误").strip()
        raise AudioConversionError(f"音频转换失败：{detail[-1200:]}")
    return output_path
