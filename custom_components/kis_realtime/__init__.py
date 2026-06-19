# v1.0.0
# KIS 실시간 주식 시세 Custom Integration
# - HA UI에서 App Key/Secret 입력 (config_flow)
# - 종목/지수 UI에서 추가/삭제 (options_flow)
# - WebSocket 실시간 체결가 (장중)
# - REST API 종가 조회 (장외/시작 시)
# - HA 재시작 시 자동 복구

from __future__ import annotations
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_APP_KEY, CONF_APP_SECRET, CONF_URL_BASE, CONF_STOCKS, CONF_INDEXES
from .coordinator import KisRealtimeCoordinator

log = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Config Entry 설정 - Coordinator 시작"""
    hass.data.setdefault(DOMAIN, {})

    coordinator = KisRealtimeCoordinator(hass, {
        "app_key":    entry.data[CONF_APP_KEY],
        "app_secret": entry.data[CONF_APP_SECRET],
        "url_base":   entry.data.get(CONF_URL_BASE),
        "stocks":     entry.data.get(CONF_STOCKS, []),
        "indexes":    entry.data.get(CONF_INDEXES, []),
    })

    hass.data[DOMAIN][entry.entry_id] = coordinator
    await coordinator.async_start()

    # Options 변경 시 coordinator 재설정
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    log.info("KIS 실시간 시세 통합 시작 완료")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Config Entry 제거 - Coordinator 정지"""
    coordinator: KisRealtimeCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
    await coordinator.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Options 변경 시 재로드"""
    await hass.config_entries.async_reload(entry.entry_id)
