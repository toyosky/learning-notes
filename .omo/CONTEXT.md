# Project Context

## Remote Repositories
- **Primary**: GitHub (SSH) — `git@github.com:toyosky/learning-notes.git`
- **Mirror**: Gitee (HTTPS) — `https://gitee.com/yin_river/learning-notes.git`
- Git User: chenyou <1291929850@qq.com>
- Branch: main

## Authentication
- GitHub: SSH key (`~/.ssh/github_ed25519`)
- Gitee: Credential store (`~/.git-credentials`)

## Directory Structure (English filenames, Chinese content)
```
0-index/roadmap.md                — 学习路线图（MOC）
1-ai-learning/
  1.1-transformer-internals.md   — 大模型内部结构
  1.2-llm-to-vlm.md             — 多模态大模型入门
  1.3-lora-intro.md             — LoRA 微调入门
  1.4-lora-math.md              — LoRA 数学原理
  1.5-vlm-driving-analysis.md   — VLM-Driving 项目分析
2-quant-trading/
  README.md                     — 量化交易笔记索引
  01-data/                      — 数据获取
    notes/akshare-basics.md     — akshare 数据获取基础
    deep/forward-vs-backward-adjustment.md — 前复权 vs 后复权
    code/data_fetcher.py        — 数据获取脚本
  02-backtest/                  — 策略回测
    notes/dca-backtest.md       — DCA 定投回测
     notes/ma-crossover-oxq.md   — oxq 均线交叉策略
     notes/portfolio-allocation.md — 等权 vs 风险平价 vs 动量排名
    code/macro_analysis.py      — 三资产宏观分析
     code/etf_comparison_300_nasdaq.py — 沪深300 vs 纳指100
     code/risk_parity.py         — 风险平价 & 动量排名（三策略对比）
     code/dca_backtest.py        — DCA 回测脚本
     code/ma_strategy.py         — 均线策略脚本
  assets/                       — 图表资源
    correlation-heatmap.png     — 相关性热力图
    portfolio-comparison.png    — 组合收益对比图
    etf-comparison-300-nasdaq.png — ETF 归一化走势
```

## Python Environment
- **工具**: uv (v0.11.19)
- **Python**: 3.12.13 (via `uv python install 3.12`)
- **虚拟环境**: `2-quant-trading/.venv/`
- **创建命令**: `cd 2-quant-trading && uv venv --python 3.12 .venv`
- **运行脚本**: `.venv/bin/python 02-backtest/code/macro_analysis.py`

### 关键依赖
```
akshare>=1.18.64      — A股/ETF 数据（新浪源）
pandas>=3.0.3         — 数据处理
numpy>=2.4.6          — 数值计算
matplotlib>=3.11.0    — 图表绘制
open-xquant==0.1.0    — 量化回测框架
```

### 安装依赖
```bash
UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple uv pip install --python .venv/bin/python akshare matplotlib
uv pip install --python .venv/bin/python git+https://github.com/xingwudao/open-xquant.git
```

## Data Source Notes
- **akshare 默认源** (东方财富): 当前环境连接不稳定
- **akshare 新浪源** (`fund_etf_hist_sina`): 稳定可用
- **513100 拆股**: 2022-01-14 进行 1:5 拆股，需手动修正历史价格
- **Yahoo Finance**: 限流严重，不推荐

## GitHub Pages 文档站

笔记通过 **MkDocs + Material 主题** 构建为静态站点，自动部署到 GitHub Pages。

### 站点地址
`https://toyosky.github.io/learning-notes`

### 自动部署机制
- **触发**：`git push main` 自动触发 GitHub Actions
- **工作流**：`.github/workflows/deploy-pages.yml`
- **流程**：`pip install mkdocs-material` → `mkdocs build` → `actions/deploy-pages` 推 `gh-pages` 分支
- **耗时**：约 1-2 分钟

### 关键配置
- **`mkdocs.yml`** — 站点配置文件（主题/导航/MathJax/插件）
- **`docs/`** — 构建源目录，内含 `README.md` 和子目录的 **symlink** 指向仓库根目录（不破坏 Obsidian 结构）
- **MathJax 3** — LaTeX `$$` 公式渲染

### 本地预览
```bash
mkdocs serve    # 访问 http://127.0.0.1:8000
```

### 注意事项
- 新增笔记时需同步更新 `mkdocs.yml` 的 `nav:` 配置
- 页面间的 `[[wiki-links]]` 由 `mkdocs-roamlinks-plugin` 处理，部分相对路径链接可能不生效（不影响阅读）
- 构建不通过 `--strict`，预存的链接警告不会阻断部署
- `.venv/`、`.omo/`、`.obsidian/` 等已在 `exclude_docs` 排除

## Workflow
```bash
# 提交笔记（自动触发 GitHub Pages 更新）
git add -A && git commit -m "描述修改内容"
git push github main     # 推 GitHub（触发 Pages 部署）

# 新增笔记后，记得更新：
#   - mkdocs.yml 的 nav:
#   - 0-index/roadmap.md 中的链接
```

## Notes
- 文件名使用纯英文，避免 GitHub App 中文编码问题
- 文件内容保持中文标题和正文
- Do NOT commit large binary files (>50 MB) to the repo
- .venv 目录已在 .gitignore 中排除
