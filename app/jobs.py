from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .audio import prepare_wav
from .config import Settings
from .llm import SummaryError, generate_summary
from .models import JobRecord, Segment, SummaryRequest, Transcript, utc_now
from .transcription import FunASRTranscriber, MockTranscriber, TranscriptionError


class JobNotFoundError(KeyError):
    pass


class JobService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir = self.settings.data_dir / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voxnote")
        self._transcriber = (
            MockTranscriber()
            if settings.mock_transcription or settings.transcriber_backend == "mock"
            else FunASRTranscriber(settings)
        )

    def _job_dir(self, job_id: str) -> Path:
        path = self.jobs_dir / job_id
        if not path.is_dir():
            raise JobNotFoundError(job_id)
        return path

    def _record_path(self, job_id: str) -> Path:
        return self._job_dir(job_id) / "job.json"

    @staticmethod
    def _write_json(path: Path, value: Any) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    def _read_record(self, job_id: str) -> JobRecord:
        try:
            return JobRecord.model_validate(json.loads(self._record_path(job_id).read_text("utf-8")))
        except FileNotFoundError as exc:
            raise JobNotFoundError(job_id) from exc

    def _save_record(self, record: JobRecord) -> JobRecord:
        record.updated_at = utc_now()
        self._write_json(self._record_path(record.job_id), record.model_dump())
        return record

    def create_job(self, filename: str, extension: str, upload_file) -> JobRecord:
        job_id = uuid.uuid4().hex
        job_dir = self.jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=False)
        original = job_dir / f"original{extension.lower()}"
        total = 0
        max_bytes = self.settings.max_upload_mb * 1024 * 1024
        try:
            with original.open("wb") as target:
                while True:
                    chunk = upload_file.file.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError(f"文件超过 {self.settings.max_upload_mb} MB 限制。")
                    target.write(chunk)
        except Exception:
            for child in job_dir.iterdir():
                child.unlink(missing_ok=True)
            job_dir.rmdir()
            raise

        now = utc_now()
        record = JobRecord(
            job_id=job_id,
            filename=filename,
            status="uploaded",
            progress=0,
            created_at=now,
            updated_at=now,
        )
        self._write_json(job_dir / "job.json", record.model_dump())
        return record

    def list_jobs(self) -> list[JobRecord]:
        records = []
        for path in self.jobs_dir.iterdir():
            if path.is_dir() and (path / "job.json").exists():
                try:
                    records.append(self._read_record(path.name))
                except (JobNotFoundError, ValueError):
                    continue
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def get_job(self, job_id: str) -> JobRecord:
        return self._read_record(job_id)

    def start_transcription(self, job_id: str) -> JobRecord:
        with self._lock:
            record = self._read_record(job_id)
            if record.status in {"transcribing", "summarizing"}:
                return record
            if record.status == "completed":
                return record
            record.status = "transcribing"
            record.progress = 5
            record.error = None
            self._save_record(record)
            self._executor.submit(self._run_transcription, job_id)
            return record

    def _run_transcription(self, job_id: str) -> None:
        try:
            record = self._read_record(job_id)
            job_dir = self._job_dir(job_id)
            original = next(job_dir.glob("original.*"))
            wav_path = job_dir / "normalized.wav"
            record.progress = 15
            self._save_record(record)
            if isinstance(self._transcriber, MockTranscriber):
                audio_path = original
            else:
                audio_path = prepare_wav(original, wav_path, self.settings.ffmpeg_binary)
            segments, engine = self._transcriber.transcribe(audio_path)
            transcript = Transcript(
                job_id=job_id,
                filename=record.filename,
                engine=engine,
                segments=[Segment.model_validate(segment) for segment in segments],
                created_at=utc_now(),
            )
            self._write_json(job_dir / "transcript.json", transcript.model_dump())
            wav_path.unlink(missing_ok=True)
            record.status = "completed"
            record.progress = 100
            record.transcript_available = True
            self._save_record(record)
        except (TranscriptionError, OSError, ValueError, StopIteration, RuntimeError) as exc:
            self._fail(job_id, str(exc))
        except Exception as exc:
            self._fail(job_id, f"未预期错误：{exc}")

    def _fail(self, job_id: str, error: str) -> None:
        try:
            record = self._read_record(job_id)
            record.status = "failed"
            record.progress = 0
            record.error = error
            self._save_record(record)
        except JobNotFoundError:
            pass

    def get_transcript(self, job_id: str) -> Transcript:
        path = self._job_dir(job_id) / "transcript.json"
        try:
            return Transcript.model_validate(json.loads(path.read_text("utf-8")))
        except FileNotFoundError as exc:
            raise ValueError("转写结果尚未生成。") from exc

    def start_summary(self, job_id: str, request: SummaryRequest) -> JobRecord:
        with self._lock:
            record = self._read_record(job_id)
            if not record.transcript_available:
                raise ValueError("请先完成转写，再生成会议纪要。")
            if record.status == "summarizing":
                return record
            record.status = "summarizing"
            record.progress = 10
            record.error = None
            self._save_record(record)
            self._executor.submit(self._run_summary, job_id, request)
            return record

    def _run_summary(self, job_id: str, request: SummaryRequest) -> None:
        try:
            transcript = self.get_transcript(job_id)
            summary = generate_summary(
                transcript,
                self.settings,
                api_key=request.api_key,
                base_url=request.base_url,
                model=request.model,
                language=request.language,
                extra_instruction=request.extra_instruction,
            )
            self._job_dir(job_id).joinpath("summary.md").write_text(summary, encoding="utf-8")
            record = self._read_record(job_id)
            record.status = "completed"
            record.progress = 100
            record.summary_available = True
            self._save_record(record)
        except (SummaryError, ValueError, OSError) as exc:
            self._fail(job_id, str(exc))

    def get_summary(self, job_id: str) -> str:
        try:
            return (self._job_dir(job_id) / "summary.md").read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ValueError("会议纪要尚未生成。") from exc
