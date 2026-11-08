import hashlib
import os

import streamlit as st
from dotenv import load_dotenv

from agent import ask_agent, log_failure
from analysis import analyze_scores
from export import build_excel
from grading import extract_answer_key, grade_omr
from safety import sanitized_history, protect_response

load_dotenv()
st.set_page_config(page_title="영어 학원 평가 도우미", page_icon="📚", layout="wide")
st.session_state.setdefault("chat_history", [])

# 색상은 Streamlit 테마를 따라 밝은 화면과 어두운 화면에서 모두 읽힌다.
st.markdown("""
<style>
.stMainBlockContainer { max-width: 1100px; padding-top: 3rem; padding-bottom: 3rem; }
h1 { font-size: 2rem !important; font-weight: 700 !important; letter-spacing: -.045em; }
h2, h3 { letter-spacing: -.025em; }
h3 { font-size: 1.15rem !important; }
[data-testid="stSidebar"] { border-right: 1px solid rgba(128,140,160,.15); }
[data-testid="stSidebar"] h3 { font-size: 1rem !important; }
[data-testid="stMetric"] {
    padding: 1.1rem 1.25rem; border: 1px solid rgba(128,140,160,.22);
    border-radius: 12px; background: var(--secondary-background-color);
}
[data-testid="stMetricLabel"] { opacity: .7; }
[data-testid="stMetricValue"] { font-size: 1.8rem; font-weight: 650; letter-spacing: -.04em; }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 12px; }
[data-testid="stChatMessage"] {
    border-radius: 16px; padding: 1.15rem 1.3rem;
    border: 1px solid #dce4ed; margin-bottom: .65rem;
    background: #fff; color: #253449;
    box-shadow: 0 2px 8px rgba(30, 50, 75, .035);
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: #edf2f8; border-color: #d5dfeb;
    margin-left: clamp(0px, 4vw, 48px); border-top-right-radius: 5px;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    border-left: 3px solid #345272; border-top-left-radius: 5px;
}
[data-testid="stChatMessageAvatarUser"], [data-testid="stChatMessageAvatarAssistant"] {
    background: #345272; color: #fff;
}
[data-testid="stChatMessageContent"] p { line-height: 1.8; }
[data-testid="stChatInput"] {
    border: 1px solid #aabbd0; border-radius: 14px;
    box-shadow: 0 3px 14px rgba(30, 50, 75, .06);
}
[data-testid="stChatInput"]:focus-within {
    border-color: #345272; box-shadow: 0 0 0 3px rgba(52,82,114,.12);
}
[data-testid="stMetric"] { border-top: 3px solid #345272; }
.chat-heading {
    background: #2d4663; color: #fff; padding: 1.2rem 1.4rem;
    border-radius: 14px; margin: .4rem 0 1.2rem;
}
.chat-heading strong { display: block; font-size: 1.1rem; margin-bottom: .3rem; }
.chat-heading span { color: #d6e1ed; font-size: .85rem; line-height: 1.6; }
.export-ready {
    background: #edf8d9; border: 1px solid #c8dfa2; color: #35531b;
    border-radius: 11px; padding: .9rem 1rem; margin: .65rem 0;
}
.export-ready strong { font-size: .9rem; }
.export-ready small { display: block; margin-top: .25rem; color: #4b652e; line-height: 1.6; }
.stDownloadButton button:not(:disabled) {
    background: #e4f2cb; color: #35531b; border-color: #b5d28d;
}
.stDownloadButton button:not(:disabled):hover {
    background: #d7ebba; color: #294315; border-color: #87ad57;
}
[data-testid="stFileUploaderDropzone"] { border-radius: 10px; }
.stButton button, .stDownloadButton button { border-radius: 9px; font-weight: 600; min-height: 2.7rem; }
.brand-label { font-size: .72rem; letter-spacing: .16em; opacity: .6; margin-bottom: .65rem; font-weight: 600; }
.intro-copy { font-size: 1.05rem; line-height: 1.8; opacity: .75; max-width: 640px; margin: .5rem 0 1.8rem; }
.step-number { font-size: .75rem; font-weight: 700; opacity: .5; margin: .1rem 0 .7rem; }
@media (max-width: 640px) {
    .stMainBlockContainer { padding-top: 1.5rem; }
    h1 { font-size: 1.6rem !important; }
    [data-testid="stMetric"] { padding: .8rem; }
}
</style>
""", unsafe_allow_html=True)


def get_api_key():
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key
    try:
        return st.secrets.get("OPENAI_API_KEY", "")
    except FileNotFoundError:
        return ""


def file_signature(file):
    return hashlib.sha256(file.getvalue()).hexdigest() if file is not None else None


def clear_analysis():
    for key in ("grading_result", "score_stats", "excel_data"):
        st.session_state.pop(key, None)
    st.session_state["chat_history"] = []


def open_analysis():
    st.session_state["navigation"] = "데이터 분석"


with st.sidebar:
    st.markdown('<div class="brand-label">ACADEMY ASSISTANT</div>', unsafe_allow_html=True)
    st.subheader("영어 학원 평가 도우미")
    st.caption("채점부터 다음 수업 준비까지")
    st.divider()
    page = st.radio("페이지 이동", ["홈", "데이터 분석"], key="navigation")
    st.divider()
