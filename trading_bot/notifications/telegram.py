"""
Telegram Notifier
─────────────────
Sends real-time trade alerts and daily summaries to a Telegram chat.

Setup:
  1. Create a bot via @BotFather → get TELEGRAM_TOKEN
  2. Send a message to the bot, then get your TELEGRAM_CHAT_ID
  3. Set both in your .env file
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Optional

import requests

from trading_bot.config import settings
from trading_bot.core.portfolio import Trade
from trading_bot.strategies.base import Signal

logger = logging.getLogger(__name__)

_EMOJI = {
    "buy":     "🟢",
    "sell":    "🔴",
    "hold":    "⚪",
    "profit":  "✅",
    "loss":    "❌",
    "alert":   "⚠️",
    "rocket":  "🚀",
    "chart":   "📊",
    "money":   "💰",
    "halt":    "🛑",
}


class TelegramNotifier:

    API_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(
        self,
        token:   str = settings.TELEGRAM_TOKEN,
        chat_id: str = settings.TELEGRAM_CHAT_ID,
    ):
        self.token   = token
        self.chat_id = chat_id
        self._enabled = bool(token and chat_id)
        if not self._enabled:
            logger.info("Telegram notifications disabled (no token/chat_id).")

    # ── Public API ────────────────────────────────────────────────────────────

    def send(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message. Fire-and-forget (non-blocking)."""
        if not self._enabled:
            return False
        threading.Thread(
            target=self._post, args=(text, parse_mode), daemon=True
        ).start()
        return True

    def trade_opened(self, symbol: str, side: str, qty: float,
                     price: float, sl: float, tp: float, reason: str) -> None:
        emoji = _EMOJI["buy"] if side == "buy" else _EMOJI["sell"]
        msg = (
            f"{emoji} <b>POSITION OPENED</b>\n"
            f"<code>Symbol  : {symbol}</code>\n"
            f"<code>Side    : {side.upper()}</code>\n"
            f"<code>Qty     : {qty:.6f}</code>\n"
            f"<code>Price   : ${price:,.4f}</code>\n"
            f"<code>Stop    : ${sl:,.4f}</code>\n"
            f"<code>Target  : ${tp:,.4f}</code>\n"
            f"<i>{reason[:120]}</i>"
        )
        self.send(msg)

    def trade_closed(self, trade: Trade) -> None:
        emoji = _EMOJI["profit"] if trade.is_win else _EMOJI["loss"]
        sign  = "+" if trade.pnl >= 0 else ""
        msg = (
            f"{emoji} <b>POSITION CLOSED</b>\n"
            f"<code>Symbol  : {trade.symbol}</code>\n"
            f"<code>PnL     : {sign}{trade.pnl:,.2f} USDT</code>\n"
            f"<code>Return  : {sign}{trade.pnl_pct*100:.2f}%</code>\n"
            f"<code>Entry   : ${trade.entry_price:,.4f}</code>\n"
            f"<code>Exit    : ${trade.exit_price:,.4f}</code>\n"
            f"<i>{trade.reason[:120]}</i>"
        )
        self.send(msg)

    def signal_alert(self, signal: Signal) -> None:
        if signal.is_hold:
            return
        emoji = _EMOJI["buy"] if signal.is_buy else _EMOJI["sell"]
        label = "BUY" if signal.is_buy else "SELL"
        msg = (
            f"{emoji} <b>SIGNAL: {label}</b>\n"
            f"<code>Symbol   : {signal.symbol}</code>\n"
            f"<code>Strength : {signal.strength:.2f}</code>\n"
            f"<code>Price    : ${signal.price:,.4f}</code>\n"
            f"<i>{signal.reason[:200]}</i>"
        )
        self.send(msg)

    def daily_summary(self, equity: float, initial: float,
                      stats: dict) -> None:
        ret    = (equity / initial - 1) * 100
        emoji  = _EMOJI["rocket"] if ret >= 0 else _EMOJI["alert"]
        win_r  = stats.get("win_rate", 0) * 100
        trades = stats.get("total_trades", 0)
        pf     = stats.get("profit_factor", 0)
        dd     = stats.get("max_drawdown", 0) * 100
        ts     = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        msg = (
            f"{emoji} <b>DAILY SUMMARY</b> — {ts}\n\n"
            f"{_EMOJI['money']} <b>Equity    : ${equity:>12,.2f}</b>\n"
            f"<code>Return    : {'+' if ret>=0 else ''}{ret:.2f}%</code>\n"
            f"<code>Trades    : {trades}</code>\n"
            f"<code>Win rate  : {win_r:.1f}%</code>\n"
            f"<code>Prof.fac  : {pf:.2f}</code>\n"
            f"<code>Drawdown  : {dd:.1f}%</code>"
        )
        self.send(msg)

    def halt_alert(self, reason: str, equity: float) -> None:
        msg = (
            f"{_EMOJI['halt']} <b>BOT HALTED</b>\n"
            f"<code>Reason  : {reason}</code>\n"
            f"<code>Equity  : ${equity:,.2f}</code>"
        )
        self.send(msg)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _post(self, text: str, parse_mode: str) -> None:
        url  = self.API_URL.format(token=self.token)
        data = {"chat_id": self.chat_id, "text": text,
                "parse_mode": parse_mode, "disable_web_page_preview": True}
        try:
            resp = requests.post(url, json=data, timeout=10)
            if not resp.ok:
                logger.warning("Telegram API error %d: %s",
                               resp.status_code, resp.text[:200])
        except Exception as exc:
            logger.warning("Telegram send failed: %s", exc)
