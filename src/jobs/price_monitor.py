import logging
import sys

import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def load_yaml(path: str) -> dict:
    """YAML 파일을 로드합니다."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"YAML 파일 로드 실패 ({path}): {e}")
        return {}


def format_price(price: float, market: str) -> str:
    """시장에 맞는 가격 포맷을 반환합니다."""
    if market in ("KOSPI", "KOSDAQ"):
        return f"{price:,.0f}원"
    else:
        return f"${price:,.2f}"


def build_daily_alert_message(
    name: str,
    ticker: str,
    market: str,
    price: float,
    prev_close: float,
    change_pct: float,
    news: list,
    ai_analysis: str,
) -> str:
    """일간 급등락 알림 메시지를 생성합니다."""
    direction = "급등" if change_pct > 0 else "급락"
    icon = "🟢" if change_pct > 0 else "🔴"

    lines = [
        f"🚨 <b>[일간 급등락] {name} ({ticker})</b>",
        "",
        f"  {icon} {direction}: {change_pct:+.2f}% (전일 종가 대비)",
        f"  현재가: {format_price(price, market)}",
        f"  전일 종가: {format_price(prev_close, market)}",
    ]

    if news:
        lines.append("")
        lines.append("<b>📰 관련 뉴스</b>")
        for item in news[:3]:
            title = item.get("title", "")
            link = item.get("link", "")
            if title and link:
                # 제목이 너무 길면 자름
                display_title = title[:60] + "..." if len(title) > 60 else title
                lines.append(f"  • <a href='{link}'>{display_title}</a>")

    if ai_analysis:
        lines.append("")
        lines.append("<b>🤖 AI 분석 (Gemini)</b>")
        lines.append(f"  {ai_analysis}")

    return "\n".join(lines)


def build_short_term_alert_message(
    name: str,
    ticker: str,
    market: str,
    price: float,
    short_change_pct: float,
    interval_min: int,
) -> str:
    """단기 급변 알림 메시지를 생성합니다."""
    icon = "🟢" if short_change_pct > 0 else "🔴"

    lines = [
        f"⚡ <b>[단기 급변] {name} ({ticker})</b>",
        "",
        f"  {icon} {short_change_pct:+.2f}% (최근 {interval_min}분 기준)",
        f"  현재가: {format_price(price, market)}",
    ]

    return "\n".join(lines)


def main():
    """주가 급등락 모니터링을 실행합니다."""
    from src.analyzers.gemini_analyzer import analyze_stock_movement
    from src.collectors.news import get_stock_news
    from src.collectors.stock_data import get_stock_prices
    from src.notifiers.telegram_notifier import send_message
    from src.state.alert_state import AlertState
    from src.utils.market_hours import is_any_market_open

    # 장 운영 시간 확인
    if not is_any_market_open():
        logger.info("장 마감 상태. 모니터링 종료.")
        sys.exit(0)

    # 설정 로드
    settings = load_yaml("config/settings.yaml")
    watchlist_config = load_yaml("config/watchlist.yaml")

    alerts_config = settings.get("alerts", {})
    daily_threshold = alerts_config.get("daily_change_threshold_pct", 5.0)
    short_threshold = alerts_config.get("short_change_threshold_pct", 3.0)
    interval_min = alerts_config.get("short_change_interval_minutes", 5)
    cooldown_minutes = alerts_config.get("cooldown_minutes", 10)

    watchlist = watchlist_config.get("stocks", [])
    if not watchlist:
        logger.warning("watchlist.yaml에 종목이 없습니다.")
        sys.exit(0)

    # 알림 상태 로드
    state = AlertState()

    # 주가 조회
    logger.info(f"종목 가격 조회 시작 ({len(watchlist)}개 종목)")
    prices = get_stock_prices(watchlist)
    logger.info(f"가격 조회 완료: {len(prices)}개")

    for stock in prices:
        name = stock.get("name", "")
        ticker = stock.get("ticker", "")
        yf_ticker = stock.get("yf_ticker", "")
        market = stock.get("market", "US")
        price = stock.get("price")
        prev_close = stock.get("prev_close")
        change_pct = stock.get("change_pct", 0.0)

        if price is None:
            continue

        # 가격 이력 업데이트
        state.update_price(yf_ticker, price)

        # 1. 일간 5% 급등락 체크
        if (
            prev_close is not None
            and abs(change_pct) >= daily_threshold
            and state.can_send_five_pct_alert(yf_ticker)
            and state.can_send_alert(yf_ticker, cooldown_minutes)
        ):
            logger.info(
                f"일간 급등락 감지: {name} ({ticker}) {change_pct:+.2f}%"
            )

            # 뉴스 수집
            news = get_stock_news(name, ticker, market, count=5)

            # Gemini AI 분석
            try:
                ai_analysis = analyze_stock_movement(name, ticker, change_pct, news)
            except Exception as e:
                logger.error(f"AI 분석 실패 ({name}): {e}")
                ai_analysis = ""

            # 알림 메시지 전송
            message = build_daily_alert_message(
                name=name,
                ticker=ticker,
                market=market,
                price=price,
                prev_close=prev_close,
                change_pct=change_pct,
                news=news,
                ai_analysis=ai_analysis,
            )
            success = send_message(message)
            if success:
                state.mark_five_pct_alert(yf_ticker)
                state.mark_alert_sent(yf_ticker)
                logger.info(f"일간 급등락 알림 전송 완료: {name}")
            else:
                logger.error(f"일간 급등락 알림 전송 실패: {name}")

        # 2. 단기 급변 체크
        price_ago = state.get_price_n_minutes_ago(yf_ticker, interval_min)
        if price_ago is not None and price_ago > 0:
            short_change_pct = (price - price_ago) / price_ago * 100
            if (
                abs(short_change_pct) >= short_threshold
                and state.can_send_alert(yf_ticker, cooldown_minutes)
            ):
                logger.info(
                    f"단기 급변 감지: {name} ({ticker}) {short_change_pct:+.2f}% ({interval_min}분)"
                )
                message = build_short_term_alert_message(
                    name=name,
                    ticker=ticker,
                    market=market,
                    price=price,
                    short_change_pct=short_change_pct,
                    interval_min=interval_min,
                )
                success = send_message(message)
                if success:
                    state.mark_alert_sent(yf_ticker)
                    logger.info(f"단기 급변 알림 전송 완료: {name}")
                else:
                    logger.error(f"단기 급변 알림 전송 실패: {name}")

    # 상태 저장
    state.save()
    logger.info("주가 모니터링 완료")


if __name__ == "__main__":
    main()