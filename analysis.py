"""채점 결과(DataFrame)를 이용한 성적 통계 계산."""

import pandas as pd


def analyze_scores(result: pd.DataFrame) -> dict:
    """채점 결과에서 평균/중앙값/표준편차/오답 TOP3를 계산한다."""
    if result.empty:
        raise ValueError("채점 결과가 비어 있습니다.")

    question_cols = [f"Q{i:02d}" for i in range(1, 46)]
    required_cols = ["학생명", "총점", *question_cols]
    missing = [col for col in required_cols if col not in result.columns]
    if missing:
        raise ValueError(f"채점 결과에 필요한 컬럼이 없습니다: {missing}")

    scores = pd.to_numeric(result["총점"], errors="raise")
    wrong_counts = (result[question_cols] == "X").sum()

    top3 = sorted(
        (
            {"문항": int(col[1:]), "오답 수": int(count)}
            for col, count in wrong_counts.items()
        ),
        key=lambda item: (-item["오답 수"], item["문항"]),
    )[:3]

    return {
        "학생 수": len(result),
        "평균": round(float(scores.mean()), 2),
        "중앙값": round(float(scores.median()), 2),
        "표준편차": round(float(scores.std(ddof=0)), 2),  # 모집단 표준편차
        "최다 오답 TOP3": top3,
    }
