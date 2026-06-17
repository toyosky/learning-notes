---
tags: [量化, 回测, 组合, 风险平价, 动量, 资产配置, MOC]
date: 2026-06-15
---

# 组合分配系列笔记

> 在前文三资产（沪深300 / 纳指100 / 黄金）等权组合的基础上，引入**风险平价**和**动量排名**两种分配方法，做系统性对比。
> 核心问题：**权重怎么分比 1/3 更好？**

本文件是系列笔记的入口，详细内容按主题拆分到以下子笔记中。

---

## 系列结构

```
组合分配系列
│
├─ portfolio-overview          ← 【你在这里】三种方法总览与选型指南
│
├─ portfolio-results           ← 主回测结果、年度权重、逐月/逐年分析
│
├─ portfolio-rebalance         ← 再平衡频率与交易成本研究
│
├─ portfolio-risk              ← 止损/止盈保护与风险管理
│
├─ deep/risk-parity-intuition  ← 风险平价数学：直觉与组合方差
│
├─ deep/risk-parity-decomposition  ← 风险平价数学：MRC 与 RC 分解
│
├─ deep/risk-parity-solution   ← 风险平价数学：条件、求解与推广
│
├─ deep/momentum-ranking-derivation  ← 动量排名数学推导
│
└─ deep/bt-portfolio-allocation     ← 代码逐段讲解
```

---

## 快速入口

| 你想了解什么 | 去哪看 |
|-------------|--------|
| 三种方法的核心思想对比 | [[portfolio-overview\|方法总览]] |
| 哪个策略收益最高 | [[portfolio-results\|回测结果]] |
| 最优调仓频率是多少 | [[portfolio-rebalance\|再平衡研究]] |
| 止损到底有没有用 | [[portfolio-risk\|止损保护]] |
| 风险平价的数学推导 | [[../deep/risk-parity-solution\|风险平价求解]] |
| 动量排名的数学推导 | [[../deep/momentum-ranking-derivation\|动量排名推导]] |
| 代码实现细节 | [[../deep/bt-portfolio-allocation\|代码讲解]] |

---

## 相关笔记

- [[macro-analysis|三资产宏观分析]] — 前置：相关性分析 + 等权组合 baseline
- [[../deep/backtrader-intro|backtrader 核心概念速查]] — 回测框架基础
- [[dca-backtest|DCA 定投回测]] — 另一种策略类型
- [[../../01-data/notes/akshare-basics|akshare 数据获取]] — 数据来源
