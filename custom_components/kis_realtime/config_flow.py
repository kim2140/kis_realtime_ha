# v1.1.0
# KIS 실시간 주식 시세 Config Flow
# v1.1.0: 업데이트 간격(throttle_sec, index_poll_sec) 설정 UI 추가

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import aiohttp

from .const import (
    DOMAIN,
    CONF_APP_KEY, CONF_APP_SECRET, CONF_URL_BASE,
    CONF_STOCKS, CONF_INDEXES,
    CONF_THROTTLE_SEC, CONF_INDEX_POLL,
    KIS_REST_BASE_DEFAULT,
    DEFAULT_THROTTLE_SEC, DEFAULT_INDEX_POLL,
    MIN_THROTTLE_SEC, MAX_THROTTLE_SEC,
    MIN_INDEX_POLL, MAX_INDEX_POLL,
)

STEP_USER_SCHEMA = vol.Schema({
    vol.Required(CONF_APP_KEY):    str,
    vol.Required(CONF_APP_SECRET): str,
    vol.Optional(CONF_URL_BASE, default=KIS_REST_BASE_DEFAULT): str,
})

STEP_INTERVAL_SCHEMA = vol.Schema({
    vol.Optional(CONF_THROTTLE_SEC, default=DEFAULT_THROTTLE_SEC):
        vol.All(int, vol.Range(min=MIN_THROTTLE_SEC, max=MAX_THROTTLE_SEC)),
    vol.Optional(CONF_INDEX_POLL, default=DEFAULT_INDEX_POLL):
        vol.All(int, vol.Range(min=MIN_INDEX_POLL, max=MAX_INDEX_POLL)),
})


