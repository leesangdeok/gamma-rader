import logging
import os
import time
from datetime import datetime

import pytz
import requests

logger = logging.getLogger(__name__)

_BASE_URL_REAL = "https://openapi.koreainvestment.com:9443"
_BASE_URL_MOCK = "https://openapivts.koreainvestment.com:9443"

# process-level token 캐시
_token_cache: dict = {}


def _base_url() -> str:
    if os.environ.get("KIS_MOCK", "").lower() in ("1", "true", "yes"):
        return _BASE_URL_MOCK
    return _BASE_URL_REAL


def _app_key() -> str | None:
    return os.environ.get("KIS_APP_KEY")


def _app_secret() -> str | None:
    return os.environ.get("KIS_APP_SECRET")


def get_access_token() -> str | None:
    """KIS access token을 반환합니다. 만료 전 캐시를 재사용합니다."""
    now = time.time()
    if _token_cache.get("token") and _token_cache.get("expires_at", 0) > now + 60:
        return _token_cache["token"]

    app_key = _app_key()
    app_secret = _app_secret()
    if not app_key or not app_secret:
        logger.warning("KIS_APP_KEY 또는 KIS_APP_SECRET 환경변수가 설정되지 않았습니다.")
        return None

    try:
        resp = requests.post(
            f"{_base_url()}/oauth2/tokenP",
            json={"grant_type": "client_credentials", "appkey": app_key, "appsecret": app_secret},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token")
        expires_in = int(data.get("expires_in", 86400))
        if token:
            _token_cache["token"] = token
            _token_cache["expires_at"] = now + expires_in
            logger.debug("KIS access token 발급 완료")
            return token
    except Exception as e:
        logger.warning(f"KIS access token 발급 실패: {e}")
    return None


def get(path: str, tr_id: str, params: dict) -> dict | None:
    """KIS API GET 요청을 수행합니다."""
    token = get_access_token()
    if not token:
        return None

    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": _app_key(),
        "appsecret": _app_secret(),
        "tr_id": tr_id,
        "custtype": "P",
        "tr_cont": "",
    }
    try:
        resp = requests.get(
            f"{_base_url()}{path}",
            headers=headers,
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("rt_cd") != "0":
            logger.warning(f"KIS API 오류 [{tr_id}]: {data.get('msg1', '')}")
            return None
        return data
    except Exception as e:
        logger.warning(f"KIS API 요청 실패 [{tr_id}]: {e}")
        return None


def get_kospi200_futures_front_month_code() -> str:
    """
    KOSPI200 야간선물 근월물 종목코드를 반환합니다.
    만기: 3·6·9·12월 두 번째 목요일. 만기 당일 이후는 다음 분기월로 전환.

    반환 예: "101W2606" (2026년 6월물 야간선물)
    """
    kst = pytz.timezone("Asia/Seoul")
    today = datetime.now(kst)
    year, month = today.year, today.month

    # 가장 가까운 분기 만기월 찾기
    expiry_months = [3, 6, 9, 12]
    for em in expiry_months:
        if em < month:
            continue
        expiry_date = _second_thursday(year, em)
        if today.date() <= expiry_date:
            return f"101W{str(year)[2:]}{em:02d}"

    # 내년 3월물
    return f"101W{str(year + 1)[2:]}03"


def _second_thursday(year: int, month: int):
    """해당 년월의 두 번째 목요일 날짜를 반환합니다."""
    from calendar import monthcalendar
    thursdays = [w[3] for w in monthcalendar(year, month) if w[3] > 0]
    from datetime import date
    return date(year, month, thursdays[1])
