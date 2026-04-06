#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║          CRYPTO TRADING BOT  —  Multi-Factor Edition         ║
║  Strategies: MA Crossover · RSI · MACD · Bollinger Bands    ║
║  Features  : Backtesting · Risk Mgmt · Paper Trading        ║
╚══════════════════════════════════════════════════════════════╝

Usage
─────
  python main.py backtest          # Run historical simulation
  python main.py paper             # Paper trading (live data, fake money)
  python main.py live              # Live trading (requires API keys in .env)
  python main.py demo              # Quick demo: single signal for each symbol
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# ── Logging setup ─────────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).parent / "trading_bot" / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")


# ── Imports after logging setup ───────────────────────────────────────────────
from trading_bot.config import settings
from trading_bot.data.fetcher import DataFetcher
from trading_bot.strategies.multi_factor import MultiFactor
from trading_bot.strategies.ma_crossover import MACrossover
from trading_bot.strategies.rsi_strategy import RSIStrategy
from trading_bot.strategies.macd_strategy import MACDStrategy
from trading_bot.strategies.bb_strategy import BBStrategy
from trading_bot.core.engine import TradingEngine
from trading_bot.core.portfolio import Portfolio
from trading_bot.core.risk_manager import RiskManager
from trading_bot.backtester.engine import Backtester
from trading_bot.ui.dashboard import (
    render_dashboard, print_backtest_summary, console
)


# ─────────────────────────────────────────────────────────────────────────────
# DEMO MODE
# ─────────────────────────────────────────────────────────────────────────────

def run_demo() -> None:
    console.rule("[bold blue]DEMO MODE — Single Signal per Symbol[/bold blue]")
    fetcher  = DataFetcher()
    strategy = MultiFactor()

    from rich.table import Table
    from rich import box as rbox

    tbl = Table(title="Signal Snapshot", box=rbox.ROUNDED,
                header_style="bold cyan", show_lines=True)
    tbl.add_column("Symbol",   style="bold white", no_wrap=True)
    tbl.add_column("Signal",   justify="center")
    tbl.add_column("Strength", justify="right")
    tbl.add_column("Price",    justify="right")
    tbl.add_column("Reason",   overflow="fold")

    action_map = {1: "[bold green] BUY [/bold green]",
                  -1: "[bold red] SELL [/bold red]",
                   0: "[dim] HOLD [/dim]"}

    for sym in settings.SYMBOLS:
        df  = fetcher.fetch_ohlcv(sym, settings.TIMEFRAME, 200)
        sig = strategy.generate_signal(df, sym)
        tbl.add_row(
            sym,
            action_map.get(sig.action, "?"),
            f"{sig.strength:.2f}",
            f"${float(df['close'].iloc[-1]):,.4f}",
            sig.reason[:80],
        )

    console.print(tbl)
    console.print("\n[dim]Run with 'backtest' or 'paper' for full simulation.[/dim]")


# ─────────────────────────────────────────────────────────────────────────────
# BACKTEST MODE
# ─────────────────────────────────────────────────────────────────────────────

def run_backtest(symbols: list[str] = None, n_candles: int = 500) -> None:
    console.rule("[bold blue]BACKTEST MODE[/bold blue]")
    symbols  = symbols or settings.SYMBOLS
    fetcher  = DataFetcher()

    console.print(f"[cyan]Loading {n_candles} candles for {len(symbols)} symbols…[/cyan]")
    data = {}
    for sym in symbols:
        df = fetcher.fetch_ohlcv(sym, settings.TIMEFRAME, n_candles)
        data[sym] = df
        console.print(f"  [green]✓[/green] {sym}: {len(df)} candles "
                      f"({df.index[0].strftime('%Y-%m-%d')} → "
                      f"{df.index[-1].strftime('%Y-%m-%d')})")

    backtester = Backtester(
        strategy         = MultiFactor(),
        capital          = settings.INITIAL_CAPITAL,
        stop_loss_pct    = settings.STOP_LOSS_PCT,
        take_profit_pct  = settings.TAKE_PROFIT_PCT,
        trailing_stop_pct= settings.TRAILING_STOP_PCT,
        max_open_trades  = settings.MAX_OPEN_TRADES,
        commission_pct   = 0.001,
    )

    console.print("\n[cyan]Running simulation…[/cyan]")
    result = backtester.run(data, warmup=50)

    print_backtest_summary(result)

    if result.trades:
        from rich.table import Table
        from rich import box as rbox
        tbl = Table(title="[bold]Trade Log (all trades)[/bold]",
                    box=rbox.SIMPLE_HEAVY, header_style="bold cyan")
        tbl.add_column("#",       justify="right", style="dim")
        tbl.add_column("Symbol",  style="bold white")
        tbl.add_column("PnL",     justify="right")
        tbl.add_column("Return",  justify="right")
        tbl.add_column("Reason",  overflow="fold")

        for i, t in enumerate(result.trades, 1):
            color = "green" if t.pnl >= 0 else "red"
            tbl.add_row(
                str(i),
                t.symbol,
                f"[{color}]{'+' if t.pnl>=0 else ''}{t.pnl:,.2f}[/{color}]",
                f"[{color}]{'+' if t.pnl_pct>=0 else ''}{t.pnl_pct*100:.1f}%[/{color}]",
                t.reason[:60],
            )
        console.print(tbl)


