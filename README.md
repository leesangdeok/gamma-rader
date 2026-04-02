# Gamma Radar - 주식/금융 알림 서비스

Python 기반 주식 및 금융 정보 자동 알림 서비스입니다. GitHub Actions 스케줄러를 통해 주기적으로 실행되며, Telegram Bot으로 알림을 전송하고 Gemini AI로 시장 분석을 제공합니다.

---

## 주요 기능

### 1. 오전 시황 브리핑 (07:50 KST)
매일 아침 7시 50분에 다음 정보를 Telegram으로 전송합니다:
- **USD/KRW 환율**: 실시간 달러/원 환율
- **VIX 공포지수**: 25 이상 시 경고 알림
- **외국인 순매도 현황**: KOSPI 외국인 연속 순매도 일수 및 총액 (1조원 이상 경고)
- **미/한 국채 금리 스프레드**: 미국·한국 10년물 국채 금리차 (1.5%p 이상 경고)

### 2. 시장 시황 요약 (10:00 KST / 17:00 KST)
- **오전 10시**: 한국 시장 개장 후 주요 지수 및 AI 시황 분석
- **오후 5시**: 한국 시장 마감 + 미국 시장 동향 포함 종합 분석
- **Gemini AI 분석**: 최신 뉴스 기반 2-3문장 시황 요약
- **주요 지수**: KOSPI, KOSDAQ, S&P500, NASDAQ, DOW

### 3. 주가 급등락 모니터링 (5분마다)
- **일간 급등락 알림**: 전일 종가 대비 ±5% 이상 변동 시
  - 관련 뉴스 자동 수집 (Google News RSS)
  - Gemini AI 원인 분석
  - 당일 1회 중복 알림 방지
- **단기 급변 알림**: 최근 5분 대비 ±3% 이상 변동 시
  - 쿨다운 10분 (동일 종목 중복 알림 방지)

---

## 아키텍처

```
GitHub Actions (Scheduler)
        │
        ├── morning_report.yml  (07:50 KST)
        ├── market_summary.yml  (10:00, 17:00 KST)
        └── price_monitor.yml   (5분마다)
                │
                ▼
        Python Scripts (src/jobs/)
                │
        ┌───────┼───────────┐
        │       │           │
        ▼       ▼           ▼
   collectors  analyzers  notifiers
        │       │           │
   yfinance  Gemini API  Telegram Bot
   pykrx        │           │
   Google News  └───────────┘
```

### 디렉토리 구조
```
gamma-rader/
├── .github/
│   └── workflows/
│       ├── morning_report.yml
│       ├── market_summary.yml
│       └── price_monitor.yml
├── config/
│   ├── settings.yaml          # 알림 임계값 설정
│   └── watchlist.yaml         # 모니터링 종목 목록
├── src/
│   ├── collectors/
│   │   ├── market_data.py     # 시장 데이터 수집 (환율, VIX, 금리 등)
│   │   ├── stock_data.py      # 개별 종목 가격 수집
│   │   └── news.py            # Google News RSS 뉴스 수집
│   ├── analyzers/
│   │   └── gemini_analyzer.py # Gemini AI 분석
│   ├── notifiers/
│   │   └── telegram_notifier.py # Telegram 알림 전송
│   ├── state/
│   │   └── alert_state.py     # 알림 상태 관리 (중복 방지)
│   ├── utils/
│   │   └── market_hours.py    # 장 운영 시간 체크
│   └── jobs/
│       ├── morning_report.py  # 오전 시황 브리핑
│       ├── market_summary.py  # 시장 시황 요약
│       └── price_monitor.py   # 주가 모니터링
├── requirements.txt
└── README.md
```

---

## 설정 방법

### GitHub Secrets 설정

GitHub 저장소의 **Settings > Secrets and variables > Actions** 에서 다음 시크릿을 추가하세요:

