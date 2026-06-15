#!/usr/bin/env python3
"""
等权 / 风险平价 / 动量排名 — backtrader 实现。

设计：
  数据预处理（pandas 计算出 mom, vol, ram）→ 传给 backtrader
  → 一个策略类，method 参数切换三种分配方式
  → 每日再平衡（order_target_percent）

与数学推导的对应关系：
  - mom, vol, ram 的计算 → 见 momentum-ranking-derivation.md
  - 风险平价逻辑（RC 分解, w ∝ 1/σ）→ 见 risk-parity-derivation.md
  - backtrader 框架概念 → 见 backtrader-intro.md
"""

import backtrader as bt
import pandas as pd
import numpy as np
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../01-data/code"))
from data_fetcher import fetch_etf_data


# ══════════════════════════════════════════════════════════════════
# 常量
# ══════════════════════════════════════════════════════════════════

SYMBOLS = {"510300": "沪深300", "513100": "纳指100", "518880": "黄金"}
START = "2021-01-01"
END = "2025-12-31"
INITIAL_CASH = 100_000.0
MOM_PERIOD = 20  # 动量/波动率窗口


# ══════════════════════════════════════════════════════════════════
# 1. 数据准备（纯 pandas，与 backtrader 无关）
# ══════════════════════════════════════════════════════════════════

def build_panel() -> dict[str, pd.DataFrame]:
    """
    获取三只 ETF 数据，并算出所有指标列。

    返回 {symbol: DataFrame}，列含:
      Open, High, Low, Close, Volume  — 原始行情
      log_return                      — 日度对数收益率 r_t = ln(P_t / P_{t-1})
      mom                             — 20 日对数动量 = avg(r)
      vol                             — 20 日波动率 = std(r, ddof=1)
      ram                             — mom / vol
    """
    data = {}
    for symbol in ("510300", "513100", "518880"):
        df = fetch_etf_data(symbol=symbol, start_date="20210101", end_date="20260101")

        # — 指标计算（对应 momentum-ranking-derivation.md §1-4） —
        # §1.3 对数收益率：r_t = ln(P_t / P_{t-1})
        df["log_return"] = np.log(df["Close"] / df["Close"].shift(1))

        # §2.2 动量：mom = avg(r) over N days
        df["mom"] = df["log_return"].rolling(MOM_PERIOD).mean()

        # §3.1 波动率：vol = std(r, ddof=1) over N days
        df["vol"] = df["log_return"].rolling(MOM_PERIOD).std(ddof=1)

        # §4.1 RAM = mom / vol
        df["ram"] = df["mom"] / df["vol"]

        data[symbol] = df

    return data


# ══════════════════════════════════════════════════════════════════
# 2. backtrader 数据馈送（PandasData with extra lines）
# ══════════════════════════════════════════════════════════════════

class ETFData(bt.feeds.PandasData):
    """
    PandasData 子类：把 DataFrame 里的 mom, vol, ram 列映射为 backtrader lines。
    这样策略代码里就能用 data.mom[0], data.vol[0], data.ram[0] 访问。
    """
    lines = ("mom", "vol", "ram")

    params = (
        ("datetime", None),       # 用 DataFrame.index 做日期
        ("open", "Open"),
        ("high", "High"),
        ("low", "Low"),
        ("close", "Close"),
        ("volume", "Volume"),
        ("mom", "mom"),
        ("vol", "vol"),
        ("ram", "ram"),
    )


# ══════════════════════════════════════════════════════════════════
# 3. 策略
# ══════════════════════════════════════════════════════════════════

