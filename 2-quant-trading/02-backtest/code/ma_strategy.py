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
    
    # 计算胜率和盈亏比（若末次买入未卖出则强制平仓）
    buy_trades = [t for t in trades if t['action'] == 'BUY']
    sell_trades = [t for t in trades if t['action'] == 'SELL']
    
    # 补齐未配对平仓（以最后一天收盘价）
    if len(buy_trades) > len(sell_trades):
        last_row = result_df.iloc[-1]
        if last_row['shares'] > 0:
            sell_trades.append({
                'date': last_row.name,
                'action': 'SELL',
                'price': last_row['close'],
                'shares': buy_trades[-1]['shares'],
                'value': last_row['shares'] * last_row['close']
            })
    
    if buy_trades and sell_trades:
        n_pairs = min(len(buy_trades), len(sell_trades))
        profits = []
        for i in range(n_pairs):
            profit = (sell_trades[i]['price'] - buy_trades[i]['price']) / buy_trades[i]['price']
            profits.append(profit)
        
        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p <= 0]
        
        metrics['win_rate'] = round(len(wins) / len(profits) * 100, 2) if profits else 0
        loss_sum = sum(losses)
        metrics['profit_factor'] = round(
            abs(sum(wins)) / abs(loss_sum), 2
        ) if losses and loss_sum != 0 else float('inf')
    
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


# ═══════════════════════════════════════════════════════
# 月线策略：月首买入 → 月末卖出
# ═══════════════════════════════════════════════════════

