import time
from pathlib import Path
from threading import Event

import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
import app.jobs as job_module


def _wait_for_job(client: TestClient, job_id: str, expected_status: str) -> dict:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] == expected_status:
            return job
        time.sleep(0.025)
    raise AssertionError(f"job {job_id} did not reach {expected_status}")


def test_active_jobs_report_unknown_progress_until_they_finish(
    tmp_path: Path, monkeypatch
):
    transcription_started = Event()
    release_transcription = Event()

    original_transcribe = job_module.MockTranscriber.transcribe

    def blocking_transcribe(transcriber, audio_path):
        transcription_started.set()
        release_transcription.wait(timeout=3)
        return original_transcribe(transcriber, audio_path)

    monkeypatch.setattr(job_module.MockTranscriber, "transcribe", blocking_transcribe)
    settings = Settings(data_dir=tmp_path / "data", mock_transcription=True)
    with TestClient(create_app(settings)) as client:
        uploaded = client.post(
            "/api/jobs", files={"file": ("meeting.wav", b"RIFF-test", "audio/wav")}
        ).json()
        job_id = uploaded["job_id"]
        assert uploaded["progress"] == 0

        client.post(f"/api/jobs/{job_id}/transcribe")
        assert transcription_started.wait(timeout=1)
        assert client.get(f"/api/jobs/{job_id}").json()["progress"] is None

        release_transcription.set()
        completed = _wait_for_job(client, job_id, "completed")
        assert completed["progress"] == 100

        summary_started = Event()
        release_summary = Event()

        class FakeResponse:
            is_error = False
            text = ""

            @staticmethod
            def json():
                return {"choices": [{"message": {"content": "Meeting summary"}}]}

        class BlockingClient:
            def __init__(self, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def post(self, *args, **kwargs):
                summary_started.set()
                release_summary.wait(timeout=3)
                return FakeResponse()

        monkeypatch.setattr(httpx, "Client", BlockingClient)
        client.post(f"/api/jobs/{job_id}/summary", json={"api_key": "request-key"})
        assert summary_started.wait(timeout=1)
        assert client.get(f"/api/jobs/{job_id}").json()["progress"] is None

        release_summary.set()
        summarized = _wait_for_job(client, job_id, "completed")
        assert summarized["progress"] == 100
        assert summarized["summary_available"] is True
