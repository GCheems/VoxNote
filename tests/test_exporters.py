from app.exporters import transcript_to_json, transcript_to_markdown, transcript_to_srt, transcript_to_txt
from app.models import Segment, Transcript


def sample_transcript() -> Transcript:
    return Transcript(
        job_id="abc",
        filename="例会.wav",
        engine={"backend": "mock", "asr_model": "mock"},
        segments=[
            Segment(start_ms=0, end_ms=1250, speaker="Speaker 0", text="大家好。"),
            Segment(start_ms=1500, end_ms=3123, speaker="Speaker 1", text="开始吧。"),
        ],
        created_at="2026-01-01T00:00:00+00:00",
    )


def test_exports_keep_speaker_and_timestamp_information():
    transcript = sample_transcript()
    assert "Speaker 0" in transcript_to_markdown(transcript)
    assert "00:00:01.500" in transcript_to_txt(transcript)
    assert "00:00:01,500 --> 00:00:03,123" in transcript_to_srt(transcript)
    assert '"job_id": "abc"' in transcript_to_json(transcript)
