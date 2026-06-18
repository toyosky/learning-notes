#!/usr/bin/env python3
"""
DCA 定投策略可视化 — 生成笔记所需的辅助图表

输出:
  assets/dca-price-buypoints.png   — 价格走势 + 各MA策略买入点
  assets/dca-cost-basis.png       — DCA平均持仓成本 vs 收盘价
  assets/dca-capital-efficiency.png — 累计投入 vs 市值对比
"""

import sys, os, pandas as pd, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../01-data/code'))
sys.path.insert(0, os.path.dirname(__file__))
from data_fetcher import fetch_etf_data
from dca_backtest import dca_strategy, dca_ma_strategy, benchmark_strategy

plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
ASSETS = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../assets'))
os.makedirs(ASSETS, exist_ok=True)


def load_data():
    data = fetch_etf_data(symbol="510300", start_date="20210101", end_date="20260101")
    return data


# ═══════════════════════════════════════════════════════
# 图1: 价格走势 + 各MA策略买入点
# ═══════════════════════════════════════════════════════
def plot_buy_points(data):
    """
    4行子图:
      第1行: 价格 + MA10 + MA10买入点
      第2行: 价格 + MA20 + MA20买入点
      第3行: 价格 + MA60 + MA60买入点
      第4行: 各策略累计买入次数对比
    """
    fig, axes = plt.subplots(4, 1, figsize=(14, 14),
                             gridspec_kw={'height_ratios': [2.5, 2.5, 2.5, 1.5]})
    fig.suptitle('DCA + 均线择时 — 买入点可视化', fontsize=15, fontweight='bold')

    strategies = [(10, '#FF9800'), (20, '#4CAF50'), (60, '#9C27B0')]
    monthly_first = data.resample('ME').first()
    monthly_dates = monthly_first.index

    for idx, (ma_period, color) in enumerate(strategies):
        ax = axes[idx]
        ma_label = f'MA{ma_period}'
        ma_vals = data['Close'].rolling(ma_period).mean()

        # 价格线
        ax.plot(data.index, data['Close'], color='#2196F3', linewidth=1.0,
                alpha=0.7, label='收盘价')
        # 均线
        ax.plot(data.index, ma_vals, color=color, linewidth=0.8,
                alpha=0.8, label=ma_label)

        # 买入点标注（每月第一个交易日）
        ma_monthly = ma_vals.reindex(monthly_dates)
        buy_dates = []
        skip_dates = []
        for dt in monthly_dates:
            if dt in ma_monthly.index and pd.notna(ma_monthly.loc[dt]):
                close_val = monthly_first.loc[dt, 'Close']
                if close_val > ma_monthly.loc[dt]:
                    buy_dates.append(dt)
                else:
                    skip_dates.append(dt)

        if buy_dates:
            buy_prices = [monthly_first.loc[d, 'Close'] for d in buy_dates]
            ax.scatter(buy_dates, buy_prices, marker='^', color='green',
                       s=50, zorder=5, edgecolors='white', linewidth=0.5,
                       label=f'买入 ({len(buy_dates)}次)')
        if skip_dates:
            skip_prices = [monthly_first.loc[d, 'Close'] for d in skip_dates]
            ax.scatter(skip_dates, skip_prices, marker='v', color='red',
                       s=30, zorder=4, alpha=0.5, edgecolors='white', linewidth=0.3,
                       label=f'跳过 ({len(skip_dates)}次)')

        ax.set_ylabel('价格 (元)')
        ax.set_title(f'MA{ma_period} 策略 — 买入 {len(buy_dates)}/60 个月', fontsize=11)
        ax.legend(loc='upper left', ncol=3, fontsize=8)
        ax.grid(True, alpha=0.2)
        ax.set_xlim(data.index[0], data.index[-1])

    # 第4行: 累计买入次数对比柱状图
    ax4 = axes[3]
    ma_names = ['MA10', 'MA20', 'MA60']
    buy_counts = []
    cum_buy = [0, 0, 0]
    for idx, (ma_period, _) in enumerate(strategies):
        ma_vals = data['Close'].rolling(ma_period).mean()
        ma_monthly = ma_vals.reindex(monthly_dates)
        count = 0
        cum = []
        for dt in monthly_dates:
            if dt in ma_monthly.index and pd.notna(ma_monthly.loc[dt]):
                if monthly_first.loc[dt, 'Close'] > ma_monthly.loc[dt]:
                    count += 1
            cum.append(count)
        cum_buy[idx] = cum

    x = range(len(monthly_dates))
    width = 0.25
    colors_bar = ['#FF9800', '#4CAF50', '#9C27B0']
    for i in range(3):
        ax4.bar([xi + i * width for xi in x], cum_buy[i],
                width=width, alpha=0.7, color=colors_bar[i],
                label=ma_names[i])

    ax4.set_ylabel('累计买入次数')
    ax4.set_xlabel('日期')
    ax4.legend(loc='upper left', fontsize=9)
    ax4.grid(True, alpha=0.2)
    ax4.set_xlim(-0.5, len(monthly_dates) - 0.5 + 2 * width)

    for ax in axes:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=8)

    plt.tight_layout()
    path = os.path.join(ASSETS, 'dca-price-buypoints.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'✓ {path}')


# ═══════════════════════════════════════════════════════
# 图2: DCA持仓成本 vs 收盘价
# ═══════════════════════════════════════════════════════
def plot_cost_basis(data):
    """展示DCA如何通过低位买入拉低平均持仓成本"""
    monthly_first = data.resample('ME').first()
    monthly_dates = monthly_first.index

    # 模拟纯DCA
    total_cost = 0.0
    total_shares = 0.0
    avg_costs = []
    for dt in monthly_dates:
        close = monthly_first.loc[dt, 'Close']
        shares = 1000 / close
        total_cost += 1000
        total_shares += shares
        avg_costs.append(total_cost / total_shares)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10),
                                    gridspec_kw={'height_ratios': [2, 1]})
    fig.suptitle('DCA 定投 — 持仓成本与价格走势', fontsize=15, fontweight='bold')

    # 上图: 价格 vs 平均成本
    ax1.plot(data.index, data['Close'], color='#2196F3', linewidth=1.2,
             alpha=0.7, label='收盘价')
    ax1.plot(monthly_dates, avg_costs, color='#FF5722', linewidth=2.0,
             linestyle='--', label='DCA平均持仓成本', marker='o', markersize=3)

    # 填充成本 vs 价格的差额
    ax1.fill_between(monthly_dates, avg_costs,
                     [monthly_first.loc[d, 'Close'] for d in monthly_dates],
                     where=[monthly_first.loc[d, 'Close'] > avg_costs[i]
                            for i, d in enumerate(monthly_dates)],
                     color='green', alpha=0.1, label='盈利区域')
    ax1.fill_between(monthly_dates, avg_costs,
                     [monthly_first.loc[d, 'Close'] for d in monthly_dates],
                     where=[monthly_first.loc[d, 'Close'] <= avg_costs[i]
                            for i, d in enumerate(monthly_dates)],
                     color='red', alpha=0.1, label='亏损区域')

    ax1.set_ylabel('价格 (元)')
    ax1.legend(loc='upper left', fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(data.index[0], data.index[-1])

    # 下图: 累计投入 vs 市值
    dca_result = dca_strategy(data, monthly_amount=1000, start_date='2021-01-01')
    ax2.fill_between(dca_result['date'], 0, dca_result['total_cost'],
                      color='#FF9800', alpha=0.3, label='累计投入')
    ax2.plot(dca_result['date'], dca_result['portfolio_value'], color='#4CAF50',
             linewidth=2, label='市值')
    ax2.fill_between(dca_result['date'], dca_result['total_cost'],
                     dca_result['portfolio_value'],
                     where=dca_result['portfolio_value'] >= dca_result['total_cost'],
                     color='green', alpha=0.15, label='盈利')
    ax2.fill_between(dca_result['date'], dca_result['total_cost'],
                     dca_result['portfolio_value'],
                     where=dca_result['portfolio_value'] < dca_result['total_cost'],
                     color='red', alpha=0.15, label='亏损')
    ax2.set_ylabel('金额 (元)')
    ax2.legend(loc='upper left', fontsize=10)
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(data.index[0], data.index[-1])

    for ax in [ax1, ax2]:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

    plt.tight_layout()
    path = os.path.join(ASSETS, 'dca-cost-basis.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'✓ {path}')


# ═══════════════════════════════════════════════════════
# 图3: 各策略累计收益率曲线 + 关键事件标注
# ═══════════════════════════════════════════════════════
def plot_enhanced_comparison(data):
    """
    增强版收益率对比:
    - 标注关键市场阶段
    - 展示不同均线周期的信号差异
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10),
                                    gridspec_kw={'height_ratios': [2, 1.5]})
    fig.suptitle('DCA 定投策略 — 增强对比', fontsize=15, fontweight='bold')

    # ── 上图: 收益率曲线（复用原有逻辑但补充标注）──
    dca_res = dca_strategy(data, monthly_amount=1000, start_date='2021-01-01')
    ax1.plot(dca_res['date'], dca_res['return'] * 100, label='DCA（无择时）',
             linewidth=2, color='#2196F3')

    styles = [(10, '#FF9800'), (20, '#4CAF50'), (60, '#9C27B0')]
    for ma_period, color in styles:
        ma_res = dca_ma_strategy(data, ma_period, 1000, start_date='2021-01-01')
        ax1.plot(ma_res['date'], ma_res['return'] * 100,
                 label=f'DCA + MA{ma_period}', linewidth=1.5, color=color, alpha=0.8)

    bm_res = benchmark_strategy(data, 1000, start_date='2021-01-01')
    ax1.plot(bm_res['date'], bm_res['return'] * 100,
             label='一次性买入（基准）', linewidth=1.5, color='#F44336', linestyle='--')

    # 市场阶段标注
    phases = [
        ('2021-01', '2021-12', '震荡', 0.92),
        ('2022-01', '2022-10', '下跌', 0.85),
        ('2022-11', '2024-09', '磨底', 0.98),
        ('2024-10', '2025-12', '反弹', 0.92),
    ]
    y_min, y_max = ax1.get_ylim()
    for start_m, end_m, label, y_pos in phases:
        ax1.axvspan(pd.Timestamp(start_m), pd.Timestamp(end_m),
                    alpha=0.08, color='gray')
        ax1.text(pd.Timestamp(start_m) + (pd.Timestamp(end_m) - pd.Timestamp(start_m)) / 2,
                 y_min + (y_max - y_min) * y_pos, label,
                 ha='center', fontsize=10, color='gray', style='italic')

    ax1.set_ylabel('累计收益率 (%)')
    ax1.legend(loc='upper left', fontsize=9, ncol=2)
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=0, color='black', linewidth=0.5)
    ax1.set_xlim(data.index[0], data.index[-1])

    # ── 下图: 各策略每月买入金额对比（堆叠条形）──
    monthly_first = data.resample('ME').first()
    monthly_dates = monthly_first.index

    # 收集各策略的每月买入信号
    buy_signals = {}
    for ma_period, _ in styles:
        ma_vals = data['Close'].rolling(ma_period).mean()
        ma_monthly = ma_vals.reindex(monthly_dates)
        signals = []
        for dt in monthly_dates:
            if dt in ma_monthly.index and pd.notna(ma_monthly.loc[dt]):
                signals.append(1 if monthly_first.loc[dt, 'Close'] > ma_monthly.loc[dt] else 0)
            else:
                signals.append(0)
        buy_signals[f'MA{ma_period}'] = signals

    x = range(len(monthly_dates))
    ax2.bar(x, [1] * len(monthly_dates), width=0.6, color='#E0E0E0',
            alpha=0.5, label='DCA无择时（每月都买）', zorder=1)

    offsets = {'MA10': -0.3, 'MA20': 0, 'MA60': 0.3}
    colors_dot = {'MA10': '#FF9800', 'MA20': '#4CAF50', 'MA60': '#9C27B0'}
    for name, offset in offsets.items():
        buy_x = [xi + offset for xi in x if buy_signals[name][xi] == 1]
        skip_x = [xi + offset for xi in x if buy_signals[name][xi] == 0]
        ax2.scatter(buy_x, [1] * len(buy_x), marker='o', s=12,
                    color=colors_dot[name], alpha=0.8, zorder=3)
        ax2.scatter(skip_x, [0.5] * len(skip_x), marker='x', s=8,
                    color=colors_dot[name], alpha=0.3, zorder=2)

    ax2.set_ylabel('买入 / 跳过')
    ax2.set_xlabel('月份')
    ax2.set_ylim(0, 1.8)
    ax2.set_yticks([0.5, 1])
    ax2.set_yticklabels(['跳过', '买入'])
    ax2.legend(loc='upper left', fontsize=8, ncol=2)
    ax2.grid(True, alpha=0.2, axis='x')

    ax2.set_xticks(range(0, len(monthly_dates), 6))
    ax2.set_xticklabels([d.strftime('%Y-%m') for d in monthly_dates[::6]], rotation=45)

    plt.tight_layout()
    path = os.path.join(ASSETS, 'dca-enhanced-comparison.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'✓ {path}')


# ═══════════════════════════════════════════════════════
# 图4: 各策略买入价格分布
# ═══════════════════════════════════════════════════════
def plot_price_distribution(data):
    """展示各策略分别在什么价格区间买入"""
    monthly_first = data.resample('ME').first()
    monthly_dates = monthly_first.index

    fig, ax = plt.subplots(figsize=(14, 6))
    fig.suptitle('各策略买入价格分布', fontsize=15, fontweight='bold')

    # 价格走势（背景）
    ax.plot(data.index, data['Close'], color='#2196F3', linewidth=1.0, alpha=0.3)

    strategies = [(None, '#2196F3', 'DCA'), (10, '#FF9800', 'MA10'),
                  (20, '#4CAF50', 'MA20'), (60, '#9C27B0', 'MA60')]

    for idx, (ma_period, color, label) in enumerate(strategies):
        y_val = 6.5 - idx * 0.5
        buy_dates = []
        for dt in monthly_dates:
            close = monthly_first.loc[dt, 'Close']
            if ma_period is None:
                buy_dates.append(dt)
            else:
                ma_vals = data['Close'].rolling(ma_period).mean()
                if dt in ma_vals.index and pd.notna(ma_vals.loc[dt]):
                    if close > ma_vals.loc[dt]:
                        buy_dates.append(dt)
        buy_prices = [monthly_first.loc[d, 'Close'] for d in buy_dates]
        ax.scatter(buy_dates, [y_val] * len(buy_dates), marker='o', s=12,
                   color=color, alpha=0.6, label=f'{label} ({len(buy_dates)}次)')

    ax.set_ylabel('策略')
    ax.set_xlabel('日期')
    ax.set_ylim(5.3, 6.8)
    ax.set_yticks([6.5, 6.0, 5.5, 5.0])
    ax.set_yticklabels(['DCA（60次）', 'MA10（30次）', 'MA20（24次）', 'MA60（26次）'])
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(True, alpha=0.2)
    ax.set_xlim(data.index[0], data.index[-1])

    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

    plt.tight_layout()
    path = os.path.join(ASSETS, 'dca-price-distribution.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'✓ {path}')


if __name__ == '__main__':
    print('加载数据...')
    data = load_data()
    print(f'数据: {data.index[0].date()} ~ {data.index[-1].date()} ({len(data)} 条)')

    print('\n生成买入点可视化...')
    plot_buy_points(data)

    print('\n生成持仓成本 vs 价格走势...')
    plot_cost_basis(data)

    print('\n生成增强对比图...')
    plot_enhanced_comparison(data)

    print('\n生成买入价格分布...')
    plot_price_distribution(data)

    print('\n全部完成!')
