from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
import html
import json
import re

import streamlit as st
from openai import OpenAI


APP_TITLE = "먹을까 말까"
SEOUL_TZ = ZoneInfo("Asia/Seoul")

LIGHT_MENUS = [
    "요거트",
    "그릭요거트",
    "바나나",
    "사과",
    "과일",
    "견과류",
    "샐러드",
    "오이",
    "방울토마토",
    "구운 과자",
    "크래커",
    "곡물바",
]

HEAVY_MENUS = [
    "치킨",
    "피자",
    "햄버거",
    "떡볶이",
    "라면",
    "족발",
    "보쌈",
    "야식",
]

SWEET_MENUS = [
    "초콜릿",
    "초코",
    "케이크",
    "쿠키",
    "아이스크림",
    "도넛",
    "빵",
    "마카롱",
]

CRUNCHY_MENUS = [
    "감자칩",
    "과자",
    "나쵸",
    "팝콘",
]

FEELING_OPTIONS = ["배고픔", "스트레스", "입이 심심함", "보상심리", "지루함", "집중 안 됨"]


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🍽️",
    layout="centered",
)

st.markdown(
    """
    <style>
    .block-container {
        max-width: 760px;
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    .title {
        font-size: 2.3rem;
        font-weight: 800;
        margin-bottom: 0.25rem;
    }

    .sub {
        color: #6a6259;
        margin-bottom: 1rem;
    }

    .info-card {
        background: linear-gradient(135deg, #fff7ef 0%, #fff0df 100%);
        border: 1px solid #f3ddc2;
        border-radius: 18px;
        padding: 16px 18px;
        margin-bottom: 18px;
        line-height: 1.7;
    }

    .summary-card {
        background: #fff3e7;
        border: 1px solid #ffd4aa;
        border-radius: 16px;
        padding: 14px 16px;
        font-weight: 700;
        margin: 12px 0;
    }

    .result-card {
        background: #ffffff;
        border: 1px solid #ece4da;
        border-radius: 18px;
        padding: 18px;
        margin-top: 10px;
        box-shadow: 0 6px 18px rgba(63, 34, 6, 0.05);
        line-height: 1.8;
    }

    .alt-title {
        font-weight: 700;
        margin: 14px 0 10px;
    }

    .small-note {
        color: #776d62;
        font-size: 0.9rem;
        margin-top: 14px;
    }

    .badge {
        display: inline-block;
        padding: 7px 12px;
        border-radius: 999px;
        font-size: 0.86rem;
        font-weight: 700;
        margin-bottom: 12px;
    }

    .badge-ok {
        background: #e8f7ec;
        color: #1f7a3a;
    }

    .badge-mid {
        background: #fff4e5;
        color: #a35a00;
    }

    .badge-no {
        background: #fdeaea;
        color: #b42318;
    }

    .stButton > button,
    .stTextInput input,
    div[data-baseweb="select"] > div {
        border-radius: 12px;
    }

    .stButton > button {
        height: 3rem;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_client() -> OpenAI:
    api_key = st.secrets.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY가 설정되어 있지 않습니다.")
    return OpenAI(api_key=api_key)


def get_korea_hour() -> int:
    return datetime.now(SEOUL_TZ).hour


def normalize_menu(menu: str) -> str:
    return " ".join(menu.strip().split())


def clean_text(text: str) -> str:
    if not text:
        return ""

    value = str(text)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    value = value.replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", value).strip()


def clean_result(result: dict) -> dict:
    return {
        "summary": clean_text(result.get("summary", "")),
        "menu": clean_text(result.get("menu", "")),
        "psych": [clean_text(x) for x in result.get("psych", [])[:2]],
        "impact": [clean_text(x) for x in result.get("impact", [])[:2]],
        "alt": [clean_text(x) for x in result.get("alt", [])[:2]],
        "closing": clean_text(result.get("closing", "")),
    }


def contains_any(menu: str, keywords: list[str]) -> bool:
    menu_l = menu.lower()
    return any(keyword.lower() in menu_l for keyword in keywords)


def should_use_llm(menu: str) -> bool:
    known_keywords = LIGHT_MENUS + HEAVY_MENUS + SWEET_MENUS + CRUNCHY_MENUS
    return not contains_any(menu, known_keywords)


def get_badge(hour: int, menu: str) -> tuple[str, str]:
    if hour >= 23:
        return "지금은 가능한 한 가볍게", "badge-no"
    if contains_any(menu, HEAVY_MENUS):
        return "양 조절 추천", "badge-mid"
    return "지금 먹어도 무난해요", "badge-ok"


def fast_snack_analysis(menu: str, hour: int, feeling: str) -> dict:
    if contains_any(menu, SWEET_MENUS):
        psych_map = {
            "스트레스": ["당 충전으로 기분을 빨리 끌어올리고 싶은 마음이 보여요.", "복잡한 생각보다 즉각적인 위로가 필요한 타이밍이에요."],
            "입이 심심함": ["입이 허전해서 달달한 자극을 찾고 있어요.", "가볍게 기분 전환하고 싶은 쪽에 가까워 보여요."],
            "보상심리": ["오늘 하루 수고한 나에게 작은 보상을 주고 싶은 마음이에요.", "만족감을 빨리 얻고 싶은 상태로 보여요."],
            "배고픔": ["배를 채우기보다 달달한 만족감이 먼저인 상태예요.", "간단하고 확실한 맛을 원하고 있어요."],
            "지루함": ["심심함을 빠르게 끊어줄 자극을 찾고 있어요.", "잠깐의 재미가 필요한 순간이에요."],
            "집중 안 됨": ["머리가 지쳐서 달달한 리프레시를 찾고 있어요.", "짧게 환기하고 다시 돌아오고 싶은 흐름이에요."],
        }
        impact = ["기분 전환은 빠르지만 금방 또 당길 수 있어요.", "늦은 시간에는 양을 줄이는 편이 좋아요."]
        alt = ["그릭요거트", "바나나"]
    elif contains_any(menu, CRUNCHY_MENUS):
        psych_map = {
            "스트레스": ["바삭한 식감으로 답답함을 풀고 싶은 마음이 보여요.", "씹는 감각으로 긴장을 털어내고 싶어 보여요."],
            "입이 심심함": ["입이 심심해서 손이 계속 가는 간식을 찾고 있어요.", "강한 포만감보다 계속 집어먹는 재미가 필요한 상태예요."],
            "보상심리": ["가볍고 편한 보상을 찾는 흐름이에요.", "복잡하지 않게 만족감을 얻고 싶어 보여요."],
            "배고픔": ["배를 꽉 채우기보다 간단하게 허기를 눌러두고 싶은 상태예요.", "한 끼보다는 군것질 쪽에 가까워요."],
            "지루함": ["심심해서 손이 계속 가는 패턴으로 보여요.", "시간 때우기용 간식일 가능성이 커요."],
            "집중 안 됨": ["머리를 깨우는 자극이 필요한 상태예요.", "잠깐 환기용으로 찾는 흐름에 가까워요."],
        }
        impact = ["먹기 시작하면 양 조절이 어려울 수 있어요.", "조금만 먹어도 짠맛 때문에 더 당길 수 있어요."]
        alt = ["구운 과자", "견과류"]
    elif contains_any(menu, HEAVY_MENUS):
        psych_map = {
            "스트레스": ["강한 맛으로 기분을 바꾸고 싶은 마음이 커 보여요.", "피곤함까지 한 번에 덮고 싶은 흐름이에요."],
            "입이 심심함": ["심심함보다는 확실한 자극을 원하고 있어요.", "가벼운 간식으로는 만족이 안 되는 상태예요."],
            "보상심리": ["오늘은 제대로 먹고 싶은 보상 모드에 가까워요.", "한 번에 만족하고 싶은 마음이 느껴져요."],
            "배고픔": ["실제로 허기가 꽤 쌓여 있는 상태일 수 있어요.", "간식보다는 식사에 가까운 메뉴를 찾고 있어요."],
            "지루함": ["지루함을 큰 자극으로 덮으려는 패턴일 수 있어요.", "먹는 행위 자체를 이벤트처럼 만들고 싶은 흐름이에요."],
            "집중 안 됨": ["집중이 안 돼서 강한 자극으로 전환하려는 상태예요.", "짧은 해결보다 큰 만족을 찾고 있어요."],
        }
        impact = ["만족감은 크지만 늦은 시간에는 부담이 커질 수 있어요.", "정말 배고픈 게 아니라면 먹고 난 뒤 무거울 수 있어요."]
        alt = ["샐러드", "방울토마토"]
    elif contains_any(menu, LIGHT_MENUS):
        psych_map = {
            "스트레스": ["지금은 부드럽고 안정적인 선택이 더 잘 맞아요.", "강한 자극보다 편안한 느낌을 원하는 상태예요."],
            "입이 심심함": ["가볍게 허전함만 달래고 싶은 흐름이에요.", "부담 없이 채우고 싶은 상태로 보여요."],
            "보상심리": ["무리하지 않는 선에서 나를 챙기고 싶은 마음이 보여요.", "자기 돌봄 쪽에 가까운 선택이에요."],
            "배고픔": ["허기를 가볍게 정리하고 싶은 상태예요.", "지금 시간에는 이 정도가 균형이 좋아요."],
            "지루함": ["심심함을 과하지 않게 넘기려는 선택이에요.", "정리된 루틴형 간식에 가까워 보여요."],
            "집중 안 됨": ["부담 없이 리프레시하고 싶은 상태예요.", "먹고 나서도 다시 돌아가기 쉬운 선택이에요."],
        }
        impact = ["지금 시간에도 비교적 부담이 적어요.", "먹고 난 뒤에도 컨디션이 무겁지 않을 가능성이 커요."]
        alt = ["그릭요거트", "과일"]
    else:
        psych_map = {
            "스트레스": ["지금은 뭔가로 분위기를 바꾸고 싶은 타이밍이에요.", "선택 자체보다 위로가 먼저 필요한 상태일 수 있어요."],
            "입이 심심함": ["배고픔보다는 입이 허전해서 메뉴가 떠오른 것 같아요.", "가볍게 만족하고 싶은 쪽에 가까워 보여요."],
            "보상심리": ["오늘 하루를 마무리하며 작은 보상을 주고 싶은 마음이 있어요.", "만족감이 중요한 선택으로 보여요."],
            "배고픔": ["허기를 달래고 싶은 마음이 가장 먼저예요.", "지금은 양보다 균형도 같이 보는 게 좋아요."],
            "지루함": ["심심함 때문에 메뉴가 떠오른 것일 수 있어요.", "짧은 환기가 필요한 타이밍이에요."],
            "집중 안 됨": ["집중력이 떨어져서 먹는 걸로 흐름을 바꾸고 싶은 상태예요.", "짧게 쉬고 다시 돌아가기 위한 선택일 수 있어요."],
        }
        impact = ["먹는 자체보다 왜 당기는지 먼저 보면 선택이 쉬워져요.", "늦은 시간엔 양을 반만 먹는 방식도 괜찮아요."]
        alt = ["과일", "그릭요거트"]

    psych = psych_map.get(feeling, psych_map["배고픔"])

    summary_map = {
        "배고픔": f"지금 {hour}시라면 허기를 달래되 너무 무겁지 않게 가는 편이 좋아요.",
        "스트레스": f"지금 {hour}시의 선택은 배보다 기분 회복이 더 큰 이유일 수 있어요.",
        "입이 심심함": f"지금 {hour}시라면 진짜 배고픔인지 먼저 한 번 분리해서 보는 게 좋아요.",
        "보상심리": f"지금 {hour}시에는 만족감은 챙기되 양을 조금만 줄여도 훨씬 편해요.",
        "지루함": f"지금 {hour}시의 간식은 허기보다 심심함 해소용에 가까워 보여요.",
        "집중 안 됨": f"지금 {hour}시라면 짧게 환기하고 돌아올 수 있는 메뉴가 더 잘 맞아요.",
    }

    return clean_result(
        {
            "summary": summary_map.get(feeling, f"지금 {hour}시에는 가볍게 조절하는 선택이 좋아 보여요."),
            "menu": f"선택한 메뉴: {menu}",
            "psych": psych,
            "impact": impact,
            "alt": alt,
            "closing": "완전히 참는 것보다 양을 줄이거나 더 가벼운 대안을 섞는 쪽이 오래 가요.",
        }
    )


def analyze_snack_with_llm(menu: str, hour: int, feeling: str) -> dict:
    client = get_client()

    system_prompt = """
너는 '먹을까 말까' 앱의 야식 코치다.

목표:
- 현재 시간과 사용자 상태를 보고 부드럽고 짧게 조언한다.
- 판단하지 말고, 왜 당기는지와 어떻게 가볍게 조절할지를 말한다.
- 반드시 JSON만 반환한다.

형식:
{
  "summary": "한 줄 요약",
  "menu": "선택한 메뉴: ...",
  "psych": ["문장 1", "문장 2"],
  "impact": ["문장 1", "문장 2"],
  "alt": ["대안 1", "대안 2"],
  "closing": "마무리 한 줄"
}
"""

    user_prompt = f"""
현재 상황
- 메뉴: {menu}
- 시간: {hour}시
- 상태: {feeling}
"""

    response = client.responses.create(
        model="gpt-4o-mini",
        max_output_tokens=220,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    raw = (response.output_text or "").strip()
    if not raw:
        raise ValueError("모델 응답이 비어 있습니다.")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return fast_snack_analysis(menu, hour, feeling)

    return clean_result(
        {
            "summary": data.get("summary", f"지금 {hour}시에는 가볍게 조절하는 선택이 좋아 보여요."),
            "menu": data.get("menu", f"선택한 메뉴: {menu}"),
            "psych": data.get("psych", ["왜 당기는지 먼저 보면 선택이 쉬워져요.", "완전히 참기보다 조금 덜 무겁게 가는 편이 좋아요."])[:2],
            "impact": data.get("impact", ["지금은 양 조절이 가장 중요해요.", "먹고 난 뒤 컨디션까지 같이 생각해보면 좋아요."])[:2],
            "alt": data.get("alt", ["그릭요거트", "과일"])[:2],
            "closing": data.get("closing", "완전히 참는 것보다 가볍게 조절하는 쪽이 오래 갑니다."),
        }
    )


def render_result(result: dict) -> None:
    result = clean_result(result)
    psych = result.get("psych", [])[:2]
    impact = result.get("impact", [])[:2]
    alt_items = result.get("alt", [])[:2]

    st.markdown(f'<div class="summary-card">{result["summary"]}</div>', unsafe_allow_html=True)
    st.markdown('<div class="result-card">', unsafe_allow_html=True)
    st.markdown(f"**{result['menu']}**")

    st.markdown("**왜 당기는지**")
    for item in psych:
        st.write(f"- {item}")

    st.markdown("**먹었을 때 포인트**")
    for item in impact:
        st.write(f"- {item}")

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('<div class="alt-title">대안 메뉴</div>', unsafe_allow_html=True)

    if alt_items:
        cols = st.columns(len(alt_items))
        for i, alt_menu in enumerate(alt_items):
            with cols[i]:
                if st.button(alt_menu, use_container_width=True, key=f"alt_{i}_{alt_menu}"):
                    st.session_state["selected_alt_menu"] = alt_menu
                    st.session_state["menu_input"] = alt_menu
                    st.session_state["auto_analyze"] = True
                    st.rerun()

    st.markdown(
        f'<div class="result-card" style="margin-top:10px;">{result["closing"]}</div>',
        unsafe_allow_html=True,
    )


if "selected_alt_menu" not in st.session_state:
    st.session_state["selected_alt_menu"] = ""
if "menu_input" not in st.session_state:
    st.session_state["menu_input"] = ""
if "auto_analyze" not in st.session_state:
    st.session_state["auto_analyze"] = False


st.markdown(f'<div class="title">{APP_TITLE} 🍽️</div>', unsafe_allow_html=True)
st.markdown('<div class="sub">지금 먹어도 괜찮은지, 더 가볍게 바꿀 수 있는지 빠르게 봐주는 간식 코치</div>', unsafe_allow_html=True)
st.markdown(
    """
    <div class="info-card">
    먹고 싶은 메뉴를 입력하면<br>
    지금 시간 기준으로 <b>왜 당기는지 / 먹으면 어떤 느낌일지 / 무엇으로 가볍게 바꿀지</b><br>
    짧고 현실적으로 정리해줍니다.
    </div>
    """,
    unsafe_allow_html=True,
)

if st.session_state["selected_alt_menu"]:
    st.session_state["menu_input"] = st.session_state["selected_alt_menu"]

menu = st.text_input(
    "먹고 싶은 메뉴",
    key="menu_input",
    placeholder="예: 떡볶이, 감자칩, 요거트, 라면",
)

feeling = st.selectbox("지금 상태", FEELING_OPTIONS)

use_current_time = st.checkbox("현재 시간 자동 사용", value=True)
if use_current_time:
    hour = get_korea_hour()
    st.write(f"현재 시각: **{hour}시**")
else:
    hour = st.slider("현재 시각을 선택하세요", 0, 23, 23)

analyze_button = st.button("분석하기", use_container_width=True)
auto_selected = st.session_state.get("auto_analyze", False)

if analyze_button or auto_selected:
    clean_menu = normalize_menu(menu or st.session_state["selected_alt_menu"])

    if not clean_menu:
        st.warning("메뉴를 먼저 입력해 주세요.")
    elif len(clean_menu) > 30:
        st.warning("메뉴명은 30자 이내로 입력해 주세요.")
    else:
        try:
            with st.spinner("지금 시간 기준으로 빠르게 보고 있어요..."):
                result = fast_snack_analysis(clean_menu, hour, feeling)
                if should_use_llm(clean_menu):
                    try:
                        result = analyze_snack_with_llm(clean_menu, hour, feeling)
                    except Exception:
                        pass

            badge_text, badge_class = get_badge(hour, clean_menu)

            st.markdown("---")
            st.markdown("## 분석 결과")
            st.markdown(f'<div class="badge {badge_class}">{badge_text}</div>', unsafe_allow_html=True)
            render_result(result)
            st.markdown(
                '<div class="small-note">안내: 이 앱은 일반적인 라이프스타일 코칭용 참고 정보이며, 의료적 진단이나 치료를 대체하지 않습니다.</div>',
                unsafe_allow_html=True,
            )

            st.session_state["selected_alt_menu"] = ""
            st.session_state["auto_analyze"] = False
        except Exception as error:
            st.error("분석 중 오류가 발생했습니다.")
            st.code(str(error))
