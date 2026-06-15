#!/usr/bin/env python3
"""
等权 / 风险平价 / 动量排名 — backtrader 实现。

再平衡频率对比：每日、每5日、每10日、每月。
佣金：0.1%，最低 5 元（A股 ETF 真实费率结构）。

输出：
  1. 控制台指标汇总表（3方法 × 4频率 = 12 组合）
  2. assets/freq-compare-{method}.png  — 每策略一张净值对比图
  3. assets/freq-summary-metrics.png   — 收益率 / 夏普 / 回撤 汇总柱状图
  4. assets/freq-delta-from-daily.png  — 以每日为基准的净值差异图

与数学推导的对应关系：
  - mom, vol, ram 的计算 → 见 momentum-ranking-derivation.md
  - 风险平价逻辑（RC 分解, w ∝ 1/σ）→ 见 risk-parity-derivation.md
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
METHODS = ["equal-weight", "risk-parity", "momentum-rank"]
METHOD_LABELS = {
    "equal-weight": "等权",
    "risk-parity": "风险平价",
    "momentum-rank": "动量排名",
}
METHOD_COLORS = {
    "equal-weight": "#2196F3",
    "risk-parity": "#4CAF50",
    "momentum-rank": "#FF9800",
}
SYMBOL_COLORS = {"510300": "#E53935", "513100": "#1E88E5", "518880": "#FDD835"}
INITIAL_CASH = 100_000.0
MOM_PERIOD = 20

# ── 再平衡频率 ──
REBALANCE_FREQS = [1, 5, 10, "monthly"]
FREQ_LABELS = {1: "每日", 5: "每5日", 10: "每10日", "monthly": "每月"}
FREQ_COLORS = {1: "#7f8c8d", 5: "#e67e22", 10: "#3498db", "monthly": "#2ecc71"}
FREQ_LINESTYLES = {1: ":", 5: "--", 10: "-.", "monthly": "-"}

# ── 佣金参数 ──
COMMISSION_RATE = 0.001      # 0.1%
MIN_COMMISSION = 5.0         # 最低 5 元


# ══════════════════════════════════════════════════════════════════
# 1. 数据准备（纯 pandas）
# ══════════════════════════════════════════════════════════════════

def build_panel() -> dict[str, pd.DataFrame]:
    """获取数据 + 计算 mom, vol, ram，返回 {symbol: DataFrame}。"""
    data = {}
    for symbol in ("510300", "513100", "518880"):
        df = fetch_etf_data(symbol=symbol, start_date="20210101", end_date="20260101")
        # 对数收益率  ← momentum-ranking-derivation §1.3
        df["log_return"] = np.log(df["Close"] / df["Close"].shift(1))
        # N 日动量  ← momentum-ranking-derivation §2.2
        df["mom"] = df["log_return"].rolling(MOM_PERIOD).mean()
        # N 日波动率  ← momentum-ranking-derivation §3.1
        df["vol"] = df["log_return"].rolling(MOM_PERIOD).std(ddof=1)
        # RAM = mom / vol  ← momentum-ranking-derivation §4.1
        df["ram"] = df["mom"] / df["vol"]
        data[symbol] = df
    return data


# ══════════════════════════════════════════════════════════════════
# 2. 数据馈送
# ══════════════════════════════════════════════════════════════════

class ETFData(bt.feeds.PandasData):
    """把 DataFrame 的 mom, vol, ram 列映射为 backtrader lines。"""
    lines = ("mom", "vol", "ram")
    params = (
        ("datetime", None),
        ("open", "Open"), ("high", "High"), ("low", "Low"),
        ("close", "Close"), ("volume", "Volume"),
        ("mom", "mom"), ("vol", "vol"), ("ram", "ram"),
    )


# ══════════════════════════════════════════════════════════════════
# 3. 策略（支持再平衡频率参数）
# ══════════════════════════════════════════════════════════════════

class AssetAllocationStrategy(bt.Strategy):
    """三合一策略，由 params.method 切换分配方式，params.rebalance_freq 控制频率。

    Parameters
    ----------
    method : str
        "equal-weight" | "risk-parity" | "momentum-rank"
    rebalance_freq : int | str
        1=每日, 5=每5日, 10=每10日, "monthly"=每月
    """
    params = (
        ("method", "equal-weight"),
        ("rebalance_freq", 1),
    )

    def __init__(self):
        self.history = []  # [(date_str, portfolio_value, {symbol: weight})]
        self._bars_since_last_rebalance = 0
        self._last_month = None

    def _compute_weights(self) -> dict:
        """根据 method 计算当 bar 的目标权重。"""
        vols, rams = {}, {}
        for d in self.datas:
            vols[d._name] = d.vol[0]
            rams[d._name] = d.ram[0]

        if self.params.method == "equal-weight":
            n = len(SYMBOLS)
            return {name: 1.0 / n for name in SYMBOLS}
        elif self.params.method == "risk-parity":
            return self._risk_parity(vols)
        else:  # momentum-rank
            return self._momentum_rank(rams)

    def next(self):
        freq = self.params.rebalance_freq

        # ── 判断是否再平衡 ──
        if freq == "monthly":
            dt = self.datas[0].datetime.date(0)
            should_rebalance = (
                self._last_month is None or dt.month != self._last_month
            )
            self._last_month = dt.month
        else:
            should_rebalance = (self._bars_since_last_rebalance == 0)

        # ── 计算目标权重（每根 bar 都算，用于记录） ──
        weights = self._compute_weights()

        # ── 记录历史（每天记录，无论是否调仓） ──
        self.history.append((
            self.datas[0].datetime.date(0).isoformat(),
            self.broker.getvalue(),
            dict(weights),
        ))

        # ── 执行再平衡 ──
        if should_rebalance:
            for d in self.datas:
                self.order_target_percent(d, weights.get(d._name, 0.0))

        # ── 更新计数器 ──
        self._bars_since_last_rebalance += 1
        if isinstance(freq, int) and self._bars_since_last_rebalance >= freq:
            self._bars_since_last_rebalance = 0

    @staticmethod
    def _risk_parity(vols: dict) -> dict:
        """w_i ∝ 1/σ_i  ← risk-parity-derivation.md §5.2"""
        clean = {k: v for k, v in vols.items()
                 if v is not None and v > 0 and not np.isnan(v)}
        if not clean:
            n = len(SYMBOLS)
            return {name: 1.0 / n for name in SYMBOLS}
        inv = {k: 1.0 / v for k, v in clean.items()}
        total = sum(inv.values())
        return {k: inv[k] / total for k in inv}

    @staticmethod
    def _momentum_rank(rams: dict) -> dict:
        """w_i = ram_i⁺ / sum(ram⁺)  ← momentum-ranking-derivation.md §7"""
        pos = {k: v for k, v in rams.items()
               if v is not None and v > 0 and not np.isnan(v)}
        if not pos:
            return {}
        total = sum(pos.values())
        return {k: pos[k] / total for k in pos}


# ══════════════════════════════════════════════════════════════════
# 4. 回测运行器
# ══════════════════════════════════════════════════════════════════

def run_one(method: str, freq, data_panel: dict[str, pd.DataFrame]) -> dict:
    """运行单个策略 × 频率组合。返回结果字典。"""
    cerebro = bt.Cerebro()
    for symbol, df in data_panel.items():
        feed = ETFData(dataname=df)
        feed._name = symbol
        cerebro.adddata(feed)

    cerebro.addstrategy(AssetAllocationStrategy, method=method, rebalance_freq=freq)
    cerebro.broker.setcash(INITIAL_CASH)

    # 佣金：0.1%，最低 5 元（A股 ETF 真实费率结构）
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
    }


# ══════════════════════════════════════════════════════════════════
# 5. 可视化 — 频率对比图
# ══════════════════════════════════════════════════════════════════

def _init_mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    plt.rcParams["font.sans-serif"] = ["WenQuanYi Micro Hei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    return plt, mdates


def generate_frequency_charts(results: dict, panel: dict[str, pd.DataFrame]):
    """生成三类图表，保存到 assets/。

    1. 每策略一张净值对比图（3 张）
    2. 汇总柱状图（收益率 / 夏普 / 回撤）
    3. 差异图（以每日为基准的净值差）
    """
    plt, mdates = _init_mpl()
    os.makedirs(ASSETS_DIR, exist_ok=True)

    # ──────────────────────────────────────────────────────
    # Chart 1-3: 频率对比（每策略一张）
    # ──────────────────────────────────────────────────────
    for method in METHODS:
        fig, ax = plt.subplots(figsize=(14, 6))
        ax2 = ax.twinx()
        ax2.set_ylim(0, 1)
        ax2.set_ylabel("现金仓位", fontsize=9, color="gray")
        ax2.tick_params(axis="y", colors="gray")

        for freq in REBALANCE_FREQS:
            recs = results[method][freq]["history"]
            df = pd.DataFrame([{"date": r[0], "value": r[1]} for r in recs])
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")

            line, = ax.plot(
                df.index, df["value"] / INITIAL_CASH * 100,
                color=FREQ_COLORS[freq],
                linestyle=FREQ_LINESTYLES[freq],
                linewidth=1.3,
                label=(
                    f"{FREQ_LABELS[freq]} — "
                    f"¥{results[method][freq]['final_value']:,.0f}  "
                    f"({results[method][freq]['total_return']:+.1%})"
                ),
            )

        ax.axhline(100, color="gray", lw=0.5, ls="--", alpha=0.4)
        ax.set_title(
            f"{METHOD_LABELS[method]} | 不同再平衡频率对比\n"
            f"佣金 {COMMISSION_RATE:.1%} 最低 ¥{MIN_COMMISSION:.0f}",
            fontsize=13, fontweight="bold", linespacing=1.4,
        )
        ax.set_ylabel("净值（起点 = 100）")
        # Legend outside on the right
        box = ax.get_position()
        ax.set_position([box.x0, box.y0, box.width * 0.78, box.height])
        ax.legend(loc="upper left", fontsize=10, bbox_to_anchor=(1.02, 1))
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

        fig.tight_layout()
        fig.savefig(
            os.path.join(ASSETS_DIR, f"freq-compare-{method}.png"),
            dpi=150, bbox_inches="tight",
        )
        plt.close(fig)
        print(f"  ✓ assets/freq-compare-{method}.png")

    # ──────────────────────────────────────────────────────
    # Chart 4: 汇总柱状图 — 收益率 / 夏普 / 回撤
    # ──────────────────────────────────────────────────────
    fig_bar, (ax_fv, ax_sr, ax_dd) = plt.subplots(1, 3, figsize=(16, 5))

    x = np.arange(len(METHODS))
    width = 0.2
    for i, freq in enumerate(REBALANCE_FREQS):
        fv = [results[m][freq]["total_return"] for m in METHODS]
        sr = [results[m][freq]["sharpe"] for m in METHODS]
        dd = [results[m][freq]["max_drawdown"] for m in METHODS]
        offset = (i - 1.5) * width

        ax_fv.bar(x + offset, fv, width, label=FREQ_LABELS[freq],
                  color=FREQ_COLORS[freq], alpha=0.8)
        ax_sr.bar(x + offset, sr, width, label=FREQ_LABELS[freq],
                  color=FREQ_COLORS[freq], alpha=0.8)
        ax_dd.bar(x + offset, dd, width, label=FREQ_LABELS[freq],
                  color=FREQ_COLORS[freq], alpha=0.8)

    for ax, title in [
        (ax_fv, "累计收益率"),
        (ax_sr, "夏普比率"),
        (ax_dd, "最大回撤"),
    ]:
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels([METHOD_LABELS[m] for m in METHODS], fontsize=10)
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3, axis="y")
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))

    fig_bar.suptitle(
        f"再平衡频率 vs 佣金 {COMMISSION_RATE:.1%} 最低 ¥{MIN_COMMISSION:.0f}",
        fontsize=14, fontweight="bold",
    )
    fig_bar.tight_layout()
    fig_bar.savefig(
        os.path.join(ASSETS_DIR, "freq-summary-metrics.png"),
        dpi=150, bbox_inches="tight",
    )
    plt.close(fig_bar)
    print(f"  ✓ assets/freq-summary-metrics.png")

    # ──────────────────────────────────────────────────────
    # Chart 5: 差异图 — 以每日再平衡为基准
    # ──────────────────────────────────────────────────────
    fig_delta, axes = plt.subplots(1, 3, figsize=(18, 5), sharey=True)

    for idx, method in enumerate(METHODS):
        ax = axes[idx]
        baseline = results[method][1]  # daily baseline

        for freq in [5, 10, "monthly"]:
            recs = results[method][freq]["history"]
            df = pd.DataFrame([{"date": r[0], "value": r[1]} for r in recs])
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")

            base_df = pd.DataFrame(
                [{"date": r[0], "value": r[1]} for r in baseline["history"]]
            )
            base_df["date"] = pd.to_datetime(base_df["date"])
            base_df = base_df.set_index("date")

            common = df.index.intersection(base_df.index)
            diff = (df.loc[common, "value"] - base_df.loc[common, "value"]) \
                   / INITIAL_CASH * 100

            ax.plot(
                common, diff,
                color=FREQ_COLORS[freq],
                linestyle=FREQ_LINESTYLES[freq],
                linewidth=0.9,
                label=f"{FREQ_LABELS[freq]} — 每日",
            )
            # 标注终值差异
            final_diff = diff.iloc[-1]
            ax.annotate(
                f"{final_diff:+.2f}pp",
                xy=(common[-1], final_diff),
                xytext=(5, 5), textcoords="offset points",
                fontsize=9, color=FREQ_COLORS[freq], fontweight="bold",
            )

        ax.axhline(0, color="gray", lw=0.5)
        ax.set_title(METHOD_LABELS[method], fontsize=12, fontweight="bold")
        ax.set_ylabel("净值差异（百分点）")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

    fig_delta.suptitle(
        "差异图：不同频率 vs 每日再平衡（净值百分点差）",
        fontsize=14, fontweight="bold",
    )
    fig_delta.tight_layout()
    fig_delta.savefig(
        os.path.join(ASSETS_DIR, "freq-delta-from-daily.png"),
        dpi=150, bbox_inches="tight",
    )
    plt.close(fig_delta)
    print(f"  ✓ assets/freq-delta-from-daily.png")


# ══════════════════════════════════════════════════════════════════
# 6. 主流程
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 72)
    print("  再平衡频率对比研究")
    print(f"  框架: backtrader  |  初始资金: ¥{INITIAL_CASH:,.0f}  |  时间: 2021–2025")
    print(f"  佣金: {COMMISSION_RATE:.1%}  最低 ¥{MIN_COMMISSION:.0f}")
    print(f"  频率: {' / '.join(str(FREQ_LABELS[f]) for f in REBALANCE_FREQS)}")
    print("=" * 72)

    # ── 6a. 数据 ──
    print("\n▶ 获取数据 + 计算指标...")
    panel = build_panel()
    for sym, df in panel.items():
        print(f"    {sym} ({SYMBOLS[sym]}): {len(df)} 交易日")

    # ── 6b. 运行回测（3 方法 × 4 频率 = 12 个） ──
    print("\n▶ 运行回测...")
    results: dict[str, dict] = {}
    for method in METHODS:
        results[method] = {}
        for freq in REBALANCE_FREQS:
            label = f"{METHOD_LABELS[method]} · {FREQ_LABELS[freq]}"
            print(f"  ▶ {label:>14}...", end=" ")
            sys.stdout.flush()
            results[method][freq] = run_one(method, freq, panel)
            r = results[method][freq]
            print(
                f"¥{r['final_value']:>8,.0f}  "
                f"({r['total_return']:+>+7.2%})  "
                f"夏普 {r['sharpe']:.2f}  "
                f"回撤 {r['max_drawdown']:.2%}"
            )

    # ── 6c. 结果汇总表 ──
    print(f"\n{'=' * 95}")
    print("  指标汇总")
    print(f"{'=' * 95}")
    header = (
        f"  {'方法':<14} {'频率':<8} {'最终值':>10} {'累计收益':>10} "
        f"{'年化收益':>10} {'最大回撤':>10} {'夏普':>8}"
    )
    print(header)
    print(f"  {'─' * 75}")
    for method in METHODS:
        for freq in REBALANCE_FREQS:
            r = results[method][freq]
            print(
                f"  {METHOD_LABELS[method]:<14}"
                f" {FREQ_LABELS[freq]:<8}"
                f" ¥{r['final_value']:>8,.0f}"
                f" {r['total_return']:>+9.2%}"
                f" {r['annual_return']:>9.2%}"
                f" {r['max_drawdown']:>9.2%}"
                f" {r['sharpe']:>7.2f}"
            )
        print()

    # ── 6d. 生成图表 ──
    print("▶ 生成图表...")
    generate_frequency_charts(results, panel)

    print(f"\n  ✅ 完成。图表已保存到 assets/ 目录。")
