import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../01-data/code'))
from data_fetcher import fetch_etf_data

font = FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc')

etfs = {"510300": "沪深300ETF", "513100": "纳指100ETF"}

data = {}
for symbol, name in etfs.items():
    df = fetch_etf_data(symbol=symbol, start_date="20210101", end_date="20260101")
    data[name] = df['Close']
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
print(f"沪深300ETF: 100 → {df_norm['沪深300ETF'].iloc[-1]:.2f}")
print(f"纳指100ETF: 100 → {df_norm['纳指100ETF'].iloc[-1]:.2f}")
