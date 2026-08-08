# v1.0.0
# KIS 실시간 주식 시세 Custom Integration 상수 정의
# v1.1.0: 업데이트 간격 설정 추가
# v1.2.0: 종목별 기관/외국인/개인 순매수(수급) 조회용 상수 추가
#   [개요] 기존에는 웹소켓 체결가 + 지수만 다뤘는데, 여기에 "수급"(기관 순매수)을
#   추가하기 위해 KIS의 "주식현재가 투자자"(FHKST01010900) TR과 그 폴링 주기
#   설정값을 새로 정의함. 실시간 체결에는 투자자별 데이터가 없어서 REST로 별도 polling 필요.
# v1.3.1: 수급 polling 기본 간격을 60초 → 300초(5분)로 조정
#   [개요] KRX 투자자별매매동향 데이터는 애초에 실시간이 아니라 하루 중 정해진 시각
#   (09:30 외국인 잠정치 / 10:00 / 11:30 / 13:20 / 14:30 잠정치 / 15:35·18:00 확정치)
#   에만 갱신됨. 즉 서버 값 자체가 그 시점에만 바뀌므로 60초마다 불러도 대부분
#   같은 값을 반복 수신하는 셈 → API 호출만 낭비. 그래서 기본 간격을 5분으로 늘림.
# v1.4.0: 코스피/코스닥 "시장 전체" 기관/외국인/개인 순매수 추가
#   [개요] KIS API에는 시장 전체 기준 투자자매매동향 TR_ID를 못 찾아서(공식 문서가
#   로그인 후에만 보이는 JS 페이지라 확인 불가), 대신 KRX 정보데이터시스템을 직접
#   감싸는 오픈소스 pykrx 라이브러리를 씀. 종목코드 자리에 "KOSPI"/"KOSDAQ" 문자열을
#   넣으면 시장 전체 합계가 나오는 걸 실제 함수 시그니처/docstring으로 확인했음.
#   KIS 앱키와는 무관한 별도 인증 없는 공개 데이터 소스.
# v1.5.0: 이동평균선(MA) 센서 추가
#   [개요] 사용자가 원하는 기간(예: 10일, 30일, 200일 등 자유 입력)의 단순이동평균
#   (SMA)을 별도 센서로 추가할 수 있게 됨. KIS든 Yahoo든 "이동평균을 계산해서 주는
#   API"는 원래 없고(둘 다 원본 가격만 줌) 클라이언트가 직접 계산하는 게 표준이라,
#   국내주식기간별시세(FHKST03010100, 종목/지수 공용) API로 일별 종가 히스토리를
#   받아와 여기서 직접 평균을 계산함.
#   ⚠ 지수(코스피/코스닥)는 같은 엔드포인트에 FID_COND_MRKT_DIV_CODE="U"를 쓰면
#   조회된다고 여러 커뮤니티 자료에서 확인했으나, 공식 문서로 100% 검증은 못했음 -
#   coordinator.py에서 원본 응답을 log.debug로 남기니 안 맞으면 그 로그로 확인 필요
#   (기존 수급 API들과 동일한 검증 상태).
CONF_MAS     = "moving_averages"  # MA 센서 목록 (code/market_type/period/entity/friendly_name)
CONF_MA_POLL = "ma_poll_sec"      # MA 재계산 주기 (초)
DEFAULT_MA_POLL = 1800  # 30분 - 일봉 기반이라 가격/수급만큼 자주 갱신할 필요 없음
MIN_MA_POLL      = 300
MAX_MA_POLL      = 7200

TR_PERIOD_PRICE = "FHKST03010100"  # 국내주식기간별시세(일/주/월/년) - 종목/지수 공용
MA_MARKET_DIV = {"stock": "J", "index": "U"}  # FID_COND_MRKT_DIV_CODE: 종목=J, 지수=U(미검증)
MA_MIN_PERIOD = 2
MA_MAX_PERIOD = 480  # 약 2년 영업일 - 그 이상은 페이지 호출이 너무 많아져 상한을 둠

