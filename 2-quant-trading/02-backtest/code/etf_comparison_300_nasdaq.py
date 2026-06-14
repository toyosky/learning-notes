import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

font = FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc')

etfs = {"sh510300": "沪深300ETF", "sh513100": "纳指100ETF"}

data = {}
for symbol, name in etfs.items():
    df = ak.fund_etf_hist_sina(symbol=symbol)
    df['date'] = pd.to_datetime(df['date'])
    df = df[(df['date'] >= '2021-01-01') & (df['date'] < '2026-01-01')]
    df = df.set_index('date')
    data[name] = df['close']
    print(f"✓ {name}: {len(df)} 交易日")

df_all = pd.DataFrame(data)
df_norm = df_all / df_all.iloc[0] * 100

fig, ax = plt.subplots(figsize=(12, 6))
ax.plot(df_norm.index, df_norm['沪深300ETF'], label='沪深300ETF', linewidth=1.5)
ax.plot(df_norm.index, df_norm['纳指100ETF'], label='纳指100ETF', linewidth=1.5)

ax.set_title('沪深300ETF vs 纳指100ETF 归一化走势（2021-2026）', fontproperties=font, fontsize=14)
ax.set_xlabel('日期', fontproperties=font)
ax.set_ylabel('归一化价格（起点=100）', fontproperties=font)
ax.legend(prop=font)
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('etf-comparison-300-nasdaq.png', dpi=150)
print(f"\n✓ 图表已保存")
print(f"沪深300ETF: {df_norm['沪深300ETF'].iloc[-1]:.2f}")
print(f"纳指100ETF: {df_norm['纳指100ETF'].iloc[-1]:.2f}")
