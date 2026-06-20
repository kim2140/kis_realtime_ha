# v1.6.0
# KIS 실시간 주식 시세 Sensor Entity
# - 종목: sensor.kis_{entity} (단위: KRW)
# - 지수: sensor.kis_{entity} (단위: pt)
# - attribute: 현재가, 등락률, 시/고/저, 거래량, PER, PBR, 외국인비율 등

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
    """Config Entry에서 sensor 엔티티 생성"""
    coordinator: KisRealtimeCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # 종목 sensor
    for stock in entry.data.get(CONF_STOCKS, []):
        entities.append(KisStockSensor(coordinator, stock["code"], stock["entity"]))

    # 지수 sensor
    for index in entry.data.get(CONF_INDEXES, []):
        entities.append(KisIndexSensor(coordinator, index["code"], index["entity"]))

    async_add_entities(entities, update_before_add=True)


class KisStockSensor(SensorEntity):
    """KIS 종목 실시간 시세 Sensor (ETF / 개별주)"""

    _attr_state_class        = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "KRW"
    _attr_icon               = "mdi:chart-line"
    _attr_should_poll        = False

    def __init__(self, coordinator: KisRealtimeCoordinator, code: str, entity_name: str):
        self._coordinator = coordinator
        self._code        = code
        self._entity_name = entity_name
        self._data: dict  = {}

        self._attr_unique_id   = f"kis_{entity_name}"
        self._attr_name        = f"[KIS] {entity_name} ({code})"

    async def async_added_to_hass(self):
        """HA에 등록될 때 coordinator 콜백 연결"""
        self._coordinator.register_callback(self._entity_name, self._on_data)
        # 캐시된 데이터 있으면 즉시 반영
        if self._entity_name in self._coordinator.data:
            self._data = self._coordinator.data[self._entity_name]

    async def async_will_remove_from_hass(self):
        self._coordinator.unregister_callback(self._entity_name, self._on_data)

    @callback
    def _on_data(self, data: dict):
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

    _attr_state_class        = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "pt"
    _attr_icon               = "mdi:chart-areaspline"
    _attr_should_poll        = False

    def __init__(self, coordinator: KisRealtimeCoordinator, code: str, entity_name: str):
        self._coordinator = coordinator
        self._code        = code
        self._entity_name = entity_name
        self._data: dict  = {}

        self._attr_unique_id = f"kis_{entity_name}"
        self._attr_name      = f"[KIS] {entity_name} ({code})"

    async def async_added_to_hass(self):
        self._coordinator.register_callback(self._entity_name, self._on_data)
        if self._entity_name in self._coordinator.data:
            self._data = self._coordinator.data[self._entity_name]

    async def async_will_remove_from_hass(self):
        self._coordinator.unregister_callback(self._entity_name, self._on_data)

    @callback
    def _on_data(self, data: dict):
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
