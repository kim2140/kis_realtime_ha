> 🇰🇷 [한국어 README 보기](README_KO.md)

# KIS 실시간 주식 시세 for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2023.1%2B-blue)](https://www.home-assistant.io/)
[![Version](https://img.shields.io/badge/Version-1.4.0-green)]()

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
| **Moving averages (MA) 🆕** | Add SMA sensors for any period you want (e.g. 10/30/60/200 days) on top of any stock or index — multiple periods at once via a comma-separated list |

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
| MA poll interval 🆕 | Moving average recalculation interval (300~7200s, default 1800s/30min) — daily-close based, doesn't need to be frequent |

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

#### Add Moving Average (MA) 🆕
1. Select **이동평균선(MA) 추가** (requires at least one stock/index already added)
2. Choose a target stock or index
3. Enter desired periods as a comma-separated list, e.g. `10,30,60,200` — no default value, must be typed each time
4. Submit → one sensor is created per period (duplicates for the same target+period are silently skipped)

#### Remove Stock / Index / MA
1. Select **종목/지수/MA 삭제**
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
> API, but market-wide (index) supply/demand couldn't be matched to a KIS TR_ID. Three fallback tiers
> are tried in order: (1) KIS REST — currently disabled, see Troubleshooting; (2) scraping Naver
> Finance's investor-trend page directly; (3) **[pykrx](https://github.com/sharebook-kr/pykrx)**, which
> queries the KRX data system directly. Both (2) and (3) are independent of your KIS app key.
> `pandas`/`lxml`/`pykrx` are added to `manifest.json` and installed automatically by HA.
> ✅ As of v1.3.2, the Naver scraping path (tier 2) has been confirmed working on a live HA instance for
> both KOSPI and KOSDAQ. A related bug where price polling could wipe out the supply/demand fields right
> after they were set has also been fixed (see `_notify` in `coordinator.py`).

### Moving Average Sensor (`sensor.kis_{code}_ma{period}`) 🆕

| Attribute | Description |
|---|---|
| `price` (state) | The moving average value itself (KRW for stocks, pt for indices) |
| `base_code` | Underlying stock code or index code the MA is calculated from |
| `market_type` | `stock` or `index` |
| `period` | The period this sensor represents (e.g. `20` for a 20-day MA) |
| `data_points` | How many days of history were actually used — if lower than `period`, the calculation was skipped that cycle (see below) |
| `last_calc` | Timestamp of the last successful calculation |

Values are recalculated every `ma_poll_sec` (default 30 min) by `coordinator._run_ma_poll()`, which pulls
daily closing-price history via KIS's period-price API (`FHKST03010100`, shared by stocks and indices) and
computes a simple moving average (SMA) locally — neither KIS nor Yahoo Finance provide pre-computed moving
averages, so this is calculated client-side like any other MA-based indicator.

If `data_points` stays below the requested `period`, the sensor keeps its last known value and a warning is
logged (`[MA] {entity}: 확보된 데이터(N일)가 요청 기간(M일)보다 적어 계산 스킵`) — this means not enough
history was retrieved that cycle, not that the value is wrong.

> ⚠️ **Index MA uses a 3-tier fallback, same spirit as index supply/demand**: KIS's period-price endpoint
> only documents `FID_COND_MRKT_DIV_CODE` values `J` (stock/ETF/ETN) and `W` (ELW) — the `U` code used here
> for indices is unverified and may not work. If KIS REST returns nothing, the integration falls back to
> (2) **pykrx** (`get_index_ohlcv`), and if that also fails (e.g. pykrx gets blocked by KRX, which has
> happened before with the supply/demand feature), to (3) **scraping Naver Finance's
> `sise_index_day.naver` page** directly, paging through ~10 days per page until enough history is
> collected. ✅ Confirmed working end-to-end on a live HA instance for KOSPI 200-day MA (via the Naver
> fallback tier) as of v1.4.0. If it fails for you, check the HA logs for lines starting with `[MA]` —
> they show exactly which tier failed and why.

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

**MA sensor shows `Unknown` or is stuck at an old value** 🆕
- Check HA logs for `[MA]` lines — each fallback tier (KIS REST → pykrx → Naver) logs why it failed
- `data_points` attribute lower than `period` means not enough history was retrieved that cycle; the
  sensor keeps its previous value rather than showing a wrong average
- For index MA specifically, if pykrx is failing (`pykrx 지수 OHLCV ... 실패`), the Naver fallback should
  kick in automatically — if that also fails, the page structure may have changed; open an issue with the
  log line

---

## 📄 License

MIT License
