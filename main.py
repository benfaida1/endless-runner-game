#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║        CRYPTO TRADING BOT  —  Multi-Factor Edition v2           ║
║  Strategies: MA Crossover · RSI · MACD · Bollinger · VWAP      ║
║  Features  : Backtesting · Optimizer · Risk Mgmt · Telegram    ║
╚══════════════════════════════════════════════════════════════════╝

Usage
─────
  python main.py demo              # Quick signal snapshot
  python main.py backtest          # Historical simulation + equity chart
  python main.py optimize          # Grid-search best parameters
  python main.py paper             # Paper trading (live data, fake money)
  python main.py live              # Live trading (requires API keys in .env)
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
from trading_bot.strategies.vwap_strategy import VWAPStrategy
from trading_bot.core.engine import TradingEngine
from trading_bot.core.portfolio import Portfolio
from trading_bot.core.risk_manager import RiskManager
from trading_bot.backtester.engine import Backtester
from trading_bot.optimizer.grid_search import GridSearchOptimizer, FAST_GRID
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

    # ── Monte Carlo risk analysis ──────────────────────────────────────────────
    if result.trades and len(result.trades) >= 3:
        from trading_bot.backtester.monte_carlo import MonteCarloSimulator
        console.print("\n[cyan]Running Monte Carlo simulation (5,000 paths)…[/cyan]")
        pnls = [t.pnl for t in result.trades]
        mc   = MonteCarloSimulator(pnls, settings.INITIAL_CAPITAL, annual_trades=len(pnls))
        report = mc.run(n_simulations=5_000)

        from rich.table import Table
        from rich import box as rbox
        mc_tbl = Table(title="[bold magenta]Monte Carlo Risk Analysis[/bold magenta]",
                       box=rbox.ROUNDED, show_header=False, padding=(0, 2))
        mc_tbl.add_column("Metric", style="magenta bold")
        mc_tbl.add_column("Value",  justify="right")

        ic = settings.INITIAL_CAPITAL
        def eq_color(v): return "green" if v >= ic else "red"

        mc_tbl.add_row("5th pct equity  (worst case)",
                       f"[{eq_color(report.final_equity_p5)}]${report.final_equity_p5:,.2f}[/]")
        mc_tbl.add_row("Median equity",
                       f"[{eq_color(report.final_equity_p50)}]${report.final_equity_p50:,.2f}[/]")
        mc_tbl.add_row("95th pct equity (best case)",
                       f"[green]${report.final_equity_p95:,.2f}[/green]")
        mc_tbl.add_row("Median max drawdown",
                       f"[yellow]{report.max_dd_p50*100:.1f}%[/yellow]")
        mc_tbl.add_row("95th pct max drawdown",
                       f"[red]{report.max_dd_p95*100:.1f}%[/red]")
        mc_tbl.add_row("Median CAGR",
                       f"[{'green' if report.cagr_p50>=0 else 'red'}]"
                       f"{'+' if report.cagr_p50>=0 else ''}{report.cagr_p50*100:.1f}%[/]")
        mc_tbl.add_row("P(lose money)",
                       f"[{'red' if report.prob_loss>0.3 else 'yellow'}]"
                       f"{report.prob_loss*100:.1f}%[/]")
        mc_tbl.add_row("P(drawdown > 30%)",
                       f"[{'red' if report.prob_ruin>0.1 else 'green'}]"
                       f"{report.prob_ruin*100:.1f}%[/]")
        console.print(mc_tbl)

    # ── Trade log ─────────────────────────────────────────────────────────────
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
# OPTIMIZER MODE
# ─────────────────────────────────────────────────────────────────────────────