def monthly_ma_strategy(
    data: pd.DataFrame,
    ma_period: int = 20,
    ma_type: str = 'sma',
    monthly_amount: float = 100000,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> dict:
    """
    月线均线策略：按月度频率操作
    
    每月第一个交易日：
      - 若收盘价(close) > MA(period) → 全额买入
      - 否则空仓等待
    
    每月最后一个交易日：
      - 若持有 → 全部卖出（无论盈亏）
    
    Args:
        data: DataFrame，需含 Close 列
        ma_period: 均线周期
        ma_type: 'sma' 或 'ema'
        monthly_amount: 每月投入金额（全仓时即总资金）
        start_date: 回测开始日期
        end_date: 回测结束日期
    
    Returns:
        dict，含 result_df, trades, metrics
    """
    if start_date:
        data = data[data.index >= start_date]
    if end_date:
        data = data[data.index <= end_date]
    data = data.copy()
    
    # 计算均线
    if ma_type == 'sma':
        data['MA'] = data['Close'].rolling(ma_period).mean()
    else:
        data['MA'] = data['Close'].ewm(span=ma_period, adjust=False).mean()
    
    # 按月分组
    monthly_first = data.resample('ME').first()
    monthly_last = data.resample('ME').last()
    monthly_dates = monthly_first.index
    
    cash = monthly_amount
    shares = 0.0
    trades = []
    portfolio_values = []
    
    for dt in monthly_dates:
        first_close = monthly_first.loc[dt, 'Close']
        ma_val = monthly_first.loc[dt, 'MA']
        last_close = monthly_last.loc[dt, 'Close']
        
        # 月初：判断信号
        signal = 0
        if pd.notna(ma_val) and first_close > ma_val:
            signal = 1
            if cash > 0:
                shares = cash / first_close
                cash = 0
                trades.append({
                    'date': dt,
                    'action': 'BUY',
                    'price': first_close,
                    'shares': shares,
                    'value': shares * first_close
                })
        
        # 月末：强制卖出
        if shares > 0:
            cash = shares * last_close
            trades.append({
                'date': dt,
                'action': 'SELL',
                'price': last_close,
                'shares': shares,
                'value': cash
            })
            shares = 0
        
        portfolio_value = cash
        portfolio_values.append({
            'date': dt,
            'cash': cash,
            'shares': 0,
            'close': last_close,
            'portfolio_value': portfolio_value,
            'signal': signal,
            'position': 1 if signal else 0
        })
    
    result_df = pd.DataFrame(portfolio_values)
    result_df.set_index('date', inplace=True)
    
    # 计算指标
    final_value = result_df['portfolio_value'].iloc[-1]
    total_return = (final_value - monthly_amount) / monthly_amount
    
    days = (result_df.index[-1] - result_df.index[0]).days
    annual_return = (1 + total_return) ** (365 / days) - 1 if days > 0 else 0
    
    result_df['peak'] = result_df['portfolio_value'].cummax()
    result_df['drawdown'] = (result_df['portfolio_value'] - result_df['peak']) / result_df['peak']
    max_drawdown = result_df['drawdown'].min()
    
    daily_returns = result_df['portfolio_value'].pct_change().dropna()
    rf = 0.03 / 252
    sharpe = (daily_returns.mean() - rf) / daily_returns.std() * np.sqrt(252) if daily_returns.std() > 0 else 0
    ann_vol = daily_returns.std() * np.sqrt(252)
    
    # 计算胜率（每笔买卖为一对）
    buy_trades = [t for t in trades if t['action'] == 'BUY']
    sell_trades = [t for t in trades if t['action'] == 'SELL']
    profits = []
    for buy, sell in zip(buy_trades, sell_trades):
        profits.append((sell['price'] - buy['price']) / buy['price'])
    wins = [p for p in profits if p > 0]
    win_rate = round(len(wins) / len(profits) * 100, 2) if profits else 0
    profit_factor = (abs(sum(wins)) / abs(sum(p for p in profits if p <= 0))
                     ) if any(p <= 0 for p in profits) and sum(p for p in profits if p <= 0) != 0 else float('inf')
    
    return {
        'result_df': result_df,
        'trades': trades,
        'metrics': {
            'initial_cash': monthly_amount,
            'final_value': round(final_value, 2),
            'total_return': round(total_return * 100, 2),
            'annual_return': round(annual_return * 100, 2),
            'max_drawdown': round(max_drawdown * 100, 2),
            'sharpe_ratio': round(sharpe, 4),
            'annual_volatility': round(ann_vol * 100, 2),
            'total_trades': len(trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
        }
    }


# ═══════════════════════════════════════════════════════
# 多策略对比（同一标的）
# ═══════════════════════════════════════════════════════

def compare_strategies_for_symbol(
    data: pd.DataFrame,
    initial_cash: float = 100000,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> pd.DataFrame:
    """
    对同一标的同时运行三个策略并返回对比结果。
    
    策略：
      1. SMA10 日线交叉（价格 vs MA10）
      2. SMA20 日线交叉（价格 vs MA20）
      3. 月线策略（月首信号 → 月末强制卖出）
    """
    strategies = {
        'SMA10 日线交叉': {'fast': 1, 'slow': 10},
        'SMA20 日线交叉': {'fast': 1, 'slow': 20},
    }
    
    rows = []
    # 日线交叉策略
    for name, params in strategies.items():
        res = ma_crossover_strategy(
            data, fast_period=params['fast'], slow_period=params['slow'],
            ma_type='sma', initial_cash=initial_cash,
            start_date=start_date, end_date=end_date
        )
        m = res['metrics']
        rows.append({
            'strategy': name,
            'total_return': m['total_return'],
            'annual_return': m['annual_return'],
            'max_drawdown': m['max_drawdown'],
            'sharpe_ratio': m['sharpe_ratio'],
            'annual_vol': m['annual_volatility'],
            'total_trades': m['total_trades'],
            'win_rate': m['win_rate'],
            'buy_months': len([t for t in res['trades'] if t['action'] == 'BUY']),
        })
    
    # 月线策略（使用ma_period=20作为信号线）
    res = monthly_ma_strategy(
        data, ma_period=20, ma_type='sma',
        monthly_amount=initial_cash,
        start_date=start_date, end_date=end_date
    )
    m = res['metrics']
    rows.append({
        'strategy': '月线策略(MA20)',
        'total_return': m['total_return'],
        'annual_return': m['annual_return'],
        'max_drawdown': m['max_drawdown'],
        'sharpe_ratio': m['sharpe_ratio'],
        'annual_vol': m['annual_volatility'],
        'total_trades': m['total_trades'],
        'win_rate': m['win_rate'],
        'buy_months': len([t for t in res['trades'] if t['action'] == 'BUY']),
    })
    
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════
# 图表：标的 x 策略的收益曲线对比
# ═══════════════════════════════════════════════════════

def plot_ma_strategies_comparison(
    data: pd.DataFrame,
    symbol_name: str = "510300",
    initial_cash: float = 100000,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    save_path: Optional[str] = None
):
    """
    三策略对比图（2行 × 2列）：
      左列：SMA10 / SMA20 日线信号（价格+MA+买卖点）
      右上：月线策略信号（月度柱状）
      右下：三条收益曲线叠加
    """
    plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    
    # 运行三个策略
    res10 = ma_crossover_strategy(data, fast_period=1, slow_period=10, ma_type='sma',
                                   initial_cash=initial_cash, start_date=start_date, end_date=end_date)
    res20 = ma_crossover_strategy(data, fast_period=1, slow_period=20, ma_type='sma',
                                   initial_cash=initial_cash, start_date=start_date, end_date=end_date)
    res_monthly = monthly_ma_strategy(data, ma_period=20, ma_type='sma',
                                       monthly_amount=initial_cash, start_date=start_date, end_date=end_date)
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle(f'{symbol_name} — 均线交叉策略对比', fontsize=14, fontweight='bold')
    
    colors_sma = {'SMA10': '#FF9800', 'SMA20': '#4CAF50'}
    
    for idx, (period, res, label) in enumerate([
        (10, res10, 'SMA10'), (20, res20, 'SMA20')
    ]):
        ax = axes[0][idx]
        rd = res['result_df']
        trades = res['trades']
        
        # 价格
        ax.plot(rd.index, rd['close'], color='#2196F3', linewidth=1, alpha=0.7, label='收盘价')
        # MA
        ma = rd['close'].rolling(period).mean()
        ax.plot(ma.index, ma, color=colors_sma[label], linewidth=0.8, alpha=0.7, label=label)
        
        buy_dates = [t['date'] for t in trades if t['action'] == 'BUY']
        buy_prices = [t['price'] for t in trades if t['action'] == 'BUY']
        sell_dates = [t['date'] for t in trades if t['action'] == 'SELL']
        sell_prices = [t['price'] for t in trades if t['action'] == 'SELL']
        
        ax.scatter(buy_dates, buy_prices, marker='^', color='green', s=30, zorder=5)
        ax.scatter(sell_dates, sell_prices, marker='v', color='red', s=30, zorder=5)
        
        ax.set_title(f'{label} — 日线交叉 ({res["metrics"]["total_trades"]//2}笔交易)')
        ax.set_ylabel('价格')
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, alpha=0.2)
    
    # 右上：月线策略信号
    ax_monthly = axes[1][0]
    rd_m = res_monthly['result_df']
    
    # 价格走势（使用月度收盘价，rd_m的index是月末交易日，可直接用于data）
    ax_monthly.plot(rd_m.index, rd_m['close'], color='#2196F3', linewidth=1, alpha=0.3)
    
    buy_months = [t['date'] for t in res_monthly['trades'] if t['action'] == 'BUY']
    # 用柱状表示买入月份
    for dt in rd_m.index:
        close_val = rd_m.loc[dt, 'close']
        is_buy = dt in buy_months
        color = '#4CAF50' if is_buy else '#F44336'
        ax_monthly.bar(dt, close_val, width=15, color=color, alpha=0.6)
    
    ax_monthly.set_title(f'月线策略(MA20) — 买入{len(buy_months)}/{len(rd_m)}个月')
    ax_monthly.set_ylabel('价格')
    ax_monthly.legend(['收盘价', '买入月', '跳过月'], loc='upper left', fontsize=8)
    ax_monthly.grid(True, alpha=0.2)
    
    # 右下：三条收益曲线叠加
    ax_eq = axes[1][1]
    
    # 日线策略的 daily portfolio_value
    for period, res, label, color in [
        (10, res10, f'SMA10 ({res10["metrics"]["total_return"]:+.2f}%)', '#FF9800'),
        (20, res20, f'SMA20 ({res20["metrics"]["total_return"]:+.2f}%)', '#4CAF50'),
    ]:
        rd = res['result_df']
        eq_pct = (rd['portfolio_value'] / initial_cash - 1) * 100
        ax_eq.plot(rd.index, eq_pct, label=label, color=color, linewidth=1.2)
    
    # 月线策略
    rd_m = res_monthly['result_df']
    eq_m = (rd_m['portfolio_value'] / initial_cash - 1) * 100
    ax_eq.plot(rd_m.index, eq_m, label=f'月线MA20 ({res_monthly["metrics"]["total_return"]:+.2f}%)',
               color='#9C27B0', linewidth=1.5, linestyle='--')
    
    # 基准：买入持有
    if start_date:
        data_range = data[data.index >= start_date]
    else:
        data_range = data
    bh_return = (data_range['Close'] / data_range.iloc[0]['Close'] - 1) * 100
    ax_eq.plot(data_range.index, bh_return,
               label=f'买入持有 ({bh_return.iloc[-1]:+.2f}%)',
               color='#F44336', linewidth=1, linestyle=':', alpha=0.7)
    
    ax_eq.axhline(y=0, color='gray', linewidth=0.5, linestyle='--')
    ax_eq.set_title('各策略收益率曲线对比')
    ax_eq.set_ylabel('累计收益率 (%)')
    ax_eq.legend(loc='upper left', fontsize=8)
    ax_eq.grid(True, alpha=0.2)
    
    for ax_row in axes:
        for ax in ax_row:
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=8)
    
    plt.tight_layout()
    plt.subplots_adjust(top=0.93)
    
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"图表已保存到: {save_path}")
    plt.close()


