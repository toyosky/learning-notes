---
tags: [量化, 数学, MPT, 有效前沿, 马科维茨, 资产配置]
date: 2026-06-18
---

# 有效前沿（Efficient Frontier）数学推导

> **写给谁**：了解概率论和线性代数基础，想深入理解马科维茨投资组合理论 (MPT) 数学推导的读者。
> **阅读目标**：从组合方差的基本定义出发，一步步推出有效前沿的数学表达式、解析解的条件，以及对实际应用的启示。

---

## 目录

- [1. 组合的基本数学工具](#1-组合的基本数学工具)
- [2. 分散化的数学本质](#2-分散化的数学本质)
- [3. 有效前沿的优化问题](#3-有效前沿的优化问题)
- [4. 两资产案例：有效前沿的解析解](#4-两资产案例有效前沿的解析解)
- [5. 全局最小方差组合（GMV）](#5-全局最小方差组合gmv)
- [6. 最大夏普组合（切线组合）](#6-最大夏普组合切线组合)
- [7. 一般情况下的有效前沿](#7-一般情况下的有效前沿)
- [8. 蒙特卡洛方法 vs 二次规划](#8-蒙特卡洛方法-vs-二次规划)
- [9. MPT 的固有局限](#9-mpt-的固有局限)
- [附录：向量/矩阵速查](#附录-向量矩阵速查)

---

## 1. 组合的基本数学工具

### 1.1 符号约定

设组合中有 $n$ 个资产：

| 符号 | 含义 | 维度 |
|------|------|------|
| $\mathbf{w}$ | 权重向量 | $n \times 1$ |
| $\boldsymbol{\mu}$ | 预期收益率向量 | $n \times 1$ |
| $\boldsymbol{\Sigma}$ | 协方差矩阵 | $n \times n$ |
| $\mathbf{1}$ | 全 1 向量 | $n \times 1$ |
| $\sigma_i$ | 资产 $i$ 的收益率标准差 | 标量 |
| $\rho_{ij}$ | 资产 $i$ 与 $j$ 的相关系数 | 标量 |

约束条件：$\mathbf{w}^T \mathbf{1} = \sum_{i=1}^{n} w_i = 1$（权重之和为 1）。

### 1.2 组合预期收益

$$
E(R_p) = \mathbf{w}^T \boldsymbol{\mu} = \sum_{i=1}^{n} w_i \mu_i
$$

### 1.3 组合方差

$$
\sigma_p^2 = \text{Var}(R_p) = \mathbf{w}^T \boldsymbol{\Sigma} \mathbf{w}
= \sum_{i=1}^{n} \sum_{j=1}^{n} w_i w_j \sigma_{ij}
$$

其中协方差矩阵的元素为：

$$
\sigma_{ij} = \text{Cov}(R_i, R_j) = \rho_{ij} \sigma_i \sigma_j
$$

特别地，当 $i = j$ 时，$\sigma_{ii} = \sigma_i^2$（方差）。

---

## 2. 分散化的数学本质

### 2.1 两资产情况

展开两资产组合（$n=2$）的方差公式：

$$
\sigma_p^2 = w_1^2 \sigma_1^2 + w_2^2 \sigma_2^2 + 2 w_1 w_2 \rho_{12} \sigma_1 \sigma_2
$$

因为 $w_2 = 1 - w_1$，上式是 $w_1$ 的二次函数。

### 2.2 分散化收益（Diversification Benefit）

组合的方差是否小于各资产方差的加权平均？比较：

$$
\sigma_p^2 \; \text{vs} \; w_1 \sigma_1^2 + w_2 \sigma_2^2
$$

将 $\sigma_p^2$ 展开代入，化简得：

$$
w_1 \sigma_1^2 + w_2 \sigma_2^2 - \sigma_p^2
= w_1 w_2 \left[ \sigma_1^2 + \sigma_2^2 - 2 \rho_{12} \sigma_1 \sigma_2 \right]
= w_1 w_2 (\sigma_1 - \sigma_2)^2 + 2 w_1 w_2 \sigma_1 \sigma_2 (1 - \rho_{12})
$$

当 $\rho_{12} < 1$ 且 $0 < w_1 < 1$ 时，上式恒为正。**只要资产间不完全正相关，组合的方差就一定小于各资产方差的加权平均。**

### 2.3 三种极端情况

**$\rho = 1$（完全正相关）：**

$$
\sigma_p^2 = w_1^2 \sigma_1^2 + (1-w_1)^2 \sigma_2^2 + 2 w_1 (1-w_1) \sigma_1 \sigma_2
= (w_1 \sigma_1 + (1-w_1) \sigma_2)^2
$$

$$\sigma_p = w_1 \sigma_1 + (1-w_1) \sigma_2$$

无分散化效果 — 组合风险就是加权平均。

**$\rho = -1$（完全负相关）：**

$$
\sigma_p^2 = w_1^2 \sigma_1^2 + (1-w_1)^2 \sigma_2^2 - 2 w_1 (1-w_1) \sigma_1 \sigma_2
= (w_1 \sigma_1 - (1-w_1) \sigma_2)^2
$$

令 $\sigma_p = 0$ 求解：

$$w_1 \sigma_1 = (1-w_1) \sigma_2 \implies w_1 = \frac{\sigma_2}{\sigma_1 + \sigma_2}$$

完全对冲，理论上的零风险组合。但在现实中几乎不存在这样的资产对。

**$\rho = 0$（不相关）：**

$$
\sigma_p^2 = w_1^2 \sigma_1^2 + (1-w_1)^2 \sigma_2^2
$$

最小方差权重（令偏导为 0）：

$$\frac{\partial \sigma_p^2}{\partial w_1} = 2 w_1 \sigma_1^2 - 2(1-w_1)\sigma_2^2 = 0$$

$$w_1^* = \frac{\sigma_2^2}{\sigma_1^2 + \sigma_2^2}$$

即**波动率平方的倒数加权**，这也是风险平价在两资产、零相关情况下的解析解。

### 2.4 多资产的一般情况

对于 $n$ 个资产，组合方差为：

$$\sigma_p^2 = \sum_{i=1}^{n} w_i^2 \sigma_i^2 + 2 \sum_{i < j} w_i w_j \rho_{ij} \sigma_i \sigma_j$$

交叉项的数量为 $\binom{n}{2} = n(n-1)/2$，当 $n$ 较大时，交叉项占总方差的比重远大于单个方差项。这意味着：

> **组合中资产越多，资产间的相关性对总风险的影响越大，单个资产的波动反而变得次要。**

---

## 3. 有效前沿的优化问题

### 3.1 二次规划的标准形式

马科维茨有效前沿通过求解以下**二次规划**得到：

$$
\begin{aligned}
\min_{\mathbf{w}} \quad & \frac{1}{2} \mathbf{w}^T \boldsymbol{\Sigma} \mathbf{w} \\
\text{s.t.} \quad & \mathbf{w}^T \boldsymbol{\mu} = R_{\text{target}} \\
& \mathbf{w}^T \mathbf{1} = 1
\end{aligned}
$$

目标函数中的 $1/2$ 仅为求导方便，不影响最优解。约束条件有两个：
1. 组合收益等于目标值 $R_{\text{target}}$
2. 权重之和为 1

### 3.2 拉格朗日乘子法

构造拉格朗日函数：

$$
\mathcal{L}(\mathbf{w}, \lambda_1, \lambda_2) = \frac{1}{2} \mathbf{w}^T \boldsymbol{\Sigma} \mathbf{w} + \lambda_1 (R_{\text{target}} - \mathbf{w}^T \boldsymbol{\mu}) + \lambda_2 (1 - \mathbf{w}^T \mathbf{1})
$$

一阶条件（对 $\mathbf{w}$ 求偏导）：

$$\frac{\partial \mathcal{L}}{\partial \mathbf{w}} = \boldsymbol{\Sigma} \mathbf{w} - \lambda_1 \boldsymbol{\mu} - \lambda_2 \mathbf{1} = \mathbf{0}$$

$$\boldsymbol{\Sigma} \mathbf{w} = \lambda_1 \boldsymbol{\mu} + \lambda_2 \mathbf{1}$$

$$\mathbf{w}^* = \lambda_1 \boldsymbol{\Sigma}^{-1} \boldsymbol{\mu} + \lambda_2 \boldsymbol{\Sigma}^{-1} \mathbf{1}$$

### 3.3 求解拉格朗日乘子

将 $\mathbf{w}^*$ 代入约束条件：

$$
\begin{aligned}
\mathbf{w}^{*T} \boldsymbol{\mu} &= \lambda_1 \boldsymbol{\mu}^T \boldsymbol{\Sigma}^{-1} \boldsymbol{\mu} + \lambda_2 \boldsymbol{\mu}^T \boldsymbol{\Sigma}^{-1} \mathbf{1} = R_{\text{target}} \\
\mathbf{w}^{*T} \mathbf{1} &= \lambda_1 \mathbf{1}^T \boldsymbol{\Sigma}^{-1} \boldsymbol{\mu} + \lambda_2 \mathbf{1}^T \boldsymbol{\Sigma}^{-1} \mathbf{1} = 1
\end{aligned}
$$

引入记法：

- $A = \boldsymbol{\mu}^T \boldsymbol{\Sigma}^{-1} \boldsymbol{\mu}$（标量）
- $B = \boldsymbol{\mu}^T \boldsymbol{\Sigma}^{-1} \mathbf{1}$（标量）
- $C = \mathbf{1}^T \boldsymbol{\Sigma}^{-1} \mathbf{1}$（标量）

则方程组为：

$$
\begin{cases}
A \lambda_1 + B \lambda_2 = R_{\text{target}} \\
B \lambda_1 + C \lambda_2 = 1
\end{cases}
$$

解得：

$$
\lambda_1 = \frac{C R_{\text{target}} - B}{AC - B^2}, \quad
\lambda_2 = \frac{A - B R_{\text{target}}}{AC - B^2}
$$

### 3.4 有效前沿的解析表达式

将 $\lambda_1, \lambda_2$ 代回 $\mathbf{w}^*$，得到对于给定 $R_{\text{target}}$ 的最优权重。此时最小方差为：

$$\sigma_p^2 = \mathbf{w}^{*T} \boldsymbol{\Sigma} \mathbf{w}^* = \frac{C R_{\text{target}}^2 - 2B R_{\text{target}} + A}{AC - B^2}$$

这是一个以 $R_{\text{target}}$ 为变量、$\sigma_p^2$ 为因变量的**二次函数**。将 $R_{\text{target}}$ 和 $\sigma_p$ 视为坐标，有效前沿在（风险，收益）平面上是**一条抛物线**（确切地说，在 $\sigma_p$-$E(R_p)$ 平面上是双曲线的一支）。

---

## 4. 两资产案例：有效前沿的解析解

对于两资产组合，可以直接推导出有效前沿的封闭形式，不需要矩阵工具。

### 4.1 收益与方差

设权重 $w_1 = w$，$w_2 = 1 - w$：

$$E(R_p) = w \mu_1 + (1-w) \mu_2$$

$$\sigma_p^2 = w^2 \sigma_1^2 + (1-w)^2 \sigma_2^2 + 2w(1-w) \rho \sigma_1 \sigma_2$$

### 4.2 参数化（以 $w$ 为参数）

当我们变化 $w$ 从 0 到 1，得到一组 $( \sigma_p(w), \, E(R_p)(w) )$ 点。这些点的集合就在（风险，收益）平面上构成了一条曲线 — 这就是有效前沿的**可行集**。

### 4.3 消去 $w$ 得到显示表达

从收益表达式反解 $w$：

$$w = \frac{E(R_p) - \mu_2}{\mu_1 - \mu_2}$$

代入方差表达式，得到 $E(R_p)$ 作为 $\sigma_p$ 的函数。当 $\rho \neq \pm 1$ 时，这个函数是一个**双曲线**。

### 4.4 最小方差点（GMV）

对 $\sigma_p^2$ 关于 $w$ 求导并令为 0：

$$\frac{\partial \sigma_p^2}{\partial w} = 2w \sigma_1^2 - 2(1-w) \sigma_2^2 + 2(1-2w) \rho \sigma_1 \sigma_2 = 0$$

解得：

$$w^* = \frac{\sigma_2^2 - \rho \sigma_1 \sigma_2}{\sigma_1^2 + \sigma_2^2 - 2 \rho \sigma_1 \sigma_2}$$

这就是两资产情况下全局最小方差组合的解析解。验证 $\rho = 0$ 时退化为 $w^* = \sigma_2^2 / (\sigma_1^2 + \sigma_2^2)$（即波动率平方倒数加权），与 2.3 节一致。

---

## 5. 全局最小方差组合（GMV）

### 5.1 解析解（无约束情况）

全局最小方差组合是有效前沿上的**最左侧点**，即方差最小的组合。在不引入额外约束（允许做空）的情况下，它有封闭的解析解：

$$\mathbf{w}_{GMV} = \frac{\boldsymbol{\Sigma}^{-1} \mathbf{1}}{\mathbf{1}^T \boldsymbol{\Sigma}^{-1} \mathbf{1}}$$

推导：在拉格朗日解中令 $R_{\text{target}}$ 自由优化，即对 $\sigma_p^2$ 关于 $R_{\text{target}}$ 求导，等价于在二次规划中忽略收益约束。另一种方式：在 3.4 节的解中取 $\sigma_p^2$ 对 $R_{\text{target}}$ 的极小值。

### 5.2 GMV 的预期收益和方差

将 $\mathbf{w}_{GMV}$ 代入收益和方差公式：

$$E(R_{GMV}) = \frac{\boldsymbol{\mu}^T \boldsymbol{\Sigma}^{-1} \mathbf{1}}{\mathbf{1}^T \boldsymbol{\Sigma}^{-1} \mathbf{1}}$$

$$\sigma_{GMV}^2 = \frac{1}{\mathbf{1}^T \boldsymbol{\Sigma}^{-1} \mathbf{1}}$$

### 5.3 加入做空限制

如果禁止做空（$w_i \geq 0$），GMV 没有解析解，需要数值求解。这是实践中更常见的情况。

直观理解：做空限制把可行的权重空间从整个 $\mathbb{R}^n$ 压缩到 $n$ 维单纯形 $\{ \mathbf{w} \geq 0, \, \sum w_i = 1 \}$，边界上的最优解通常落在约束的顶点或棱上。

---

## 6. 最大夏普组合（切线组合）

### 6.1 定义

夏普比率（Sharpe Ratio）定义为：

$$S_p = \frac{E(R_p) - R_f}{\sigma_p}$$

其中 $R_f$ 是无风险利率。当 $R_f = 0$ 时简化为 $E(R_p) / \sigma_p$。

最大夏普组合是有效前沿上使 $S_p$ 最大的点，即从 $(0, R_f)$ 点出发与有效前沿相切的射线对应的组合。

### 6.2 解析解

$$S_p = \frac{\mathbf{w}^T \boldsymbol{\mu} - R_f}{\sqrt{\mathbf{w}^T \boldsymbol{\Sigma} \mathbf{w}}}$$

最大化 $S_p$ 等价于最大化 $\frac{\mathbf{w}^T (\boldsymbol{\mu} - R_f \mathbf{1})}{\sqrt{\mathbf{w}^T \boldsymbol{\Sigma} \mathbf{w}}}$。

通过一阶条件可以推导出：

$$\mathbf{w}_{MSR} = \frac{\boldsymbol{\Sigma}^{-1} (\boldsymbol{\mu} - R_f \mathbf{1})}{\mathbf{1}^T \boldsymbol{\Sigma}^{-1} (\boldsymbol{\mu} - R_f \mathbf{1})}$$

这就是**切线组合（Tangency Portfolio）**的解析解。

### 6.3 资本市场线（CML）

当无风险资产存在时，有效前沿变为从 $(0, R_f)$ 出发通过切线组合的一条射线，称为**资本市场线（Capital Market Line, CML）**：

$$E(R_p) = R_f + \frac{E(R_{MSR}) - R_f}{\sigma_{MSR}} \sigma_p$$

CML 上的所有点都是无风险资产 $R_f$ 与切线组合的线性组合。投资者根据风险偏好选择 CML 上的不同位置。

### 6.4 重要观察

当 $R_f = 0$ 时，切线组合与 GMV 的关系：

- 如果 $\mathbf{w}_{MSR}$ 和 $\mathbf{w}_{GMV}$ 相同，说明收益最高的风险调整后策略就是最小方差策略（通常不会发生，因为这意味着所有资产的夏普比率相等）
- 在我们的三资产案例中，等权组合非常接近切线组合 — 意味着简单分配策略已经捕获了大部分分散化收益

---

## 7. 一般情况下的有效前沿

### 7.1 有效前沿 vs 可行集

**可行集**（Feasible Set）：所有可能权重组合对应的（风险，收益）点的集合。
**有效前沿**（Efficient Frontier）：可行集的上包络线 — 在每个风险水平上收益最高的点。

严格定义：

$$\mathcal{F} = \{ (\sigma_p, E(R_p)) \mid \mathbf{w}^T \mathbf{1} = 1, \, w_i \geq 0 \}$$

$$\mathcal{E} = \{ (\sigma_p, E(R_p)) \in \mathcal{F} \mid \nexists (\sigma'_p, E(R'_p)) \in \mathcal{F} \text{ s.t. } \sigma'_p \leq \sigma_p \text{ and } E(R'_p) \geq E(R_p) \}$$

### 7.2 为什么不含做空限制时前沿是双曲线

从 3.4 节的表达式：

$$\sigma_p^2 = \frac{C R_{\text{target}}^2 - 2B R_{\text{target}} + A}{AC - B^2}$$

整理成标准双曲线形式：

$$\frac{\sigma_p^2}{1/(AC-B^2)} - \frac{(R_{\text{target}} - B/C)^2}{(AC-B^2)/C^2} = 1$$

当 $AC - B^2 > 0$（组合中的资产不完全相关）时，有效前沿在（$\sigma$, $E(R)$）平面是双曲线的**上支**。

### 7.3 加入做空限制的影响

加入 $w_i \geq 0$ 约束后，有效前沿不再是平滑的双曲线，而是分段函数：
- 某些边界上，一个或多个资产的权重被锁定为 0
- 有效前沿可能是可行集凸包的一部分
- 通常需要数值求解

---

## 8. 蒙特卡洛方法 vs 二次规划

### 8.1 蒙特卡洛模拟

原理：随机生成大量权重向量 $\mathbf{w}^{(k)}$，计算每个的 $\sigma_p$ 和 $E(R_p)$，散点图的上包络线近似有效前沿。

**优点**：
- 直观、容易实现
- 天然支持任意约束（做空限制、行业集中度等）
- 散点图可以展示可行集的全貌

**缺点**：
- 精度有限，在 $n$ 较大时需要大量模拟才能逼近前沿
- 无法精确找到最优解
- 在高维空间中效率极低（维度灾难）

### 8.2 二次规划求解

使用优化器（如 `scipy.optimize.minimize`）精确求解。

**优点**：
- 高精度，保证收敛到最优解
- 效率高，$n$ 在 100 以内都很快速
- 可以得到精确的权重分配

**缺点**：
- 实现复杂度高
- 对约束类型的支持取决于求解器
- 只能给出最优解，不能直观展示可行集

### 8.3 实际选择

- **探索性分析**（2-5 个资产）：蒙特卡洛模拟更直观，可以看到全部的可行集
- **精确优化**（复杂约束、大量资产）：二次规划是必要工具
- **混合方法**：先用蒙特卡洛观察前沿形状，再用二次规划精确定位关键点（GMV、切线组合）

---

## 9. MPT 的固有局限

### 9.1 估计误差（Estimation Error）

MPT 使用历史数据估计 $\boldsymbol{\mu}$ 和 $\boldsymbol{\Sigma}$：

$$\hat{\boldsymbol{\mu}} = \frac{1}{T} \sum_{t=1}^{T} \mathbf{r}_t, \quad
\hat{\boldsymbol{\Sigma}} = \frac{1}{T-1} \sum_{t=1}^{T} (\mathbf{r}_t - \hat{\boldsymbol{\mu}})(\mathbf{r}_t - \hat{\boldsymbol{\mu}})^T$$

但 $\hat{\boldsymbol{\mu}}$ 的估计误差远大于 $\hat{\boldsymbol{\Sigma}}$。对于年化收益率，需要大约 30 年的数据才能以高置信度估计 $\boldsymbol{\mu}$，而 $\boldsymbol{\Sigma}$ 的估计在 2-3 年的数据中就相对稳定（Merton, 1980）。

**后果**：MPT 对输入参数极其敏感，尤其是 $\boldsymbol{\mu}$ 的微小变化会导致权重剧烈波动（Jobson & Korkie, 1980）。

### 9.2 参数敏感性的数学证明

设 $\mathbf{w}^*$ 为真实参数下的最优权重，$\hat{\mathbf{w}}$ 为估计参数下的最优权重。可以证明：

$$\mathbb{E}[||\hat{\mathbf{w}} - \mathbf{w}^*||^2] \approx \frac{n}{T-n} \cdot \frac{1}{S_p^2}$$

其中 $S_p^2$ 是真实夏普比率的平方。这意味着：
- 资产数量 $n$ 越大，估计误差越大
- 样本量 $T$ 越小，估计误差越大
- 真实夏普越低，估计误差越大（信噪比低）

这也是为什么**等权组合**在实践中常常优于优化组合的原因（DeMiguel, Garlappi & Uppal, 2009）。

### 9.3 结构突变与相关性上升

协方差矩阵 $\boldsymbol{\Sigma}$ 假设是**平稳**的，但金融市场存在结构突变：

- 正常时期：资产间相关性较低（如 $\rho \approx 0.1$），分散化效果好
- 危机时期：相关性急剧上升（如 $\rho \to 0.8$），分散化效果下降
- 2022 年全球资产普跌就是一个典型例子：股票和债券的正相关性飙升

这种**非对称相关性**是 MPT 框架无法捕捉的。

### 9.4 实践建议

1. **避免使用 $\hat{\boldsymbol{\mu}}$ 做优化**：估计误差太大。建议仅在此基础上优化 $\boldsymbol{\Sigma}$（如 GMV 组合）
2. **使用收缩估计（Shrinkage Estimation）**：对 $\hat{\boldsymbol{\Sigma}}$ 做正则化
3. **极端约束**：设置权重的上下限（如 $5\% \leq w_i \leq 40\%$），降低对参数的敏感度
4. **等权组合作为基准**：如果优化组合不能显著超越等权组合（通过交叉验证），就用等权
5. **Black-Litterman 模型**：将主观观点与市场均衡结合，降低对 $\boldsymbol{\mu}$ 估计的依赖

---

## 附录：向量/矩阵速查

| 表达式 | 含义 |
|--------|------|
| $\mathbf{a}^T \mathbf{b}$ | $\sum a_i b_i$（内积） |
| $\mathbf{a}^T \boldsymbol{\Sigma} \mathbf{b}$ | $\sum_i \sum_j a_i \Sigma_{ij} b_j$（二次型） |
| $\boldsymbol{\Sigma}^{-1}$ | 协方差矩阵的逆矩阵 |
| $\partial (\mathbf{w}^T \boldsymbol{\Sigma} \mathbf{w}) / \partial \mathbf{w}$ | $2 \boldsymbol{\Sigma} \mathbf{w}$ |
| $\partial (\mathbf{w}^T \boldsymbol{\mu}) / \partial \mathbf{w}$ | $\boldsymbol{\mu}$ |

---

## 参考文献

- Markowitz, H. (1952). Portfolio Selection. *The Journal of Finance*, 7(1), 77-91.
- Merton, R. C. (1980). On Estimating the Expected Return on the Market. *Journal of Financial Economics*, 8(4), 323-361.
- Jobson, J. D. & Korkie, B. (1980). Estimation for Markowitz Efficient Portfolios. *Journal of the American Statistical Association*, 75(371), 544-554.
- DeMiguel, V., Garlappi, L. & Uppal, R. (2009). Optimal Versus Naive Diversification. *The Review of Financial Studies*, 22(5), 1915-1953.
- Black, F. & Litterman, R. (1992). Global Portfolio Optimization. *Financial Analysts Journal*, 48(5), 28-43.
