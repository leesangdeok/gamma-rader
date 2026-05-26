import logging

import yfinance as yf

logger = logging.getLogger(__name__)


def get_yfinance_ticker(ticker: str, market: str) -> str:
    """
    종목 코드와 시장을 받아 yfinance용 티커 문자열로 변환합니다.

    Args:
        ticker: 종목 코드 (예: "005930", "AAPL")
        market: 시장 구분 ("KOSPI", "KOSDAQ", "US", "NXT_KOSPI", "NXT_KOSDAQ")

    Returns:
        str: yfinance 티커 (예: "005930.KS", "035420.KQ", "AAPL")
    """
    if market in ("KOSPI", "NXT_KOSPI"):
        return f"{ticker}.KS"
    elif market in ("KOSDAQ", "NXT_KOSDAQ"):
        return f"{ticker}.KQ"
    else:
        return ticker


def _get_price_via_yfinance(ticker: str, market: str) -> dict | None:
    """yfinance를 통해 주가를 조회합니다. KRX 정규 시간에만 신뢰할 수 있습니다."""
    yf_ticker = get_yfinance_ticker(ticker, market)
    try:
        t = yf.Ticker(yf_ticker)
        hist = t.history(period="2d")

        price = None
        prev_close = None

        if not hist.empty:
            if len(hist) >= 2:
                price = float(hist["Close"].iloc[-1])
                prev_close = float(hist["Close"].iloc[-2])
            elif len(hist) == 1:
                price = float(hist["Close"].iloc[-1])
                prev_close = float(hist["Open"].iloc[-1])

        if price is None:
            try:
                intraday = t.history(period="1d", interval="5m")
                if not intraday.empty:
                    price = float(intraday["Close"].iloc[-1])
            except Exception as e:
                logger.debug(f"{yf_ticker} 인트라데이 조회 실패: {e}")

        if price is None:
            logger.warning(f"{yf_ticker} 가격 데이터를 가져오지 못했습니다.")
            return None

        change_pct = 0.0
        if prev_close and prev_close != 0:
            change_pct = (price - prev_close) / prev_close * 100

        return {
            "ticker": ticker,
            "yf_ticker": yf_ticker,
            "market": market,
            "price": price,
            "prev_close": prev_close,
            "change_pct": change_pct,
        }
    except Exception as e:
        logger.error(f"{yf_ticker} 가격 조회 실패: {e}")
        return None


def _parse_kis_output(output: dict, ticker: str, market: str) -> dict | None:
    """KIS API output 딕셔너리를 파싱해 표준 가격 dict를 반환합니다."""
    def _f(key: str) -> float | None:
        raw = output.get(key, "").replace(",", "").replace("+", "")
        try:
            return float(raw) if raw else None
        except ValueError:
            return None

    price = _f("stck_prpr")
    prev_close = _f("stck_sdpr")
    change_pct = _f("prdy_ctrt")

    if not price:
        return None

    if change_pct is None and prev_close and prev_close != 0:
        change_pct = (price - prev_close) / prev_close * 100

    return {
        "ticker": ticker,
        "yf_ticker": get_yfinance_ticker(ticker, market),
        "market": market,
        "price": price,
        "prev_close": prev_close,
        "change_pct": change_pct or 0.0,
    }


def _get_price_via_kis(ticker: str, market: str) -> dict | None:
    """KIS API를 통해 국내 주가(KOSPI/KOSDAQ/NXT)를 조회합니다."""
    try:
        from src.collectors import kis_client

        data = kis_client.get(
            path="/uapi/domestic-stock/v1/quotations/inquire-price",
            tr_id="FHKST01010100",
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": ticker,
            },
        )
        if data:
            return _parse_kis_output(data.get("output") or {}, ticker, market)
    except Exception as e:
        logger.debug(f"KIS 조회 실패 ({ticker}): {e}")
    return None


def _get_nxt_price(ticker: str, market: str) -> dict | None:
    """NXT(넥스트트레이드) 종목 현재가를 조회합니다. KIS API 우선, yfinance 폴백."""
    result = _get_price_via_kis(ticker, market)
    if result:
        return result
    logger.debug(f"NXT {ticker} yfinance 폴백 시도")
    return _get_price_via_yfinance(ticker, market)


def get_current_price(ticker: str, market: str) -> dict | None:
    """
    현재 주가 정보를 반환합니다.

    Args:
        ticker: 종목 코드
        market: 시장 구분 ("KOSPI", "KOSDAQ", "US", "NXT_KOSPI", "NXT_KOSDAQ")

    Returns:
        dict | None: {
            "ticker": str,
            "yf_ticker": str,
            "market": str,
            "price": float,
            "prev_close": float,
            "change_pct": float
        }
    """
    if market in ("NXT_KOSPI", "NXT_KOSDAQ"):
        return _get_nxt_price(ticker, market)

    if market in ("KOSPI", "KOSDAQ"):
        result = _get_price_via_kis(ticker, market)
        if result:
            return result
        logger.debug(f"{ticker} KIS 조회 실패, yfinance 폴백")

    return _get_price_via_yfinance(ticker, market)


def get_stock_prices(watchlist: list) -> list:
    """
    watchlist 설정 리스트에 있는 모든 종목의 현재 가격을 조회합니다.

    Args:
        watchlist: [{"name": str, "ticker": str, "market": str}, ...]

    Returns:
        list: 각 종목의 가격 정보 dict 리스트 (name 필드 포함)
    """
    results = []
    for item in watchlist:
        name = item.get("name", "")
        ticker = item.get("ticker", "")
        market = item.get("market", "US")

        price_data = get_current_price(ticker, market)
        if price_data is not None:
            price_data["name"] = name
            results.append(price_data)
        else:
            logger.warning(f"{name} ({ticker}) 가격 조회 실패, 건너뜁니다.")

    return results