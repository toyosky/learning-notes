#!/usr/bin/env python3
"""
止损 + 止盈保护研究 — 基于风险平价 + 每月再平衡。
对比 5% 止损、5% 止损 + 10%/20% 止盈、纯止盈的效果。
"""

import backtrader as bt
import pandas as pd
import numpy as np
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../01-data/code"))
from data_fetcher import fetch_etf_data

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "../../assets")

# ── 常量 ──
SYMBOLS = {"510300": "沪深300", "513100": "纳指100", "518880": "黄金"}
INITIAL_CASH = 100_000.0
MOM_PERIOD = 20
COMMISSION_RATE = 0.001
MIN_COMMISSION = 5.0

CONFIGS = [
    ("buy_hold",       None,  None,  False,  "买入持有"),
    ("none",           None,  None,  False,  "无止损失"),
    ("sl_5",           0.05,  None,  False,  "5% 止损"),
    ("sl_5_immediate", 0.05,  None,  True,   "5%止+即时重配"),
    ("sl_5_tp_10",     0.05,  0.10,  False,  "止5%+盈10%"),
    ("sl_5_tp_20",     0.05,  0.20,  False,  "止5%+盈20%"),
    ("tp_10",          None,  0.10,  False,  "10%止盈"),
    ("tp_20",          None,  0.20,  False,  "20%止盈"),
]
CFG_COLORS = {
    "buy_hold": "#333333", "none": "#2196F3", "sl_5": "#e67e22",
    "sl_5_immediate": "#f39c12",
    "sl_5_tp_10": "#2ecc71", "sl_5_tp_20": "#27ae60",
    "tp_10": "#9b59b6", "tp_20": "#8e44ad",
}
CFG_LINESTYLES = {
    "buy_hold": "-", "none": "-", "sl_5": "--",
    "sl_5_immediate": ":",
    "sl_5_tp_10": "-.", "sl_5_tp_20": ":",
    "tp_10": "--", "tp_20": "-.",
}


# ══════════════════════════════════════════════════════════════════
# 1. 数据准备
# ══════════════════════════════════════════════════════════════════

def build_panel(start_date="20210101", end_date="20260101", mom_period=20) -> dict[str, pd.DataFrame]:
    data = {}
    for symbol in ("510300", "513100", "518880"):
        df = fetch_etf_data(symbol=symbol, start_date=start_date, end_date=end_date)
        df["log_return"] = np.log(df["Close"] / df["Close"].shift(1))
        df["mom"] = df["log_return"].rolling(mom_period).mean()
        df["vol"] = df["log_return"].rolling(mom_period).std(ddof=1)
        df["ram"] = df["mom"] / df["vol"]
        data[symbol] = df
    return data


# ══════════════════════════════════════════════════════════════════
# 2. 数据馈送
# ══════════════════════════════════════════════════════════════════

class ETFData(bt.feeds.PandasData):
    lines = ("mom", "vol", "ram")
    params = (
        ("datetime", None),
        ("open", "Open"), ("high", "High"), ("low", "Low"),
        ("close", "Close"), ("volume", "Volume"),
        ("mom", "mom"), ("vol", "vol"), ("ram", "ram"),
    )


# ══════════════════════════════════════════════════════════════════
# 3. 策略 — 风险平价 + 可配置止损/止盈（每月再平衡）
# ══════════════════════════════════════════════════════════════════