if page == "홈":
    st.markdown('<div class="brand-label">LESS GRADING, MORE TEACHING</div>', unsafe_allow_html=True)
    st.title("시험 분석을 간결하게,\n수업 준비를 가볍게.")
    st.markdown('<div class="intro-copy">시험 파일을 올리면 채점과 성적 분석을 한 번에.<br>학생들의 취약점을 확인하고, 다음 수업에 필요한 문제까지 준비하세요.</div>', unsafe_allow_html=True)
    st.button("성적 분석 시작하기 →", type="primary", on_click=open_analysis)
    st.divider()
    cards = st.columns(3, gap="medium")
    features = [
        ("01", "자동 채점", "문제지·정답지·OMR을 올려 학생별 점수와 정오 여부를 확인하세요."),
        ("02", "한눈에 보는 성적", "평균, 중앙값, 오답 문항을 살펴보고 엑셀로 내려받으세요."),
        ("03", "대화로 이어지는 분석", "학생 성적을 질문하고 취약 유형에 맞는 새 문제를 만들어 보세요."),
    ]
    for col, (number, title, description) in zip(cards, features):
        with col.container(border=True):
            st.markdown(f'<div class="step-number">{number}</div>', unsafe_allow_html=True)
            st.subheader(title)
            st.caption(description)
    st.caption("준비할 파일  ·  영어 문제지 PDF  /  정답지 PDF  /  학생 OMR CSV")
else:
    st.markdown('<div class="brand-label">EXAM OVERVIEW</div>', unsafe_allow_html=True)
    st.title("학생 성적 분석")
    st.caption("전체 결과를 살펴보고, 궁금한 내용은 아래 대화에서 확인하세요.")
    with st.sidebar:
        st.subheader("데이터 업로드")
        st.caption("파일 3개를 올린 뒤 분석을 시작하세요.")
        question_pdf = st.file_uploader("영어 문제지", type=["pdf"], key="question_pdf")
        answer_pdf = st.file_uploader("영어 정답지", type=["pdf"], key="answer_pdf")
        omr_csv = st.file_uploader("학생 OMR 데이터", type=["csv"], key="omr_csv")
        ready = all(file is not None for file in (question_pdf, answer_pdf, omr_csv))
        signature = tuple(file_signature(file) for file in (question_pdf, answer_pdf, omr_csv))
        if st.session_state.get("file_signature") != signature:
            clear_analysis()
            st.session_state["file_signature"] = signature
        st.caption(f"업로드 {sum(file is not None for file in (question_pdf, answer_pdf, omr_csv))} / 3")
        if st.button("분석 시작", disabled=not ready, type="primary", width="stretch"):
            clear_analysis()
            try:
                import pymupdf
                with pymupdf.open(stream=question_pdf.getvalue(), filetype="pdf") as doc:
                    if not len(doc) or not any(page.get_text().strip() for page in doc):
                        raise ValueError("문제지에서 텍스트를 읽을 수 없습니다. 텍스트 PDF를 업로드해 주세요.")
                result = grade_omr(omr_csv, extract_answer_key(answer_pdf))
                stats = analyze_scores(result)
                excel = build_excel(result, stats)
                st.session_state.update(grading_result=result, score_stats=stats, excel_data=excel)
                st.success("자동 채점 및 통계 분석 완료!")
            except Exception as exc:
                st.error(f"분석 오류: {exc}")
        analyzed = "grading_result" in st.session_state
        if analyzed:
            st.markdown('<div class="export-ready" role="status"><strong>✓ 엑셀 추출 준비 완료</strong><small>전체 통계와 학생별 채점 결과를<br>아래 버튼으로 내려받으세요.</small></div>', unsafe_allow_html=True)
        st.download_button("엑셀 추출", data=st.session_state.get("excel_data", b""),
                           file_name="성적분석_결과.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           disabled=not analyzed, width="stretch")

    if analyzed:
        stats = st.session_state["score_stats"]
        st.caption(f"분석 완료  ·  학생 {stats['학생 수']}명")
        cols = st.columns(3)
        for col, label in zip(cols, ("평균", "중앙값", "표준편차")):
            col.metric(label, f"{stats[label]}점")
        st.subheader("집중해서 살펴볼 문항")
        with st.container(border=True):
            for col, item in zip(st.columns(3), stats["최다 오답 TOP3"]):
                col.markdown(f"**{item['문항']}번 문항**")
                col.caption(f"{item['오답 수']}명 오답")
        with st.expander("학생별 채점 결과"):
            st.dataframe(st.session_state["grading_result"])

    st.divider()
    st.markdown('<div class="chat-heading"><strong>성적 분석 도우미</strong><span>학생 성적부터 다음 수업에 쓸 문제까지, 편하게 질문하세요.</span></div>', unsafe_allow_html=True)
    api_key = get_api_key()
    # 기존에 노출된 답변도 다시 표시하거나 모델에 전달하지 않는다.
    st.session_state["chat_history"] = sanitized_history(
        st.session_state["chat_history"], secrets=(api_key,))
    if not analyzed:
        st.info("채점이 완료되면 채팅을 사용할 수 있습니다.")
    elif not api_key:
        st.warning("OPENAI_API_KEY 설정이 필요합니다.")
    elif not st.session_state["chat_history"]:
        with st.container(border=True):
            st.markdown("**어떤 내용이 궁금하신가요?**")
            st.caption("이번 시험 평균과 중앙값은?  ·  가장 많이 틀린 문제와 비슷한 문제를 만들어 줘.")
    for message in st.session_state["chat_history"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    prompt = st.chat_input("성적에 관해 질문하세요.", disabled=not (analyzed and bool(api_key)))
    if prompt:
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("분석 중..."):
                try:
                    answer = ask_agent(prompt, st.session_state["grading_result"], question_pdf.getvalue(),
                                       st.session_state["chat_history"], api_key)
                except Exception as exc:
                    log_failure(exc)
                    answer = "AI 응답 중 오류가 발생했습니다. API 설정과 서버 상태를 확인해 주세요."
            answer = protect_response(answer, secrets=(api_key,))
            st.markdown(answer)
        st.session_state["chat_history"].extend([
            {"role": "user", "content": prompt}, {"role": "assistant", "content": answer}])

