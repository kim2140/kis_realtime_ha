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
INDEX_MARKET_MAP = {
    "0001": "KOSPI",
    "1001": "KOSDAQ",
}

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
