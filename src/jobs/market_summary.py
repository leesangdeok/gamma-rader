import logging
import sys
from datetime import datetime

import pytz

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

KST = pytz.timezone("Asia/Seoul")


def format_index_line(name: str, data: dict) -> str:
    """지수 한 줄을 포맷합니다."""
    price = data.get("price")
    change_pct = data.get("change_pct")

    if price is None:
        return f"  {name}: N/A"

    if change_pct is None:
        change_pct = 0.0

    if change_pct > 0:
        arrow = "🟢"
    elif change_pct < 0:
        arrow = "🔴"
    else:
        arrow = "➡️"

    return f"  {name}: {price:,.2f} {arrow} {change_pct:+.2f}%"


def main():
    """시장 시황 요약을 생성하고 Telegram으로 전송합니다."""
    from src.analyzers.gemini_analyzer import generate_market_summary
    from src.collectors.market_data import get_market_indices
    from src.collectors.news import search_google_news
    from src.notifiers.telegram_notifier import send_message

    now_kst = datetime.now(KST)
    hour = now_kst.hour
    date_str = now_kst.strftime("%Y-%m-%d")

    # 오전/오후 구분
    is_morning = hour < 12
    if is_morning:
        time_label = "오전 10시 시황"
        header_icon = "🌅"
        gemini_label = "오전 10시"
    else:
        time_label = "오후 5시 시황"
        header_icon = "🌆"
        gemini_label = "오후 5시"

    logger.info(f"{time_label} 시작")

    # 시장 지수 조회
    logger.info("시장 지수 조회 중...")
    indices = get_market_indices()

    # 뉴스 수집
    logger.info("뉴스 수집 중...")
    news_items = []

    # 한국 시장 뉴스
    kr_news = search_google_news("한국 주식시장 코스피", lang="ko", country="KR", count=4)
    news_items.extend(kr_news)

    # 오후에는 미국 시장 뉴스도 포함
    if not is_morning:
        us_news = search_google_news("US stock market today", lang="en", country="US", count=4)
        news_items.extend(us_news)

    # Gemini AI 시황 요약
    logger.info("Gemini AI 시황 분석 중...")
    ai_summary = generate_market_summary(gemini_label, indices, news_items)

    # 메시지 조립
    lines = [
        f"{header_icon} <b>{time_label}</b> {date_str} KST",
        "",
        ai_summary,
        "",
        "<b>📊 주요 지수</b>",
    ]

    index_order = ["KOSPI", "KOSDAQ", "S&P500", "NASDAQ", "DOW"]
    for name in index_order:
        if name in indices:
            lines.append(format_index_line(name, indices[name]))

    message = "\n".join(lines)

    logger.info("시황 요약 메시지 생성 완료, Telegram 전송 중...")
    success = send_message(message)

    if success:
        logger.info(f"{time_label} 전송 완료")
    else:
        logger.error(f"{time_label} 전송 실패")
        sys.exit(1)


if __name__ == "__main__":
    main()
