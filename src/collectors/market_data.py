import logging
from datetime import datetime, timedelta

import pytz
import yfinance as yf

logger = logging.getLogger(__name__)


def get_usd_krw() -> dict:
    """USD/KRW 환율과 전일 대비 변동을 반환합니다."""
    empty = {"rate": None, "change": None, "change_pct": None}
    try:
        ticker = yf.Ticker("KRW=X")
        hist = ticker.history(period="2d")
        if hist.empty:
            logger.warning("USD/KRW 데이터를 가져오지 못했습니다.")
            return empty
        rate = float(hist["Close"].iloc[-1])
        if len(hist) >= 2:
            prev = float(hist["Close"].iloc[-2])
            change = rate - prev
            change_pct = (change / prev * 100) if prev else 0.0
        else:
            change, change_pct = None, None
        return {"rate": rate, "change": change, "change_pct": change_pct}
    except Exception as e:
        logger.error(f"USD/KRW 조회 실패: {e}")
        return empty


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


_gemini_cache: dict | None = None


def _fetch_all_via_gemini() -> dict:
    """
    Gemini Google Search로 전일 기준 시장 데이터를 한 번에 조회합니다.
    같은 프로세스 내에서는 캐시된 결과를 반환합니다.
    """
    global _gemini_cache
    if _gemini_cache is not None:
        return _gemini_cache

    import json
    import os
    import re

    result = {
        "kr_10y_yield": None,
        "night_futures_price": None,
        "night_futures_change": None,
        "night_futures_change_pct": None,
        "foreign_selling_days": 0,
        "foreign_selling_total_trillion": 0.0,
    }

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        _gemini_cache = result
        return result

    kst = pytz.timezone("Asia/Seoul")
    today = datetime.now(kst)
    # 월요일이면 금요일로
    days_back = 3 if today.weekday() == 0 else 1
    prev_day = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=(
                f"{prev_day} 기준(가장 최근 거래일) 한국 금융시장 데이터를 검색해서 "
                "아래 JSON 형식으로만 답해줘. 다른 텍스트 없이 JSON만 출력.\n"
                '{"kr_10y_yield": 3.691, "night_futures_price": 374.50, '
                '"night_futures_change": -1.20, "night_futures_change_pct": -0.32, '
                '"foreign_selling_days": 3, "foreign_selling_total_trillion": -2.5}\n'
                "- kr_10y_yield: 한국 국고채 10년물 금리 (% 단위 float)\n"
                "- night_futures_price: KOSPI200 야간선물 종가 (float, 데이터 없으면 null)\n"
                "- night_futures_change: 야간선물 전일 대비 등락 (float, 없으면 null)\n"
                "- night_futures_change_pct: 야간선물 등락률 (% 단위 float, 없으면 null)\n"
                "- foreign_selling_days: KOSPI 외국인 연속 순매도 일수 (int, 순매수이면 0)\n"
                "- foreign_selling_total_trillion: 연속 순매도 누적 금액 (조원 float, 순매도면 음수)"
            ),
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            ),
        )
        text = response.text.strip()
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        data = json.loads(text.strip())

        for key in ("kr_10y_yield", "night_futures_price", "night_futures_change", "night_futures_change_pct"):
            if isinstance(data.get(key), (int, float)):
                result[key] = float(data[key])
        if isinstance(data.get("foreign_selling_days"), (int, float)):
            result["foreign_selling_days"] = int(data["foreign_selling_days"])
        if isinstance(data.get("foreign_selling_total_trillion"), (int, float)):
            result["foreign_selling_total_trillion"] = float(data["foreign_selling_total_trillion"])

        logger.info(
            f"Gemini 일괄 조회 완료 ({prev_day}) - "
            f"KR10Y: {result['kr_10y_yield']}%, "
            f"야간선물: {result['night_futures_price']}, "
            f"외국인 순매도: {result['foreign_selling_days']}일"
        )
    except Exception as e:
        logger.warning(f"Gemini 일괄 조회 실패: {e}")

    _gemini_cache = result
    return result


def get_kr_10y_yield() -> float | None:
    """한국 10년물 국채 금리(%)를 반환합니다. pykrx 실패 시 Gemini로 대체."""
    try:
        from pykrx import bond

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

    return _fetch_all_via_gemini().get("kr_10y_yield")


