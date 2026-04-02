from datetime import datetime

import pytz

KST = pytz.timezone("Asia/Seoul")
EST = pytz.timezone("America/New_York")


def is_korean_market_open() -> bool:
    """
    한국 주식시장 (KOSPI/KOSDAQ) 개장 여부를 확인합니다.
    운영 시간: KST 09:00 ~ 15:30, 월~금

    Returns:
        bool: 한국 시장 개장 여부
    """
    now_kst = datetime.now(KST)
    weekday = now_kst.weekday()  # 0=월요일, 6=일요일

    if weekday >= 5:  # 토요일(5), 일요일(6)
        return False

    market_open = now_kst.replace(hour=9, minute=0, second=0, microsecond=0)
    market_close = now_kst.replace(hour=15, minute=30, second=0, microsecond=0)

    return market_open <= now_kst <= market_close


def is_us_market_open() -> bool:
    """
    미국 주식시장 개장 여부를 확인합니다.
    운영 시간: EST 09:30 ~ 16:00, 월~금

    Returns:
        bool: 미국 시장 개장 여부
    """
    now_est = datetime.now(EST)
    weekday = now_est.weekday()  # 0=월요일, 6=일요일

    if weekday >= 5:  # 토요일(5), 일요일(6)
        return False

    market_open = now_est.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now_est.replace(hour=16, minute=0, second=0, microsecond=0)

    return market_open <= now_est <= market_close


def is_any_market_open() -> bool:
    """
    한국 또는 미국 시장 중 하나라도 개장 중인지 확인합니다.

    Returns:
        bool: 어느 시장이든 개장 여부
    """
    return is_korean_market_open() or is_us_market_open()
