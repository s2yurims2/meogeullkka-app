from datetime import datetime
from zoneinfo import ZoneInfo
import json
import re
import html

import streamlit as st
from openai import OpenAI

# -----------------------------
# 기본 설정
# -----------------------------
st.set_page_config(
    page_title="먹을까말까",
    page_icon="🍽️",
    layout="centered"
)

# -----------------------------
# 스타일
# -----------------------------
st.markdown("""
<style>
.block-container {
    max-width: 720px;
    padding-top: 2rem;
    padding-bottom: 2rem;
}

.title {
    font-size: 2.2rem;
    font-weight: 800;
    margin-bottom: 0.3rem;
}

.sub {
    color: #666666;
    font-size: 1rem;
    margin-bottom: 1rem;
}

.info-card {
    background: #fffaf5;
    border: 1px solid #f3e6d8;
    border-radius: 16px;
    padding: 16px 18px;
    margin-bottom: 18px;
}

.summary-card {
    background: #fff3e8;
    border: 1px solid #ffd7b0;
    border-radius: 14px;
    padding: 14px 16px;
    font-weight: 700;
    margin-top: 10px;
    margin-bottom: 12px;
}

.result-card {
    background: #ffffff;
    border: 1px solid #ece7e1;
    border-radius: 16px;
    padding: 18px;
    margin-top: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.03);
    line-height: 1.8;
}

.badge {
    display: inline-block;
    padding: 7px 12px;
    border-radius: 12px;
    font-size: 0.85rem;
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

.alt-title {
    font-weight: 700;
    margin-top: 10px;
    margin-bottom: 10px;
}

.small-note {
    color: #777777;
    font-size: 0.88rem;
    margin-top: 12px;
}

.section-title {
    font-weight: 700;
    margin-bottom: 6px;
}

.bullet-line {
    margin-bottom: 2px;
}

.stButton > button {
    border-radius: 12px;
    height: 3rem;
    font-weight: 700;
}

div[data-baseweb="select"] > div {
    border-radius: 12px;
}

.stTextInput input {
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# 세션 상태 초기화
# -----------------------------
if "selected_alt_menu" not in st.session_state:
    st.session_state["selected_alt_menu"] = ""

if "menu_input" not in st.session_state:
    st.session_state["menu_input"] = ""

if "auto_analyze" not in st.session_state:
    st.session_state["auto_analyze"] = False

# -----------------------------
# OpenAI
# -----------------------------
def get_client():
    api_key = st.secrets.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY가 .streamlit/secrets.toml에 없습니다.")
    return OpenAI(api_key=api_key)

# -----------------------------
# 유틸
# -----------------------------
def get_korea_hour() -> int:
    return datetime.now(ZoneInfo("Asia/Seoul")).hour

def normalize_menu(menu: str) -> str:
    return " ".join(menu.strip().split())

def clean_text(text: str) -> str:
    if not text:
        return ""

    text = str(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text

def clean_result(result: dict) -> dict:
    return {
        "summary": clean_text(result.get("summary", "")),
        "menu": clean_text(result.get("menu", "")),
        "psych": [clean_text(x) for x in result.get("psych", [])[:2]],
        "impact": [clean_text(x) for x in result.get("impact", [])[:2]],
        "alt": [clean_text(x) for x in result.get("alt", [])[:2]],
        "closing": clean_text(result.get("closing", "")),
    }

def should_use_llm(menu: str) -> bool:
    known_keywords = [
        "젤리", "초콜릿", "사탕", "감자칩", "과자", "스낵",
        "치킨", "피자", "햄버거", "라면", "떡볶이", "꽈배기",
        "도넛", "아이스크림", "케이크", "조각케익", "조각케이크",
        "요거트", "그릭요거트", "바나나", "견과류", "구운 과자",
        "샐러드", "닭가슴살", "두부", "계란", "과일", "따뜻한 차", "사과"
    ]
    return not any(keyword in menu for keyword in known_keywords)

def get_badge(hour: int, menu: str):
    heavy_keywords = ["치킨", "라면", "피자", "햄버거", "떡볶이"]
    if hour >= 23:
        return "지금은 미루기 추천", "badge-no"
    if any(keyword in menu for keyword in heavy_keywords):
        return "가볍게 바꾸기 추천", "badge-mid"
    return "먹어도 OK", "badge-ok"

# -----------------------------
# 빠른 분석
# -----------------------------
def fast_snack_analysis(menu: str, hour: int, feeling: str) -> dict:
    menu_l = menu.lower()

    if any(x in menu_l for x in ["젤리", "초콜릿", "사탕", "케이크", "도넛", "꽈배기", "아이스크림", "조각케익", "조각케이크"]):
        psych_map = {
            "스트레스": ["달달한 위안이 필요한 순간이에요 😮‍💨", "복잡한 생각보다 빠른 기분 전환을 찾는 흐름이에요"],
            "심심함": ["입이 심심해서 단맛이 더 당길 수 있어요 🙂", "가볍게 기분을 채우고 싶은 상태예요"],
            "보상심리": ["오늘 수고한 나를 달래고 싶은 마음이 보여요 ✨", "작은 보상으로 기분을 올리고 싶은 흐름이에요"],
            "배고픔": ["허기보다 빠른 에너지가 당기는 느낌이에요", "간단하고 익숙한 만족을 찾고 있어요"],
            "습관": ["늘 먹던 패턴이 이어진 걸 수 있어요", "시간대 습관이 단맛으로 연결된 느낌이에요"],
            "집중 안 됨": ["집중이 흐트러져서 당으로 리프레시하고 싶을 수 있어요", "짧게 기분 전환하고 싶은 상태예요"],
        }
        impact = ["기분은 금방 올라갈 수 있지만 금방 꺼질 수 있어요 🌙", "조금 무겁게 먹으면 나중에 더 처질 수 있어요"]
        alt = ["요거트", "바나나"]

    elif any(x in menu_l for x in ["감자칩", "과자", "스낵"]):
        psych_map = {
            "스트레스": ["바삭한 자극으로 답답함을 풀고 싶은 순간이에요 😮‍💨", "씹는 감각으로 긴장을 낮추고 싶은 흐름이에요"],
            "심심함": ["입이 심심해서 손이 가는 패턴일 수 있어요", "배고픔보다 심심함 해소에 가까워 보여요"],
            "보상심리": ["오늘의 피로를 간단히 보상받고 싶은 마음이에요", "수고한 하루 끝에 자극적인 맛이 당길 수 있어요"],
            "배고픔": ["허기를 빨리 채우고 싶은 느낌이 있어요", "간단하고 손쉬운 만족을 찾고 있어요"],
            "습관": ["습관적으로 집게 되는 간식 타이밍일 수 있어요", "시간대 루틴이 이어진 느낌이에요"],
            "집중 안 됨": ["머리 식히려고 바삭한 자극을 찾는 상태예요", "짧게 전환하고 싶은 마음이 보여요"],
        }
        impact = ["짠맛은 만족감이 빠르지만 더 손이 갈 수 있어요", "많이 먹으면 다음이 조금 무겁게 느껴질 수 있어요 🌙"]
        alt = ["견과류", "구운 과자"]

    elif any(x in menu_l for x in ["치킨", "피자", "햄버거"]):
        psych_map = {
            "스트레스": ["든든하고 강한 맛으로 확 풀고 싶은 순간이에요", "지친 마음을 크게 달래고 싶은 흐름이에요"],
            "심심함": ["심심함이 큰 메뉴로 번진 느낌일 수 있어요", "입 심심함보다 기분 전환 욕구가 더 커 보여요"],
            "보상심리": ["오늘은 제대로 보상받고 싶은 마음이 커 보여요 ✨", "한 끼처럼 만족하고 싶은 상태예요"],
            "배고픔": ["실제로 허기가 꽤 올라온 상태일 수 있어요", "든든한 만족을 찾고 있어요"],
            "습관": ["이 시간대에 익숙하게 찾는 메뉴일 수 있어요", "편한 선택으로 흘러간 느낌이에요"],
            "집중 안 됨": ["집중이 깨져서 확실한 만족을 찾는 상태예요", "작게보다 크게 리셋하고 싶은 흐름이에요"],
        }
        impact = ["지금은 든든하지만 나중엔 조금 무겁게 느껴질 수 있어요 🌙", "양이 많아지면 쉬는 시간까지 늘어질 수 있어요"]
        alt = ["샐러드", "닭가슴살"]

    elif any(x in menu_l for x in ["라면", "떡볶이"]):
        psych_map = {
            "스트레스": ["강한 맛으로 기분을 확 바꾸고 싶은 순간이에요 🔥", "지친 상태에서 자극적인 위안을 찾는 흐름이에요"],
            "심심함": ["심심함이 강한 맛 craving으로 이어진 느낌이에요", "입이 심심해서 자극을 찾는 상태예요"],
            "보상심리": ["오늘 하루 끝에 확실한 만족을 주고 싶은 마음이에요", "작고 깔끔한 보상보다 강한 보상을 원하는 흐름이에요"],
            "배고픔": ["허기가 꽤 올라와 따뜻하고 강한 음식이 끌릴 수 있어요", "빨리 채워지는 메뉴를 찾고 있어요"],
            "습관": ["습관적인 야식 패턴일 가능성이 있어요", "익숙한 만족으로 바로 가는 흐름이에요"],
            "집중 안 됨": ["집중이 안 돼서 강한 자극으로 깨우고 싶은 상태예요", "짧고 확실한 전환을 찾는 마음이에요"],
        }
        impact = ["먹는 순간 만족감은 크지만 조금 자극적으로 남을 수 있어요 🌙", "늦은 시간엔 몸이 쉬는 흐름과 살짝 엇갈릴 수 있어요"]
        alt = ["두부", "계란"]

    elif any(x in menu_l for x in ["요거트", "그릭요거트"]):
        psych_map = {
            "스트레스": ["지금은 조금 부드럽게 쉬고 싶은 상태예요 🙂", "자극보다 안정적인 선택이 잘 맞는 흐름이에요"],
            "심심함": ["가볍게 입 심심함을 달래고 싶은 마음이에요", "부담 없이 채우고 싶은 상태예요"],
            "보상심리": ["작지만 기분 좋은 보상을 찾는 흐름이에요 ✨", "가볍게 나를 챙기고 싶은 상태예요"],
            "배고픔": ["허기를 너무 무겁지 않게 다루고 싶은 순간이에요", "부드럽게 채우는 선택이 잘 맞아요"],
            "습관": ["익숙하게 손이 가는 편한 선택일 수 있어요", "과하지 않게 채우려는 흐름이에요"],
            "집중 안 됨": ["머리를 쉬게 하면서 가볍게 채우고 싶은 상태예요", "부담 적은 리프레시가 필요한 순간이에요"],
        }
        impact = ["지금 시간에도 비교적 편하게 느껴질 수 있어요 🌿", "과하지 않아서 흐름을 크게 깨지 않을 수 있어요"]
        alt = ["바나나", "과일"]

    elif any(x in menu_l for x in ["바나나", "과일", "사과"]):
        psych_map = {
            "스트레스": ["지금은 가볍고 편한 위안이 필요한 상태예요 🙂", "자극보다 부드러운 만족이 어울리는 흐름이에요"],
            "심심함": ["입이 심심한 상태를 가볍게 달래고 싶은 순간이에요", "작은 간식으로 충분할 수 있어요"],
            "보상심리": ["무겁지 않은 보상을 주고 싶은 마음이 보여요 ✨", "스스로를 가볍게 챙기고 싶은 상태예요"],
            "배고픔": ["허기를 크게 부담 없이 채우고 싶은 상태예요", "지금은 가벼운 쪽이 더 잘 맞아요"],
            "습관": ["편한 루틴으로 이어진 선택일 수 있어요", "과하지 않게 정리하고 싶은 흐름이에요"],
            "집중 안 됨": ["가볍게 전환하고 싶은 상태예요", "머리를 무겁게 하지 않는 쪽이 어울려요"],
        }
        impact = ["지금 시간에도 비교적 산뜻하게 느껴질 수 있어요 🌿", "무겁지 않아서 다음 흐름이 편할 수 있어요"]
        alt = ["요거트", "따뜻한 차"]

    elif any(x in menu_l for x in ["견과류"]):
        psych_map = {
            "스트레스": ["지금은 자극보다 차분한 쪽이 더 맞는 상태예요", "가볍게 손이 가는 안정적인 선택이에요 🙂"],
            "심심함": ["입 심심함을 가볍게 다루고 싶은 흐름이에요", "적당히 씹히는 감각이 도움이 될 수 있어요"],
            "보상심리": ["큰 보상보다 깔끔한 만족을 원하는 상태예요 ✨", "부담 적게 챙기고 싶은 흐름이에요"],
            "배고픔": ["허기를 간단하게 다루고 싶은 상태예요", "지금은 무겁지 않은 선택이 잘 맞아요"],
            "습관": ["익숙한 시간대에 손이 가는 간식일 수 있어요", "무난하게 정리하려는 흐름이에요"],
            "집중 안 됨": ["가볍게 리듬을 되찾고 싶은 상태예요", "작게 전환하기 좋은 선택이에요"],
        }
        impact = ["지금 시간에도 비교적 부담이 적을 수 있어요 🌿", "양만 조절하면 깔끔하게 마무리하기 좋아요"]
        alt = ["요거트", "과일"]

    elif any(x in menu_l for x in ["샐러드", "닭가슴살", "두부", "계란", "구운 과자", "따뜻한 차"]):
        psych_map = {
            "스트레스": ["지금은 몸을 편하게 두고 싶은 상태예요 🙂", "자극보다 안정감을 찾는 흐름이에요"],
            "심심함": ["가볍게 채우고 정리하고 싶은 상태예요", "입 심심함을 부담 없이 다루려는 느낌이에요"],
            "보상심리": ["스스로를 잘 챙기고 싶은 마음이 보여요 ✨", "덜 무겁게 만족하고 싶은 흐름이에요"],
            "배고픔": ["허기를 편하게 다루려는 선택이에요", "지금 시간엔 꽤 잘 맞는 편이에요"],
            "습관": ["과하지 않게 마무리하려는 루틴으로 보여요", "편안하게 정리하는 흐름이에요"],
            "집중 안 됨": ["가볍게 리듬을 되찾고 싶은 상태예요", "지금은 부담 적은 쪽이 더 잘 어울려요"],
        }
        impact = ["지금 시간에도 비교적 편하게 느껴질 수 있어요 🌿", "흐름을 크게 깨지 않고 넘어가기 좋아요"]
        alt = ["과일", "요거트"]

    else:
        psych_map = {
            "스트레스": ["지금은 뭔가로 분위기를 바꾸고 싶은 순간이에요 😮‍💨", "선택보다 위안이 먼저 필요한 상태일 수 있어요"],
            "심심함": ["배고픔보다 심심함이 먼저 온 것 같아요 🙂", "입이 심심해서 메뉴가 떠오른 흐름일 수 있어요"],
            "보상심리": ["오늘을 보상받고 싶은 마음이 보여요 ✨", "작은 만족으로 하루를 마무리하고 싶은 상태예요"],
            "배고픔": ["허기가 올라와서 뭔가 채우고 싶은 순간이에요", "지금은 에너지를 보충하고 싶은 흐름이에요"],
            "습관": ["익숙한 시간대라 자연스럽게 메뉴가 떠올랐을 수 있어요", "습관성 선택일 가능성도 있어 보여요"],
            "집중 안 됨": ["기분 전환이 필요해서 메뉴가 당길 수 있어요", "짧게 리프레시하고 싶은 흐름이에요"],
        }
        impact = ["지금은 만족이 되지만 양이 커지면 조금 부담될 수 있어요 🌙", "가볍게 먹으면 훨씬 편하게 마무리할 수 있어요"]
        alt = ["과일", "따뜻한 차"]

    psych = psych_map.get(feeling, ["지금은 마음을 달래고 싶은 순간이에요", "빠르게 만족되는 선택이 끌릴 수 있어요"])

    summary_map = {
        "스트레스": f"지금 {hour}시엔 스트레스를 달래는 선택에 가까워 보여요 🙂",
        "심심함": f"지금 {hour}시엔 배고픔보다 심심함이 더 크게 작동한 것 같아요 🙂",
        "보상심리": f"지금 {hour}시엔 나를 보상해주고 싶은 마음이 보여요 ✨",
        "배고픔": f"지금 {hour}시엔 허기를 가볍게 다루는 쪽이 더 편해 보여요 🍽️",
        "습관": f"지금 {hour}시엔 습관성 선택일 수 있어서 양 조절이 중요해요 ⏰",
        "집중 안 됨": f"지금 {hour}시엔 리프레시가 필요한 흐름으로 보여요 🌿",
    }

    return clean_result({
        "summary": f"👉 {summary_map.get(feeling, f'지금 {hour}시엔 가볍게 조절하는 선택이 더 잘 맞아요 🙂')}",
        "menu": f"🍽️ {menu}",
        "psych": psych,
        "impact": impact,
        "alt": alt,
        "closing": "> 지금 이 시간엔 완전히 참기보다, 가볍게 조절하는 게 더 좋아요 🙂",
    })

# -----------------------------
# LLM 보완 분석
# -----------------------------
def analyze_snack_with_llm(menu: str, hour: int, feeling: str) -> dict:
    client = get_client()

    system_prompt = """
너는 '먹을까말까' 앱의 시간 코치다.

역할:
지금 시간과 상태를 보고, 사용자의 선택을 짧고 부드럽게 코칭한다.

톤:
- 친구처럼 자연스럽게 말한다
- "지금 이 시간엔 ~" 같은 시간 코치 말투를 사용한다
- 절대 훈계하지 않는다
- 짧고 직관적으로 말한다
- 사용자를 이해해주는 느낌으로 쓴다

규칙:
- HTML 태그나 마크다운 기호를 절대 쓰지 마라
- 각 항목은 짧게 작성
- 대체 항목은 반드시 단답형 두 개
- 반드시 한국어만 사용

반드시 아래 JSON 형식으로만 답해라:
{
  "summary": "👉 ...",
  "menu": "🍽️ ...",
  "psych": ["...", "..."],
  "impact": ["...", "..."],
  "alt": ["...", "..."],
  "closing": "> 지금 이 시간엔 완전히 참기보다, 가볍게 조절하는 게 더 좋아요 🙂"
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
        return clean_result({
            "summary": data.get("summary", "👉 지금은 가볍게 조절하는 선택이 더 잘 맞아요 🙂"),
            "menu": data.get("menu", f"🍽️ {menu}"),
            "psych": data.get("psych", ["지금은 마음을 달래고 싶은 순간이에요", "가볍게 만족되는 선택이 끌릴 수 있어요"])[:2],
            "impact": data.get("impact", ["지금은 만족이 되지만 조금 부담될 수 있어요", "가볍게 가면 더 편할 수 있어요"])[:2],
            "alt": data.get("alt", ["과일", "요거트"])[:2],
            "closing": data.get("closing", "> 지금 이 시간엔 완전히 참기보다, 가볍게 조절하는 게 더 좋아요 🙂"),
        })
    except Exception:
        return clean_result(fast_snack_analysis(menu, hour, feeling))

# -----------------------------
# 결과 렌더링
# -----------------------------
def render_result(result: dict):
    result = clean_result(result)

    psych = result.get("psych", [])[:2]
    impact = result.get("impact", [])[:2]
    alt_items = result.get("alt", [])[:2]

    st.markdown(
        f'<div class="summary-card">{result["summary"]}</div>',
        unsafe_allow_html=True
    )

    # 메뉴 카드 시작
    st.markdown('<div class="result-card">', unsafe_allow_html=True)

    st.markdown(result["menu"])

    st.markdown("**🧠 심리**")
    for item in psych:
        st.write(f"- {item}")

    st.markdown("**🌙 영향**")
    for item in impact:
        st.write(f"- {item}")

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="alt-title">🥗 대체</div>', unsafe_allow_html=True)

    if alt_items:
        cols = st.columns(len(alt_items))
        for i, alt_menu in enumerate(alt_items):
            with cols[i]:
                if st.button(alt_menu, use_container_width=True, key=f"alt_{alt_menu}_{i}"):
                    st.session_state["selected_alt_menu"] = alt_menu
                    st.session_state["menu_input"] = alt_menu
                    st.session_state["auto_analyze"] = True
                    st.rerun()

    st.markdown(
        f'<div class="result-card" style="margin-top:10px;">{result["closing"]}</div>',
        unsafe_allow_html=True
    )

# -----------------------------
# UI
# -----------------------------
st.markdown('<div class="title">먹을까말까 🍽️</div>', unsafe_allow_html=True)
st.markdown('<div class="sub">야식 전, 빠르게 판단 도와주는 코치</div>', unsafe_allow_html=True)

st.markdown("""
<div class="info-card">
먹고 싶은 메뉴를 입력하면<br>
지금 시간 기준으로 <b>왜 당기는지 / 어떻게 느껴질지 / 뭘로 가볍게 바꾸면 좋을지</b><br>
짧고 빠르게 알려줘요.
</div>
""", unsafe_allow_html=True)

if st.session_state["selected_alt_menu"]:
    st.session_state["menu_input"] = st.session_state["selected_alt_menu"]

menu = st.text_input(
    "먹고 싶은 메뉴",
    key="menu_input",
    placeholder="예: 꽈배기, 감자칩, 라면, 치킨"
)

feeling = st.selectbox(
    "현재 상태",
    ["배고픔", "스트레스", "심심함", "습관", "보상심리", "집중 안 됨"]
)

use_current_time = st.checkbox("현재 시간 자동 사용", value=True)

if use_current_time:
    hour = get_korea_hour()
    st.write(f"현재 시각: **{hour}시**")
else:
    hour = st.slider("현재 시각을 선택하세요", 0, 23, 23)

analyze_button = st.button("분석하기", use_container_width=True)

# -----------------------------
# 실행
# -----------------------------
auto_selected = st.session_state.get("auto_analyze", False)

if analyze_button or auto_selected:
    clean_menu = normalize_menu(menu or st.session_state["selected_alt_menu"])

    if not clean_menu:
        st.warning("메뉴를 먼저 입력해 주세요.")
    elif len(clean_menu) > 30:
        st.warning("메뉴명은 너무 길지 않게 입력해 주세요.")
    else:
        try:
            with st.spinner("지금 시간 기준으로 빠르게 보는 중이에요..."):
                result = fast_snack_analysis(
                    menu=clean_menu,
                    hour=hour,
                    feeling=feeling
                )

                if should_use_llm(clean_menu):
                    try:
                        result = analyze_snack_with_llm(
                            menu=clean_menu,
                            hour=hour,
                            feeling=feeling
                        )
                    except Exception:
                        pass

            badge_text, badge_class = get_badge(hour, clean_menu)

            st.markdown("---")
            st.markdown("## 🧠 빠른 분석")

            st.markdown(
                f'<div class="badge {badge_class}">{badge_text}</div>',
                unsafe_allow_html=True
            )

            render_result(result)

            st.markdown(
                '<div class="small-note">안내: 이 앱은 일반적인 라이프스타일 코칭을 위한 정보 제공용이며, 의료적 진단이나 치료를 대체하지 않습니다.</div>',
                unsafe_allow_html=True
            )

            st.session_state["selected_alt_menu"] = ""
            st.session_state["auto_analyze"] = False

        except Exception as e:
            st.error("분석 중 오류가 발생했어요.")
            st.code(str(e))