def _get_foreign_net_selling_via_kis(consecutive_days: int) -> dict | None:
    """
    KIS Developers API로 KOSPI 외국인 순매매 현황을 조회합니다.

    사용 API: 시장별 투자자매매동향(일별) [국내주식-075]
      - endpoint: /uapi/domestic-stock/v1/quotations/inquire-investor-daily-by-market
      - tr_id: FHPTJ04040000
      - 응답 output 배열: 날짜 오름차순, frgn_ntby_tr_pbmn = 외국인 순매수금액(원, 음수이면 순매도)
    """
    from src.collectors import kis_client

    kst = pytz.timezone("Asia/Seoul")
    today = datetime.now(kst)
    from_date = (today - timedelta(days=30)).strftime("%Y%m%d")
    to_date = today.strftime("%Y%m%d")

    data = kis_client.get(
        path="/uapi/domestic-stock/v1/quotations/inquire-investor-daily-by-market",
        tr_id="FHPTJ04040000",
        params={
            "FID_COND_MRKT_DIV_CODE": "J",    # 유가증권(KOSPI)
            "FID_INPUT_ISCD": "0001",          # KOSPI 종합
            "FID_INPUT_DATE_1": from_date,
            "FID_INPUT_DATE_2": to_date,
        },
    )
    if not data:
        return None

    rows = data.get("output") or []
    if not rows:
        return None

    # 최근 15 거래일
    rows = rows[-15:]
    foreign_values = []
    for row in rows:
        raw = row.get("frgn_ntby_tr_pbmn", "0").replace(",", "").replace("+", "")
        try:
            foreign_values.append(int(raw))
        except ValueError:
            foreign_values.append(0)

    consecutive = 0
    total_selling = 0
    for val in reversed(foreign_values):
        if val < 0:
            consecutive += 1
            total_selling += val
        else:
            break

    return {
        "is_consecutive": consecutive >= consecutive_days,
        "days": consecutive,
        "total_selling": total_selling,
    }


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

    # 1순위: KIS Developers API
    try:
        kis_result = _get_foreign_net_selling_via_kis(consecutive_days)
        if kis_result is not None:
            return kis_result
    except Exception as e:
        logger.debug(f"KIS 외국인 순매도 조회 실패, pykrx로 대체: {e}")

    # 2순위: pykrx
    try:
        from pykrx import stock

        kst = pytz.timezone("Asia/Seoul")
        today = datetime.now(kst)
        from_date = (today - timedelta(days=30)).strftime("%Y%m%d")
        to_date = today.strftime("%Y%m%d")

        df = stock.get_market_trading_value_by_investor(from_date, to_date, "KOSPI")
        if df is None or df.empty:
            raise ValueError("pykrx 외국인 데이터 없음")

        foreign_col = None
        for col in df.columns:
            if "외국인" in str(col):
                foreign_col = col
                break

        if foreign_col is None:
            raise ValueError(f"외국인 컬럼 없음: {df.columns.tolist()}")

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
        logger.debug(f"pykrx 외국인 순매도 조회 실패: {e}")

    # 3순위: Gemini
    g = _fetch_all_via_gemini()
    days = g["foreign_selling_days"]
    total_trillion = g["foreign_selling_total_trillion"]
    if days > 0 or total_trillion != 0.0:
        return {
            "is_consecutive": days >= consecutive_days,
            "days": days,
            "total_selling": int(total_trillion * 1_000_000_000_000),
        }

    return result


def _get_night_futures_via_kis() -> dict | None:
    """
    KIS Developers API로 KOSPI200 야간선물 현재가를 조회합니다.

    사용 API: 선물옵션 현재가 [v1_국내선물-006]
      - endpoint: /uapi/domestic-futureoption/v1/quotations/inquire-price
      - tr_id: FHMIF10000000
      - FID_COND_MRKT_DIV_CODE: "F" (지수선물)
      - FID_INPUT_ISCD: KOSPI200 야간선물 근월물 종목코드
      - 응답 output1 필드: futs_prpr(현재가), futs_prdy_vrss(전일대비), futs_prdy_ctrt(등락률)
    """
    from src.collectors import kis_client

    iscd = kis_client.get_kospi200_futures_front_month_code()
    data = kis_client.get(
        path="/uapi/domestic-futureoption/v1/quotations/inquire-price",
        tr_id="FHMIF10000000",
        params={
            "FID_COND_MRKT_DIV_CODE": "F",
            "FID_INPUT_ISCD": iscd,
        },
    )
    if not data:
        return None

    output = data.get("output1") or {}
    if not output:
        return None

    def _f(key: str) -> float | None:
        raw = output.get(key, "").replace(",", "").replace("+", "")
        try:
            return float(raw) if raw else None
        except ValueError:
            return None

    price = _f("futs_prpr")        # 선물 현재가
    change = _f("futs_prdy_vrss")  # 선물 전일 대비
    change_pct = _f("futs_prdy_ctrt")  # 선물 등락률

    if not price:
        return None

    logger.info(f"KIS 야간선물 조회 완료 - {iscd}: {price} ({change_pct}%)")
    return {"price": price, "change": change, "change_pct": change_pct}


def get_kospi_night_futures() -> dict:
    """
    KOSPI 야간 선물 현황을 반환합니다.

    Returns:
        dict: {"price": float|None, "change": float|None, "change_pct": float|None}
    """
    empty = {"price": None, "change": None, "change_pct": None}

    # 1순위: KIS Developers API
    try:
        result = _get_night_futures_via_kis()
        if result is not None:
            return result
    except Exception as e:
        logger.debug(f"KIS 야간선물 조회 실패: {e}")

    # 2순위: Gemini (전일 종가 기준)
    g = _fetch_all_via_gemini()
    if g["night_futures_price"] is not None:
        return {
            "price": g["night_futures_price"],
            "change": g["night_futures_change"],
            "change_pct": g["night_futures_change_pct"],
        }

    return empty


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
