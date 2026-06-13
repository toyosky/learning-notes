#!/usr/bin/env python3
"""
DCA 定投回测模块 - 支持均线择时
基于 2.2-dca-backtest.md 笔记
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from typing import Optional
import os


def dca_strategy(
    data: pd.DataFrame,
    monthly_amount: float = 1000,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> pd.DataFrame:
    """
    纯 DCA 定投策略（无择时）
    
    Args:
        data: DataFrame，需含 Close 列，索引为 DatetimeIndex
        monthly_amount: 每月定投金额
        start_date: 回测开始日期
        end_date: 回测结束日期
    
    Returns:
        DataFrame，含 date, total_cost, total_shares, portfolio_value, return 等列
    """
    # 筛选日期范围
    if start_date:
        data = data[data.index >= start_date]
    if end_date:
        data = data[data.index <= end_date]
    
    # 按月采样
    monthly_first = data.resample('ME').first()
    monthly_last = data.resample('ME').last()
    
    rows = []
    total_cost = 0.0
    total_shares = 0.0
    
    for dt in monthly_first.index:
        close = monthly_first.loc[dt, 'Close']
        
        # 买入
        shares = monthly_amount / close
        total_cost += monthly_amount
        total_shares += shares
        
        # 月末估值
        last_close = monthly_last.loc[dt, 'Close']
        portfolio_value = total_shares * last_close
        ret = (portfolio_value - total_cost) / total_cost if total_cost > 0 else 0.0
        
        rows.append({
            'date': dt,
            'total_cost': round(total_cost, 2),
            'total_shares': round(total_shares, 4),
            'portfolio_value': round(portfolio_value, 2),
            'return': round(ret, 6),
            'monthly_return': round((portfolio_value - total_cost) / total_cost, 6) if total_cost > 0 else 0.0
        })
    
    return pd.DataFrame(rows)


def dca_ma_strategy(
    data: pd.DataFrame,
    ma_period: int = 20,
    monthly_amount: float = 1000,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> pd.DataFrame:
    """
    DCA + 均线择时策略
    
    Args:
        data: DataFrame，需含 Close 列，索引为 DatetimeIndex
        ma_period: 均线周期
        monthly_amount: 每月定投金额
        start_date: 回测开始日期
        end_date: 回测结束日期
    
    Returns:
        DataFrame，含 date, total_cost, total_shares, portfolio_value, return, signal 等列
    """
    # 筛选日期范围
    if start_date:
        data = data[data.index >= start_date]
    if end_date:
        data = data[data.index <= end_date]
    
    # 计算均线
    data = data.copy()
    data[f'MA{ma_period}'] = data['Close'].rolling(window=ma_period).mean()
    
    # 按月采样
    monthly_first = data.resample('ME').first()
    monthly_last = data.resample('ME').last()
    
    rows = []
    total_cost = 0.0
    total_shares = 0.0
    buy_count = 0
    
    for dt in monthly_first.index:
        close = monthly_first.loc[dt, 'Close']
        ma_val = monthly_first.loc[dt, f'MA{ma_period}']
        
        # 信号判断：收盘价 > 均线才买入
        signal = 1 if (pd.notna(ma_val) and close > ma_val) else 0
        
        # 买入
        if signal:
            shares = monthly_amount / close
            total_cost += monthly_amount
            total_shares += shares
            buy_count += 1
        
        # 月末估值
        last_close = monthly_last.loc[dt, 'Close']
        portfolio_value = total_shares * last_close
        ret = (portfolio_value - total_cost) / total_cost if total_cost > 0 else 0.0
        
        rows.append({
            'date': dt,
            'total_cost': round(total_cost, 2),
            'total_shares': round(total_shares, 4),
            'portfolio_value': round(portfolio_value, 2),
            'return': round(ret, 6),
            'signal': signal,
            'buy_count': buy_count
        })
    
    return pd.DataFrame(rows)


def benchmark_strategy(
    data: pd.DataFrame,
    monthly_amount: float = 1000,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> pd.DataFrame:
    """
    基准策略：一次性买入（每月用相同成本在首日买入）
    
    Args:
        data: DataFrame，需含 Close 列
        monthly_amount: 每月投入金额
        start_date: 回测开始日期
        end_date: 回测结束日期
    
    Returns:
        DataFrame
    """
    # 筛选日期范围
    if start_date:
        data = data[data.index >= start_date]
    if end_date:
        data = data[data.index <= end_date]
    
    # 按月采样
    monthly_first = data.resample('ME').first()
    monthly_last = data.resample('ME').last()
    first_close = monthly_first.iloc[0]['Close']
    
    rows = []
    total_cost = 0.0
    
    for dt in monthly_first.index:
        total_cost += monthly_amount
        last_close = monthly_last.loc[dt, 'Close']
        
        # 一次性买入：用累计成本在首日买入
        portfolio_value = (total_cost / first_close) * last_close
        ret = (portfolio_value - total_cost) / total_cost if total_cost > 0 else 0.0
        
        rows.append({
            'date': dt,
            'total_cost': round(total_cost, 2),
            'portfolio_value': round(portfolio_value, 2),
            'return': round(ret, 6)
        })
    
    return pd.DataFrame(rows)


def compare_strategies(
    data: pd.DataFrame,
    ma_periods: list[int] = [10, 20, 60],
    monthly_amount: float = 1000,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> pd.DataFrame:
    """
    比较不同策略的表现
    
    Args:
        data: DataFrame
        ma_periods: 均线周期列表
        monthly_amount: 每月定投金额
        start_date: 回测开始日期
        end_date: 回测结束日期
    
    Returns:
        DataFrame，比较结果
    """
    results = []
    
    # 1. 纯 DCA
    dca_result = dca_strategy(data, monthly_amount, start_date, end_date)
    final = dca_result.iloc[-1]
    results.append({
        'strategy': 'DCA（无择时）',
        'total_return': final['return'],
        'total_cost': final['total_cost'],
        'final_value': final['portfolio_value'],
        'buy_months': len(dca_result),
        'total_months': len(dca_result)
    })
    
    # 2. DCA + 不同均线
    for ma_period in ma_periods:
        ma_result = dca_ma_strategy(data, ma_period, monthly_amount, start_date, end_date)
        final = ma_result.iloc[-1]
        results.append({
            'strategy': f'DCA + MA{ma_period}',
            'total_return': final['return'],
            'total_cost': final['total_cost'],
            'final_value': final['portfolio_value'],
            'buy_months': final['buy_count'],
            'total_months': len(ma_result)
        })
    
    # 3. 基准
    benchmark_result = benchmark_strategy(data, monthly_amount, start_date, end_date)
    final = benchmark_result.iloc[-1]
    results.append({
        'strategy': '一次性买入（基准）',
        'total_return': final['return'],
        'total_cost': final['total_cost'],
        'final_value': final['portfolio_value'],
        'buy_months': len(benchmark_result),
        'total_months': len(benchmark_result)
    })
    
    return pd.DataFrame(results)


def plot_strategy_comparison(
    data: pd.DataFrame,
    ma_periods: list[int] = [10, 20, 60],
    monthly_amount: float = 1000,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    save_path: Optional[str] = None
):
    """
    绘制策略对比图
    
    Args:
        data: DataFrame
        ma_periods: 均线周期列表
        monthly_amount: 每月定投金额
        start_date: 回测开始日期
        end_date: 回测结束日期
        save_path: 图表保存路径
    """
    plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    fig.suptitle('DCA 定投策略对比', fontsize=14, fontweight='bold')
    
    # 纯 DCA
    dca_result = dca_strategy(data, monthly_amount, start_date, end_date)
    ax1.plot(dca_result['date'], dca_result['return'] * 100, 
             label='DCA（无择时）', linewidth=2, color='#2196F3')
    
    # DCA + 均线
    colors = ['#FF9800', '#4CAF50', '#9C27B0']
    for i, ma_period in enumerate(ma_periods):
        ma_result = dca_ma_strategy(data, ma_period, monthly_amount, start_date, end_date)
        ax1.plot(ma_result['date'], ma_result['return'] * 100,
                 label=f'DCA + MA{ma_period}', linewidth=1.5, 
                 color=colors[i % len(colors)], alpha=0.8)
    
    # 基准
    benchmark_result = benchmark_strategy(data, monthly_amount, start_date, end_date)
    ax1.plot(benchmark_result['date'], benchmark_result['return'] * 100,
             label='一次性买入（基准）', linewidth=1.5, 
             color='#F44336', linestyle='--')
    
    ax1.set_ylabel('累计收益率 (%)')
    ax1.set_xlabel('日期')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=0, color='black', linewidth=0.5)
    
    # 下图：每月买入信号（以 MA20 为例）
    if 20 in ma_periods:
        ma_result = dca_ma_strategy(data, 20, monthly_amount, start_date, end_date)
        buy_signals = ma_result[ma_result['signal'] == 1]
        skip_signals = ma_result[ma_result['signal'] == 0]
        
        ax2.bar(buy_signals['date'], buy_signals['signal'], 
                width=20, color='#4CAF50', alpha=0.6, label='买入月份')
        ax2.bar(skip_signals['date'], skip_signals['signal'],
                width=20, color='#F44336', alpha=0.3, label='跳过月份')
        
        ax2.set_ylabel('买入信号')
        ax2.set_xlabel('日期')
        ax2.legend(loc='upper left')
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(0, 1.5)
    
    # 格式化x轴日期
    for ax in [ax1, ax2]:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    plt.tight_layout()
    
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"图表已保存到: {save_path}")
    
    plt.close()


if __name__ == "__main__":
    # 示例：加载数据并运行回测
    from data_fetcher import fetch_etf_data
    
    # 获取数据
    data = fetch_etf_data(symbol="510300", start_date="20210101")
    
    # 比较策略
    comparison = compare_strategies(
        data,
        ma_periods=[10, 20, 60],
        monthly_amount=1000,
        start_date="2021-01-01"
    )
    
    print("\n策略对比结果:")
    print(comparison.to_string(index=False))
    
    # 绘制图表
    plot_strategy_comparison(
        data,
        ma_periods=[10, 20, 60],
        monthly_amount=1000,
        start_date="2021-01-01",
        save_path="./output/dca_comparison.png"
    )
