---
tags: [量化, 回测, backtrader, 框架]
date: 2026-06-15
---

# backtrader 核心概念速查

> 你只需要这 5 个概念就能读懂 `risk_parity.py`。

---

## 0. 一句话

backtrader 做的事情：**给你数据，在每根 bar 上调用你的策略，策略决定交易什么，经纪人执行交易，最后算业绩**。

---

## 1. Cerebro（大脑）

```python
cerebro = bt.Cerebro()
cerebro.adddata(feed)           # 喂数据
cerebro.addstrategy(MyStrategy) # 塞策略
cerebro.broker.setcash(100000)  # 设本金
cerebro.run()                   # 跑回测
```

这是 backtrader 的**入口和调度器**。它负责：
1. 把数据一条条推给策略
2. 管理经纪人（订单、持仓、现金）
3. 触发分析器（算指标）

**类比**：Cerebro 就像 Python 的 `main()`——它把所有组件串起来。

---

## 2. Data Feed（数据流）

```python
class ETFData(bt.feeds.PandasData):
    lines = ("mom", "vol", "ram")
    params = (
        ("open", "Open"),
        ("close", "Close"),
        ("mom", "mom"),      # DataFrame 列名 → backtrader line
        ("vol", "vol"),
        ("ram", "ram"),
    )
```

**Lines** 是 backtrader 的核心抽象。每一条数据有若干 line：
- 标准：`datetime`, `open`, `high`, `low`, `close`, `volume`
- 自定义：`mom`, `vol`, `ram`

访问方式：
```python
d.close[0]   # 当前 bar 的收盘价
d.close[-1]  # 上一根 bar
d.mom[0]     # 当前 bar 的动量值
```

**[0] 永远代表当前 bar**，[-1] 是上一根，[-2] 是更早的。这是 backtrader 最重要的约定。

**多资产怎么处理？**
```python
for d in self.datas:        # 遍历所有数据
    name = d._name          # 数据的名字（如 "510300"）
    print(d.close[0])       # 这只资产当前 bar 的收盘价
```

---

## 3. Strategy（策略）

```python
class MyStrategy(bt.Strategy):
    params = (("method", "equal-weight"),)

    def __init__(self):
        # 初始化指标（可选）
        pass

    def next(self):
        # 每根 bar 都执行一次
        # 这里决定交易什么
        # self.datas[0] = 第一条数据
        # self.datas[1] = 第二条...
        pass
```

**`__init__` vs `next()` 的分工**：

| 方法 | 何时执行 | 用来做什么 |
|------|---------|-----------|
| `__init__` | 开始前执行一次 | 创建指标、初始化变量 |
| `next()` | 每根 bar 执行一次 | 读当前数据、算权重、下单 |

在我们的 `risk_parity.py` 中，指标（mom, vol, ram）已经在 pandas 里算好了，所以 `__init__` 只记录一个空字典。

---

## 4. order_target_percent（调仓）

这是多资产策略最重要的方法：

```python
for d in self.datas:
    target = weights.get(d._name, 0.0)
    self.order_target_percent(d, target)
```

**含义**："把这只资产的目标仓位调到 target%"

- 如果当前持有 30%，目标 40% → 买入 10%
- 如果当前持有 50%，目标 40% → 卖出 10%
- 如果当前持有 0%，目标 0% → 什么都不做

**为什么用它而不是 buy/sell？**

因为 `buy()`/`sell()` 是"买 N 股/卖 N 股"——你需要在交易前把权重换算成股数。
`order_target_percent` 直接接受百分比，内部自动换算，**适合每日再平衡策略**。

---

## 5. 生命周期

一根 bar 的完整生命周期：

```
next() 被调用
  → 读数据 (d.close[0], d.vol[0], ...)
  → 算目标权重
  → order_target_percent()  下单
    ↓
backtrader 用下一根 bar 的 open 执行订单
  → 更新持仓、现金
  → 下一根 bar → 回到 next()
```

**关键**：`next()` 里看的 `d.close[0]` 是**当前 bar**，但下单的执行价是**下一根 bar 的 open**。这模拟了真实交易中的"看到收盘价，明天开盘下单"。

---

## 完整流程图

```
DataFeed ──→ Cerebro ──→ Strategy.next()
  ↑                          │
  │                  计算目标权重
  │                          │
  │                  order_target_percent()
  │                          │
  │                  经纪人执行（下根 bar open）
  │                          │
  └────── 下一根 bar ────────┘
                            │
                     回测结束 → Analyzer 出报表
```

---

## 相关笔记

- [[bt-portfolio-allocation|bt 策略实现讲解]] — `risk_parity.py` 逐段解读
- [[../notes/portfolio-allocation|组合分配笔记]] — 回测结果
