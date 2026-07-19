# v1.0.0
# KIS 실시간 시세 Coordinator
# - WebSocket (H0STCNT0): 장중 실시간 체결가
# - REST (FHKST01010100): 장외 종가 조회
# - REST (FHPUP02100000): 코스피/코스닥 지수 조회
# - 장외 시간 자동 대기, 장 시작 시 자동 연결
# - 연결 끊김 자동 재연결
# v1.2.0: KIS access token 자체 발급 (kis_token_cache.json 의존 제거)
# v1.3.0: 종목별 기관/외국인/개인 순매수(수급) polling 추가
#   [개요] 웹소켓 체결(H0STCNT0)에는 투자자 구분이 없어서, 지수 polling과 동일한 패턴으로
#   REST(FHKST01010900, 주식현재가 투자자)를 별도 태스크로 주기 조회함.
#   기존 self.data[entity_name]을 통째로 덮어쓰면 가격 정보가 날아가므로, 수급 값은
#   기존 캐시에 "병합"해서 _notify 하도록 구현 (아래 _run_investor_poll 참고).
#   ⚠ 주의: FHKST01010900 TR_ID와 필드명(orgn_ntby_qty 등)은 KIS 공식 문서/커뮤니티 자료
#   기준으로 확인했지만, 실제 앱키로 살아있는 응답을 직접 테스트하지는 못했음.
#   처음 실행 시 로그(log.debug)로 실제 응답 구조를 한번 확인해보는 걸 권장.
# v1.4.0: 코스피/코스닥 "시장 전체" 수급(기관/외국인/개인 순매수) 추가
#   [개요] KIS에는 시장 전체 기준 투자자매매동향 TR_ID를 못 찾아서, 대신 KRX 데이터를
#   직접 감싸는 pykrx 라이브러리를 씀. pykrx는 동기(sync) 라이브러리라서 HA의 비동기
#   이벤트 루프를 막지 않도록 hass.async_add_executor_job으로 별도 스레드에서 실행함.
#   지수 polling(_run_index_poll)과는 별개로, 종목 수급과 같은 _run_investor_poll
#   루프 안에서 같이 처리 (업데이트 주기가 어차피 같은 수준이라 태스크를 늘리지 않음).
# v1.3.1.1: 지수 수급을 KIS REST(FHPDK01010200, 업종 투자자매매동향)로 우선 시도하고,
#   실패하면 pykrx로 자동 대체(fallback)하도록 변경.
#   [개요] 사용자가 KIS 가이드에서 지수용 TR_ID를 찾아줌. 다만 Claude가 독립적으로
#   재검증은 못한 값이라, 혹시 틀렸을 때를 대비해 기존 pykrx 경로를 지우지 않고
#   "1차 시도: KIS REST → 실패 시 2차 시도: pykrx" 순서로 이중 안전망을 만듦.
#   원본 응답은 log.debug로 그대로 남겨서, 필드명이 안 맞으면 로그 보고 바로 고칠 수 있게 함.
# v1.3.1.2: 수급 딕셔너리 키를 institution_buy/foreign_buy_qty/individual_buy →
#   investor_institution_buy/investor_foreign_buy/investor_individual_buy 로 리네임.
#   기존 이름이 서로 통일이 안 돼있었고, 기존 foreign_buy(현재가 API 값)와 헷갈린다는
#   피드백을 반영 (sensor.py 쪽 상세 설명 참고).
# v1.3.1.4: pykrx가 KRX 서버로부터 계속 빈 응답/차단을 당하는 문제(100% 실패, 18시간+)가
#   해결되지 않아서, pykrx보다 먼저 시도할 대체 경로로 네이버 금융 "투자자별 매매동향"
#   페이지 직접 파싱을 추가함 (_fetch_index_investor_naver / _sync_parse_naver_investor_html).
#   [개요] 이 방식도 제가(Claude) 직접 네이버 페이지에 접근해서 테스트해보진 못했음
#   (제 web_fetch 도구가 finance.naver.com을 차단 목록으로 막고 있음) — pykrx 제작자의
#   공개 참고 구현(GitHub Gist)에서 확인한 테이블 구조를 기준으로 작성했고, 컬럼명이
#   달라도 최대한 안 죽게 방어적으로 짰음. 우선순위: (비활성)KIS REST → 네이버 스크랩 →
#   pykrx(최후 폴백). pandas/lxml을 새 의존성으로 manifest.json에 추가함.
# v1.3.1.5: _notify가 dict를 통째로 덮어써서 수급(investor_*) 필드가 다음 가격 polling에
#   지워지던 버그 수정 (아래 _notify 함수 주석 참고). 사용자 실기기 테스트로 네이버 스크랩 +
#   이 버그 수정까지 정상 동작 확인됨.
# v1.3.2: 위 1.3.1.1~1.3.1.5 테스트 사이클에서 나온 변경사항을 정식 버전으로 확정.
#   [개요] 사용자가 실제 HA 서버(코스피/코스닥 둘 다)에서 네이버 스크랩 기반 지수 수급이
#   정상 조회되고, 가격 polling에도 값이 안 지워지고 유지되는 것까지 확인해줌 → 테스트
#   완료로 판단하고 4자리 테스트 버전 표기를 3자리 정식 버전으로 전환. 기능적으로 1.3.1.5와
#   동일 (코드 변경 없음, 버전 번호만 정리).

import asyncio
import json
import logging
import time
from datetime import datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

import aiohttp
import websockets

