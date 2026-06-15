#!/usr/bin/env python3
"""
Risk Parity / Momentum Ranking / Equal Weight — 三资产组合分配对比。

Pipeline:
  Universe(510300, 513100, 518880)
    → Indicators: RollingVolatility / Momentum / Ratio(ram=mom/vol)
    → Signal: Threshold(close > 0) → 始终持仓
    → Optimizer: 三个策略仅此不同

一个 COMMON 字典 + 一个信号（注册全部指标），三个策略只换 portfolio= 一行：
  - EqualWeightOptimizer()                          — 固定 1/3
  - RiskParityOptimizer(volatility_col="vol")        — 波动率倒数
  - TopNRankingOptimizer(score_col="ram", n=3, ...) — 动量排名
"""

import pandas as pd
import numpy as np
import akshare as ak

from oxq.core import Engine, Strategy
from oxq.portfolio.optimizers import (
    EqualWeightOptimizer,
    RiskParityOptimizer,
    TopNRankingOptimizer,
)
from oxq.signals import Threshold
from oxq.indicators import RollingVolatility, Momentum, Ratio
from oxq.universe import StaticUniverse
from oxq.trade import SimBroker

# ── 常量 ──────────────────────────────────────────────────────────
SYMBOLS = {"510300": "沪深300", "513100": "纳指100", "518880": "黄金"}
START = "2021-01-01"
END = "2025-12-31"
INITIAL_CASH = 100_000.0
TZ = "Asia/Shanghai"
MOMENTUM_PERIOD = 20
VOL_PERIOD = 20


# ══════════════════════════════════════════════════════════════════
# 1. 数据提供者
# ══════════════════════════════════════════════════════════════════

