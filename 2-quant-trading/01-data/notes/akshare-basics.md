---
tags: [量化, 数据, akshare, A股, yfinance]
date: 2026-06-09
---

# akshare 获取 ETF 数据

> 用 akshare 替代 yfinance，获取沪深300、纳指100、黄金 ETF 数据。当前数据源为**新浪**（东方财富暂不可达时自动回退）。

## 为什么不用 yfinance？

yfinance 请求雅虎财经接口有**频率限制**（`YFRateLimitError`），而且对中国 A 股支持不好。改用 akshare，速度更快、更稳定。

`data_fetcher.py` 的数据源策略：优先尝试东方财富（支持原生 `adjust` 复权参数），不可达时自动回退到新浪源（手动检测拆股并前复权）。当前东方财富接口不可用，数据统一来自新浪源。

## 环境准备

```bash
python3 -m venv /tmp/yf_env
source /tmp/yf_env/bin/activate
pip install akshare pandas
```

---

## A股数据获取（沪深300ETF）

以 **510300（沪深300ETF）** 为例，获取 A 股核心资产的日线数据。

### 核心代码

```python
import akshare as ak
import pandas as pd

# 获取 510300（沪深300ETF）日线数据
df = ak.fund_etf_hist_em(
    symbol="510300",
    period="daily",
    start_date="20210101",
    end_date="20260101",
    adjust="qfq"      # 前复权，等价于 yfinance 的 auto_adjust=True
)

# 日期列 → DatetimeIndex
df['日期'] = pd.to_datetime(df['日期'])
df = df.set_index('日期')
df.index.name = 'Date'

# 重命名关键列
df = df.rename(columns={
    '开盘': 'Open', '收盘': 'Close',
    '最高': 'High', '最低': 'Low', '成交量': 'Volume',
})

df = df[['Close', 'High', 'Low', 'Open', 'Volume']]
print(df.head())
```

### 运行结果

```
            Close   High    Low   Open     Volume
Date
2021-01-04  5.334  5.366  5.260  5.280  506705639
2021-01-05  5.433  5.445  5.305  5.321  622830794
2021-01-06  5.482  5.514  5.417  5.447  374945107
```

### 股价走势图

![510300股价走势](../../assets/stock-price-510300.png)

---

## 美股数据获取（纳指100ETF）

akshare 同样支持跨境 ETF。这里以 **513100（纳指100ETF）** 为例，跟踪纳斯达克 100 指数，成分股为苹果、微软、英伟达等美国科技龙头。

### 核心代码

```python
import akshare as ak
import pandas as pd

# 获取 513100（纳指100ETF）日线数据
df = ak.fund_etf_hist_em(
    symbol="513100",
    period="daily",
    start_date="20210101",
    end_date="20260101",
    adjust="qfq"      # 前复权
)

# 日期列 → DatetimeIndex
df['日期'] = pd.to_datetime(df['日期'])
df = df.set_index('日期')
df.index.name = 'Date'

# 重命名关键列
df = df.rename(columns={
    '开盘': 'Open', '收盘': 'Close',
    '最高': 'High', '最低': 'Low', '成交量': 'Volume',
})

df = df[['Close', 'High', 'Low', 'Open', 'Volume']]
print(df.head())
```

### 运行结果

```
            Close    High     Low    Open     Volume
Date
2021-01-04  0.847   0.854   0.845   0.854   17143700
2021-01-05  0.836   0.839   0.832   0.837   15363100
2021-01-06  0.832   0.840   0.832   0.838   18123702
```

> ⚠️ 513100 在 2022-01-14 发生过 1:5 拆股，前复权价格已自动调整。
> 价格单位是**元（人民币）**，而非美元。净值按实时汇率折算。

### 股价走势图

![513100股价走势](../../assets/stock-price-513100.png)

### 与沪深300对比

![纳指100 vs 沪深300归一化走势](../../assets/etf-comparison-300-nasdaq.png)

纳指 100 在 2021-2024 年大幅跑赢沪深 300，体现出美股科技股的强劲表现。

---

## 黄金数据获取（黄金ETF）

黄金是量化配置中重要的避险资产。以 **518880（黄金ETF）** 为例，跟踪上海黄金交易所 AU99.99 价格，是国内规模最大的黄金 ETF。

### 核心代码

```python
import akshare as ak
import pandas as pd

# 获取 518880（黄金ETF）日线数据
df = ak.fund_etf_hist_em(
    symbol="518880",
    period="daily",
    start_date="20210101",
    end_date="20260101",
    adjust="qfq"      # 前复权
)

# 日期列 → DatetimeIndex
df['日期'] = pd.to_datetime(df['日期'])
df = df.set_index('日期')
df.index.name = 'Date'

# 重命名关键列
df = df.rename(columns={
    '开盘': 'Open', '收盘': 'Close',
    '最高': 'High', '最低': 'Low', '成交量': 'Volume',
})

df = df[['Close', 'High', 'Low', 'Open', 'Volume']]
print(df.head())
```

### 运行结果

```
            Close   High    Low   Open      Volume
Date
2021-01-04  3.902  3.909  3.894  3.897   355073116
2021-01-05  3.920  3.930  3.914  3.923   415591092
2021-01-06  3.931  3.939  3.922  3.931   459531490
```

### 股价走势图

![518880股价走势](../../assets/stock-price-518880.png)

### 黄金的避险属性

