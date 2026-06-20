# v1.0.0
# KIS 실시간 시세 Coordinator
# - WebSocket (H0STCNT0): 장중 실시간 체결가
# - REST (FHKST01010100): 장외 종가 조회
# - REST (FHPUP02100000): 코스피/코스닥 지수 조회
# - 장외 시간 자동 대기, 장 시작 시 자동 연결
# - 연결 끊김 자동 재연결
# v1.2.0: KIS access token 자체 발급 (kis_token_cache.json 의존 제거)

import asyncio
import json
import logging
import time
from datetime import datetime, time as dt_time, timedelta

import aiohttp
import websockets

from .const import (
    KIS_REST_BASE_DEFAULT,
    KIS_WS_URL,
    DEFAULT_THROTTLE_SEC,
    DEFAULT_INDEX_POLL,
    CONF_THROTTLE_SEC,
    CONF_INDEX_POLL,
    MARKET_OPEN_H, MARKET_OPEN_M,
    MARKET_CLOSE_H, MARKET_CLOSE_M,
    TR_STOCK_CONTRACT,
    TR_STOCK_PRICE,
    TR_INDEX_PRICE,
    SIGN_MAP,
    WS_FIELD_NAMES,
)

log = logging.getLogger(__name__)


def is_market_hours() -> bool:
    """현재 장중 여부 (평일 09:00~15:35)"""
    now = datetime.now()
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

        # KIS access token 자체 발급 및 캐시
        # App Key/Secret으로 직접 발급 → kis_token_cache.json 불필요
        self._access_token: str       = ""
        self._token_expires: datetime = datetime.min

        # sensor 콜백: entity_name → callable(data)
        self._callbacks: dict[str, list] = {}

        # 마지막 수신 데이터 캐시
        self.data: dict[str, dict] = {}

        self._task   = None
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
        self._session = aiohttp.ClientSession()
        self._task = asyncio.create_task(self._run())

    async def async_stop(self):
        if self._task:
            self._task.cancel()
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
        now = datetime.now()
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
