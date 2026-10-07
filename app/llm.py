from __future__ import annotations

import httpx

from .config import Settings
from .models import Transcript


class SummaryError(RuntimeError):
    pass


MAX_SUMMARY_INPUT_CHARS = 10_000
MAX_REDUCTION_ROUNDS = 8


def _endpoint(base_url: str) -> str:
    base_url = base_url.rstrip("/")
    return base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"


def _transcript_text(transcript: Transcript) -> str:
    return "\n".join(
        f"[{segment.start} - {segment.end}] {segment.speaker}: {segment.text}"
        for segment in transcript.segments
    )


def _split_text(text: str, max_chars: int = MAX_SUMMARY_INPUT_CHARS) -> list[str]:
    """Split text near line boundaries without discarding any characters."""
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    if not text:
        return [""]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            newline = text.rfind("\n", start, end)
            if newline > start + max_chars // 2:
                end = newline + 1
        chunks.append(text[start:end])
        start = end
    return chunks


def _request_completion(
    client: httpx.Client,
    endpoint: str,
    key: str,
    model: str,
    prompt: str,
) -> str:
    try:
        response = client.post(
            endpoint,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "temperature": 0.2,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一名严谨的会议纪要助手，只基于输入内容总结，不补充未出现的事实。",
                    },
                    {"role": "user", "content": prompt},
                ],
            },
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
    return content.strip()


def _required_sections(language_hint: str, extra_instruction: str) -> str:
    extra = extra_instruction.strip()
    return f"""请用{language_hint}整理会议内容，输出结构清晰的会议纪要。

请严格包含以下栏目：
1. 会议摘要
2. 关键讨论
3. 决策与结论
4. 待办事项（负责人、事项、截止时间；不确定时写“未明确”）
5. 风险与后续问题

不要编造输入中没有的信息。尽量保留说话人和时间戳作为引用线索。""" + (f"\n\n额外要求：\n{extra}" if extra else "")


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
    transcript_chunks = _split_text(_transcript_text(transcript))
    requirements = _required_sections(language_hint, extra_instruction)

    with httpx.Client(timeout=300) as client:
        if len(transcript_chunks) == 1:
            prompt = f"""{requirements}

会议转写：
{transcript_chunks[0]}"""
            return _request_completion(client, endpoint, key, selected_model, prompt) + "\n"

        # Map: summarize every source chunk. No source chunk is dropped, including
        # a single unusually long segment that had to be split in the middle.
        partials = []
        total = len(transcript_chunks)
        for index, chunk in enumerate(transcript_chunks, start=1):
            prompt = f"""{requirements}

以下是同一场会议转写的第 {index}/{total} 部分。请详细保留本部分独有的讨论、决定、待办、负责人、时间戳和风险；不要假设本部分包含整场会议。

转写片段：
{chunk}"""
            partials.append(_request_completion(client, endpoint, key, selected_model, prompt))

        # Reduce: combine partial minutes in bounded requests until they fit in
        # one final prompt. This also handles transcripts producing many chunks.
        for _ in range(MAX_REDUCTION_ROUNDS):
            combined = "\n\n".join(
                f"分段纪要 {index}:\n{partial}" for index, partial in enumerate(partials, start=1)
            )
            partial_chunks = _split_text(combined)
            if len(partial_chunks) == 1:
                final_prompt = f"""{requirements}

下面是同一场会议各部分的阶段性纪要。请整合成一份完整纪要，合并重复内容，保留每部分独有的信息；如果分段之间存在冲突，请明确标出，不要自行裁决。

阶段性纪要：
{partial_chunks[0]}"""
                return _request_completion(client, endpoint, key, selected_model, final_prompt) + "\n"

            partials = []
            for index, chunk in enumerate(partial_chunks, start=1):
                prompt = f"""请把以下同一场会议的阶段性纪要压缩整理为一份更精炼的阶段性纪要，保留所有独有决定、待办、负责人、截止时间和风险，不要把它当作整场会议的最终纪要。

{_required_sections(language_hint, extra_instruction)}

阶段性纪要片段 {index}/{len(partial_chunks)}：
{chunk}"""
                partials.append(_request_completion(client, endpoint, key, selected_model, prompt))

    raise SummaryError("长会议纪要仍无法合并；请缩短额外要求或改用上下文更大的模型后重试。")