class RiskParityWithStopLoss(bt.Strategy):
    """风险平价 + 单 ETF 止损 + 止盈。"""
    params = (
        ("rebalance_freq", "monthly"),
        ("drawdown_stop", None),
        ("take_profit", None),
        ("rebalance_on_stop", False),
    )

    def __init__(self):
        self.history = []   # [(date, value, {sym: w}, {"stopped":[], "taken":[]})]
        self._bars_since_rebalance = 0
        self._last_month = None
        self._sold_etfs: dict[str, str] = {}   # {sym: "stop"|"take"}
        self._avg_costs: dict[str, float] = {}

    def _compute_weights(self) -> dict:
        vols = {}
        for d in self.datas:
            vols[d._name] = d.vol[0]
        clean = {k: v for k, v in vols.items()
                 if v is not None and v > 0 and not np.isnan(v)}
        if not clean:
            n = len(SYMBOLS)
            return {name: 1.0 / n for name in SYMBOLS}
        inv = {k: 1.0 / v for k, v in clean.items()}
        total = sum(inv.values())
        return {k: inv[k] / total for k in inv}

    def _is_rebalance_day(self) -> bool:
        freq = self.params.rebalance_freq
        if freq == "monthly":
            dt = self.datas[0].datetime.date(0)
            should = (self._last_month is None or dt.month != self._last_month)
            self._last_month = dt.month
            return should
        return self._bars_since_rebalance == 0

    def next(self):
        current_value = self.broker.getvalue()
        weights = self._compute_weights()
        is_rebalance = self._is_rebalance_day()
        events = {"stopped": [], "taken": []}
        stop_th = self.params.drawdown_stop
        take_th = self.params.take_profit

        # ── 单 ETF 止损 + 止盈检查（每根 bar） ──
        for d in self.datas:
            pos = self.getposition(d)
            if pos.size > 0:
                current_price = d.close[0]
                if d._name not in self._avg_costs:
                    self._avg_costs[d._name] = pos.price
                avg_cost = self._avg_costs[d._name]
                if avg_cost > 0:
                    # 止损：从 avg_cost 跌了 X%
                    if stop_th is not None:
                        drop = (avg_cost - current_price) / avg_cost
                        if drop >= stop_th:
                            self.order_target_percent(d, 0.0)
                            self._sold_etfs[d._name] = "stop"
                            events["stopped"].append(d._name)
                            continue
                    # 止盈：从 avg_cost 涨了 X%（仅当同一 ETF 未触发止损时）
                    if take_th is not None:
                        rise = (current_price - avg_cost) / avg_cost
                        if rise >= take_th:
                            self.order_target_percent(d, 0.0)
                            self._sold_etfs[d._name] = "take"
                            events["taken"].append(d._name)

        # ── 止损后即时重配：将现金重新分配到剩余 ETF ──
        if self.params.rebalance_on_stop and (events["stopped"] or events["taken"]):
            remaining = [d for d in self.datas if d._name not in self._sold_etfs]
            if remaining:
                vols = {}
                for d in remaining:
                    vols[d._name] = d.vol[0]
                clean = {k: v for k, v in vols.items()
                         if v is not None and v > 0 and not np.isnan(v)}
                if clean:
                    inv = {k: 1.0 / v for k, v in clean.items()}
                    total = sum(inv.values())
                    for d in remaining:
                        self.order_target_percent(d, inv[d._name] / total)

        # ── 再平衡日 ──
        if is_rebalance:
            self._sold_etfs.clear()
            for d in self.datas:
                self.order_target_percent(d, weights.get(d._name, 0.0))

        # 仓位存在但 avg_cost=0 → 从 pos.price 获取
        for d in self.datas:
            pos = self.getposition(d)
            if pos.size > 0 and self._avg_costs.get(d._name, 0.0) == 0.0:
                self._avg_costs[d._name] = pos.price

        # ── 记录历史 ──
        self.history.append((
            self.datas[0].datetime.date(0).isoformat(),
            current_value, dict(weights), events,
        ))

        self._bars_since_rebalance += 1
        if isinstance(self.params.rebalance_freq, int) and \
           self._bars_since_rebalance >= self.params.rebalance_freq:
            self._bars_since_rebalance = 0


# ══════════════════════════════════════════════════════════════════
# 4. 买入持有策略（基准）
# ══════════════════════════════════════════════════════════════════

class BuyAndHold(bt.Strategy):
    """首日按风险平价权重买入，永不调仓。"""
    def __init__(self):
        self.history = []
        self._bought = False

    def _compute_weights(self) -> dict:
        vols = {}
        for d in self.datas:
            vols[d._name] = d.vol[0]
        clean = {k: v for k, v in vols.items()
                 if v is not None and v > 0 and not np.isnan(v)}
        if not clean:
            n = len(SYMBOLS)
            return {name: 1.0 / n for name in SYMBOLS}
        inv = {k: 1.0 / v for k, v in clean.items()}
        total = sum(inv.values())
        return {k: inv[k] / total for k in inv}

    def next(self):
        if not self._bought:
            weights = self._compute_weights()
            for d in self.datas:
                self.order_target_percent(d, weights.get(d._name, 0.0))
            self._bought = True
        self.history.append((
            self.datas[0].datetime.date(0).isoformat(),
            self.broker.getvalue(), {}, {"stopped": [], "taken": []},
        ))


# ══════════════════════════════════════════════════════════════════
# 5. 回测运行器
# ══════════════════════════════════════════════════════════════════

