---
tags: [量化, 数学, 风险平价, 求解, 数值方法, 资产配置]
date: 2026-06-15
---

# 风险平价条件与求解

> **写给谁**：已经理解 MRC 和 RC 的概念，想知道如何从"RC 相等"解出权重的读者。
> **阅读目标**：掌握风险平价条件的数学形式、两资产封闭解、为什么一般情况需要数值求解、以及波动率倒数加权的适用边界。

---

## 目录

- [风险平价条件](#风险平价条件)
- [两资产特例：封闭解](#两资产特例封闭解)
- [波动率倒数加权的含义](#波动率倒数加权的含义)
- [为什么一般情况没有解析解](#为什么一般情况没有解析解)
- [数值求解方法](#数值求解方法)
- [回头看：波动率倒数是零阶近似](#回头看波动率倒数是零阶近似)
- [延伸：风险预算](#延伸风险预算)
- [附录：向量/矩阵速查](#附录向量矩阵速查)
- [相关笔记](#相关笔记)

---

## 风险平价条件

### 核心等式

风险平价的定义就是：**让每只资产的风险贡献相等**。

$$
\operatorname{RC}_1 = \operatorname{RC}_2 = \cdots = \operatorname{RC}_n
$$

代入 RC 的定义：

$$
\frac{w_1 (\Sigma w)_1}{\sigma_p} = \frac{w_2 (\Sigma w)_2}{\sigma_p} = \cdots = \frac{w_n (\Sigma w)_n}{\sigma_p}
$$

消去所有分母的 $\sigma_p$：

$$
w_1 (\Sigma w)_1 = w_2 (\Sigma w)_2 = \cdots = w_n (\Sigma w)_n
$$

加上权重之和为 1 的约束 $\sum w_i = 1$，这就是风险平价的完整数学定义。

### 展开来看

对于资产 $i$：

$$
w_i (\Sigma w)_i = w_i \left( \sum_{j=1}^{n} w_j \sigma_i \sigma_j \rho_{ij} \right)
= w_i^2 \sigma_i^2 + \sum_{j \neq i} w_i w_j \sigma_i \sigma_j \rho_{ij}
$$

**第一项** $w_i^2 \sigma_i^2$：资产自身的方差贡献
**第二项** $\sum_{j \neq i} w_i w_j \sigma_i \sigma_j \rho_{ij}$：与其它资产的交叉贡献

### 这为什么是一个非线性方程组？

展开 $w_1 (\Sigma w)_1$：

$$
w_1 (\Sigma w)_1 = w_1^2 \sigma_1^2 + w_1 w_2 \sigma_1 \sigma_2 \rho_{12} + \cdots + w_1 w_n \sigma_1 \sigma_n \rho_{1n}
$$

这里有 $w_i^2$（二次项），还有 $w_i w_j$（交叉项）。当我们让 $w_1 (\Sigma w)_1 = w_2 (\Sigma w)_2$ 时，这个等式两边都含有 **所有** 的 $w$。

换句话说：**你不能独立地确定每个 $w_i$，因为每个等式都纠缠了所有变量。** 这就是为什么风险平价一般没有封闭解。

> **例外**：当所有资产互不相关（$\rho_{ij} = 0$）时，交叉项消失，问题大幅简化。我们在下个章节推导。

### 几何直觉

想象你在平衡一个多杆天平：
- 每根杆（资产）的长度不同（波动率不同）
- 杆之间的角度不同（相关性不同）
- 你需要移动配重（调整权重）让整个系统平衡

当杆之间有角度（相关性），移动一根杆会影响其他所有杆的力矩——这就是耦合（coupling）。

---

## 两资产特例：封闭解

### 一般情况（带相关性）

两个资产，权重 $w_1$ 和 $w_2 = 1 - w_1$，相关性 $\rho$。

组合波动率：

$$
\sigma_p = \sqrt{w_1^2 \sigma_1^2 + w_2^2 \sigma_2^2 + 2 w_1 w_2 \sigma_1 \sigma_2 \rho}
$$

风险贡献：

$$
\operatorname{RC}_1 = \frac{w_1 (w_1 \sigma_1^2 + w_2 \sigma_1 \sigma_2 \rho)}{\sigma_p}
$$

$$
\operatorname{RC}_2 = \frac{w_2 (w_2 \sigma_2^2 + w_1 \sigma_1 \sigma_2 \rho)}{\sigma_p}
$$

令 $\operatorname{RC}_1 = \operatorname{RC}_2$，消去 $\sigma_p$：

$$
w_1 (w_1 \sigma_1^2 + w_2 \sigma_1 \sigma_2 \rho) = w_2 (w_2 \sigma_2^2 + w_1 \sigma_1 \sigma_2 \rho)
$$

代入 $w_2 = 1 - w_1$，得到一个关于 $w_1$ 的方程。当 $\rho \neq 0$ 时，它是一个二次方程——有解，但形式复杂，不如直接数值求解。

### 不相关的情况（$\rho = 0$）

当 $\rho = 0$ 时，交叉项消失：

$$
w_1^2 \sigma_1^2 = w_2^2 \sigma_2^2
$$

两边开方：

$$
w_1 \sigma_1 = w_2 \sigma_2
$$

代入 $w_2 = 1 - w_1$：

$$
w_1 \sigma_1 = (1 - w_1) \sigma_2
$$

解得：

$$
w_1 = \frac{\sigma_2}{\sigma_1 + \sigma_2}, \quad w_2 = \frac{\sigma_1}{\sigma_1 + \sigma_2}
$$

或者写成比例形式：

$$
\frac{w_1}{w_2} = \frac{\sigma_2}{\sigma_1}
$$

即：

$$
w_i \propto \frac{1}{\sigma_i}
$$

### 相关性的影响：一个数值扫描

用两资产 $\sigma_1=18\%, \sigma_2=3\%$，看不同相关系数下风险平价权重的变化：

| $\rho$ | $w_1$ (高波) | $w_2$ (低波) | 解读 |
|--------|-------------|-------------|------|
| -0.8 | 10.1% | 89.9% | 负相关→对冲效果好，可稍微多配高波 |
| -0.5 | 11.2% | 88.8% | |
| 0.0 | **14.3%** | **85.7%** | **波动率倒数解** |
| +0.5 | 19.8% | 80.2% | 正相关→风险叠加，必须大幅降低高波权重 |
| +0.8 | 26.5% | 73.5% | |
| +0.95 | 31.5% | 68.5% | 近似完全正相关，逼近等风险权 |

**关键观察**：
- $\rho=0$ 处的波动率倒数解是一个**中间点**，不是极端情况
- $\rho$ 为负时，高波资产因为对冲效果反而可以多配（这反直觉！）
- $\rho$ 为正时，高波资产必须大幅减仓（因为风险叠加）

---

## 波动率倒数加权的含义

让我们验证一下 $\rho=0$ 时这个解的经济直觉：

| 资产 | $\sigma$ | 风险平价权重 | 等权 |
|------|----------|------------|------|
| 沪深300 | 18% | $\frac{3}{18+3}=14.3\%$ | 50% |
| 国债 | 3% | $\frac{18}{18+3}=85.7\%$ | 50% |

**解读**：
- 等权（50/50）下，沪深300的 RC 远大于国债，组合风险被沪深300主导
- 风险平价下，国债配了 85.7%，沪深300只配了 14.3%
- 这样两者的风险贡献相等

**国债配到 85.7% 会不会太多？**
不——因为风险平价只关心风险贡献相等，不关心资金分配。
85.7% × 3% ≈ 14.3% × 18%，两者波动量相当。

> 这是风险平价最核心也是最反直觉的特点：**高权重 ≠ 高风险**。

### 多资产数值对比

以下用三资产对比等权和风险平价（$\rho=0$ 简化版）：

| 资产 | $\sigma$ | 等权 $w$ | 等权 RC | 风险平价 $w$ | 风险平价 RC |
|------|----------|---------|---------|-------------|-------------|
| A | 25% | 33.3% | **72%** | $1/25$ = 0.04 → 归一化: **14.3%** | **33.3%** |
| B | 15% | 33.3% | **26%** | $1/15$ = 0.067 → 归一化: **23.8%** | **33.3%** |
| C | 5% | 33.3% | **2%** | $1/5$ = 0.2 → 归一化: **61.9%** | **33.3%** |

等权下 A 贡献了 72% 的风险，C 只贡献了 2%。风险平价下三者的 RC 完全相等（各 1/3）。

---

## 为什么一般情况没有解析解

### 耦合的来源

回到一般情况下的等式：

$$
w_1 (\Sigma w)_1 = w_2 (\Sigma w)_2 = \cdots = w_n (\Sigma w)_n
$$

展开来看，每个等式左边实际是：

$$
w_i \left( \sum_{j=1}^{n} w_j \sigma_i \sigma_j \rho_{ij} \right)
$$

这里 $\rho_{ij} \neq 0$ 意味着：
- $w_i$ 的波动不仅取决于自身（$\sigma_i$），还取决于它与其他所有资产的关系
- 改变 $w_1$ 会影响 $w_2$ 的等式，改变 $w_2$ 又反过来影响 $w_1$ 的等式

这是一个**耦合的非线性方程组**。

### 与线性方程组的区别

线性方程组（如 $Ax = b$）有成熟的闭式解（矩阵求逆）。但这里：

1. **二次项**：$w_i^2 \sigma_i^2$ 来自自身方差
2. **交叉项**：$w_i w_j \sigma_i \sigma_j \rho_{ij}$ 来自协方差
3. **耦合**：每个方程包含所有变量

所以一般情况需要数值求解。

### 现实意义

**当 $\rho$ 很大时（如两个股票型 ETF），简化版 $w \propto 1/\sigma$ 会给出严重误导。**

例如沪深300（$\sigma=18\%$）和中证500（$\sigma=20\%$），两者 $\rho \approx 0.8$。

- $w \propto 1/\sigma$ 版本：$w_{300} \approx 52.6\%, w_{500} \approx 47.4\%$
- 考虑 $\rho=0.8$ 的真实版本：$w_{300}$ 会更少，$w_{500}$ 会更多（因为两者高度同向波动，一个的"风险贡献"已经包含了另一个）

**直观理解**：两只高度正相关的资产本质上在"分担"同一个风险源。在你分配风险预算时，应该把它们视为**部分重复**的风险暴露，不能独立看待。

---

## 数值求解方法

### 优化问题的形式

风险平价问题可以写成一个最小化问题：

$$
\min_{w} \sum_{i=1}^{n} \sum_{j=1}^{n} \left( w_i (\Sigma w)_i - w_j (\Sigma w)_j \right)^2
$$

约束：

$$
\sum_{i=1}^{n} w_i = 1, \quad w_i \geq 0
$$

也就是：**找一组权重，使得所有资产的 RC 两两之间差异的平方和最小**。

### 为什么不用直接解方程？

因为超过 2 个资产时，方程个数多于自由参数，方程组是**过定的**。你无法让所有 RC 严格相等（或者解不存在，或者解超出 $[0,1]$ 范围），只能最小化它们之间的差异。

> 实践中"严格相等"往往不可行，所以风险平价在 3+ 资产时是"尽量接近相等"，而不是严格相等。

### 常用算法

#### 1. 牛顿法（Newton's Method）

利用梯度和 Hessian 矩阵迭代逼近：

```python
# 伪代码
w = initial_guess()  # 例如从波动率倒数开始
for iteration in range(max_iter):
    F = compute_rc_diff(w, Sigma)      # 残差：RC_i - RC_j
    J = compute_jacobian(w, Sigma)     # Jacobian 矩阵
    delta = solve(J, -F)               # 解线性系统
    w = w + delta
    if norm(delta) < tolerance:
        break
```

- 收敛快（二次收敛），但每步需要计算 $n \times n$ Jacobian
- 对初始值敏感，可能收敛到边界解

#### 2. SQP（Sequential Quadratic Programming）

把非线性约束逐步线性化，每步解一个二次规划：

```python
# 伪代码
w = initial_guess()
for iteration in range(max_iter):
    # 在当前点线性化约束
    A = linearize_constraints(w, Sigma)
    # 解 QP 子问题
    delta = solve_qp(Hessian, gradient, A, bounds)
    w = w + delta
    if converged:
        break
```

- 适合带约束的问题（$w_i \geq 0$ 天然支持）
- 比牛顿法更稳定，但每步计算量更大

#### 3. Cyclical Coordinate Descent

轮流固定其他变量，解一个变量的方程——实现简单，对风险平价问题特别有效：

```python
# 伪代码
w = initial_guess()
for iteration in range(max_iter):
    for i in range(n):
        # 固定所有 j ≠ i，求解 w_i 使 RC_i = avg(RC)
        w_i = solve_single(w, i, Sigma)
        w[i] = clip(w_i, 0, 1)
    # 重新归一化
    w = w / sum(w)
    if converged:
        break
```

- 实现最简单，每步只需解一维方程
- 收敛较慢（线性收敛），但每次迭代计算量极小
- 对风险平价问题特别有效，因为每个子问题可以解析求解

#### 4. Python 实际实现

使用 `scipy.optimize`：

```python
import numpy as np
from scipy.optimize import minimize

def risk_parity_weights(Sigma):
    n = Sigma.shape[0]
    
    def objective(w):
        sigma_p = np.sqrt(w @ Sigma @ w)
        RC = w * (Sigma @ w) / sigma_p
        # 目标：最小化 RC 之间的方差
        return np.var(RC)
    
    constraints = [
        {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},  # sum(w) = 1
    ]
    bounds = [(0, 1)] * n  # 非负约束
    
    # 初始值：波动率倒数
    init_w = 1.0 / np.sqrt(np.diag(Sigma))
    init_w = init_w / init_w.sum()
    
    result = minimize(objective, init_w, 
                      method='SLSQP',
                      bounds=bounds, 
                      constraints=constraints)
    return result.x
```

---

## 回头看：波动率倒数是零阶近似

### 我们的简化实现做了什么

```python
inv_vols[symbol] = 1.0 / vol
total = sum(inv_vols.values())
return {symbol: iv / total for symbol, iv in inv_vols.items()}
```

等价于解 $\rho=0$ 时的风险平价。这在数学上是**零阶近似**。

### 代价是什么

1. **正的 $\rho$ 被忽略**：正相关资产的风险被低估 → 配的权重过多
2. **负的 $\rho$ 被忽略**：负相关资产的对冲效果不被利用 → 配的权重过少
3. **RC 不再相等**：简化解算出的权重代入完整 RC 公式后，RC 不相等

### 什么时候用简化版，什么时候用完整版？

| 场景 | 推荐 | 原因 |
|------|------|------|
| 资产间相关性低（跨资产类别） | 简化版 $1/\sigma$ | 相关性误差 < 简化误差 |
| 资产间相关性高（同类别） | 完整数值解 | 忽略 $\rho$ 会严重偏离 |
| $n$ 很大（>10） | 简化版 + 聚类 | 完整解不稳定，先聚类再简化 |
| 数据量不足（< 2年） | 简化版 | $\rho$ 的估计误差可能比简化误差更大 |

### 为什么实践中还是用这个简化

1. **协方差的估计误差更大**：估计 $\sigma_i$ 已经不容易（需要 20-60 个交易日），估计 $\rho_{ij}$ 需要的样本量是平方级的。用一个误差很大的 $\rho$ 做数值优化，很可能不如直接用 $\rho=0$ 的简化解。
2. **数值稳定性**：迭代求解可能不收敛或在边界震荡
3. **简洁性**：一个除法就出结果，容易解释、容易调试
4. **过拟合风险**：完整解在样本内表现好，但 $\rho$ 的时序不稳定性可能导致样本外反而更差

> 这是量化中常见的权衡：**估计偏差（bias）vs 估计方差（variance）**。
> 带 $\rho$ 的全解更精确（低偏差），但 $\rho$ 本身估计不准（高方差），最终效果可能还不如简化版。

---

## 延伸：风险预算

### 从"平等"到"预算"

风险平价是"每只资产拿相等的风险预算"。但有些时候你不想平等——比如你更看好某个行业，愿意给它多分配一些风险。

**风险预算**（Risk Budgeting）是风险平价的推广：不是让 RC 相等，而是让 RC 等于预设的比例 $b_i$（满足 $\sum b_i = 1$）：

$$
\frac{\operatorname{RC}_i}{\sigma_p} = b_i
$$

即：

$$
\frac{w_i (\Sigma w)_i}{\sigma_p^2} = b_i
$$

### 风险平价是风险预算的特例

风险平价就是 $b_i = 1/n$（每只资产拿相同的风险预算）。

### 实际应用场景

| 场景 | 风险预算设置 | 逻辑 |
|------|------------|------|
| 看好科技行业 | $b_{科技} = 40\%$, 其他均分 60% | 主动超配看好的板块 |
| 核心-卫星策略 | $b_{核心} = 70\%$（宽基指数），$b_{卫星} = 30\%$（行业ETF） | 核心稳、卫星冲 |
| 风险厌恶投资者 | $b_{债券} = 60\%$, $b_{股票} = 30\%$, $b_{商品} = 10\%$ | 给低风险资产更多预算 |
| ESG 约束 | $b_{ESG} = 50\%$ | 给符合 ESG 标准的资产双倍预算 |

### 自由度对比

| 方法 | 参数 | 自由度 |
|------|------|--------|
| 等权 | 无 | 0 |
| 风险平价 | 目标: RC 相等 | 0（由 $\Sigma$ 决定） |
| 风险预算 | 比例 $b_i$ | $n-1$ |
| 均值-方差 | 收益率预期 $\mu$ + $\Sigma$ | $2n-1$ |

自由度从低到高，灵活性和对输入误差的敏感性同步增加。

### 风险预算的数值求解

风险预算的求解与风险平价几乎相同，只需修改目标函数：

```python
def risk_budget_weights(Sigma, budgets):
    n = Sigma.shape[0]
    budgets = np.array(budgets)
    budgets = budgets / budgets.sum()  # 确保归一化
    
    def objective(w):
        sigma_p = np.sqrt(w @ Sigma @ w)
        RC = w * (Sigma @ w) / sigma_p
        target_RC = budgets * sigma_p
        return np.sum((RC - target_RC)**2)
    
    # 其余优化逻辑与风险平价相同
    ...
```

---

## 附录：向量/矩阵速查

本文用到的线性代数知识（如果你不熟悉的话）：

| 符号 | 含义 |
|------|------|
| $w = (w_1, \dots, w_n)^\mathsf{T}$ | 权重向量（列向量） |
| $w^\mathsf{T}$ | 转置（行向量） |
| $\Sigma$ | 协方差矩阵，$n \times n$ |
| $\Sigma_{ij} = \sigma_i \sigma_j \rho_{ij}$ | 矩阵元素 |
| $w^\mathsf{T} \Sigma w$ | 二次型，结果为标量 |
| $(\Sigma w)_i$ | 向量 $\Sigma w$ 的第 $i$ 个分量 |
| $\frac{\partial}{\partial w} (w^\mathsf{T} \Sigma w) = 2\Sigma w$ | 二次型求导（列向量形式） |

---

## 相关笔记

- [[risk-parity-intuition|风险平价直觉：等权 ≠ 等风险]] — 前置：组合方差公式
- [[risk-parity-decomposition|风险贡献的数学分解]] — 前置：MRC 和 RC 的定义
- [[../notes/portfolio-allocation|组合分配总览]] — 回测实现与结果对比
