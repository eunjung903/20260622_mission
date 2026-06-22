import asyncio
from typing import Any

from google import genai
from google.genai import types

from app.config import get_settings

REPORT_BODY_PROMPT = """키워드 '{keyword}'에 대해 Google 검색을 통해 최근 2일 이내 뉴스 기사를 찾아 분석하세요.

아래 형식의 1, 2번 섹션만 한국어 마크다운으로 작성하세요. 3번 섹션(기사 출처)은 작성하지 마세요.

# '{keyword}' 뉴스 보고서

## 1. 3줄 요약
- 반드시 정확히 3줄만 작성 (4줄 이상 절대 금지)
- 각 줄은 50자 이내의 짧은 한 문장
- 불릿(-), 번호, 마크다운 기호 없이 줄바꿈으로만 구분
- 예시 형식:
첫 번째 핵심 요약 문장.
두 번째 핵심 요약 문장.
세 번째 핵심 요약 문장.

## 2. 상세 내용
(수집한 기사를 종합한 상세 분석. 단락과 불릿 포인트를 활용)
"""


async def search_and_generate_report(keyword: str) -> tuple[str, list[dict[str, Any]]]:
    """Gemini + Google Search 그라운딩으로 뉴스 검색 및 보고서를 생성합니다."""
    settings = get_settings()

    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY 환경 변수를 설정해 주세요.")

    client = genai.Client(api_key=settings.gemini_api_key)
    prompt = REPORT_BODY_PROMPT.format(keyword=keyword)

    def _call() -> Any:
        try:
            return client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.7,
                ),
            )
        except Exception as exc:
            message = str(exc)
            if "404" in message and "no longer available" in message:
                raise ValueError(
                    f"모델 '{settings.gemini_model}'을(를) 사용할 수 없습니다. "
                    "GEMINI_MODEL을 gemini-2.5-flash로 변경해 주세요."
                ) from exc
            if "401" in message or "403" in message or "API key" in message:
                raise ValueError(
                    "Gemini API 키가 유효하지 않습니다. "
                    "Google AI Studio에서 키를 확인해 주세요."
                ) from exc
            raise

    response = await asyncio.to_thread(_call)
    articles = _extract_articles(response)
    body = (response.text or "").strip()

    if not body:
        raise ValueError("Gemini가 보고서를 생성하지 못했습니다.")

    body = _normalize_summary(body)
    report = body + _build_source_section(articles)
    return report, articles


def _normalize_summary(report: str) -> str:
    """3줄 요약 섹션을 정확히 3줄, 각 50자 이내로 정리합니다."""
    import re

    match = re.search(
        r"(## 1\. 3줄 요약\s*\n)(.*?)(\n## 2\.)",
        report,
        flags=re.DOTALL,
    )
    if not match:
        return report

    header, summary_block, next_section = match.groups()
    lines = [
        line.strip().lstrip("-•*0123456789. ").strip()
        for line in summary_block.strip().splitlines()
        if line.strip()
    ]

    if not lines:
        return report

    short_lines = []
    for line in lines:
        if len(line) > 50:
            line = line[:47].rstrip() + "..."
        short_lines.append(line)
        if len(short_lines) == 3:
            break

    while len(short_lines) < 3:
        short_lines.append("관련 추가 뉴스 동향이 확인되었습니다.")

    normalized = header + "\n".join(short_lines[:3]) + next_section
    return report[: match.start()] + normalized + report[match.end() :]


def _extract_articles(response: Any) -> list[dict[str, Any]]:
    """그라운딩 메타데이터에서 기사 출처를 추출합니다."""
    articles: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    if not response.candidates:
        return articles

    metadata = response.candidates[0].grounding_metadata
    if not metadata:
        return articles

    for chunk in metadata.grounding_chunks or []:
        web = getattr(chunk, "web", None)
        if not web:
            continue

        uri = getattr(web, "uri", "") or ""
        title = getattr(web, "title", "") or uri

        if uri and uri not in seen_urls:
            seen_urls.add(uri)
            articles.append(
                {
                    "title": title,
                    "link": uri,
                    "snippet": "",
                    "published": None,
                }
            )

    return articles


def _build_source_section(articles: list[dict[str, Any]]) -> str:
    """보고서 3번 섹션(기사 출처 링크)을 생성합니다."""
    lines = ["", "## 3. 기사 출처 링크", ""]

    if not articles:
        lines.append("- 참고 기사를 찾지 못했습니다.")
    else:
        for article in articles:
            title = article["title"]
            link = article["link"]
            lines.append(f"- [{title}]({link})")

    return "\n".join(lines)
