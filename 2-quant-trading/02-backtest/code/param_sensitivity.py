#!/usr/bin/env python3
"""
参数敏感性分析 — 动量排名策略

对三个关键参数分别做单参数扫描（其余参数固定在最优值），
计算每组 Sharpe 比极差（range），绘制三子图折线对比，共享 Y 轴。

参数扫描范围（围绕最优值）:
  1. 再平衡频率: [1, 3, 5, 7, 10, 15, 20, "monthly"]  — 最优 5
  2. 止损阈值:   [0.03, 0.05, 0.07, 0.10, 0.12, 0.15, 0.20] — 最优 0.10
  3. 动量窗口 N:  [5, 10, 15, 20, 25, 30, 40, 60]          — 最优 20

佣金：0.1%，最低 5 元。
"""

import backtrader as bt
import pandas as pd
import numpy as np
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../01-data/code"))
from data_fetcher import fetch_etf_data

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "../../assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

# ── 常量 ──
SYMBOLS = {"510300": "沪深300", "513100": "纳指100", "518880": "黄金"}
INITIAL_CASH = 100_000.0
COMMISSION_RATE = 0.001
MIN_COMMISSION = 5.0
TRADING_DAYS = 252
RISK_FREE = 0.03

# ── 参数扫描范围 ──
# 最优值来自历史回测结论
REBALANCE_FREQS = [1, 3, 5, 7, 10, 15, 20, "monthly"]
STOP_LOSS_THRESHOLDS = [0.03, 0.05, 0.07, 0.10, 0.12, 0.15, 0.20]
MOM_WINDOWS = [5, 10, 15, 20, 25, 30, 40, 60]

# 最优参数
OPTIMAL_FREQ = 5
OPTIMAL_STOP = 0.10
OPTIMAL_MOM = 20

# 数值映射（用于 X 轴刻度）
FREQ_NUMS = [1, 3, 5, 7, 10, 15, 20, 21]  # "monthly" → 21
FREQ_LABELS = {1: "1", 3: "3", 5: "5", 7: "7", 10: "10",
               15: "15", 20: "20", 21: "月", "monthly": "月"}

# ── 颜色方案 ──
SENSITIVITY_COLORS = {
    "rebalance_freq": "#2196F3",
    "stop_loss":      "#E53935",
    "mom_window":     "#4CAF50",
}
OPTIMAL_MARKER_COLOR = "#FF9800"


# ══════════════════════════════════════════════════════════════════
# 1. 数据准备（通用）
# ══════════════════════════════════════════════════════════════════

def build_panel(mom_period: int = OPTIMAL_MOM) -> dict[str, pd.DataFrame]:
    """获取数据 + 按给定窗口计算 mom, vol, ram。"""
    data = {}
    for symbol in ("510300", "513100", "518880"):
        df = fetch_etf_data(symbol=symbol, start_date="20210101", end_date="20260101")
        df["log_return"] = np.log(df["Close"] / df["Close"].shift(1))
        df["mom"] = df["log_return"].rolling(mom_period).mean()
        df["vol"] = df["log_return"].rolling(mom_period).std(ddof=1)
        df["ram"] = df["mom"] / df["vol"]
        data[symbol] = df
    return data


# ══════════════════════════════════════════════════════════════════
# 2. 数据馈送（复用 stop_loss_study.py 模式）
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
# 3. 策略 — 动量排名 + 可配置止损（与 stop_loss_study.py 一致）
# ══════════════════════════════════════════════════════════════════

