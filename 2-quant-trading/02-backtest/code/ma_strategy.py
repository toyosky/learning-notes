#!/usr/bin/env python3
"""
均线交叉策略模块 - 独立实现（pandas 原生，不依赖回测框架）
基于均线交叉策略笔记（原 open-xquant 策略的独立重实现）
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from typing import Optional
import os


def calculate_sma(data: pd.DataFrame, period: int, column: str = 'Close') -> pd.Series:
    """
    计算简单移动平均线
    
    Args:
        data: DataFrame
        period: 均线周期
        column: 计算均线的列名
    
    Returns:
        Series
    """
    return data[column].rolling(window=period).mean()


def calculate_ema(data: pd.DataFrame, period: int, column: str = 'Close') -> pd.Series:
    """
    计算指数移动平均线
    
    Args:
        data: DataFrame
        period: 均线周期
        column: 计算均线的列名
    
    Returns:
        Series
    """
    return data[column].ewm(span=period, adjust=False).mean()


def ma_crossover_strategy(
    data: pd.DataFrame,
    fast_period: int = 1,
    slow_period: int = 20,
    ma_type: str = 'sma',
    initial_cash: float = 100000,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> dict:
    """
    均线交叉策略回测
    
    Args:
        data: DataFrame，需含 Close 列
        fast_period: 快线周期
        slow_period: 慢线周期
        ma_type: 均线类型，'sma' 或 'ema'
        initial_cash: 初始资金
        start_date: 回测开始日期
        end_date: 回测结束日期
    
    Returns:
        dict，含 result_df, trades, metrics 等
    """
    # 筛选日期范围
    if start_date:
        data = data[data.index >= start_date]
    if end_date:
        data = data[data.index <= end_date]
    
    data = data.copy()
    
    # 计算均线
    if ma_type == 'sma':
        data['MA_fast'] = calculate_sma(data, fast_period)
        data['MA_slow'] = calculate_sma(data, slow_period)
    else:
        data['MA_fast'] = calculate_ema(data, fast_period)
        data['MA_slow'] = calculate_ema(data, slow_period)
    
    # 生成信号：快线上穿慢线 → 买入(1)，快线下穿慢线 → 卖出(-1)
    data['signal'] = 0
    data.loc[data['MA_fast'] > data['MA_slow'], 'signal'] = 1
    data.loc[data['MA_fast'] <= data['MA_slow'], 'signal'] = -1
    
    # 生成交易信号（只在信号变化时交易）
    data['trade_signal'] = data['signal'].diff()
    
    # 回测
    cash = initial_cash
    shares = 0
    position = 0  # 0: 空仓, 1: 持仓
    
    trades = []
    portfolio_values = []
    
    for i, (date, row) in enumerate(data.iterrows()):
        close = row['Close']
        trade_signal = row['trade_signal']
        
        # 买入信号
        if trade_signal == 2 and position == 0:  # 从 -1 到 1
            shares = cash / close
            cash = 0
            position = 1
            trades.append({
                'date': date,
                'action': 'BUY',
                'price': close,
                'shares': shares,
                'value': shares * close
            })
        
        # 卖出信号
        elif trade_signal == -2 and position == 1:  # 从 1 到 -1
            cash = shares * close
            trades.append({
                'date': date,
                'action': 'SELL',
                'price': close,
                'shares': shares,
                'value': cash
            })
            shares = 0
            position = 0
        
        # 记录每日资产
        portfolio_value = cash + shares * close
        portfolio_values.append({
            'date': date,
            'cash': cash,
            'shares': shares,
            'close': close,
            'portfolio_value': portfolio_value,
            'position': position
        })
    
    result_df = pd.DataFrame(portfolio_values)
    result_df.set_index('date', inplace=True)
    
    # 计算指标
    final_value = result_df['portfolio_value'].iloc[-1]
    total_return = (final_value - initial_cash) / initial_cash
    
    # 计算年化收益率
    days = (result_df.index[-1] - result_df.index[0]).days
    annual_return = (1 + total_return) ** (365 / days) - 1 if days > 0 else 0
    
    # 计算最大回撤
    result_df['peak'] = result_df['portfolio_value'].cummax()
    result_df['drawdown'] = (result_df['portfolio_value'] - result_df['peak']) / result_df['peak']
    max_drawdown = result_df['drawdown'].min()
    
    # 计算夏普比率（假设无风险利率 3%）
    daily_returns = result_df['portfolio_value'].pct_change().dropna()
    risk_free_rate = 0.03 / 252  # 日无风险利率
    sharpe_ratio = (daily_returns.mean() - risk_free_rate) / daily_returns.std() * np.sqrt(252) if daily_returns.std() > 0 else 0
    
    # 计算波动率
    annual_volatility = daily_returns.std() * np.sqrt(252)
    
    metrics = {
        'initial_cash': initial_cash,
        'final_value': round(final_value, 2),
        'total_return': round(total_return * 100, 2),
        'annual_return': round(annual_return * 100, 2),
        'max_drawdown': round(max_drawdown * 100, 2),
        'sharpe_ratio': round(sharpe_ratio, 4),
        'annual_volatility': round(annual_volatility * 100, 2),
        'total_trades': len(trades),
        'win_rate': 0,  # 需要计算
        'profit_factor': 0  # 需要计算
    }
    
    # 计算胜率和盈亏比
    if len(trades) >= 2:
        buy_trades = [t for t in trades if t['action'] == 'BUY']
        sell_trades = [t for t in trades if t['action'] == 'SELL']
        
        if len(buy_trades) == len(sell_trades):
            profits = []
            for buy, sell in zip(buy_trades, sell_trades):
                profit = (sell['price'] - buy['price']) / buy['price']
                profits.append(profit)
            
            wins = [p for p in profits if p > 0]
            losses = [p for p in profits if p <= 0]
            
            metrics['win_rate'] = round(len(wins) / len(profits) * 100, 2) if profits else 0
            metrics['profit_factor'] = round(
                abs(sum(wins)) / abs(sum(losses)), 2
            ) if losses and sum(losses) != 0 else float('inf')
    
    return {
        'result_df': result_df,
        'trades': trades,
        'metrics': metrics
    }


def multi_symbol_strategy(
    symbols_data: dict[str, pd.DataFrame],
    fast_period: int = 1,
    slow_period: int = 20,
    ma_type: str = 'sma',
    initial_cash: float = 100000,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> pd.DataFrame:
    """
    多标的均线交叉策略
    
    Args:
        symbols_data: 字典，key 为标的代码，value 为 DataFrame
        fast_period: 快线周期
        slow_period: 慢线周期
        ma_type: 均线类型
        initial_cash: 每个标的的初始资金
        start_date: 回测开始日期
        end_date: 回测结束日期
    
    Returns:
        DataFrame，各标的的回测指标
    """
    results = []
    
    for symbol, data in symbols_data.items():
        try:
            result = ma_crossover_strategy(
                data, fast_period, slow_period, ma_type,
                initial_cash, start_date, end_date
            )
            
            metrics = result['metrics']
            metrics['symbol'] = symbol
            results.append(metrics)
            
        except Exception as e:
            print(f"回测 {symbol} 失败: {e}")
    
    return pd.DataFrame(results)


def plot_strategy_result(
    result: dict,
    title: str = "均线交叉策略回测",
    save_path: Optional[str] = None
):
    """
    绘制策略回测结果图
    
    Args:
        result: ma_crossover_strategy 返回的结果
        title: 图表标题
        save_path: 保存路径
    """
    plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    
    result_df = result['result_df']
    trades = result['trades']
    metrics = result['metrics']
    
    fig, axes = plt.subplots(3, 1, figsize=(12, 12))
    fig.suptitle(title, fontsize=14, fontweight='bold')
    
    # 上图：价格和均线
    ax1 = axes[0]
    ax1.plot(result_df.index, result_df['close'], label='收盘价', linewidth=1, color='#2196F3')
    ax1.plot(result_df.index, result_df['close'].rolling(20).mean(), 
             label='MA20', linewidth=0.8, color='#FF9800', alpha=0.7)
    ax1.plot(result_df.index, result_df['close'].rolling(60).mean(),
             label='MA60', linewidth=0.8, color='#4CAF50', alpha=0.7)
    
    # 标记买卖点
    buy_dates = [t['date'] for t in trades if t['action'] == 'BUY']
    buy_prices = [t['price'] for t in trades if t['action'] == 'BUY']
    sell_dates = [t['date'] for t in trades if t['action'] == 'SELL']
    sell_prices = [t['price'] for t in trades if t['action'] == 'SELL']
    
    ax1.scatter(buy_dates, buy_prices, color='green', marker='^', s=60, 
                label='买入', zorder=5)
    ax1.scatter(sell_dates, sell_prices, color='red', marker='v', s=60,
                label='卖出', zorder=5)
    
    ax1.set_ylabel('价格')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # 中图：资产曲线
    ax2 = axes[1]
    ax2.plot(result_df.index, result_df['portfolio_value'], 
             label='资产总值', linewidth=1.5, color='#2196F3')
    ax2.axhline(y=metrics['initial_cash'], color='gray', linestyle='--', 
                label='初始资金', alpha=0.5)
    ax2.fill_between(result_df.index, metrics['initial_cash'], 
                     result_df['portfolio_value'],
                     where=result_df['portfolio_value'] >= metrics['initial_cash'],
                     color='#4CAF50', alpha=0.2)
    ax2.fill_between(result_df.index, metrics['initial_cash'],
                     result_df['portfolio_value'],
                     where=result_df['portfolio_value'] < metrics['initial_cash'],
                     color='#F44336', alpha=0.2)
    
    ax2.set_ylabel('资产总值')
    ax2.legend(loc='upper left')
    ax2.grid(True, alpha=0.3)
    
    # 下图：回撤
    ax3 = axes[2]
    ax3.fill_between(result_df.index, 0, result_df['drawdown'] * 100,
                     color='#F44336', alpha=0.3)
    ax3.plot(result_df.index, result_df['drawdown'] * 100,
             color='#F44336', linewidth=0.8)
    
    ax3.set_ylabel('回撤 (%)')
    ax3.set_xlabel('日期')
    ax3.grid(True, alpha=0.3)
    
    # 格式化x轴日期
    for ax in axes:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    # 添加指标文本
    metrics_text = (
        f"总收益率: {metrics['total_return']}%  |  "
        f"年化收益率: {metrics['annual_return']}%  |  "
        f"最大回撤: {metrics['max_drawdown']}%  |  "
        f"夏普比率: {metrics['sharpe_ratio']}  |  "
        f"交易次数: {metrics['total_trades']}"
    )
    fig.text(0.5, 0.01, metrics_text, ha='center', fontsize=10)
    
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.05)
    
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"图表已保存到: {save_path}")
    
    plt.close()


def plot_multi_symbol_comparison(
    results_df: pd.DataFrame,
    save_path: Optional[str] = None
):
    """
    绘制多标的表现对比图
    
    Args:
        results_df: multi_symbol_strategy 返回的结果
        save_path: 保存路径
    """
    plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle('均线交叉策略多标的表现对比', fontsize=14, fontweight='bold')
    
    # 排序
    results_df = results_df.sort_values('total_return', ascending=True)
    
    colors = ['#4CAF50' if r >= 0 else '#F44336' for r in results_df['total_return']]
    
    # 左图：总收益率
    ax1 = axes[0]
    bars1 = ax1.barh(results_df['symbol'], results_df['total_return'], color=colors, alpha=0.8)
    ax1.set_xlabel('总收益率 (%)')
    ax1.set_title('总收益率')
    ax1.axvline(x=0, color='black', linewidth=0.5)
    ax1.grid(True, alpha=0.3, axis='x')
    
    for bar, val in zip(bars1, results_df['total_return']):
        ax1.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                 f'{val:.1f}%', ha='left', va='center', fontsize=9)
    
    # 中图：最大回撤
    ax2 = axes[1]
    ax2.barh(results_df['symbol'], results_df['max_drawdown'].abs(), 
             color='#F44336', alpha=0.7)
    ax2.set_xlabel('最大回撤 (%)')
    ax2.set_title('最大回撤')
    ax2.grid(True, alpha=0.3, axis='x')
    
    # 右图：夏普比率
    ax3 = axes[2]
    colors_sharpe = ['#4CAF50' if s >= 0 else '#F44336' for s in results_df['sharpe_ratio']]
    ax3.barh(results_df['symbol'], results_df['sharpe_ratio'], 
             color=colors_sharpe, alpha=0.8)
    ax3.set_xlabel('夏普比率')
    ax3.set_title('夏普比率')
    ax3.axvline(x=0, color='black', linewidth=0.5)
    ax3.grid(True, alpha=0.3, axis='x')
    
    plt.tight_layout()
    
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"图表已保存到: {save_path}")
    
    plt.close()


if __name__ == "__main__":
    # 示例：单标的回测
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../01-data/code'))
    from data_fetcher import fetch_etf_data
    
    # 获取数据
    data = fetch_etf_data(symbol="510300", start_date="20210101")
    
    # 运行策略
    result = ma_crossover_strategy(
        data,
        fast_period=1,
        slow_period=20,
        ma_type='sma',
        initial_cash=100000,
        start_date="2023-01-01"
    )
    
    print("\n回测指标:")
    for key, value in result['metrics'].items():
        print(f"  {key}: {value}")
    
    print(f"\n交易记录: {len(result['trades'])} 笔")
    
    # 绘制图表
    plot_strategy_result(
        result,
        title="510300 均线交叉策略回测",
        save_path="./output/ma_crossover_510300.png"
    )