def run_one(key: str, sl_threshold: float | None, tp_threshold: float | None,
            rebalance_on_stop: bool,
            data_panel: dict[str, pd.DataFrame]) -> dict:
    cerebro = bt.Cerebro()
    for symbol, df in data_panel.items():
        feed = ETFData(dataname=df)
        feed._name = symbol
        cerebro.adddata(feed)

    if key == "buy_hold":
        cerebro.addstrategy(BuyAndHold)
    else:
        cerebro.addstrategy(
            RiskParityWithStopLoss,
            rebalance_freq="monthly",
            drawdown_stop=sl_threshold,
            take_profit=tp_threshold,
            rebalance_on_stop=rebalance_on_stop,
        )
    cerebro.broker.setcash(INITIAL_CASH)

    class MinCommCommission(bt.CommInfoBase):
        params = (
            ("commission", COMMISSION_RATE),
            ("commtype", bt.CommInfoBase.COMM_PERC),
            ("percabs", True),
            ("stocklike", True),
            ("min_commission", MIN_COMMISSION),
        )
    cerebro.broker.addcommissioninfo(MinCommCommission())

    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe",
                        riskfreerate=0.03, annualize=True)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")

    cerebro.run()
    strat = cerebro.runstrats[0][0]

    ret = strat.analyzers.returns.get_analysis()
    sharpe = strat.analyzers.sharpe.get_analysis()
    dd = strat.analyzers.drawdown.get_analysis()
    final_value = cerebro.broker.getvalue()

    return {
        "history": strat.history,
        "final_value": final_value,
        "total_return": (final_value / INITIAL_CASH) - 1,
        "annual_return": ret.get("rnorm100", 0) / 100,
        "sharpe": sharpe.get("sharperatio", 0),
        "max_drawdown": dd.get("max", {}).get("drawdown", 0) / 100,
        "n_stops": sum(1 for h in strat.history if h[3].get("stopped")),
        "n_takes": sum(1 for h in strat.history if h[3].get("taken")),
    }


# ══════════════════════════════════════════════════════════════════
# 6. 计量函数（252 交易日口径）
# ══════════════════════════════════════════════════════════════════

TRADING_DAYS = 252
RISK_FREE = 0.03


def compute_metrics(history: list) -> dict:
    """计算 7 个评价指标，全部基于日收益率、252 交易日年化。"""
    values = np.array([h[1] for h in history])
    dret = values[1:] / values[:-1] - 1
    n = len(dret)

    cum_ret = values[-1] / values[0] - 1
    ann_ret = (values[-1] / values[0]) ** (TRADING_DAYS / n) - 1
    ann_vol = np.std(dret, ddof=1) * np.sqrt(TRADING_DAYS)

    peak = np.maximum.accumulate(values)
    dd = (peak - values) / peak
    max_dd = np.max(dd)

    sharpe = (ann_ret - RISK_FREE) / ann_vol if ann_vol > 0 else 0
    calmar = ann_ret / max_dd if max_dd > 0 else 0

    downside = dret[dret < 0]
    dv = np.std(downside, ddof=1) * np.sqrt(TRADING_DAYS) if len(downside) > 0 else 0
    sortino = (ann_ret - RISK_FREE) / dv if dv > 0 else 0

    return {
        "cum_ret": cum_ret,
        "ann_ret": ann_ret,
        "ann_vol": ann_vol,
        "max_dd": max_dd,
        "sharpe": sharpe,
        "calmar": calmar,
        "sortino": sortino,
    }


METRIC_LABELS = {
    "cum_ret": "累计收益", "ann_ret": "年化收益", "ann_vol": "波动率",
    "max_dd": "最大回撤", "sharpe": "夏普比", "calmar": "卡玛比", "sortino": "索提诺比",
}


def fmt_pct(v: float) -> str:
    return f"{v:+.2%}" if abs(v) < 10 else f"{v:+.1%}"


def fmt_ratio(v: float) -> str:
    return f"{v:+.2f}"


# ══════════════════════════════════════════════════════════════════
# 7. 按年份拆解 + 动量窗口敏感性测试
# ══════════════════════════════════════════════════════════════════

def compute_yearly_metrics(history: list) -> dict[str, dict]:
    """按日历年份计算年收益率、年波动率、年内最大回撤。"""
    from collections import OrderedDict
    yearly: dict[str, list] = {}
    for h in history:
        yr = h[0][:4]
        yearly.setdefault(yr, []).append(h)

    result = OrderedDict()
    for yr in sorted(yearly):
        vals = np.array([r[1] for r in yearly[yr]])
        dret = vals[1:] / vals[:-1] - 1
        n = len(dret)
        ann_ret = vals[-1] / vals[0] - 1  # 年收益率（非年化，因为就是一年）
        ann_vol = np.std(dret, ddof=1) * np.sqrt(TRADING_DAYS) if n > 1 else 0.0
        peak = np.maximum.accumulate(vals)
        dd = (peak - vals) / peak
        max_dd = float(np.max(dd)) if len(dd) > 0 else 0.0
        result[yr] = {"ann_ret": ann_ret, "ann_vol": ann_vol, "max_dd": max_dd}
    return result


def _find_config(key: str):
    for k, sl, tp, rob, label in CONFIGS:
        if k == key:
            return sl, tp, rob, label
    return None, None, False, ""


SENSITIVITY_WINDOWS = [5, 10, 15, 20, 25, 30]


def run_sensitivity(key: str, year: str, sl_th, tp_th, rob):
    """对指定 (策略, 年份) 换 6 种动量窗口重跑，返回 {窗口: 年收益率}。"""
    start = f"{year}0101"
    end = f"{int(year) + 1}0101"
    results = {}
    for mp in SENSITIVITY_WINDOWS:
        panel = build_panel(start_date=start, end_date=end, mom_period=mp)
        res = run_one(key, sl_th, tp_th, rob, panel)
        results[mp] = res["total_return"]
    return results


