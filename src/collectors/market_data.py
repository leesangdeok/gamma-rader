import logging
from datetime import datetime, timedelta

import pandas as pd
import pytz
import requests
import yfinance as yf

logger = logging.getLogger(__name__)


_krx_initialized = False


def _init_krx_session():
    """KRX 데이터 포털 세션을 초기화합니다 (LOGOUT 방지)."""
    global _krx_initialized
    if _krx_initialized:
        return
    _krx_initialized = True
    try:
        import pykrx.website.comm.webio as webio

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
            "Referer": "https://data.krx.co.kr/contents/MDC/MDI/outerLoader/index.cmd",
        })
        session.get("https://data.krx.co.kr/contents/MDC/MAIN/main/MDCMain.cmd", timeout=10)

        def _session_read(self, **params):
            resp = session.post(self.url, headers={**self.headers, **session.headers}, data=params)
            return resp

        webio.Post.read = _session_read
    except Exception as e:
        logger.debug(f"KRX 세션 초기화 실패 (무시): {e}")


def get_usd_krw() -> float | None:
    """USD/KRW 환율을 반환합니다."""
    try:
        ticker = yf.Ticker("KRW=X")
        hist = ticker.history(period="2d")
        if hist.empty:
            logger.warning("USD/KRW 데이터를 가져오지 못했습니다.")
            return None
        return float(hist["Close"].iloc[-1])
    except Exception as e:
        logger.error(f"USD/KRW 조회 실패: {e}")
        return None


def get_vix() -> float | None:
    """VIX 공포지수를 반환합니다."""
    try:
        ticker = yf.Ticker("^VIX")
        hist = ticker.history(period="2d")
        if hist.empty:
            logger.warning("VIX 데이터를 가져오지 못했습니다.")
            return None
        return float(hist["Close"].iloc[-1])
    except Exception as e:
        logger.error(f"VIX 조회 실패: {e}")
        return None


def get_us_10y_yield() -> float | None:
    """미국 10년물 국채 금리(%)를 반환합니다."""
    try:
        ticker = yf.Ticker("^TNX")
        hist = ticker.history(period="2d")
        if hist.empty:
            logger.warning("미국 10년물 금리 데이터를 가져오지 못했습니다.")
            return None
        return float(hist["Close"].iloc[-1])
    except Exception as e:
        logger.error(f"미국 10년물 금리 조회 실패: {e}")
        return None


_gemini_kr_cache: dict | None = None


def _fetch_kr_data_via_gemini() -> dict:
    """
    Gemini Google Search로 한국 10년물 금리와 외국인 순매도 데이터를 조회합니다.
    같은 프로세스 내에서는 캐시된 결과를 반환합니다.

    Returns:
        dict: {"kr_10y_yield": float|None, "foreign_net": int|None}
    """
    global _gemini_kr_cache
    if _gemini_kr_cache is not None:
        return _gemini_kr_cache

    import json
    import os
    import re

    result = {"kr_10y_yield": None, "foreign_net": None}
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return result
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=(
                "한국 국고채 10년물 금리와 오늘 KOSPI 외국인 순매도/순매수 금액을 검색해서 "
                "아래 JSON 형식으로만 답해줘. 다른 텍스트 없이 JSON만 출력.\n"
                "{\n"
                '  "kr_10y_yield": 3.691,\n'
                '  "foreign_net": -134650000000\n'
                "}\n"
                "- kr_10y_yield: % 단위 float\n"
                "- foreign_net: 원(KRW) 단위 int, 순매도면 음수, 순매수면 양수"
            ),
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            ),
        )
        text = response.text.strip()
        # ```json ... ``` 마크다운 제거
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        data = json.loads(text.strip())
        if isinstance(data.get("kr_10y_yield"), (int, float)):
            result["kr_10y_yield"] = float(data["kr_10y_yield"])
        if isinstance(data.get("foreign_net"), (int, float)):
            result["foreign_net"] = int(data["foreign_net"])
        logger.info(
            f"Gemini 조회 완료 - 한국 10년물: {result['kr_10y_yield']}%, "
            f"외국인 순매도: {result['foreign_net']:,}원"
        )
    except Exception as e:
        logger.warning(f"Gemini 데이터 조회 실패: {e}")
    _gemini_kr_cache = result
    return result


