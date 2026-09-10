import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    settings = Settings(data_dir=tmp_path / "data", mock_transcription=True)
    return TestClient(create_app(settings))


def test_upload_transcribe_and_export(tmp_path: Path):
    with make_client(tmp_path) as client:
        response = client.post(
            "/api/jobs",
            files={"file": ("meeting.wav", b"RIFF-test", "audio/wav")},
        )
        assert response.status_code == 200
        job_id = response.json()["job_id"]

        response = client.post(f"/api/jobs/{job_id}/transcribe")
        assert response.status_code == 200

        job = {}
        for _ in range(20):
            job = client.get(f"/api/jobs/{job_id}").json()
            if job["status"] == "completed":
                break
            time.sleep(0.05)
        assert job["transcript_available"] is True

        transcript = client.get(f"/api/jobs/{job_id}/transcript").json()
        assert transcript["segments"][0]["speaker"] == "Speaker 0"
        exported = client.get(f"/api/jobs/{job_id}/export/srt")
        assert exported.status_code == 200
        assert "Speaker 1" in exported.text


def test_rejects_unsupported_extension(tmp_path: Path):
    with make_client(tmp_path) as client:
        response = client.post("/api/jobs", files={"file": ("notes.pdf", b"x", "application/pdf")})
        assert response.status_code == 415


def test_accepts_aac_extension(tmp_path: Path):
    with make_client(tmp_path) as client:
        response = client.post(
            "/api/jobs",
            files={"file": ("meeting.aac", b"aac-test", "audio/aac")},
        )
        assert response.status_code == 200
        assert response.json()["filename"] == "meeting.aac"
