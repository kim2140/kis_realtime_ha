# v1.0.0
# KIS 실시간 주식 시세 Sensor Entity
# ─────────────────────────────────────────────────────────────────────────────
# [개요]
# KisRealtimeCoordinator에서 수신한 데이터를 HA sensor로 노출하는 파일.
# - 종목: sensor.kis_{종목코드} (단위: KRW)  예) sensor.kis_005930
# - 지수: sensor.kis_{entity}  (단위: pt)    예) sensor.kis_kospi
#
# [v1.7.0] options 우선 병합으로 종목/지수 읽기 버그 수정
# [v1.7.3] unique_id 제거, has_entity_name=False로 entity_id 고정
# [v1.7.4] unique_id 복구 + entity_id 고정 동시 해결
#   ★ 문제: v1.7.3에서 unique_id 제거 시 HA UI에서 entity 설정 불가 경고 발생
#   ★ 해결: unique_id는 유지하되, suggested_object_id로 entity_id를 종목코드로 고정
#     - unique_id = "kis_{code}" → HA가 entity 추적 가능 (UI 설정 정상)
#     - suggested_object_id = "kis_{code}" → registry 최초 등록 시 entity_id 고정
#     - self.entity_id 직접 지정 → 이미 등록된 entity도 강제 고정
#     - _attr_has_entity_name = False → friendly_name 기반 변환 차단
# [v1.8.0] 종목별 기관/외국인/개인 순매수(수급) 속성 추가
#   coordinator.py의 _run_investor_poll이 institution_buy/foreign_buy_qty/individual_buy/
#   investor_date를 기존 데이터에 병합해서 넘겨주므로, 여기서는 그 값을 속성으로 노출만 하면 됨.
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
    v1.7.0: entry.options 우선 병합 (종목은 options_flow에서 options에 저장됨)
    """
    coordinator: KisRealtimeCoordinator = hass.data[DOMAIN][entry.entry_id]

    cfg = {**entry.data, **entry.options}

    entities = []

    for stock in cfg.get(CONF_STOCKS, []):
        entities.append(
            KisStockSensor(
                coordinator,
                stock["code"],
                stock["entity"],
                stock.get("friendly_name", ""),
            )
        )

    for index in cfg.get(CONF_INDEXES, []):
        entities.append(
            KisIndexSensor(
                coordinator,
                index["code"],
                index["entity"],
                index.get("friendly_name", ""),
            )
        )

    if entities:
        log.info(f"sensor 생성: {len(entities)}개 (종목 {len(cfg.get(CONF_STOCKS,[]))}개 / 지수 {len(cfg.get(CONF_INDEXES,[]))}개)")
    else:
        log.warning("생성할 sensor가 없습니다. 종목/지수를 먼저 추가해주세요.")

    async_add_entities(entities, update_before_add=True)


class KisStockSensor(SensorEntity):
    """KIS 종목 실시간 시세 Sensor (ETF / 개별주)"""

    _attr_state_class                = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "KRW"
    _attr_icon                       = "mdi:chart-line"
    _attr_should_poll                = False
    # friendly_name 기반 entity_id 자동 변환 차단
    _attr_has_entity_name            = False

    def __init__(
        self,
        coordinator: KisRealtimeCoordinator,
        code: str,
        entity_name: str,
        friendly_name: str = "",
    ):
        self._coordinator = coordinator
        self._code        = code
        self._entity_name = entity_name
        self._data: dict  = {}

        # unique_id 유지 → HA UI에서 entity 설정 가능
        self._attr_unique_id = f"kis_{code}"

        # suggested_object_id → registry 최초 등록 시 entity_id를 kis_{code}로 고정
        self._attr_suggested_object_id = f"kis_{code}"

        # entity_id 직접 지정 → 이미 등록된 entity도 강제 고정
        self.entity_id = f"sensor.kis_{code}"

        # 표시 이름: friendly_name 우선, 없으면 종목코드
        self._attr_name = friendly_name if friendly_name else f"[KIS] {code}"

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
            # v1.8.0: 기관/외국인/개인 순매수 (수급) - investor polling에서 병합됨
            "institution_buy": self._data.get("institution_buy", 0),
            "foreign_buy_qty":  self._data.get("foreign_buy_qty", 0),
            "individual_buy":   self._data.get("individual_buy", 0),
            "investor_date":    self._data.get("investor_date", ""),
            "last_updated":  datetime.now().isoformat(),
        }


class KisIndexSensor(SensorEntity):
    """KIS 지수 Sensor (코스피 / 코스닥)"""

    _attr_state_class                = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "pt"
    _attr_icon                       = "mdi:chart-areaspline"
    _attr_should_poll                = False
    # friendly_name 기반 entity_id 자동 변환 차단
    _attr_has_entity_name            = False

    def __init__(
        self,
        coordinator: KisRealtimeCoordinator,
        code: str,
        entity_name: str,
        friendly_name: str = "",
    ):
        self._coordinator = coordinator
        self._code        = code
        self._entity_name = entity_name
        self._data: dict  = {}

        # unique_id 유지 → HA UI에서 entity 설정 가능
        self._attr_unique_id = f"kis_{entity_name}"

        # suggested_object_id → registry 최초 등록 시 entity_id 고정
        self._attr_suggested_object_id = f"kis_{entity_name}"

        # entity_id 직접 지정 → sensor.kis_kospi / sensor.kis_kosdaq
        self.entity_id = f"sensor.kis_{entity_name}"

        # 표시 이름: friendly_name 우선
        self._attr_name = friendly_name if friendly_name else f"[KIS] {entity_name}"

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