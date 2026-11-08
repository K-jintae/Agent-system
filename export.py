"""성적 통계 및 학생별 채점 결과를 한 시트의 엑셀 파일로 만든다."""

from io import BytesIO

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def build_excel(result: pd.DataFrame, stats: dict) -> bytes:
    """Streamlit st.download_button의 data로 전달할 XLSX 바이트를 반환한다."""
    top3_text = ", ".join(
        f'{item["문항"]}번 ({item["오답 수"]}명)'
        for item in stats["최다 오답 TOP3"]
    )
    summary = pd.DataFrame(
        [
            ("학생 수", f'{stats["학생 수"]}명'),
            ("평균", f'{stats["평균"]:.2f}점'),
            ("중앙값", f'{stats["중앙값"]:.2f}점'),
            ("표준편차 (모집단)", f'{stats["표준편차"]:.2f}점'),
            ("최다 오답 문항 3개", top3_text),
        ],
        columns=["항목", "결과"],
    )

    buffer = BytesIO()
    sheet_name = "성적 결과"
    result_startrow = len(summary) + 4  # pandas의 startrow는 0부터 시작

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name=sheet_name, index=False, startrow=1)
        result.to_excel(
            writer,
            sheet_name=sheet_name,
            index=False,
            startrow=result_startrow,
        )

        ws = writer.sheets[sheet_name]
        # 학생 이름을 수식으로 해석하지 않고 업로드된 문자 그대로 저장한다.
        for row_number, name in enumerate(result["학생명"], result_startrow + 2):
            cell = ws.cell(row_number, 1, str(name))
            cell.data_type = "s"
        ws["A1"] = "영어 시험 성적 분석"
        ws["A1"].font = Font(size=16, bold=True)
        ws.sheet_view.showGridLines = False

        # 통계 헤더와 학생별 결과 헤더 꾸미기
        for row_number in (2, result_startrow + 1):
            for cell in ws[row_number][: (2 if row_number == 2 else len(result.columns))]:
                cell.fill = PatternFill("solid", fgColor="1E3A5F")
                cell.font = Font(color="FFFFFF", bold=True)
                cell.alignment = Alignment(horizontal="center")

        ws.column_dimensions["A"].width = 23
        ws.column_dimensions["B"].width = 31
        for col_index in range(3, len(result.columns) + 1):
            ws.column_dimensions[get_column_letter(col_index)].width = 8

        ws.freeze_panes = f"C{result_startrow + 2}"

    return buffer.getvalue()
