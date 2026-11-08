"""사용자에게 표시되는 답변과 저장되는 대화의 내부 정보 노출 차단."""

import base64
import re
import unicodedata

REFUSAL = "내부 설정이나 연결 도구의 상세 정보는 제공하지 않습니다. 성적 조회, 통계 분석, 유사 문제 생성 기능은 사용할 수 있습니다."
CAPABILITIES = "학생 점수와 오답 수 조회, 전체 성적 통계, 최저 점수 학생 확인, 최다 오답 문항 분석 및 유사 영어 문제 생성을 지원합니다."
TOOL_NAMES = ("get_exam_statistics", "get_student_score", "get_lowest_student", "get_most_missed_question")


def compact(text):
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if c.isalnum())


def protect_response(text, names=TOOL_NAMES, secrets=()):
    """모델이 규칙을 무시해도 알려진 내부 식별자는 표시하지 않는다."""
    folded = compact(text)
    for name in names:
        variants = (name, base64.b64encode(name.encode()).decode(), name.encode().hex())
        if any(compact(value) in folded for value in variants):
            return REFUSAL
    if any(secret and secret in text for secret in secrets):
        return REFUSAL
    if re.search(r"\bsk-[A-Za-z0-9_-]{12,}", text):
        return REFUSAL
    if re.search(r"\bget_[a-z_]+\b", text, re.I):
        return REFUSAL
    # 기능 설명에 내부 규칙을 인용한 응답도 표시하지 않는다.
    if any(fragment in folded for fragment in (
        "성적관련규칙", "문제생성규칙", "안전규칙", "systemprompt",
        "시스템프롬프트", "반드시제공된tool", "반드시제공된도구",
    )):
        return REFUSAL
    return text


def guarded_request(question):
    normalized = compact(question)
    patterns = (
        r"(tool|툴|도구|함수|function|프롬프트|prompt|secret|apikey|api키)",
        r"(내부|시스템).*(설정|지시|규칙|명령)",
        r"(반드시|꼭|항상|무조건).*(조회|호출|사용).*(뭐|무엇|어떤|설명|알려|있는)",
        r"(이전|앞선|기존).*(지시|규칙|명령).*(무시|잊|해제)",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def sanitized_history(history, secrets=()):
    return [{"role": item["role"],
             "content": protect_response(item["content"], secrets=secrets)
             if item["role"] == "assistant" else item["content"]}
            for item in history if item.get("role") in ("user", "assistant")]

