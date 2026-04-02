import logging
import os

import requests

logger = logging.getLogger(__name__)


def send_message(text: str, parse_mode: str = "HTML") -> bool:
    """
    Telegram 봇을 통해 메시지를 전송합니다.

    Args:
        text: 전송할 메시지 텍스트 (HTML 형식 지원)
        parse_mode: 파싱 모드 ("HTML" 또는 "Markdown")

    Returns:
        bool: 전송 성공 여부
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token:
        logger.error("TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않았습니다.")
        return False
    if not chat_id:
        logger.error("TELEGRAM_CHAT_ID 환경변수가 설정되지 않았습니다.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    separator = "\n\n━━━━━━━━━━━━━━━━━"
    payload = {
        "chat_id": chat_id,
        "text": text + separator,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        if result.get("ok"):
            logger.info("Telegram 메시지 전송 성공")
            return True
        else:
            logger.error(f"Telegram 메시지 전송 실패: {result}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Telegram API 요청 실패: {e}")
        return False
    except Exception as e:
        logger.error(f"Telegram 메시지 전송 중 오류 발생: {e}")
        return False
