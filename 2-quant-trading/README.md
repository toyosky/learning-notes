---
tags: [量化, 索引, MOC]
date: 2026-06-14
---

# 量化交易笔记

学习量化交易的笔记、代码和回测记录。

---

## 目录结构

```
2-quant-trading/
├── 01-data/                # 数据获取
│   ├── notes/              # 笔记
│   ├── deep/               # 深挖概念
│   └── code/               # 代码
├── 02-backtest/            # 策略回测
│   ├── notes/              # 笔记
│   ├── deep/               # 深挖概念
│   └── code/               # 代码
└── assets/                 # 图片资源
```

---

## 笔记索引

### 01-data（数据获取）

| 笔记 | 内容 |
|------|------|
| [[01-data/notes/akshare-basics\|akshare 数据获取]] | 用 akshare 替代 yfinance 获取 A 股/ETF 数据 |
| [[01-data/notes/akshare-reference\|akshare 接口速查]] | 按数据类型分类的策略开发参考手册 |
| [[01-data/deep/forward-vs-backward-adjustment\|前复权 vs 后复权]] | 复权概念深挖，对回测收益率的影响 |

### 02-backtest（策略回测）

| 笔记 | 内容 |
|------|------|
| [[02-backtest/notes/dca-backtest\|DCA 定投回测]] | 定投 + 均线择时策略回测 |
| [[02-backtest/notes/ma-crossover-backtest\|均线交叉策略回测]] | pandas 独立实现 + backtrader 框架对比 |
| [[02-backtest/notes/macro-analysis\|三资产宏观分析]] | 沪深300/纳指100/黄金 相关性 + 组合回测 |
| [[02-backtest/notes/portfolio-allocation\|组合分配系列笔记（入口）]] | 等权 vs 风险平价 vs 动量排名：数学推导→回测→风险管理 系统对比 |

---

## 学习路线

```
数据获取 → 简单策略 → 框架使用 → 进阶策略 → 宏观分析 → 组合分配
   ↓           ↓           ↓           ↓           ↓
akshare     DCA定投      backtrader  均线策略    三资产组合
   ↓                                       ↓           ↓
复权概念                              等权组合    风险平价
   ↓
动量排名
```

---

## 代码文件

| 文件 | 位置 |
|------|------|
| `data_fetcher.py` | 01-data/code/ |
| `dca_backtest.py` | 02-backtest/code/ |
| `ma_strategy.py` | 02-backtest/code/ |
| `etf_comparison.py` | 02-backtest/code/ |
| `generate_charts.py` | 02-backtest/code/ |
| `macro_analysis.py` | 02-backtest/code/ |
| `risk_parity.py` | 02-backtest/code/ |
| `etf_comparison_300_nasdaq.py` | 02-backtest/code/ |

---

## 后续计划

- [ ] 更多策略类型（动量、价值、套利）
- [x] 回测框架对比（oxq → backtrader 迁移完成）
- [ ] 实盘接入
- [ ] 风险管理
- [ ] 更多组合分配方法（均值-方差、动量加权）
