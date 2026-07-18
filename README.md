> 🇰🇷 [한국어 README 보기](README_KO.md)

# KIS 실시간 주식 시세 for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2023.1%2B-blue)](https://www.home-assistant.io/)
[![Version](https://img.shields.io/badge/Version-1.3.1.3-orange)]()

Real-time Korean stock/ETF prices and KOSPI/KOSDAQ index via KIS (Korea Investment & Securities) API as Home Assistant sensors.

---

## ✨ Features

| Feature | Description |
|---|---|
| **Real-time price** | KIS WebSocket (H0STCNT0), no rate limit impact |
| **KOSPI/KOSDAQ index** | REST API polling |
| **Auto after-hours** | Fetches closing price after market close, auto-reconnects at open |
| **UI configuration** | App Key/Secret, add/remove stocks, update intervals — all from HA UI |
| **Korean name support** | Set sensor display name in Korean |
| **Rich attributes** | Price, change rate, O/H/L, volume, strength, PER/PBR, foreign ratio, etc. |
| **Fixed entity ID** | Always `sensor.kis_{code}` regardless of display name |
| **Supply/demand (institutional net buy) 🆕** | Institutional/foreign/individual net buy for stocks + KOSPI/KOSDAQ market-wide totals via polling |

---

## 📦 Installation

### HACS (Recommended)

1. HACS → Integrations → ⋮ Menu → **Custom repositories**
2. URL: `https://github.com/kim2140/kis_realtime_ha` / Category: `Integration`
3. Search **KIS 실시간 주식 시세** and download
4. Restart Home Assistant

### Manual

1. Copy `custom_components/kis_realtime` to `/homeassistant/custom_components/kis_realtime/`
2. Restart Home Assistant

---

## 🔑 Getting KIS API Key

### 1. Prepare Korea Investment & Securities account
- Requires a KIS brokerage account and HTS ID

### 2. Apply for Open API service
1. Login to [KIS website](https://www.truefriend.com)
2. Go to **Banking/Service → Open API**
3. Click **Apply for Open API Service**
4. Select account and apply
5. Receive temporary password via KakaoTalk

### 3. Issue App Key / App Secret
1. Visit [KIS Developers](https://apiportal.koreainvestment.com)
2. Login with HTS ID + temporary password
3. **My Page** → **Copy App Key / App Secret**

> ⚠️ Keep your App Key and App Secret confidential.

---

## ⚙️ Configuration

### 1. Add Integration

**Settings → Devices & Services → Add Integration → `KIS 실시간 주식 시세`**

| Field | Description |
|---|---|
| App Key | App Key from KIS Developers |
| App Secret | App Secret from KIS Developers |
| Realtime update interval | Minimum WebSocket update interval during market hours (1~60s, default 3s) |
| Index poll interval | KOSPI/KOSDAQ REST polling interval (10~300s, default 30s) |
| Supply/demand poll interval 🆕 | Institutional/foreign/individual net buy REST polling interval (20~600s, default 300s/5min) |

### 2. Add Stock / Index

Integration → KIS 실시간 주식 시세 → **⚙️ Configure**

#### Add Stock (ETF / Individual)
1. Select **종목 추가**
2. Enter 6-digit stock code (e.g. `069500`)
3. Korean name is auto-fetched as suggested display name
4. Confirm/edit display name → Submit

> ⏱️ **Note:** Data may take up to 1 minute to appear due to KIS API token rate limit (1 request/min).

#### Add Index (KOSPI/KOSDAQ)
1. Select **지수 추가**
2. Choose KOSPI (0001) or KOSDAQ (1001)
3. Confirm/edit display name → Submit

#### Remove Stock / Index
1. Select **종목/지수 삭제**
2. Check items to remove → Submit → removed immediately

---

## 📊 Sensors

### Stock Sensor (`sensor.kis_{code}`)

| Attribute | Description |
|---|---|
| `price` | Current price (KRW) |
| `change` / `change_rate` | Change / Change rate (%) |
| `sign` | Direction (↑/↓/→) |
| `open` / `high` / `low` | Open / High / Low |
| `acc_volume` / `acc_amount` | Accumulated volume / amount |
| `strength` / `buy_ratio` | Trade strength / Buy ratio (market hours only) |
| `week52_high` / `week52_low` | 52-week high / low |
| `per` / `pbr` / `eps` / `bps` | Valuation metrics |
| `foreign_rate` | Foreign ownership ratio (%) |
| `market_cap` | Market cap (100M KRW) |
| `investor_institution_buy` 🆕 | Institutional net buy quantity (daily cumulative, from supply/demand polling) |
| `investor_foreign_buy` 🆕 | Foreign net buy quantity (daily cumulative) |
| `investor_individual_buy` 🆕 | Individual net buy quantity (daily cumulative) |
| `investor_date` 🆕 | Reference date for the above (YYYYMMDD) |

> ⚠️ **Note on supply/demand data**: `investor_institution_buy` etc. are based on KIS's "Stock Current Price -
> Investor" API (FHKST01010900). This is a server-aggregated snapshot, not a tick-by-tick real-time
> value like the trade price, and is refreshed via REST polling (default every 300s/5min), not WebSocket.
> The underlying KRX investor-trend data itself is only refreshed at fixed times during the day
> (09:30/10:00/11:30/13:20/14:30 provisional, 15:35/18:00 final), so polling much more often than
> that mostly returns the same repeated value.

### Index Sensor (`sensor.kis_kospi`, `sensor.kis_kosdaq`)

| Attribute | Description |
|---|---|
| `price` | Current index (pt) |
| `change` / `change_rate` | Change / Change rate |
| `open` / `high` / `low` | Open / High / Low |
| `acc_volume` | Accumulated volume |
| `investor_institution_buy` 🆕 | Market-wide institutional net buy quantity |
| `investor_foreign_buy` 🆕 | Market-wide foreign net buy quantity |
| `investor_individual_buy` 🆕 | Market-wide individual net buy quantity |
| `investor_date` 🆕 | Reference date for the above |

> ⚠️ **Index supply/demand data comes from a different source**: per-stock supply/demand uses the KIS
> API, but market-wide (index) supply/demand couldn't be matched to a KIS TR_ID, so it's fetched via
> **[pykrx](https://github.com/sharebook-kr/pykrx)**, which queries the KRX data system directly —
> independent of your KIS app key. `pykrx` is added to `manifest.json` and installed automatically by HA.

---

## 🕐 Market Hours

| Time (KST) | Behavior |
|---|---|
| 09:00 ~ 15:30 | WebSocket real-time price |
| 15:30 close | REST API fetches closing price |
| After hours / Weekend | Last closing price retained, auto-reconnect at 09:00 |

---

## 🔧 Troubleshooting

**No data after adding stock**
- KIS API token is limited to 1 request/minute
- Wait up to 1 minute after adding

**Sensor shows Unknown**
- Normal during after-hours (weekends/holidays)
- Auto-updates after 09:00 KST on weekdays

**App Key error**
- Verify App Key/Secret on KIS Developers
- Confirm Open API service is activated

**`investor_institution_buy` is 0 or looks wrong** 🆕
- Supply/demand polling has up to 5 minutes (default) delay — wait a bit
- Check the `수급 polling` debug logs in HA to see if the KIS response shape matches expectations
- These fields were implemented from community/public docs and haven't been 100% verified against a
  live KIS response — please file an issue if the field names differ

---

## 📄 License

MIT License
