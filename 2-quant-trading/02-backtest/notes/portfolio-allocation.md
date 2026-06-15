---
tags: [量化, 回测, 组合, 风险平价, 动量, 资产配置]
date: 2026-06-15
---

# 组合分配：等权 vs 风险平价 vs 动量排名

## 目标

在前文三资产（沪深300 / 纳指100 / 黄金）等权组合的基础上，引入**风险平价**和**动量排名**两种分配方法，做系统性对比。

核心问题：**权重怎么分比 1/3 更好？**

---

## 三种分配思想

| 方法 | 核心逻辑 | 一句话 |
|------|---------|--------|
| **等权** | 1/n | 简单、稳健 |
| **风险平价** | 波动率倒数 | 低波多配、高波少配 |
| **动量排名** | 动量 ÷ 波动率 (ram) | 选涨得稳的买 |

---

## 数学原理

> 以下公式直接给出结论。完整的推导链条（从"等权 ≠ 等风险"到波动率倒数加权）见独立文章：
> [[../deep/risk-parity-derivation|风险平价数学推导 — 从零到公式]]

### 风险平价（Risk Parity）

#### 基本定义

记 $w_i$ 为资产 $i$ 的权重，$\Sigma$ 为 $n \times n$ 协方差矩阵（$\Sigma_{ij} = \sigma_i \sigma_j \rho_{ij}$），组合方差为：

$$
\sigma_p^2 = w^\mathsf{T} \Sigma w = \sum_{i=1}^{n} \sum_{j=1}^{n} w_i w_j \sigma_i \sigma_j \rho_{ij}
$$

#### 风险贡献的分解

边际风险贡献（Marginal Risk Contribution, MRC）——权重 $w_i$ 增加一个微小量时，组合波动率的变化：

$$
\operatorname{MRC}_i = \frac{\partial \sigma_p}{\partial w_i}
= \frac{(\Sigma w)_i}{\sigma_p}
= \frac{\sum_{j=1}^{n} w_j \sigma_i \sigma_j \rho_{ij}}{\sigma_p}
$$

总风险贡献（Risk Contribution, RC）——资产 $i$ 对组合总波动的贡献额（满足 $\sum \operatorname{RC}_i = \sigma_p$）：

$$
\operatorname{RC}_i = w_i \cdot \frac{\partial \sigma_p}{\partial w_i}
= \frac{w_i (\Sigma w)_i}{\sigma_p}
$$

#### 风险平价条件

风险平价要求 **每类资产的风险贡献相等**：

$$
\operatorname{RC}_1 = \operatorname{RC}_2 = \cdots = \operatorname{RC}_n
$$

即：

$$
\frac{w_1 (\Sigma w)_1}{\sigma_p} = \frac{w_2 (\Sigma w)_2}{\sigma_p} = \cdots = \frac{w_n (\Sigma w)_n}{\sigma_p}
$$

消去 $\sigma_p$：

$$
w_1 (\Sigma w)_1 = w_2 (\Sigma w)_2 = \cdots = w_n (\Sigma w)_n
$$

#### 两资产特例的解析解

设只有两个资产，相关性为 $\rho$：

$$
\sigma_p = \sqrt{w_1^2 \sigma_1^2 + w_2^2 \sigma_2^2 + 2 w_1 w_2 \sigma_1 \sigma_2 \rho}
$$

$$
\operatorname{RC}_1 = \frac{w_1 (w_1 \sigma_1^2 + w_2 \sigma_1 \sigma_2 \rho)}{\sigma_p}, \quad
\operatorname{RC}_2 = \frac{w_2 (w_2 \sigma_2^2 + w_1 \sigma_1 \sigma_2 \rho)}{\sigma_p}
$$

令 $\operatorname{RC}_1 = \operatorname{RC}_2$：

$$
w_1 (w_1 \sigma_1^2 + w_2 \sigma_1 \sigma_2 \rho) = w_2 (w_2 \sigma_2^2 + w_1 \sigma_1 \sigma_2 \rho)
$$

**当 $\rho = 0$（资产不相关）** 时，简化为：

$$
w_1^2 \sigma_1^2 = w_2^2 \sigma_2^2 \quad\Longrightarrow\quad w_1 \sigma_1 = w_2 \sigma_2 \quad\Longrightarrow\quad \frac{w_1}{w_2} = \frac{\sigma_2}{\sigma_1}
$$

