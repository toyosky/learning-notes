---
tags: [量化, 回测, backtrader, 风险平价, 动量, 代码讲解]
date: 2026-06-15
---

# `risk_parity.py` 代码讲解

> 把 `risk_parity.py` 从头到尾拆开讲，每段代码对应哪个数学概念。
> 配合 [[risk-parity-derivation]] 和 [[momentum-ranking-derivation]] 阅读。

---

## 设计总览

```
pandas 预处理            →  backtrader 回测
─────────────────────────────────────────
  fetch_etf_data()       →  ETFData (PandasData)
  e: 算 log_return         →  额外的 lines: mom, vol, ram
  f: 算 mom(20)           →  
  f: 算 vol(20)           →  AssetAllocationStrategy
  f: 算 ram               →    _equal_weight()
                            →    _risk_parity()
                            →    _momentum_rank()
```

**为什么这样分？**

数学推导中的指标计算（对数收益率、20 日滚动均值、波动率估计）是纯数据处理问题，适合 pandas 直接做。策略执行（每日调仓权重）需要模拟订单、现金管理、逐日净值——这是回测框架的价值。

这样分离后，你只需要关注两块东西：
1. **pandas 部分**：对应数学推导的前 4 节
2. **backtrader 部分**：对应"如何把数学结论变成交易决策"

---

## 第 1 块：数据准备（pandas）

```python
def build_panel() -> dict[str, pd.DataFrame]:
    data = {}
    for symbol in ("510300", "513100", "518880"):
        df = fetch_etf_data(symbol=symbol, ...)
        
        # 对数收益率  ← 对应 momentum-ranking-derivation §1.3
        df["log_return"] = np.log(df["Close"] / df["Close"].shift(1))

        # 20 日动量    ← 对应 momentum-ranking-derivation §2.2
        df["mom"] = df["log_return"].rolling(20).mean()

        # 20 日波动率  ← 对应 momentum-ranking-derivation §3.1
        df["vol"] = df["log_return"].rolling(20).std(ddof=1)

        # RAM 分数     ← 对应 momentum-ranking-derivation §4.1
        df["ram"] = df["mom"] / df["vol"]

        data[symbol] = df
    return data
```

### 逐行解读

**`fetch_etf_data()`** — 从 `data_fetcher` 获取行情数据。
返回的 DataFrame 有 `Open/High/Low/Close/Volume` 五列。

**`log_return = ln(P_t / P_{t-1})`** — 对数收益率。
- `shift(1)` 把价格序列整体下移一行，让 `Close / Close.shift(1)` 计算"今天的收盘价比昨天"
- 第一行因为没有前一天的价格，结果为 NaN

**`rolling(20).mean()`** — 过去 20 天的平均值。
- 前 19 天不够20个数据，结果是 NaN
- 第 20 天开始有值
- 这就是动量：`mom_t(20) = (1/20) * sum(r_t, r_{t-1}, ..., r_{t-19})`

**`rolling(20).std(ddof=1)`** — 有偏 → 无偏校正。
- `ddof=1` 就是贝塞尔校正（用 N-1 做分母，不是 N）
- 对应推导中的 $s^2 = \frac{1}{N-1}\sum(r_i-\bar{r})^2$

**为什么不在 backtrader 里计算这些指标？**

可以在 backtrader 里用 `bt.ind.SMA`, `bt.ind.StdDev` 算，但在 pandas 里算更清晰：
- 每步计算都对应推导中的一行公式
- 出错时容易调试（打印 df 检查中间结果）
- backtrader 的指标系统是做高频策略用的，这里不需要

---

## 第 2 块：数据馈送（backtrader 接入）

```python
class ETFData(bt.feeds.PandasData):
    lines = ("mom", "vol", "ram")
    params = (
        ("datetime", None),
        ("open", "Open"), ("high", "High"),
        ("low", "Low"), ("close", "Close"), ("volume", "Volume"),
        ("mom", "mom"), ("vol", "vol"), ("ram", "ram"),
    )
```

