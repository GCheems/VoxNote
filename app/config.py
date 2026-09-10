from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # Keep module importable in the lightweight test environment.
    load_dotenv = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if load_dotenv is not None:
    load_dotenv(PROJECT_ROOT / ".env")


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_path(name: str, default: str) -> Path:
    raw = os.getenv(name, default)
    path = Path(raw).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    model_cache_dir: Path = PROJECT_ROOT / "model-cache"
    hf_cache_dir: Path = PROJECT_ROOT / "hf-cache"
    torch_cache_dir: Path = PROJECT_ROOT / "torch-cache"
    max_upload_mb: int = 2048
    ffmpeg_binary: str = "ffmpeg"
    transcriber_backend: str = "funasr"
    mock_transcription: bool = False
    funasr_device: str = "cpu"
    funasr_model: str = "paraformer-zh"
    funasr_vad_model: str = "fsmn-vad"
    funasr_punc_model: str = "ct-punc"
    funasr_spk_model: str = "cam++"
    funasr_batch_size_s: int = 300
    vad_max_single_segment_time_ms: int = 30000
    deepseek_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(
            data_dir=_env_path("VOXNOTE_DATA_DIR", "data"),
            model_cache_dir=_env_path("MODELSCOPE_CACHE", "model-cache"),
            hf_cache_dir=_env_path("HF_HOME", "hf-cache"),
            torch_cache_dir=_env_path("TORCH_HOME", "torch-cache"),
            max_upload_mb=int(os.getenv("VOXNOTE_MAX_UPLOAD_MB", "2048")),
            ffmpeg_binary=os.getenv("FFMPEG_BINARY", "ffmpeg"),
            transcriber_backend=os.getenv("TRANSCRIBER_BACKEND", "funasr").lower(),
            mock_transcription=_env_bool("MOCK_TRANSCRIPTION", False),
            funasr_device=os.getenv("FUNASR_DEVICE", "cpu"),
            funasr_model=os.getenv("FUNASR_MODEL", "paraformer-zh"),
            funasr_vad_model=os.getenv("FUNASR_VAD_MODEL", "fsmn-vad"),
            funasr_punc_model=os.getenv("FUNASR_PUNC_MODEL", "ct-punc"),
            funasr_spk_model=os.getenv("FUNASR_SPK_MODEL", "cam++"),
            funasr_batch_size_s=int(os.getenv("FUNASR_BATCH_SIZE_S", "300")),
            vad_max_single_segment_time_ms=int(
                os.getenv("VAD_MAX_SINGLE_SEGMENT_TIME_MS", "30000")
            ),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            llm_base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
            llm_model=os.getenv("LLM_MODEL", "deepseek-chat"),
        )
        # Set these before FunASR/ModelScope is imported so every model download
        # goes to the configured local drive instead of the user profile cache.
        os.environ["MODELSCOPE_CACHE"] = str(settings.model_cache_dir)
        os.environ["HF_HOME"] = str(settings.hf_cache_dir)
        os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(settings.hf_cache_dir / "hub"))
        os.environ["TORCH_HOME"] = str(settings.torch_cache_dir)
        return settings


SUPPORTED_EXTENSIONS = {".aac", ".mp3", ".m4a", ".wav", ".mp4"}