这就是 **波动率倒数加权**：

$$
w_i \propto \frac{1}{\sigma_i}
$$

**当 $\rho \neq 0$** 时，上述等式变为一个非线性方程组，无封闭解，需要数值求解（通常用牛顿法或 SQP 优化）。

#### `RiskParityOptimizer` 的实现等价于什么？

`RiskParityOptimizer(volatility_col="vol")` 的代码是：

```python
inv_vols[symbol] = 1.0 / vol
total = sum(inv_vols.values())
return {symbol: iv / total for symbol, iv in inv_vols.items()}
```

这等价于在 **假设 $\rho = 0$** 的前提下求解 $w_i \propto 1/\sigma_i$。这是风险平价的零阶近似。

#### 数学层面的局限性

1. **相关性被忽略**：假设 $\rho = 0$ 是强假设。当资产间相关性为负时（如股债跷跷板），真正的风险平价应该给这两类资产更高权重（因为它们互相 hedging），但简化版会低估它们。
2. **$\sigma$ 的估计误差会被平方放大**：RC 中包含 $\sigma_i^2$ 项，$\sigma$ 的 10% 估计误差会导致 RC 的约 20% 误差。
3. **不考虑期望收益**：如果低波资产长期不涨（如 2010-2020 的 A 股），风险平价只是"系统性地把资金配置到不赚钱的资产上"。
4. **权重的波动率倒数线性**：$\sigma \to 0$ 时 $w \to \infty$（无杠杆约束下发散），$\sigma \to \infty$ 时 $w \to 0$（但不会完全剔除）。

---

### 动量排名（Momentum Ranking）

#### 动量定义

对数动量（log-momentum）：

$$
\operatorname{mom}_t(N) = \frac{\ln P_t - \ln P_{t-N}}{N}
$$

展开为日度对数收益率的均值：

$$
\operatorname{mom}_t(N) = \frac{1}{N} \sum_{k=1}^{N} r_{t-k+1}, \quad\text{where}\quad r_t = \ln\frac{P_t}{P_{t-1}}
$$

对于小幅价格变动，$\ln(1+x) \approx x$，所以 $\operatorname{mom}_t(N) \approx \frac{1}{N}\left(\frac{P_t - P_{t-N}}{P_{t-N}}\right)$，即近似等于简单收益率的日均值。

**为什么用对数价格？** 对数收益率在时间上可加，计算多期收益率只需相加，且其分布更接近正态。

#### 波动率定义

样本标准差（ddof=1，即无偏估计）：

$$
\operatorname{vol}_t(N) = \sqrt{\frac{1}{N-1} \sum_{k=1}^{N} (r_{t-k+1} - \bar{r}_t)^2}
$$

其中 $\bar{r}_t = \frac{1}{N} \sum_{k=1}^{N} r_{t-k+1}$。

#### RAM 分数

$$
\operatorname{ram}_t(N) = \frac{\operatorname{mom}_t(N)}{\operatorname{vol}_t(N)}
$$

量纲分析：
- $\operatorname{mom}$ 量纲：$\text{return} / \text{time}$，即 $[\text{T}^{-1}]$
- $\operatorname{vol}$ 量纲：$\text{return} / \sqrt{\text{time}}$，即 $[\text{T}^{-1/2}]$
- $\operatorname{ram}$ 量纲：$[\text{T}^{-1/2}]$，即 $\frac{1}{\sqrt{\text{day}}}$

乘以 $\sqrt{252}$ 可年化。但排名时只需相对大小，量纲常数不影响排序。

**RAM 的本质**：这是动量因子的**信噪比（Signal-to-Noise Ratio, SNR）**。

$$
\operatorname{SNR} = \frac{\text{信号强度}}{\text{噪声幅度}} = \frac{\text{趋势}}{\text{随机波动}}
$$

RAM 越高，说明该资产的上涨趋势越强且越稳定（相对于其随机波动）。

#### `TopNRankingOptimizer` 的数学逻辑

记 $S = \{i \mid \operatorname{ram}_i > 0\}$ 为所有 ram 为正的资产集合。

$$
w_i = \begin{cases}
\dfrac{\operatorname{ram}_i}{\sum_{j \in S} \operatorname{ram}_j}, & i \in S \\[6pt]
0, & i \notin S
\end{cases}
$$

