
import pymupdf
import pandas as pd
import re

def extract_answer_key(pdf_file):
    # 업로드한 PDF 열기
    doc = pymupdf.open(
        stream=pdf_file.getvalue(),
        filetype="pdf"
    )

    # PDF의 텍스트 추출
    text = "\n".join(page.get_text(sort=True) for page in doc)
    doc.close()

    # 문항번호, 정답, 배점 찾기
    pattern = r"(?<!\d)([1-9]|[1-3]\d|4[0-5])\s*([①②③④⑤])\s*([23])(?!\d)"
    matches = re.findall(pattern, text)

    answer_map = {
        "①": 1, "②": 2, "③": 3,
        "④": 4, "⑤": 5
    }

    answer_key = {}

    for number, answer, score in matches:
        entry = {
            "answer": answer_map[answer],
            "score": int(score)
        }
        if int(number) in answer_key and answer_key[int(number)] != entry:
            raise ValueError(f"{number}번 정답 또는 배점이 중복되어 서로 다릅니다.")
        answer_key[int(number)] = entry

    # 추출 결과 검증
    if len(answer_key) != 45:
        raise ValueError("45문항을 모두 추출하지 못했습니다.")

    if sum(v["score"] for v in answer_key.values()) != 100:
        raise ValueError("총 배점이 100점이 아닙니다.")

    return dict(sorted(answer_key.items()))


def grade_omr(omr_csv, answer_key):

    # 1. 학생 OMR 데이터 읽기
    omr_csv.seek(0)
    df = pd.read_csv(omr_csv, encoding="utf-8-sig", dtype={"학생명": str})

    # 2. 필요한 컬럼 확인
    question_cols = [f"Q{i:02d}" for i in range(1, 46)]
    required_cols = ["학생명"] + question_cols

    missing = [col for col in required_cols if col not in df.columns]

    if missing:
        raise ValueError(f"OMR 데이터에 없는 컬럼: {missing}")

    if df.empty:
        raise ValueError("OMR 데이터에 학생이 없습니다.")
    names = df["학생명"].fillna("").str.strip()
    if names.eq("").any() or names.duplicated().any():
        raise ValueError("학생명은 비어 있거나 중복될 수 없습니다.")
    df["학생명"] = names

    # 3. 학생별 결과 데이터 생성
    result = pd.DataFrame({"학생명": df["학생명"]})
    total_scores = pd.Series(0, index=df.index, dtype=int)

    # 4. 45개 문항 채점
    for number in range(1, 46):
        column = f"Q{number:02d}"

        correct_answer = answer_key[number]["answer"]
        point = answer_key[number]["score"]

        # 학생 응답을 숫자로 변환
        responses = pd.to_numeric(df[column], errors="coerce")
        # 빈칸과 0은 미응답으로 채점하되, 잘못된 입력은 숨기지 않는다.
        blank = df[column].isna() | df[column].astype(str).str.strip().eq("")
        invalid = ~blank & ~responses.isin([0, 1, 2, 3, 4, 5])
        if invalid.any():
            raise ValueError(f"{column}: 응답은 1~5, 미응답은 빈칸 또는 0이어야 합니다.")

        # 정답과 학생 응답 비교
        correct = responses == correct_answer

        # 정답 여부 기록
        result[column] = correct.map({True: "O", False: "X"})

        # 맞힌 문항의 배점만 추가
        total_scores += correct.astype(int) * point

    # 5. 총점을 두 번째 컬럼에 추가
    result.insert(1, "총점", total_scores)

    return result