class MomentumWithStopLoss(bt.Strategy):
    """动量排名 + 回撤止损。

    Parameters
    ----------
    rebalance_freq : int | str
        再平衡频率（交易日数，或 "monthly"）。
    drawdown_stop : float | None
        回撤止损阈值，None = 不止损。
    """
    params = (
        ("rebalance_freq", OPTIMAL_FREQ),
        ("drawdown_stop", OPTIMAL_STOP),
    )

    def __init__(self):
        self.history = []
        self._bars_since_rebalance = 0
        self._peak_value = INITIAL_CASH
        self._stopped_out = False
        self._last_month = None

    def _compute_weights(self) -> dict:
        rams = {}
        for d in self.datas:
            rams[d._name] = d.ram[0]
        pos = {k: v for k, v in rams.items()
               if v is not None and v > 0 and not np.isnan(v)}
        if not pos:
            return {}
        total = sum(pos.values())
        return {k: pos[k] / total for k in pos}

    def _is_rebalance_day(self) -> bool:
        freq = self.params.rebalance_freq
        if freq == "monthly":
            dt = self.datas[0].datetime.date(0)
            should = (self._last_month is None or dt.month != self._last_month)
            self._last_month = dt.month
            return should
        return self._bars_since_rebalance == 0

    def next(self):
        freq = self.params.rebalance_freq
        is_rebalance = self._is_rebalance_day()
        current_value = self.broker.getvalue()
        weights = self._compute_weights()

        # 更新峰值
        if not self._stopped_out:
            self._peak_value = max(self._peak_value, current_value)

        # 检查止损
        stop_triggered = False
        if self.params.drawdown_stop is not None and not self._stopped_out:
            dd = (self._peak_value - current_value) / self._peak_value
            if dd >= self.params.drawdown_stop:
                stop_triggered = True
                self._stopped_out = True
                for d in self.datas:
                    self.order_target_percent(d, 0.0)

        # 已止损 → 等待下一个再平衡日重新入场
        if self._stopped_out:
            if is_rebalance:
                self._stopped_out = False
                self._peak_value = current_value
            else:
                self.history.append((
                    self.datas[0].datetime.date(0).isoformat(),
                    current_value, dict(weights), True,
                ))
                self._bars_since_rebalance += 1
                if isinstance(freq, int) and self._bars_since_rebalance >= freq:
                    self._bars_since_rebalance = 0
                return

        # 正常操作
        self.history.append((
            self.datas[0].datetime.date(0).isoformat(),
            current_value, dict(weights), stop_triggered,
        ))

        if is_rebalance:
            for d in self.datas:
                self.order_target_percent(d, weights.get(d._name, 0.0))

        self._bars_since_rebalance += 1
        if isinstance(freq, int) and self._bars_since_rebalance >= freq:
            self._bars_since_rebalance = 0


# ══════════════════════════════════════════════════════════════════
# 4. 回测运行器
# ══════════════════════════════════════════════════════════════════

def run_one(rebalance_freq=OPTIMAL_FREQ, drawdown_stop=OPTIMAL_STOP,
            data_panel=None) -> dict:
    """运行单次动量排名回测。"""
    cerebro = bt.Cerebro()
    for symbol, df in data_panel.items():
        feed = ETFData(dataname=df)
        feed._name = symbol
        cerebro.adddata(feed)

    cerebro.addstrategy(
        MomentumWithStopLoss,
        rebalance_freq=rebalance_freq,
        drawdown_stop=drawdown_stop,
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

    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe",
                        riskfreerate=0.03, annualize=True)
    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")

    cerebro.run()
    strat = cerebro.runstrats[0][0]

    ret = strat.analyzers.returns.get_analysis()
    sharpe = strat.analyzers.sharpe.get_analysis()
    dd = strat.analyzers.drawdown.get_analysis()
    final_value = cerebro.broker.getvalue()

    return {
        "final_value": final_value,
        "total_return": (final_value / INITIAL_CASH) - 1,
        "annual_return": ret.get("rnorm100", 0) / 100,
        "sharpe": sharpe.get("sharperatio", 0),
        "max_drawdown": dd.get("max", {}).get("drawdown", 0) / 100,
    }


# ══════════════════════════════════════════════════════════════════
# 5. 参数扫描
# ══════════════════════════════════════════════════════════════════