如果 $\sum_{j \in S} \operatorname{ram}_j = 0$ 或 $S = \varnothing$，则全部配置到现金（`{"CASH": 1.0}`）。

`max_weight` 参数（默认 1.0）会截断单个权重的上限，超出部分按比例回退到现金。

#### `filter_negative` 的数学后果

```
filter_negative=True → 激活阶跃函数在 ram = 0 处：
  w(ram) = ram⁺ / sum(ram⁺)    (其中 ram⁺ = max(ram, 0))
```

这个阶跃导致权重函数 $\frac{\partial w}{\partial \text{ram}}$ 在 $\text{ram}=0$ 处不连续。两只资产 ram 分别为 +0.001 和 -0.001，一只获得正权重，另一只权重为 0。这种不连续性可能引发 **边界翻转效应**——微小的数据变化导致剧烈的权重切换（也是动量排名调仓频繁的数学根源）。

#### 数学层面的局限性

1. **动量持续性假设**：$\operatorname{ram}_t$ 预测 $\operatorname{ram}_{t+1}$ 的前提是动量因子在时间上自相关。如果市场风格切换（动量因子崩溃，如 2009 年 3 月的美国市场），RAM 排名会给出完全相反的信号。
2. **横截面独立性假设**：各资产 ram 分数被视为独立，但实际中资产间的相关性会导致同一时期多个资产同时具有正 ram（或负 ram），排名优化器无法处理这种集中度的风险——它只按分数排序，不看仓位之间的相关性。
3. **估计误差的非线性传播**：设真实波动率为 $\sigma^*$，估计值为 $\hat{\sigma} = \sigma^* + \varepsilon$，则：

$$
\widehat{\operatorname{ram}} = \frac{\operatorname{mom}}{\hat{\sigma}} = \frac{\operatorname{mom}}{\sigma^*} \cdot \frac{1}{1 + \varepsilon / \sigma^*} \approx \operatorname{ram}^* \left(1 - \frac{\varepsilon}{\sigma^*}\right)
$$

当 $\sigma^*$ 本身很小（低波动环境）时，$\varepsilon / \sigma^*$ 被放大，RAM 估计的噪声极大。
4. **参数敏感性**：$N=20$ 是经验值。当 $N$ 过小时，ram 被短期噪声主导；过大时，ram 对趋势变化的响应滞后。且在 $N$ 较小的极端情况下，$\operatorname{vol}_t(N)$ 的自由度过低导致估计方差爆炸。
5. **非平稳性**：$\operatorname{ram}_t$ 不是一个平稳过程。在趋势市场中 ram 持续为正，在震荡市场中 ram 围绕 0 摆动。用历史 ram 预测未来 ram 在制度切换时失效。

---

## 代码实现：一个 COMMON，三个策略

**核心设计：把所有指标注册在同一个信号上，三个策略共享 COMMON，只换 `portfolio=`。**

```python
from oxq.portfolio.optimizers import (
    EqualWeightOptimizer, RiskParityOptimizer, TopNRankingOptimizer,
)
from oxq.signals import Threshold
from oxq.indicators import RollingVolatility, Momentum, Ratio
from oxq.core import Strategy

# 一个信号承载全部指标（三个策略共享）
signal = Threshold()
signal.required_indicators = {
    "mom": (Momentum(), {"column": "close", "period": 20}),
    "vol": (RollingVolatility(), {"column": "close", "period": 20}),
    "ram": (Ratio(), {"col_a": "mom", "col_b": "vol"}),
}

# 公共配置
COMMON = dict(
    universe=universe,
    signals={
        "signal": (signal, {"column": "close", "threshold": 0, "relationship": "gt"}),
    },
)

# 三个策略只在 portfolio 一行不同：
strategies = {
    "equal-weight": Strategy(name="equal-weight", **COMMON, portfolio=EqualWeightOptimizer()),
    "risk-parity": Strategy(name="risk-parity", **COMMON, portfolio=RiskParityOptimizer(volatility_col="vol")),
    "momentum-rank": Strategy(name="momentum-rank", **COMMON, portfolio=TopNRankingOptimizer(score_col="ram", n=3, filter_negative=True)),
}
```

