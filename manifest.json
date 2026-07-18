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


def _sync_fetch_market_investor(market: str) -> dict | None:
    """v1.4.0 신규 - pykrx로 시장 전체(KOSPI/KOSDAQ) 기관/외국인/개인 순매수 조회
    v1.3.1.1: 원인 파악이 안 되는 "조용한 실패"를 없애기 위해 로그를 촘촘히 추가
      (이전 버전은 df가 비어있을 때 아무 로그도 안 남기고 그냥 None을 반환해서,
       왜 지수 수급이 안 뜨는지 사용자 쪽 로그로는 전혀 알 수 없었음)

    - 동기(sync) 함수라서 반드시 hass.async_add_executor_job으로 별도 스레드에서 호출할 것
      (asyncio 이벤트 루프 안에서 직접 부르면 다른 sensor 업데이트가 멈춤)
    - pykrx는 내부적으로 KRX 정보데이터시스템에 OTP 발급→다운로드 방식으로 접근함
      (KIS 앱키/시크릿과 무관, 별도 인증 없는 공개 데이터)
    - 최근 10일치를 조회해서 가장 최근(마지막) 행을 사용 (당일 데이터가 아직 없으면
      직전 영업일 값이 자동으로 잡힘)
    """
    log.debug(f"[수급] pykrx 조회 시작: market={market}")
    try:
        from pykrx import stock as pykrx_stock  # 지연 import: 설치 전에도 통합 자체는 죽지 않게
    except ImportError as e:
        log.error(f"[수급] pykrx import 실패 (설치가 안 됐거나 버전 문제): {e}")
        return None

    try:
        today = datetime.now(KST)
        fromdate = (today - timedelta(days=10)).strftime("%Y%m%d")
        todate   = today.strftime("%Y%m%d")
        df = pykrx_stock.get_market_trading_volume_by_date(fromdate, todate, market)
        if df is None or df.empty:
            log.warning(f"[수급] pykrx 응답이 비어있음: market={market}, 기간={fromdate}~{todate}")
            return None
        last = df.iloc[-1]
        last_date = df.index[-1]
        date_str = last_date.strftime("%Y-%m-%d") if hasattr(last_date, "strftime") else str(last_date)
        return {
            "institution_buy": int(last.get("기관합계", 0)),
            "foreign_buy_qty": int(last.get("외국인합계", 0)),
            "individual_buy":  int(last.get("개인", 0)),
            "investor_date":   date_str,
        }
    except Exception as e:
        log.error(f"pykrx 시장 수급 조회 실패 [{market}]: {e}")
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

    def _notify(self, entity_name: str, data: dict):
        self.data[entity_name] = data
        for cb in self._callbacks.get(entity_name, []):
            cb(data)

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
                    "institution_buy": int(out.get("orgn_ntby_qty", 0) or 0),
                    # 외국인/개인 순매수도 같은 응답에 포함되어 있어 함께 저장 (참고용)
                    "foreign_buy_qty": int(out.get("frgn_ntby_qty", 0) or 0),
                    "individual_buy":  int(out.get("prsn_ntby_qty", 0) or 0),
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
                    "institution_buy": int(out.get("orgn_ntby_qty", 0) or 0),
                    "foreign_buy_qty": int(out.get("frgn_ntby_qty", 0) or 0),
                    "individual_buy":  int(out.get("prsn_ntby_qty", 0) or 0),
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

    # ── 지수 수급 통합 진입점: KIS REST 우선, 실패 시 pykrx로 대체 ──── v1.3.1.1
    async def _fetch_index_investor(self, code: str) -> dict | None:
        result = await self._fetch_index_investor_kis(code)
        if result:
            log.debug(f"[수급] 지수 {code}: KIS REST 성공 - {result}")
            return result

        log.debug(f"[수급] 지수 {code}: KIS REST 실패/빈 응답 → pykrx로 재시도")
        result = await self._fetch_index_investor_pykrx(code)
        if result:
            log.debug(f"[수급] 지수 {code}: pykrx 대체 성공 - {result}")
        else:
            log.warning(f"[수급] 지수 {code}: KIS REST, pykrx 둘 다 실패 (당분간 수급 속성이 안 뜰 수 있음)")
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
                            f"수급 polling: {symbol} 기관 {investor['institution_buy']:,} / "
                            f"외국인 {investor['foreign_buy_qty']:,} / 개인 {investor['individual_buy']:,}"
                        )
                    await asyncio.sleep(0.5)

                # v1.4.0: 지수(코스피/코스닥) 시장 전체 수급 - pykrx 기반
                for code, entity_name in list(self._indexes.items()):
                    investor = await self._fetch_index_investor(code)
                    if investor:
                        merged = {**self.data.get(entity_name, {}), **investor}
                        self._notify(entity_name, merged)
                        log.debug(
                            f"시장 수급 polling: {code} 기관 {investor['institution_buy']:,} / "
                            f"외국인 {investor['foreign_buy_qty']:,} / 개인 {investor['individual_buy']:,}"
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
