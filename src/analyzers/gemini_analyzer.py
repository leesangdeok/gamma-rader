import logging
import os

import google.generativeai as genai

logger = logging.getLogger(__name__)

_model = None


def get_model():
    """Gemini 모델 인스턴스를 반환합니다."""
    global _model
    if _model is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
        genai.configure(api_key=api_key)
        _model = genai.GenerativeModel("gemini-3-flash-preview") # gemini-2.0-flash-exp
    return _model


def analyze_stock_movement(
    name: str, ticker: str, change_pct: float, news: list
) -> str:
    """
    주가 급등락 원인을 Gemini AI로 분석합니다.

    Args:
        name: 종목 이름
        ticker: 종목 코드
        change_pct: 변동률 (%)
        news: 관련 뉴스 리스트 [{"title": str, ...}, ...]

    Returns:
        str: 2-3문장 분석 텍스트
    """
    try:
        model = get_model()

        direction = "급등" if change_pct > 0 else "급락"
        news_headlines = "\n".join(
            [f"- {item['title']}" for item in news[:5] if item.get("title")]
        )
        if not news_headlines:
            news_headlines = "관련 뉴스 없음"

        prompt = f"""다음 정보를 바탕으로 주가 변동 원인을 한국어로 2-3문장으로 간결하게 분석해주세요.

종목: {name} ({ticker})
변동: {change_pct:+.2f}% {direction}

관련 뉴스 헤드라인:
{news_headlines}

분석 시 주의사항:
- 투자 조언이 아닌 시황 분석임을 명시하지 않아도 됩니다
- 명확한 사실에 기반한 분석을 제공하세요
- 2-3문장으로 간결하게 작성하세요"""

        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini 주가 분석 실패 ({name}): {e}")
        return "AI 분석을 일시적으로 사용할 수 없습니다."


def generate_market_summary(time_label: str, indices: dict, news_items: list) -> str:
    """
    시장 시황 요약을 Gemini AI로 생성합니다.

    Args:
        time_label: 시간대 라벨 (예: "오전 10시", "오후 5시")
        indices: 주요 지수 데이터 dict
        news_items: 최신 뉴스 리스트

    Returns:
        str: 2-3문장 시황 요약 텍스트
    """
    try:
        model = get_model()

        index_summary = []
        for name, data in indices.items():
            if data.get("price") is not None:
                change = data.get("change_pct", 0.0) or 0.0
                direction = "상승" if change > 0 else ("하락" if change < 0 else "보합")
                index_summary.append(
                    f"- {name}: {data['price']:,.2f} ({change:+.2f}% {direction})"
                )
        index_text = "\n".join(index_summary) if index_summary else "지수 데이터 없음"

        news_headlines = "\n".join(
            [f"- {item['title']}" for item in news_items[:8] if item.get("title")]
        )
        if not news_headlines:
            news_headlines = "관련 뉴스 없음"

        prompt = f"""현재 {time_label} 시장 상황을 한국어로 2-3문장으로 간결하게 요약해주세요.

주요 지수:
{index_text}

최신 뉴스:
{news_headlines}

다음 사항을 고려하여 작성하세요:
- 전반적인 시장 분위기
- 주요 등락 원인 (뉴스 기반)
- 투자자가 주목해야 할 포인트
- 2-3문장으로 간결하게 한국어로 작성"""

        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini 시황 요약 생성 실패: {e}")
        return "AI 시황 분석을 일시적으로 사용할 수 없습니다."
