from pathlib import Path

from app.config import Settings
from app.llm import generate_summary
from app.models import Segment, Transcript


def test_long_transcript_is_summarized_without_dropping_the_tail(
    tmp_path: Path, monkeypatch
):
    import app.llm as llm

    submitted_prompts: list[str] = []

    class FakeResponse:
        is_error = False
        text = ""

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": "Partial summary"}}]}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, **kwargs):
            submitted_prompts.append(kwargs["json"]["messages"][1]["content"])
            return FakeResponse()

    monkeypatch.setattr(llm.httpx, "Client", FakeClient)
    transcript = Transcript(
        job_id="a" * 32,
        filename="long-meeting.wav",
        engine={"backend": "mock"},
        segments=[
            Segment(
                start_ms=index * 1_000,
                end_ms=(index + 1) * 1_000,
                speaker="Speaker 0",
                text=f"SEGMENT-{index}-START " + "甲" * 10_000 + f" SEGMENT-{index}-END",
            )
            for index in range(10)
        ],
        created_at="2026-01-01T00:00:00+00:00",
    )

    result = generate_summary(
        transcript,
        Settings(data_dir=tmp_path / "data", deepseek_api_key="test-key"),
    )

    combined_source = "\n".join(submitted_prompts)
    for index in range(10):
        assert f"SEGMENT-{index}-START" in combined_source
        assert f"SEGMENT-{index}-END" in combined_source
    assert sum(prompt.count("甲") for prompt in submitted_prompts) == 100_000
    assert len(submitted_prompts) > 1
    assert result == "Partial summary\n"
