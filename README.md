# KIS 실시간 주식 시세 for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2023.1%2B-blue)](https://www.home-assistant.io/)
[![Version](https://img.shields.io/badge/Version-1.6.0-green)]()

한국투자증권(KIS) API를 사용하여 국내 주식/ETF 실시간 시세와 코스피/코스닥 지수를 Home Assistant sensor로 제공합니다.

## 특징

- **실시간 체결가** - KIS WebSocket(H0STCNT0) 기반, rate limit 영향 없음
- **코스피/코스닥 지수** - REST API polling 방식
- **장외 자동 처리** - 장마감 후 종가 자동 조회, 장 시작 시 자동 재연결
- **HA UI 설정** - App Key/Secret, 종목 추가/삭제, 업데이트 간격 모두 UI에서 설정
- **한글 이름 지원** - sensor 표시 이름을 한글로 설정 가능
- **풍부한 데이터** - 현재가, 등락률, 시/고/저, 거래량, 체결강도, PER/PBR, 외국인비율 등

## 설치

### HACS (권장)

1. HACS → 통합구성요소 → 우측 상단 메뉴(점 3개) → **사용자 정의 저장소**
2. URL: `https://github.com/kim2140/kis_realtime_ha` / 범주: `Integration`
3. **KIS 실시간 주식 시세** 검색 후 다운로드
4. Home Assistant 재시작

### 수동 설치

1. 이 저장소의 `custom_components/kis_realtime` 폴더를 `/homeassistant/custom_components/kis_realtime/` 에 복사
2. Home Assistant 재시작

## KIS Developers App Key 발급

### 1. 한국투자증권 계좌 준비
- 한국투자증권 계좌 및 HTS ID 필요

### 2. 오픈API 서비스 신청
1. [한국투자증권 홈페이지](https://www.truefriend.com) 로그인
2. **뱅킹/서비스 → 오픈API** 접속
3. **오픈API 서비스 신청하기** 클릭
4. 계좌번호 선택 후 신청
5. 카카오톡 알림톡으로 KIS Developers 임시 비밀번호 수신

### 3. App Key / App Secret 발급
1. [KIS Developers](https://apiportal.koreainvestment.com) 접속
2. HTS ID + 임시 비밀번호로 로그인
3. **마이페이지** → **App Key / App Secret 복사**

> ⚠️ App Key와 App Secret은 외부에 노출되지 않도록 주의하세요.

## 설정

### 1. 통합구성요소 추가

**설정 → 장치 및 서비스 → 통합구성요소 추가 → `KIS 실시간 주식 시세`**

| 항목 | 설명 |
|---|---|
| App Key | KIS Developers에서 발급한 App Key |
| App Secret | KIS Developers에서 발급한 App Secret |
| 실시간 시세 업데이트 간격 | 장중 WebSocket 업데이트 최소 간격 (1~60초, 기본 3초) |
| 지수 조회 간격 | 코스피/코스닥 REST 조회 간격 (10~300초, 기본 30초) |

### 2. 종목/지수 추가

통합구성요소 → KIS 실시간 주식 시세 → **설정(⚙️)**

#### 종목 추가 (ETF/개별주)
1. **종목 추가** 선택
2. 종목코드 6자리 입력 (예: `069500`)
3. 한글 종목명이 자동 조회되어 표시 이름으로 제안됨
4. 표시 이름 확인/수정 후 Submit

> ⏱️ **참고**: 종목 추가 직후 sensor 값이 나타나지 않을 수 있습니다. KIS API token 발급 제한(1분 1회)으로 인해 **최대 1분 후** 데이터가 표시됩니다.

#### 지수 추가 (코스피/코스닥)
1. **지수 추가** 선택
2. 코스피(0001) 또는 코스닥(1001) 선택
3. 표시 이름 확인/수정 후 Submit

#### 종목/지수 삭제
1. **종목/지수 삭제** 선택
2. 삭제할 항목 체크 후 Submit → 즉시 삭제

## 생성되는 Sensor

### 종목 Sensor (`sensor.kis_stock_{코드}`)

| Attribute | 설명 |
|---|---|
| `price` | 현재가 (KRW) |
| `change` / `change_rate` | 전일대비 / 등락률 (%) |
| `sign` | 등락 방향 (↑/↓/→) |
| `open` / `high` / `low` | 시가/고가/저가 |
| `acc_volume` / `acc_amount` | 누적거래량 / 누적거래대금 |
| `strength` / `buy_ratio` | 체결강도 / 매수비율 (장중만) |
| `week52_high` / `week52_low` | 52주 최고/최저가 |
| `per` / `pbr` / `eps` / `bps` | 밸류에이션 지표 |
| `foreign_rate` | 외국인 보유율 (%) |
| `market_cap` | 시가총액 (억원) |

### 지수 Sensor (`sensor.kis_kospi`, `sensor.kis_kosdaq`)

| Attribute | 설명 |
|---|---|
| `price` | 현재 지수 (pt) |
| `change` / `change_rate` | 전일대비 / 등락률 |
| `open` / `high` / `low` | 시가/고가/저가 |
| `acc_volume` | 누적거래량 |

## 장 운영 시간

| 시간 | 동작 |
|---|---|
| 09:00 ~ 15:30 | WebSocket 실시간 체결가 수신 |
| 15:30 장마감 | REST API로 종가 자동 조회 |
| 장외 / 주말 | 마지막 종가 유지, 09:00 자동 재연결 |

## 문제 해결

### 종목 추가 후 값이 안 나오는 경우
- KIS API token 발급은 **1분에 1회** 제한이 있습니다
- 종목 추가 후 **최대 1분** 기다리면 자동으로 데이터가 표시됩니다
- 장외 시간(주말/공휴일)에도 **종가 기준으로 데이터가 표시**됩니다

### sensor 값이 Unknown인 경우
- 종목 추가 직후일 수 있습니다. **최대 1분** 기다려주세요
- 1분 후에도 Unknown이면 HA 로그에서 `kis_realtime` 오류를 확인해주세요
- 장외/주말에도 종가는 정상적으로 표시됩니다. Unknown이 지속되면 App Key/Secret을 확인해주세요

### App Key 오류
- KIS Developers에서 App Key/Secret 유효성 확인
- 오픈API 서비스 신청 여부 확인

## 변경 이력

### v1.6.0
- entity ID 자동 생성 (`stock_{코드}`)
- 표시 이름(friendly name) 한글 지원
- 종목 추가 시 한글 종목명 자동 조회
- 종목/지수 삭제 즉시 반영
- KIS token 1분 제한 오류 처리 개선
- 업데이트 간격 슬라이더 UI

### v1.0.0
- 최초 릴리즈

## License

MIT License