**为什么可以共享？**
- `EqualWeightOptimizer` 不看指标列，只数信号数量
- `RiskParityOptimizer(volatility_col="vol")` 只看 `vol` 列
- `TopNRankingOptimizer(score_col="ram")` 只看 `ram` 列
- 三者互不冲突，一个信号一次计算，三条优化器各取所需

---

## 回测结果

### 回测设置

| 参数 | 值 |
|------|-----|
| 标的 | 510300(沪深300) / 513100(纳指100) / 518880(黄金) |
| 时间窗 | 2021-01-01 ~ 2025-12-31（5年） |
| 初始资金 | 100,000 元 |
| 再平衡 | 每日（优化器每 bar 调用） |
| 交易成本 | 未考虑 |

### 回测指标对比

| 指标 | 等权 | 风险平价 | **动量排名** |
|------|------|---------|------------|
| **累计收益率** | +76.95% | +93.37% | **+152.76%** |
| **年化收益率** | +12.61% | +14.71% | **+21.28%** |
| **年化波动率** | 11.94% | 10.41% | **14.06%** |
| **夏普比率** | 1.06 | 1.37 | **1.44** |
| **最大回撤** | -16.13% | -12.00% | **-9.85%** |
| **卡尔玛比率** | 0.78 | 1.23 | **2.16** |

### 最新一日权重对比

| 标的 | 等权 | 风险平价 | 动量排名 | 等权(¥10万) | 风险平价(¥10万) | 动量排名(¥10万) |
|------|------|---------|---------|------------|---------------|----------------|
| **沪深300** | 33.3% | 42.5% | **61.2%** | 33,333 | 42,521 | **61,210** |
| **纳指100** | 33.3% | 29.7% | **0.0%** | 33,333 | 29,678 | **0** |
| **黄金** | 33.3% | 27.8% | **38.8%** | 33,333 | 27,801 | **38,790** |

> 最新一日纳指100 ram = -0.16（负动量），`filter_negative=True` 将其剔除。

---

## 各策略权重年度演变

### 风险平价

| 年份 | 沪深300 | 纳指100 | 黄金 |
|------|---------|---------|------|
| 2021末 | 33.3% | 20.4% | 46.3% |
| 2022末 | 31.9% | 25.0% | 43.1% |
| 2023末 | 28.0% | 29.8% | 42.2% |
| 2024末 | 31.1% | 19.3% | 49.6% |
| 2025末 | 42.5% | 29.7% | 27.8% |

### 动量排名

| 年份 | 沪深300 | 纳指100 | 黄金 |
|------|---------|---------|------|
| 2021末 | 11.3% | 31.0% | 57.7% |
| 2022末 | 34.9% | 0.0% | 65.1% |
| 2023末 | 0.0% | 75.3% | 24.7% |
| 2024末 | 0.0% | **100.0%** | 0.0% |
| 2025末 | 61.2% | 0.0% | 38.8% |

**动量排名的特征极其鲜明：**

- **集中持仓**：平均只持有 1.7 个标的（风险平价 2.9 个）
- **全仓单一资产**：2024 年末全部押在纳指100（ram 排名最高）
- **快速切换**：2022 年沪深300被剔除时换到黄金，2023 年又切到纳指100

---

## 动量排名 vs 风险平价：本质区别

```
风险平价:
  永远满仓，权重随波动率缓慢变化
  → "配"的逻辑：低波多配、高波少配
  → 持仓稳定，调仓温和

动量排名:
  不满仓，ram 为负的剔除，ram 为正的按分数配
  → "选"的逻辑：只买涨得好的
  → 持仓集中，调仓剧烈
```

### 动量排名在 2024 年做了什么？

2024 年纳指100大幅上涨（+35%+），其 ram 分数持续为正且最高，动量排名给出 100% 权重。
而风险平价因为纳指100波动率高，只给了 19.3%——**这正是两种思想的分水岭**：

- 风险平价怕波动 → 低配了纳指100
- 动量排名要动量 → 全仓了纳指100

结果 2024 年动量排名大胜。但也要注意：**如果 2024 年是纳指100大跌，动量排名也会全仓吃满跌幅**。

---

## 综合评价