from .const import (
    KIS_REST_BASE_DEFAULT,
    KIS_WS_URL,
    DEFAULT_THROTTLE_SEC,
    DEFAULT_INDEX_POLL,
    DEFAULT_INVESTOR_POLL,
    CONF_THROTTLE_SEC,
    CONF_INDEX_POLL,
    CONF_INVESTOR_POLL,
    MARKET_OPEN_H, MARKET_OPEN_M,
    MARKET_CLOSE_H, MARKET_CLOSE_M,
    TR_STOCK_CONTRACT,
    TR_STOCK_PRICE,
    TR_INDEX_PRICE,
    TR_STOCK_INVESTOR,
    TR_INDEX_INVESTOR,
    INDEX_MARKET_MAP,
    NAVER_SOSOK_MAP,
    NAVER_INVESTOR_URL,
    SIGN_MAP,
    WS_FIELD_NAMES,
)

log = logging.getLogger(__name__)


def is_market_hours() -> bool:
    """현재 장중 여부 (평일 09:00~15:35) - KST 기준"""
    now = datetime.now(KST)
    if now.weekday() >= 5:
        return False
    t = now.time()
    open_t  = dt_time(MARKET_OPEN_H,  MARKET_OPEN_M)
    close_t = dt_time(MARKET_CLOSE_H, MARKET_CLOSE_M)
    return open_t <= t <= close_t


def parse_ws_message(raw: str) -> dict | None:
    """H0STCNT0 WebSocket 체결 메시지 파싱"""
    fields = raw.split("^")
    if len(fields) < 23:
        return None
    d = {name: fields[i] for i, name in enumerate(WS_FIELD_NAMES)}
    sign_str = SIGN_MAP.get(d["sign"], d["sign"])
    try:
        return {
            "symbol":      d["symbol"],
            "time":        d["time"],
            "price":       int(d["price"]),
            "change":      int(d["change"]),
            "change_rate": float(d["change_rate"]),
            "sign":        sign_str,
            "open":        int(d["open"]),
            "high":        int(d["high"]),
            "low":         int(d["low"]),
            "ask1":        int(d["ask1"]),
            "bid1":        int(d["bid1"]),
            "volume":      int(d["volume"]),
            "acc_volume":  int(d["acc_volume"]),
            "acc_amount":  int(d["acc_amount"]),
            "strength":    float(d["strength"]),
            "buy_ratio":   float(d["buy_ratio"]),
        }
    except (ValueError, KeyError):
        return None


def _sync_fetch_market_investor(market: str, retries: int = 3) -> dict | None:
    """v1.4.0 신규 - pykrx로 시장 전체(KOSPI/KOSDAQ) 기관/외국인/개인 순매수 조회
    v1.3.1.1: 원인 파악이 안 되는 "조용한 실패"를 없애기 위해 로그를 촘촘히 추가
      (이전 버전은 df가 비어있을 때 아무 로그도 안 남기고 그냥 None을 반환해서,
       왜 지수 수급이 안 뜨는지 사용자 쪽 로그로는 전혀 알 수 없었음)
    v1.3.1.3: 재시도(retry) 로직 추가
      [개요] 사용자 로그로 확인해보니 KIS 서버(openapi.koreainvestment.com)는 정상 응답
      (404였지만 어쨌든 응답은 옴)하는데, KRX 쪽(data.krx.co.kr)만 유독 빈 응답
      (JSONDecodeError)이 오는 걸 확인함. 즉 네트워크 자체가 막힌 게 아니라 KRX가
      가끔/일시적으로 요청을 거부하는(봇 감지, 세션 처리 실패 등) 상황으로 추정됨.
      pykrx는 undocumented 내부 API를 흉내내는 방식이라 원래 이런 일시적 실패가
      흔하다고 알려져 있어서, 짧은 대기 후 최대 3회까지 재시도하도록 함.
      ⚠ 그래도 계속 실패한다면 일시적 문제가 아니라 사용자 네트워크(방화벽/DNS/ISP
      차단 등)가 data.krx.co.kr 자체를 못 가는 상황일 수 있음 - 이 경우 코드로는
      해결이 안 되고 네트워크 쪽을 확인해봐야 함.

    - 동기(sync) 함수라서 반드시 hass.async_add_executor_job으로 별도 스레드에서 호출할 것
      (asyncio 이벤트 루프 안에서 직접 부르면 다른 sensor 업데이트가 멈춤)
    - pykrx는 내부적으로 KRX 정보데이터시스템에 OTP 발급→다운로드 방식으로 접근함
      (KIS 앱키/시크릿과 무관, 별도 인증 없는 공개 데이터)
    - 최근 10일치를 조회해서 가장 최근(마지막) 행을 사용 (당일 데이터가 아직 없으면
      직전 영업일 값이 자동으로 잡힘)
    """
    try:
        from pykrx import stock as pykrx_stock  # 지연 import: 설치 전에도 통합 자체는 죽지 않게
    except ImportError as e:
        log.error(f"[수급] pykrx import 실패 (설치가 안 됐거나 버전 문제): {e}")
        return None

    today = datetime.now(KST)
    fromdate = (today - timedelta(days=10)).strftime("%Y%m%d")
    todate   = today.strftime("%Y%m%d")

    for attempt in range(1, retries + 1):
        log.debug(f"[수급] pykrx 조회 시도 {attempt}/{retries}: market={market}")
        try:
            df = pykrx_stock.get_market_trading_volume_by_date(fromdate, todate, market)
            if df is None or df.empty:
                log.warning(f"[수급] pykrx 응답이 비어있음 (시도 {attempt}/{retries}): market={market}, 기간={fromdate}~{todate}")
            else:
                last = df.iloc[-1]
                last_date = df.index[-1]
                date_str = last_date.strftime("%Y-%m-%d") if hasattr(last_date, "strftime") else str(last_date)
                return {
                    "investor_institution_buy": int(last.get("기관합계", 0)),
                    "investor_foreign_buy": int(last.get("외국인합계", 0)),
                    "investor_individual_buy":  int(last.get("개인", 0)),
                    "investor_date":   date_str,
                }
        except Exception as e:
            log.warning(f"[수급] pykrx 조회 오류 (시도 {attempt}/{retries}) market={market}: {e}")

        if attempt < retries:
            time.sleep(2)  # 동기 함수 안이라 asyncio.sleep이 아니라 time.sleep 사용 (executor 스레드 안이라 안전)

    log.error(f"[수급] pykrx {retries}회 재시도 모두 실패: market={market} — 네트워크(방화벽/DNS)에서 data.krx.co.kr 접근이 막혀있는지 확인 필요")
    return None


