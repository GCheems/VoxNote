from __future__ import annotations

from typing import Any

import httpx

from .config import Settings
from .models import Transcript


class SummaryError(RuntimeError):
    pass


def _endpoint(base_url: str) -> str:
    base_url = base_url.rstrip("/")
    return base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"


def _transcript_text(transcript: Transcript, max_chars: int = 80_000) -> str:
    lines = [
        f"[{segment.start} - {segment.end}] {segment.speaker}: {segment.text}"
        for segment in transcript.segments
    ]
    return "\n".join(lines)[:max_chars]


def generate_summary(
    transcript: Transcript,
    settings: Settings,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    language: str = "zh-CN",
    extra_instruction: str = "",
) -> str:
    key = (api_key or settings.deepseek_api_key).strip()
    if not key:
        raise SummaryError("未提供 API Key。请在页面中填写，或配置 DEEPSEEK_API_KEY。")

    endpoint = _endpoint((base_url or settings.llm_base_url).strip())
    selected_model = (model or settings.llm_model).strip()
    language_hint = "中文" if language.lower().startswith("zh") else language
    user_prompt = f"""请整理下面的会议转写，输出一份结构清晰的{language_hint}会议纪要。

请严格包含以下栏目：
1. 会议摘要
2. 关键讨论
3. 决策与结论
4. 待办事项（负责人、事项、截止时间；不确定时写“未明确”）
5. 风险与后续问题

不要编造转写中没有的信息。保留说话人和时间戳作为引用线索。
{extra_instruction.strip()}

会议转写：
{_transcript_text(transcript)}"""
    payload: dict[str, Any] = {
        "model": selected_model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": "你是一名严谨的中文会议纪要助手，只基于输入内容总结。",
            },
            {"role": "user", "content": user_prompt},
        ],
    }
    try:
        with httpx.Client(timeout=300) as client:
            response = client.post(
                endpoint,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise SummaryError(f"调用纪要 API 失败：{exc}") from exc

    if response.is_error:
        detail = response.text.strip()
        raise SummaryError(f"纪要 API 返回 HTTP {response.status_code}：{detail[:1000]}")
    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise SummaryError("纪要 API 返回格式不是 OpenAI 兼容的 chat/completions 格式。") from exc
    if not isinstance(content, str) or not content.strip():
        raise SummaryError("纪要 API 返回了空内容。")
    return content.strip() + "\n"