# ══════════════════════════════════════════════════════════════════
# 8. 月度分布分析
# ══════════════════════════════════════════════════════════════════

MONTHLY_KEYS = ["buy_hold", "none", "sl_5", "sl_5_immediate"]
MONTHLY_LABELS = ["买入持有", "无止损失", "5% 止损", "5%止+即时重配"]


def compute_monthly_returns(history: list) -> dict[str, float]:
    """按{年-月}分组计算月度收益率。月收益 = (月末净值 / 月初净值) - 1。"""
    month_vals: dict[str, list] = {}
    for h in history:
        ym = h[0][:7]
        month_vals.setdefault(ym, []).append(h[1])
    monthly = {}
    for ym in sorted(month_vals):
        vals = month_vals[ym]
        ret = vals[-1] / vals[0] - 1
        monthly[ym] = ret
    return monthly


def monthly_analysis(monthly: dict[str, float]) -> dict:
    """月度分布统计。月收益 = 0 视为亏损。"""
    rets = list(monthly.values())
    n = len(rets)
    if n == 0:
        return {}
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    n_win = len(wins)
    n_loss = len(losses)
    win_rate = n_win / n if n > 0 else 0
    avg_win = float(np.mean(wins)) if wins else 0
    avg_loss = float(np.mean(losses)) if losses else 0
    profit_factor = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else float("inf")
    win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf")

    streak = 0
    longest_win = 0
    longest_loss = 0
    for r in rets:
        if r > 0:
            streak = streak + 1 if streak > 0 else 1
        else:
            streak = streak - 1 if streak < 0 else -1
        longest_win = max(longest_win, streak)
        longest_loss = min(longest_loss, streak)
    longest_loss = abs(longest_loss)

    return {
        "n_months": n,
        "n_win": n_win, "n_loss": n_loss,
        "win_rate": win_rate,
        "avg_win": avg_win, "avg_loss": avg_loss,
        "win_loss_ratio": win_loss_ratio,
        "profit_factor": profit_factor,
        "longest_win": longest_win,
        "longest_loss": longest_loss,
    }


# ══════════════════════════════════════════════════════════════════
# 9. 回撤事件追踪（≥ threshold 才算事件）
# ══════════════════════════════════════════════════════════════════

DD_THRESHOLD = 0.001


def get_drawdown_events(history: list, threshold: float = DD_THRESHOLD) -> dict:
    """
    回撤事件追踪。

    规则：
    - 起点：dd 从 ≤threshold 变为 >threshold 的那天（跌穿阈值）
    - 恢复：dd 从 >threshold 变为 ≤threshold 的那天（回到阈值之上）
    - dd 以每日收盘价计算，非 intraday
    - 未恢复的事件：恢复日标记为 None
    """
    values = np.array([h[1] for h in history])
    dates = [h[0] for h in history]
    peak = np.maximum.accumulate(values)
    dd = (peak - values) / peak

    events = []
    in_event = False
    event_start = None
    event_start_val = None
    event_peak_val = None

    for i in range(len(dd)):
        if not in_event and dd[i] > threshold:
            in_event = True
            event_start = i
            event_start_val = values[i]
            event_peak_val = peak[i]
        elif in_event and dd[i] <= threshold:
            in_event = False
            events.append({
                "start_idx": event_start,
                "end_idx": i,
                "start_date": dates[event_start],
                "end_date": dates[i],
                "start_value": event_start_val,
                "end_value": values[i],
                "peak_value": event_peak_val,
                "max_dd": float(np.max(dd[event_start:i+1])),
                "depth": float(np.max(dd[event_start:i+1])),
                "recovered": True,
            })
            event_start = None
            event_start_val = None
            event_peak_val = None

    if in_event:
        events.append({
            "start_idx": event_start,
            "end_idx": None,
            "start_date": dates[event_start],
            "end_date": None,
            "start_value": event_start_val,
            "end_value": values[-1],
            "peak_value": event_peak_val,
            "max_dd": float(np.max(dd[event_start:])),
            "depth": float(np.max(dd[event_start:])),
            "recovered": False,
        })

    if not events:
        return {"events": [], "n_events": 0, "avg_depth": 0, "avg_duration": 0,
                "max_depth": 0, "longest_duration": 0, "n_unrecovered": 0}

    depths = [e["depth"] for e in events]
    durations = []
    for e in events:
        if e["recovered"]:
            durations.append(e["end_idx"] - e["start_idx"])
    n_unrec = sum(1 for e in events if not e["recovered"])

    return {
        "events": sorted(events, key=lambda x: x["depth"], reverse=True),
        "n_events": len(events),
        "avg_depth": float(np.mean(depths)),
        "avg_duration": int(np.mean(durations)) if durations else 0,
        "max_depth": float(np.max(depths)),
        "longest_duration": max(durations) if durations else 0,
        "n_unrecovered": n_unrec,
    }


