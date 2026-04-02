import logging
import sys
from datetime import datetime

import pytz
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

KST = pytz.timezone("Asia/Seoul")


def load_settings() -> dict:
    """설정 파일을 로드합니다."""
    try:
        with open("config/settings.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"설정 파일 로드 실패: {e}")
        return {}


def format_morning_report(settings: dict) -> str:
    """오전 시황 브리핑 메시지를 포맷합니다."""
    from src.collectors.market_data import (
        get_foreign_investor_net_selling,
        get_kr_10y_yield,
        get_us_10y_yield,
        get_usd_krw,
        get_vix,
    )

    now_kst = datetime.now(KST)
    date_str = now_kst.strftime("%Y-%m-%d")
    time_str = now_kst.strftime("%H:%M")

    thresholds = settings.get("thresholds", {})
    vix_warning = thresholds.get("vix_warning", 25.0)
    yield_spread_warning = thresholds.get("yield_spread_warning", 1.5)
    foreign_selling_warning_trillion = thresholds.get(
        "foreign_selling_warning_trillion", 1.0
    )
    consecutive_days_threshold = thresholds.get("foreign_selling_consecutive_days", 3)

    lines = [
        f"📊 <b>오전 시황 브리핑</b> {date_str} {time_str} KST",
        "",
    ]

    # USD/KRW 환율
    usd_krw = get_usd_krw()
    lines.append("💱 <b>환율 (USD/KRW)</b>")
    if usd_krw is not None:
        lines.append(f"  {usd_krw:,.1f}원")
    else:
        lines.append("  N/A")
    lines.append("")

    # VIX 공포지수
    vix = get_vix()
    lines.append("📉 <b>VIX 공포지수</b>")
    if vix is not None:
        if vix >= vix_warning:
            lines.append(f"  ⚠️ {vix:.2f} (경고: 공포지수 {vix_warning:.0f} 이상)")
        else:
            lines.append(f"  ✅ {vix:.2f}")
    else:
        lines.append("  N/A")
    lines.append("")

    # 외국인 순매도 현황
    foreign_data = get_foreign_investor_net_selling(
        consecutive_days=consecutive_days_threshold
    )
    lines.append("🏦 <b>외국인 순매도 현황</b> (KOSPI 기준)")
    days = foreign_data.get("days", 0)
    total_selling = foreign_data.get("total_selling", 0)
    is_consecutive = foreign_data.get("is_consecutive", False)

    if days > 0:
        consecutive_icon = "📛" if is_consecutive else ""
        lines.append(f"  연속 순매도: {days}일 {consecutive_icon}".strip())
        total_trillion = abs(total_selling) / 1_000_000_000_000
        if total_trillion >= foreign_selling_warning_trillion:
            lines.append(
                f"  총 순매도: {total_trillion:.2f}조원 ⚠️ ({foreign_selling_warning_trillion:.0f}조원 이상)"
            )
        else:
            lines.append(f"  총 순매도: {total_trillion:.2f}조원")
    else:
        lines.append("  외국인 순매수 또는 데이터 없음")
    lines.append("")

    # 국채 금리 스프레드
    us_yield = get_us_10y_yield()
    kr_yield = get_kr_10y_yield()
    lines.append("📈 <b>국채 금리 스프레드</b>")

    if us_yield is not None:
        lines.append(f"  미국 10년물: {us_yield:.3f}%")
    else:
        lines.append("  미국 10년물: N/A")

    if kr_yield is not None:
        lines.append(f"  한국 10년물: {kr_yield:.3f}%")
    else:
        lines.append("  한국 10년물: N/A")

    if us_yield is not None and kr_yield is not None:
        spread = us_yield - kr_yield
        if abs(spread) >= yield_spread_warning:
            lines.append(
                f"  ⚠️ 금리차: {spread:+.3f}%p (경고: {yield_spread_warning:.1f}%p 이상)"
            )
        else:
            lines.append(f"  ✅ 금리차: {spread:+.3f}%p")
    else:
        lines.append("  금리차: N/A")

    return "\n".join(lines)


def main():
    """오전 시황 브리핑을 생성하고 Telegram으로 전송합니다."""
    from src.notifiers.telegram_notifier import send_message

    logger.info("오전 시황 브리핑 시작")

    settings = load_settings()
    message = format_morning_report(settings)

    logger.info("브리핑 메시지 생성 완료, Telegram 전송 중...")
    success = send_message(message)

    if success:
        logger.info("오전 시황 브리핑 전송 완료")
    else:
        logger.error("오전 시황 브리핑 전송 실패")
        sys.exit(1)


if __name__ == "__main__":
    main()
