#!/usr/bin/env python3
"""
三资产宏观分析 —— 相关性 + 组合回测 + 可视化

资产：沪深300(510300) / 纳指100(513100) / 黄金(518880)
数据源：data_fetcher（新浪源）
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter
import sys, os, warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../01-data/code'))
from data_fetcher import fetch_etf_data

plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

ASSETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../assets'))
os.makedirs(ASSETS_DIR, exist_ok=True)

START, END = "20210101", "20260101"
TICKERS = {"510300": "沪深300", "513100": "纳指100", "518880": "黄金"}


def load_data():
    """获取三资产日线数据"""
    data = {}
    for sym, name in TICKERS.items():
        df = fetch_etf_data(symbol=sym, start_date=START, end_date=END)
        data[name] = df['Close']
        print(f"  {name}: {len(df)} 条, {df.index[0].date()}~{df.index[-1].date()}")
    df_prices = pd.DataFrame(data)
    df_rets = df_prices.pct_change().dropna()
    return df_prices, df_rets


def fmt_pct(x):
    return f"{x:.0%}"


def annualize(series, periods=252):
    """年化收益率"""
    return (series.iloc[-1] / series.iloc[0]) ** (periods / len(series)) - 1


# ═══════════════════════════════════════════════════════
# 图1: 相关性热力图（保持不变，色调优化）
# ═══════════════════════════════════════════════════════
def plot_corr_heatmap(corr, save_path):
    fig, ax = plt.subplots(figsize=(7, 5.5))
    cmap = plt.cm.RdYlBu_r
    im = ax.imshow(corr.values, cmap=cmap, vmin=-0.3, vmax=0.7)
    ax.set_xticks(range(3))
    ax.set_yticks(range(3))
    ax.set_xticklabels(corr.columns, fontsize=12)
    ax.set_yticklabels(corr.index, fontsize=12)
    for i in range(3):
        for j in range(3):
            ax.text(j, i, f'{corr.iloc[i,j]:.3f}', ha='center', va='center',
                    fontsize=14, fontweight='bold',
                    color='white' if abs(corr.iloc[i,j]) > 0.4 else 'black')
    ax.set_title('日收益率相关性矩阵 (2021-2025)', fontsize=13, fontweight='bold')
    plt.colorbar(im, shrink=0.75)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ {save_path}")


# ═══════════════════════════════════════════════════════
# 图2: 滚动60日相关性
# ═══════════════════════════════════════════════════════
def plot_rolling_corr(rets, save_path):
    fig, ax = plt.subplots(figsize=(14, 5))
    pairs = [('沪深300-纳指100', rets['沪深300'].rolling(60).corr(rets['纳指100']), '#2196F3'),
             ('沪深300-黄金', rets['沪深300'].rolling(60).corr(rets['黄金']), '#4CAF50'),
             ('纳指100-黄金', rets['纳指100'].rolling(60).corr(rets['黄金']), '#FF9800')]
    for label, series, color in pairs:
        ax.plot(series.index, series.values, label=label, color=color, linewidth=0.8, alpha=0.85)
    ax.axhline(y=0, color='gray', linewidth=0.5, linestyle='--')
    ax.set_ylabel('滚动60日相关系数')
    ax.set_title('三资产滚动60日相关性 (2021-2025)', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.25)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ {save_path}")


# ═══════════════════════════════════════════════════════
# 图3: 三资产归一化走势（含黄金）
# ═══════════════════════════════════════════════════════
def plot_normalized(prices, save_path):
    norm = prices / prices.iloc[0] * 100
    colors = {'沪深300': '#F44336', '纳指100': '#2196F3', '黄金': '#FF9800'}
    fig, ax = plt.subplots(figsize=(14, 6))
    for name in prices.columns:
        ax.plot(norm.index, norm[name], label=name, color=colors.get(name, '#666'), linewidth=1.2)
    ax.axhline(y=100, color='gray', linewidth=0.5, linestyle='--', alpha=0.5)
    ax.set_ylabel('归一化价格 (起点=100)')
    ax.set_title('三资产走势对比 (2021-2025)', fontsize=13, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.25)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ {save_path}")
    # 打印终值
    for name in prices.columns:
        print(f"    {name}: 100 → {norm[name].iloc[-1]:.1f}")


# ═══════════════════════════════════════════════════════
# 图4: 组合 vs 单押对比 + 回撤
# ═══════════════════════════════════════════════════════
def plot_portfolio_comparison(rets, save_path):
    weights = np.array([1/3, 1/3, 1/3])
    port_rets = rets.values @ weights
    port_cum = (1 + port_rets).cumprod()
    single_cum = (1 + rets).cumprod()

    # 回撤计算
    port_peak = np.maximum.accumulate(port_cum)
    port_dd = (port_cum - port_peak) / port_peak
    single_dd = {}
    for name in rets.columns:
        peak = np.maximum.accumulate(single_cum[name].values)
        dd = (single_cum[name].values - peak) / peak
        single_dd[name] = dd

    fig, axes = plt.subplots(2, 1, figsize=(14, 9), gridspec_kw={'height_ratios': [2, 1]})
    fig.suptitle('等权组合 vs 单资产 — 累计收益与回撤', fontsize=14, fontweight='bold')

    # 上图：累计收益
    ax1 = axes[0]
    colors_line = {'沪深300': '#F44336', '纳指100': '#2196F3', '黄金': '#FF9800'}
    for name in rets.columns:
        ax1.plot(rets.index, single_cum[name], label=name, color=colors_line.get(name, '#666'),
                 linewidth=0.9, alpha=0.6)
    ax1.plot(rets.index, port_cum, label=f'等权组合 (最终{port_cum[-1]:.2f}x)',
             color='#4CAF50', linewidth=2)
    ax1.axhline(y=1.0, color='gray', linewidth=0.5, linestyle='--')
    ax1.set_ylabel('累计净值')
    ax1.legend(fontsize=9, ncol=2)
    ax1.grid(True, alpha=0.2)

    # 下图：回撤
    ax2 = axes[1]
    for name in rets.columns:
        ax2.fill_between(rets.index, 0, single_dd[name] * 100, alpha=0.15,
                         color=colors_line.get(name, '#666'))
        ax2.plot(rets.index, single_dd[name] * 100, color=colors_line.get(name, '#666'),
                 linewidth=0.6, alpha=0.5)
    ax2.fill_between(rets.index, 0, port_dd * 100, alpha=0.3, color='#4CAF50')
    ax2.plot(rets.index, port_dd * 100, color='#4CAF50', linewidth=1.2, label=f'组合最大回撤 {port_dd.min():.1%}')
    ax2.set_ylabel('回撤 (%)')
    ax2.set_xlabel('日期')
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.2)

    for ax in axes:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=9)

    plt.tight_layout()
    plt.subplots_adjust(top=0.93)
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ {save_path}")


# ═══════════════════════════════════════════════════════
# 图5: 不同权重的风险收益 scatter
# ═══════════════════════════════════════════════════════
def plot_weight_scan(rets, save_path):
    n_iter = 2000
    np.random.seed(42)
    results = []
    for _ in range(n_iter):
        w = np.random.dirichlet(np.ones(3))
        p_rets = rets.values @ w
        ann_ret = (1 + p_rets).prod() ** (252 / len(p_rets)) - 1
        ann_vol = p_rets.std() * np.sqrt(252)
        sharpe = (p_rets.mean() / p_rets.std()) * np.sqrt(252)
        results.append((ann_ret, ann_vol, sharpe, w))

    res_df = pd.DataFrame(results, columns=['ret', 'vol', 'sharpe', 'weights'])

    fig, ax = plt.subplots(figsize=(10, 7))
    scatter = ax.scatter(res_df['vol'], res_df['ret'], c=res_df['sharpe'],
                         cmap='RdYlGn', alpha=0.6, s=20)

    # 标出等权组合
    w_eq = np.array([1/3, 1/3, 1/3])
    p_eq = rets.values @ w_eq
    eq_ret = (1 + p_eq).prod() ** (252 / len(p_eq)) - 1
    eq_vol = p_eq.std() * np.sqrt(252)
    ax.scatter(eq_vol, eq_ret, marker='*', color='black', s=200, zorder=5,
               label=f'等权组合 (夏普={((p_eq.mean()/p_eq.std())*np.sqrt(252)):.2f})')

    # 最大夏普组合
    best = res_df.loc[res_df['sharpe'].idxmax()]
    ax.scatter(best['vol'], best['ret'], marker='D', color='gold', s=120, zorder=5,
               label=f"最大夏普 ({best['sharpe']:.2f})")

    # 最小方差组合
    minvol = res_df.loc[res_df['vol'].idxmin()]
    ax.scatter(minvol['vol'], minvol['ret'], marker='s', color='cyan', s=120, zorder=5,
               label=f"最小方差 (波动={minvol['vol']:.1%})")

    # 单资产
    for name in rets.columns:
        ann_r = (1 + rets[name]).prod() ** (252 / len(rets)) - 1
        ann_v = rets[name].std() * np.sqrt(252)
        ax.scatter(ann_v, ann_r, marker='o', s=80, zorder=4,
                   label=f'{name}')
        ax.annotate(name, (ann_v, ann_r), fontsize=10, xytext=(5, 5),
                    textcoords='offset points')

    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label('夏普比率')
    ax.set_xlabel('年化波动率')
    ax.set_ylabel('年化收益率')
    ax.set_title('三资产组合有效前沿 (蒙特卡洛模拟)', fontsize=13, fontweight='bold')
    ax.legend(fontsize=8, loc='lower right')
    ax.grid(True, alpha=0.25)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f'{y:.0%}'))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:.0%}'))

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ {save_path}")
    print(f"    等权组合: 年化{best['ret']:.2%} 波动{best['vol']:.2%} 夏普{best['sharpe']:.3f}")
    print(f"    最大夏普: 年化{best['ret']:.2%} 波动{best['vol']:.2%} 夏普{best['sharpe']:.3f}")
    print(f"    最小方差: 年化{minvol['ret']:.2%} 波动{minvol['vol']:.2%}")


# ═══════════════════════════════════════════════════════
# 图6: 分阶段累计收益对比
# ═══════════════════════════════════════════════════════
def plot_phase_analysis(rets, save_path):
    """将回测期划分为四个阶段，对比各资产和组合的表现"""
    phases = [
        ('2021 高位震荡', '2021-01-01', '2021-12-31'),
        ('2022 普跌', '2022-01-01', '2022-10-31'),
        ('2022底-2024 分化', '2022-11-01', '2024-09-30'),
        ('2024末-2025 反弹', '2024-10-01', '2025-12-31'),
    ]
    weights = np.array([1/3, 1/3, 1/3])
    port_rets = rets.values @ weights

    data_rows = []
    for phase_name, ps, pe in phases:
        mask = (rets.index >= ps) & (rets.index <= pe)
        row = {'阶段': phase_name}
        for name in rets.columns:
            seg = rets.loc[mask, name]
            cum_ret = (1 + seg).prod() - 1
            row[name] = cum_ret
        seg_port = port_rets[mask]
        row['等权组合'] = (1 + seg_port).prod() - 1
        data_rows.append(row)

    df_phase = pd.DataFrame(data_rows).set_index('阶段')

    # 柱状图
    fig, ax = plt.subplots(figsize=(12, 6))
    n_phases = len(df_phase)
    x = np.arange(n_phases)
    width = 0.15
    colors = {'沪深300': '#F44336', '纳指100': '#2196F3', '黄金': '#FF9800', '等权组合': '#4CAF50'}

    for i, name in enumerate(['沪深300', '纳指100', '黄金', '等权组合']):
        vals = df_phase[name].values
        bars = ax.bar(x + i * width, vals * 100, width, label=name, color=colors[name], alpha=0.8)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width()/2,
                    bar.get_height() + (0.5 if v >= 0 else -2.5),
                    f'{v:.1%}', ha='center', va='bottom' if v >= 0 else 'top', fontsize=8)

    ax.set_xticks(x + width * 1.5)
    ax.set_xticklabels(df_phase.index, fontsize=10)
    ax.axhline(y=0, color='gray', linewidth=0.5)
    ax.set_ylabel('阶段收益率 (%)')
    ax.set_title('各阶段收益对比 (2021-2025)', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.2, axis='y')
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  ✓ {save_path}")
    print(df_phase.to_string(float_format=lambda x: f'{x:.2%}'))


# ═══════════════════════════════════════════════════════
# 主程序
# ═══════════════════════════════════════════════════════
if __name__ == '__main__':
    print("=" * 50)
    print("三资产宏观分析")
    print("=" * 50)

    print("\n加载数据...")
    prices, rets = load_data()
    print(f"\n数据: {rets.index[0].date()} ~ {rets.index[-1].date()} ({len(rets)} 交易日)")

    # ── 指标计算 ──
    print("\n===== 各资产风险收益指标 =====")
    metrics_rows = []
    for name in prices.columns:
        ann_ret = annualize(prices[name])
        ann_vol = rets[name].std() * np.sqrt(252)
        sharpe = (rets[name].mean() / rets[name].std()) * np.sqrt(252)
        cummax = prices[name].cummax()
        mdd = ((prices[name] - cummax) / cummax).min()
        calmar = ann_ret / abs(mdd) if mdd != 0 else np.inf
        metrics_rows.append({'资产': name, '年化收益': ann_ret, '年化波动': ann_vol,
                              '夏普比率': sharpe, '最大回撤': mdd, '卡玛比率': calmar})
    df_metrics = pd.DataFrame(metrics_rows)
    print(df_metrics.to_string(index=False, float_format=lambda x: f'{x:.4f}'))
    print()

    # 等权组合
    w_eq = np.array([1/3, 1/3, 1/3])
    p_rets = rets.values @ w_eq
    eq_ann_ret = (1 + p_rets).prod() ** (252 / len(p_rets)) - 1
    eq_ann_vol = p_rets.std() * np.sqrt(252)
    eq_sharpe = (p_rets.mean() / p_rets.std()) * np.sqrt(252)
    eq_cum = (1 + p_rets).cumprod()
    eq_peak = np.maximum.accumulate(eq_cum)
    eq_mdd = ((eq_cum - eq_peak) / eq_peak).min()
    eq_calmar = eq_ann_ret / abs(eq_mdd) if eq_mdd != 0 else np.inf
    print(f"等权组合: 年化={eq_ann_ret:.2%} 波动={eq_ann_vol:.2%} 夏普={eq_sharpe:.3f} 回撤={eq_mdd:.2%} 卡玛={eq_calmar:.2f}")

    # ── 相关性 ──
    corr = rets.corr()
    print(f"\n===== 日收益相关性 =====")
    print(corr.round(3))

    # ── 年化相关性 ──
    yearly_rets = prices.resample('YE').last().pct_change().dropna()
    if len(yearly_rets) >= 2:
        yearly_corr = yearly_rets.corr()
        print(f"\n===== 年收益相关性 (n={len(yearly_rets)}) =====")
        print(yearly_corr.round(3))

    # ── 生成图表 ──
    print("\n===== 生成图表 =====")
    plot_corr_heatmap(corr, os.path.join(ASSETS_DIR, 'correlation-heatmap.png'))
    plot_rolling_corr(rets, os.path.join(ASSETS_DIR, 'correlation-rolling.png'))
    plot_normalized(prices, os.path.join(ASSETS_DIR, 'etf-normalized-all.png'))
    plot_portfolio_comparison(rets, os.path.join(ASSETS_DIR, 'portfolio-comparison.png'))
    plot_weight_scan(rets, os.path.join(ASSETS_DIR, 'portfolio-efficient-frontier.png'))
    plot_phase_analysis(rets, os.path.join(ASSETS_DIR, 'portfolio-phases.png'))

    print("\n全部完成!")