| 시크릿 이름 | 설명 | 획득 방법 |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | Telegram 봇 토큰 | [@BotFather](https://t.me/BotFather)에서 봇 생성 후 토큰 발급 |
| `TELEGRAM_CHAT_ID` | 알림 받을 채팅 ID | [@userinfobot](https://t.me/userinfobot)에서 자신의 Chat ID 확인 |
| `GEMINI_API_KEY` | Google Gemini API 키 | [Google AI Studio](https://aistudio.google.com/)에서 발급 |

#### Telegram Bot 설정 방법
1. Telegram에서 `@BotFather` 검색
2. `/newbot` 명령어로 봇 생성
3. 봇 이름 및 username 설정
4. 발급된 토큰을 `TELEGRAM_BOT_TOKEN`에 저장
5. 봇과 대화 시작 후 `@userinfobot`에서 Chat ID 확인
6. Chat ID를 `TELEGRAM_CHAT_ID`에 저장

#### Gemini API 설정 방법
1. [Google AI Studio](https://aistudio.google.com/) 접속
2. "Get API Key" 클릭
3. 발급된 API 키를 `GEMINI_API_KEY`에 저장

---

## watchlist.yaml 설정 가이드

`config/watchlist.yaml` 파일에서 모니터링할 종목을 설정합니다:

```yaml
stocks:
  # 한국 주식 (KOSPI)
  - name: "삼성전자"          # 표시 이름
    ticker: "005930"          # 종목 코드
    market: "KOSPI"           # 시장 구분: KOSPI, KOSDAQ, US

  # 한국 주식 (KOSDAQ)
  - name: "카카오"
    ticker: "035720"
    market: "KOSDAQ"

  # 미국 주식
  - name: "Apple"
    ticker: "AAPL"
    market: "US"

  # 한국 ETF
  - name: "KODEX 200"
    ticker: "069500"
    market: "KOSPI"

  # 미국 ETF
  - name: "S&P500 ETF"
    ticker: "SPY"
    market: "US"
```

### 지원 시장 구분

| market 값 | 설명 | yfinance 변환 |
| --- | --- | --- |
| `KOSPI` | 한국 유가증권시장 | `{ticker}.KS` |
| `KOSDAQ` | 한국 코스닥시장 | `{ticker}.KQ` |
| `US` | 미국 주식/ETF | `{ticker}` (그대로) |

---

## settings.yaml 설정 가이드

```yaml
alerts:
  daily_change_threshold_pct: 5.0     # 일간 급등락 기준 (%)
  short_change_threshold_pct: 3.0     # 단기 급변 기준 (%)
  short_change_interval_minutes: 5    # 단기 변동 기준 시간 (분): 5 또는 15
  cooldown_minutes: 10                # 중복 알림 방지 시간 (분)

thresholds:
  vix_warning: 25.0                   # VIX 경고 기준
  yield_spread_warning: 1.5           # 미/한 금리차 경고 기준 (%p)
  foreign_selling_warning_trillion: 1.0  # 외국인 순매도 경고 기준 (조원)
  foreign_selling_consecutive_days: 3    # 연속 매도 기준 일수

timezone: "Asia/Seoul"
```

---

## 로컬 테스트 방법

### 환경 설정

```bash
# 저장소 클론
git clone https://github.com/YOUR_USERNAME/gamma-rader.git
cd gamma-rader

# Python 가상환경 생성 (권장)
python3.11 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 환경 변수 설정

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
export TELEGRAM_CHAT_ID="your_chat_id_here"
export GEMINI_API_KEY="your_gemini_api_key_here"
export PYTHONPATH=$(pwd)
```

### 각 스크립트 실행

```bash
# 오전 시황 브리핑 테스트
python src/jobs/morning_report.py

# 시장 시황 요약 테스트
python src/jobs/market_summary.py

# 주가 모니터링 테스트 (장 시간 외에는 바로 종료됨)
python src/jobs/price_monitor.py
```

### 데이터 수집 모듈 테스트

```bash
python -c "
from src.collectors.market_data import get_usd_krw, get_vix, get_market_indices
print('USD/KRW:', get_usd_krw())
print('VIX:', get_vix())
print('Indices:', get_market_indices())
"
```

---

## GitHub Actions 무료 티어 안내

| 저장소 종류 | 무료 실행 시간 | 비고 |
| --- | --- | --- |
| **공개(Public) 저장소** | **무제한** | 완전 무료 |
| 비공개(Private) 저장소 | 2,000분/월 | 초과 시 과금 |

### 예상 실행 시간 계산 (Private 저장소 기준)
- 오전 브리핑: ~2분 × 22일 = 44분/월
- 시황 요약: ~2분 × 2회 × 22일 = 88분/월
- 가격 모니터링: ~1분 × 12회/일 × 22일 × 2(한/미 시장) ≒ 528분/월
- **총 예상**: ~660분/월 (2,000분 한도의 33%)

**권장**: 비용 절감을 위해 **공개 저장소**로 설정하거나, 가격 모니터링 빈도를 조정하세요.

---

## 기술 스택

| 분류 | 기술 |
| --- | --- |
| 언어 | Python 3.11 |
| 스케줄러 | GitHub Actions |
| 알림 | Telegram Bot API |
| AI 분석 | Google Gemini 2.0 Flash |
| 주식 데이터 | yfinance (미국/글로벌) |
| 한국 주식 데이터 | pykrx |
| 뉴스 | Google News RSS (feedparser) |

---

## 라이선스

MIT License