async def _validate_kis_key(app_key: str, app_secret: str, url_base: str) -> bool:
    """KIS App Key/Secret 유효성 검증"""
    url = f"{url_base}/oauth2/Approval"
    payload = {
        "grant_type": "client_credentials",
        "appkey":     app_key,
        "secretkey":  app_secret,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                return bool(data.get("approval_key"))
    except Exception:
        return False


class KisRealtimeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """KIS 실시간 시세 설정 플로우 (2단계: 인증 → 업데이트 간격)"""

    VERSION = 1

    def __init__(self):
        self._data = {}

    async def async_step_user(self, user_input=None):
        """1단계: App Key/Secret 입력"""
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
            else:
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
            description_placeholders={"url": "https://apiportal.koreainvestment.com"},
        )

    async def async_step_interval(self, user_input=None):
        """2단계: 업데이트 간격 설정"""
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(
                title="KIS 실시간 주식 시세",
                data={
                    **self._data,
                    CONF_STOCKS:  [],
                    CONF_INDEXES: [],
                },
            )

        return self.async_show_form(
            step_id="interval",
            data_schema=STEP_INTERVAL_SCHEMA,
            description_placeholders={
                "throttle_min": str(MIN_THROTTLE_SEC),
                "throttle_max": str(MAX_THROTTLE_SEC),
                "poll_min":     str(MIN_INDEX_POLL),
                "poll_max":     str(MAX_INDEX_POLL),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return KisRealtimeOptionsFlow(config_entry)


class KisRealtimeOptionsFlow(config_entries.OptionsFlow):
    """종목/지수 추가·삭제 + 업데이트 간격 조정 Options Flow"""

    def __init__(self, config_entry):
        self._entry   = config_entry
        self._stocks  = list(config_entry.data.get(CONF_STOCKS, []))
        self._indexes = list(config_entry.data.get(CONF_INDEXES, []))
        self._throttle = config_entry.data.get(CONF_THROTTLE_SEC, DEFAULT_THROTTLE_SEC)
        self._poll     = config_entry.data.get(CONF_INDEX_POLL,   DEFAULT_INDEX_POLL)

    async def async_step_init(self, user_input=None):
        return await self.async_step_menu()

    async def async_step_menu(self, user_input=None):
        if user_input is not None:
            action = user_input.get("action")
            if action == "add_stock":
                return await self.async_step_add_stock()
            elif action == "add_index":
                return await self.async_step_add_index()
            elif action == "remove":
                return await self.async_step_remove()
            elif action == "interval":
                return await self.async_step_interval()
            else:
                return self.async_create_entry(title="", data={
                    **self._entry.data,
                    CONF_STOCKS:       self._stocks,
                    CONF_INDEXES:      self._indexes,
                    CONF_THROTTLE_SEC: self._throttle,
                    CONF_INDEX_POLL:   self._poll,
                })

        stock_list = ", ".join(f"{s['code']}({s['entity']})" for s in self._stocks)  or "없음"
        index_list = ", ".join(f"{i['code']}({i['entity']})" for i in self._indexes) or "없음"

        return self.async_show_form(
            step_id="menu",
            data_schema=vol.Schema({
                vol.Required("action", default="save"): vol.In({
                    "add_stock": "종목 추가 (ETF/개별주)",
                    "add_index": "지수 추가 (코스피/코스닥)",
                    "remove":    "종목/지수 삭제",
                    "interval":  f"업데이트 간격 조정 (현재: 종목 {self._throttle}초 / 지수 {self._poll}초)",
                    "save":      "저장",
                }),
            }),
            description_placeholders={
                "stocks":  stock_list,
                "indexes": index_list,
            },
        )

    async def async_step_interval(self, user_input=None):
        """업데이트 간격 조정"""
        if user_input is not None:
            self._throttle = user_input[CONF_THROTTLE_SEC]
            self._poll     = user_input[CONF_INDEX_POLL]
            return await self.async_step_menu()

        return self.async_show_form(
            step_id="interval",
            data_schema=vol.Schema({
                vol.Optional(CONF_THROTTLE_SEC, default=self._throttle):
                    vol.All(int, vol.Range(min=MIN_THROTTLE_SEC, max=MAX_THROTTLE_SEC)),
                vol.Optional(CONF_INDEX_POLL, default=self._poll):
                    vol.All(int, vol.Range(min=MIN_INDEX_POLL, max=MAX_INDEX_POLL)),
            }),
            description_placeholders={
                "throttle_min": str(MIN_THROTTLE_SEC),
                "throttle_max": str(MAX_THROTTLE_SEC),
                "poll_min":     str(MIN_INDEX_POLL),
                "poll_max":     str(MAX_INDEX_POLL),
            },
        )

    async def async_step_add_stock(self, user_input=None):
        errors = {}
        if user_input is not None:
            code   = str(user_input["code"]).zfill(6)
            entity = user_input["entity"].strip().lower().replace(" ", "_")
            if any(s["code"] == code for s in self._stocks):
                errors["code"] = "already_exists"
            else:
                self._stocks.append({"code": code, "entity": entity})
                return await self.async_step_menu()

        return self.async_show_form(
            step_id="add_stock",
            data_schema=vol.Schema({
                vol.Required("code"):   str,
                vol.Required("entity"): str,
            }),
            errors=errors,
        )

    async def async_step_add_index(self, user_input=None):
        errors = {}
        if user_input is not None:
            code   = str(user_input["code"]).zfill(4)
            entity = user_input["entity"].strip().lower().replace(" ", "_")
            if any(i["code"] == code for i in self._indexes):
                errors["code"] = "already_exists"
            else:
                self._indexes.append({"code": code, "entity": entity})
                return await self.async_step_menu()

        return self.async_show_form(
            step_id="add_index",
            data_schema=vol.Schema({
                vol.Required("code", default="0001"): vol.In({
                    "0001": "코스피(0001)",
                    "1001": "코스닥(1001)",
                }),
                vol.Required("entity", default="kospi"): str,
            }),
            errors=errors,
        )

    async def async_step_remove(self, user_input=None):
        all_items = (
            [f"stock:{s['code']}:{s['entity']}" for s in self._stocks] +
            [f"index:{i['code']}:{i['entity']}" for i in self._indexes]
        )
        if not all_items:
            return await self.async_step_menu()

        if user_input is not None:
            to_remove = user_input.get("items", [])
            self._stocks  = [s for s in self._stocks  if f"stock:{s['code']}:{s['entity']}" not in to_remove]
            self._indexes = [i for i in self._indexes if f"index:{i['code']}:{i['entity']}" not in to_remove]
            return await self.async_step_menu()

        return self.async_show_form(
            step_id="remove",
            data_schema=vol.Schema({
                vol.Optional("items"): vol.All([vol.In(all_items)]),
            }),
        )