# ─────────────────────────────────────────────────────────────────────────────
# PAPER / LIVE TRADING MODE
# ─────────────────────────────────────────────────────────────────────────────

def run_trading(paper: bool = True, interval: int = 60,
                max_ticks: int = 0) -> None:
    mode = "PAPER" if paper else "LIVE"
    console.rule(f"[bold {'blue' if paper else 'red'}]{mode} TRADING MODE[/bold {'blue' if paper else 'red'}]")

    if not paper:
        console.print("[bold red]⚠  LIVE MODE: real money at risk![/bold red]")
        if not settings.API_KEY or not settings.API_SECRET:
            console.print("[red]ERROR: API_KEY / API_SECRET not set in .env — aborting.[/red]")
            sys.exit(1)

    engine = TradingEngine(
        symbols   = settings.SYMBOLS,
        timeframe = settings.TIMEFRAME,
        paper     = paper,
        capital   = settings.INITIAL_CAPITAL,
    )

    signals: dict = {}
    tick = 0

    while True:
        try:
            prices = {}
            for sym in engine.symbols:
                df  = engine.fetcher.fetch_ohlcv(sym, engine.timeframe, 200)
                sig = engine.strategy.generate_signal(df, sym)
                signals[sym] = sig
                prices[sym]  = float(df["close"].iloc[-1])

            engine._tick()
            tick = engine.tick_count

            state = engine.current_state(prices)
            render_dashboard(
                portfolio = engine.portfolio,
                prices    = prices,
                signals   = signals,
                initial   = settings.INITIAL_CAPITAL,
                tick      = tick,
                drawdown  = state["drawdown"],
            )

            if not engine._running:
                console.print("[red]Engine stopped — max drawdown reached.[/red]")
                break

            if max_ticks and tick >= max_ticks:
                break

            if interval > 0:
                console.print(f"\n[dim]Next tick in {interval}s… (Ctrl+C to stop)[/dim]")
                time.sleep(interval)

        except KeyboardInterrupt:
            console.print("\n[yellow]Stopped by user.[/yellow]")
            break

    # Final stats
    if engine.portfolio.trade_log:
        console.rule("[bold]Final Statistics[/bold]")
        stats = engine.portfolio.stats()
        for k, v in stats.items():
            if isinstance(v, float):
                console.print(f"  [cyan]{k}:[/cyan] {v:.4f}")
            else:
                console.print(f"  [cyan]{k}:[/cyan] {v}")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-Factor Crypto Trading Bot",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "mode",
        nargs="?",
        default="demo",
        choices=["demo", "backtest", "paper", "live"],
        help=(
            "demo     — show one signal per symbol (default)\n"
            "backtest — historical simulation with performance report\n"
            "paper    — live data, simulated orders (no real money)\n"
            "live     — real trading (requires API keys in .env)"
        ),
    )
    parser.add_argument("--symbols",  nargs="+", default=None,
                        help="Override symbol list, e.g. BTC/USDT ETH/USDT")
    parser.add_argument("--candles",  type=int, default=500,
                        help="Number of candles to load (backtest mode)")
    parser.add_argument("--interval", type=int, default=60,
                        help="Seconds between ticks in paper/live mode")
    parser.add_argument("--max-ticks", type=int, default=0,
                        help="Stop after N ticks (0 = run forever)")

    args = parser.parse_args()

    if args.mode == "demo":
        run_demo()
    elif args.mode == "backtest":
        run_backtest(args.symbols, args.candles)
    elif args.mode == "paper":
        run_trading(paper=True,  interval=args.interval, max_ticks=args.max_ticks)
    elif args.mode == "live":
        run_trading(paper=False, interval=args.interval, max_ticks=args.max_ticks)


if __name__ == "__main__":
    main()
