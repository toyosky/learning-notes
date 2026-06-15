#!/usr/bin/env python3
"""
止损保护研究 — 基于动量排名 + 每5日再平衡。

核心思想：当组合从峰值回撤超过阈值时，立即清仓（现金），
等待下一个再平衡日重新入场。避免"眼睁睁看着下跌而无能为力"。

对比方案：
  - 无止损失（baseline）
  - 5% 回撤触发止损
  - 10% 回撤触发止损
  - 15% 回撤触发止损

佣金：0.1%，最低 5 元。
"""

import backtrader as bt
import pandas as pd
import numpy as np
import sys, os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../01-data/code"))
from data_fetcher import fetch_etf_data

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "../../assets")

# ── 常量 ──
SYMBOLS = {"510300": "沪深300", "513100": "纳指100", "518880": "黄金"}
SYMBOL_COLORS = {"510300": "#E53935", "513100": "#1E88E5", "518880": "#FDD835"}
INITIAL_CASH = 100_000.0
MOM_PERIOD = 20
COMMISSION_RATE = 0.001
MIN_COMMISSION = 5.0

# ── 止损方案 ──
STOP_LOSS_CONFIGS = [
    ("none",   None,  "无止损失"),
    ("pct_5",  0.05,  "5% 止损"),
    ("pct_10", 0.10, "10% 止损"),
    ("pct_15", 0.15, "15% 止损"),
]
SL_COLORS = {"none": "#7f8c8d", "pct_5": "#e67e22", "pct_10": "#e74c3c", "pct_15": "#9b59b6"}
SL_LINESTYLES = {"none": "-", "pct_5": "--", "pct_10": "-.", "pct_15": ":"}
SL_ALPHAS = {"none": 0.9, "pct_5": 0.9, "pct_10": 0.9, "pct_15": 0.9}


# ══════════════════════════════════════════════════════════════════
# 1. 数据准备
# ══════════════════════════════════════════════════════════════════

def build_panel() -> dict[str, pd.DataFrame]:
    """获取数据 + 计算 mom, vol, ram。"""
    data = {}
    for symbol in ("510300", "513100", "518880"):
        df = fetch_etf_data(symbol=symbol, start_date="20210101", end_date="20260101")
        df["log_return"] = np.log(df["Close"] / df["Close"].shift(1))
        df["mom"] = df["log_return"].rolling(MOM_PERIOD).mean()
        df["vol"] = df["log_return"].rolling(MOM_PERIOD).std(ddof=1)
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
# 3. 策略 — 动量排名 + 可配置回撤止损
# ══════════════════════════════════════════════════════════════════

class MomentumWithStopLoss(bt.Strategy):
    """动量排名 + 回撤止损。

    Parameters
    ----------
    rebalance_freq : int
        再平衡频率（交易日数）。
    drawdown_stop : float | None
        回撤止损阈值，None = 不止损。
    """
    params = (
        ("rebalance_freq", 5),
        ("drawdown_stop", None),
    )

    def __init__(self):
        self.history = []       # [(date, value, {sym: weight}, is_stopped)]
        self._bars_since_rebalance = 0
        self._peak_value = INITIAL_CASH
        self._stopped_out = False

    def _compute_weights(self) -> dict:
        """动量排名权重。"""
        rams = {}
        for d in self.datas:
            rams[d._name] = d.ram[0]
        pos = {k: v for k, v in rams.items()
               if v is not None and v > 0 and not np.isnan(v)}
        if not pos:
            return {}
        total = sum(pos.values())
        return {k: pos[k] / total for k in pos}

    def next(self):
        freq = self.params.rebalance_freq
        is_rebalance_day = (self._bars_since_rebalance == 0)

        current_value = self.broker.getvalue()
        weights = self._compute_weights()

        # ── 更新峰值（每个 bar 都做） ──
        if not self._stopped_out:
            self._peak_value = max(self._peak_value, current_value)

        # ── 检查是否触发止损 ──
        stop_triggered = False
        if self.params.drawdown_stop is not None and not self._stopped_out:
            dd = (self._peak_value - current_value) / self._peak_value
            if dd >= self.params.drawdown_stop:
                stop_triggered = True
                self._stopped_out = True
                # 立即清仓
                for d in self.datas:
                    self.order_target_percent(d, 0.0)

        # ── 如果已止损 ──
        if self._stopped_out:
            if is_rebalance_day:
                # 再平衡日：重置并重新入场
                self._stopped_out = False
                self._peak_value = current_value
                # 继续往下执行正常再平衡
            else:
                self.history.append((
                    self.datas[0].datetime.date(0).isoformat(),
                    current_value, dict(weights), True,
                ))
                self._bars_since_rebalance += 1
                if isinstance(freq, int) and self._bars_since_rebalance >= freq:
                    self._bars_since_rebalance = 0
                return

        # ── 正常操作 ──
        self.history.append((
            self.datas[0].datetime.date(0).isoformat(),
            current_value,
            dict(weights),
            stop_triggered,  # 仅标记触发当天
        ))

        if is_rebalance_day:
            for d in self.datas:
                self.order_target_percent(d, weights.get(d._name, 0.0))

        self._bars_since_rebalance += 1
        if isinstance(freq, int) and self._bars_since_rebalance >= freq:
            self._bars_since_rebalance = 0


