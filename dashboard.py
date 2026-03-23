# ============================================================
#  dashboard.py — Live Terminal Dashboard
# ============================================================
import os
import time
from datetime import datetime
from colorama import Fore, Back, Style, init
from tabulate import tabulate

init(autoreset=True)

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def color_val(val, good_if_positive=True):
    if isinstance(val, (int, float)):
        if val > 0:
            c = Fore.GREEN if good_if_positive else Fore.RED
        elif val < 0:
            c = Fore.RED if good_if_positive else Fore.GREEN
        else:
            c = Fore.WHITE
        return f"{c}{val}{Style.RESET_ALL}"
    return str(val)


def render_dashboard(risk_mgr, signal: dict, df, price: float,
                     trade_logger, symbol: str):
    clear()
    now = datetime.utcnow().strftime("%Y-%m-%d  %H:%M:%S UTC")
    env = f"{Back.YELLOW}{Fore.BLACK} TESTNET {Style.RESET_ALL}" \
          if os.getenv("USE_TESTNET", "1") == "1" \
          else f"{Back.RED}{Fore.WHITE} ⚠ LIVE ⚠ {Style.RESET_ALL}"

    print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"  🤖  Binance Scalper Bot  {env}   {Fore.YELLOW}{now}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")

    # ── Price & Signal ────────────────────────────────────────
    combined = signal.get("combined", 0)
    sig_color = Fore.GREEN if combined > 0.1 else Fore.RED if combined < -0.1 else Fore.WHITE
    direction = "🟢 BUY " if combined > 0.1 else "🔴 SELL" if combined < -0.1 else "⚪ HOLD"

    print(f"  Symbol : {Fore.YELLOW}{symbol}{Style.RESET_ALL}   "
          f"Price : {Fore.WHITE}${price:,.4f}{Style.RESET_ALL}")
    print(f"  Signal : {sig_color}{combined:+.4f}{Style.RESET_ALL}  "
          f"Direction : {direction}")

    # ── Strategy Scores ───────────────────────────────────────
    scores = signal.get("scores", {})
    score_rows = [
        ["RSI + EMA",      f"{scores.get('rsi_ema', 0):+.4f}"],
        ["Bollinger",      f"{scores.get('bollinger', 0):+.4f}"],
        ["Order Book",     f"{scores.get('orderbook', 0):+.4f}"],
        ["ML Model",       f"{scores.get('ml_signal', 0):+.4f}"],
        ["── COMBINED ──", f"{combined:+.4f}"],
    ]
    print(f"\n{Fore.CYAN}  Strategy Scores{Style.RESET_ALL}")
    print(tabulate(score_rows, headers=["Strategy","Score"],
                   tablefmt="simple", colalign=("left","right")))

    # ── Indicators snapshot ───────────────────────────────────
    if df is not None and len(df):
        row = df.iloc[-1]
        adx = row.get('adx', 0)
        adx_color = Fore.GREEN if adx >= 25 else Fore.YELLOW if adx >= 20 else Fore.RED

        ind_rows = [
            ["RSI",       f"{row.get('rsi', 0):.1f}"],
            ["EMA Fast",  f"{row.get('ema_fast', 0):.2f}"],
            ["EMA Slow",  f"{row.get('ema_slow', 0):.2f}"],
            ["BB %",      f"{row.get('bb_pct', 0):.3f}"],
            ["ATR %",     f"{row.get('atr_pct', 0):.3f}"],
            ["ADX",       f"{adx_color}{adx:.1f}{Style.RESET_ALL}"],
            ["Stoch K",   f"{row.get('stoch_k', 0):.1f}"],
            ["Vol Ratio", f"{row.get('vol_ratio', 0):.2f}x"],
        ]
        print(f"\n{Fore.CYAN}  Indicators{Style.RESET_ALL}")
        print(tabulate(ind_rows, headers=["Indicator","Value"],
                       tablefmt="simple", colalign=("left","right")))

    # ── Account stats ─────────────────────────────────────────
    s = risk_mgr.summary()
    pnl_str = color_val(s["total_pnl"])
    day_str = color_val(s["daily_pnl"])
    print(f"\n{Fore.CYAN}  Account{Style.RESET_ALL}")
    acct_rows = [
        ["Capital",       f"${s['capital']:,.2f}"],
        ["Total PnL",     pnl_str],
        ["Day PnL",       day_str],
        ["Day Trades",    s["daily_trades"]],
        ["Open Pos.",     s["open"]],
        ["Win Rate",      f"{s['win_rate']:.1f}%"],
        ["W / L",         f"{s['wins']} / {s['losses']}"],
        ["Paused",        f"{Fore.RED}YES{Style.RESET_ALL}" if s["paused"] else "No"],
    ]
    print(tabulate(acct_rows, headers=["Metric","Value"],
                   tablefmt="simple", colalign=("left","right")))

    # ── Open positions ────────────────────────────────────────
    if risk_mgr.open_positions:
        print(f"\n{Fore.CYAN}  Open Positions{Style.RESET_ALL}")
        pos_rows = []
        for oid, pos in risk_mgr.open_positions.items():
            upnl = pos.unrealised_pnl(price)
            pos_rows.append([
                pos.side, pos.symbol, pos.entry_price,
                pos.stop_loss, pos.take_profit,
                f"{upnl:+.4f}"
            ])
        print(tabulate(pos_rows,
                       headers=["Side","Symbol","Entry","SL","TP","uPnL"],
                       tablefmt="simple"))

    # ── Performance summary ───────────────────────────────────
    perf = trade_logger.performance_summary()
    if perf:
        print(f"\n{Fore.CYAN}  Historical Performance{Style.RESET_ALL}")
        perf_rows = [[k, v] for k, v in perf.items()]
        print(tabulate(perf_rows, headers=["Metric","Value"],
                       tablefmt="simple"))

    print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"  Press Ctrl+C to stop bot\n")
