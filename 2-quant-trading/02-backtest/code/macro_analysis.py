import akshare as ak
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import matplotlib

font = FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc')
matplotlib.rcParams['axes.unicode_minus'] = False

# ===== 1. 获取数据 =====
etfs = {
    "sh510300": "沪深300",
    "sh513100": "纳指100",
    "sh518880": "黄金"
}

data = {}
for symbol, name in etfs.items():
    df_etf = ak.fund_etf_hist_sina(symbol=symbol)
    df_etf['date'] = pd.to_datetime(df_etf['date'])
    df_etf = df_etf[(df_etf['date'] >= '2021-01-01') & (df_etf['date'] < '2026-01-01')]
    df_etf = df_etf.set_index('date')
    data[name] = df_etf['close']
    print(f"✓ {name}: {len(df_etf)} 交易日")

df = pd.DataFrame(data)
df.loc[df.index < '2022-01-14', '纳指100'] /= 5

print(f"\n数据范围: {df.index[0].date()} ~ {df.index[-1].date()}")
print(df.tail())

# ===== 2. 相关性矩阵 + 热力图 =====
returns = df.pct_change().dropna()
corr_matrix = returns.corr()

fig, ax = plt.subplots(figsize=(8, 6))
im = ax.imshow(corr_matrix.values, cmap='coolwarm', vmin=-1, vmax=1)

ax.set_xticks(range(3))
ax.set_yticks(range(3))
ax.set_xticklabels(corr_matrix.columns, fontproperties=font, fontsize=12)
ax.set_yticklabels(corr_matrix.index, fontproperties=font, fontsize=12)

for i in range(3):
    for j in range(3):
        ax.text(j, i, f'{corr_matrix.iloc[i, j]:.2f}',
                ha='center', va='center', fontsize=14, color='black')

ax.set_title('三资产日收益率相关性', fontproperties=font, fontsize=14)
plt.colorbar(im)
plt.tight_layout()
plt.savefig('/root/obsidian-vault/2-quant-trading/assets/correlation-heatmap.png', dpi=150)
print("\n✓ 相关性热力图已保存")

# ===== 3. 组合 vs 单押指标计算 =====
weights = np.array([1/3, 1/3, 1/3])
portfolio_returns = returns.values @ weights
portfolio_cum = (1 + portfolio_returns).cumprod()
single_cum = (1 + returns).cumprod()

def calc_metrics(cum_returns, annual_factor=252):
    total_return = cum_returns[-1] / cum_returns[0] - 1
    daily_returns = np.diff(cum_returns) / cum_returns[:-1]
    annual_vol = np.std(daily_returns) * np.sqrt(annual_factor)
    peak = np.maximum.accumulate(cum_returns)
    drawdown = (cum_returns - peak) / peak
    max_drawdown = np.min(drawdown)
    return total_return, annual_vol, max_drawdown

port_ret, port_vol, port_mdd = calc_metrics(portfolio_cum)
h300_ret, h300_vol, h300_mdd = calc_metrics(single_cum['沪深300'].values)

print(f"\n===== 回测指标 (2021-2025) =====")
print(f"{'指标':<12} {'等权组合':>10} {'单押沪深300':>12}")
print(f"{'累计收益率':<12} {port_ret:>10.2%} {h300_ret:>12.2%}")
print(f"{'年化波动率':<12} {port_vol:>10.2%} {h300_vol:>12.2%}")
print(f"{'最大回撤':<12} {port_mdd:>10.2%} {h300_mdd:>12.2%}")

# ===== 4. 累计收益率对比图 =====
fig, ax = plt.subplots(figsize=(12, 6))
ax.plot(returns.index, single_cum['沪深300'], label='单押沪深300', color='gray', linestyle='--', linewidth=1.5)
ax.plot(returns.index, portfolio_cum, label='三资产等权组合', color='green', linewidth=1.5)

ax.set_title('累计收益率对比：等权组合 vs 单押沪深300', fontproperties=font, fontsize=14)
ax.set_xlabel('日期', fontproperties=font)
ax.set_ylabel('累计净值', fontproperties=font)
ax.legend(prop=font)
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('/root/obsidian-vault/2-quant-trading/assets/portfolio-comparison.png', dpi=150)
print("\n✓ 累计收益率对比图已保存")

# ===== 5. oxq StaticUniverse =====
print("\n===== oxq StaticUniverse =====")
print("投资宇宙配置:")
print("  name: global-macro-etf")
print("  symbols: ['510300', '513100', '518880']")
print("  as_of_date: 2026-01-01")
print()
print("示例代码:")
print("  from oxq.universe import StaticUniverse")
print("  universe = StaticUniverse(")
print("      symbols=['510300', '513100', '518880'],")
print("      name='global-macro-etf'")
print("  )")
print("  snapshot = universe.get_universe(as_of_date='2026-01-01')")
print()
print("注意: open-xquant 需要 Python>=3.12，当前环境为 3.11.2")
print("      如需运行，请升级 Python 或使用 uv: uv venv --python 3.12 .venv")