# ═══════════════════════════════════════════════════════
# 图表：两标的 × 三策略 综合对比
# ═══════════════════════════════════════════════════════

def plot_dual_symbol_comparison(
    results_300: dict,
    results_pa: dict,
    name_300: str = "510300 沪深300ETF",
    name_pa: str = "601318 中国平安",
    save_path: Optional[str] = None
):
    """
    两标的 x 三策略 热力图/柱状图对比
    """
    plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    
    symbols = [name_300, name_pa]
    strategies = ['SMA10', 'SMA20', '月线MA20']
    
    # 提取指标
    data = {'total_return': {}, 'max_drawdown': {}, 'sharpe_ratio': {}, 'win_rate': {}}
    
    def _extract(res, s_name, strat_name):
        m = res['metrics']
        data['total_return'][(s_name, strat_name)] = m['total_return']
        data['max_drawdown'][(s_name, strat_name)] = abs(m['max_drawdown'])
        data['sharpe_ratio'][(s_name, strat_name)] = m['sharpe_ratio']
        data['win_rate'][(s_name, strat_name)] = m['win_rate']
    
    _extract(results_300['sma10'], name_300, 'SMA10')
    _extract(results_300['sma20'], name_300, 'SMA20')
    _extract(results_300['monthly'], name_300, '月线MA20')
    _extract(results_pa['sma10'], name_pa, 'SMA10')
    _extract(results_pa['sma20'], name_pa, 'SMA20')
    _extract(results_pa['monthly'], name_pa, '月线MA20')
    
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.5))
    fig.suptitle('两标的 x 三策略 — 综合对比', fontsize=14, fontweight='bold')
    
    titles = ['总收益率 (%)', '最大回撤 (%)', '夏普比率', '胜率 (%)']
    keys = ['total_return', 'max_drawdown', 'sharpe_ratio', 'win_rate']
    cmaps = ['RdYlGn', 'RdYlGn_r', 'RdYlGn', 'RdYlGn']
    
    for ax, title, key, cmap in zip(axes, titles, keys, cmaps):
        vals = [[data[key].get((s, strat), 0) for strat in strategies] for s in symbols]
        im = ax.imshow(vals, cmap=cmap, aspect='auto', alpha=0.8)
        ax.set_xticks(range(len(strategies)))
        ax.set_xticklabels(strategies, fontsize=9)
        ax.set_yticks(range(len(symbols)))
        ax.set_yticklabels([s.split()[-1] for s in symbols], fontsize=9)
        ax.set_title(title, fontsize=10)
        
        # 标注数值
        for i in range(len(symbols)):
            for j in range(len(strategies)):
                v = data[key].get((symbols[i], strategies[j]), 0)
                ax.text(j, i, f'{v:.1f}', ha='center', va='center', fontsize=9,
                        color='black', fontweight='bold')
        
        plt.colorbar(im, ax=ax, shrink=0.8)
    
    plt.tight_layout()
    plt.subplots_adjust(top=0.82)
    
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"图表已保存到: {save_path}")
    plt.close()