# v1.5.1: 지수 MA용 pykrx 폴백 - inquire-daily-itemchartprice의 공식 문서 상
# FID_COND_MRKT_DIV_CODE는 "J"(주식/ETF/ETN)와 "W"(ELW)만 확인되고 "U"(지수)는
# 검증 안 됨 → 이 엔드포인트가 지수를 아예 지원 안 할 가능성이 있어, KIS REST가
# 실패하면 자동으로 pykrx(get_index_ohlcv)로 넘어가는 폴백을 둠(수급 조회와
# 동일한 이중 안전망 패턴).
# ⚠ pykrx의 get_index_ohlcv() 지수코드는 KIS 자체 코드(0001=코스피/1001=코스닥)와
# 체계가 다름(커뮤니티 예제 기준 1001=코스피/2001=코스닥으로 확인) - 아래 매핑은
# 그 커뮤니티 예제를 근거로 한 것이라 공식 문서 100% 검증은 아님.
PYKRX_INDEX_OHLCV_CODE = {
    "0001": "1001",  # KIS 0001(코스피) → pykrx get_index_ohlcv 코드 1001
    "1001": "2001",  # KIS 1001(코스닥) → pykrx get_index_ohlcv 코드 2001
}

# v1.4.0: 위 v1.5.0~v1.5.4 개발/테스트 사이클(이동평균선 기능 신규 추가 + 지수 MA
# 3단계 폴백 안정화)을 정식 릴리즈로 확정. 사용자 실제 HA 서버에서 종목·지수
# MA(코스피 200일선 포함) 모두 정상 조회되는 것까지 확인 완료. 4자리대 개발
# 버전 표기(1.5.x)를 3자리 정식 버전(1.4.0)으로 전환 - 기존 v1.3.2가 마지막
# 정식 릴리즈였으므로, MA는 버그수정이 아닌 신규 기능이라 minor 버전을 올림
# (1.3.2 → 1.4.0). 코드 변경 없음, 버전 번호 정리 + README 갱신만 포함.

INDEX_MARKET_MAP = {
    "0001": "KOSPI",
    "1001": "KOSDAQ",
}

# v1.3.1.4: pykrx가 KRX 서버로부터 지속적으로 차단(빈 응답/JSONDecodeError)당하는 문제 확인
#   (사용자 로그 기준 18시간+/672회 100% 실패) → pykrx보다 먼저 시도할 대체 경로로
#   네이버 금융의 "투자자별 매매동향" 페이지를 직접 파싱하는 방식 추가.
#   [출처] pykrx 라이브러리 제작자(sharebook-kr)가 공개한 참고 구현(GitHub Gist)에서
#   테이블 구조(개인/외국인/기관계 등 컬럼)를 확인. 단, 저(Claude)의 web_fetch 툴이
#   finance.naver.com 도메인을 차단(blocklist)하고 있어 실제 페이지 응답을 직접
#   테스트하지는 못했음 — 합성(가짜) HTML로 파싱 로직만 검증한 상태. 실제 페이지
#   구조가 다르면 아래 파싱 함수가 None을 반환하고 pykrx로 자동 폴백하도록 방어적으로 작성함.
#   sosok: 코스피=01, 코스닥=02 (일반적으로 알려진 값 - 100% 공식 확인은 아님)
# v1.3.2: 위 네이버 스크랩 방식, 사용자의 실제 HA 서버(코스피/코스닥)에서 정상 동작 확인됨
#   (2026-07-19). 별도로 coordinator.py의 _notify 병합 버그도 같이 고쳐져서, 조회된
#   수급 값이 가격 polling에 지워지지 않고 sensor에 정상 유지되는 것까지 확인 완료.
#   sosok 매핑도 실기기 응답으로 간접 검증됨 (0001→01 코스피, 1001→02 코스닥 값이
#   실제 코스피/코스닥과 일치하는 걸 확인).
NAVER_SOSOK_MAP = {
    "0001": "01",   # KOSPI
    "1001": "02",   # KOSDAQ
}
NAVER_INVESTOR_URL = "https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate={bizdate}&sosok={sosok}&page=1"

# v1.5.3: 지수 MA용 3차 폴백(네이버 금융 일별시세 페이지) - KIS REST(U 코드,
# 미검증) → pykrx(get_index_ohlcv) 둘 다 실패할 경우의 최후 경로. 수급 조회에서
# pykrx가 KRX로부터 장시간 차단당했던 전례(18시간+, 100% 실패)가 있어 지수 MA도
# 같은 이유로 막힐 가능성을 대비함. code는 INDEX_MARKET_MAP으로 이미 있는
# "KOSPI"/"KOSDAQ" 문자열을 그대로 재사용 - 별도 매핑 불필요.
NAVER_INDEX_DAY_URL = "https://finance.naver.com/sise/sise_index_day.naver?code={code}&page={page}"

DOMAIN = "kis_realtime"

# 설정 키
CONF_APP_KEY      = "app_key"
CONF_APP_SECRET   = "app_secret"
CONF_URL_BASE     = "url_base"
CONF_STOCKS       = "stocks"
CONF_INDEXES      = "indexes"
CONF_THROTTLE_SEC = "throttle_sec"   # WebSocket 종목 업데이트 간격 (초)
CONF_INDEX_POLL   = "index_poll_sec" # 지수 polling 간격 (초)
CONF_INVESTOR_POLL = "investor_poll_sec"  # v1.2.0: 기관/외국인/개인 수급 polling 간격 (초)

