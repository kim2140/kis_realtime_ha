# v1.7.0
# KIS 실시간 주식 시세 Sensor Entity
# ─────────────────────────────────────────────────────────────────────────────
# [개요]
# KisRealtimeCoordinator에서 수신한 데이터를 HA sensor로 노출하는 파일.
# - 종목: sensor.kis_{entity} (단위: KRW)
# - 지수: sensor.kis_{entity} (단위: pt)
# - attribute: 현재가, 등락률, 시/고/저, 거래량, PER, PBR, 외국인비율 등
#
# [v1.7.0 수정사항]
# ★ 핵심 버그 수정: entry.data 대신 entry.options 우선 병합으로 종목/지수 읽기
#   - options_flow에서 저장한 종목은 entry.options에 있음
#   - 기존 코드는 entry.data만 참조해서 종목 추가 후 sensor가 생성되지 않는 문제
# ★ sensor 이름에 friendly_name 반영 (한글 이름 표시)
#   - 기존: "[KIS] stock_069500 (069500)" 형태
#   - 수정: "[KIS] KODEX 200" 형태 (friendly_name 우선)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations
from datetime import datetime
import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_STOCKS, CONF_INDEXES
from .coordinator import KisRealtimeCoordinator

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Config Entry에서 sensor 엔티티 생성.

    v1.7.0 수정: entry.options를 우선 읽도록 변경.
    종목/지수는 options_flow에서 저장되므로 entry.options에 존재하며,
    entry.data는 초기 빈 리스트([])를 가지고 있어 sensor가 생성되지 않던 문제 수정.
    """
    coordinator: KisRealtimeCoordinator = hass.data[DOMAIN][entry.entry_id]

    # ★ v1.7.0: options 우선, 없으면 data에서 읽음 (기존: entry.data만 참조)
    cfg = {**entry.data, **entry.options}

    entities = []

    # 종목 sensor 생성
    for stock in cfg.get(CONF_STOCKS, []):
        entities.append(
            KisStockSensor(
                coordinator,
                stock["code"],
                stock["entity"],
                stock.get("friendly_name", ""),  # v1.7.0: friendly_name 전달
            )
        )

    # 지수 sensor 생성
    for index in cfg.get(CONF_INDEXES, []):
        entities.append(
            KisIndexSensor(
                coordinator,
                index["code"],
                index["entity"],
                index.get("friendly_name", ""),  # v1.7.0: friendly_name 전달
            )
        )

    if entities:
        log.info(f"sensor 생성: {len(entities)}개 (종목 {len(cfg.get(CONF_STOCKS,[]))}개 / 지수 {len(cfg.get(CONF_INDEXES,[]))}개)")
    else:
        log.warning("생성할 sensor가 없습니다. 종목/지수를 먼저 추가해주세요.")

    async_add_entities(entities, update_before_add=True)


class KisStockSensor(SensorEntity):
    """KIS 종목 실시간 시세 Sensor (ETF / 개별주)"""

    _attr_state_class                 = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement  = "KRW"
    _attr_icon                        = "mdi:chart-line"
    _attr_should_poll                 = False

    def __init__(
        self,
        coordinator: KisRealtimeCoordinator,
        code: str,
        entity_name: str,
        friendly_name: str = "",   # v1.7.0: 한글 이름 파라미터 추가
    ):
        self._coordinator  = coordinator
        self._code         = code
        self._entity_name  = entity_name
        self._data: dict   = {}

        self._attr_unique_id = f"kis_{entity_name}"

        # v1.7.0: friendly_name 있으면 한글 이름 우선, 없으면 기존 형식
        if friendly_name:
            self._attr_name = f"[KIS] {friendly_name}"
        else:
            self._attr_name = f"[KIS] {entity_name} ({code})"

    async def async_added_to_hass(self):
        """HA에 등록될 때 coordinator 콜백 연결"""
        self._coordinator.register_callback(self._entity_name, self._on_data)
        # 캐시된 데이터 있으면 즉시 반영
        if self._entity_name in self._coordinator.data:
            self._data = self._coordinator.data[self._entity_name]

    async def async_will_remove_from_hass(self):
        """HA에서 제거될 때 콜백 해제"""
        self._coordinator.unregister_callback(self._entity_name, self._on_data)

    @callback
    def _on_data(self, data: dict):
        """Coordinator에서 데이터 수신 시 HA 상태 갱신"""
        self._data = data
        self.async_write_ha_state()

    @property
    def native_value(self):
        return self._data.get("price")

    @property
    def extra_state_attributes(self):
        if not self._data:
            return {}
        t = self._data.get("time", "")
        time_fmt = f"{t[0:2]}:{t[2:4]}:{t[4:6]}" if len(t) >= 6 else t
        return {
            "symbol":        self._data.get("symbol"),
            "time":          time_fmt,
            "change":        self._data.get("change"),
            "change_rate":   self._data.get("change_rate"),
            "sign":          self._data.get("sign"),
            "open":          self._data.get("open"),
            "high":          self._data.get("high"),
            "low":           self._data.get("low"),
            "ask1":          self._data.get("ask1"),
            "bid1":          self._data.get("bid1"),
            "volume":        self._data.get("volume"),
            "acc_volume":    self._data.get("acc_volume"),
            "acc_amount":    self._data.get("acc_amount"),
            "strength":      self._data.get("strength"),
            "buy_ratio":     self._data.get("buy_ratio"),
            "week52_high":   self._data.get("week52_high", 0),
            "week52_low":    self._data.get("week52_low", 0),
            "per":           self._data.get("per", "0"),
            "pbr":           self._data.get("pbr", "0"),
            "eps":           self._data.get("eps", "0"),
            "bps":           self._data.get("bps", "0"),
            "foreign_rate":  self._data.get("foreign_rate", "0"),
            "foreign_buy":   self._data.get("foreign_buy", "0"),
            "listed_shares": self._data.get("listed_shares", "0"),
            "market_cap":    self._data.get("market_cap", 0),
            "vol_rate":      self._data.get("vol_rate", "0"),
            "vwap":          self._data.get("vwap", "0"),
            "last_updated":  datetime.now().isoformat(),
        }


class KisIndexSensor(SensorEntity):
    """KIS 지수 Sensor (코스피 / 코스닥)"""

    _attr_state_class                 = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement  = "pt"
    _attr_icon                        = "mdi:chart-areaspline"
    _attr_should_poll                 = False

    def __init__(
        self,
        coordinator: KisRealtimeCoordinator,
        code: str,
        entity_name: str,
        friendly_name: str = "",   # v1.7.0: 한글 이름 파라미터 추가
    ):
        self._coordinator  = coordinator
        self._code         = code
        self._entity_name  = entity_name
        self._data: dict   = {}

        self._attr_unique_id = f"kis_{entity_name}"

        # v1.7.0: friendly_name 있으면 한글 이름 우선, 없으면 기존 형식
        if friendly_name:
            self._attr_name = f"[KIS] {friendly_name}"
        else:
            self._attr_name = f"[KIS] {entity_name} ({code})"

    async def async_added_to_hass(self):
        """HA에 등록될 때 coordinator 콜백 연결"""
        self._coordinator.register_callback(self._entity_name, self._on_data)
        if self._entity_name in self._coordinator.data:
            self._data = self._coordinator.data[self._entity_name]

    async def async_will_remove_from_hass(self):
        """HA에서 제거될 때 콜백 해제"""
        self._coordinator.unregister_callback(self._entity_name, self._on_data)

    @callback
    def _on_data(self, data: dict):
        """Coordinator에서 데이터 수신 시 HA 상태 갱신"""
        self._data = data
        self.async_write_ha_state()

    @property
    def native_value(self):
        return self._data.get("price")

    @property
    def extra_state_attributes(self):
        if not self._data:
            return {}
        t = self._data.get("time", "")
        time_fmt = f"{t[0:2]}:{t[2:4]}:{t[4:6]}" if len(t) >= 6 else t
        return {
            "symbol":       self._data.get("symbol"),
            "time":         time_fmt,
            "change":       self._data.get("change"),
            "change_rate":  self._data.get("change_rate"),
            "sign":         self._data.get("sign"),
            "open":         self._data.get("open"),
            "high":         self._data.get("high"),
            "low":          self._data.get("low"),
            "acc_volume":   self._data.get("acc_volume"),
            "acc_amount":   self._data.get("acc_amount"),
            "last_updated": datetime.now().isoformat(),
        }
