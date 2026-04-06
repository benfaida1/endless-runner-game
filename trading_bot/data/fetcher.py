"""
Market data fetcher — supports live exchange data (via ccxt) and CSV import
for backtesting without any internet dependency.
"""

from __future__ import annotations

import time
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


# ── Demo OHLCV generator (no exchange needed for backtesting) ─────────────────

def _generate_demo_ohlcv(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 500,
    seed: Optional[int] = None,
) -> pd.DataFrame:
    """Synthesise realistic OHLCV data using geometric Brownian motion."""
    rng = np.random.default_rng(seed or hash(symbol) % (2**32))

    base_prices = {
        "BTC/USDT": 45_000.0,
        "ETH/USDT": 2_500.0,
        "SOL/USDT": 120.0,
        "BNB/USDT": 400.0,
        "XRP/USDT": 0.65,
    }
    price = base_prices.get(symbol, 100.0)

    # Drift + volatility (annualised ~80 % vol for crypto)
    dt     = 1 / (365 * 24) if timeframe == "1h" else 1 / 365
    mu     = 0.5            # annual drift
    sigma  = 0.80           # annual volatility
    n      = limit

    returns = rng.normal(
        (mu - 0.5 * sigma**2) * dt,
        sigma * np.sqrt(dt),
        size=n,
    )
    prices = price * np.exp(np.cumsum(returns))

    # Build OHLCV from close prices
    noise  = rng.uniform(0.998, 1.002, size=n)
    opens  = np.roll(prices, 1); opens[0] = price
    highs  = np.maximum(opens, prices) * (1 + rng.uniform(0, 0.005, size=n))
    lows   = np.minimum(opens, prices) * (1 - rng.uniform(0, 0.005, size=n))
    volumes = rng.uniform(1_000, 50_000, size=n) * (price / 1_000)

    freq_map = {"1m": "min", "5m": "5min", "15m": "15min",
                "1h": "h", "4h": "4h", "1d": "D"}
    freq = freq_map.get(timeframe, "h")
    # Use a fixed reference time (floored to hour) so all symbols share the same index
    ref_end = pd.Timestamp.now(tz=timezone.utc).floor("h")
    index = pd.date_range(end=ref_end, periods=n, freq=freq)

    return pd.DataFrame({
        "open":   opens,
        "high":   highs,
        "low":    lows,
        "close":  prices,
        "volume": volumes,
    }, index=index)


# ── Live fetcher ──────────────────────────────────────────────────────────────

class DataFetcher:
    """
    Fetches OHLCV data.
    - If ccxt is available and API keys are set → live data.
    - Otherwise → synthetic demo data (safe for paper trading / backtesting).
    """

    def __init__(self, exchange_id: str = "binance",
                 api_key: str = "", api_secret: str = "",
                 testnet: bool = True):
        self.exchange_id = exchange_id
        self.api_key     = api_key
        self.api_secret  = api_secret
        self.testnet     = testnet
        self._exchange   = None
        self._live       = False

        if api_key and api_secret:
            self._init_exchange()

    # ── Init ──────────────────────────────────────────────────────────────────

    def _init_exchange(self) -> None:
        try:
            import ccxt
            cls = getattr(ccxt, self.exchange_id)
            self._exchange = cls({
                "apiKey":    self.api_key,
                "secret":    self.api_secret,
                "enableRateLimit": True,
                "options":   {"defaultType": "spot"},
            })
            if self.testnet:
                self._exchange.set_sandbox_mode(True)
            self._exchange.load_markets()
            self._live = True
            logger.info("Exchange connected: %s (testnet=%s)",
                        self.exchange_id, self.testnet)
        except Exception as exc:
            logger.warning("Exchange init failed (%s) — using demo data.", exc)

    # ── Public API ────────────────────────────────────────────────────────────

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h",
                    limit: int = 500) -> pd.DataFrame:
        if self._live:
            return self._fetch_live(symbol, timeframe, limit)
        return _generate_demo_ohlcv(symbol, timeframe, limit)

    def fetch_ticker(self, symbol: str) -> dict:
        if self._live:
            try:
                return self._exchange.fetch_ticker(symbol)
            except Exception as exc:
                logger.warning("fetch_ticker failed: %s", exc)
        # Demo ticker
        df = _generate_demo_ohlcv(symbol, "1h", 2)
        return {"last": float(df["close"].iloc[-1]),
                "bid":  float(df["close"].iloc[-1] * 0.999),
                "ask":  float(df["close"].iloc[-1] * 1.001)}

    def fetch_balance(self) -> dict:
        if self._live:
            try:
                return self._exchange.fetch_balance()
            except Exception as exc:
                logger.warning("fetch_balance failed: %s", exc)
        return {"USDT": {"free": 10_000.0, "used": 0.0, "total": 10_000.0}}

    # ── Internal ──────────────────────────────────────────────────────────────

    def _fetch_live(self, symbol: str, timeframe: str,
                    limit: int) -> pd.DataFrame:
        retries = 3
        for attempt in range(retries):
            try:
                raw = self._exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                df  = pd.DataFrame(raw, columns=[
                    "timestamp", "open", "high", "low", "close", "volume"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms",
                                                 utc=True)
                df.set_index("timestamp", inplace=True)
                return df
            except Exception as exc:
                wait = 2 ** attempt
                logger.warning("OHLCV fetch attempt %d failed: %s — retry in %ds",
                               attempt + 1, exc, wait)
                time.sleep(wait)
        logger.error("All OHLCV fetch attempts failed; falling back to demo data.")
        return _generate_demo_ohlcv(symbol, timeframe, limit)
