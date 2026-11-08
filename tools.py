
import json
import re

import pandas as pd
import pymupdf
from langchain_core.tools import tool


def extract_question_text(pdf_bytes: bytes, question_no: int) -> str:
    """업로드한 문제 PDF에서 지정된 문항의 원문을 추출한다."""

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            # 수능 문제지는 2단 구성이라 양쪽 열을 구분한다.
            columns = [[], []]
            middle = page.rect.width / 2

            for block in page.get_text("blocks"):
                if not isinstance(block[4], str):
                    continue

                x_center = (block[0] + block[2]) / 2
                column_idx = 0 if x_center < middle else 1
                columns[column_idx].append((block[1], block[4]))

            for blocks in columns:
                text = "\n".join(
                    content
                    for _, content in sorted(blocks)
                )

                # 문항 번호가 시작되는 위치 탐색
                matches = list(
                    re.finditer(
                        r"(?m)^[ \t]*(\d{1,2})\.[ \t]+",
                        text
                    )
                )

                for i, match in enumerate(matches):
                    number = int(match.group(1))

                    if number != question_no:
                        continue

                    end = (
                        matches[i + 1].start()
                        if i + 1 < len(matches)
                        else len(text)
                    )

                    return text[match.start():end].strip()[:2500]

    return ""


def build_tools(result: pd.DataFrame, question_pdf_bytes: bytes):
    """현재 채점 결과에 연결된 Agent 도구를 생성한다."""

    data = result.copy()
    scores = pd.to_numeric(data["총점"])
    question_cols = [f"Q{i:02d}" for i in range(1, 46)]

    # 오답 문항 집계: 오답 수 내림차순, 문항 번호 오름차순
    wrong_counts = sorted(
        [
            {
                "문항": i,
                "오답 수": int(data[f"Q{i:02d}"].eq("X").sum())
            }
            for i in range(1, 46)
        ],
        key=lambda item: (-item["오답 수"], item["문항"])
    )

    @tool
    def get_exam_statistics() -> str:
        """전체 학생의 평균, 중앙값, 표준편차, 인원, 최다 오답 3개를 조회한다."""

        info = {
            "학생 수": len(data),
            "평균": round(float(scores.mean()), 2),
            "중앙값": round(float(scores.median()), 2),
            "표준편차": round(float(scores.std(ddof=0)), 2),
            "최다 오답 TOP3": wrong_counts[:3]
        }

        return json.dumps(info, ensure_ascii=False)

    @tool
    def get_student_score(student_name: str) -> str:
        """특정 학생의 점수를 조회한다. 예: 900학생, 900번 학생."""

        def normalize(value):
            value = re.sub(r"\s+", "", str(value))
            match = re.fullmatch(r"(\d+)(?:번)?(?:학생)?", value)
            return str(int(match.group(1))) if match else value

        target = student_name.strip()
        row = data[data["학생명"].map(normalize) == normalize(target)]

        if row.empty:
            return f"{target}은(는) 업로드된 데이터에 없습니다."
        if len(row) > 1:
            return "동일한 학생 번호에 여러 학생이 있어 특정할 수 없습니다. 학생명을 확인해 주세요."

        student = row.iloc[0]
        wrong = int(student[question_cols].eq("X").sum())
        return json.dumps({"학생명": str(student["학생명"]),
                           "점수": int(student["총점"]), "오답 수": wrong}, ensure_ascii=False)

    @tool
    def get_lowest_student() -> str:
        """가장 낮은 점수를 받은 학생과 점수를 조회한다."""

        minimum = int(scores.min())

        students = data.loc[
            scores == minimum, "학생명"
        ].astype(str).tolist()

        info = {
            "최저 점수": minimum,
            "학생": students
        }

        return json.dumps(info, ensure_ascii=False)

    @tool
    def get_most_missed_question() -> str:
        """가장 많이 틀린 문항과 문제 PDF의 해당 원문을 조회한다."""

        top = wrong_counts[0]
        number = top["문항"]

        source = extract_question_text(
            question_pdf_bytes,
            number
        )

        info = {
            "문항 번호": number,
            "오답 학생 수": top["오답 수"],
            "원문 추출 성공": bool(source),
            "문항 원문": source if source else "추출 실패",
            "주의": "원문의 유형만 참고하고 새 문제를 창작할 것"
        }

        return json.dumps(info, ensure_ascii=False)

    return [
        get_exam_statistics,
        get_student_score,
        get_lowest_student,
        get_most_missed_question
    ]