if __name__ == "__main__":
    # ===== 演示：双标的 × 三策略 完整分析 =====
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../01-data/code'))
    from data_fetcher import fetch_etf_data, fetch_stock_data
    import warnings
    warnings.filterwarnings('ignore')
    
    ASSET_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../assets'))
    os.makedirs(ASSET_DIR, exist_ok=True)
    
    # 获取数据
    print("获取数据...")
    data_300 = fetch_etf_data(symbol="510300", start_date="20230101", end_date="20260101")
    data_pa = fetch_stock_data(symbol="601318", start_date="20230101", end_date="20260101")
    
    START, END = "2023-01-01", "2026-01-01"
    CASH = 100000
    
    for name, data, symbol_id in [("510300 沪深300ETF", data_300, "510300"),
                                     ("601318 中国平安", data_pa, "601318")]:
        print(f"\n{'='*50}")
        print(f"【{name}】")
        print(f"{'='*50}")
        
        # SMA10
        res10 = ma_crossover_strategy(data, fast_period=1, slow_period=10, initial_cash=CASH,
                                       start_date=START, end_date=END)
        print(f"\nSMA10 日线交叉:")
        for k, v in res10['metrics'].items():
            print(f"  {k}: {v}")
        
        # SMA20
        res20 = ma_crossover_strategy(data, fast_period=1, slow_period=20, initial_cash=CASH,
                                       start_date=START, end_date=END)
        print(f"\nSMA20 日线交叉:")
        for k, v in res20['metrics'].items():
            print(f"  {k}: {v}")
        
        # 月线
        res_monthly = monthly_ma_strategy(data, ma_period=20, monthly_amount=CASH,
                                          start_date=START, end_date=END)
        print(f"\n月线策略(MA20):")
        for k, v in res_monthly['metrics'].items():
            print(f"  {k}: {v}")
        
        # 三策略对比图（该标的）
        plot_ma_strategies_comparison(data, symbol_name=name, initial_cash=CASH,
                                      start_date=START, end_date=END,
                                      save_path=os.path.join(ASSET_DIR, f'ma-cross-strategies-{symbol_id}.png'))
    
    # 双标的综合对比图
    res_300 = {
        'sma10': ma_crossover_strategy(data_300, fast_period=1, slow_period=10, initial_cash=CASH,
                                        start_date=START, end_date=END),
        'sma20': ma_crossover_strategy(data_300, fast_period=1, slow_period=20, initial_cash=CASH,
                                        start_date=START, end_date=END),
        'monthly': monthly_ma_strategy(data_300, ma_period=20, monthly_amount=CASH,
                                        start_date=START, end_date=END),
    }
    res_pa = {
        'sma10': ma_crossover_strategy(data_pa, fast_period=1, slow_period=10, initial_cash=CASH,
                                        start_date=START, end_date=END),
        'sma20': ma_crossover_strategy(data_pa, fast_period=1, slow_period=20, initial_cash=CASH,
                                        start_date=START, end_date=END),
        'monthly': monthly_ma_strategy(data_pa, ma_period=20, monthly_amount=CASH,
                                        start_date=START, end_date=END),
    }
    
    plot_dual_symbol_comparison(res_300, res_pa, save_path=os.path.join(ASSET_DIR, 'ma-cross-dual-comparison.png'))
    
    print("\n全部完成!")