def get_kr_10y_yield() -> float | None:
    """한국 10년물 국채 금리(%)를 반환합니다. pykrx 실패 시 Gemini로 대체."""
    try:
        from pykrx import bond

        _init_krx_session()

        kst = pytz.timezone("Asia/Seoul")
        today = datetime.now(kst)
        from_date = (today - timedelta(days=14)).strftime("%Y%m%d")
        to_date = today.strftime("%Y%m%d")

        df = bond.get_otc_treasury_yields(from_date, to_date, "국고채10년")
        if df is not None and not df.empty:
            col = "수익률" if "수익률" in df.columns else df.columns[0]
            series = df[col].dropna()
            if not series.empty:
                return float(series.iloc[-1])
    except Exception as e:
        logger.debug(f"pykrx 한국 10년물 조회 실패, Gemini로 대체: {e!r}")

    # pykrx 실패 시 Gemini fallback
    data = _fetch_kr_data_via_gemini()
    return data.get("kr_10y_yield")


def get_foreign_investor_net_selling(consecutive_days: int = 3) -> dict:
    """
    KOSPI 외국인 순매도 현황을 반환합니다.

    Returns:
        dict: {
            "is_consecutive": bool,
            "days": int,
            "total_selling": int  # 음수이면 순매도 (단위: 원)
        }
    """
    result = {"is_consecutive": False, "days": 0, "total_selling": 0}
    try:
        from pykrx import stock

        _init_krx_session()

        kst = pytz.timezone("Asia/Seoul")
        today = datetime.now(kst)
        from_date = (today - timedelta(days=30)).strftime("%Y%m%d")
        to_date = today.strftime("%Y%m%d")

        df = stock.get_market_trading_value_by_investor(from_date, to_date, "KOSPI")
        if df is None or df.empty:
            raise ValueError("pykrx 외국인 데이터 없음")

        # '외국인' 컬럼 찾기
        foreign_col = None
        for col in df.columns:
            if "외국인" in str(col):
                foreign_col = col
                break

        if foreign_col is None:
            raise ValueError(f"외국인 컬럼 없음: {df.columns.tolist()}")

        # 최근 15 거래일만 사용
        df = df.tail(15)
        foreign_values = df[foreign_col].tolist()

        consecutive = 0
        total_selling = 0
        for val in reversed(foreign_values):
            if val < 0:
                consecutive += 1
                total_selling += val
            else:
                break

        result["days"] = consecutive
        result["total_selling"] = total_selling
        result["is_consecutive"] = consecutive >= consecutive_days
        return result

    except Exception as e:
        logger.debug(f"pykrx 외국인 순매도 조회 실패, Gemini로 대체: {e}")

    # pykrx 실패 시 Gemini fallback (오늘 하루치만 반영)
    data = _fetch_kr_data_via_gemini()
    foreign_net = data.get("foreign_net")
    if foreign_net is not None and foreign_net < 0:
        result["days"] = 1
        result["total_selling"] = foreign_net
        result["is_consecutive"] = False  # 연속일수는 단일 API 호출로 확인 불가
    return result


def get_market_indices() -> dict:
    """
    주요 시장 지수를 반환합니다.

    Returns:
        dict: {
            "KOSPI": {"price": float, "prev_close": float, "change_pct": float},
            "KOSDAQ": {...},
            "S&P500": {...},
            "NASDAQ": {...},
            "DOW": {...}
        }
    """
    indices_map = {
        "KOSPI": "^KS11",
        "KOSDAQ": "^KQ11",
        "S&P500": "^GSPC",
        "NASDAQ": "^IXIC",
        "DOW": "^DJI",
    }

    result = {}
    for name, symbol in indices_map.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="2d")
            if hist.empty or len(hist) < 1:
                logger.warning(f"{name} ({symbol}) 데이터 없음")
                result[name] = {"price": None, "prev_close": None, "change_pct": None}
                continue

            price = float(hist["Close"].iloc[-1])
            if len(hist) >= 2:
                prev_close = float(hist["Close"].iloc[-2])
            else:
                prev_close = float(hist["Open"].iloc[-1])

            change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0.0
            result[name] = {
                "price": price,
                "prev_close": prev_close,
                "change_pct": change_pct,
            }
        except Exception as e:
            logger.error(f"{name} 지수 조회 실패: {e}")
            result[name] = {"price": None, "prev_close": None, "change_pct": None}

    return result