### 它在做什么？

`PandasData` 是 backtrader 自带的适配器，把 pandas DataFrame 转成 backtrader 能吃的格式。

默认情况下，`PandasData` 只认识 `datetime, open, high, low, close, volume` 这些标准列。

**我们额外传了 3 列（`mom, vol, ram`）所以需要子类化。**

```python
lines = ("mom", "vol", "ram")   # 声明新增的 line 名字
params = (("mom", "mom"), ...)  # ("backtrader line 名", "DataFrame 列名")
```

之后在策略里就能直接用了：

```python
d.mom[0]   # 当前 bar 的动量
d.vol[0]   # 当前 bar 的波动率
d.ram[0]   # 当前 bar 的 RAM 分数
```

---

## 第 3 块：策略框架

```python
class AssetAllocationStrategy(bt.Strategy):
    params = (("method", "equal-weight"),)

    def next(self):
        # 1. 收集当前所有资产的指标
        vols, rams = {}, {}
        for d in self.datas:
            vols[d._name] = d.vol[0]
            rams[d._name] = d.ram[0]

        # 2. 按方法算权重
        if self.params.method == "equal-weight":
            weights = self._equal_weight()
        elif ...

        # 3. 执行调仓
        for d in self.datas:
            target = weights.get(d._name, 0.0)
            self.order_target_percent(d, target)
```

### `params`：策略参数

```python
params = (("method", "equal-weight"),)
```

这是 backtrader 的参数系统。三个策略用同一个类，只换参数：

```python
cerebro.addstrategy(AssetAllocationStrategy, method="equal-weight")
cerebro.addstrategy(AssetAllocationStrategy, method="risk-parity")
cerebro.addstrategy(AssetAllocationStrategy, method="momentum-rank")
```

### `next()`：每根 bar 的流程

**1. 收集数据**
```python
for d in self.datas:
    vols[d._name] = d.vol[0]
```
`self.datas` 是策略中所有数据的列表（顺序跟 `cerebro.adddata()` 一致）。
`d._name` 是我们在加载数据时设的名字（如 `"510300"`）。
`d.vol[0]` 是当前 bar 的波动率值。

**2. 算权重**
三种分配方法用三个静态方法实现，互不影响。

**3. 下单**
```python
self.order_target_percent(d, target)
```
这个调用告诉 backtrader：我希望把这只资产的仓位调到 `target` 比例。

backtrader 会自动计算：
- 当前持仓市值比例 → 按 (target - 当前比例) × 总资产 下单
- 用下一根 bar 的 open 价执行
- 如果 target=0 → 清仓该资产

---

## 第 4 块：三种分配方法

### 等权（Equal Weight）

```python
@staticmethod
def _equal_weight():
    n = len(SYMBOLS)
    return {name: 1.0 / n for name in SYMBOLS}
```

最简单。永远返回 `{"510300": 0.333, "513100": 0.333, "518880": 0.333}`。

**数学对应**：不需要公式。等权是"无信息先验"——你对任何资产没有偏好。

---

### 风险平价（Risk Parity）

```python
@staticmethod
def _risk_parity(vols):
    # 过滤掉缺失值
    vols_clean = {k: v for k, v in vols.items()
                  if v is not None and v > 0 and not np.isnan(v)}

    if not vols_clean:
        return {name: 1.0 / len(SYMBOLS) for name in SYMBOLS}

    inv = {k: 1.0 / v for k, v in vols_clean.items()}
    total = sum(inv.values())
    return {k: inv[k] / total for k in inv}
```

**数学对应**：`risk-parity-derivation.md` §5.2

推导结论：当 $\rho = 0$ 时，风险平价条件 $w_1\sigma_1 = w_2\sigma_2$ 的解是 $w_i \propto 1/\sigma_i$。

