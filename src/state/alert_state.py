import json
import logging
import os
from datetime import datetime, timedelta

import pytz

logger = logging.getLogger(__name__)

KST = pytz.timezone("Asia/Seoul")
STATE_FILE = ".state/alert_state.json"


class AlertState:
    """
    알림 상태를 관리하는 클래스.
    중복 알림 방지 및 가격 이력 추적을 담당합니다.
    """

    def __init__(self):
        os.makedirs(".state", exist_ok=True)
        self._state = self._load()

    def _load(self) -> dict:
        """파일에서 상태를 로드합니다."""
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"상태 파일 로드 실패, 새로 초기화합니다: {e}")
        return {
            "daily_alerts": {},
            "recent_alerts": {},
            "price_history": {},
        }

    def save(self):
        """현재 상태를 파일에 저장합니다."""
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
            logger.debug(f"상태 저장 완료: {STATE_FILE}")
        except Exception as e:
            logger.error(f"상태 파일 저장 실패: {e}")

    def can_send_five_pct_alert(self, yf_ticker: str) -> bool:
        """
        일간 5% 급등락 알림을 보낼 수 있는지 확인합니다.
        당일 이미 알림을 보낸 경우 False를 반환합니다.

        Args:
            yf_ticker: yfinance 티커 문자열

        Returns:
            bool: 알림 전송 가능 여부
        """
        today = datetime.now(KST).strftime("%Y-%m-%d")
        daily_alerts = self._state.get("daily_alerts", {})
        ticker_data = daily_alerts.get(yf_ticker, {})
        last_date = ticker_data.get("five_pct_date")
        return last_date != today

    def mark_five_pct_alert(self, yf_ticker: str):
        """
        일간 5% 알림을 오늘 보냈다고 표시합니다.

        Args:
            yf_ticker: yfinance 티커 문자열
        """
        today = datetime.now(KST).strftime("%Y-%m-%d")
        if "daily_alerts" not in self._state:
            self._state["daily_alerts"] = {}
        if yf_ticker not in self._state["daily_alerts"]:
            self._state["daily_alerts"][yf_ticker] = {}
        self._state["daily_alerts"][yf_ticker]["five_pct_date"] = today

    def can_send_alert(self, yf_ticker: str, cooldown_minutes: int = 10) -> bool:
        """
        쿨다운 시간이 지났는지 확인합니다.

        Args:
            yf_ticker: yfinance 티커 문자열
            cooldown_minutes: 쿨다운 시간 (분)

        Returns:
            bool: 알림 전송 가능 여부
        """
        recent_alerts = self._state.get("recent_alerts", {})
        ticker_data = recent_alerts.get(yf_ticker, {})
        last_alert_time_str = ticker_data.get("last_alert_time")

        if not last_alert_time_str:
            return True

        try:
            last_alert_time = datetime.fromisoformat(last_alert_time_str)
            now = datetime.now(KST)
            elapsed = (now - last_alert_time).total_seconds() / 60
            return elapsed > cooldown_minutes
        except Exception as e:
            logger.warning(f"쿨다운 시간 파싱 실패: {e}")
            return True

    def mark_alert_sent(self, yf_ticker: str):
        """
        알림을 보냈다고 표시합니다 (현재 KST 시각 기록).

        Args:
            yf_ticker: yfinance 티커 문자열
        """
        now = datetime.now(KST)
        if "recent_alerts" not in self._state:
            self._state["recent_alerts"] = {}
        if yf_ticker not in self._state["recent_alerts"]:
            self._state["recent_alerts"][yf_ticker] = {}
        self._state["recent_alerts"][yf_ticker]["last_alert_time"] = now.isoformat()

    def update_price(self, yf_ticker: str, price: float):
        """
        종목 가격 이력을 업데이트합니다. 최근 50개 항목을 유지합니다.

        Args:
            yf_ticker: yfinance 티커 문자열
            price: 현재 가격
        """
        now = datetime.now(KST)
        if "price_history" not in self._state:
            self._state["price_history"] = {}
        if yf_ticker not in self._state["price_history"]:
            self._state["price_history"][yf_ticker] = []

        self._state["price_history"][yf_ticker].append(
            {"price": price, "timestamp": now.isoformat()}
        )

        # 최근 50개만 유지
        if len(self._state["price_history"][yf_ticker]) > 50:
            self._state["price_history"][yf_ticker] = self._state["price_history"][
                yf_ticker
            ][-50:]

    def get_price_n_minutes_ago(
        self, yf_ticker: str, minutes: int
    ) -> float | None:
        """
        N분 전 가격을 반환합니다.

        Args:
            yf_ticker: yfinance 티커 문자열
            minutes: 몇 분 전 가격을 조회할지

        Returns:
            float | None: N분 전 가격, 없으면 None
        """
        history = self._state.get("price_history", {}).get(yf_ticker, [])
        if not history:
            return None

        now = datetime.now(KST)
        target_time = now - timedelta(minutes=minutes)
        tolerance = timedelta(minutes=minutes * 2)  # 2x 허용 범위

        closest = None
        closest_diff = None

        for entry in history:
            try:
                ts = datetime.fromisoformat(entry["timestamp"])
                diff = abs(ts - target_time)
                if diff <= tolerance:
                    if closest_diff is None or diff < closest_diff:
                        closest = entry["price"]
                        closest_diff = diff
            except Exception:
                continue

        return closest