def sweep_rebalance_freq(data_panel) -> dict:
    """扫描再平衡频率，固定止损=10%, 动量窗口=20。"""
    results = {}
    for freq in REBALANCE_FREQS:
        label = f"freq={freq}"
        print(f"  ▶ {label:>15}...", end=" ")
        sys.stdout.flush()
        r = run_one(rebalance_freq=freq, drawdown_stop=OPTIMAL_STOP,
                    data_panel=data_panel)
        results[freq] = r["sharpe"]
        print(f"Sharpe {r['sharpe']:.4f}  "
              f"总收益 {r['total_return']:+.2%}")
    return results


def sweep_stop_loss(data_panel) -> dict:
    """扫描止损阈值，固定频率=5, 动量窗口=20。"""
    results = {}
    for th in STOP_LOSS_THRESHOLDS:
        label = f"stop={th:.0%}"
        print(f"  ▶ {label:>15}...", end=" ")
        sys.stdout.flush()
        r = run_one(rebalance_freq=OPTIMAL_FREQ, drawdown_stop=th,
                    data_panel=data_panel)
        results[th] = r["sharpe"]
        print(f"Sharpe {r['sharpe']:.4f}  "
              f"总收益 {r['total_return']:+.2%}")
    return results


def sweep_mom_window() -> dict:
    """扫描动量窗口 N，固定频率=5, 止损=10%。
    每次重建 data_panel（因为 mom/vol/ram 依赖窗口大小）。"""
    results = {}
    for mp in MOM_WINDOWS:
        label = f"mom_N={mp}"
        print(f"  ▶ {label:>15}...", end=" ")
        sys.stdout.flush()
        panel = build_panel(mom_period=mp)
        r = run_one(rebalance_freq=OPTIMAL_FREQ, drawdown_stop=OPTIMAL_STOP,
                    data_panel=panel)
        results[mp] = r["sharpe"]
        print(f"Sharpe {r['sharpe']:.4f}  "
              f"总收益 {r['total_return']:+.2%}")
    return results


# ══════════════════════════════════════════════════════════════════
# 6. 可视化 — 三子图折线（共享 Y 轴）
# ══════════════════════════════════════════════════════════════════

