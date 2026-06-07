# ₿ Crypto Portfolio Tracker v2.0

A feature-rich **command-line crypto portfolio tracker** with live prices, P&L tracking, price alerts, export to CSV, and a beautiful terminal UI — all powered by the free [CoinGecko API](https://www.coingecko.com/en/api).

---

## Preview

```
  ╔══════════════════════════════════════════════════════════╗
  ║  ₿  CRYPTO PORTFOLIO TRACKER  v2.0  ₿                   ║
  ║      Powered by CoinGecko  •  Real-time prices           ║
  ╚══════════════════════════════════════════════════════════╝
  Saturday, June 07 2026  •  14:32:05

  ══════════════════════════════════════════════════════════════
     LIVE PORTFOLIO
  ══════════════════════════════════════════════════════════════

  ╭──────────┬───────────┬───────────────┬──────────┬──────────────╮
  │ Symbol   │ Qty       │ Price         │ 24h      │ Value        │
  ├──────────┼───────────┼───────────────┼──────────┼──────────────┤
  │ ₿ BTC    │ 0.5       │  $ 67,000.00  │ ▲  2.31% │  $33,500.00  │
  │ Ξ ETH    │ 2.0       │  $  3,500.00  │ ▼  0.85% │   $7,000.00  │
  │ ◎ SOL    │ 10.0      │     $170.00   │ ▲  1.12% │   $1,700.00  │
  ╰──────────┴───────────┴───────────────┴──────────┴──────────────╯

  ────────────────────────────────────────────────────────────
  PORTFOLIO SUMMARY
  ────────────────────────────────────────────────────────────
  ▶  Total Value    :   $42,200.00
  ▶  Total Invested :   $39,000.00
  ▶  Total P&L      :    +$3,200.00  +8.20%
```

---

## Features

| Feature | Description |
|---|---|
| **Live Prices** | Real-time prices via CoinGecko (no API key needed) |
| **P&L Tracking** | Track profit/loss per coin and total portfolio |
| **24h Change** | Color-coded 24h price movement with directional arrows |
| **Allocation Bar** | Visual breakdown of portfolio allocation per coin |
| **Price Alerts** | Get notified when a coin reaches your target price |
| **History** | Track portfolio value over time with sparkline trend |
| **CSV Export** | Export full portfolio snapshot to a timestamped CSV file |
| **Coin Info** | Detailed market data: ATH, market cap, volume, supply |
| **Spinner Animation** | Live loading spinner while fetching data |
| **Color UI** | Full ANSI color terminal interface with gradients |
| **Windows Support** | UTF-8 fix for Windows terminals built-in |

---

## Requirements

- Python **3.10+**
- Internet connection (for live prices)

### Dependencies

```bash
pip install requests tabulate
```

| Package | Purpose |
|---|---|
| `requests` | HTTP calls to the CoinGecko API |
| `tabulate` | Formatted table output in the terminal |

---

## Installation

```bash
# 1. Clone or download the script
git clone <your-repo-url>
cd crypto-portfolio-tracker

# 2. Install dependencies
pip install requests tabulate

# 3. Run it
python phyton-example-eccomerce.py show
```

No configuration needed. Data files are created automatically on first run.

---

## Usage

```
python phyton-example-eccomerce.py <command> [options]
```

### Commands

#### `add` — Add a coin to your portfolio

```bash
# Add 0.5 BTC (no buy price, P&L won't be tracked)
python phyton-example-eccomerce.py add BTC 0.5

# Add 2 ETH with buy price for P&L tracking
python phyton-example-eccomerce.py add ETH 2.0 --buy-price 3200

# Add more of an existing coin (quantity is summed, avg buy price is recalculated)
python phyton-example-eccomerce.py add BTC 0.25 --buy-price 60000
```

#### `show` — Display your portfolio with live prices

```bash
python phyton-example-eccomerce.py show
```

Shows:
- Current price and 24h change per coin
- Current value, P&L amount and P&L percentage
- Portfolio allocation bar per coin
- Total portfolio value, invested, and P&L
- Any triggered price alerts

#### `remove` — Remove a coin

```bash
python phyton-example-eccomerce.py remove BTC
```

#### `export` — Export portfolio to CSV

```bash
python phyton-example-eccomerce.py export
```

Creates a file like `portfolio_export_20260607_143200.csv` with full data including P&L, 24h change, and timestamps.

#### `history` — View portfolio value over time

```bash
# Show last 20 snapshots (default)
python phyton-example-eccomerce.py history

# Show last 10
python phyton-example-eccomerce.py history --last 10
```

A sparkline trend graph is shown at the bottom. A snapshot is saved every time you run `show`.

#### `info` — Detailed coin information

```bash
python phyton-example-eccomerce.py info SOL
```

Shows: name, CMC rank, market cap, 24h volume, circulating supply, all-time high, all-time low, and description.

#### `alert` — Set a price alert

```bash
# Alert when BTC reaches $100,000
python phyton-example-eccomerce.py alert BTC 100000
```

Alerts are displayed at the bottom of the `show` output when triggered.

#### `coins` — List all supported coins

```bash
python phyton-example-eccomerce.py coins
```

---

## Supported Coins

| Symbol | Name | Symbol | Name |
|---|---|---|---|
| BTC | Bitcoin | SHIB | Shiba Inu |
| ETH | Ethereum | TRX | Tron |
| BNB | BNB | TON | Toncoin |
| SOL | Solana | NEAR | NEAR Protocol |
| ADA | Cardano | APT | Aptos |
| DOT | Polkadot | LINK | Chainlink |
| DOGE | Dogecoin | UNI | Uniswap |
| MATIC | Polygon | LTC | Litecoin |
| AVAX | Avalanche | XRP | Ripple |
| ATOM | Cosmos | XLM | Stellar |

> Any coin not in this list can still be added by its CoinGecko ID — the tracker will try to resolve it automatically and show a warning.

---

## Data Files

All data is stored locally in the same directory as the script:

| File | Description |
|---|---|
| `portfolio.json` | Your holdings and price alerts |
| `price_history.json` | Portfolio value snapshots (max 500 entries) |
| `crypto_portfolio.log` | Operation log for debugging |

> If a data file becomes corrupt, it is automatically backed up (e.g. `portfolio.corrupt.1749300000.bak`) and a fresh one is created.

---

## API & Rate Limits

This tool uses the **CoinGecko free public API** — no API key required.

- The free tier allows ~10–30 requests/minute
- If you see a `429 Rate Limited` warning, wait ~60 seconds and try again
- All network errors are handled gracefully (timeout, no internet, HTTP errors)

---

## Error Handling

| Scenario | Behavior |
|---|---|
| No internet | Shows portfolio without prices, continues |
| API timeout | Friendly message, no crash |
| Rate limited (429) | Clear message with wait instruction |
| Corrupt data file | Auto-backup + fresh start |
| Missing dependency | Clear install instruction on startup |
| Unknown coin symbol | Warning shown, proceeds anyway |

---

## License

MIT — free to use, modify, and distribute.