def _sync_parse_naver_investor_html(html: str) -> dict | None:
    """v1.3.1.4 신규 - 네이버 금융 "투자자별 매매동향" 페이지 HTML을 파싱해서
    시장 전체(코스피/코스닥) 기관계/외국인/개인 순매수 수량을 뽑아냄.

    [왜 이렇게 짰나]
    pykrx 제작자(sharebook-kr)가 공개한 참고 구현은 pd.read_html(...,
    skiprows=[0,1,2,8,9,10,16,17])처럼 "몇 번째 줄을 건너뛸지"를 고정된 숫자로
    지정하는 방식인데, 이건 네이버가 페이지 마크업을 조금만 바꿔도 깨지는
    취약한 방식이라 판단함. 그래서 skiprows를 쓰는 대신, pd.read_html()로 페이지의
    모든 테이블을 가져온 뒤 "개인"/"외국인"/"기관계" 컬럼명이 실제로 존재하는
    테이블을 찾아서 그 컬럼명으로 값을 뽑는 방식으로 바꿈 (컬럼 순서가 바뀌어도
    안전, 다만 컬럼명 텍스트 자체가 바뀌면 여전히 실패할 수 있음 - 이 경우
    아래에서 실패 사유를 로그로 남기고 None을 반환해서 pykrx로 자동 폴백됨).

    ⚠ 실제 네이버 페이지에 직접 접근해서 검증하지 못했음 (Claude의 web_fetch 도구가
    finance.naver.com을 차단 목록으로 막고 있어서). 합성(가짜) HTML로 파싱 로직
    자체의 동작만 확인한 상태 - 실제 페이지 구조가 다르면 아래 로그를 보고 컬럼명/
    구조를 다시 맞춰야 할 수 있음.

    - 동기(sync) 함수: pandas.read_html은 CPU 바운드라 hass.async_add_executor_job으로
      별도 스레드에서 호출해야 함 (이벤트 루프 안에서 직접 부르면 안 됨)
    """
    try:
        import pandas as pd
    except ImportError as e:
        log.error(f"[수급] pandas import 실패 (설치가 안 됐거나 버전 문제): {e}")
        return None

    import io

    try:
        tables = pd.read_html(io.StringIO(html), thousands=",")
    except Exception as e:
        log.warning(f"[수급] 네이버 페이지 테이블 파싱 실패 (read_html): {e}")
        return None

    if not tables:
        log.warning("[수급] 네이버 페이지에서 테이블을 하나도 못 찾음 (구조가 예상과 다를 수 있음)")
        return None

    target = None
    for t in tables:
        # colspan 헤더가 있으면 MultiIndex 컬럼이 되므로 마지막 레벨만 사용
        if isinstance(t.columns, pd.MultiIndex):
            t.columns = t.columns.get_level_values(-1)
        cols = [str(c).strip() for c in t.columns]
        if "개인" in cols and "외국인" in cols and "기관계" in cols:
            target = t
            target.columns = cols
            break

    if target is None:
        log.warning(
            "[수급] 네이버 페이지에서 개인/외국인/기관계 컬럼을 가진 테이블을 못 찾음 "
            "(페이지 구조가 바뀌었을 수 있음 - pykrx로 자동 폴백)"
        )
        return None

    # 첫 번째 컬럼을 날짜 컬럼으로 간주 (네이버 표는 보통 첫 칸이 날짜)
    date_col = target.columns[0]

    def _parse_date(s):
        return pd.to_datetime(str(s).strip(), format="%y.%m.%d", errors="coerce")

    target["_date"] = target[date_col].apply(_parse_date)
    valid = target.dropna(subset=["_date"])
    if valid.empty:
        log.warning(f"[수급] 네이버 테이블에서 유효한 날짜 행을 못 찾음 (date_col={date_col})")
        return None

    latest = valid.loc[valid["_date"].idxmax()]
    try:
        return {
            "investor_institution_buy": int(latest["기관계"]),
            "investor_foreign_buy": int(latest["외국인"]),
            "investor_individual_buy": int(latest["개인"]),
            "investor_date": latest["_date"].strftime("%Y%m%d"),
        }
    except (ValueError, TypeError) as e:
        log.warning(f"[수급] 네이버 테이블 값 변환 실패 (숫자가 아닌 값 포함 가능): {e}")
        return None