def run_optimize(symbols: list[str] = None, n_candles: int = 500,
                 metric: str = "sharpe") -> None:
    console.rule("[bold magenta]OPTIMIZER — Grid Search[/bold magenta]")
    symbols = symbols or settings.SYMBOLS[:3]   # keep fast by default
    fetcher = DataFetcher()

    console.print(f"[cyan]Loading data for {symbols}…[/cyan]")
    data = {sym: fetcher.fetch_ohlcv(sym, settings.TIMEFRAME, n_candles)
            for sym in symbols}

    optimizer = GridSearchOptimizer(
        data    = data,
        grid    = FAST_GRID,
        metric  = metric,
        capital = settings.INITIAL_CAPITAL,
        top_n   = 5,
    )

    console.print(f"[cyan]Running grid search (metric={metric})… this may take a minute.[/cyan]\n")
    results = optimizer.run()

    from rich.table import Table
    from rich import box as rbox

    tbl = Table(title=f"[bold]Top Results (sorted by {metric})[/bold]",
                box=rbox.ROUNDED, header_style="bold magenta")
    tbl.add_column("Rank", justify="right", style="dim")
    tbl.add_column(metric.capitalize(), justify="right")
    tbl.add_column("Equity",     justify="right")
    tbl.add_column("Trades",     justify="right")
    tbl.add_column("Win Rate",   justify="right")
    tbl.add_column("Max DD",     justify="right")
    tbl.add_column("Key Params", overflow="fold")

    for rank, r in enumerate(results, 1):
        ret_color = "green" if r.equity >= settings.INITIAL_CAPITAL else "red"
        key_params = (
            f"ma={r.params.get('ma_fast')}/{r.params.get('ma_slow')} "
            f"rsi={r.params.get('rsi_period')} "
            f"sl={r.params.get('stop_loss_pct',0)*100:.0f}% "
            f"tp={r.params.get('take_profit_pct',0)*100:.0f}%"
        )
        tbl.add_row(
            str(rank),
            f"{r.metric:.4f}",
            f"[{ret_color}]${r.equity:,.2f}[/{ret_color}]",
            str(r.stats.get("total_trades", 0)),
            f"{r.stats.get('win_rate', 0)*100:.1f}%",
            f"[red]{r.stats.get('max_drawdown', 0)*100:.1f}%[/red]",
            key_params,
        )

    console.print(tbl)

    if results:
        best = results[0]
        console.print("\n[bold green]Best parameter set:[/bold green]")
        for k, v in best.params.items():
            console.print(f"  [cyan]{k}[/cyan] = {v}")

        console.print(
            "\n[dim]To use these params, update config/settings.py or pass them "
            "directly when instantiating strategies.[/dim]"
        )


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
                regimes   = engine.regimes,
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
        choices=["demo", "backtest", "optimize", "paper", "live"],
        help=(
            "demo     — show one signal per symbol (default)\n"
            "backtest — historical simulation with equity chart\n"
            "optimize — grid-search best strategy parameters\n"
            "paper    — live data, simulated orders (no real money)\n"
            "live     — real trading (requires API keys in .env)"
        ),
    )
    parser.add_argument("--symbols",  nargs="+", default=None,
                        help="Override symbol list, e.g. BTC/USDT ETH/USDT")
    parser.add_argument("--candles",  type=int, default=500,
                        help="Number of candles to load (backtest/optimize)")
    parser.add_argument("--interval", type=int, default=60,
                        help="Seconds between ticks in paper/live mode")
    parser.add_argument("--max-ticks", type=int, default=0,
                        help="Stop after N ticks (0 = run forever)")
    parser.add_argument("--metric",   default="sharpe",
                        choices=["sharpe", "return", "profit_factor", "win_rate"],
                        help="Optimisation objective (default: sharpe)")

    args = parser.parse_args()

    if args.mode == "demo":
        run_demo()
    elif args.mode == "backtest":
        run_backtest(args.symbols, args.candles)
    elif args.mode == "optimize":
        run_optimize(args.symbols, args.candles, args.metric)
    elif args.mode == "paper":
        run_trading(paper=True,  interval=args.interval, max_ticks=args.max_ticks)
    elif args.mode == "live":
        run_trading(paper=False, interval=args.interval, max_ticks=args.max_ticks)


if __name__ == "__main__":
    main()
