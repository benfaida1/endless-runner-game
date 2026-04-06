"""
Central configuration for the trading bot.
All live keys should be set via environment variables or a .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ── Exchange ──────────────────────────────────────────────────────────────────
EXCHANGE_ID       = os.getenv("EXCHANGE_ID", "binance")
API_KEY           = os.getenv("API_KEY", "")
API_SECRET        = os.getenv("API_SECRET", "")
TESTNET           = os.getenv("TESTNET", "true").lower() == "true"

# ── Trading universe ──────────────────────────────────────────────────────────
SYMBOLS = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "BNB/USDT",
    "XRP/USDT",
]
TIMEFRAME           = "1h"          # OHLCV timeframe
OHLCV_LIMIT         = 500           # candles to load per fetch

# ── Risk management ───────────────────────────────────────────────────────────
INITIAL_CAPITAL     = float(os.getenv("INITIAL_CAPITAL", 10_000))
MAX_POSITION_PCT    = 0.20          # max 20 % of portfolio per trade
MAX_OPEN_TRADES     = 5
STOP_LOSS_PCT       = 0.03          # 3 % stop-loss
TAKE_PROFIT_PCT     = 0.06          # 6 % take-profit  (2:1 RR)
TRAILING_STOP_PCT   = 0.015         # 1.5 % trailing stop
MAX_DRAWDOWN_PCT    = 0.15          # halt bot if drawdown > 15 %
RISK_PER_TRADE_PCT  = 0.01          # 1 % of capital risked per trade

# ── Strategy weights (multi-factor) ───────────────────────────────────────────
STRATEGY_WEIGHTS = {
    "MACrossover":  0.25,
    "RSIStrategy":  0.25,
    "MACDStrategy": 0.25,
    "BBStrategy":   0.25,
}

# ── Strategy parameters ───────────────────────────────────────────────────────
MA_FAST          = 9
MA_SLOW          = 21
MA_SIGNAL        = 50

RSI_PERIOD       = 14
RSI_OVERSOLD     = 30
RSI_OVERBOUGHT   = 70

MACD_FAST        = 12
MACD_SLOW        = 26
MACD_SIGNAL      = 9

BB_PERIOD        = 20
BB_STD           = 2.0

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR          = BASE_DIR / "trading_bot" / "logs"
LOG_FILE         = LOG_DIR / "bot.log"

# ── Backtesting ───────────────────────────────────────────────────────────────
BACKTEST_START   = "2023-01-01"
BACKTEST_END     = "2024-12-31"

# ── Notifications (optional) ──────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