class AssetAllocationStrategy(bt.Strategy):
    """
    三合一策略，由 params.method 切换：

      "equal-weight"   — §portfolio-allocation.md: 固定 1/3
      "risk-parity"    — §risk-parity-derivation.md: w ∝ 1/σ
      "momentum-rank"  — §momentum-ranking-derivation.md: ram 排名
    """
    params = (
        ("method", "equal-weight"),
    )

    def __init__(self):
        # 记录每只数据对应的最近权重（用于日志）
        self.target_weights = {}

    def next(self):
        """
        每根 bar 调用一次。收集当前指标 → 算权重 → order_target_percent 调仓。
        """
        # ── 收集当前指标 ──
        vols = {}
        rams = {}
        for d in self.datas:
            name = d._name
            vols[name] = d.vol[0]
            rams[name] = d.ram[0]

        # ── 按策略算权重 ──
        if self.params.method == "equal-weight":
            weights = self._equal_weight()

        elif self.params.method == "risk-parity":
            weights = self._risk_parity(vols)

        elif self.params.method == "momentum-rank":
            weights = self._momentum_rank(rams)

        else:
            raise ValueError(f"未知方法: {self.params.method}")

        # ── 执行调仓 ──
        # order_target_percent 会自动计算当前持有 vs 目标权重的差异，只交易差额
        for d in self.datas:
            name = d._name
            target = weights.get(name, 0.0)
            self.order_target_percent(d, target)

    # ── 三种分配方式 ──────────────────────────────────────────────

    @staticmethod
    def _equal_weight():
        """等权：每只资产 1/n。"""
        n = len(SYMBOLS)  # 3 只
        return {name: 1.0 / n for name in SYMBOLS}

    @staticmethod
    def _risk_parity(vols: dict[str, float]) -> dict[str, float]:
        """
        风险平价：w_i ∝ 1/σ_i。

        对应 risk-parity-derivation.md §5.2-5.3：
          当 ρ=0 时，风险平价条件 w_i σ_i = w_j σ_j 的解
          假设所有 vol > 0（否则给等权）。
        """
        vols_clean = {k: v for k, v in vols.items() if v is not None and v > 0 and not np.isnan(v)}
        if not vols_clean:
            return {name: 1.0 / len(SYMBOLS) for name in SYMBOLS}

        inv = {k: 1.0 / v for k, v in vols_clean.items()}
        total = sum(inv.values())
        return {k: inv[k] / total for k in inv}

    @staticmethod
    def _momentum_rank(rams: dict[str, float]) -> dict[str, float]:
        """
        动量排名：只选 ram > 0 的，按 ram 比例分配权重。

        对应 momentum-ranking-derivation.md §7：
          filter_negative=True → w_i = ram_i⁺ / sum(ram⁺)
          如果所有 ram ≤ 0，返回空权重（全现金）。
        """
        pos = {k: v for k, v in rams.items() if v is not None and v > 0 and not np.isnan(v)}
        if not pos:
            return {}  # 全现金

        total = sum(pos.values())
        return {k: pos[k] / total for k in pos}


# ══════════════════════════════════════════════════════════════════
# 4. 回测运行器
# ══════════════════════════════════════════════════════════════════

def run_backtest(method: str, data_panel: dict[str, pd.DataFrame]) -> bt.Cerebro:
    """
    运行单个策略回测。

    参数:
      method: "equal-weight" | "risk-parity" | "momentum-rank"
      data_panel: build_panel() 的输出

    返回:
      运行完毕的 Cerebro 实例（通过 cerebro.broker.getvalue() 获取结果）
    """
    cerebro = bt.Cerebro()

    # ├─ 添加数据
    for symbol, df in data_panel.items():
        feed = ETFData(dataname=df)
        # 在 cerebro 里给数据命名，方便策略中用 d._name 识别
        feed._name = symbol
        cerebro.adddata(feed)

    # ├─ 添加策略
    cerebro.addstrategy(AssetAllocationStrategy, method=method)

    # ├─ 经纪人设置
    cerebro.broker.setcash(INITIAL_CASH)
    # 设置交易成本（暂未考虑）
    cerebro.broker.setcommission(commission=0.0)

    # ├─ 添加分析器（用于提取指标）
    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.03, annualize=True)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.VWR, _name="vwr")

    # ── 运行 ──
    cerebro.run()

    return cerebro


