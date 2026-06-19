# KIS 실시간 주식 시세 for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2023.1%2B-blue)](https://www.home-assistant.io/)

한국투자증권(KIS) API를 사용하여 국내 주식/ETF 실시간 시세와 코스피/코스닥 지수를 Home Assistant sensor로 제공합니다.

## 특징

- **실시간 체결가** - KIS WebSocket(H0STCNT0) 기반, rate limit 영향 없음
- **코스피/코스닥 지수** - REST API polling 방식
- **장외 자동 처리** - 장마감 후 종가 자동 조회, 장 시작 시 자동 재연결
- **HA UI 설정** - App Key/Secret, 종목 추가/삭제, 업데이트 간격 모두 UI에서 설정
- **풍부한 데이터** - 현재가, 등락률, 시/고/저, 거래량, 체결강도, PER/PBR, 외국인비율 등

## 설치

### HACS (권장)

1. HACS → 통합구성요소 → 우측 상단 메뉴 → **사용자 정의 저장소**
2. URL: `https://github.com/YOUR_GITHUB_ID/kis_realtime_ha` / 범주: Integration
3. **KIS 실시간 주식 시세** 검색 후 설치
4. Home Assistant 재시작

### 수동 설치

1. 이 저장소의 `custom_components/kis_realtime` 폴더를
   `/homeassistant/custom_components/kis_realtime/` 에 복사
2. Home Assistant 재시작

## 설정

### 1. KIS Developers에서 App Key 발급

[KIS Developers](https://apiportal.koreainvestment.com) 접속 → 앱 등록 → App Key / App Secret 발급

### 2. HA 통합구성요소 추가

**설정 → 통합구성요소 → 추가 → `KIS 실시간 주식 시세`**

| 항목 | 설명 |
|---|---|
| App Key | KIS Developers에서 발급한 App Key |
| App Secret | KIS Developers에서 발급한 App Secret |
| API URL | 기본값 사용 권장 |
| 종목 업데이트 간격 | WebSocket 업데이트 최소 간격 (1~60초, 기본 3초) |
| 지수 polling 간격 | 코스피/코스닥 REST 조회 간격 (10~300초, 기본 30초) |

### 3. 종목/지수 추가

통합구성요소 → KIS 실시간 주식 시세 → **설정(옵션)**

- **종목 추가**: 종목코드(6자리) + entity 이름 입력
- **지수 추가**: 코스피(0001) / 코스닥(1001) 선택
- **종목 삭제**: 목록에서 선택 후 삭제

## 생성되는 Sensor

### 종목 Sensor (`sensor.kis_{entity}`)

| Attribute | 설명 |
|---|---|
| `price` | 현재가 (KRW) |
| `change` | 전일대비 |
| `change_rate` | 등락률 (%) |
| `sign` | 등락 방향 (↑/↓/→) |
| `open` / `high` / `low` | 시가/고가/저가 |
| `acc_volume` | 누적거래량 |
| `acc_amount` | 누적거래대금 |
| `strength` | 체결강도 |
| `buy_ratio` | 매수비율 (%) |
| `week52_high` / `week52_low` | 52주 최고/최저가 |
| `per` / `pbr` / `eps` / `bps` | 밸류에이션 지표 |
| `foreign_rate` | 외국인 보유율 (%) |
| `market_cap` | 시가총액 (억원) |

### 지수 Sensor (`sensor.kis_{entity}`)

| Attribute | 설명 |
|---|---|
| `price` | 현재 지수 (pt) |
| `change` / `change_rate` | 전일대비 / 등락률 |
| `open` / `high` / `low` | 시가/고가/저가 |
| `acc_volume` | 누적거래량 |

## 사전 요구사항

- Home Assistant 2023.1 이상
- KIS Developers App Key/Secret

> **참고**: v1.2.0부터 `kis_token_cache.json` 파일이 불필요합니다.  
> App Key/Secret으로 access token을 자동 발급하며 24시간마다 자동 갱신됩니다.

## 장 운영 시간

| 시간 | 동작 |
|---|---|
| 09:00 ~ 15:30 | WebSocket 실시간 체결가 수신 |
| 15:30 장마감 | REST API로 종가 자동 조회 |
| 장외 / 주말 | 마지막 종가 유지, 09:00 자동 재연결 |

## 문제 해결

### sensor가 생성되지 않는 경우
- HA 로그에서 `kis_realtime` 오류 확인
- App Key/Secret 유효성 확인

### 종가가 0으로 나오는 경우
- App Key/Secret 유효성 확인
- HA 로그에서 `access token 발급 실패` 메시지 확인

### WebSocket 연결이 바로 끊기는 경우
- 장외 시간(주말/공휴일)에는 정상 동작입니다
- 평일 09:00 이후 자동 재연결됩니다

## License

MIT License
