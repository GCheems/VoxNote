import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.transcription import FunASRTranscriber, TranscriptionError


def test_macos_arm64_lock_pins_mps_compatible_stack():
    root = Path(__file__).resolve().parents[1]
    lock = (root / "requirements-macos-arm64-py311.lock.txt").read_text(encoding="utf-8")

    assert "aarch64-apple-darwin" in lock.splitlines()[1]
    assert "funasr==1.4.16" in lock
    assert "torch==2.6.0" in lock
    assert "torchaudio==2.6.0" in lock
    assert "pytest==" not in lock
    assert lock.count("--hash=sha256:") > 100


def _settings():
    return Settings(data_dir=Path("data"), funasr_device="mps")


def _install_mocks(monkeypatch, *, available, auto_model):
    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            backends=SimpleNamespace(
                mps=SimpleNamespace(is_available=lambda: available, is_built=lambda: True)
            )
        ),
    )
    monkeypatch.setitem(sys.modules, "funasr", SimpleNamespace(AutoModel=auto_model))


def test_mps_transcription_checks_runtime_availability(monkeypatch):
    called = False

    def auto_model(**_kwargs):
        nonlocal called
        called = True
        return object()

    _install_mocks(monkeypatch, available=False, auto_model=auto_model)

    with pytest.raises(TranscriptionError, match="MPS 不可用"):
        FunASRTranscriber(_settings())._get_model()

    assert called is False


def test_mps_places_asr_on_gpu_and_pipeline_models_on_cpu(monkeypatch):
    captured = {}

    def auto_model(**kwargs):
        captured.update(kwargs)
        return object()

    _install_mocks(monkeypatch, available=True, auto_model=auto_model)
    FunASRTranscriber(_settings())._get_model()

    assert captured["device"] == "mps"
    assert captured["vad_kwargs"] == {"max_single_segment_time": 30000, "device": "cpu"}
    assert captured["punc_kwargs"] == {"device": "cpu"}
    assert captured["spk_kwargs"] == {"device": "cpu"}
