import logging
import sys
import time

import schedule

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def run_price_monitor():
    from src.jobs.price_monitor import main
    try:
        main()
    except Exception as e:
        logger.error(f"price_monitor 실행 중 오류: {e}", exc_info=True)


def main():
    logger.info("가격 모니터 스케줄러 시작 (1분 간격)")
    run_price_monitor()  # 시작 즉시 1회 실행
    schedule.every(2).minutes.do(run_price_monitor)

    while True:
        schedule.run_pending()
        time.sleep(5)


if __name__ == "__main__":
    main()