```python
inv = {k: 1.0 / v for k, v in vols_clean.items()}  # w_i ∝ 1/σ_i
total = sum(inv.values())
return {k: inv[k] / total for k in inv}              # 归一化到和为 1
```

**为什么这对应的是"零阶近似"？**

回顾推导，$w_i \propto 1/\sigma_i$ 只在 $\rho=0$ 时才严格成立。
当 $\rho \neq 0$ 时，完整方程组为 $w_i(\Sigma w)_i = w_j(\Sigma w)_j$，其中交叉项 $w_i w_j \sigma_i \sigma_j \rho_{ij}$ 不可忽略。

这里用了简化版：**只考虑自身波动率，忽略了资产间相关性的修正**。

---

### 动量排名（Momentum Ranking）

```python
@staticmethod
def _momentum_rank(rams):
    pos = {k: v for k, v in rams.items()
           if v is not None and v > 0 and not np.isnan(v)}
    if not pos:
        return {}                      # 全现金
    total = sum(pos.values())
    return {k: pos[k] / total for k in pos}
```

**数学对应**：`momentum-ranking-derivation.md` §7

```python
pos = {k: v for k, v in rams.items() if v > 0}  # filter_negative = True
```

这对应 `TopNRankingOptimizer(filter_negative=True, n=3)`：
- `filter_negative=True`：只保留 RAM > 0 的资产
- `n=3`：实际上三个标的其实都能选（但 RAM ≤ 0 的会被剔除）

```python
return {k: pos[k] / total for k in pos}
```

对应权重公式：

$$w_i = \frac{\operatorname{ram}_i^+}{\sum_{j} \operatorname{ram}_j^+}$$

当所有 RAM ≤ 0 时，返回 `{}`（全现金）——对应 $S = \varnothing$ 的情况。

**为什么不实现 `max_weight`？**

这里没做截断。三只资产的情况下，单只权重不太可能超过 100%。如果以后资产多了需要加约束：

```python
max_w = 0.5
clipped = {k: min(v, max_w) for k, v in weights.items()}
# 把超过的权重分配给现金
excess = sum(weights.values()) - sum(clipped.values())
if excess > 0:
    clipped["CASH"] = excess
```

---

## 第 5 块：backtrader 指标计算说明

### `backtrader.analyzers.SharpeRatio`

`bt.analyzers.SharpeRatio` 的默认参数：
- 年化因子：252（交易日）
- 无风险利率：通过 `riskfreerate` 参数传入（默认 0）
- 使用对数收益率还是简单收益率：框架默认

三个策略使用相同的 analyzer 配置，所以夏普比率的**相对排名**是可靠的（动量排名 > 风险平价 > 等权）。

### 订单执行模型

`order_target_percent` 在下一根 bar 的开盘价成交（`open` 价格），这是 backtrader 的默认行为。这意味着回测收益比理想化的"当前 bar 收盘价成交"略低 1-2%，但更接近实盘。

---

## 第 6 块：运行全部三个策略

```python
methods = ["equal-weight", "risk-parity", "momentum-rank"]
for method in methods:
    cerebro = run_backtest(method, panel)
    results[method] = {
        "final_value": cerebro.broker.getvalue(),
        "total_return": (cerebro.broker.getvalue() / INITIAL_CASH) - 1,
    }
```

这里为每个方法**独立运行一次 Cerebro**，不是并行运行三个策略在一个 Cerebro 里。

为什么不放在一个 Cerebro 里？
- 一个 Cerebro 跑多个策略时，它们是共享现金池的
- 我们要的是：三个独立的 10 万元账户各跑各的
- 所以每个方法单独创建一个 Cerebro

---

## 对照阅读

| 你想理解什么 | 读哪篇 |
|-------------|--------|
| backtrader 的最小概念 | [[backtrader-intro]] |
| 风险平价的数学推导 | [[risk-parity-derivation]] |
| 动量排名的数学推导 | [[momentum-ranking-derivation]] |
| 回测结果和对比 | [[../notes/portfolio-allocation]] |