class DataFrameMarketDataProvider:
    """基于内存 DataFrame 的 MarketDataProvider，免去 parquet 依赖。"""
    def __init__(self, data: dict[str, pd.DataFrame]) -> None:
        self._data = data

    def get_bars(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        df = self._data[symbol]
        return df.loc[start:end].copy()

    def get_latest(self, symbol: str) -> pd.Series:
        return self._data[symbol].iloc[-1]


def fetch_data() -> dict[str, pd.DataFrame]:
    """通过 data_fetcher 获取三只 ETF 的日线数据（自动尝试东财 → 回退新浪）。
    
    返回 {symbol: DataFrame}，列名为 oxq 要求的 lowercase open/close/high/low/volume。
    """
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../01-data/code'))
    from data_fetcher import fetch_etf_data
    
    data: dict[str, pd.DataFrame] = {}
    for symbol in ("510300", "513100", "518880"):
        df = fetch_etf_data(symbol=symbol, start_date="20210101", end_date="20260101")
        df.index = df.index.tz_localize(TZ)
        df = df.rename(columns={
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume",
        })
        data[symbol] = df

    return data


# ══════════════════════════════════════════════════════════════════
# 2. 策略构造
# ══════════════════════════════════════════════════════════════════

def build_strategies(universe):
    """构建三个策略，仅 portfolio 参数不同。

    指标依赖链（顺序敏感）：
      mom = Momentum(close, 20)           — 20日动量
      vol = RollingVolatility(close, 20)  — 20日波动率
      ram = Ratio(mom / vol)              — 动量/波动率（排序分数）
    三个指标注册在同一个信号上，Indicators 按插入顺序驱动计算。
    """
    signal = Threshold()
    signal.required_indicators = {
        "mom": (Momentum(), {"column": "close", "period": MOMENTUM_PERIOD}),
        "vol": (RollingVolatility(), {"column": "close", "period": VOL_PERIOD}),
        "ram": (Ratio(), {"col_a": "mom", "col_b": "vol"}),
    }

    # 公共配置：三个策略完全共享
    COMMON = dict(
        universe=universe,
        signals={
            "signal": (
                signal,
                {"column": "close", "threshold": 0, "relationship": "gt"},
            )
        },
    )

    strategies = {
        "equal-weight": Strategy(
            name="equal-weight",
            **COMMON,
            portfolio=EqualWeightOptimizer(),
        ),
        "risk-parity": Strategy(
            name="risk-parity",
            **COMMON,
            portfolio=RiskParityOptimizer(volatility_col="vol"),
        ),
        "momentum-rank": Strategy(
            name="momentum-rank",
            **COMMON,
            portfolio=TopNRankingOptimizer(
                score_col="ram",
                n=3,
                filter_negative=True,
            ),
        ),
    }
    return strategies


# ══════════════════════════════════════════════════════════════════
# 3. 回测
# ══════════════════════════════════════════════════════════════════

def run_backtest(strategy, provider) -> "RunResult":
    """运行单个策略回测，返回 RunResult。"""
    engine = Engine()
    return engine.run(
        strategy=strategy,
        market=provider,
        broker=SimBroker(),
        start=START,
        end=END,
        initial_cash=INITIAL_CASH,
    )


# ══════════════════════════════════════════════════════════════════
# 4. 回测指标
# ══════════════════════════════════════════════════════════════════

def print_metrics(name: str, result) -> None:
    """打印策略回测指标。"""
    ret = result.total_return()
    ann_ret = result.annualized_return()
    vol = result.annualized_volatility()
    sharpe = result.sharpe_ratio()
    mdd = result.max_drawdown()
    calmar = result.calmar_ratio()
    print(f"\n  {'─'*35}")
    print(f"  {name}")
    print(f"  {'─'*35}")
    print(f"    累计收益率:      {ret:>+8.2%}")
    print(f"    年化收益率:      {ann_ret:>+8.2%}")
    print(f"    年化波动率:      {vol:>8.2%}")
    print(f"    夏普比率:        {sharpe:>8.2f}")
    print(f"    最大回撤:        {mdd:>8.2%}")
    print(f"    卡尔玛比率:      {calmar:>8.2f}")


def print_weight_comparison(all_weights: dict[str, dict]) -> None:
    """打印最新一日权重对比 + 10 万元换算。"""
    strategies = list(all_weights)
    n = len(strategies)
    # 动态表头 — 每列宽 12
    col_w = 12
    hdr = f"  {'标的':<10}"
    sep = f"  {'─'*10}"
    for s in strategies:
        hdr += f" {s:>{col_w}}"
        sep += f" {'─'*col_w}"
    hdr += f" {'等权(¥)':>{col_w}}"
    sep += f" {'─'*col_w}"
    print(f"\n  {sep}")
    print(f"  {hdr}")
    print(f"  {sep}")
    for sym in ["510300", "513100", "518880"]:
        name = SYMBOLS[sym]
        row = f"  {name:<10}"
        ew_val = all_weights[strategies[0]].get(sym, 0) if strategies else 0
        for s in strategies:
            w = all_weights[s].get(sym, 0)
            row += f" {w:>{col_w}.1%}"
        row += f" {ew_val * INITIAL_CASH:>{col_w},.0f}"
        print(row)
    print(f"  {sep}")


# ══════════════════════════════════════════════════════════════════
# 5. 主流程
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("  三资产组合分配：等权 vs 风险平价 vs 动量排名")
    print(f"  时间范围: {START} ~ {END}  |  初始资金: {INITIAL_CASH:,.0f} 元")
    print("=" * 70)

    # -- 5a. 数据 ---------------------------------------------------
    print("\n▶ 获取数据 (akshare)...")
    raw_data = fetch_data()
    for sym, df in raw_data.items():
        name = SYMBOLS[sym]
        print(f"    {sym} ({name}): {len(df)} 个交易日")

    provider = DataFrameMarketDataProvider(raw_data)
    universe = StaticUniverse(symbols=list(SYMBOLS), name="global-macro-etf")

    # -- 5b. 策略 ---------------------------------------------------
    strategies = build_strategies(universe)

    # -- 5c. 回测 ---------------------------------------------------
    results = {}
    for name, strategy in strategies.items():
        print(f"\n▶ 运行「{name}」策略...")
        results[name] = run_backtest(strategy, provider)
        print(f"   完成")

    # -- 5d. 回测指标 ------------------------------------------------
    print(f"\n{'='*70}")
    print("  回测指标对比")
    print(f"{'='*70}")
    for name in strategies:
        print_metrics(name, results[name])

    # -- 5e. 最新一日权重对比 -----------------------------------------
    print(f"\n{'='*70}")
    print("  最新一日权重对比")
    print(f"{'='*70}")

    all_weights = {
        name: results[name].snapshots[-1].target_weights
        for name in strategies
    }
    print_weight_comparison(all_weights)

    # -- 5f. 各策略权重的时间序列（年度末采样） -------------------------
    print(f"\n▶ 各策略权重年度变化:")

    for name in ["risk-parity", "momentum-rank"]:
        wts = results[name].weights_df()
        monthly = wts.resample("YE").last()
        print(f"\n  ── {name} ──")
        print(f"  {'日期':<14} {'沪深300':>8} {'纳指100':>10} {'黄金':>8}")
        print(f"  {'─'*44}")
        for dt, row in monthly.iterrows():
            dt_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
            print(f"  {dt_str:<14} {row.get('510300', 0):>8.1%} {row.get('513100', 0):>10.1%} {row.get('518880', 0):>8.1%}")

    # -- 5g. 动量排名：ram 分数快照 -----------------------------------
    print(f"\n▶ 动量排名最新 ram 分数（ram = mom / vol）:")
    mktdata = results["momentum-rank"].mktdata
    print(f"\n  {'标的':<10} {'mom':>10} {'vol':>10} {'ram':>10} {'持仓':>6}")
    print(f"  {'─'*48}")
    for sym in ["510300", "513100", "518880"]:
        name = SYMBOLS[sym]
        df = mktdata[sym]
        mom = float(df["mom"].iloc[-1])
        vol = float(df["vol"].iloc[-1])
        ram = float(df["ram"].iloc[-1])
        # 检查该标的是否在最后一日的持仓中
        last_snapshot = results["momentum-rank"].snapshots[-1]
        held = "✓" if sym in last_snapshot.positions else "✗"
        print(f"  {name:<10} {mom:>+10.6f} {vol:>10.4f} {ram:>+10.6f} {held:>6}")

    # -- 5h. 动量排名 vs 风险平价：持仓天数对比 -----------------------
    print(f"\n▶ 持仓天数对比:")
    for name in ["risk-parity", "momentum-rank"]:
        wts = results[name].weights_df()
        n_held = (wts.drop(columns="CASH", errors="ignore") > 0).sum(axis=1)
        print(f"  {name:<20}: 平均持仓 {n_held.mean():.1f} 个标的 / 最大 {n_held.max():.0f} / 最小 {n_held.min():.0f}")

    print(f"\n  ✅ 完成")
