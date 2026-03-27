import json
import re
from typing import Any, Dict, List

import streamlit as st
from openai import OpenAI

# -----------------------------
# Page config
# -----------------------------
st.set_page_config(
    page_title="먹을까말까",
    page_icon="🍽️",
    layout="centered",
)

# -----------------------------
# Custom CSS
# -----------------------------
st.markdown(
    """
    <style>
    .main {
        padding-top: 1.2rem;
        padding-bottom: 3rem;
    }

    .hero-card {
        background: linear-gradient(135deg, #fff7ed 0%, #fff1f2 100%);
        border: 1px solid #fed7aa;
        border-radius: 24px;
        padding: 28px 24px;
        margin-bottom: 18px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.05);
    }

    .hero-title {
        font-size: 2rem;
        font-weight: 800;
        color: #111827;
        margin-bottom: 6px;
    }

    .hero-sub {
        color: #4b5563;
        font-size: 1rem;
        line-height: 1.6;
    }

    .section-title {
        font-size: 1.05rem;
        font-weight: 700;
        margin-top: 12px;
        margin-bottom: 10px;
        color: #111827;
    }

    .soft-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 20px;
        padding: 18px 18px;
        box-shadow: 0 6px 20px rgba(17,24,39,0.04);
        margin-bottom: 14px;
    }

    .result-banner {
        border-radius: 22px;
        padding: 20px;
        margin-top: 8px;
        margin-bottom: 18px;
        border: 1px solid transparent;
    }

    .banner-eat {
        background: #ecfdf5;
        border-color: #a7f3d0;
    }

    .banner-half {
        background: #fffbeb;
        border-color: #fde68a;
    }

    .banner-no {
        background: #fef2f2;
        border-color: #fecaca;
    }

    .banner-title {
        font-size: 1.35rem;
        font-weight: 800;
        margin-bottom: 6px;
        color: #111827;
    }

    .banner-desc {
        color: #374151;
        line-height: 1.6;
    }

    .three-card-wrap {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 12px;
        margin-top: 10px;
        margin-bottom: 10px;
    }

    .choice-card {
        border-radius: 20px;
        padding: 16px 14px;
        border: 1px solid #e5e7eb;
        background: #fff;
        min-height: 158px;
    }

    .choice-card.active-eat {
        background: #ecfdf5;
        border: 2px solid #10b981;
        box-shadow: 0 8px 20px rgba(16,185,129,0.12);
    }

    .choice-card.active-half {
        background: #fffbeb;
        border: 2px solid #f59e0b;
        box-shadow: 0 8px 20px rgba(245,158,11,0.12);
    }

    .choice-card.active-no {
        background: #fef2f2;
        border: 2px solid #ef4444;
        box-shadow: 0 8px 20px rgba(239,68,68,0.12);
    }

    .choice-emoji {
        font-size: 1.6rem;
        margin-bottom: 8px;
    }

    .choice-title {
        font-size: 1.02rem;
        font-weight: 800;
        color: #111827;
        margin-bottom: 8px;
    }

    .choice-desc {
        font-size: 0.92rem;
        color: #4b5563;
        line-height: 1.55;
    }

    .metric-chip-wrap {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 8px;
        margin-bottom: 4px;
    }

    .metric-chip {
        display: inline-block;
        padding: 8px 12px;
        border-radius: 999px;
        background: #f3f4f6;
        color: #111827;
        font-size: 0.9rem;
        border: 1px solid #e5e7eb;
    }

    .alt-card {
        background: #f9fafb;
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        padding: 14px 14px;
        margin-bottom: 10px;
    }

    .alt-title {
        font-weight: 800;
        color: #111827;
        margin-bottom: 6px;
    }

    .footer-note {
        font-size: 0.84rem;
        color: #6b7280;
        line-height: 1.6;
    }

    @media (max-width: 768px) {
        .three-card-wrap {
            grid-template-columns: 1fr;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# Header
# -----------------------------
st.markdown(
    """
    <div class="hero-card">
        <div class="hero-title">🍽️ 먹을까말까</div>
        <div class="hero-sub">
            감량 목표와 오늘 먹은 음식, 지금 먹고 싶은 음식을 바탕으로<br>
            <b>먹자 / 반만 먹자 / 오늘은 말자</b>를 직관적으로 판단해줘요.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# OpenAI
# -----------------------------
def get_openai_client() -> OpenAI:
    api_key = st.secrets.get("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
    return OpenAI(api_key=api_key)


MODEL_NAME = st.secrets.get("OPENAI_MODEL", "gpt-5-mini")

# -----------------------------
# Logic helpers
# -----------------------------
def calculate_bmr(gender: str, weight: float, height: float, age: int) -> float:
    if gender == "여성":
        return 10 * weight + 6.25 * height - 5 * age - 161
    return 10 * weight + 6.25 * height - 5 * age + 5


def activity_multiplier(level: str) -> float:
    mapping = {
        "거의 움직이지 않음": 1.2,
        "가벼운 활동": 1.375,
        "보통 활동": 1.55,
        "활동 많음": 1.725,
        "매우 활동 많음": 1.9,
    }
    return mapping[level]


def safe_json_load(text: str) -> Dict[str, Any]:
    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass

    return {}


def food_analysis_with_llm(client: OpenAI, food_text: str, include_alts: bool = False) -> Dict[str, Any]:
    system_prompt = """
너는 한국 사용자 식단 코치 앱의 음식 분석기다.
반드시 JSON만 출력해라.
설명문, 마크다운, 코드블록 금지.

규칙:
- 한국 기준 일반적인 1인분/보통 양 기준으로 추정
- total_kcal는 정수
- food_summary는 짧고 자연스럽게
- sodium_level은 "낮음" | "보통" | "높음"
- carb_level은 "낮음" | "보통" | "높음"
- protein_level은 "낮음" | "보통" | "높음"
- alternatives는 최대 3개
- alternatives 각 항목은 name, est_kcal, reason 포함
"""

    user_prompt = f"""
분석할 음식: {food_text}

아래 JSON 형식만 출력:
{{
  "total_kcal": 0,
  "food_summary": "",
  "sodium_level": "보통",
  "carb_level": "보통",
  "protein_level": "보통",
  "alternatives": [
    {{
      "name": "",
      "est_kcal": 0,
      "reason": ""
    }}
  ]
}}

주의:
- 음식명이 여러 개면 총합으로 계산
- total_kcal는 현실적인 범위로 추정
- alternatives는 {"최대 3개 채워라" if include_alts else "빈 배열로 둬라"}
"""

    response = client.responses.create(
        model=MODEL_NAME,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    parsed = safe_json_load(response.output_text)

    total_kcal = int(parsed.get("total_kcal", 0) or 0)
    food_summary = str(parsed.get("food_summary", "") or "")
    sodium_level = str(parsed.get("sodium_level", "보통") or "보통")
    carb_level = str(parsed.get("carb_level", "보통") or "보통")
    protein_level = str(parsed.get("protein_level", "보통") or "보통")
    alternatives = parsed.get("alternatives", [])

    if not isinstance(alternatives, list):
        alternatives = []

    cleaned_alts: List[Dict[str, Any]] = []
    for item in alternatives[:3]:
        if not isinstance(item, dict):
            continue
        cleaned_alts.append(
            {
                "name": str(item.get("name", "") or "").strip(),
                "est_kcal": int(item.get("est_kcal", 0) or 0),
                "reason": str(item.get("reason", "") or "").strip(),
            }
        )

    return {
        "total_kcal": total_kcal,
        "food_summary": food_summary,
        "sodium_level": sodium_level,
        "carb_level": carb_level,
        "protein_level": protein_level,
        "alternatives": cleaned_alts,
    }


def predict_next_day_weight_change(
    today_total_kcal: float,
    target_kcal: float,
    want_food_analysis: Dict[str, Any],
) -> Dict[str, Any]:
    calorie_diff = today_total_kcal - target_kcal
    fat_equivalent_kg = calorie_diff / 7700.0

    sodium = want_food_analysis.get("sodium_level", "보통")
    carb = want_food_analysis.get("carb_level", "보통")

    water_shift = 0.0
    if sodium == "높음":
        water_shift += 0.20
    elif sodium == "보통":
        water_shift += 0.05

    if carb == "높음":
        water_shift += 0.20
    elif carb == "보통":
        water_shift += 0.05

    scale_tomorrow_estimate = fat_equivalent_kg + water_shift

    if scale_tomorrow_estimate <= -0.15:
        message = "내일 체중계 숫자는 소폭 내려갈 가능성이 있어요."
    elif scale_tomorrow_estimate < 0.15:
        message = "내일 체중계 숫자는 큰 변화 없을 가능성이 높아요."
    elif scale_tomorrow_estimate < 0.4:
        message = "내일 체중계 숫자는 약간 올라갈 수 있어요."
    else:
        message = "내일 체중계 숫자는 꽤 올라 보일 수 있어요."

    return {
        "calorie_diff": calorie_diff,
        "fat_equivalent_kg": fat_equivalent_kg,
        "scale_tomorrow_estimate": scale_tomorrow_estimate,
        "message": message,
    }


def get_decision(remaining_after_food: float) -> str:
    if remaining_after_food >= 250:
        return "eat"
    if remaining_after_food >= -150:
        return "half"
    return "no"


def render_result_banner(decision: str, remaining_after_food: float) -> None:
    if decision == "eat":
        css_class = "banner-eat"
        title = "먹자 ✅"
        desc = f"지금 먹어도 괜찮아요. 먹고 나서도 오늘 목표 칼로리까지 약 {remaining_after_food:.0f}kcal 여유가 있어요."
    elif decision == "half":
        css_class = "banner-half"
        title = "반만 먹자 🟡"
        if remaining_after_food >= 0:
            desc = f"먹을 수는 있지만 여유가 크진 않아요. 먹고 나면 약 {remaining_after_food:.0f}kcal 정도 남아요."
        else:
            desc = f"조금 초과할 수 있어요. 전부보다 반 정도가 더 안전해요. 예상 초과량은 약 {abs(remaining_after_food):.0f}kcal예요."
    else:
        css_class = "banner-no"
        title = "오늘은 말자 ❌"
        desc = f"지금 먹으면 오늘 목표 칼로리를 약 {abs(remaining_after_food):.0f}kcal 초과해요. 오늘은 대체식이 더 유리해요."

    st.markdown(
        f"""
        <div class="result-banner {css_class}">
            <div class="banner-title">{title}</div>
            <div class="banner-desc">{desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_three_cards(active: str) -> None:
    eat_class = "choice-card active-eat" if active == "eat" else "choice-card"
    half_class = "choice-card active-half" if active == "half" else "choice-card"
    no_class = "choice-card active-no" if active == "no" else "choice-card"

    st.markdown(
        f"""
        <div class="three-card-wrap">
            <div class="{eat_class}">
                <div class="choice-emoji">✅</div>
                <div class="choice-title">먹자</div>
                <div class="choice-desc">
                    오늘 페이스 안에서 비교적 여유가 있는 상태예요.
                    너무 늦은 시간만 아니라면 무리 없는 선택이에요.
                </div>
            </div>
            <div class="{half_class}">
                <div class="choice-emoji">🟡</div>
                <div class="choice-title">반만 먹자</div>
                <div class="choice-desc">
                    완전 금지는 아니지만 전부 먹으면 아슬아슬해요.
                    양을 줄이면 만족감과 목표를 같이 챙길 수 있어요.
                </div>
            </div>
            <div class="{no_class}">
                <div class="choice-emoji">❌</div>
                <div class="choice-title">오늘은 말자</div>
                <div class="choice-desc">
                    지금은 참는 쪽이 목표 달성에 더 유리해요.
                    대신 더 가벼운 대체식으로 방향을 바꾸는 걸 추천해요.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def goal_risk_text(daily_deficit_needed: float) -> str:
    if daily_deficit_needed > 1000:
        return "목표가 꽤 빠른 편이에요. 기간을 조금 늘리면 더 현실적이고 건강하게 갈 수 있어요."
    if daily_deficit_needed > 700:
        return "조금 타이트한 감량 속도예요. 식단과 활동량을 꾸준히 맞추는 게 중요해요."
    return "비교적 현실적인 목표 속도예요."


# -----------------------------
# Input form
# -----------------------------
with st.form("diet_form"):
    st.markdown('<div class="section-title">1) 목표 설정</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        gender = st.selectbox("성별", ["여성", "남성"])
        age = st.number_input("나이", min_value=10, max_value=100, value=26)
        height = st.number_input("키(cm)", min_value=120.0, max_value=220.0, value=160.0)

    with col2:
        current_weight = st.number_input("현재 몸무게(kg)", min_value=30.0, max_value=250.0, value=58.0)
        target_weight = st.number_input("목표 몸무게(kg)", min_value=30.0, max_value=250.0, value=52.0)
        period_weeks = st.number_input("목표 기간(주)", min_value=1, max_value=52, value=8)

    activity = st.selectbox(
        "활동량",
        ["거의 움직이지 않음", "가벼운 활동", "보통 활동", "활동 많음", "매우 활동 많음"],
    )

    st.markdown('<div class="section-title">2) 오늘 이미 먹은 음식</div>', unsafe_allow_html=True)
    eaten_food_text = st.text_area(
        "오늘 먹은 음식 입력",
        value="알탕 + 공기밥 반공기",
        placeholder="예: 알탕 + 공기밥 반공기 + 아이스라떼",
        label_visibility="collapsed",
    )

    st.markdown('<div class="section-title">3) 지금 먹고 싶은 음식</div>', unsafe_allow_html=True)
    want_food_text = st.text_input(
        "지금 먹고 싶은 음식 입력",
        value="초코케이크 1조각",
        placeholder="예: 초코케이크 1조각 / 김밥 / 떡볶이",
        label_visibility="collapsed",
    )

    submitted = st.form_submit_button("🍴 먹을까 말까 판단하기", use_container_width=True)

# -----------------------------
# Result section
# -----------------------------
if submitted:
    if target_weight >= current_weight:
        st.error("목표 몸무게는 현재 몸무게보다 낮아야 해요.")
        st.stop()

    try:
        client = get_openai_client()
    except Exception as e:
        st.error(f"OpenAI 설정 오류: {e}")
        st.stop()

    with st.spinner("AI가 음식과 목표를 분석하는 중..."):
        eaten_analysis = food_analysis_with_llm(client, eaten_food_text, include_alts=False)
        want_analysis = food_analysis_with_llm(client, want_food_text, include_alts=True)

    eaten_cal = eaten_analysis["total_kcal"]
    want_cal = want_analysis["total_kcal"]

    weight_to_lose = current_weight - target_weight
    total_deficit_needed = weight_to_lose * 7700
    days = period_weeks * 7
    daily_deficit_needed = total_deficit_needed / days

    bmr = calculate_bmr(gender, current_weight, height, age)
    tdee = bmr * activity_multiplier(activity)

    safe_deficit = min(daily_deficit_needed, 1000)
    target_calories = tdee - safe_deficit

    min_safe_calories = 1200 if gender == "여성" else 1500
    target_calories = max(target_calories, min_safe_calories)

    today_total_if_eat = eaten_cal + want_cal
    remaining_after_food = target_calories - today_total_if_eat
    decision = get_decision(remaining_after_food)

    next_day = predict_next_day_weight_change(
        today_total_kcal=today_total_if_eat,
        target_kcal=target_calories,
        want_food_analysis=want_analysis,
    )

    st.markdown("---")
    st.markdown('<div class="section-title">결과</div>', unsafe_allow_html=True)
    render_result_banner(decision, remaining_after_food)
    render_three_cards(decision)

    st.markdown('<div class="section-title">핵심 수치</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="metric-chip-wrap">
            <span class="metric-chip">하루 목표 칼로리 {target_calories:.0f} kcal</span>
            <span class="metric-chip">오늘 총섭취 예상 {today_total_if_eat} kcal</span>
            <span class="metric-chip">오늘 먹은 음식 {eaten_cal} kcal</span>
            <span class="metric-chip">먹고 싶은 음식 {want_cal} kcal</span>
            <span class="metric-chip">하루 필요 적자 {daily_deficit_needed:.0f} kcal</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown('<div class="soft-card">', unsafe_allow_html=True)
        st.markdown("**오늘 먹은 음식**")
        st.write(eaten_food_text)
        st.write(f"추정 칼로리: **{eaten_cal} kcal**")
        if eaten_analysis["food_summary"]:
            st.write(f"요약: {eaten_analysis['food_summary']}")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_b:
        st.markdown('<div class="soft-card">', unsafe_allow_html=True)
        st.markdown("**지금 먹고 싶은 음식**")
        st.write(want_food_text)
        st.write(f"추정 칼로리: **{want_cal} kcal**")
        if want_analysis["food_summary"]:
            st.write(f"요약: {want_analysis['food_summary']}")
        st.write(
            f"특성: 나트륨 **{want_analysis['sodium_level']}** / "
            f"탄수화물 **{want_analysis['carb_level']}** / "
            f"단백질 **{want_analysis['protein_level']}**"
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-title">내일 체중 변화 예상</div>', unsafe_allow_html=True)
    st.markdown('<div class="soft-card">', unsafe_allow_html=True)
    st.write(next_day["message"])
    st.write(f"- 장기 열량 기준 변화 추정: **{next_day['fat_equivalent_kg']:+.03f}kg**")
    st.write(f"- 수분변동 포함 내일 체중계 예상 반응: **{next_day['scale_tomorrow_estimate']:+.02f}kg 내외**")
    st.markdown(
        '<div class="footer-note">※ 실제 다음 날 체중은 지방보다 수분, 나트륨, 탄수화물 영향이 더 크게 보일 수 있어요.</div>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-title">대체 음식 추천</div>', unsafe_allow_html=True)
    alts = want_analysis.get("alternatives", [])

    if alts:
        for idx, alt in enumerate(alts, start=1):
            name = alt.get("name", "").strip() or f"대체식 {idx}"
            kcal = alt.get("est_kcal", 0)
            reason = alt.get("reason", "").strip() or "더 가볍게 먹기 좋은 선택"
            st.markdown(
                f"""
                <div class="alt-card">
                    <div class="alt-title">{idx}. {name}</div>
                    <div>예상 칼로리: <b>{kcal} kcal</b></div>
                    <div style="margin-top:6px; color:#4b5563;">{reason}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            """
            <div class="alt-card">
                더 가벼운 대체식을 찾지 못했어요. 단백질 위주 간식이나 저당 메뉴로 바꿔보는 걸 추천해요.
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title">한 줄 코칭</div>', unsafe_allow_html=True)
    st.markdown('<div class="soft-card">', unsafe_allow_html=True)

    if decision == "eat":
        st.write("👉 오늘은 비교적 여유가 있어요. 너무 늦은 시간만 아니라면 괜찮아요.")
    elif decision == "half":
        st.write("👉 아예 금지보다 양 조절이 포인트예요. 반 정도로 만족감을 챙기는 쪽이 좋아요.")
    else:
        st.write("👉 지금은 참는 쪽이 더 유리해요. 먹고 싶다면 추천 대체식으로 방향을 바꿔보세요.")

    st.write(f"👉 목표 속도 코멘트: {goal_risk_text(daily_deficit_needed)}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        """
        <div class="footer-note" style="margin-top:16px;">
            ※ 이 앱은 일반적인 추정치 기반 참고용이에요. 건강 상태, 호르몬 변화, 약물 복용, 질환 여부는 반영하지 않아요.
        </div>
        """,
        unsafe_allow_html=True,
    )