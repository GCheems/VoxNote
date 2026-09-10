from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .config import PROJECT_ROOT, SUPPORTED_EXTENSIONS, Settings
from .exporters import transcript_to_json, transcript_to_markdown, transcript_to_srt, transcript_to_txt
from .jobs import JobNotFoundError, JobService
from .models import JobRecord, SummaryRequest


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, JobNotFoundError):
        return HTTPException(status_code=404, detail="找不到该任务。")
    return HTTPException(status_code=400, detail=str(exc))


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    service = JobService(settings)
    app = FastAPI(title="VoxNote", version="0.1.0")
    app.state.settings = settings
    app.state.service = service
    app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "static"), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(PROJECT_ROOT / "static" / "index.html")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/config")
    def config() -> dict[str, str]:
        return {
            "llm_base_url": settings.llm_base_url,
            "llm_model": settings.llm_model,
            "transcriber_backend": "mock" if settings.mock_transcription else settings.transcriber_backend,
            "asr_model": settings.funasr_model,
            "vad_model": settings.funasr_vad_model,
            "punc_model": settings.funasr_punc_model,
            "spk_model": settings.funasr_spk_model,
        }

    @app.get("/api/jobs", response_model=list[JobRecord])
    def list_jobs() -> list[JobRecord]:
        return service.list_jobs()

    @app.post("/api/jobs", response_model=JobRecord)
    def upload_job(file: UploadFile = File(...)) -> JobRecord:
        filename = Path(file.filename or "meeting").name
        extension = Path(filename).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=415,
                detail=f"不支持的格式：{extension or '无扩展名'}。支持 aac、mp3、m4a、wav、mp4。",
            )
        try:
            return service.create_job(filename, extension, file)
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.get("/api/jobs/{job_id}", response_model=JobRecord)
    def get_job(job_id: str) -> JobRecord:
        try:
            return service.get_job(job_id)
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.post("/api/jobs/{job_id}/transcribe", response_model=JobRecord)
    def transcribe_job(job_id: str) -> JobRecord:
        try:
            return service.start_transcription(job_id)
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.get("/api/jobs/{job_id}/transcript")
    def get_transcript(job_id: str):
        try:
            return service.get_transcript(job_id)
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.post("/api/jobs/{job_id}/summary", response_model=JobRecord)
    def summarize_job(job_id: str, request: SummaryRequest) -> JobRecord:
        try:
            return service.start_summary(job_id, request)
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.get("/api/jobs/{job_id}/summary")
    def get_summary(job_id: str) -> Response:
        try:
            return Response(service.get_summary(job_id), media_type="text/markdown; charset=utf-8")
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.get("/api/jobs/{job_id}/export/{file_format}")
    def export_job(job_id: str, file_format: str) -> Response:
        if file_format not in {"md", "txt", "json", "srt"}:
            raise HTTPException(status_code=404, detail="不支持的导出格式。")
        try:
            transcript = service.get_transcript(job_id)
        except Exception as exc:
            raise _http_error(exc) from exc
        if file_format == "md":
            content, media_type = transcript_to_markdown(transcript), "text/markdown; charset=utf-8"
        elif file_format == "txt":
            content, media_type = transcript_to_txt(transcript), "text/plain; charset=utf-8"
        elif file_format == "srt":
            content, media_type = transcript_to_srt(transcript), "application/x-subrip; charset=utf-8"
        else:
            content, media_type = transcript_to_json(transcript), "application/json; charset=utf-8"
        filename = f"{job_id}.{file_format}"
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return app


app = create_app()