def _init_mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["WenQuanYi Micro Hei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    return plt


def generate_chart(results: dict):
    """生成 3 子图折线对比（共享 Y 轴）。

    results = {
        "rebalance_freq": {freq: sharpe, ...},
        "stop_loss":      {threshold: sharpe, ...},
        "mom_window":     {window: sharpe, ...},
    }
    """
    plt = _init_mpl()
    import matplotlib.ticker as ticker

    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5), sharey=True)

    # ── 子图 1: 再平衡频率 ──
    ax = axes[0]
    freq_data = results["rebalance_freq"]
    xs = []
    ys = []
    for f in REBALANCE_FREQS:
        x = 21 if f == "monthly" else f
        xs.append(x)
        ys.append(freq_data[f])

    ax.plot(xs, ys, color=SENSITIVITY_COLORS["rebalance_freq"],
            marker="o", linewidth=2, markersize=6, zorder=3)
    # 最优值高亮
    opt_idx = REBALANCE_FREQS.index(OPTIMAL_FREQ)
    opt_x = xs[opt_idx]
    opt_y = ys[opt_idx]
    ax.scatter([opt_x], [opt_y], color=OPTIMAL_MARKER_COLOR,
               s=150, zorder=5, marker="*",
               label=f"最优 ({FREQ_LABELS[REBALANCE_FREQS[opt_idx]]}日)")

    ax.set_xticks([1, 3, 5, 7, 10, 15, 20, 21])
    ax.set_xticklabels(["1", "3", "5", "7", "10", "15", "20", "月"])
    ax.set_xlabel("再平衡频率（交易日）", fontsize=11)
    ax.set_ylabel("夏普比率", fontsize=11)
    ax.set_title("① 再平衡频率敏感性", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9, loc="lower left")
    ax.grid(True, alpha=0.3)
    # 极差标注
    sharpe_range = max(ys) - min(ys)
    ax.annotate(
        f"极差 {sharpe_range:.4f}",
        xy=(0.95, 0.05), xycoords="axes fraction",
        ha="right", va="bottom",
        fontsize=11, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow",
                  edgecolor=SENSITIVITY_COLORS["rebalance_freq"], alpha=0.9),
    )

    # ── 子图 2: 止损阈值 ──
    ax = axes[1]
    sl_data = results["stop_loss"]
    xs = [t * 100 for t in STOP_LOSS_THRESHOLDS]  # % 显示
    ys = [sl_data[t] for t in STOP_LOSS_THRESHOLDS]

    ax.plot(xs, ys, color=SENSITIVITY_COLORS["stop_loss"],
            marker="o", linewidth=2, markersize=6, zorder=3)
    opt_idx = STOP_LOSS_THRESHOLDS.index(OPTIMAL_STOP)
    ax.scatter([xs[opt_idx]], [ys[opt_idx]], color=OPTIMAL_MARKER_COLOR,
               s=150, zorder=5, marker="*",
               label=f"最优 ({OPTIMAL_STOP:.0%})")

    ax.set_xticks(xs)
    ax.set_xticklabels([f"{t*100:.0f}%" for t in STOP_LOSS_THRESHOLDS])
    ax.set_xlabel("止损阈值", fontsize=11)
    ax.set_title("② 止损阈值敏感性", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9, loc="lower left")
    ax.grid(True, alpha=0.3)
    sharpe_range = max(ys) - min(ys)
    ax.annotate(
        f"极差 {sharpe_range:.4f}",
        xy=(0.95, 0.05), xycoords="axes fraction",
        ha="right", va="bottom",
        fontsize=11, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow",
                  edgecolor=SENSITIVITY_COLORS["stop_loss"], alpha=0.9),
    )

    # ── 子图 3: 动量窗口 N ──
    ax = axes[2]
    mom_data = results["mom_window"]
    xs = MOM_WINDOWS
    ys = [mom_data[w] for w in MOM_WINDOWS]

    ax.plot(xs, ys, color=SENSITIVITY_COLORS["mom_window"],
            marker="o", linewidth=2, markersize=6, zorder=3)
    opt_idx = MOM_WINDOWS.index(OPTIMAL_MOM)
    ax.scatter([xs[opt_idx]], [ys[opt_idx]], color=OPTIMAL_MARKER_COLOR,
               s=150, zorder=5, marker="*",
               label=f"最优 ({OPTIMAL_MOM}日)")

    ax.set_xticks(xs)
    ax.set_xticklabels([str(w) for w in MOM_WINDOWS])
    ax.set_xlabel("动量窗口（交易日）", fontsize=11)
    ax.set_title("③ 动量窗口 N 敏感性", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9, loc="lower left")
    ax.grid(True, alpha=0.3)
    sharpe_range = max(ys) - min(ys)
    ax.annotate(
        f"极差 {sharpe_range:.4f}",
        xy=(0.95, 0.05), xycoords="axes fraction",
        ha="right", va="bottom",
        fontsize=11, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow",
                  edgecolor=SENSITIVITY_COLORS["mom_window"], alpha=0.9),
    )

    # ── 统一 Y 轴格式（共享后只需设置一次） ──
    fig.suptitle(
        "动量排名策略 — 参数敏感性分析\n"
        f"（基准: 频率{OPTIMAL_FREQ}日 / 止损{OPTIMAL_STOP:.0%} / 窗口{OPTIMAL_MOM}日  |  "
        f"佣金 {COMMISSION_RATE:.1%} 最低 ¥{MIN_COMMISSION:.0f}）",
        fontsize=14, fontweight="bold", linespacing=1.4, y=1.02,
    )

    fig.tight_layout()
    output_path = os.path.join(ASSETS_DIR, "param-sensitivity.png")
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✅ {output_path}")

    return output_path


