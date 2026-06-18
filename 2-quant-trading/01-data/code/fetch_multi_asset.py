#!/usr/bin/env python3
"""
获取多资产数据（纳指100、黄金）+ 沪深300，并绘制各自的价格走势图。

用法:
    python3 fetch_multi_asset.py

输出到 ../../assets/:
    stock-price-513100.png  — 纳指100ETF 股价走势
    stock-price-518880.png  — 黄金ETF 股价走势
    multi-asset-comparison.png  — 三资产归一化走势对比
"""

import os, sys
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.font_manager import FontProperties

# ── 路径 ──
CODE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CODE_DIR)
from data_fetcher import fetch_etf_data

ASSETS_DIR = os.path.abspath(os.path.join(CODE_DIR, '../../assets'))
os.makedirs(ASSETS_DIR, exist_ok=True)

# ── 字体 ──
FONT_PATH = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
font = FontProperties(fname=FONT_PATH)
font_small = FontProperties(fname=FONT_PATH, size=10)
font_bold = FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc', size=14)
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'DejaVu Sans']


def fetch_all() -> dict[str, pd.DataFrame]:
    """获取三资产数据"""
    targets = {
        "510300": "沪深300ETF",
        "513100": "纳指100ETF",
        "518880": "黄金ETF",
    }
    data = {}
    for symbol, name in targets.items():
        df = fetch_etf_data(symbol=symbol, start_date="20210101", end_date="20260101")
        data[name] = df
        print(f"✓ {name} ({symbol}): {len(df)} 个交易日, "
              f"{df.index[0].date()} ~ {df.index[-1].date()}")
    return data


def plot_stock_price(df: pd.DataFrame, title: str, filename: str):
    """
    绘制单资产股价走势图（双轴：价格+成交量）
    与 generate_charts.py 风格一致
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8),
                                     gridspec_kw={'height_ratios': [3, 1]})
    fig.suptitle(title, fontproperties=font_bold)

    # ── 上图：收盘价 + 均线 ──
    ax1.plot(df.index, df['Close'], color='#2196F3', linewidth=1.2, label='收盘价')
    ax1.plot(df.index, df['Close'].rolling(20).mean(), color='#FF9800',
             linewidth=0.8, alpha=0.7, label='MA20')
    ax1.plot(df.index, df['Close'].rolling(60).mean(), color='#4CAF50',
             linewidth=0.8, alpha=0.7, label='MA60')
    ax1.fill_between(df.index, df['Close'].min() * 0.95, df['Close'],
                     alpha=0.1, color='#2196F3')
    ax1.set_ylabel('价格 (元)', fontproperties=font_small)
    ax1.legend(prop=font_small, loc='upper left')
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(df.index[0], df.index[-1])

    # ── 下图：成交量 ──
    colors = ['#4CAF50' if df['Close'].iloc[i] >= df['Close'].iloc[i-1]
              else '#F44336' for i in range(1, len(df))]
    colors.insert(0, '#4CAF50')
    ax2.bar(df.index, df['Volume'] / 1e6, color=colors, alpha=0.6, width=1)
    ax2.set_ylabel('成交量 (百万股)', fontproperties=font_small)
    ax2.set_xlabel('日期', fontproperties=font_small)
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(df.index[0], df.index[-1])

    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.xticks(rotation=45)

    plt.tight_layout()
    path = os.path.join(ASSETS_DIR, filename)
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✓ 图表已保存: {path}")


def plot_multi_comparison(data: dict[str, pd.DataFrame]):
    """
    三资产归一化走势对比（起点=100）
    """
    fig, ax = plt.subplots(figsize=(12, 6))

    colors = {'沪深300ETF': '#F44336', '纳指100ETF': '#2196F3', '黄金ETF': '#FF9800'}
    for name in data:
        close = data[name]['Close']
        norm = close / close.iloc[0] * 100
        ax.plot(norm.index, norm, label=name, color=colors.get(name),
                linewidth=1.5)

    ax.set_title('三资产归一化走势对比 (2021-2026)', fontproperties=font, fontsize=14)
    ax.set_xlabel('日期', fontproperties=font)
    ax.set_ylabel('归一化价格（起点=100）', fontproperties=font)
    ax.legend(prop=font)
    ax.grid(True, alpha=0.3)

    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.xticks(rotation=45)

    plt.tight_layout()
    path = os.path.join(ASSETS_DIR, 'multi-asset-comparison.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✓ 图表已保存: {path}")


if __name__ == '__main__':
    print("=" * 50)
    print("获取多资产数据...")
    print("=" * 50)
    data = fetch_all()

    print("\n" + "=" * 50)
    print("绘制各资产股价走势图...")
    print("=" * 50)
    for name in data:
        symbol_map = {"沪深300ETF": "510300", "纳指100ETF": "513100", "黄金ETF": "518880"}
        fn = f"stock-price-{symbol_map[name]}.png"
        plot_stock_price(data[name], f"{name} 股价走势", fn)

    print("\n" + "=" * 50)
    print("绘制三资产归一化走势对比...")
    print("=" * 50)
    plot_multi_comparison(data)

    print("\n全部完成!")