def fmt_duration(days: int) -> str:
    if days < 5:
        return f"{days}天"
    m = days // 21
    d = days % 21
    return f"{m}月{d}天" if d else f"{m}月"


# ══════════════════════════════════════════════════════════════════
# 10. 可视化（扩展）
# ══════════════════════════════════════════════════════════════════

def _init_mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    plt.rcParams["font.sans-serif"] = ["WenQuanYi Micro Hei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    return plt, mdates


def generate_charts(results: dict, panel: dict[str, pd.DataFrame]):
    plt, mdates = _init_mpl()
    os.makedirs(ASSETS_DIR, exist_ok=True)

    # ── Chart 1: 净值对比 ──
    fig1, ax1 = plt.subplots(figsize=(16, 7))
    for key, _, _, _, label in CONFIGS:
        recs = results[key]["history"]
        df = pd.DataFrame([{"date": r[0], "value": r[1]} for r in recs])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        ax1.plot(
            df.index, df["value"] / INITIAL_CASH * 100,
            color=CFG_COLORS[key], linestyle=CFG_LINESTYLES[key],
            linewidth=1.4, alpha=0.9,
            label=(
                f"{label} — "
                f"¥{results[key]['final_value']:,.0f}  "
                f"({results[key]['total_return']:+.1%})"
            ),
        )
    ax1.axhline(100, color="gray", lw=0.5, ls="--", alpha=0.4)
    ax1.set_title(
        "风险平价（每月再平衡）| 止损 + 止盈对比\n"
        f"佣金 {COMMISSION_RATE:.1%} 最低 ¥{MIN_COMMISSION:.0f}",
        fontsize=14, fontweight="bold", linespacing=1.4,
    )
    ax1.set_ylabel("净值（起点 = 100）")
    box = ax1.get_position()
    ax1.set_position([box.x0, box.y0, box.width * 0.72, box.height])
    ax1.legend(loc="upper left", fontsize=10, bbox_to_anchor=(1.02, 1))
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
    fig1.tight_layout()
    fig1.savefig(os.path.join(ASSETS_DIR, "rp-sl-tp-nav-compare.png"),
                 dpi=150, bbox_inches="tight")
    plt.close(fig1)
    print("  ✓ assets/rp-sl-tp-nav-compare.png")

    # ── Chart 2: 事件标注（3×3 子图，隐藏多余） ──
    fig2, axes = plt.subplots(3, 3, figsize=(18, 12))
    axes = axes.flatten()
    for idx, (key, _, _, _, label) in enumerate(CONFIGS):
        ax = axes[idx]
        recs = results[key]["history"]
        df = pd.DataFrame([
            {
                "date": r[0], "value": r[1],
                "stopped": len(r[3].get("stopped", [])) > 0,
                "taken": len(r[3].get("taken", [])) > 0,
            }
            for r in recs
        ])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        ax.plot(df.index, df["value"] / INITIAL_CASH * 100,
                color=CFG_COLORS[key], linewidth=1.0, alpha=0.8, label="净值")
        stop_pts = df[df["stopped"]]
        if not stop_pts.empty:
            ax.scatter(stop_pts.index,
                       stop_pts["value"] / INITIAL_CASH * 100,
                       color="red", s=40, marker="v", zorder=5,
                       label=f"止损({len(stop_pts)}天)")
        take_pts = df[df["taken"]]
        if not take_pts.empty:
            ax.scatter(take_pts.index,
                       take_pts["value"] / INITIAL_CASH * 100,
                       color="green", s=40, marker="^", zorder=5,
                       label=f"止盈({len(take_pts)}天)")
        ax.axhline(100, color="gray", lw=0.5, ls="--", alpha=0.3)
        ax.set_title(f"{label} | 最终 ¥{results[key]['final_value']:,.0f}  "
                     f"夏普 {results[key]['sharpe']:.2f}",
                     fontsize=11, fontweight="bold")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=12))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    for ax in axes[len(CONFIGS):]:
        ax.set_visible(False)
    fig2.suptitle("风险平价止损/止盈触发点标注（▼止损 ▲止盈）",
                  fontsize=14, fontweight="bold")
    fig2.tight_layout()
    fig2.savefig(os.path.join(ASSETS_DIR, "rp-sl-tp-events.png"),
                 dpi=150, bbox_inches="tight")
    plt.close(fig2)
    print("  ✓ assets/rp-sl-tp-events.png")

    # ── Chart 3: 回撤曲线对比 ──
    fig3, ax3 = plt.subplots(figsize=(16, 5))
    for key, _, _, _, label in CONFIGS:
        values = [h[1] for h in results[key]["history"]]
        peak = np.maximum.accumulate(values)
        dd = (peak - np.array(values)) / peak
        ax3.plot(dd * 100, color=CFG_COLORS[key],
                 linestyle=CFG_LINESTYLES[key],
                 linewidth=0.9, alpha=0.8, label=label)
    for thr, lbl, clr in [
        (0.05, "5% 止损线", "#e67e22"),
        (0.10, "10% 止盈线", "#27ae60"),
        (0.20, "20% 止盈线", "#8e44ad"),
    ]:
        ax3.axhline(thr * 100, color=clr, lw=0.7, ls=":", alpha=0.5)
        ax3.text(len(dd) - 10, thr * 100 + 0.5, lbl,
                 fontsize=8, color=clr, alpha=0.6)
    ax3.set_title("风险平价 — 回撤曲线对比", fontsize=13, fontweight="bold")
    ax3.set_ylabel("回撤幅度")
    ax3.legend(fontsize=9)
    ax3.grid(True, alpha=0.3)
    fig3.tight_layout()
    fig3.savefig(os.path.join(ASSETS_DIR, "rp-sl-tp-drawdown.png"),
                 dpi=150, bbox_inches="tight")
    plt.close(fig3)
    print("  ✓ assets/rp-sl-tp-drawdown.png")