# ══════════════════════════════════════════════════════════════════
# 4. 回测运行器
# ══════════════════════════════════════════════════════════════════

def run_one(sl_key: str, sl_threshold: float | None,
            data_panel: dict[str, pd.DataFrame]) -> dict:
    """运行单个止损方案的动量排名回测。"""
    cerebro = bt.Cerebro()
    for symbol, df in data_panel.items():
        feed = ETFData(dataname=df)
        feed._name = symbol
        cerebro.adddata(feed)

    cerebro.addstrategy(
        MomentumWithStopLoss,
        rebalance_freq=5,
        drawdown_stop=sl_threshold,
    )
    cerebro.broker.setcash(INITIAL_CASH)

    # 佣金
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

    # 从 history 提取止损事件信息
    stop_events = [
        (h[0], h[1]) for h in strat.history if h[3]
    ]

    # 记录每周的 cash/equity 比例，观察止损后的现金状态
    cash_series = []
    for h in strat.history:
        cash_series.append((h[0], h[1]))

    ret = strat.analyzers.returns.get_analysis()
    sharpe = strat.analyzers.sharpe.get_analysis()
    dd = strat.analyzers.drawdown.get_analysis()
    final_value = cerebro.broker.getvalue()

    return {
        "history": strat.history,
        "stop_events": stop_events,
        "final_value": final_value,
        "total_return": (final_value / INITIAL_CASH) - 1,
        "annual_return": ret.get("rnorm100", 0) / 100,
        "sharpe": sharpe.get("sharperatio", 0),
        "max_drawdown": dd.get("max", {}).get("drawdown", 0) / 100,
        "n_stops": len(stop_events),
    }


# ══════════════════════════════════════════════════════════════════
# 5. 可视化
# ══════════════════════════════════════════════════════════════════

def _init_mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import matplotlib.patches as mpatches
    plt.rcParams["font.sans-serif"] = ["WenQuanYi Micro Hei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    return plt, mdates, mpatches


def generate_charts(results: dict, panel: dict[str, pd.DataFrame]):
    """生成止损对比图表。"""
    plt, mdates, mpatches = _init_mpl()
    os.makedirs(ASSETS_DIR, exist_ok=True)

    # ──────────────────────────────────────────────────────────
    # Chart 1: 净值对比
    # ──────────────────────────────────────────────────────────
    fig1, ax1 = plt.subplots(figsize=(16, 7))

    for sl_key, _, sl_label in STOP_LOSS_CONFIGS:
        recs = results[sl_key]["history"]
        df = pd.DataFrame([{"date": r[0], "value": r[1]} for r in recs])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")

        ax1.plot(
            df.index, df["value"] / INITIAL_CASH * 100,
            color=SL_COLORS[sl_key], linestyle=SL_LINESTYLES[sl_key],
            linewidth=1.4, alpha=SL_ALPHAS[sl_key],
            label=(
                f"{sl_label} — "
                f"¥{results[sl_key]['final_value']:,.0f}  "
                f"({results[sl_key]['total_return']:+.1%})  "
                f"止损{results[sl_key]['n_stops']}次"
            ),
        )

    ax1.axhline(100, color="gray", lw=0.5, ls="--", alpha=0.4)
    ax1.set_title(
        "动量排名（每5日再平衡）| 回撤止损对比\n"
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
    fig1.savefig(os.path.join(ASSETS_DIR, "stop-loss-nav-compare.png"),
                 dpi=150, bbox_inches="tight")
    plt.close(fig1)
    print("  ✓ assets/stop-loss-nav-compare.png")

    # ──────────────────────────────────────────────────────────
    # Chart 2: 净值 + 止损触发点标注（仅 5% 止损为例，展示机制）
    # ──────────────────────────────────────────────────────────
    fig2, axes = plt.subplots(2, 2, figsize=(16, 10))
    axes = axes.flatten()

    for idx, (sl_key, sl_threshold, sl_label) in enumerate(STOP_LOSS_CONFIGS):
        ax = axes[idx]
        recs = results[sl_key]["history"]
        df = pd.DataFrame([
            {"date": r[0], "value": r[1], "stopped": r[3]}
            for r in recs
        ])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")

        # 净值线
        ax.plot(
            df.index, df["value"] / INITIAL_CASH * 100,
            color=SL_COLORS[sl_key], linewidth=1.0, alpha=0.8,
            label="净值",
        )
        # 止损点
        stop_points = df[df["stopped"]]
        if not stop_points.empty:
            ax.scatter(
                stop_points.index,
                stop_points["value"] / INITIAL_CASH * 100,
                color="red", s=40, marker="v", zorder=5,
                label=f"止损触发 ({len(stop_points)}次)",
            )

        ax.axhline(100, color="gray", lw=0.5, ls="--", alpha=0.3)
        ax.set_title(
            f"{sl_label} | 最终 ¥{results[sl_key]['final_value']:,.0f}  "
            f"夏普 {results[sl_key]['sharpe']:.2f}",
            fontsize=11, fontweight="bold",
        )
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=12))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

    fig2.suptitle(
        "逐仓止损触发点标注（红色▼ = 止损事件）",
        fontsize=14, fontweight="bold",
    )
    fig2.tight_layout()
    fig2.savefig(os.path.join(ASSETS_DIR, "stop-loss-events.png"),
                 dpi=150, bbox_inches="tight")
    plt.close(fig2)
    print("  ✓ assets/stop-loss-events.png")

    # ──────────────────────────────────────────────────────────
    # Chart 3: 回撤曲线对比
    # ──────────────────────────────────────────────────────────
    fig3, ax3 = plt.subplots(figsize=(16, 5))

    for sl_key, _, sl_label in STOP_LOSS_CONFIGS:
        recs = results[sl_key]["history"]
        values = [h[1] for h in recs]
        peak = np.maximum.accumulate(values)
        dd = (peak - np.array(values)) / peak

        ax3.plot(dd * 100,
                 color=SL_COLORS[sl_key], linestyle=SL_LINESTYLES[sl_key],
                 linewidth=0.9, alpha=0.8, label=sl_label)

    # 止损阈值参考线
    for threshold, label, color in [
        (0.05, "5% 阈值", "#e67e22"),
        (0.10, "10% 阈值", "#e74c3c"),
        (0.15, "15% 阈值", "#9b59b6"),
    ]:
        ax3.axhline(threshold * 100, color=color, lw=0.7, ls=":", alpha=0.5)
        ax3.text(len(dd) - 10, threshold * 100 + 0.5, label,
                 fontsize=8, color=color, alpha=0.6)

    ax3.set_title("回撤曲线对比", fontsize=13, fontweight="bold")
    ax3.set_ylabel("回撤幅度")
    ax3.legend(fontsize=9)
    ax3.grid(True, alpha=0.3)
    plt.tight_layout()
    fig3.savefig(os.path.join(ASSETS_DIR, "stop-loss-drawdown.png"),
                 dpi=150, bbox_inches="tight")
    plt.close(fig3)
    print("  ✓ assets/stop-loss-drawdown.png")


