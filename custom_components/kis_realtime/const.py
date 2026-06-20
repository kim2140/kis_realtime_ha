# v1.0.0
# KIS 실시간 주식 시세 Custom Integration 상수 정의
# v1.1.0: 업데이트 간격 설정 추가

DOMAIN = "kis_realtime"

# 설정 키
CONF_APP_KEY      = "app_key"
CONF_APP_SECRET   = "app_secret"
CONF_URL_BASE     = "url_base"
CONF_STOCKS       = "stocks"
CONF_INDEXES      = "indexes"
CONF_THROTTLE_SEC = "throttle_sec"   # WebSocket 종목 업데이트 간격 (초)
CONF_INDEX_POLL   = "index_poll_sec" # 지수 polling 간격 (초)

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
