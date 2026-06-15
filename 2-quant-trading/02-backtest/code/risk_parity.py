#!/usr/bin/env python3
"""
等权 / 风险平价 / 动量排名 — backtrader 实现。

回测 + 图表生成。
每根 bar 记录组合价值和权重历史，留作可视化使用。

与数学推导的对应关系：
  - mom, vol, ram 的计算 → 见 momentum-ranking-derivation.md
  - 风险平价逻辑（RC 分解, w ∝ 1/σ）→ 见 risk-parity-derivation.md
  - backtrader 框架概念 → 见 backtrader-intro.md
  - 代码逐段讲解 → 见 bt-portfolio-allocation.md
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
# 3. 策略（记录每日历史用于出图）
# ══════════════════════════════════════════════════════════════════

class AssetAllocationStrategy(bt.Strategy):
    """三合一策略，由 params.method 切换三种分配方式。"""
    params = (("method", "equal-weight"),)

    def __init__(self):
        self.history = []  # [(date_str, portfolio_value, {symbol: weight})]

    def next(self):
        vols, rams = {}, {}
        for d in self.datas:
            vols[d._name] = d.vol[0]
            rams[d._name] = d.ram[0]

        if self.params.method == "equal-weight":
            weights = {name: 1.0 / len(SYMBOLS) for name in SYMBOLS}
        elif self.params.method == "risk-parity":
            weights = self._risk_parity(vols)
        else:
            weights = self._momentum_rank(rams)

        # 记录历史
        self.history.append((
            self.datas[0].datetime.date(0).isoformat(),
            self.broker.getvalue(),
            dict(weights),
        ))

        # 调仓
        for d in self.datas:
            self.order_target_percent(d, weights.get(d._name, 0.0))

    @staticmethod
    def _risk_parity(vols):
        """w_i ∝ 1/σ_i  ← risk-parity-derivation.md §5.2"""
        clean = {k: v for k, v in vols.items()
                 if v is not None and v > 0 and not np.isnan(v)}
        if not clean:
            return {name: 1.0 / len(SYMBOLS) for name in SYMBOLS}
        inv = {k: 1.0 / v for k, v in clean.items()}
        total = sum(inv.values())
        return {k: inv[k] / total for k in inv}

    @staticmethod
    def _momentum_rank(rams):
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

def run_one(method: str, data_panel: dict[str, pd.DataFrame]) -> dict:
    """运行单个策略。返回结果字典（含 history 列表）。"""
    cerebro = bt.Cerebro()
    for symbol, df in data_panel.items():
        feed = ETFData(dataname=df)
        feed._name = symbol
        cerebro.adddata(feed)

    cerebro.addstrategy(AssetAllocationStrategy, method=method)
    cerebro.broker.setcash(INITIAL_CASH)
    cerebro.broker.setcommission(commission=0.0)

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
# 5. 可视化
# ══════════════════════════════════════════════════════════════════

def _init_mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    plt.rcParams["font.sans-serif"] = ["WenQuanYi Micro Hei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    return plt, mdates


def generate_charts(results: dict[str, dict], panel: dict[str, pd.DataFrame]):
    """生成 4 张图，保存到 assets/。"""
    plt, mdates = _init_mpl()
    os.makedirs(ASSETS_DIR, exist_ok=True)

    # ── 整理数据 ──
    value_dfs = {}
    weight_dfs = {}
    for m in METHODS:
        recs_v = [{"date": h[0], "value": h[1]} for h in results[m]["history"]]
        value_dfs[m] = pd.DataFrame(recs_v).set_index("date")
        value_dfs[m].index = pd.to_datetime(value_dfs[m].index)

        if m != "equal-weight":
            recs_w = [{"date": h[0], **h[2]} for h in results[m]["history"]]
            df_w = pd.DataFrame(recs_w).set_index("date")
            df_w.index = pd.to_datetime(df_w.index)
            for s in ("510300", "513100", "518880"):
                if s not in df_w.columns:
                    df_w[s] = 0.0
            weight_dfs[m] = df_w[["510300", "513100", "518880"]]

    # ── Chart 1: 累计净值对比 ──────────────────────────────────
    fig1, ax1 = plt.subplots(figsize=(14, 6))
    for m in METHODS:
        df = value_dfs[m]
        ax1.plot(df.index, df["value"] / INITIAL_CASH * 100,
                 color=METHOD_COLORS[m], linewidth=1.2,
                 label=f"{METHOD_LABELS[m]} — ¥{results[m]['final_value']:,.0f}")
    ax1.axhline(100, color="gray", lw=0.5, ls="--", alpha=0.4)
    ax1.set_title("三策略累计净值对比（2021–2025）", fontsize=14, fontweight="bold")
    ax1.set_ylabel("净值（起点 = 100）")
    ax1.legend(loc="upper left", fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
    fig1.tight_layout()
    fig1.savefig(os.path.join(ASSETS_DIR, "strategy-comparison.png"),
                 dpi=150, bbox_inches="tight")
    plt.close(fig1)
    print(f"  ✓ assets/strategy-comparison.png")

    # ── Chart 2: 风险平价权重演变 ────────────────────────────
    if "risk-parity" in weight_dfs:
        fig2, ax2 = plt.subplots(figsize=(14, 5))
        df_w = weight_dfs["risk-parity"]
        ax2.stackplot(df_w.index, df_w.T,
                      labels=[SYMBOLS[c] for c in df_w.columns],
                      colors=[SYMBOL_COLORS[c] for c in df_w.columns],
                      alpha=0.75)
        ax2.set_title("风险平价：每日权重演变", fontsize=14, fontweight="bold")
        ax2.set_ylabel("权重")
        ax2.set_ylim(0, 1)
        ax2.legend(loc="upper left", fontsize=10)
        ax2.grid(True, alpha=0.3, axis="y")
        ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
        fig2.tight_layout()
        fig2.savefig(os.path.join(ASSETS_DIR, "risk-parity-weights.png"),
                     dpi=150, bbox_inches="tight")
        plt.close(fig2)
        print(f"  ✓ assets/risk-parity-weights.png")

    # ── Chart 3: 动量排名权重演变 ────────────────────────────
    if "momentum-rank" in weight_dfs:
        fig3, ax3 = plt.subplots(figsize=(14, 5))
        df_w = weight_dfs["momentum-rank"]
        ax3.stackplot(df_w.index, df_w.T,
                      labels=[SYMBOLS[c] for c in df_w.columns],
                      colors=[SYMBOL_COLORS[c] for c in df_w.columns],
                      alpha=0.75)
        ax3.set_title("动量排名：每日权重演变", fontsize=14, fontweight="bold")
        ax3.set_ylabel("权重")
        ax3.set_ylim(0, 1)
        ax3.legend(loc="upper left", fontsize=10)
        ax3.grid(True, alpha=0.3, axis="y")
        ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45)
        fig3.tight_layout()
        fig3.savefig(os.path.join(ASSETS_DIR, "momentum-rank-weights.png"),
                     dpi=150, bbox_inches="tight")
        plt.close(fig3)
        print(f"  ✓ assets/momentum-rank-weights.png")

    # ── Chart 4: RAM 分数时间序列 ──────────────────────────────
    fig4, ax4 = plt.subplots(figsize=(14, 5))
    for sym, sym_name in SYMBOLS.items():
        df = panel[sym].dropna(subset=["ram"])
        ax4.plot(df.index, df["ram"], label=sym_name,
                 color=SYMBOL_COLORS[sym], linewidth=0.8, alpha=0.8)
    ax4.axhline(0, color="gray", lw=0.5, ls="--", alpha=0.4)
    ax4.set_title("RAM 分数时间序列（20 日滚动）", fontsize=14, fontweight="bold")
    ax4.set_ylabel("RAM")
    ax4.legend(loc="upper left", fontsize=10)
    ax4.grid(True, alpha=0.3)
    ax4.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    ax4.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45)
    fig4.tight_layout()
    fig4.savefig(os.path.join(ASSETS_DIR, "ram-time-series.png"),
                 dpi=150, bbox_inches="tight")
    plt.close(fig4)
    print(f"  ✓ assets/ram-time-series.png")


# ══════════════════════════════════════════════════════════════════
# 6. 主流程
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("  三资产组合分配：等权 vs 风险平价 vs 动量排名")
    print(f"  框架: backtrader  |  初始资金: ¥{INITIAL_CASH:,.0f}")
    print(f"  时间: 2021–2025")
    print("=" * 70)

    # ── 6a. 数据 ──
    print("\n▶ 获取数据 + 计算指标...")
    panel = build_panel()
    for sym, df in panel.items():
        print(f"    {sym} ({SYMBOLS[sym]}): {len(df)} 交易日")

    # ── 6b. 运行回测 ──
    print("\n▶ 运行三个策略...")
    results = {}
    for method in METHODS:
        print(f"  ▶ {METHOD_LABELS[method]}...", end=" ")
        results[method] = run_one(method, panel)
        print(f"¥{results[method]['final_value']:>8,.0f}")

    # ── 6c. 打印结果 ──
    print(f"\n{'='*70}")
    print("  回测指标对比")
    print(f"{'='*70}")
    print(f"\n  {'指标':<14}", end="")
    for m in METHODS:
        print(f" {METHOD_LABELS[m]:>10}", end="")
    print(f"\n  {'─'*48}")
    for key, label, fmt in [
        ("total_return", "累计收益率", "%"),
        ("annual_return", "年化收益率", "%"),
        ("max_drawdown", "最大回撤", "%"),
        ("sharpe", "夏普比率", "f"),
    ]:
        print(f"  {label:<14}", end="")
        for m in METHODS:
            v = results[m][key]
            print(f" {v:>10.2%}" if fmt == "%" else f" {v:>10.2f}", end="")
        print()

    # 最新一日权重
    print(f"\n  {'─'*48}")
    print(f"  {'标的':<10}", end="")
    for m in METHODS:
        print(f" {METHOD_LABELS[m]:>10}", end="")
    print(f"\n  {'─'*48}")
    for sym, sym_name in SYMBOLS.items():
        print(f"  {sym_name:<10}", end="")
        for m in METHODS:
            print(f" {results[m]['history'][-1][2].get(sym, 0):>10.1%}", end="")
        print()

    # RAM 快照
    print(f"\n▶ 动量排名 — 最新 RAM 分数:")
    print(f"  {'标的':<10} {'mom':>12} {'vol':>12} {'ram':>12}")
    print(f"  {'─'*48}")
    for d in results["momentum-rank"]["history"]:
        pass  # RAM 值在 cerebro 里，继续用 cerebro 方法
    # 从 cerebro 获取
    cerebro = bt.Cerebro()
    for symbol, df in panel.items():
        feed = ETFData(dataname=df)
        feed._name = symbol
        cerebro.adddata(feed)
    cerebro.addstrategy(AssetAllocationStrategy, method="momentum-rank")
    cerebro.broker.setcash(INITIAL_CASH)
    cerebro.broker.setcommission(commission=0.0)
    cerebro.run()
    for d in cerebro.runstrats[0][0].datas:
        name = SYMBOLS[d._name]
        print(f"  {name:<10} {d.mom[0]:>+12.6f} {d.vol[0]:>12.4f} {d.ram[0]:>+12.6f}")

    # ── 6d. 生成图表 ──
    print("\n▶ 生成图表...")
    generate_charts(results, panel)

    print(f"\n  ✅ 完成")