# ── Chart 4: 月度收益直方图 ──
def generate_monthly_histogram(results: dict):
    plt, _ = _init_mpl()
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), sharey=True)
    axes = axes.flatten()
    # 计算全局 Y 范围（统一所有子图）
    all_rets = []
    for key in MONTHLY_KEYS:
        monthly = compute_monthly_returns(results[key]["history"])
        all_rets.extend(monthly.values())
    global_max = max(abs(r) for r in all_rets) * 1.15
    global_ylim = (-global_max * 100, global_max * 100)

    for idx, (key, label) in enumerate(zip(MONTHLY_KEYS, MONTHLY_LABELS)):
        ax = axes[idx]
        monthly = compute_monthly_returns(results[key]["history"])
        rets = list(monthly.values())
        colors = ["#e74c3c" if r < 0 else "#2ecc71" for r in rets]
        ax.bar(range(len(rets)), [r * 100 for r in rets],
               color=colors, width=0.8, alpha=0.8)
        ax.axhline(0, color="gray", lw=0.5)
        ax.set_ylim(global_ylim)
        stat = monthly_analysis(monthly)
        ax.set_title(
            f"{label}\n"
            f"胜率 {stat['win_rate']:.0%}  |  "
            f"均值盈 {stat['avg_win']:+.2%} / 亏 {stat['avg_loss']:+.2%}  |  "
            f"盈亏比 {stat['win_loss_ratio']:.2f}",
            fontsize=11, fontweight="bold", linespacing=1.2,
        )
        ax.set_xlabel(f"共 {stat['n_months']} 个月 | "
                       f"最长连赢 {stat['longest_win']} / 连亏 {stat['longest_loss']}")
        xtick_step = 12
        ax.set_xticks(range(0, len(rets), xtick_step))
        ax.set_xticklabels(list(monthly.keys())[::xtick_step], fontsize=8)
        ax.grid(True, alpha=0.2, axis="y")
    # 左边子图加 Y 轴标签
    axes[0].set_ylabel("月度收益率", fontsize=10)
    axes[2].set_ylabel("月度收益率", fontsize=10)
    fig.suptitle("月度收益分布（统一 Y 轴）", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "rp-monthly-histogram.png"),
                dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  ✓ assets/rp-monthly-histogram.png")


# ── Chart 5: 水下曲线（逐策略） ──
def generate_underwater_curves(results: dict):
    plt, _ = _init_mpl()
    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    axes = axes.flatten()
    for idx, (key, label) in enumerate(zip(MONTHLY_KEYS, MONTHLY_LABELS)):
        ax = axes[idx]
        values = np.array([h[1] for h in results[key]["history"]])
        dates = pd.to_datetime([h[0] for h in results[key]["history"]])
        peak = np.maximum.accumulate(values)
        dd = (peak - values) / peak
        ax.fill_between(dates, dd * 100, 0,
                        color="#e74c3c", alpha=0.5, linewidth=0)
        ax.plot(dates, dd * 100, color="#c0392b", linewidth=0.5, alpha=0.8)
        ax.axhline(0, color="gray", lw=0.5)
        ax.axhline(-5, color="#e67e22", lw=0.7, ls=":", alpha=0.5)
        ax.set_title(f"{label} — 水下曲线", fontsize=12, fontweight="bold")
        ax.set_ylabel("回撤幅度")
        ax.set_xlabel(f"最大回撤 {np.max(dd):.1%}")
        ax.grid(True, alpha=0.2)
    fig.suptitle("回撤曲线（水下）", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "rp-underwater.png"),
                dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  ✓ assets/rp-underwater.png")