# ══════════════════════════════════════════════════════════════════
# 6. 主流程
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 72)
    print("  回撤止损保护研究")
    print(f"  策略: 动量排名 + 每5日再平衡")
    print(f"  佣金: {COMMISSION_RATE:.1%}  最低 ¥{MIN_COMMISSION:.0f}")
    print(f"  止损方案: {' | '.join(s[2] for s in STOP_LOSS_CONFIGS)}")
    print("=" * 72)

    # ── 数据 ──
    print("\n▶ 获取数据 + 计算指标...")
    panel = build_panel()
    for sym, df in panel.items():
        print(f"    {sym} ({SYMBOLS[sym]}): {len(df)} 交易日")

    # ── 回测 ──
    print("\n▶ 运行回测（4 种止损方案）...")
    results = {}
    for sl_key, sl_threshold, sl_label in STOP_LOSS_CONFIGS:
        print(f"  ▶ {sl_label:>10}...", end=" ")
        sys.stdout.flush()
        results[sl_key] = run_one(sl_key, sl_threshold, panel)
        r = results[sl_key]
        print(
            f"¥{r['final_value']:>8,.0f}  "
            f"({r['total_return']:+>+7.2%})  "
            f"夏普 {r['sharpe']:.2f}  "
            f"回撤 {r['max_drawdown']:.2%}  "
            f"止损 {r['n_stops']}次"
        )

    # ── 汇总表 ──
    print(f"\n{'=' * 95}")
    print("  止损方案对比汇总")
    print(f"{'=' * 95}")
    header = (
        f"  {'方案':<12} {'最终值':>10} {'累计收益':>10} {'年化收益':>10} "
        f"{'最大回撤':>10} {'夏普':>8} {'止损次数':>8}"
    )
    print(header)
    print(f"  {'─' * 70}")
    for sl_key, _, sl_label in STOP_LOSS_CONFIGS:
        r = results[sl_key]
        print(
            f"  {sl_label:<12}"
            f" ¥{r['final_value']:>8,.0f}"
            f" {r['total_return']:>+9.2%}"
            f" {r['annual_return']:>9.2%}"
            f" {r['max_drawdown']:>9.2%}"
            f" {r['sharpe']:>7.2f}"
            f" {r['n_stops']:>8d}"
        )
    print()

    # ── 图表 ──
    print("▶ 生成图表...")
    generate_charts(results, panel)
    print(f"\n  ✅ 完成。")