# ══════════════════════════════════════════════════════════════════
# 5. 主流程
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("  三资产组合分配：等权 vs 风险平价 vs 动量排名")
    print(f"  时间范围: {START} ~ {END}  |  初始资金: {INITIAL_CASH:,.0f} 元")
    print(f"  框架: backtrader")
    print("=" * 70)

    # ── 5a. 数据 ──
    print("\n▶ 获取数据 + 计算指标...")
    panel = build_panel()
    for sym, df in panel.items():
        name = SYMBOLS[sym]
        print(f"    {sym} ({name}): {len(df)} 交易日")
        print(f"      mom 范围: [{df['mom'].min():+.6f}, {df['mom'].max():+.6f}]")
        print(f"      vol 范围: [{df['vol'].min():.4f}, {df['vol'].max():.4f}]")
        print(f"      ram 范围: [{df['ram'].min():+.4f}, {df['ram'].max():+.4f}]")

    # ── 5b. 运行三个策略 ──
    methods = ["equal-weight", "risk-parity", "momentum-rank"]
    results = {}

    for method in methods:
        print(f"\n▶ 运行「{method}」...")
        cerebro = run_backtest(method, panel)
        results[method] = cerebro

        strat = cerebro.runstrats[0][0]
        portfolio_value = cerebro.broker.getvalue()

        ret = strat.analyzers.returns.get_analysis()
        sharpe = strat.analyzers.sharpe.get_analysis()
        dd = strat.analyzers.drawdown.get_analysis()

        print(f"    完成  最终资产: ¥{portfolio_value:,.2f}")
        results[method] = {
            "cerebro": cerebro,
            "final_value": portfolio_value,
            "total_return": (portfolio_value / INITIAL_CASH) - 1,
            "annual_return": ret.get("rnorm100", 0) / 100,
            "sharpe": sharpe.get("sharperatio", 0),
            "max_drawdown": dd.get("max", {}).get("drawdown", 0) / 100,
        }

    # ── 5c. 回测指标对比 ──
    print(f"\n{'='*70}")
    print("  回测指标对比")
    print(f"{'='*70}")

    print(f"\n  {'指标':<14} {'等权':>12} {'风险平价':>12} {'动量排名':>12}")
    print(f"  {'─'*52}")
    for metric in ["total_return", "annual_return", "max_drawdown", "sharpe"]:
        labels = {
            "total_return": "累计收益率",
            "annual_return": "年化收益率",
            "max_drawdown": "最大回撤",
            "sharpe": "夏普比率",
        }
        row = f"  {labels[metric]:<14}"
        for method in methods:
            val = results[method][metric]
            if metric == "sharpe":
                row += f" {val:>12.2f}"
            else:
                row += f" {val:>12.2%}"
        print(row)

    # ── 5d. 最新一日权重 ──
    print(f"\n{'='*70}")
    print("  最新一日权重对比")
    print(f"{'='*70}")

    # 从 cerebro 获取最后一个 bar 的权重
    # 由于 backtrader 不直接暴露目标权重，我们从策略中最后一天的 order 推断
    # 这里用策略的 target_weights 是近似值
    print(f"\n  {'标的':<10} {'等权':>12} {'风险平价':>12} {'动量排名':>12}")
    print(f"  {'─'*48}")
    for sym_name in ["沪深300", "纳指100", "黄金"]:
        row = f"  {sym_name:<10}"
        for method in methods:
            # 从数据的最后一天取指标，用策略方法算出权重
            cerebro = results[method]["cerebro"]
            strat = cerebro.runstrats[0][0]
            # 获取最后一个有效值
            w = 0.0
            # 遍历 datas 找对应 name
            for d in strat.datas:
                name = d._name
                full_name = SYMBOLS[name]
                if full_name == sym_name:
                    if method == "equal-weight":
                        w = 1.0 / 3
                    elif method == "risk-parity":
                        v = d.vol[0]
                        if v and v > 0 and not np.isnan(v):
                            w = (1.0 / v) / sum(1.0 / dd.vol[0] for dd in strat.datas
                                               if dd.vol[0] and dd.vol[0] > 0 and not np.isnan(dd.vol[0]))
                    elif method == "momentum-rank":
                        ram = d.ram[0]
                        if ram and ram > 0 and not np.isnan(ram):
                            pos = {dd._name: dd.ram[0] for dd in strat.datas
                                   if dd.ram[0] and dd.ram[0] > 0 and not np.isnan(dd.ram[0])}
                            total = sum(pos.values())
                            if total > 0:
                                w = ram / total
            row += f" {w:>12.1%}"
        print(row)

    # ── 5e. 动量排名：ram 快照 ──
    print(f"\n▶ 动量排名最新 ram 分数:")
    print(f"  {'标的':<10} {'mom':>12} {'vol':>12} {'ram':>12}")
    print(f"  {'─'*48}")
    cerebro_mr = results["momentum-rank"]["cerebro"]
    strat_mr = cerebro_mr.runstrats[0][0]
    for d in strat_mr.datas:
        name = SYMBOLS[d._name]
        mom = d.mom[0]
        vol = d.vol[0]
        ram = d.ram[0]
        print(f"  {name:<10} {mom:>+12.6f} {vol:>12.4f} {ram:>+12.6f}")

    print(f"\n  ✅ 完成")
