#!/usr/bin/env python3
"""生成量化交易笔记所需的图表"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import akshare as ak
import os

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

OUTPUT_DIR = '/root/obsidian-vault/2-quant-trading'


def get_data():
    """使用 akshare（东财源）获取 510300（沪深300ETF）数据"""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../01-data/code'))
    from data_fetcher import fetch_etf_data
    return fetch_etf_data(symbol="510300", start_date="20210101")


def plot_stock_price(df):
    """绘制股价走势图"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), 
                                     gridspec_kw={'height_ratios': [3, 1]})
    fig.suptitle('510300 沪深300ETF 股价走势', fontsize=14, fontweight='bold')
    
    # 上图：收盘价 + 均线
    ax1.plot(df.index, df['Close'], color='#2196F3', linewidth=1.2, label='收盘价')
    ax1.plot(df.index, df['Close'].rolling(20).mean(), color='#FF9800', 
             linewidth=0.8, alpha=0.7, label='MA20')
    ax1.plot(df.index, df['Close'].rolling(60).mean(), color='#4CAF50', 
             linewidth=0.8, alpha=0.7, label='MA60')
    ax1.fill_between(df.index, df['Close'].min() * 0.95, df['Close'], 
                     alpha=0.1, color='#2196F3')
    ax1.set_ylabel('价格 (元)')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(df.index[0], df.index[-1])
    
    # 下图：成交量
    colors = ['#4CAF50' if df['Close'].iloc[i] >= df['Close'].iloc[i-1] 
              else '#F44336' for i in range(1, len(df))]
    colors.insert(0, '#4CAF50')
    ax2.bar(df.index, df['Volume'] / 1e6, color=colors, alpha=0.6, width=1)
    ax2.set_ylabel('成交量 (百万股)')
    ax2.set_xlabel('日期')
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(df.index[0], df.index[-1])
    
    # 格式化x轴日期
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, 'stock-price-510300.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'已保存: {output_path}')


def plot_ma_signals(df):
    """绘制均线信号图"""
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.suptitle('510300 均线交叉信号', fontsize=14, fontweight='bold')
    
    # 计算均线
    ma10 = df['Close'].rolling(10).mean()
    ma20 = df['Close'].rolling(20).mean()
    ma60 = df['Close'].rolling(60).mean()
    
    ax.plot(df.index, df['Close'], color='#2196F3', linewidth=1, label='收盘价', alpha=0.7)
    ax.plot(df.index, ma10, color='#FF9800', linewidth=0.8, label='MA10')
    ax.plot(df.index, ma20, color='#4CAF50', linewidth=0.8, label='MA20')
    ax.plot(df.index, ma60, color='#9C27B0', linewidth=0.8, label='MA60')
    
    # 标记金叉/死叉（以MA20为例）
    for i in range(1, len(df)):
        if ma20.iloc[i-1] is not None and ma20.iloc[i] is not None:
            if df['Close'].iloc[i-1] < ma20.iloc[i-1] and df['Close'].iloc[i] > ma20.iloc[i]:
                ax.scatter(df.index[i], df['Close'].iloc[i], color='green', 
                          marker='^', s=60, zorder=5)
            elif df['Close'].iloc[i-1] > ma20.iloc[i-1] and df['Close'].iloc[i] < ma20.iloc[i]:
                ax.scatter(df.index[i], df['Close'].iloc[i], color='red', 
                          marker='v', s=60, zorder=5)
    
    ax.set_ylabel('价格 (元)')
    ax.set_xlabel('日期')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)
    ax.set_xlim(df.index[0], df.index[-1])
    
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, 'ma-signals-510300.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'已保存: {output_path}')


def plot_oxq_returns():
    """绘制oxq策略收益对比图"""
    # 基于笔记中的数据
    assets = ['沪深300ETF', '招商银行', '中国平安', '平安银行', '五粮液', '贵州茅台']
    returns = [13.07, 33.91, 40.59, 11.00, 9.34, -9.20]
    volatility = [14.43, 19.09, 23.38, 19.07, 22.09, 16.99]
    sharpe = [0.3662, 0.6254, 0.6196, 0.2835, 0.2486, -0.1110]
    
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle('SMA(1,20) 交叉策略回测结果（2023-2026）', fontsize=14, fontweight='bold')
    
    colors = ['#4CAF50' if r >= 0 else '#F44336' for r in returns]
    
    # 左图：累计收益率
    bars1 = ax1.barh(assets, returns, color=colors, alpha=0.8)
    ax1.set_xlabel('累计收益率 (%)')
    ax1.set_title('累计收益率')
    ax1.axvline(x=0, color='black', linewidth=0.5)
    ax1.grid(True, alpha=0.3, axis='x')
    for bar, val in zip(bars1, returns):
        ax1.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2, 
                f'{val:.1f}%', ha='left', va='center', fontsize=9)
    
    # 中图：年化波动率
    ax2.barh(assets, volatility, color='#2196F3', alpha=0.7)
    ax2.set_xlabel('年化波动率 (%)')
    ax2.set_title('年化波动率')
    ax2.grid(True, alpha=0.3, axis='x')
    
    # 右图：夏普比率
    colors_sharpe = ['#4CAF50' if s >= 0 else '#F44336' for s in sharpe]
    ax3.barh(assets, sharpe, color=colors_sharpe, alpha=0.8)
    ax3.set_xlabel('夏普比率')
    ax3.set_title('夏普比率')
    ax3.axvline(x=0, color='black', linewidth=0.5)
    ax3.grid(True, alpha=0.3, axis='x')
    
    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, 'oxq-returns.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'已保存: {output_path}')


if __name__ == '__main__':
    print('获取数据中...')
    df = get_data()
    print(f'数据量: {len(df)} 条')
    
    print('\n绘制股价走势图...')
    plot_stock_price(df)
    
    print('绘制均线信号图...')
    plot_ma_signals(df)
    
    print('绘制oxq策略收益图...')
    plot_oxq_returns()
    
    print('\n全部完成!')