class KisRealtimeCoordinator:
    """KIS 실시간 시세 데이터 관리 및 HA sensor 콜백"""

    def __init__(self, hass, config: dict):
        self.hass        = hass
        self._app_key    = config["app_key"]
        self._app_secret = config["app_secret"]
        self._url_base   = config.get("url_base", KIS_REST_BASE_DEFAULT)
        self._stocks     = {s["code"]: s["entity"] for s in config.get("stocks", [])}
        self._indexes    = {i["code"]: i["entity"] for i in config.get("indexes", [])}

        # 업데이트 간격 (UI에서 설정 가능)
        self._throttle_sec = config.get(CONF_THROTTLE_SEC, DEFAULT_THROTTLE_SEC)
        self._index_poll   = config.get(CONF_INDEX_POLL,   DEFAULT_INDEX_POLL)
        self._investor_poll = config.get(CONF_INVESTOR_POLL, DEFAULT_INVESTOR_POLL)  # v1.3.0

        # KIS access token 자체 발급 및 캐시
        # App Key/Secret으로 직접 발급 → kis_token_cache.json 불필요
        self._access_token: str       = ""
        self._token_expires: datetime = datetime.min

        # sensor 콜백: entity_name → callable(data)
        self._callbacks: dict[str, list] = {}

        # 마지막 수신 데이터 캐시
        self.data: dict[str, dict] = {}

        self._task         = None
        self._index_task   = None  # v1.0.0: 지수 polling 전용 태스크
        self._investor_task = None  # v1.3.0: 수급(기관 순매수) polling 전용 태스크
        self._session: aiohttp.ClientSession | None = None

    # ── 콜백 등록/해제 ──────────────────────────
    def register_callback(self, entity_name: str, callback):
        self._callbacks.setdefault(entity_name, []).append(callback)
        # 이미 캐시된 데이터가 있으면 즉시 콜백 호출
        if entity_name in self.data:
            callback(self.data[entity_name])

    def unregister_callback(self, entity_name: str, callback):
        if entity_name in self._callbacks:
            try:
                self._callbacks[entity_name].remove(callback)
            except ValueError:
                pass

    # v1.3.1.5: _notify가 항상 dict를 "통째로" 덮어쓰던 걸 "기존 캐시 + 새 데이터 병합"으로 변경
    #   [개요] 지수 수급이 실제로는 정상 조회(네이버 스크랩 성공)되는데도 sensor에는 항상 0으로만
    #   보이는 원인을 로그로 추적한 결과, 수급 polling(_run_investor_poll, 5분 주기)이 값을 넣어놔도
    #   그 직후 돌아오는 지수 가격 polling(_run_index_poll, 10~30초 주기)이 가격 필드만 담긴 dict로
    #   self._notify를 호출하면서 수급 필드가 통째로 사라지는 구조적 버그를 발견함.
    #   (수급 polling 루프 쪽은 이미 자기 호출부에서 {**기존값, **새값} 병합을 해서 _notify를 부르고
    #   있었지만, 가격 polling/WebSocket 체결 수신부/_fetch_all_closing 등 다른 호출부들은 병합 없이
    #   그냥 새 dict를 통째로 넘기고 있었음 — 호출하는 쪽마다 "병합해야 한다"는 걸 기억해야 하는
    #   구조라 실수하기 쉬웠음)
    #   그래서 _notify 자체를 "항상 병합"하도록 바꿔서, 앞으로 어떤 곳에서 _notify를 부르든
    #   실수로 다른 필드를 지우는 일이 구조적으로 없도록 함. (이미 병합해서 넘기던 호출부는
    #   중복 병합이라 결과가 똑같아서 안전함)
    #   ⚠ 종목(주식) 쪽도 장중 WebSocket 체결 수신부가 같은 버그를 갖고 있었는데, 장중에만
    #   발생해서(장외엔 WebSocket이 안 돎) 지금까지 장외 시간에 확인할 땐 우연히 안 드러났던 것으로
    #   추정됨 — 이번 수정으로 같이 해결됨.
    def _notify(self, entity_name: str, data: dict):
        merged = {**self.data.get(entity_name, {}), **data}
        self.data[entity_name] = merged
        for cb in self._callbacks.get(entity_name, []):
            cb(merged)

    # ── 시작/종료 ────────────────────────────────
    async def async_start(self):
        self._session    = aiohttp.ClientSession()
        self._task       = asyncio.create_task(self._run())
        # v1.0.0: 지수 polling 전용 태스크 (장중/장외 무관하게 독립 실행)
        self._index_task = asyncio.create_task(self._run_index_poll())
        # v1.3.0: 수급(기관 순매수) polling 전용 태스크
        self._investor_task = asyncio.create_task(self._run_investor_poll())

    async def async_stop(self):
        if self._task:
            self._task.cancel()
        if self._index_task:
            self._index_task.cancel()
        if self._investor_task:  # v1.3.0
            self._investor_task.cancel()
        if self._session:
            await self._session.close()

    # ── 종목/지수 동적 업데이트 ──────────────────
    def update_config(self, stocks: dict, indexes: dict):
        self._stocks  = stocks
        self._indexes = indexes

    # ── WebSocket 접속키 발급 ────────────────────
    async def _get_approval_key(self) -> str:
        url = f"{self._url_base}/oauth2/Approval"
        payload = {
            "grant_type": "client_credentials",
            "appkey":     self._app_key,
            "secretkey":  self._app_secret,
        }
        async with self._session.post(url, json=payload) as resp:
            data = await resp.json()
            key = data.get("approval_key", "")
            if not key:
                raise RuntimeError(f"접속키 발급 실패: {data}")
            return key

    # ── KIS Access Token 발급 ───────────────────
    async def _get_access_token(self) -> str:
        """KIS OAuth2 access token 발급 (24시간 유효, 자동 갱신)
        - 1분에 1회 발급 제한 → 기존 token 유지 후 60초 후 재시도
        - App Key/Secret으로 직접 발급 → 외부 파일 불필요
        """
        now = datetime.now(KST)  # KST 기준
        # 만료 10분 전에 갱신
        if self._access_token and now < self._token_expires - timedelta(minutes=10):
            return self._access_token

        url = f"{self._url_base}/oauth2/tokenP"
        payload = {
            "grant_type": "client_credentials",
            "appkey":     self._app_key,
            "appsecret":  self._app_secret,
        }
        # 최대 3회 재시도 (1분 간격)
        for attempt in range(3):
            try:
                async with self._session.post(url, json=payload, ssl=False) as resp:
                    data = await resp.json()
                    token = data.get("access_token", "")
                    if not token:
                        err_code = data.get("error_code", "")
                        if err_code == "EGW00133":
                            # 1분에 1회 제한 → 기존 token 있으면 유지
                            if self._access_token:
                                log.warning("token 발급 제한 (1분 1회) → 기존 token 유지")
                                return self._access_token
                            log.warning(f"token 발급 제한 → 60초 후 재시도 ({attempt+1}/3)")
                            await asyncio.sleep(62)
                            continue
                        log.error(f"access token 발급 실패: {data}")
                        return self._access_token
                    expires_in = int(data.get("expires_in", 86400))
                    self._access_token  = token
                    self._token_expires = now + timedelta(seconds=expires_in)
                    log.info(f"KIS access token 발급 완료 (만료: {self._token_expires.strftime('%H:%M')})")
                    return token
            except Exception as e:
                log.error(f"access token 발급 오류: {e}")
                return self._access_token
        return self._access_token

    # ── REST: 종목 현재가/종가 조회 ──────────────
    async def _fetch_stock_price(self, symbol: str) -> dict | None:
        """FHKST01010100 - 현재가(장외=종가) + 부가정보"""
        access_token = await self._get_access_token()
        if not access_token:
            return None

        url = f"{self._url_base}/uapi/domestic-stock/v1/quotations/inquire-price"
        headers = {
            "authorization": f"Bearer {access_token}",
            "appkey":        self._app_key,
            "appsecret":     self._app_secret,
            "tr_id":         TR_STOCK_PRICE,
            "custtype":      "P",
        }
        params = {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": symbol}
        try:
            async with self._session.get(url, headers=headers, params=params, ssl=False) as resp:
                out = (await resp.json()).get("output", {})
                if not out:
                    return None
                sign_str = SIGN_MAP.get(out.get("prdy_vrss_sign", "3"), "→")
                return {
                    "symbol":        symbol,
                    "time":          "153000",
                    "price":         int(out.get("stck_prpr", 0)),
                    "change":        int(out.get("prdy_vrss", 0)),
                    "change_rate":   float(out.get("prdy_ctrt", 0)),
                    "sign":          sign_str,
                    "open":          int(out.get("stck_oprc", 0)),
                    "high":          int(out.get("stck_hgpr", 0)),
                    "low":           int(out.get("stck_lwpr", 0)),
                    "ask1":          0,
                    "bid1":          0,
                    "volume":        0,
                    "acc_volume":    int(out.get("acml_vol", 0)),
                    "acc_amount":    int(out.get("acml_tr_pbmn", 0)),
                    "strength":      0.0,
                    "buy_ratio":     0.0,
                    "week52_high":   int(out.get("stck_mxpr", 0)),
                    "week52_low":    int(out.get("stck_llam", 0)),
                    "per":           out.get("per", "0"),
                    "pbr":           out.get("pbr", "0"),
                    "eps":           out.get("eps", "0"),
                    "bps":           out.get("bps", "0"),
                    "foreign_rate":  out.get("hts_frgn_ehrt", "0"),
                    "foreign_buy":   out.get("frgn_ntby_qty", "0"),
                    "listed_shares": out.get("lstn_stcn", "0"),
                    "market_cap":    int(out.get("hts_avls", 0)) if out.get("hts_avls") else 0,
                    "vol_rate":      out.get("prdy_vrss_vol_rate", "0"),
                    "vwap":          out.get("wghn_avrg_stck_prc", "0"),
                }
        except Exception as e:
            log.error(f"종목 가격 조회 실패 [{symbol}]: {e}")
            return None

    # ── REST: 종목별 기관/외국인/개인 순매수(수급) 조회 ──── v1.3.0 신규
    async def _fetch_stock_investor(self, symbol: str) -> dict | None:
        """FHKST01010900 - 주식현재가 투자자 (기관계/외국인/개인 순매수 수량)

        - KIS 서버가 집계한 당일 누적 순매수 수량 스냅샷 (체결처럼 틱 단위 아님)
        - output이 배열(list)로 오는 경우와 단일 객체(dict)로 오는 경우 둘 다 대응
          → 문서상으로는 최신순 배열일 가능성이 높다고 알려져 있으나, 계정 없이는
            100% 확정할 수 없어서 방어적으로 두 형태 모두 처리하도록 작성함
        """
        access_token = await self._get_access_token()
        if not access_token:
            return None

        url = f"{self._url_base}/uapi/domestic-stock/v1/quotations/inquire-investor"
        headers = {
            "authorization": f"Bearer {access_token}",
            "appkey":        self._app_key,
            "appsecret":     self._app_secret,
            "tr_id":         TR_STOCK_INVESTOR,
            "custtype":      "P",
        }
        params = {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": symbol}
        try:
            async with self._session.get(url, headers=headers, params=params, ssl=False) as resp:
                body = await resp.json()
                raw_out = body.get("output", body.get("output1", {}))

                # 응답이 배열이면 가장 최근(0번째) 값을 사용, 객체면 그대로 사용
                if isinstance(raw_out, list):
                    if not raw_out:
                        return None
                    out = raw_out[0]
                else:
                    out = raw_out
                if not out:
                    return None

                return {
                    # 기관계 순매수 수량 (요청하신 "기관 순매수" 핵심 필드)
                    "investor_institution_buy": int(out.get("orgn_ntby_qty", 0) or 0),
                    # 외국인/개인 순매수도 같은 응답에 포함되어 있어 함께 저장 (참고용)
                    "investor_foreign_buy": int(out.get("frgn_ntby_qty", 0) or 0),
                    "investor_individual_buy":  int(out.get("prsn_ntby_qty", 0) or 0),
                    "investor_date":   out.get("stck_bsop_date", ""),
                }
        except Exception as e:
            log.error(f"수급(투자자매매동향) 조회 실패 [{symbol}]: {e}")
            return None

    # ── REST: 지수(업종) 투자자매매동향 조회 ──── v1.3.1.1 신규
    async def _fetch_index_investor_kis(self, code: str) -> dict | None:
        """FHPDK01010200 - 업종별 투자자매매동향 (지수 기준 기관/외국인/개인 순매수)

        ⚠ TR_ID·파라미터는 사용자가 KIS 가이드에서 찾아준 값이고, 응답 필드명은
        종목용 TR(FHKST01010900)과 같은 네이밍 패턴일 거라 "추정"해서 파싱함.
        원본 응답을 log.debug로 통째로 남기니, 값이 이상하면 그 로그를 보고
        필드명을 다시 맞추면 됨.
        """
        access_token = await self._get_access_token()
        if not access_token:
            return None

        url = f"{self._url_base}/uapi/domestic-stock/v1/quotations/inquire-investor-trend"
        headers = {
            "authorization": f"Bearer {access_token}",
            "appkey":        self._app_key,
            "appsecret":     self._app_secret,
            "tr_id":         TR_INDEX_INVESTOR,
            "custtype":      "P",
        }
        params = {
            "FID_INPUT_ISCD":    code,  # 0001=코스피, 1001=코스닥
            "FID_DIV_CLS_CODE":  "0",   # 0: 정규장 수급 기준
        }
        try:
            async with self._session.get(url, headers=headers, params=params, ssl=False) as resp:
                body = await resp.json()
                log.debug(f"[수급] KIS 지수 투자자매매동향 원본 응답 [{code}]: {body}")

                raw_out = body.get("output", body.get("output1", {}))
                if isinstance(raw_out, list):
                    if not raw_out:
                        return None
                    out = raw_out[0]
                else:
                    out = raw_out
                if not out:
                    return None

                return {
                    "investor_institution_buy": int(out.get("orgn_ntby_qty", 0) or 0),
                    "investor_foreign_buy": int(out.get("frgn_ntby_qty", 0) or 0),
                    "investor_individual_buy":  int(out.get("prsn_ntby_qty", 0) or 0),
                    "investor_date":   out.get("stck_bsop_date", ""),
                }
        except Exception as e:
            log.error(f"[수급] KIS 지수 투자자매매동향 조회 실패 [{code}]: {e}")
            return None

    # ── pykrx: 시장 전체(코스피/코스닥) 수급 조회 (KIS 실패 시 대체용) ──── v1.4.0
    async def _fetch_index_investor_pykrx(self, code: str) -> dict | None:
        """지수 코드(0001/1001)를 KOSPI/KOSDAQ 문자열로 매핑해서 pykrx 조회

        실제 네트워크 호출은 동기 함수(_sync_fetch_market_investor)에서 일어나므로
        이벤트 루프를 막지 않도록 executor job으로 위임.
        """
        market = INDEX_MARKET_MAP.get(code)
        if not market:
            return None
        try:
            return await self.hass.async_add_executor_job(_sync_fetch_market_investor, market)
        except Exception as e:
            log.error(f"[수급] pykrx 지수 수급 조회 실패 [{code}]: {e}")
            return None

    # ── 네이버 금융: 시장 전체(코스피/코스닥) 수급 조회 ──── v1.3.1.4 신규
    #   [개요] pykrx가 KRX로부터 지속적으로 차단당해서(100% 실패, 18시간+ 확인), pykrx보다
    #   먼저 시도할 대체 경로로 추가. KIS 앱키와 무관, 별도 인증 없는 공개 페이지를
    #   그냥 GET해서 HTML 테이블을 파싱하는 방식이라 KRX 봇 차단과는 다른 경로임.
    #   실제 파싱은 CPU 바운드(pandas)라 executor job으로 위임.
    async def _fetch_index_investor_naver(self, code: str) -> dict | None:
        sosok = NAVER_SOSOK_MAP.get(code)
        if not sosok:
            return None

        bizdate = datetime.now(KST).strftime("%Y%m%d")
        url = NAVER_INVESTOR_URL.format(bizdate=bizdate, sosok=sosok)
        headers = {
            # 네이버가 non-browser User-Agent를 다르게 취급할 가능성을 대비해 일반 브라우저처럼 요청
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        }
        try:
            async with self._session.get(url, headers=headers, ssl=False) as resp:
                if resp.status != 200:
                    log.warning(f"[수급] 네이버 지수 수급 페이지 응답 실패 [{code}]: HTTP {resp.status}")
                    return None
                html = await resp.text()
        except Exception as e:
            log.warning(f"[수급] 네이버 지수 수급 페이지 요청 실패 [{code}]: {e}")
            return None

        try:
            result = await self.hass.async_add_executor_job(_sync_parse_naver_investor_html, html)
        except Exception as e:
            log.warning(f"[수급] 네이버 지수 수급 파싱 실패 [{code}]: {e}")
            return None

        if result:
            log.debug(f"[수급] 지수 {code}: 네이버 스크랩 성공 - {result}")
        return result

    # ── 지수 수급 통합 진입점 ──── v1.3.1.4
    #   [개요] v1.3.1.1에서 KIS REST(FHPDK01010200)를 1차로 시도하도록 만들었는데,
    #   실제 서버에서 호출해보니 404(그런 endpoint 자체가 없음)로 확인됨 → TR_ID가
    #   틀린 정보였던 것으로 결론. 매번 404를 받는 호출은 의미가 없어서 우선 순위에서
    #   제외함. _fetch_index_investor_kis 함수 자체는 나중에 정확한 TR_ID를 찾으면
    #   바로 다시 켤 수 있도록 지우지 않고 남겨둠 (아래에서 주석 처리한 코드 참고).
    #   v1.3.1.4: pykrx가 계속 막혀서, pykrx보다 먼저 네이버 스크랩을 시도하도록 순서 변경.
    #   우선순위: (비활성)KIS REST → 네이버 스크랩(신규) → pykrx(최후 폴백).
    async def _fetch_index_investor(self, code: str) -> dict | None:
        # ⚠ FHPDK01010200 / inquire-investor-trend 는 실제 KIS 서버에서 404 확인됨
        #   (2026-07-18 사용자 로그로 확인). 정확한 TR_ID를 찾기 전까지는 비활성화.
        # result = await self._fetch_index_investor_kis(code)
        # if result:
        #     log.debug(f"[수급] 지수 {code}: KIS REST 성공 - {result}")
        #     return result
        # log.debug(f"[수급] 지수 {code}: KIS REST 실패/빈 응답 → 네이버로 재시도")

        result = await self._fetch_index_investor_naver(code)
        if result:
            return result
        log.debug(f"[수급] 지수 {code}: 네이버 스크랩 실패/빈 응답 → pykrx로 재시도")

        result = await self._fetch_index_investor_pykrx(code)
        if result:
            log.debug(f"[수급] 지수 {code}: pykrx 성공 - {result}")
        else:
            log.warning(f"[수급] 지수 {code}: 네이버·pykrx 둘 다 실패 (당분간 수급 속성이 안 뜰 수 있음)")
        return result

    # ── REST: 지수 조회 ──────────────────────────
    async def _fetch_index_price(self, code: str) -> dict | None:
        """FHPUP02100000 - 코스피/코스닥 지수"""
        access_token = await self._get_access_token()
        if not access_token:
            return None
        url = f"{self._url_base}/uapi/domestic-stock/v1/quotations/inquire-index-price"
        headers = {
            "authorization": f"Bearer {access_token}",
            "appkey":        self._app_key,
            "appsecret":     self._app_secret,
            "tr_id":         TR_INDEX_PRICE,
            "custtype":      "P",
        }
        params = {"fid_cond_mrkt_div_code": "U", "fid_input_iscd": code}
        try:
            async with self._session.get(url, headers=headers, params=params, ssl=False) as resp:
                out = (await resp.json()).get("output", {})
                if not out:
                    return None
                sign_str = SIGN_MAP.get(out.get("prdy_vrss_sign", "3"), "→")
                return {
                    "symbol":      code,
                    "time":        "153000",
                    "price":       float(out.get("bstp_nmix_prpr", 0)),
                    "change":      float(out.get("bstp_nmix_prdy_vrss", 0)),
                    "change_rate": float(out.get("bstp_nmix_prdy_ctrt", 0)),
                    "sign":        sign_str,
                    "open":        float(out.get("bstp_nmix_oprc", 0)),
                    "high":        float(out.get("bstp_nmix_hgpr", 0)),
                    "low":         float(out.get("bstp_nmix_lwpr", 0)),
                    "acc_volume":  int(out.get("acml_vol", 0)),
                    "acc_amount":  int(out.get("acml_tr_pbmn", 0)),
                    "is_index":    True,
                }
        except Exception as e:
            log.error(f"지수 조회 실패 [{code}]: {e}")
            return None

    # ── 지수 polling 루프 (독립 태스크) ──────────
    async def _run_index_poll(self):
        """v1.0.0: 장중/장외 무관하게 주기적으로 지수 REST API 조회
        - WebSocket 루프와 별도 태스크로 실행
        - 지수는 WebSocket 미지원이므로 REST polling 필수
        - _index_poll 초(기본 30초) 간격으로 반복
        - 토큰이 없으면 직접 발급 후 조회 (장외에도 동작)
        """
        # HA 시작 직후 세션 준비 대기
        await asyncio.sleep(5)

        while True:
            try:
                # 토큰 없으면 직접 발급 (장외에도 지수 조회 가능하도록)
                if not self._access_token:
                    await self._get_access_token()

                for code, entity_name in list(self._indexes.items()):
                    data = await self._fetch_index_price(code)
                    # v1.0.0: price가 0 이하면 KIS 서버 점검/비정상값으로 판단 → 마지막 정상값 유지
                    if data and float(data.get("price", 0)) > 0:
                        self._notify(entity_name, data)
                        log.debug(f"지수 polling: {code} {data['price']}pt")
                    elif data:
                        log.warning(f"지수 비정상값 무시: {code} price={data.get('price')}")
                    await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                log.info("지수 polling 태스크 종료")
                break
            except Exception as e:
                log.error(f"지수 polling 오류: {e}")

            await asyncio.sleep(self._index_poll)

    # ── 수급(기관 순매수) polling 루프 (독립 태스크) ──── v1.3.0 신규
    async def _run_investor_poll(self):
        """장중/장외 무관하게 주기적으로 종목별 + 시장 전체 기관/외국인/개인 순매수 조회

        - _index_poll과 동일한 패턴: 별도 태스크로 독립 실행
        - 기존 self.data(가격/체결 정보)를 지우지 않도록, 조회한 수급 값만
          기존 캐시 위에 "병합"해서 _notify 호출 (그냥 덮어쓰면 가격 필드가 사라짐)
        - v1.4.0: 종목(KIS REST)뿐 아니라 지수(pykrx)도 같은 루프에서 같이 처리.
          둘 다 "하루 몇 번만 갱신되는 수급 데이터"라 굳이 태스크를 따로 둘 필요가 없음.
        """
        await asyncio.sleep(7)  # 시작 직후 세션/토큰 준비 대기

        while True:
            try:
                for symbol, entity_name in list(self._stocks.items()):
                    investor = await self._fetch_stock_investor(symbol)
                    if investor:
                        # 기존 캐시(가격 등) + 새로 받은 수급 데이터 병합
                        merged = {**self.data.get(entity_name, {}), **investor}
                        self._notify(entity_name, merged)
                        log.debug(
                            f"수급 polling: {symbol} 기관 {investor['investor_institution_buy']:,} / "
                            f"외국인 {investor['investor_foreign_buy']:,} / 개인 {investor['investor_individual_buy']:,}"
                        )
                    await asyncio.sleep(0.5)

                # v1.4.0: 지수(코스피/코스닥) 시장 전체 수급 - pykrx 기반
                for code, entity_name in list(self._indexes.items()):
                    investor = await self._fetch_index_investor(code)
                    if investor:
                        merged = {**self.data.get(entity_name, {}), **investor}
                        self._notify(entity_name, merged)
                        log.debug(
                            f"시장 수급 polling: {code} 기관 {investor['investor_institution_buy']:,} / "
                            f"외국인 {investor['investor_foreign_buy']:,} / 개인 {investor['investor_individual_buy']:,}"
                        )
                    await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                log.info("수급 polling 태스크 종료")
                break
            except Exception as e:
                log.error(f"수급 polling 오류: {e}")

            await asyncio.sleep(self._investor_poll)

    # ── 전체 종가/지수 일괄 조회 ─────────────────
    async def _fetch_all_closing(self):
        """종목 + 지수 전체 종가 조회 → 콜백 호출"""
        log.info("종가 초기화/업데이트 중...")
        for symbol, entity_name in self._stocks.items():
            data = await self._fetch_stock_price(symbol)
            if data:
                self._notify(entity_name, data)
                log.info(f"종가: {symbol} {data['price']:,}원 ({data['sign']}{data['change_rate']:+.2f}%)")
            await asyncio.sleep(0.5)

        for code, entity_name in self._indexes.items():
            data = await self._fetch_index_price(code)
            if data:
                self._notify(entity_name, data)
                log.info(f"지수: {code} {data['price']}pt ({data['sign']}{data['change_rate']:+.2f}%)")
            await asyncio.sleep(0.5)

    # ── 메인 루프 ────────────────────────────────
    async def _run(self):
        last_update: dict[str, float] = {}

        # 시작 즉시 종가 로드
        try:
            await self._fetch_all_closing()
        except Exception as e:
            log.error(f"초기 종가 조회 실패: {e}")

        while True:
            try:
                # 장외 대기
                while not is_market_hours():
                    await asyncio.sleep(60)

                log.info("장 시작 - WebSocket 연결")
                approval_key = await self._get_approval_key()

                async with websockets.connect(
                    KIS_WS_URL,
                    ping_interval=60,
                    ping_timeout=30,
                    close_timeout=10,
                    max_size=1024 * 1024,
                    open_timeout=30,
                ) as ws:
                    log.info(f"WebSocket 연결 완료")

                    # 종목 구독
                    for symbol in self._stocks:
                        msg = json.dumps({
                            "header": {
                                "approval_key": approval_key,
                                "custtype":     "P",
                                "tr_type":      "1",
                                "content-type": "utf-8",
                            },
                            "body": {"input": {"tr_id": TR_STOCK_CONTRACT, "tr_key": symbol}}
                        })
                        await ws.send(msg)
                        log.info(f"구독: {symbol} ({self._stocks[symbol]})")
                        await asyncio.sleep(0.1)

                    # 수신 루프
                    async for raw_msg in ws:
                        if raw_msg.startswith("{"):
                            msg = json.loads(raw_msg)
                            rt_cd = msg.get("body", {}).get("rt_cd", "")
                            if rt_cd != "0":
                                log.warning(f"제어 메시지: {msg}")
                            continue

                        parts = raw_msg.split("|")
                        if len(parts) < 4 or parts[0] != "0" or parts[1] != TR_STOCK_CONTRACT:
                            continue

                        data = parse_ws_message(parts[3])
                        if not data:
                            continue

                        symbol = data["symbol"]
                        entity_name = self._stocks.get(symbol)
                        if not entity_name:
                            continue

                        now = time.time()
                        if now - last_update.get(symbol, 0) < self._throttle_sec:
                            continue
                        last_update[symbol] = now

                        self._notify(entity_name, data)

            except websockets.exceptions.ConnectionClosed as e:
                log.warning(f"WebSocket 끊김: {e}")
                if not is_market_hours():
                    log.info("장마감 → 종가 업데이트")
                    try:
                        await self._fetch_all_closing()
                    except Exception as ce:
                        log.error(f"종가 조회 오류: {ce}")
                await asyncio.sleep(10)

            except asyncio.CancelledError:
                log.info("Coordinator 종료")
                break

            except Exception as e:
                log.error(f"예외: {e} — 15초 후 재시도")
                await asyncio.sleep(15)
