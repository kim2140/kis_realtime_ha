# KIS 실시간 주식 시세 for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2023.1%2B-blue)](https://www.home-assistant.io/)
[![Version](https://img.shields.io/badge/Version-1.3.1.3-orange)]()

한국투자증권(KIS) API를 사용하여 국내 주식/ETF 실시간 시세와 코스피/코스닥 지수를 Home Assistant sensor로 제공합니다.

---

## ✨ 특징

| 기능 | 설명 |
|---|---|
| **실시간 체결가** | KIS WebSocket(H0STCNT0) 기반, rate limit 영향 없음 |
| **코스피/코스닥 지수** | REST API polling 방식 |
| **장외 자동 처리** | 장마감 후 종가 자동 조회, 장 시작 시 자동 재연결 |
| **HA UI 설정** | App Key/Secret, 종목 추가/삭제, 업데이트 간격 모두 UI에서 설정 |
| **한글 이름 지원** | sensor 표시 이름을 한글로 설정 가능 |
| **풍부한 데이터** | 현재가, 등락률, 시/고/저, 거래량, 체결강도, PER/PBR, 외국인비율 등 |
| **entity ID 고정** | 표시 이름과 무관하게 항상 `sensor.kis_{종목코드}` 형태 유지 |
| **수급(기관 순매수) 🆕** | 종목별 + 코스피/코스닥 시장 전체 기관/외국인/개인 순매수 수량을 polling으로 조회 |

---

## 📦 설치

### HACS (권장)

1. HACS → 통합구성요소 → 우측 상단 메뉴(점 3개) → **사용자 정의 저장소**
2. URL: `https://github.com/kim2140/kis_realtime_ha` / 범주: `Integration`
3. **KIS 실시간 주식 시세** 검색 후 다운로드
4. Home Assistant 재시작

### 수동 설치

1. 이 저장소의 `custom_components/kis_realtime` 폴더를 `/homeassistant/custom_components/kis_realtime/` 에 복사
2. Home Assistant 재시작

---

## 🔑 KIS Developers App Key 발급

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

---

## ⚙️ 설정

### 1. 통합구성요소 추가

**설정 → 장치 및 서비스 → 통합구성요소 추가 → `KIS 실시간 주식 시세`**

| 항목 | 설명 |
|---|---|
| App Key | KIS Developers에서 발급한 App Key |
| App Secret | KIS Developers에서 발급한 App Secret |
| 실시간 시세 업데이트 간격 | 장중 WebSocket 업데이트 최소 간격 (1~60초, 기본 3초) |
| 지수 조회 간격 | 코스피/코스닥 REST 조회 간격 (10~300초, 기본 30초) |
| 수급 조회 간격 🆕 | 종목별 기관/외국인/개인 순매수 REST 조회 간격 (20~600초, 기본 300초/5분) |

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

---

## 📊 생성되는 Sensor

### 종목 Sensor (`sensor.kis_{종목코드}`)

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
| `investor_institution_buy` 🆕 | 기관계 순매수 수량 (당일 누적, 수급 polling 기준) |
| `investor_foreign_buy` 🆕 | 외국인 순매수 수량 (당일 누적) |
| `investor_individual_buy` 🆕 | 개인 순매수 수량 (당일 누적) |
| `investor_date` 🆕 | 위 수급 데이터 기준일자 (YYYYMMDD) |

> ⚠️ **수급 데이터 관련 주의**: `investor_institution_buy` 등은 KIS "주식현재가 투자자"(FHKST01010900) API를
> 기반으로 하며, 체결가처럼 틱 단위 실시간이 아니라 KIS 서버가 집계한 스냅샷입니다.
> 웹소켓이 아니라 REST polling(기본 300초/5분 간격)으로 갱신됩니다.
> KRX 투자자별매매동향 데이터 자체가 하루 중 정해진 시각(09:30·10:00·11:30·13:20·14:30 잠정치,
> 15:35·18:00 확정치)에만 갱신되기 때문에, 이보다 훨씬 자주 조회해도 대부분 같은 값만 반복됩니다.

### 지수 Sensor (`sensor.kis_kospi`, `sensor.kis_kosdaq`)

| Attribute | 설명 |
|---|---|
| `price` | 현재 지수 (pt) |
| `change` / `change_rate` | 전일대비 / 등락률 |
| `open` / `high` / `low` | 시가/고가/저가 |
| `acc_volume` | 누적거래량 |
| `investor_institution_buy` 🆕 | 시장 전체 기관계 순매수 수량 (KOSPI/KOSDAQ 합계) |
| `investor_foreign_buy` 🆕 | 시장 전체 외국인 순매수 수량 |
| `investor_individual_buy` 🆕 | 시장 전체 개인 순매수 수량 |
| `investor_date` 🆕 | 위 수급 데이터 기준일자 |

> ⚠️ **지수 수급 데이터 출처가 다릅니다**: 종목별 수급(`investor_institution_buy` 등)은 KIS API를 쓰지만,
> 지수(시장 전체) 수급은 KIS에 해당 TR_ID를 찾지 못해서 **[pykrx](https://github.com/sharebook-kr/pykrx)**
> 라이브러리로 KRX 정보데이터시스템을 직접 조회합니다. KIS 앱키와는 무관한 별도 공개 데이터
> 소스이며, `manifest.json`에 `pykrx` 의존성이 추가되어 HA가 자동으로 설치합니다.

---

## 🕐 장 운영 시간

| 시간 | 동작 |
|---|---|
| 09:00 ~ 15:30 | WebSocket 실시간 체결가 수신 |
| 15:30 장마감 | REST API로 종가 자동 조회 |
| 장외 / 주말 | 마지막 종가 유지, 09:00 자동 재연결 |

---

## 🔧 문제 해결

**종목 추가 후 값이 안 나오는 경우**
- KIS API token 발급은 **1분에 1회** 제한
- 종목 추가 후 **최대 1분** 기다리면 자동으로 데이터 표시

**sensor 값이 Unknown인 경우**
- 장외 시간(주말/공휴일)에는 정상
- 평일 09:00 이후 자동으로 실시간 데이터로 업데이트

**App Key 오류**
- KIS Developers에서 App Key/Secret 유효성 확인
- 오픈API 서비스 신청 여부 확인

**`investor_institution_buy`(기관 순매수) 값이 0이거나 이상한 경우** 🆕
- 수급 polling은 최대 5분(기본값) 지연이 있음 → 잠시 기다려보기
- HA 로그에서 `수급 polling` 관련 debug 로그를 확인해서 KIS 응답 구조가 예상과 다른지 확인
- 위 값들은 커뮤니티/공식 문서 기준으로 구현했고 실제 서버 응답으로 100% 검증되진 않았으므로,
  필드명이 다르게 오면 이슈로 남겨주세요

---

## 📄 License

MIT License
