#!/usr/bin/env python3
"""510300 vs 513100 归一化走势对比"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../01-data/code'))
from data_fetcher import fetch_etf_data

# ── 数据下载（自动尝试东财 → 回退新浪）─────────────────────────────
SYMBOLS = {
    "510300": "沪深300ETF",
    "513100": "纳指100ETF",
}
COLORS = {"沪深300ETF": "#E53935", "纳指100ETF": "#1E88E5"}
START, END = "2021-01-01", "2026-01-01"

close_data = {}

for sym, label in SYMBOLS.items():
    print(f"  获取 {sym} ({label}) ...")
    df = fetch_etf_data(symbol=sym, start_date=START.replace("-", ""), end_date=END.replace("-", ""))
    close_data[label] = df["Close"]
    print(f"    → {len(df)} 条, {df.index[0].date()} ~ {df.index[-1].date()}")

close = pd.DataFrame(close_data)
norm = close.div(close.iloc[0]).mul(100)

# ── 输出统计 ──────────────────────────────────────────────────────
print("\n累计收益率:")
for label in norm.columns:
    ret = norm[label].iloc[-1] - 100
    print(f"  {label}: {ret:+.2f}%")

# ── 绘图 ──────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.sans-serif": ["WenQuanYi Micro Hei", "SimHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.facecolor": "white",
})

fig, ax = plt.subplots(figsize=(12, 6))
fig.suptitle("沪深300ETF vs 纳指100ETF — 归一化走势（起点 = 100）",
             fontsize=14, fontweight="bold", y=0.98)

for label in norm.columns:
    ax.plot(norm.index, norm[label], color=COLORS[label],
            linewidth=1.5, label=label)

ax.axhline(y=100, color="gray", linewidth=0.5, linestyle="--", alpha=0.5)
ax.set_ylabel("归一化价格")
ax.set_xlabel("日期")
ax.legend(loc="upper left", fontsize=11)
ax.grid(True, alpha=0.3)

ax.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
plt.xticks(rotation=45)

text = "  |  ".join(
    f"{label}: {ret:+.1f}%"
    for label in norm.columns
    for ret in [norm[label].iloc[-1] - 100]
)
fig.text(0.5, 0.02, text, ha="center", fontsize=10,
         bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.8))

plt.tight_layout()
out = "/root/obsidian-vault/2-quant-trading/etf-comparison.png"
plt.savefig(out, dpi=150, bbox_inches="tight")
print(f"\n图表已保存: {out}")
plt.close()
