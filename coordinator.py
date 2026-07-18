# v1.0.0
# KIS 실시간 주식 시세 Config Flow
# ─────────────────────────────────────────────────────────────────────────────
# [개요]
# HA UI에서 App Key/Secret 입력, 종목/지수 추가·삭제, 업데이트 간격 설정을 처리.
# options_flow에서 저장된 종목/지수는 entry.options에 기록됨.
#
# [v1.4.0] selector 사용으로 UI 개선, 종목명 자동 조회, 삭제 버그 수정
# [v1.7.1] entity 이름 단순화: 종목명 영문변환 → 종목코드 그대로 사용
#   - 기존: sensor.kis_tiger_riceubudongsaninpeura (종목명 영문 변환, 너무 길고 불명확)
#   - 변경: sensor.kis_329200 (종목코드 6자리, 단순하고 명확)
#   - _to_entity() 함수 제거 (더 이상 사용 안 함)
#   - 지수는 기존 유지: sensor.kis_kospi / sensor.kis_kosdaq
# [v1.8.0] 수급(기관 순매수) polling 간격 설정 슬라이더 추가
#   - 기존 종목/지수 간격 설정 화면에 investor_poll_sec 슬라이더만 추가 (구조는 그대로)
# ─────────────────────────────────────────────────────────────────────────────

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
import aiohttp

from .const import (
    DOMAIN,
    CONF_APP_KEY, CONF_APP_SECRET, CONF_URL_BASE,
    CONF_STOCKS, CONF_INDEXES,
    CONF_THROTTLE_SEC, CONF_INDEX_POLL, CONF_INVESTOR_POLL,
    KIS_REST_BASE_DEFAULT,
    DEFAULT_THROTTLE_SEC, DEFAULT_INDEX_POLL, DEFAULT_INVESTOR_POLL,
    MIN_THROTTLE_SEC, MAX_THROTTLE_SEC,
    MIN_INDEX_POLL, MAX_INDEX_POLL,
    MIN_INVESTOR_POLL, MAX_INVESTOR_POLL,
)


async def _validate_kis_key(app_key: str, app_secret: str, url_base: str) -> bool:
    """App Key / Secret 유효성 검증 (WebSocket approval_key 발급 시도)"""
    url = f"{url_base}/oauth2/Approval"
    payload = {"grant_type": "client_credentials", "appkey": app_key, "secretkey": app_secret}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return bool((await resp.json()).get("approval_key"))
    except Exception:
        return False


async def _get_token(app_key: str, app_secret: str, url_base: str) -> str:
    """REST API 접근용 Bearer 토큰 발급"""
    url = f"{url_base}/oauth2/tokenP"
    payload = {"grant_type": "client_credentials", "appkey": app_key, "appsecret": app_secret}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, ssl=False, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return (await resp.json()).get("access_token", "")
    except Exception:
        return ""


async def _fetch_stock_info(app_key: str, app_secret: str, url_base: str, code: str) -> tuple[str, str]:
    """종목코드 → (entity 이름, 한글 종목명) 반환

    v1.7.1 변경:
    - entity: 종목코드 그대로 사용 (예: "329200" → sensor.kis_329200)
    - 기존 stock_{code} 방식 제거
    - friendly_name: 한글 종목명 (KIS API 조회, 실패 시 빈 문자열)
    """
    token = await _get_token(app_key, app_secret, url_base)
    entity = code          # ★ v1.7.1: 종목코드를 entity 이름으로 직접 사용
    friendly = ""
    if not token:
        return entity, friendly
    url = f"{url_base}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {
        "authorization": f"Bearer {token}",
        "appkey": app_key, "appsecret": app_secret,
        "tr_id": "FHKST01010100", "custtype": "P",
    }
    params = {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, ssl=False,
                                   timeout=aiohttp.ClientTimeout(total=10)) as resp:
                out = (await resp.json()).get("output", {})
                kor_name = out.get("hts_kor_isnm", "")
                if kor_name:
                    friendly = kor_name
    except Exception:
        pass
    return entity, friendly


class KisRealtimeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._data = {}

    async def async_step_user(self, user_input=None):
        """초기 설정: App Key / Secret 입력"""
        errors = {}
        if user_input is not None:
            valid = await _validate_kis_key(
                user_input[CONF_APP_KEY],
                user_input[CONF_APP_SECRET],
                user_input.get(CONF_URL_BASE, KIS_REST_BASE_DEFAULT),
            )
            if valid:
                self._data.update(user_input)
                return await self.async_step_interval()
            errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_APP_KEY): str,
                vol.Required(CONF_APP_SECRET): str,
                vol.Optional(CONF_URL_BASE, default=KIS_REST_BASE_DEFAULT): str,
            }),
            errors=errors,
        )

    async def async_step_interval(self, user_input=None):
        """업데이트 간격 설정"""
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(
                title="KIS 실시간 주식 시세",
                data={**self._data, CONF_STOCKS: [], CONF_INDEXES: []},
            )
        return self.async_show_form(
            step_id="interval",
            data_schema=vol.Schema({
                vol.Optional(CONF_THROTTLE_SEC, default=DEFAULT_THROTTLE_SEC):
                    selector.NumberSelector(selector.NumberSelectorConfig(
                        min=MIN_THROTTLE_SEC, max=MAX_THROTTLE_SEC, step=1, mode="slider")),
                vol.Optional(CONF_INDEX_POLL, default=DEFAULT_INDEX_POLL):
                    selector.NumberSelector(selector.NumberSelectorConfig(
                        min=MIN_INDEX_POLL, max=MAX_INDEX_POLL, step=5, mode="slider")),
                # v1.8.0: 수급(기관 순매수) polling 간격
                vol.Optional(CONF_INVESTOR_POLL, default=DEFAULT_INVESTOR_POLL):
                    selector.NumberSelector(selector.NumberSelectorConfig(
                        min=MIN_INVESTOR_POLL, max=MAX_INVESTOR_POLL, step=10, mode="slider")),
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return KisRealtimeOptionsFlow(config_entry)


class KisRealtimeOptionsFlow(config_entries.OptionsFlow):

    def __init__(self, config_entry):
        self._entry    = config_entry
        # options 우선, 없으면 data에서 읽음
        opts = config_entry.options if config_entry.options else config_entry.data
        self._stocks   = list(opts.get(CONF_STOCKS, []))
        self._indexes  = list(opts.get(CONF_INDEXES, []))
        self._throttle = opts.get(CONF_THROTTLE_SEC, DEFAULT_THROTTLE_SEC)
        self._poll     = opts.get(CONF_INDEX_POLL, DEFAULT_INDEX_POLL)
        self._investor_poll = opts.get(CONF_INVESTOR_POLL, DEFAULT_INVESTOR_POLL)  # v1.8.0
        self._pending_code     = ""
        self._pending_entity   = ""
        self._pending_friendly = ""

    def _save(self):
        """현재 상태를 options에 저장"""
        return self.async_create_entry(title="", data={
            **self._entry.data,
            CONF_STOCKS:       self._stocks,
            CONF_INDEXES:      self._indexes,
            CONF_THROTTLE_SEC: int(self._throttle),
            CONF_INDEX_POLL:   int(self._poll),
            CONF_INVESTOR_POLL: int(self._investor_poll),  # v1.8.0
        })

    async def async_step_init(self, user_input=None):
        return await self.async_step_menu()

    async def async_step_menu(self, user_input=None):
        """메인 메뉴: 종목/지수 추가·삭제·간격 조정·저장"""
        if user_input is not None:
            action = user_input.get("action")
            if action == "add_stock":  return await self.async_step_add_stock_code()
            if action == "add_index":  return await self.async_step_add_index()
            if action == "remove":     return await self.async_step_remove()
            if action == "interval":   return await self.async_step_interval()
            return self._save()

        # 현재 등록 목록 표시 (sensor ID 형태로)
        stock_list = ", ".join(f"sensor.kis_{s['entity']}" for s in self._stocks) or "없음"
        index_list = ", ".join(f"sensor.kis_{i['entity']}" for i in self._indexes) or "없음"

        return self.async_show_form(
            step_id="menu",
            data_schema=vol.Schema({
                vol.Required("action", default="save"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=[
                        {"value": "add_stock", "label": "종목 추가 (ETF/개별주)"},
                        {"value": "add_index", "label": "지수 추가 (코스피/코스닥)"},
                        {"value": "remove",    "label": "종목/지수 삭제"},
                        {"value": "interval",  "label": f"업데이트 간격 조정 (종목 {int(self._throttle)}초 / 지수 {int(self._poll)}초 / 수급 {int(self._investor_poll)}초)"},
                        {"value": "save",      "label": "저장"},
                    ], mode="list")
                ),
            }),
            description_placeholders={"stocks": stock_list, "indexes": index_list},
        )

    async def async_step_add_stock_code(self, user_input=None):
        """종목 추가 1단계: 종목코드 입력"""
        errors = {}
        if user_input is not None:
            code = str(user_input["code"]).zfill(6)
            if any(s["code"] == code for s in self._stocks):
                errors["code"] = "already_exists"
            else:
                self._pending_code = code
                self._pending_entity, self._pending_friendly = await _fetch_stock_info(
                    self._entry.data[CONF_APP_KEY],
                    self._entry.data[CONF_APP_SECRET],
                    self._entry.data.get(CONF_URL_BASE, KIS_REST_BASE_DEFAULT),
                    code,
                )
                return await self.async_step_add_stock_confirm()

        return self.async_show_form(
            step_id="add_stock_code",
            data_schema=vol.Schema({vol.Required("code"): str}),
            errors=errors,
            description_placeholders={"example": "예) 069500 (KODEX 200), 005930 (삼성전자)"},
        )

    async def async_step_add_stock_confirm(self, user_input=None):
        """종목 추가 2단계: 표시 이름(friendly_name) 확인·수정
        entity는 종목코드로 자동 확정 (수정 불가)
        """
        if user_input is not None:
            friendly = user_input.get("friendly_name", "").strip() or f"[KIS] {self._pending_code}"
            self._stocks.append({
                "code":          self._pending_code,
                "entity":        self._pending_entity,   # 종목코드 (예: "329200")
                "friendly_name": friendly,
            })
            return await self.async_step_menu()

        return self.async_show_form(
            step_id="add_stock_confirm",
            data_schema=vol.Schema({
                vol.Optional("friendly_name", default=self._pending_friendly): str,
            }),
            description_placeholders={
                "code":   self._pending_code,
                "entity": self._pending_entity,
                "sensor": f"sensor.kis_{self._pending_entity}",  # 예: sensor.kis_329200
            },
        )

    async def async_step_add_index(self, user_input=None):
        """지수 추가 1단계: 코스피/코스닥 선택"""
        if user_input is not None:
            code = str(user_input["code"]).zfill(4)
            if any(i["code"] == code for i in self._indexes):
                return self.async_show_form(
                    step_id="add_index",
                    data_schema=vol.Schema({
                        vol.Required("code"): selector.SelectSelector(
                            selector.SelectSelectorConfig(options=[
                                {"value": "0001", "label": "코스피 (0001) → sensor.kis_kospi"},
                                {"value": "1001", "label": "코스닥 (1001) → sensor.kis_kosdaq"},
                            ], mode="list")
                        ),
                    }),
                    errors={"code": "already_exists"},
                )
            self._pending_code = code
            # 지수는 코드번호보다 이름이 직관적이므로 기존 유지
            INDEX_MAP = {"0001": ("kospi", "코스피"), "1001": ("kosdaq", "코스닥")}
            self._pending_entity, self._pending_friendly = INDEX_MAP.get(code, (f"index_{code}", code))
            return await self.async_step_add_index_confirm()

        return self.async_show_form(
            step_id="add_index",
            data_schema=vol.Schema({
                vol.Required("code"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=[
                        {"value": "0001", "label": "코스피 (0001) → sensor.kis_kospi"},
                        {"value": "1001", "label": "코스닥 (1001) → sensor.kis_kosdaq"},
                    ], mode="list")
                ),
            }),
        )

    async def async_step_add_index_confirm(self, user_input=None):
        """지수 추가 2단계: 표시 이름 확인·수정"""
        if user_input is not None:
            friendly = user_input.get("friendly_name", "").strip() or self._pending_friendly
            self._indexes.append({
                "code":          self._pending_code,
                "entity":        self._pending_entity,
                "friendly_name": friendly,
            })
            return await self.async_step_menu()

        return self.async_show_form(
            step_id="add_index_confirm",
            data_schema=vol.Schema({
                vol.Optional("friendly_name", default=self._pending_friendly): str,
            }),
            description_placeholders={
                "code":   self._pending_code,
                "sensor": f"sensor.kis_{self._pending_entity}",
            },
        )

    async def async_step_interval(self, user_input=None):
        """업데이트 간격 조정"""
        if user_input is not None:
            self._throttle = user_input[CONF_THROTTLE_SEC]
            self._poll     = user_input[CONF_INDEX_POLL]
            self._investor_poll = user_input[CONF_INVESTOR_POLL]  # v1.8.0
            return await self.async_step_menu()

        return self.async_show_form(
            step_id="interval",
            data_schema=vol.Schema({
                vol.Optional(CONF_THROTTLE_SEC, default=int(self._throttle)):
                    selector.NumberSelector(selector.NumberSelectorConfig(
                        min=MIN_THROTTLE_SEC, max=MAX_THROTTLE_SEC, step=1, mode="slider")),
                vol.Optional(CONF_INDEX_POLL, default=int(self._poll)):
                    selector.NumberSelector(selector.NumberSelectorConfig(
                        min=MIN_INDEX_POLL, max=MAX_INDEX_POLL, step=5, mode="slider")),
                # v1.8.0: 수급(기관 순매수) polling 간격
                vol.Optional(CONF_INVESTOR_POLL, default=int(self._investor_poll)):
                    selector.NumberSelector(selector.NumberSelectorConfig(
                        min=MIN_INVESTOR_POLL, max=MAX_INVESTOR_POLL, step=10, mode="slider")),
            }),
        )

    async def async_step_remove(self, user_input=None):
        """종목/지수 삭제: 체크박스로 복수 선택 후 즉시 저장"""
        all_items = (
            [{"value": f"stock:{s['code']}:{s['entity']}", "label": f"{s.get('friendly_name', s['entity'])} (sensor.kis_{s['entity']})"} for s in self._stocks] +
            [{"value": f"index:{i['code']}:{i['entity']}", "label": f"{i.get('friendly_name', i['entity'])} (sensor.kis_{i['entity']})"} for i in self._indexes]
        )
        if not all_items:
            return await self.async_step_menu()

        if user_input is not None:
            to_remove = user_input.get("items", [])
            self._stocks  = [s for s in self._stocks  if f"stock:{s['code']}:{s['entity']}" not in to_remove]
            self._indexes = [i for i in self._indexes if f"index:{i['code']}:{i['entity']}" not in to_remove]
            # 삭제 즉시 저장 → __init__.py의 _async_update_listener가 entity registry 정리
            return self._save()

        return self.async_show_form(
            step_id="remove",
            data_schema=vol.Schema({
                vol.Optional("items", default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=all_items,
                        multiple=True,
                        mode="list",
                    )
                ),
            }),
        )