| 维度 | 等权 | 风险平价 | 动量排名 |
|------|------|---------|---------|
| **收益** | 🟡 中 | 🟢 高 | 🔥 最高 |
| **风险控制** | 🟡 中 | 🟢 最好 | 🟡 中等（集中度高） |
| **夏普比率** | 🟡 中 | 🟢 高 | 🟢 最高 |
| **回撤控制** | 🟡 -17% | 🟢 -12% | 🔥 -10% |
| **调仓频率** | 🟢 低 | 🟡 中 | 🔴 高 |
| **理解难度** | 🟢 简单 | 🟡 中等 | 🟡 中等 |
| **行为风险** | 🟢 容易坚持 | 🟢 容易坚持 | 🔴 大幅切换考验心态 |

> **夏普最高不代表最安全**。动量排名在 2024 年 100% 持有纳指100的行为风险极高——如果纳指回调赶上切换不及时，回撤可能远超历史水平。

---

## 局限性

### 工程层面

1. **动量排名频繁空仓**：当所有资产 ram 为负时会空仓，但历史数据看这种情况很少
2. **动量排名集中度高**：平均只持有 1.7 个标的，分散效果有限
3. **交易成本**：大幅权重切换的成本未计入，动量排名的换手率远高于其他两种
4. **参数敏感性**：20 日窗口的 ram 分数对参数敏感
5. **未考虑相关性**：动量排名直接持有多只正相关资产（如 2023 年同时持有纳指 + 黄金）

### 数学层面（本文推导的延续）

#### 风险平价

1. **零相关假设**：`RiskParityOptimizer` 简化为 $w_i \propto 1/\sigma_i$，等价于假设 $\rho = 0$。当资产间存在显著相关性时（如上证50与沪深300的 $\rho > 0.8$），风险平价权重与实际风险贡献严重偏离。
2. **波动率估计的双重放大**：风险贡献 $\operatorname{RC}_i = w_i(\Sigma w)_i / \sigma_p$ 中 $w_i \propto 1/\sigma_i$，代入后 $\operatorname{RC}_i$ 的误差与 $\sigma_i$ 的估计误差成**平方关系**。$\sigma$ 估计偏大 20%，RC 会偏大约 40%。
3. **收益率不可知**：风险平价不引入任何收益率预期。如果低波动资产长期处于低收益状态（如 2010s 的发达国家国债），风险平价会系统性地配置到低收益资产上——"把风险分散了，但也把低收益分散到了整个组合"。
4. **杠杆隐式需求**：低波资产的风险贡献天然小，要实现风险平价，要么让低波资产配极高权重（上限可能被约束），要么给低波资产加杠杆。无杠杆版本的风险平价其实是次优解。

#### 动量排名

1. **排序的非连续性**：$w(\operatorname{ram}) = \operatorname{ram}^+ / \sum \operatorname{ram}^+$ 在 $\operatorname{ram}=0$ 处存在一阶跳跃。$|\operatorname{ram}| = 0.001$ 与 0 的差异决定了"全仓"还是"零仓"，这在数学上是病态的。
2. **波动率噪声放大**：当 $\sigma^* \to 0$ 时（低波动环境），$\widehat{\operatorname{ram}} \approx \operatorname{ram}^*(1 - \varepsilon/\sigma^*)$，$\varepsilon/\sigma^*$ 项发散。低波动资产的 RAM 分数信噪比极低。
3. **非平稳性**：$\operatorname{ram}_t$ 不是平稳过程。趋势市场 vs 震荡市场的 ram 分布截然不同。用固定阈值 $\operatorname{ram} > 0$ 作为过滤条件，在不同市场制度下的假阳性率差异极大。
4. **横截面维度缺失**：TopN 只做排序，不做组合优化。持有多只正 ram 资产时，它们之间的协方差完全不纳入考量。这本质上是一个**选股器**，不是一个**组合构建器**。

---

## 代码文件

- `02-backtest/code/risk_parity.py` — 完整回测脚本（三个策略）

## 相关笔记

- [[../deep/risk-parity-derivation|风险平价数学推导]] — 完整推导过程
- [[macro-analysis|三资产宏观分析]] — 前置：相关性分析 + 等权组合 baseline
- [[../../01-data/notes/akshare-basics|akshare 数据获取]] — 数据来源

## 下一步

- 均值-方差（Markowitz）优化 → 引入收益率预期
- 风险预算（Risk Budgeting）→ 手工指定各资产的风险占比