# ── 月度分析打印 ──
def print_monthly_analysis(results: dict):
    print("▶ 月度分布分析（四策略）...")
    header = f"  {'策略':<12} {'月数':>4} {'胜率':>6} {'平均盈月':>9} {'平均亏月':>9} {'盈亏比':>7} {'盈亏因子':>9} {'连赢':>4} {'连亏':>4}"
    print(header)
    print(f"  {'─' * 70}")
    for key, label in zip(MONTHLY_KEYS, MONTHLY_LABELS):
        monthly = compute_monthly_returns(results[key]["history"])
        s = monthly_analysis(monthly)
        print(f"  {label:<12}"
              f" {s['n_months']:>4d}"
              f" {s['win_rate']:>5.0%}"
              f" {s['avg_win']:>+8.2%}"
              f" {s['avg_loss']:>+8.2%}"
              f" {s['win_loss_ratio']:>6.2f}"
              f" {s['profit_factor']:>8.2f}"
              f" {s['longest_win']:>4d}"
              f" {s['longest_loss']:>4d}")
    print()


# ── 回撤事件打印 ──
def print_drawdown_analysis(results: dict):
    print("▶ 回撤事件分析（阈值 ≥0.1%）...")
    for key, label in zip(MONTHLY_KEYS, MONTHLY_LABELS):
        info = get_drawdown_events(results[key]["history"])
        print(f"\n  {label}:")
        print(f"    总回撤事件: {info['n_events']} 次"
              f"  |  未恢复: {info['n_unrecovered']}"
              f"  |  平均深度: {info['avg_depth']:.2%}"
              f"  |  最深: {info['max_depth']:.2%}"
              f"  |  平均持续: {fmt_duration(info['avg_duration'])}")
        print(f"    {'─' * 70}")
        if info["events"]:
            print(f"    {'开始':>12} {'结束':>12} {'深度':>8} {'持续':>10} {'恢复':>6}")
            for evt in info["events"][:5]:
                end = evt["end_date"] if evt["recovered"] else "—"
                dur = fmt_duration(evt["end_idx"] - evt["start_idx"]) if evt["recovered"] else "—"
                rec = "✅" if evt["recovered"] else "❌"
                print(f"    {evt['start_date']:>12} {end:>12} {evt['depth']:>7.1%} {dur:>10} {rec:>6}")
    print()


