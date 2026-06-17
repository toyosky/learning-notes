---
tags: [量化, 数学, 风险平价, MRC, RC, 资产配置]
date: 2026-06-15
---

# 风险贡献的数学分解：MRC 与 RC

> **写给谁**：已经理解了组合方差公式，想进一步拆解"每只资产到底贡献了多少风险"的读者。
> **阅读目标**：掌握边际风险贡献（MRC）和总风险贡献（RC）的数学定义、推导和经济含义。

---

## 目录

- [边际风险贡献（MRC）](#边际风险贡献mrc)
- [总风险贡献（RC）](#总风险贡献rc)
- [关键性质：RC 之和 = 组合波动率](#关键性质rc-之和--组合波动率)
- [完整数值示例](#完整数值示例)
- [相关笔记](#相关笔记)

---

## 边际风险贡献（MRC）

### 核心问题

如果我给资产 $i$ 增加一丁点权重（从 $w_i$ 增加到 $w_i + \Delta$），组合波动率 $\sigma_p$ 会变多少？

这就是**边际风险贡献**（Marginal Risk Contribution, MRC）：

$$
\operatorname{MRC}_i = \frac{\partial \sigma_p}{\partial w_i}
$$

它回答的问题是：**"组合波动率对第 i 个权重的敏感度是多少？"**

### 推导

我们从 $\sigma_p = \sqrt{w^\mathsf{T} \Sigma w}$ 出发。对 $w_i$ 求偏导，用到两个知识点：

1. **链式法则**：$\frac{\partial}{\partial w_i} \sqrt{f} = \frac{1}{2\sqrt{f}} \cdot \frac{\partial f}{\partial w_i}$
2. **二次型求导**：$\frac{\partial}{\partial w_i} (w^\mathsf{T} \Sigma w) = 2 (\Sigma w)_i$

其中 $(\Sigma w)_i$ 是向量 $\Sigma w$ 的第 $i$ 个分量，展开为：

$$
(\Sigma w)_i = \sum_{j=1}^{n} w_j \sigma_i \sigma_j \rho_{ij}
$$

结合起来：

$$
\operatorname{MRC}_i = \frac{\partial \sigma_p}{\partial w_i}
= \frac{1}{2\sigma_p} \cdot 2 (\Sigma w)_i
= \frac{(\Sigma w)_i}{\sigma_p}
$$

展开分子：

$$
\operatorname{MRC}_i = \frac{\sum_{j=1}^{n} w_j \sigma_i \sigma_j \rho_{ij}}{\sigma_p}
$$

### 直观理解

- MRC 大的资产 → "增加它的权重会显著提高组合波动"
- MRC 小的资产 → "增加它的权重对组合波动影响不大"

**MRC 的核心驱动因素**：
1. **自身波动率 $\sigma_i$**：波动越大的资产，边际影响越大
2. **与组合的关联度**：$(\Sigma w)_i$ 包含了该资产与所有其他资产的协方差加权和

换句话说，MRC 不只是看单只资产的波动，还看它跟组合中其他资产如何互动。

### 两资产情形的 MRC

两个资产时，MRC 的表达式非常直观：

$$
\operatorname{MRC}_1 = \frac{w_1 \sigma_1^2 + w_2 \sigma_1 \sigma_2 \rho}{\sigma_p}
$$

**解读**：
- $w_1 \sigma_1^2$：资产1自身波动对 MRC 的贡献
- $w_2 \sigma_1 \sigma_2 \rho$：资产1与资产2的联动对 MRC 的贡献
- 如果 $\rho$ 为正且 $w_2$ 较大，即使资产1本身波动不大，它也会因为与资产2的正相关而拥有较大的 MRC

---

## 总风险贡献（RC）

### 定义

边际风险贡献回答的是"增加一单位权重的影响"，但资产 $i$ 当前已经有一个权重 $w_i$ 了。
**它实际贡献了多少风险？**

总风险贡献（Risk Contribution, RC）的定义很自然：

$$
\operatorname{RC}_i = w_i \cdot \operatorname{MRC}_i = w_i \cdot \frac{(\Sigma w)_i}{\sigma_p}
$$

### 为什么要乘 $w_i$？

考虑一个极端情况：如果 $w_i = 0$（我没买这只资产），那它对组合的风险贡献应该是 0，无论它的 MRC 多大。乘 $w_i$ 就保证了这一点。

另一个极端：如果 $w_i$ 很大，即使 MRC 不大，它占的"风险份额"也可能很大。

### 展开形式

把 RC 全部展开：

$$
\operatorname{RC}_i = \frac{w_i^2 \sigma_i^2}{\sigma_p} + \frac{\sum_{j \neq i} w_i w_j \sigma_i \sigma_j \rho_{ij}}{\sigma_p}
$$

**第一项**：资产自身的方差贡献
**第二项**：资产与其他资产的协方差贡献

这个展开在后面理解风险平价条件时非常关键。

---

## 关键性质：RC 之和 = 组合波动率

这里有一个非常漂亮的数学性质——**欧拉齐次函数定理(Euler's Homogeneous Function Theorem)**：

$$
\sum_{i=1}^{n} \operatorname{RC}_i = \sum_{i=1}^{n} w_i \cdot \frac{\partial \sigma_p}{\partial w_i} = \sigma_p
$$

### 为什么这个性质成立？

$\sigma_p(w)$ 是 $w$ 的一次齐次函数：$\sigma_p(tw) = t \sigma_p(w)$（权重翻倍，波动率也翻倍）。

根据欧拉定理，一次齐次函数满足：

$$
\sum_i w_i \frac{\partial f}{\partial w_i} = f(w)
$$

代入 $f = \sigma_p$ 即得。

### 验证

直接计算验证：

$$
\sum_{i=1}^{n} w_i \cdot \frac{(\Sigma w)_i}{\sigma_p}
= \frac{1}{\sigma_p} \sum_{i=1}^{n} w_i (\Sigma w)_i
= \frac{1}{\sigma_p} \cdot w^\mathsf{T} \Sigma w
= \frac{1}{\sigma_p} \cdot \sigma_p^2
= \sigma_p
$$

**这个性质为什么重要？**

因为 $\sigma_p$ 是"组合总风险"，现在我们可以说：

$$
\sigma_p = \operatorname{RC}_1 + \operatorname{RC}_2 + \cdots + \operatorname{RC}_n
$$

组合总波动率 = 各资产风险贡献的总和。

**数值例子**：假设 $\sigma_p = 15\%$，三只资产的 RC 分别是 5%、5%、5% → 风险平价！
但如果 RC 是 12%、2%、1% → 第一只资产主导了组合风险，"等权"实际上是"不等风险"。

---

## 完整数值示例

让我们用三个资产的完整数据计算 MRC 和 RC，直观感受数字。

### 设定

| 资产 | 权重 $w_i$ | 波动率 $\sigma_i$ |
|------|-----------|-----------------|
| A | 40% | 20% |
| B | 40% | 15% |
| C | 20% | 8% |

相关系数矩阵：

| | A | B | C |
|---|----|----|----|
| A | 1.0 | 0.6 | -0.2 |
| B | 0.6 | 1.0 | 0.0 |
| C | -0.2 | 0.0 | 1.0 |

### 计算协方差矩阵 $\Sigma$

$$
\begin{aligned}
\Sigma_{AA} &= 0.20^2 = 0.0400 \\
\Sigma_{BB} &= 0.15^2 = 0.0225 \\
\Sigma_{CC} &= 0.08^2 = 0.0064 \\
\Sigma_{AB} &= 0.20 \times 0.15 \times 0.6 = 0.0180 \\
\Sigma_{AC} &= 0.20 \times 0.08 \times (-0.2) = -0.0032 \\
\Sigma_{BC} &= 0.15 \times 0.08 \times 0.0 = 0.0000 \\
\end{aligned}
$$

### 计算 $(\Sigma w)$

$$
\begin{aligned}
(\Sigma w)_A &= 0.40 \times 0.0400 + 0.40 \times 0.0180 + 0.20 \times (-0.0032) = 0.02256 \\
(\Sigma w)_B &= 0.40 \times 0.0180 + 0.40 \times 0.0225 + 0.20 \times 0.0000 = 0.01620 \\
(\Sigma w)_C &= 0.40 \times (-0.0032) + 0.40 \times 0.0000 + 0.20 \times 0.0064 = 0.00000 \\
\end{aligned}
$$

### 计算组合波动率 $\sigma_p$

$$
\sigma_p^2 = w^\mathsf{T} \Sigma w = 0.40 \times 0.02256 + 0.40 \times 0.01620 + 0.20 \times 0.00000 = 0.015504
$$

$$
\sigma_p = \sqrt{0.015504} = 0.1245 = 12.45\%
$$

### 计算 MRC 和 RC

| 资产 | $(\Sigma w)_i$ | $\operatorname{MRC}_i$ | $\operatorname{RC}_i$ | RC 占比 |
|------|---------------|----------------------|---------------------|---------|
| A | 0.02256 | 0.02256/0.1245 = **0.1812** | 0.40 × 0.1812 = **0.0725** | **58.2%** |
| B | 0.01620 | 0.01620/0.1245 = **0.1301** | 0.40 × 0.1301 = **0.0521** | **41.8%** |
| C | 0.00000 | 0.00000/0.1245 = **0.0000** | 0.20 × 0.0000 = **0.0000** | **0.0%** |

### 验证 $\sum \operatorname{RC}_i = \sigma_p$

$$
0.0725 + 0.0521 + 0.0000 = 0.1245 = \sigma_p
$$

### 关键解读

1. **资产A（40%权重）贡献了 58.2% 的风险**——因为它波动大（20%）且与B高度正相关（$\rho=0.6$）
2. **资产C（20%权重）贡献了0%的风险**——虽然它有8%的波动率，但权重小且与A负相关（$\rho=-0.2$），$(\Sigma w)_C$ 正好为0
3. **风险分配极度不均**：A的RC是C的无限倍（C为0），但权重只差了2倍

> 这个例子清晰地展示了：**资金权重 ≠ 风险贡献**。风险平价的目标就是让所有 RC 相等。

### Python 验证代码

```python
import numpy as np

# 设定
w = np.array([0.40, 0.40, 0.20])
sigma = np.array([0.20, 0.15, 0.08])
rho = np.array([[1.0, 0.6, -0.2],
                [0.6, 1.0, 0.0],
                [-0.2, 0.0, 1.0]])

# 协方差矩阵
Sigma = np.outer(sigma, sigma) * rho

# 组合波动率
sigma_p = np.sqrt(w @ Sigma @ w)

# MRC 和 RC
Sigma_w = Sigma @ w
MRC = Sigma_w / sigma_p
RC = w * MRC

print(f"组合波动率: {sigma_p:.4f} = {sigma_p*100:.2f}%")
print(f"RC 之和: {RC.sum():.4f} = {RC.sum()*100:.2f}% (应等于 {sigma_p:.4f})")
for i, name in enumerate(['A', 'B', 'C']):
    print(f"{name}: MRC={MRC[i]:.4f}, RC={RC[i]:.4f} ({RC[i]/sigma_p*100:.1f}%)")
```

输出：
```
组合波动率: 0.1245 = 12.45%
RC 之和: 0.1245 = 12.45% (应等于 0.1245)
A: MRC=0.1812, RC=0.0725 (58.2%)
B: MRC=0.1301, RC=0.0521 (41.8%)
C: MRC=0.0000, RC=0.0000 (0.0%)
```

---

## 相关笔记

- [[risk-parity-intuition|风险平价直觉：等权 ≠ 等风险]] — 前置：组合方差公式
- [[risk-parity-solution|风险平价条件与求解]] — 下一步：用 RC = RC 解出权重
- [[../notes/portfolio-allocation|组合分配总览]] — 回测实现与结果对比