# ══════════════════════════════════════════════════════════════════
# 7. 主流程
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 72)
    print("  参数敏感性分析 — 动量排名策略")
    print(f"  初始资金: ¥{INITIAL_CASH:,.0f}  |  时间: 2021–2025")
    print(f"  佣金: {COMMISSION_RATE:.1%}  最低 ¥{MIN_COMMISSION:.0f}")
    print("=" * 72)

    # ── 构建基准数据面板 ──
    print("\n▶ 获取数据 + 计算指标 (MOM=20)...")
    base_panel = build_panel(mom_period=OPTIMAL_MOM)
    for sym, df in base_panel.items():
        print(f"    {sym} ({SYMBOLS[sym]}): {len(df)} 交易日")

    # 存储所有结果
    all_results = {}

    # ── 扫描 1: 再平衡频率 ──
    print(f"\n▶ 扫描 1/3: 再平衡频率 {REBALANCE_FREQS}")
    print(f"  {'─' * 55}")
    freq_results = sweep_rebalance_freq(base_panel)
    all_results["rebalance_freq"] = freq_results
    print()

    # ── 扫描 2: 止损阈值 ──
    print(f"▶ 扫描 2/3: 止损阈值 {STOP_LOSS_THRESHOLDS}")
    print(f"  {'─' * 55}")
    sl_results = sweep_stop_loss(base_panel)
    all_results["stop_loss"] = sl_results
    print()

    # ── 扫描 3: 动量窗口 N ──
    print(f"▶ 扫描 3/3: 动量窗口 N = {MOM_WINDOWS}")
    print(f"  {'─' * 55}")
    mom_results = sweep_mom_window()
    all_results["mom_window"] = mom_results
    print()

    # ── 汇总表 ──
    print("=" * 72)
    print("  参数敏感性汇总")
    print("=" * 72)

    print("\n  ① 再平衡频率:")
    print(f"  {'频率':>6}  {'夏普比':>10}")
    print(f"  {'─' * 20}")
    for f in REBALANCE_FREQS:
        label = FREQ_LABELS.get(f, f"freq={f}") if not isinstance(f, str) else f
        sharpe = freq_results[f]
        marker = " ◀ 最优" if f == OPTIMAL_FREQ else ""
        print(f"  {str(label).rjust(5)}: {sharpe:>10.4f}{marker}")
    freq_range = max(freq_results.values()) - min(freq_results.values())
    print(f"  {'─' * 20}")
    print(f"  极差: {freq_range:.4f}")

    print("\n  ② 止损阈值:")
    print(f"  {'阈值':>6}  {'夏普比':>10}")
    print(f"  {'─' * 20}")
    for t in STOP_LOSS_THRESHOLDS:
        sharpe = sl_results[t]
        marker = " ◀ 最优" if t == OPTIMAL_STOP else ""
        print(f"  {t:.0%}: {sharpe:>10.4f}{marker}")
    sl_range = max(sl_results.values()) - min(sl_results.values())
    print(f"  {'─' * 20}")
    print(f"  极差: {sl_range:.4f}")

    print("\n  ③ 动量窗口 N:")
    print(f"  {'N(日)':>6}  {'夏普比':>10}")
    print(f"  {'─' * 20}")
    for w in MOM_WINDOWS:
        sharpe = mom_results[w]
        marker = " ◀ 最优" if w == OPTIMAL_MOM else ""
        print(f"  {w:>5d}: {sharpe:>10.4f}{marker}")
    mom_range = max(mom_results.values()) - min(mom_results.values())
    print(f"  {'─' * 20}")
    print(f"  极差: {mom_range:.4f}")

    # ── 生成图表 ──
    print("\n▶ 生成三子图折线对比...")
    output = generate_chart(all_results)
    print(f"\n  ✅ 完成。图表已保存到 {output}")