# ══════════════════════════════════════════════════════════════════
# 11. 主流程
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 72)
    print("  止损 + 止盈保护研究 — 风险平价")
    print(f"  策略: 风险平价 + 每月再平衡")
    print(f"  佣金: {COMMISSION_RATE:.1%}  最低 ¥{MIN_COMMISSION:.0f}")
    print(f"  方案: {' | '.join(c[4] for c in CONFIGS)}")
    print("=" * 72)

    print("\n▶ 获取数据 + 计算指标...")
    panel = build_panel()
    for sym, df in panel.items():
        print(f"    {sym} ({SYMBOLS[sym]}): {len(df)} 交易日")

    print("\n▶ 运行回测...")
    results = {}
    for key, sl_th, tp_th, rebal_on_stop, label in CONFIGS:
        print(f"  ▶ {label:>10}...", end=" ")
        sys.stdout.flush()
        results[key] = run_one(key, sl_th, tp_th, rebal_on_stop, panel)
        r = results[key]
        parts = [f"¥{r['final_value']:>8,.0f}  ({r['total_return']:+>+7.2%})",
                 f"夏普 {r['sharpe']:.2f}",
                 f"回撤 {r['max_drawdown']:.2%}"]
        if r['n_stops']:
            parts.append(f"止损{r['n_stops']}天")
        if r['n_takes']:
            parts.append(f"止盈{r['n_takes']}天")
        print("  ".join(parts))

    print(f"\n{'=' * 105}")
    print("  方案对比汇总 — 风险平价")
    print(f"{'=' * 105}")
    header = f"  {'方案':<12} {'最终值':>10} {'累计收益':>10} {'年化收益':>10} {'最大回撤':>10} {'夏普':>8} {'止损天':>6} {'止盈天':>6}"
    print(header)
    print(f"  {'─' * 78}")
    for key, _, _, _, label in CONFIGS:
        r = results[key]
        print(f"  {label:<12}"
              f" ¥{r['final_value']:>8,.0f}"
              f" {r['total_return']:>+9.2%}"
              f" {r['annual_return']:>9.2%}"
              f" {r['max_drawdown']:>9.2%}"
              f" {r['sharpe']:>7.2f}"
              f" {r['n_stops']:>6d}"
              f" {r['n_takes']:>6d}")
    print()

    # ── 7 指标对比表（以买入持有为基准） ──
    print("▶ 计算 7 指标对比（年化口径 252 交易日）...")
    bmk_key = "buy_hold"
    bmk_m = compute_metrics(results[bmk_key]["history"])
    strat_keys = [k for k, _, _, _, _ in CONFIGS if k != bmk_key]

    metrics_order = ["cum_ret", "ann_ret", "ann_vol", "max_dd", "sharpe", "calmar", "sortino"]
    fmt_map = {"cum_ret": fmt_pct, "ann_ret": fmt_pct, "ann_vol": fmt_pct,
               "max_dd": fmt_pct, "sharpe": fmt_ratio, "calmar": fmt_ratio, "sortino": fmt_ratio}

    # 表头
    print(f"\n{'=' * 130}")
    print(f"  7 指标对比  |  基准: 买入持有")
    print(f"{'=' * 130}")
    header = f"  {'方案':<12}"
    for m in metrics_order:
        header += f" {METRIC_LABELS[m]:>10}"
        header += f" {'超额':>8}"
    print(header)
    print(f"  {'─' * (12 + 1 + 18 * len(metrics_order))}")

    # 基准行
    row = f"  {'买入持有':<12}"
    for m in metrics_order:
        row += f" {fmt_map[m](bmk_m[m]):>10}"
        row += f" {'—':>8}"
    print(row)

    # 策略行
    for key, _, _, _, label in CONFIGS:
        if key == bmk_key:
            continue
        m = compute_metrics(results[key]["history"])
        row = f"  {label:<12}"
        for met in metrics_order:
            val = m[met]
            bv = bmk_m[met]
            row += f" {fmt_map[met](val):>10}"
            if met in ("ann_vol", "max_dd"):
                # 越小越好的指标：超额 = 基准 - 策略
                diff = bv - val
            else:
                diff = val - bv
            row += f" {fmt_map[met](diff):>8}"
        print(row)
    print()

    # ── 年份拆解 ──
    print("▶ 按年份拆解收益率...")
    yearly_all = {}
    for key, _, _, _, label in CONFIGS:
        yearly_all[key] = compute_yearly_metrics(results[key]["history"])
    years = sorted(yearly_all["buy_hold"].keys())

    # 打印年收益率矩阵
    print(f"\n{'=' * (12 + 1 + 14 * len(years))}")
    print(f"  {'方案':<12}", end="")
    for yr in years:
        print(f" {yr:>>7}收益{'':>3}波动{'':>3}回撤", end="")
    print()
    print(f"  {'─' * (12 + 1 + 14 * len(years))}")

    neg_cases = []  # (key, year, label)
    for key, _, _, _, label in CONFIGS:
        row = f"  {label:<12}"
        for yr in years:
            m = yearly_all[key].get(yr, {})
            r = m.get("ann_ret", 0)
            v = m.get("ann_vol", 0)
            dd = m.get("max_dd", 0)
            row += f" {r:+>+7.1%}"
            row += f" {v:>5.1%}"
            row += f" {dd:>4.1%}"
            if r < 0:
                neg_cases.append((key, yr, label))
        print(row)
    print(f"  {'─' * (12 + 1 + 14 * len(years))}")
    print(f"  {'负收益标记':<12}", end="")
    for yr in years:
        neg_in_year = any(k == yr for _, k, _ in neg_cases)
        print(f" {'⚠️' if neg_in_year else '✅':>14}", end="")
    print()
    print()

    # ── 年收益率表（仅收益列，更紧凑） ──
    print(f"{'方案':<14}", end="")
    for yr in years:
        print(f" {yr:>10}", end="")
    print()
    print(f"{'─' * (14 + 12 * len(years))}")
    for key, _, _, _, label in CONFIGS:
        print(f"{label:<14}", end="")
        for yr in years:
            r = yearly_all[key].get(yr, {}).get("ann_ret", 0)
            print(f" {r:+>+9.1%}", end="")
        print()
    print()

    # ── 负收益年份敏感性测试 ──
    if neg_cases:
        print("▶ 负收益年份敏感性测试（换 6 种动量窗口 5/10/15/20/25/30 天）...")
        print(f"  发现 {len(neg_cases)} 个负收益 (策略, 年份) 组合:")
        for key, yr, label in neg_cases:
            rr = yearly_all[key][yr]["ann_ret"]
            print(f"    {label}  {yr}年  {rr:+.1%}")

        print()
        for key, yr, label in neg_cases:
            sl, tp, rob, _ = _find_config(key)
            print(f"  ▶ {label}  {yr}年")
            sens = run_sensitivity(key, yr, sl, tp, rob)
            for mp in SENSITIVITY_WINDOWS:
                r = sens[mp]
                flag = "✅" if r >= 0 else "❌"
                print(f"     MOM={mp:>2d}天  {r:+>+8.1%} {flag}")
            print()
    else:
        print("▶ 所有策略在所有年份均为正收益，无需敏感性测试。")
    print()

    # ── 月度分布分析 ──
    print_monthly_analysis(results)

    # ── 回撤事件分析 ──
    print_drawdown_analysis(results)

    print("▶ 生成图表...")
    generate_charts(results, panel)
    generate_monthly_histogram(results)
    generate_underwater_curves(results)
    print(f"\n  ✅ 完成。")
