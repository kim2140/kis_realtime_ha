# v1.0.0
# KIS 실시간 주식 시세 Custom Integration
# - HA UI에서 App Key/Secret 입력 (config_flow)
# - 종목/지수 UI에서 추가/삭제 (options_flow)
# - WebSocket 실시간 체결가 (장중)
# - REST API 종가 조회 (장외/시작 시)
# - HA 재시작 시 자동 복구
# v1.2.1: options에서 stocks/indexes 읽도록 수정 (data는 초기값 빈 리스트)
# v1.3.0: 수급(기관 순매수) polling 간격(investor_poll_sec)을 coordinator에 전달하도록 추가
#   ※ config_flow.py에서 사용자가 설정한 값이 여기를 거치지 않으면 항상 기본값(300초)만 쓰이므로 필수 수정

from __future__ import annotations
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN, CONF_APP_KEY, CONF_APP_SECRET, CONF_URL_BASE, CONF_STOCKS, CONF_INDEXES,
    CONF_THROTTLE_SEC, CONF_INDEX_POLL, CONF_INVESTOR_POLL,
    DEFAULT_THROTTLE_SEC, DEFAULT_INDEX_POLL, DEFAULT_INVESTOR_POLL,
)
from .coordinator import KisRealtimeCoordinator

log = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Config Entry 설정 - Coordinator 시작
    종목/지수는 options에 저장되므로 options를 우선 읽고 없으면 data에서 읽음
    """
    hass.data.setdefault(DOMAIN, {})

    # options가 있으면 options 우선, 없으면 data에서 읽음
    cfg = {**entry.data, **entry.options}

    coordinator = KisRealtimeCoordinator(hass, {
        "app_key":         cfg[CONF_APP_KEY],
        "app_secret":      cfg[CONF_APP_SECRET],
        "url_base":        cfg.get(CONF_URL_BASE),
        "stocks":          cfg.get(CONF_STOCKS, []),
        "indexes":         cfg.get(CONF_INDEXES, []),
        CONF_THROTTLE_SEC: cfg.get(CONF_THROTTLE_SEC, DEFAULT_THROTTLE_SEC),
        CONF_INDEX_POLL:   cfg.get(CONF_INDEX_POLL,   DEFAULT_INDEX_POLL),
        CONF_INVESTOR_POLL: cfg.get(CONF_INVESTOR_POLL, DEFAULT_INVESTOR_POLL),  # v1.3.0
    })

    hass.data[DOMAIN][entry.entry_id] = coordinator
    await coordinator.async_start()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    log.info(f"KIS 실시간 시세 통합 시작 완료 (종목 {len(cfg.get(CONF_STOCKS,[]))}개 / 지수 {len(cfg.get(CONF_INDEXES,[]))}개)")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Config Entry 제거 - Coordinator 정지"""
    coordinator: KisRealtimeCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
    await coordinator.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Options 변경 시 재로드 + 삭제된 entity 제거"""
    from homeassistant.helpers import entity_registry as er

    cfg = {**entry.data, **entry.options}
    active_stocks  = {f"kis_{s['entity']}" for s in cfg.get(CONF_STOCKS, [])}
    active_indexes = {f"kis_{i['entity']}" for i in cfg.get(CONF_INDEXES, [])}
    active_entities = active_stocks | active_indexes

    # entity registry에서 삭제된 sensor 제거
    ent_reg = er.async_get(hass)
    entries = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    for entity_entry in entries:
        unique_id = entity_entry.unique_id  # "kis_{entity_name}"
        if unique_id not in active_entities:
            log.info(f"entity 삭제: {entity_entry.entity_id}")
            ent_reg.async_remove(entity_entry.entity_id)

    await hass.config_entries.async_reload(entry.entry_id)
