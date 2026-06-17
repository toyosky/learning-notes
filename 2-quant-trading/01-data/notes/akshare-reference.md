---
tags: [量化, 数据, akshare, A股, 参考]
date: 2026-06-15
---

# AKShare 数据接口速查

> 策略开发时翻开的"电话本"。按数据类型组织，快速找到对应函数和参数。
> 完整文档见 [AKShare 官方文档](https://akshare.akfamily.xyz/data/stock/stock.html)。

---

## 目录

- [A 股行情](#a-股行情)
- [ETF 行情](#etf-行情)
- [指数数据](#指数数据)
- [指数成分股](#指数成分股)
- [板块/概念](#板块概念)
- [资金流向](#资金流向)
- [财务数据](#财务数据)
- [沪深港通](#沪深港通)
- [涨跌停 / 龙虎榜](#涨跌停--龙虎榜)
- [宏观数据](#宏观数据)
- [复权处理速查](#复权处理速查)
- [常用标的代码](#常用标的代码)

---

## A 股行情

### 日线历史

推荐通过 `data_fetcher.fetch_stock_data()` 统一获取（自动尝试东财 → 回退腾讯）：

```python
from data_fetcher import fetch_stock_data
df = fetch_stock_data(symbol="600519", start_date="20210101")
```

直接调用 AKShare 接口：

```python
import akshare as ak

df = ak.stock_zh_a_hist(
    symbol="600519",      # 股票代码，不带后缀
    period="daily",       # daily / weekly / monthly
    start_date="20210101", # 格式 YYYYMMDD
    end_date="20260101",
    adjust="qfq"          # qfq(前复权) / hfq(后复权) / ""(不复权)
)
```

| 参数 | 说明 |
|------|------|
| `symbol` | 如 `"000001"`、`"600519"`，**不带** `.SS` / `.SZ` 后缀 |
| `period` | `"daily"` / `"weekly"` / `"monthly"` |
| `start_date` / `end_date` | **`YYYYMMDD`** 格式（不是 `YYYY-MM-DD`） |
| `adjust` | `"qfq"` 前复权（推荐回测用）、`"hfq"` 后复权、`""` 不复权 |

**返回列：**

| 列名 | 含义 |
|------|------|
| 日期 | 交易日（自动设为 index） |
| 开盘 / 收盘 / 最高 / 最低 | OHLC |
| 成交量 / 成交额 | 单位：手 / 元 |
| 振幅 / 涨跌幅 / 涨跌额 | 百分比 / 元 |
| 换手率 | 百分比 |

### 实时全量行情

```python
# 沪深京全部 A 股实时行情（5000+ 行）
df = ak.stock_zh_a_spot_em()
# 沪市
df = ak.stock_sh_a_spot_em()
# 深市
df = ak.stock_sz_a_spot_em()
# 北交所
df = ak.stock_bj_a_spot_em()
```

返回 23 列：序号、代码、名称、最新价、涨跌幅、涨跌额、成交量、成交额、振幅、最高、最低、今开、昨收、量比、换手率、市盈率-动态、市净率、总市值、流通市值、涨速、5分钟涨跌、60日涨跌幅、年初至今涨跌幅。

**应用场景：** 全市场扫描选股、实时监控、计算全市场涨跌分布。

### 个股信息

```python
# 东方财富源 — 总股本 / 流通股 / 行业 / 上市时间
info = ak.stock_individual_info_em(symbol="000001")

# 雪球源 — 更详细的公司基本面（法人、员工数、业务介绍等）
info = ak.stock_individual_basic_info_xq(symbol="SH601127")  # 需要市场前缀
```

### 行情报价（五档）

```python
df = ak.stock_bid_ask_em(symbol="000001")
# 返回：买一~买五价量、卖一~卖五价量、最新、均价、涨幅、总手等
```

---

## ETF 行情

### `data_fetcher` 统一入口（推荐，自动回退）

本 vault 所有策略代码通过 `01-data/code/data_fetcher.py` 获取数据：

```python
from data_fetcher import fetch_etf_data, fetch_stock_data

# ETF（自动选择可用数据源）
df = fetch_etf_data(symbol="510300", start_date="20210101")

# A 股
df = fetch_stock_data(symbol="600519", start_date="20210101")
```

**数据源策略：**
1. 优先尝试东方财富（支持 `adjust` 原生复权）
2. 不可达时自动回退到新浪（ETF）或腾讯（A 股），并自动处理拆股修正

**返回格式统一：** DatetimeIndex + `Open/High/Low/Close/Volume` 列。

### 东财源（原生支持复权）

```python
df = ak.fund_etf_hist_em(
    symbol="510300",      # ETF 代码
    period="daily",
    start_date="20210101",
    end_date="20260101",
    adjust="qfq"          # 支持复权！
)
```

**优势：** 原生支持 `adjust` 参数，不需要手动处理复权。
**列名：** 日期、开盘、收盘、最高、最低、成交量、成交额、振幅、涨跌幅、换手率等。

### 新浪源（需手动处理拆股/复权）

```python
df = ak.fund_etf_hist_sina(symbol="sh510300")  # 需要 "sh" / "sz" 前缀
```

| 特点 | 说明 |
|------|------|
| 前缀 | `"sh"` 上海、`"sz"` 深圳 |
| 复权 | ❌ **不支持**，返回原始价格 |
| 拆股 | 需手动修正（见 [[#复权处理速查]]） |
| 列名 | 英文：`date, open, close, high, low, volume` |

---

## 指数数据

### 指数日线

```python
# 新浪源（数据最早，但列名英文）
df = ak.stock_zh_index_daily(symbol="sz399552")   # 需 "sh"/"sz" + 代码

# 东方财富源（含成交额）
df = ak.stock_zh_index_daily_em(symbol="sz399552")  # 格式同上

# 腾讯源（支持自定义时间范围）
df = ak.stock_zh_index_daily_tx(symbol="sh000001", start_date="20260101", end_date="20260401")

# 东财通用接口（支持周/月，含技术指标列）
df = ak.index_zh_a_hist(
    symbol="000016",       # 指数代码，不带市场标识
    period="daily",        # daily / weekly / monthly
    start_date="20210101",
    end_date="20260101"
)  # 返回含 涨跌幅/振幅/换手率
```

| 函数 | 数据源 | 支持周期 | 复权 | 特点 |
|------|--------|---------|------|------|
| `stock_zh_index_daily` | 新浪 | 日 | N/A | 历史最全，列名英文 |
| `stock_zh_index_daily_em` | 东财 | 日 | N/A | 含 amount(成交额) |
| `stock_zh_index_daily_tx` | 腾讯 | 日 | N/A | 可自定义起止日期 |
| `index_zh_a_hist` | 东财 | 日/周/月 | N/A | 含涨跌幅/振幅/换手率 |

### 指数实时行情

```python
# 东财（按系列分类）
df = ak.stock_zh_index_spot_em(symbol="上证系列指数")
# symbol 可选: "沪深重要指数" / "上证系列指数" / "深证系列指数" / "中证系列指数"

# 新浪（全量，557+ 指数）
df = ak.stock_zh_index_spot_sina()  # 含 sh/sz 前缀代码
```

### 全球指数

```python
# 实时
df = ak.index_global_spot_em()

# 历史
df = ak.index_global_hist_em(symbol="美元指数")
df = ak.index_global_hist_sina(symbol="瑞士股票指数")
```

---

## 指数成分股

```python
# 获取指数成分股列表（如沪深300）
cons = ak.index_stock_cons(symbol="000300")

# 更稳定的替代接口
cons = ak.index_stock_cons_sina(symbol="000300")
cons = ak.index_stock_cons_csindex(symbol="000300")  # 中证指数官网

# 查看有哪些指数
index_info = ak.index_stock_info()
```

**常见指数代码：**

| 指数 | 代码 |
|------|------|
| 上证指数 | 000001 |
| 上证50 | 000016 |
| 沪深300 | 000300 |
| 中证500 | 000905 |
| 中证1000 | 000852 |
| 创业板指 | 399006 |
| 科创50 | 000688 |

---

## 板块/概念

### 概念板块

```python
# 概念板块列表
df = ak.stock_board_concept_name_em()

# 概念成分股
df = ak.stock_board_concept_cons_em(symbol="AI概念")   # 板块名称

# 概念板块实时行情
df = ak.stock_board_concept_spot_em()
```

### 行业板块

```python
# 行业板块列表
df = ak.stock_board_industry_name_em()

# 行业成分股
df = ak.stock_board_industry_cons_em(symbol="半导体")  # 板块名称

# 行业板块实时行情
df = ak.stock_board_industry_spot_em()
```

**应用场景：**
- 板块轮动策略：获取某概念所有成分股，计算板块整体强度
- 选股池过滤：只交易特定板块（如半导体、AI）的股票

---

## 资金流向

```python
# 个股资金流向（日频）
df = ak.stock_individual_fund_flow(
    stock="000001",
    market="sz"            # sh / sz / bj
)

# 行业板块资金流向
df = ak.stock_sector_fund_flow_rank(
    indicator="今日",       # 今日 / 3日 / 5日 / 10日
    sector_type="行业资金流向"
)

# 概念板块资金流向
df = ak.stock_sector_fund_flow_rank(
    indicator="今日",
    sector_type="概念资金流向"
)
```

**返回列：** 名称、最新价、涨跌幅、主力净流入、超大单净流入、大单净流入、中单净流入、小单净流入等。

**应用场景：** 主力资金监控、板块资金轮动。

---

## 财务数据

### 三大报表

```python
# 利润表
df = ak.stock_profit_sheet_by_report_em(
    symbol="600519",
    date="20231231"        # 财报截止日
)

# 资产负债表
df = ak.stock_balance_sheet_by_report_em(symbol="600519")

# 现金流量表
df = ak.stock_cash_flow_sheet_by_report_em(symbol="600519")
```

### 关键财务指标

```python
# 新浪
df = ak.stock_financial_abstract_sina(symbol="600519")

# 同花顺（更详细）
df = ak.stock_financial_abstract_ths(symbol="600519")

# 东财主要指标
df = ak.stock_main_fund_em(symbol="600519")  # ROE / EPS / 每股净资产等
```

### 业绩数据

```python
# 业绩报表（季报/年报）
df = ak.stock_yjbb_em(date="20231231")

# 业绩快报
df = ak.stock_yjkb_em(date="20231231")

# 业绩预告
df = ak.stock_yjyg_em(date="20231231")
```

---

## 沪深港通

```python
# 北向资金净流入（日频）
df = ak.stock_hsgt_north_net_flow_in_em(symbol="沪股通")
# symbol 可选: "沪股通" / "深股通"

# 沪深港通每日统计（个股）
df = ak.stock_hsgt_stock_statistics_em(
    symbol="沪股通",
    start_date="20250101",
    end_date="20250601"
)

# 沪深港通持股排行
df = ak.stock_hsgt_hold_stock_em(market="沪股通", indicator="今日排行")
```

---

## 涨跌停 / 龙虎榜

### 涨停/跌停池

```python
# 涨停股池（当日）
df = ak.stock_zt_pool_em(date="20250614")

# 昨日涨停股池
df = ak.stock_zt_pool_previous_em(date="20250614")

# 强势股池
df = ak.stock_zt_pool_strong_em(date="20250614")

# 炸板股池
df = ak.stock_zt_pool_zban_em(date="20250614")

# 跌停股池
df = ak.stock_zt_pool_dtgc_em(date="20250614")

# 次新股池
df = ak.stock_zt_pool_secondary_em(date="20250614")
```

### 龙虎榜

```python
# 龙虎榜每日明细
df = ak.stock_lhb_detail_em(
    start_date="20250601",
    end_date="20250614"
)

# 营业部排行
df = ak.stock_lhb_jgmm_tmall_em()
```

**应用场景：** 市场情绪分析、短线选股、热点追踪。

---

## 宏观数据

```python
# LPR 利率
df = ak.macro_china_lpr()

# CPI
df = ak.macro_china_cpi_monthly()

# PPI
df = ak.macro_china_ppi_monthly()

# GDP
df = ak.macro_china_gdp()

# 存款准备金率
df = ak.macro_china_reserve_requirement_ratio()

# PMI
df = ak.macro_china_pmi()
```

---

## 复权处理速查

### 参数对照

| adjust 值 | 含义 | 回测适用 |
|-----------|------|---------|
| `"qfq"` | 前复权（向前调整） | ✅ 推荐 |
| `"hfq"` | 后复权（向后调整） | ⚠️ 用于计算真实累计收益 |
| `""` | 不复权（原始价格） | ❌ 含除权缺口 |

### 不同接口的复权支持

| 接口 | 复权参数 | 说明 |
|------|---------|------|
| `stock_zh_a_hist()` | ✅ `adjust=` | A股日线，直接传参 |
| `fund_etf_hist_em()` | ✅ `adjust=` | ETF日线，直接传参 |
| `fund_etf_hist_sina()` | ❌ 不支持 | 需手动处理 |
| `stock_zh_index_daily()` | N/A | 指数不存在复权问题 |

### `data_fetcher` 自动处理

`data_fetcher.fetch_etf_data()` 内部自动检测拆股事件（单日价格波动 > 50%），并将此前所有价格按比例前复权。无需手动处理。

### 新浪源手动修正拆股

```python
# 示例：纳指 100 ETF (513100) 2022-01-14 1:5 拆股
df = ak.fund_etf_hist_sina(symbol="sh513100")
df['date'] = pd.to_datetime(df['date'])
df = df.set_index('date')

# 拆股前价格 ÷ 5
df.loc[df.index < '2022-01-14', 'close'] /= 5
df.loc[df.index < '2022-01-14', ['open', 'high', 'low']] /= 5
```

---

## 常用标的代码

### ETF

| 代码 | 名称 | 跟踪指数 |
|------|------|---------|
| 510300 | 沪深300ETF | 沪深300 |
| 510500 | 中证500ETF | 中证500 |
| 159915 | 创业板ETF | 创业板指 |
| 512100 | 中证1000ETF | 中证1000 |
| 510050 | 上证50ETF | 上证50 |
| 513100 | 纳指100ETF | 纳斯达克100 |
| 518880 | 黄金ETF | 黄金 |

### A 股

| 代码 | 名称 |
|------|------|
| 600519 | 贵州茅台 |
| 000858 | 五粮液 |
| 601318 | 中国平安 |
| 000001 | 平安银行 |
| 600036 | 招商银行 |
| 300750 | 宁德时代 |
| 000333 | 美的集团 |

### 指数

| 代码 | 名称 |
|------|------|
| sh000001 | 上证指数 |
| sh000016 | 上证50 |
| sz399006 | 创业板指 |
| sh000688 | 科创50 |
| sh000300 | 沪深300 |
| sh000905 | 中证500 |

---

## 相关笔记

- [[akshare-basics|akshare 数据获取基础]] — 入门教程 / demo
- [[../deep/forward-vs-backward-adjustment|前复权 vs 后复权]] — 复权概念深挖
- [[../../02-backtest/notes/dca-backtest|DCA 定投回测]]
- [[../../02-backtest/notes/ma-crossover-backtest|均线交叉策略回测]]
- [[../../02-backtest/notes/macro-analysis|三资产宏观分析]]
- [[../../02-backtest/notes/portfolio-allocation|组合分配系列笔记（入口）]]
