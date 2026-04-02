import logging
from urllib.parse import quote

import feedparser

logger = logging.getLogger(__name__)


def search_google_news(
    query: str, lang: str = "ko", country: str = "KR", count: int = 5
) -> list:
    """
    Google News RSS를 통해 뉴스를 검색합니다.

    Args:
        query: 검색 쿼리
        lang: 언어 코드 (예: "ko", "en")
        country: 국가 코드 (예: "KR", "US")
        count: 반환할 뉴스 수

    Returns:
        list: [{"title": str, "link": str, "published": str, "summary": str}, ...]
    """
    try:
        encoded_query = quote(query)
        url = (
            f"https://news.google.com/rss/search"
            f"?q={encoded_query}&hl={lang}&gl={country}&ceid={country}:{lang}"
        )
        feed = feedparser.parse(url)

        results = []
        for entry in feed.entries[:count]:
            results.append(
                {
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "summary": entry.get("summary", ""),
                }
            )
        return results
    except Exception as e:
        logger.error(f"Google News 검색 실패 (query={query}): {e}")
        return []


def get_stock_news(name: str, ticker: str, market: str, count: int = 5) -> list:
    """
    종목에 관련된 최신 뉴스를 가져옵니다.

    Args:
        name: 종목 이름
        ticker: 종목 코드
        market: 시장 구분 ("KOSPI", "KOSDAQ", "US")
        count: 반환할 뉴스 수

    Returns:
        list: 뉴스 아이템 리스트
    """
    if market in ("KOSPI", "KOSDAQ"):
        query = f"{name} 주식"
        return search_google_news(query, lang="ko", country="KR", count=count)
    else:
        query = f"{ticker} stock"
        return search_google_news(query, lang="en", country="US", count=count)
