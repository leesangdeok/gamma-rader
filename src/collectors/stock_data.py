import logging

import yfinance as yf

logger = logging.getLogger(__name__)


def get_yfinance_ticker(ticker: str, market: str) -> str:
    """
    종목 코드와 시장을 받아 yfinance용 티커 문자열로 변환합니다.

    Args:
        ticker: 종목 코드 (예: "005930", "AAPL")
        market: 시장 구분 ("KOSPI", "KOSDAQ", "US")

    Returns:
        str: yfinance 티커 (예: "005930.KS", "035420.KQ", "AAPL")
    """
    if market == "KOSPI":
        return f"{ticker}.KS"
    elif market == "KOSDAQ":
        return f"{ticker}.KQ"
    else:
        return ticker


def get_current_price(ticker: str, market: str) -> dict | None:
    """
    현재 주가 정보를 반환합니다.

    Args:
        ticker: 종목 코드
        market: 시장 구분

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

        # 장중 인트라데이 데이터 시도
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

        if prev_close is None or prev_close == 0:
            change_pct = 0.0
        else:
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
