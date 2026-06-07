#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════╗
║           CRYPTO PORTFOLIO TRACKER  v2.0                  ║
║         Live prices powered by CoinGecko API              ║
╚═══════════════════════════════════════════════════════════╝

Usage:
    python crypto_portfolio.py add BTC 0.5 --buy-price 45000
    python crypto_portfolio.py add ETH 2.0
    python crypto_portfolio.py show
    python crypto_portfolio.py remove BTC
    python crypto_portfolio.py export
    python crypto_portfolio.py history --last 10
    python crypto_portfolio.py info SOL
    python crypto_portfolio.py alert BTC 100000
    python crypto_portfolio.py coins
"""

import argparse
import csv
import io
import json
import logging
import sys
import time
import threading
import itertools
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─── UTF-8 fix for Windows terminals (must be before any print) ───────────────
if hasattr(sys.stdout, "buffer") and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer") and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    import requests
except ImportError:
    print("\n  [ERROR] Missing dependency: requests\n  Run: pip install requests tabulate\n")
    sys.exit(1)

try:
    from tabulate import tabulate
except ImportError:
    print("\n  [ERROR] Missing dependency: tabulate\n  Run: pip install requests tabulate\n")
    sys.exit(1)

# ─── Config ───────────────────────────────────────────────────────────────────

PORTFOLIO_FILE = Path("portfolio.json")
HISTORY_FILE   = Path("price_history.json")
LOG_FILE       = Path("crypto_portfolio.log")
API_BASE       = "https://api.coingecko.com/api/v3"
CURRENCY       = "usd"

COIN_ID_MAP = {
    "BTC":   "bitcoin",
    "ETH":   "ethereum",
    "BNB":   "binancecoin",
    "SOL":   "solana",
    "ADA":   "cardano",
    "DOT":   "polkadot",
    "DOGE":  "dogecoin",
    "MATIC": "matic-network",
    "AVAX":  "avalanche-2",
    "LINK":  "chainlink",
    "UNI":   "uniswap",
    "LTC":   "litecoin",
    "XRP":   "ripple",
    "ATOM":  "cosmos",
    "XLM":   "stellar",
    "SHIB":  "shiba-inu",
    "TRX":   "tron",
    "TON":   "the-open-network",
    "NEAR":  "near",
    "APT":   "aptos",
}

COIN_EMOJI = {
    "BTC": "₿", "ETH": "Ξ", "BNB": "◈", "SOL": "◎", "ADA": "₳",
    "DOT": "●", "DOGE": "Ð", "MATIC": "⬡", "AVAX": "▲", "LINK": "⬡",
    "UNI": "🦄", "LTC": "Ł", "XRP": "✕", "ATOM": "⚛", "XLM": "✦",
    "SHIB": "🐕", "TRX": "♦", "TON": "💎", "NEAR": "Ⓝ", "APT": "◆",
}

# ─── ANSI Colors & Styles ─────────────────────────────────────────────────────

class C:
    RESET       = "\033[0m"
    BOLD        = "\033[1m"
    DIM         = "\033[2m"
    ITALIC      = "\033[3m"
    UNDERLINE   = "\033[4m"

    BLACK       = "\033[30m"
    RED         = "\033[31m"
    GREEN       = "\033[32m"
    YELLOW      = "\033[33m"
    BLUE        = "\033[34m"
    MAGENTA     = "\033[35m"
    CYAN        = "\033[36m"
    WHITE       = "\033[37m"

    BG_BLACK    = "\033[40m"
    BG_RED      = "\033[41m"
    BG_GREEN    = "\033[42m"
    BG_YELLOW   = "\033[43m"
    BG_BLUE     = "\033[44m"
    BG_MAGENTA  = "\033[45m"
    BG_CYAN     = "\033[46m"
    BG_WHITE    = "\033[47m"

    # Bright variants
    BRIGHT_RED     = "\033[91m"
    BRIGHT_GREEN   = "\033[92m"
    BRIGHT_YELLOW  = "\033[93m"
    BRIGHT_BLUE    = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN    = "\033[96m"
    BRIGHT_WHITE   = "\033[97m"

    # 256-color helpers
    GOLD    = "\033[38;5;220m"
    ORANGE  = "\033[38;5;208m"
    PURPLE  = "\033[38;5;135m"
    TEAL    = "\033[38;5;37m"
    PINK    = "\033[38;5;213m"
    LIME    = "\033[38;5;118m"

    BG_DARK  = "\033[48;5;234m"
    BG_NAVY  = "\033[48;5;17m"

def c(text: str, *codes: str) -> str:
    return "".join(codes) + str(text) + C.RESET

def gradient_text(text: str, colors: list) -> str:
    result = ""
    n = len(colors)
    for i, ch in enumerate(text):
        result += colors[i % n] + ch
    return result + C.RESET

# ─── Spinner ──────────────────────────────────────────────────────────────────

class Spinner:
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message: str = "Loading"):
        self.message = message
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self) -> None:
        for frame in itertools.cycle(self.FRAMES):
            if self._stop_event.is_set():
                break
            sys.stdout.write(f"\r  {c(frame, C.BRIGHT_CYAN, C.BOLD)}  {c(self.message, C.CYAN, C.ITALIC)}  ")
            sys.stdout.flush()
            time.sleep(0.08)
        sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
        sys.stdout.flush()

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop_event.set()
        self._thread.join()

# ─── Boot Animation ───────────────────────────────────────────────────────────

def _type_print(text: str, delay: float = 0.018) -> None:
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write("\n")
    sys.stdout.flush()

def _boot_step(label: str, duration: float = 0.4) -> None:
    frames = ["[    ]", "[=   ]", "[==  ]", "[=== ]", "[====]"]
    end = time.time() + duration
    i = 0
    while time.time() < end:
        f = frames[i % len(frames)]
        sys.stdout.write(f"\r  {c(f, C.BRIGHT_CYAN)}  {c(label, C.DIM)}  ")
        sys.stdout.flush()
        time.sleep(0.07)
        i += 1
    sys.stdout.write(f"\r  {c('[DONE]', C.BRIGHT_GREEN, C.BOLD)}  {c(label, C.WHITE)}          \n")
    sys.stdout.flush()

def _progress_bar(label: str, width: int = 30, duration: float = 0.6) -> None:
    steps = width
    delay = duration / steps
    for i in range(steps + 1):
        filled = "█" * i
        empty  = "░" * (steps - i)
        pct    = int(i / steps * 100)
        bar_col = C.BRIGHT_GREEN if pct == 100 else C.BRIGHT_CYAN
        sys.stdout.write(
            f"\r  {c(label, C.DIM)}  {c(filled, bar_col)}{c(empty, C.DIM)}  "
            f"{c(f'{pct:>3}%', C.BRIGHT_WHITE, C.BOLD)}"
        )
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write("\n")
    sys.stdout.flush()

def _animate_counter(label: str, target: float, prefix: str = "$", duration: float = 0.5) -> None:
    steps = 30
    delay = duration / steps
    for i in range(steps + 1):
        val = target * (i / steps)
        sys.stdout.write(
            f"\r  {c('▶', C.BRIGHT_CYAN)}  {c(label, C.DIM)}  "
            f"{c(f'{prefix}{val:>12,.2f}', C.GOLD, C.BOLD)}"
        )
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write("\n")
    sys.stdout.flush()

def _clear() -> None:
    import subprocess
    subprocess.run("cls" if sys.platform == "win32" else "clear", shell=True)

def print_boot_screen() -> None:
    _clear()
    logo_lines = [
        "",
        "  ██████╗ ██████╗ ██╗   ██╗██████╗ ████████╗ ██████╗",
        "  ██╔════╝██╔══██╗╚██╗ ██╔╝██╔══██╗╚══██╔══╝██╔═══██╗",
        "  ██║     ██████╔╝ ╚████╔╝ ██████╔╝   ██║   ██║   ██║",
        "  ██║     ██╔══██╗  ╚██╔╝  ██╔═══╝    ██║   ██║   ██║",
        "  ╚██████╗██║  ██║   ██║   ██║        ██║   ╚██████╔╝",
        "   ╚═════╝╚═╝  ╚═╝   ╚═╝   ╚═╝        ╚═╝    ╚═════╝ ",
        "",
        "        ██████╗  ██████╗ ██████╗ ████████╗",
        "        ██╔══██╗██╔═══██╗██╔══██╗╚══██╔══╝",
        "        ██████╔╝██║   ██║██████╔╝   ██║   ",
        "        ██╔═══╝ ██║   ██║██╔══██╗   ██║   ",
        "        ██║     ╚██████╔╝██║  ██║   ██║   ",
        "        ╚═╝      ╚═════╝ ╚═╝  ╚═╝   ╚═╝  ",
        "",
    ]
    grad = [C.BRIGHT_BLUE, C.BRIGHT_CYAN, C.CYAN, C.BRIGHT_CYAN, C.BRIGHT_BLUE]
    for i, line in enumerate(logo_lines):
        col = grad[i % len(grad)]
        print(c(line, col, C.BOLD))
        time.sleep(0.03)

    print(c("  " + "─" * 56, C.DIM))
    _type_print(c("  ₿  Portfolio Tracker  v2.0  •  Powered by CoinGecko", C.GOLD, C.BOLD), delay=0.012)
    print(c("  " + "─" * 56, C.DIM))
    print()

    boot_steps = [
        ("Initializing core modules",   0.35),
        ("Loading portfolio database",  0.40),
        ("Connecting to CoinGecko API", 0.35),
        ("Applying color theme",        0.25),
    ]
    for label, dur in boot_steps:
        _boot_step(label, dur)

    print()
    _progress_bar("System startup", width=28, duration=0.5)
    print()
    print(f"  {c('✔', C.BRIGHT_GREEN, C.BOLD)}  {c('Ready!', C.BRIGHT_GREEN, C.BOLD)}  "
          f"{c(datetime.now().strftime('%H:%M:%S'), C.DIM)}")
    print()
    time.sleep(0.3)

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ─── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class Holding:
    symbol:        str
    quantity:      float
    avg_buy_price: float = 0.0
    added_at:      str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class Portfolio:
    holdings: dict = field(default_factory=dict)
    alerts:   dict = field(default_factory=dict)

    def add(self, symbol: str, quantity: float, buy_price: float = 0.0) -> None:
        symbol = symbol.upper()
        if symbol in self.holdings:
            existing = self.holdings[symbol]
            total_qty = existing.quantity + quantity
            if buy_price > 0 and existing.avg_buy_price > 0:
                existing.avg_buy_price = (
                    (existing.avg_buy_price * existing.quantity + buy_price * quantity)
                    / total_qty
                )
            elif buy_price > 0:
                existing.avg_buy_price = buy_price
            existing.quantity = total_qty
            log.info(f"Updated {symbol}: now holding {total_qty:.8f}")
        else:
            self.holdings[symbol] = Holding(symbol, quantity, buy_price)
            log.info(f"Added {symbol}: {quantity:.8f} @ ${buy_price or 'market'}")

    def remove(self, symbol: str) -> bool:
        symbol = symbol.upper()
        if symbol in self.holdings:
            del self.holdings[symbol]
            log.info(f"Removed {symbol} from portfolio")
            return True
        return False

    def set_alert(self, symbol: str, target_price: float) -> None:
        symbol = symbol.upper()
        self.alerts[symbol] = target_price
        log.info(f"Alert set: {symbol} @ ${target_price:,.2f}")

    def to_dict(self) -> dict:
        return {
            "holdings": {s: asdict(h) for s, h in self.holdings.items()},
            "alerts":   self.alerts,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Portfolio":
        p = cls()
        for symbol, hdict in data.get("holdings", {}).items():
            try:
                p.holdings[symbol] = Holding(**hdict)
            except TypeError:
                log.warning(f"Skipping malformed holding entry for {symbol}")
        p.alerts = data.get("alerts", {})
        return p

# ─── Persistence ──────────────────────────────────────────────────────────────

def load_portfolio() -> Portfolio:
    if PORTFOLIO_FILE.exists():
        try:
            data = json.loads(PORTFOLIO_FILE.read_text(encoding="utf-8"))
            return Portfolio.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            log.warning(f"Corrupt portfolio file, starting fresh: {e}")
            _backup_corrupt_file(PORTFOLIO_FILE)
    return Portfolio()

def save_portfolio(portfolio: Portfolio) -> None:
    PORTFOLIO_FILE.write_text(
        json.dumps(portfolio.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

def load_history() -> list:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("Corrupt history file, resetting.")
            _backup_corrupt_file(HISTORY_FILE)
    return []

def save_history(entry: dict) -> None:
    history = load_history()
    history.append(entry)
    if len(history) > 500:
        history = history[-500:]
    HISTORY_FILE.write_text(
        json.dumps(history, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

def _backup_corrupt_file(path: Path) -> None:
    backup = path.with_suffix(f".corrupt.{int(time.time())}.bak")
    try:
        path.rename(backup)
        log.info(f"Corrupt file backed up to: {backup}")
    except OSError:
        pass

# ─── API ──────────────────────────────────────────────────────────────────────

def resolve_coin_id(symbol: str) -> str:
    return COIN_ID_MAP.get(symbol.upper(), symbol.lower())

def fetch_prices(symbols: list) -> dict:
    if not symbols:
        return {}
    ids = [resolve_coin_id(s) for s in symbols]
    ids_str = ",".join(ids)
    try:
        resp = requests.get(
            f"{API_BASE}/simple/price",
            params={
                "ids":              ids_str,
                "vs_currencies":    CURRENCY,
                "include_24hr_change": "true",
            },
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json()

        prices = {}
        for symbol, coin_id in zip(symbols, ids):
            if coin_id in raw:
                prices[symbol.upper()] = {
                    "price":      raw[coin_id].get(CURRENCY, 0) or 0,
                    "change_24h": raw[coin_id].get(f"{CURRENCY}_24h_change", 0) or 0,
                }
            else:
                log.warning(f"No price data for {symbol} (id={coin_id})")
        return prices

    except requests.exceptions.ConnectionError:
        print(c("\n  No internet connection — showing portfolio without live prices.\n", C.BRIGHT_YELLOW))
        return {}
    except requests.exceptions.Timeout:
        print(c("\n  API request timed out — try again in a moment.\n", C.BRIGHT_YELLOW))
        return {}
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "?"
        if status == 429:
            print(c("\n  Rate limited by CoinGecko (429) — wait ~60s and try again.\n", C.BRIGHT_YELLOW))
        else:
            print(c(f"\n  API HTTP error {status}: {e}\n", C.BRIGHT_RED))
        return {}
    except (ValueError, KeyError) as e:
        log.error(f"Unexpected API response format: {e}")
        return {}

def fetch_coin_info(symbol: str) -> Optional[dict]:
    coin_id = resolve_coin_id(symbol)
    try:
        resp = requests.get(f"{API_BASE}/coins/{coin_id}", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        market = data.get("market_data", {})
        return {
            "name":        data.get("name", "N/A"),
            "rank":        data.get("market_cap_rank", "N/A"),
            "market_cap":  market.get("market_cap", {}).get(CURRENCY),
            "volume_24h":  market.get("total_volume", {}).get(CURRENCY),
            "circulating": market.get("circulating_supply"),
            "ath":         market.get("ath", {}).get(CURRENCY),
            "ath_date":    (market.get("ath_date", {}).get(CURRENCY, "") or "")[:10],
            "atl":         market.get("atl", {}).get(CURRENCY),
            "description": (data.get("description", {}).get("en", "") or "")[:300],
        }
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "?"
        print(c(f"\n  Could not fetch info for {symbol.upper()} (HTTP {status}).\n", C.BRIGHT_RED))
        return None
    except Exception as e:
        log.error(f"fetch_coin_info error for {symbol}: {e}")
        print(c(f"\n  Unexpected error fetching info for {symbol.upper()}.\n", C.BRIGHT_RED))
        return None

# ─── Visual Helpers ───────────────────────────────────────────────────────────

def bar(value: float, max_val: float, width: int = 12) -> str:
    filled = int((value / max_val) * width) if max_val > 0 else 0
    filled = max(0, min(filled, width))
    bar_str = "█" * filled + "░" * (width - filled)
    return c(bar_str, C.BRIGHT_CYAN)

def sparkline(values: list) -> str:
    blocks = " ▁▂▃▄▅▆▇█"
    if not values or max(values) == min(values):
        return c("─" * len(values), C.DIM)
    mn, mx = min(values), max(values)
    result = ""
    for v in values:
        idx = int((v - mn) / (mx - mn) * (len(blocks) - 1))
        ch = blocks[idx]
        col = C.BRIGHT_GREEN if v >= values[0] else C.BRIGHT_RED
        result += col + ch
    return result + C.RESET

def fmt_price(value: float) -> str:
    if value == 0:
        return c("N/A", C.DIM)
    if value >= 1:
        return c(f"${value:>13,.2f}", C.BRIGHT_WHITE)
    return c(f"${value:>13,.8f}", C.BRIGHT_WHITE)

def fmt_change(pct: float) -> str:
    arrow = "▲" if pct >= 0 else "▼"
    col = C.BRIGHT_GREEN if pct >= 0 else C.BRIGHT_RED
    return c(f"{arrow} {abs(pct):>5.2f}%", col, C.BOLD)

def fmt_pnl(value: float) -> str:
    col = C.BRIGHT_GREEN if value >= 0 else C.BRIGHT_RED
    sign = "+" if value >= 0 else ""
    return c(f"{sign}${value:>10,.2f}", col, C.BOLD)

def fmt_pnl_pct(pct: float) -> str:
    col = C.BRIGHT_GREEN if pct >= 0 else C.BRIGHT_RED
    sign = "+" if pct >= 0 else ""
    return c(f"{sign}{pct:.2f}%", col)

def coin_label(symbol: str) -> str:
    emoji = COIN_EMOJI.get(symbol, "◆")
    return c(f"{emoji} {symbol}", C.GOLD, C.BOLD)

def divider(char: str = "─", width: int = 72, color: str = C.DIM) -> str:
    return c(char * width, color)

def section_header(title: str) -> str:
    line = "═" * 70
    return (
        f"\n  {c(line, C.BRIGHT_BLUE)}\n"
        f"  {c('  ' + title + '  ', C.BOLD, C.BG_NAVY, C.BRIGHT_WHITE)}\n"
        f"  {c(line, C.BRIGHT_BLUE)}\n"
    )

BOOT_FLAG = Path(".crypto_boot_done")

def print_banner() -> None:
    if not BOOT_FLAG.exists():
        print_boot_screen()
        BOOT_FLAG.write_text("1")
    else:
        # compact header for subsequent runs
        print()
        print(c("  ╔══════════════════════════════════════════════════════════╗", C.BRIGHT_BLUE, C.BOLD))
        print(c("  ║  ₿  CRYPTO PORTFOLIO TRACKER  v2.0  •  CoinGecko        ║", C.BRIGHT_CYAN, C.BOLD))
        print(c("  ╚══════════════════════════════════════════════════════════╝", C.BRIGHT_BLUE, C.BOLD))
    ts = datetime.now().strftime("%A, %B %d %Y  •  %H:%M:%S")
    print(f"  {c('  ' + ts + '  ', C.DIM)}\n")

def print_success(msg: str) -> None:
    print(f"\n  {c('✔', C.BRIGHT_GREEN, C.BOLD)}  {c(msg, C.GREEN)}\n")

def print_warning(msg: str) -> None:
    print(f"\n  {c('⚠', C.BRIGHT_YELLOW, C.BOLD)}  {c(msg, C.YELLOW)}\n")

def print_error(msg: str) -> None:
    print(f"\n  {c('✖', C.BRIGHT_RED, C.BOLD)}  {c(msg, C.RED)}\n")

def animate_value(label: str, value: str) -> None:
    print(f"  {c('▶', C.BRIGHT_CYAN)}  {c(label, C.DIM)}  {value}")

# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_show(portfolio: Portfolio) -> None:
    if not portfolio.holdings:
        print_warning("Portfolio is empty. Use 'add' to get started.")
        return

    symbols = list(portfolio.holdings.keys())
    print(section_header("LIVE PORTFOLIO"))

    with Spinner("Fetching live prices from CoinGecko"):
        prices_data = fetch_prices(symbols)

    rows = []
    total_value    = 0.0
    total_invested = 0.0
    timestamp      = datetime.now().isoformat()
    max_value      = 0.0

    entries = []
    for symbol, holding in portfolio.holdings.items():
        pdata      = prices_data.get(symbol, {})
        price      = float(pdata.get("price", 0) or 0)
        change_24h = float(pdata.get("change_24h", 0) or 0)
        value      = price * holding.quantity
        invested   = holding.avg_buy_price * holding.quantity if holding.avg_buy_price > 0 else 0.0
        pnl        = value - invested if invested > 0 else 0.0
        pnl_pct    = (pnl / invested * 100) if invested > 0 else 0.0
        total_value    += value
        total_invested += invested
        max_value = max(max_value, value)
        entries.append((symbol, holding, price, change_24h, value, invested, pnl, pnl_pct))

    for symbol, holding, price, change_24h, value, invested, pnl, pnl_pct in entries:
        allocation_bar = bar(value, total_value, width=10) if total_value > 0 else c("░" * 10, C.DIM)
        alloc_pct = (value / total_value * 100) if total_value > 0 else 0

        rows.append([
            coin_label(symbol),
            c(f"{holding.quantity:.6f}".rstrip("0").rstrip("."), C.WHITE),
            fmt_price(price) if price else c("N/A", C.DIM),
            fmt_change(change_24h) if price else c("—", C.DIM),
            fmt_price(value) if price else c("—", C.DIM),
            fmt_pnl(pnl) if invested > 0 else c("—", C.DIM),
            fmt_pnl_pct(pnl_pct) if invested > 0 else c("—", C.DIM),
            f"{allocation_bar} {c(f'{alloc_pct:.1f}%', C.DIM)}",
        ])

    headers = [
        c("Symbol",     C.BRIGHT_CYAN, C.BOLD),
        c("Qty",        C.BRIGHT_CYAN, C.BOLD),
        c("Price",      C.BRIGHT_CYAN, C.BOLD),
        c("24h",        C.BRIGHT_CYAN, C.BOLD),
        c("Value",      C.BRIGHT_CYAN, C.BOLD),
        c("P&L",        C.BRIGHT_CYAN, C.BOLD),
        c("P&L %",      C.BRIGHT_CYAN, C.BOLD),
        c("Allocation", C.BRIGHT_CYAN, C.BOLD),
    ]

    print(tabulate(rows, headers=headers, tablefmt="rounded_outline"))

    # ── Totals panel ──
    print(f"\n  {divider('─', 60, C.BRIGHT_BLUE)}")
    print(f"  {c('PORTFOLIO SUMMARY', C.BOLD, C.BRIGHT_WHITE)}")
    print(f"  {divider('─', 60, C.BRIGHT_BLUE)}")
    _animate_counter("Total Value    :", total_value, prefix="$", duration=0.6)
    if total_invested > 0:
        total_pnl     = total_value - total_invested
        total_pnl_pct = (total_pnl / total_invested) * 100
        _animate_counter("Total Invested :", total_invested, prefix="$", duration=0.4)
        animate_value("Total P&L      :", fmt_pnl(total_pnl) + "  " + fmt_pnl_pct(total_pnl_pct))
    print(f"  {divider('─', 60, C.BRIGHT_BLUE)}")

    # ── Alerts ──
    triggered = []
    for symbol, target in portfolio.alerts.items():
        pdata = prices_data.get(symbol, {})
        price = float(pdata.get("price", 0) or 0)
        if price and price >= target:
            triggered.append((symbol, price, target))

    if triggered:
        print(f"\n  {c('🔔  PRICE ALERTS TRIGGERED', C.BOLD, C.BRIGHT_YELLOW)}")
        print(f"  {divider('─', 50, C.YELLOW)}")
        for sym, pr, tg in triggered:
            print(f"  {c('!', C.BRIGHT_YELLOW, C.BOLD)}  {c(sym, C.GOLD, C.BOLD)} reached "
                  f"{c(f'${pr:,.2f}', C.BRIGHT_WHITE, C.BOLD)} "
                  f"{c(f'(target: ${tg:,.2f})', C.DIM)}")

    # ── Save snapshot ──
    save_history({
        "timestamp":   timestamp,
        "total_value": total_value,
        "prices":      {s: prices_data.get(s, {}).get("price", 0) for s in symbols},
    })
    log.info(f"Portfolio snapshot saved — total value: ${total_value:,.2f}")
    print()


def cmd_add(portfolio: Portfolio, symbol: str, quantity: float, buy_price: float) -> None:
    symbol = symbol.upper()
    if symbol not in COIN_ID_MAP:
        known = ", ".join(sorted(COIN_ID_MAP.keys()))
        print_warning(f"'{symbol}' is not in the built-in coin list.\n"
                      f"  Supported: {known}\n"
                      f"  Proceeding anyway — verify the symbol is correct.")
    portfolio.add(symbol, quantity, buy_price)
    save_portfolio(portfolio)
    label = coin_label(symbol)
    price_str = f" @ {c(f'${buy_price:,.2f}', C.GOLD)}" if buy_price else ""
    print_success(f"Added {c(f'{quantity}', C.BRIGHT_WHITE)} {label}{price_str} to portfolio.")


def cmd_remove(portfolio: Portfolio, symbol: str) -> None:
    symbol = symbol.upper()
    if portfolio.remove(symbol):
        save_portfolio(portfolio)
        print_success(f"Removed {coin_label(symbol)} from portfolio.")
    else:
        print_error(f"{symbol} not found in portfolio.")


def cmd_export(portfolio: Portfolio) -> None:
    if not portfolio.holdings:
        print_warning("Portfolio is empty — nothing to export.")
        return

    symbols = list(portfolio.holdings.keys())
    with Spinner("Fetching prices for export"):
        prices_data = fetch_prices(symbols)

    filename = f"portfolio_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Symbol", "Quantity", "Avg Buy Price", "Current Price",
            "Current Value", "P&L", "P&L %", "24h Change %", "Added At",
        ])
        for symbol, holding in portfolio.holdings.items():
            pdata      = prices_data.get(symbol, {})
            price      = float(pdata.get("price", 0) or 0)
            change_24h = float(pdata.get("change_24h", 0) or 0)
            value      = price * holding.quantity
            invested   = holding.avg_buy_price * holding.quantity if holding.avg_buy_price else 0.0
            pnl        = value - invested if invested else 0.0
            pnl_pct    = (pnl / invested * 100) if invested else 0.0
            writer.writerow([
                symbol,
                holding.quantity,
                holding.avg_buy_price or "",
                price or "",
                value or "",
                f"{pnl:.2f}" if invested else "",
                f"{pnl_pct:.2f}" if invested else "",
                f"{change_24h:.2f}",
                holding.added_at,
            ])

    print_success(f"Exported to: {c(filename, C.BRIGHT_CYAN, C.UNDERLINE)}")
    log.info(f"Portfolio exported to {filename}")


def cmd_history(n: int = 20) -> None:
    history = load_history()
    if not history:
        print_warning("No history yet. Run 'show' to start recording snapshots.")
        return

    print(section_header("PORTFOLIO HISTORY"))

    recent = history[-n:]
    rows = []
    values = [e.get("total_value", 0) for e in recent]

    for i, entry in enumerate(recent):
        ts  = entry.get("timestamp", "")[:19].replace("T", " ")
        val = entry.get("total_value", 0)
        prev_val = recent[i - 1].get("total_value", 0) if i > 0 else val
        delta = val - prev_val
        delta_str = (
            c(f"+${delta:,.2f}", C.BRIGHT_GREEN) if delta > 0
            else c(f"-${abs(delta):,.2f}", C.BRIGHT_RED) if delta < 0
            else c("   —  ", C.DIM)
        )
        rows.append([
            c(ts, C.DIM),
            c(f"${val:,.2f}", C.BRIGHT_WHITE, C.BOLD),
            delta_str,
        ])

    headers = [
        c("Timestamp",       C.BRIGHT_CYAN, C.BOLD),
        c("Portfolio Value", C.BRIGHT_CYAN, C.BOLD),
        c("Change",          C.BRIGHT_CYAN, C.BOLD),
    ]
    print(tabulate(rows, headers=headers, tablefmt="rounded_outline"))

    # sparkline
    if len(values) > 1:
        spark = sparkline(values)
        print(f"\n  {c('Trend:', C.DIM)}  {spark}\n")

    if len(history) >= 2:
        first_val = history[0].get("total_value", 0)
        last_val  = history[-1].get("total_value", 0)
        delta     = last_val - first_val
        delta_pct = (delta / first_val * 100) if first_val else 0
        print(f"  {c('Since first snapshot:', C.DIM)}  {fmt_pnl(delta)}  {fmt_pnl_pct(delta_pct)}")
    print()


def cmd_info(symbol: str) -> None:
    print(section_header(f"COIN INFO — {symbol.upper()}"))
    with Spinner(f"Fetching data for {symbol.upper()}"):
        info = fetch_coin_info(symbol)

    if not info:
        return

    def safe_num(v, fmt=",.0f", prefix="$"):
        return f"{prefix}{v:{fmt}}" if v is not None else "N/A"

    rows = [
        [c("Name",            C.BRIGHT_CYAN), c(info.get("name", "N/A"),              C.BRIGHT_WHITE, C.BOLD)],
        [c("CMC Rank",        C.BRIGHT_CYAN), c(f"#{info.get('rank', 'N/A')}",        C.GOLD, C.BOLD)],
        [c("Market Cap",      C.BRIGHT_CYAN), c(safe_num(info.get("market_cap")),      C.WHITE)],
        [c("24h Volume",      C.BRIGHT_CYAN), c(safe_num(info.get("volume_24h")),      C.WHITE)],
        [c("Circulating",     C.BRIGHT_CYAN), c(safe_num(info.get("circulating"), ",.0f", ""), C.WHITE)],
        [c("All-Time High",   C.BRIGHT_CYAN), c(safe_num(info.get("ath"), ",.2f") + f"  {c('(' + info.get('ath_date','') + ')', C.DIM)}", C.BRIGHT_GREEN)],
        [c("All-Time Low",    C.BRIGHT_CYAN), c(safe_num(info.get("atl"), ",.4f"),    C.BRIGHT_RED)],
    ]
    print(tabulate(rows, tablefmt="rounded_outline"))

    desc = (info.get("description") or "").strip()
    if desc:
        print(f"\n  {c('About:', C.DIM, C.ITALIC)}")
        words = desc.split()
        line, lines = "", []
        for w in words:
            if len(line) + len(w) + 1 > 68:
                lines.append(line)
                line = w
            else:
                line = (line + " " + w).strip()
        if line:
            lines.append(line)
        for l in lines[:6]:
            print(f"  {c(l, C.DIM)}")
    print()


def cmd_alert(portfolio: Portfolio, symbol: str, target: float) -> None:
    portfolio.set_alert(symbol, target)
    save_portfolio(portfolio)
    print_success(
        f"Alert set: notify when {coin_label(symbol)} reaches "
        f"{c(f'${target:,.2f}', C.GOLD, C.BOLD)}"
    )


def cmd_list_coins() -> None:
    print(section_header("SUPPORTED COINS"))
    rows = []
    for sym, cid in sorted(COIN_ID_MAP.items()):
        emoji = COIN_EMOJI.get(sym, "◆")
        rows.append([
            c(f"{emoji} {sym}", C.GOLD, C.BOLD),
            c(cid, C.DIM),
        ])
    headers = [c("Symbol", C.BRIGHT_CYAN, C.BOLD), c("CoinGecko ID", C.BRIGHT_CYAN, C.BOLD)]
    print(tabulate(rows, headers=headers, tablefmt="rounded_outline"))
    print(f"\n  {c(f'{len(COIN_ID_MAP)} coins supported', C.DIM)}\n")

# ─── CLI ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crypto Portfolio Tracker v2.0 — powered by CoinGecko",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python crypto_portfolio.py add BTC 0.5
  python crypto_portfolio.py add ETH 2.0 --buy-price 3200
  python crypto_portfolio.py show
  python crypto_portfolio.py remove BTC
  python crypto_portfolio.py export
  python crypto_portfolio.py history --last 10
  python crypto_portfolio.py info SOL
  python crypto_portfolio.py alert BTC 100000
  python crypto_portfolio.py coins
        """,
    )
    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.required = True

    p_add = sub.add_parser("add", help="Add or update a coin in your portfolio")
    p_add.add_argument("symbol",   type=str,   help="Coin symbol (e.g. BTC, ETH)")
    p_add.add_argument("quantity", type=float, help="Amount to add")
    p_add.add_argument("--buy-price", type=float, default=0.0, metavar="PRICE",
                       help="Average buy price in USD (optional, for P&L tracking)")

    p_rm = sub.add_parser("remove", help="Remove a coin from your portfolio")
    p_rm.add_argument("symbol", type=str, help="Coin symbol to remove")

    sub.add_parser("show",   help="Show portfolio with live prices")
    sub.add_parser("export", help="Export portfolio to CSV")

    p_hist = sub.add_parser("history", help="Show portfolio value history")
    p_hist.add_argument("--last", type=int, default=20, metavar="N",
                        help="Number of recent snapshots to show (default: 20)")

    p_info = sub.add_parser("info", help="Show detailed info about a coin")
    p_info.add_argument("symbol", type=str, help="Coin symbol")

    p_alert = sub.add_parser("alert", help="Set a price alert for a coin")
    p_alert.add_argument("symbol", type=str,   help="Coin symbol")
    p_alert.add_argument("price",  type=float, help="Target price in USD")

    sub.add_parser("coins", help="List all supported coins")

    return parser


def main() -> None:
    parser    = build_parser()
    args      = parser.parse_args()
    portfolio = load_portfolio()

    print_banner()

    dispatch = {
        "add":     lambda: cmd_add(portfolio, args.symbol, args.quantity, args.buy_price),
        "remove":  lambda: cmd_remove(portfolio, args.symbol),
        "show":    lambda: cmd_show(portfolio),
        "export":  lambda: cmd_export(portfolio),
        "history": lambda: cmd_history(args.last),
        "info":    lambda: cmd_info(args.symbol),
        "alert":   lambda: cmd_alert(portfolio, args.symbol, args.price),
        "coins":   cmd_list_coins,
    }

    action = dispatch.get(args.command)
    if action:
        action()


if __name__ == "__main__":
    main()