黄金在 A 股下跌期间往往能提供正收益，与股票的相关性接近于零，是做资产配置时的重要"压舱石"。

---

## 三资产归一化走势对比

将沪深300、纳指100、黄金放在一起对比，可以直观感受三类资产的差异化表现：

![三资产归一化走势对比](../../assets/multi-asset-comparison.png)

### 关键特征

| 资产 | 2021-2025 表现 | 特点 |
|------|--------------|------|
| **纳指100** | 大幅上涨 → 高位回调 | 高收益高波动，科技驱动 |
| **黄金** | 稳步上行 | 低波动，抗通胀，避险 |
| **沪深300** | 持续下跌 → 触底反弹 | 与 A 股经济周期绑定 |

### 多资产批量获取

使用 `data_fetcher` 的批量接口同时拉取多个标的：

```python
from data_fetcher import fetch_etf_data

symbols = {
    "510300": "沪深300ETF",
    "513100": "纳指100ETF",
    "518880": "黄金ETF",
}

data = {}
for symbol, name in symbols.items():
    df = fetch_etf_data(symbol=symbol, start_date="20210101", end_date="20260101")
    data[name] = df['Close']
    print(f"✓ {name}: {len(df)} 交易日")
```

完整的对比分析和组合回测见 [[../../02-backtest/notes/macro-analysis|三资产宏观分析]]。

---

## akshare 常用函数速查

```python
# A 股日线（东财，支持复权）
ak.stock_zh_a_hist(symbol="600519", period="daily", adjust="qfq")

# ETF 日线（东财，推荐）
ak.fund_etf_hist_em(symbol="510300", period="daily", adjust="qfq")

# ETF 日线（新浪，需手动复权）
ak.fund_etf_hist_sina(symbol="sh510300")  # 需加 "sh"/"sz" 前缀

# 指数日线
ak.stock_zh_index_daily(symbol="sh000001")

# 指数日线（东财，支持周/月）
ak.index_zh_a_hist(symbol="000300", period="daily")

# 实时全量行情
ak.stock_zh_a_spot_em()

# 完整速查 → [[akshare-reference|AKShare 数据接口速查]]
```

---

## 返回列说明

| 列名 | 含义 |
|------|------|
| Open | 开盘价（前复权） |
| High | 最高价（前复权） |
| Low | 最低价（前复权） |
| Close | 收盘价（前复权） |
| Volume | 成交量（股） |

---

## 参数对照

| 参数 | 说明 |
|------|------|
| `symbol="510300"` | ETF 代码（**不带** `.SS`/`.SZ` 后缀），适用于所有 ETF |
| `period="daily"` | 日线数据 |
| `start_date="20210101"` | 格式 YYYYMMDD，数据源取到该日期之前的最后一个交易日 |
| `end_date="20260101"` | 格式 YYYYMMDD，不传则默认到当天 |
| `adjust="qfq"` | 前复权 |

> **`.SS` / `.SZ` 是什么？** `.SS` 代表上海交易所，`.SZ` 代表深圳交易所。yfinance、新浪等数据源需要在代码后加后缀（如 `510300.SS`），但 akshare 东方财富接口**不需要**，直接写纯数字即可。
>
> **当前数据源说明**：本笔记所有示例数据均来自**新浪源**（东方财富暂不可达，`data_fetcher.py` 自动回退）。东财源恢复后，删除本地 parquet 缓存重新运行即可切回。

### 常用 ETF 代码

| 代码 | 名称 | 跟踪标的 |
|------|------|---------|
| 510300 | 沪深300ETF | 沪深300 指数 |
| 513100 | 纳指100ETF | 纳斯达克100 指数 |
| 518880 | 黄金ETF | 上海金 AU99.99 |

> 完整代码列表见 [[akshare-reference#常用标的代码|常用标的代码]]。

---

## 注意事项

1. **虚拟环境**：务必在虚拟环境中运行，避免污染系统 Python
2. **日期格式**：`"YYYYMMDD"` 格式，不是 `"YYYY-MM-DD"`
3. **复权处理**：`adjust="qfq"` = 前复权，`adjust=""` = 不复权
4. **数据量**：2021-01-04 ~ 2025-12-31 共约 1212 个交易日（参数传 `end_date="20260101"`，但 2026-01-01 为非交易日，实际取到最后一个交易日 2025-12-31）

## 速查入口

> 🔍 写策略时找数据接口？点这里。
> 
> - [[akshare-reference|AKShare 数据接口速查]] — 按数据类型分类的完整参考手册

## 深挖入口

> 🕳️ 遇到不熟悉的概念了？点进去深挖。

- [[../deep/forward-vs-backward-adjustment|前复权vs后复权]] — 前复权和后复权的区别、计算方式，以及对量化回测的影响
- 还想深挖？→ 分红除息的税费计算细则

## 相关笔记

- [[../../02-backtest/notes/dca-backtest|DCA 定投回测]] — 基于本数据的 DCA 回测
- [[../../02-backtest/notes/ma-crossover-backtest|均线交叉策略回测]] — 基于 pandas 独立实现的策略回测
- [[../../02-backtest/notes/macro-analysis|三资产宏观分析]] — 沪深300/纳指100/黄金 相关性 + 组合回测
- [[../../02-backtest/notes/portfolio-allocation|组合分配系列笔记（入口）]] — 等权/风险平价/动量排名