# KIS API
KIS_REST_BASE_DEFAULT = "https://openapi.koreainvestment.com:9443"
KIS_WS_URL            = "ws://ops.koreainvestment.com:21000"

# 업데이트 간격 기본값 / 범위
DEFAULT_THROTTLE_SEC = 3     # 종목 최소 업데이트 간격 (초)
DEFAULT_INDEX_POLL   = 30    # 지수 polling 간격 (초)
MIN_THROTTLE_SEC     = 1
MAX_THROTTLE_SEC     = 60
MIN_INDEX_POLL       = 10
MAX_INDEX_POLL       = 300

# v1.2.0: 수급(투자자별 매매동향) polling 간격 기본값 / 범위
# v1.3.1: 기본값 60 → 300(5분)으로 변경 — 위 주석 참고 (KRX 데이터 자체가 하루 몇 번만 갱신됨)
DEFAULT_INVESTOR_POLL = 300
MIN_INVESTOR_POLL     = 20
MAX_INVESTOR_POLL     = 600

# 장 운영 시간 (KST)
MARKET_OPEN_H  = 8
MARKET_OPEN_M  = 55
MARKET_CLOSE_H = 15
MARKET_CLOSE_M = 36

# WebSocket TR ID
TR_STOCK_CONTRACT = "H0STCNT0"

# REST TR ID
TR_STOCK_PRICE = "FHKST01010100"
TR_INDEX_PRICE = "FHPUP02100000"
# v1.2.0: 주식현재가 투자자(기관계/외국인/개인 순매수) - 국내주식 기본시세 카테고리
# 공식 문서: https://apiportal.koreainvestment.com (API 가이드 > [국내주식] 기본시세 > 주식현재가 투자자)
# ⚠ 실제 KIS 서버 응답으로 100% 검증은 못했음 (앱키가 없어 테스트 불가) — 공개 튜토리얼/커뮤니티
#   자료 기준으로 확인한 TR_ID/필드명이니, 실제 계정으로 처음 실행할 때 로그로 응답을 한번 확인해보는 걸 권장
TR_STOCK_INVESTOR = "FHKST01010900"
# v1.3.1.1: 업종(지수) 투자자매매동향 - 사용자가 KIS 가이드에서 찾아준 TR_ID
# ⚠⚠ 주의: 이건 저(Claude)도 검색으로 독립 검증을 못한 값입니다. 사용자가 KIS 문서에서
#   직접 찾아준 내용을 그대로 반영한 것으로, 응답 필드명(orgn_ntby_qty 등)은 종목용
#   TR(FHKST01010900)과 동일한 네이밍 패턴일 거라고 "추정"해서 파싱 코드를 짰습니다.
#   실제 응답 구조가 다르면 institution_buy 등이 0이나 이상한 값으로 나올 수 있어서,
#   coordinator.py에서 원본 응답을 log.debug로 그대로 남기도록 해뒀습니다 → 안 맞으면
#   그 로그를 보고 필드명을 다시 맞추면 됩니다. (KIS REST 실패 시 pykrx로 자동 대체됨)
TR_INDEX_INVESTOR = "FHPDK01010200"

# 부호 매핑
SIGN_MAP = {
    "1": "↑상한",
    "2": "↑",
    "3": "→",
    "4": "↓하한",
    "5": "↓",
}

# H0STCNT0 필드 순서
WS_FIELD_NAMES = [
    "symbol",         # 0  종목코드
    "time",           # 1  체결시간
    "price",          # 2  현재가
    "sign",           # 3  전일대비부호
    "change",         # 4  전일대비
    "change_rate",    # 5  등락률
    "vwap",           # 6  가중평균가
    "open",           # 7  시가
    "high",           # 8  고가
    "low",            # 9  저가
    "ask1",           # 10 매도호가1
    "bid1",           # 11 매수호가1
    "volume",         # 12 체결거래량
    "acc_volume",     # 13 누적거래량
    "acc_amount",     # 14 누적거래대금
    "sell_count",     # 15 매도체결건수
    "buy_count",      # 16 매수체결건수
    "net_buy_count",  # 17 순매수체결건수
    "strength",       # 18 체결강도
    "total_sell_vol", # 19 총매도수량
    "total_buy_vol",  # 20 총매수수량
    "trade_type",     # 21 체결구분
    "buy_ratio",      # 22 매수비율
]
