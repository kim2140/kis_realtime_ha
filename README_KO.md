# KIS 실시간 주식 시세 for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2023.1%2B-blue)](https://www.home-assistant.io/)
[![Version](https://img.shields.io/badge/Version-1.4.0-green)]()

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
| **이동평균선(MA) 🆕** | 원하는 기간(예: 10/30/60/200일)의 단순이동평균 센서를 종목/지수 위에 자유롭게 추가 - 콤마로 구분해 여러 기간 한 번에 가능 |

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
| MA 재계산 간격 🆕 | 이동평균 재계산 간격 (300~7200초, 기본 1800초/30분) - 일봉 기반이라 자주 갱신할 필요 없음 |

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

#### 이동평균선(MA) 추가 🆕
1. **이동평균선(MA) 추가** 선택 (종목/지수가 최소 1개 이상 등록되어 있어야 함)
2. 대상 종목/지수 선택
3. 원하는 기간을 콤마로 구분해서 입력 (예: `10,30,60,200`) - 기본값 없음, 매번 직접 입력
4. Submit → 기간별로 센서가 각각 하나씩 생성됨 (같은 대상+기간 조합이 이미 있으면 조용히 건너뜀)

#### 종목/지수/MA 삭제
1. **종목/지수/MA 삭제** 선택
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
> 지수(시장 전체) 수급은 KIS에 해당 TR_ID를 찾지 못했습니다. 아래 순서로 3단계 폴백을 시도합니다:
> (1) KIS REST — 현재 비활성화 (아래 문제 해결 참고), (2) 네이버 금융 투자자별 매매동향 페이지
> 직접 스크래핑, (3) **[pykrx](https://github.com/sharebook-kr/pykrx)**로 KRX 정보데이터시스템
> 직접 조회. (2)/(3) 모두 KIS 앱키와 무관한 별도 공개 데이터 소스입니다. `manifest.json`에
> `pandas`/`lxml`/`pykrx` 의존성이 추가되어 HA가 자동으로 설치합니다.
> ✅ v1.3.2 기준, 네이버 스크랩 방식(2단계)은 실제 HA 서버에서 코스피/코스닥 둘 다 정상 동작하는
> 것까지 확인됐습니다. 조회된 수급 값이 가격 polling 직후 사라지던 관련 버그(`coordinator.py`의
> `_notify`)도 같이 수정됐습니다.

### 이동평균선(MA) Sensor (`sensor.kis_{종목코드}_ma{기간}`) 🆕

| Attribute | 설명 |
|---|---|
| `price` (상태값) | 이동평균 값 자체 (종목은 KRW, 지수는 pt) |
| `base_code` | 이 평균을 계산한 기준 종목코드/지수코드 |
| `market_type` | `stock`(종목) 또는 `index`(지수) |
| `period` | 이 센서가 나타내는 기간 (예: `20`이면 20일선) |
| `data_points` | 실제로 평균 계산에 쓰인 일수 - `period`보다 적으면 그 주기엔 계산이 스킵된 것(아래 참고) |
| `last_calc` | 마지막으로 계산에 성공한 시각 |

값은 `coordinator._run_ma_poll()`이 `ma_poll_sec`(기본 30분)마다 재계산합니다. KIS의 기간별시세 API
(`FHKST03010100`, 종목/지수 공용)로 일별 종가 히스토리를 받아와 단순이동평균(SMA)을 직접 계산하는
방식입니다 - KIS든 Yahoo Finance든 이동평균을 미리 계산해서 주는 API는 원래 없어서, 다른 MA 기반
지표와 마찬가지로 클라이언트(이 통합) 쪽에서 계산합니다.

`data_points`가 요청한 `period`보다 계속 적게 나오면, 센서는 마지막으로 정상 계산됐던 값을 그대로
유지하고 경고 로그(`[MA] {entity}: 확보된 데이터(N일)가 요청 기간(M일)보다 적어 계산 스킵`)가 남습니다
- 그 주기에 히스토리를 충분히 못 받아온 것뿐이지, 값 자체가 잘못된 게 아닙니다.

> ⚠️ **지수 MA도 지수 수급과 같은 취지로 3단계 폴백을 씁니다**: KIS 기간별시세 API의 공식 문서상
> `FID_COND_MRKT_DIV_CODE`는 `J`(주식/ETF/ETN)와 `W`(ELW)만 확인되고, 여기서 지수용으로 쓴 `U` 코드는
> 검증되지 않아 안 될 수 있습니다. KIS REST가 실패하면 (2) **pykrx**(`get_index_ohlcv`)로, 그것도
> 실패하면(수급 기능 때처럼 pykrx가 KRX로부터 차단당하는 경우 등) (3) **네이버 금융
> `sise_index_day.naver` 페이지를 직접 스크래핑**하는 방식으로 넘어갑니다 - 한 페이지에 약 10일치씩
> 나오는 걸 여러 페이지 넘겨가며 필요한 만큼 모읍니다. ✅ v1.4.0 기준, 코스피 200일선이 실제 HA
> 서버에서 (네이버 폴백 경로로) 끝까지 정상 조회되는 것까지 확인 완료했습니다. 안 되시면 HA 로그에서
> `[MA]`로 시작하는 줄을 확인해주세요 - 어느 단계가 왜 실패했는지 그대로 남습니다.

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

**MA 센서가 `Unknown`이거나 예전 값에서 안 바뀌는 경우** 🆕
- HA 로그에서 `[MA]`로 시작하는 줄을 확인 - 각 폴백 단계(KIS REST → pykrx → 네이버)가 왜 실패했는지 남음
- `data_points` 속성이 `period`보다 낮으면, 그 주기엔 히스토리를 충분히 못 받아온 것 - 센서는 이상한
  평균을 보여주는 대신 마지막 정상값을 그대로 유지함
- 지수 MA인데 pykrx 단계가 실패 중이라면(`pykrx 지수 OHLCV ... 실패`), 네이버 폴백이 자동으로 이어받아야
  정상 - 그것도 실패하면 네이버 페이지 구조가 바뀐 것일 수 있으니 로그와 함께 이슈로 남겨주세요

---

## 📄 License

MIT License
