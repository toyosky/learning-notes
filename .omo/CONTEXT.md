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
  2.1-data-akshare.md           — 数据获取基础
  2.2-dca-backtest.md           — 简单定投回测
  2.3-ma-crossover-oxq.md       — 均线交叉策略回测
  strategy-comparison.png       — 策略对比图
```

## Workflow
```bash
# 提交笔记
git add -A && git commit -m "描述修改内容"
git push github main     # 推 GitHub
git push origin main     # 同步 Gitee

# 新增笔记后，记得更新 0-index/roadmap.md 中的链接
```

## Notes
- 文件名使用纯英文，避免 GitHub App 中文编码问题
- 文件内容保持中文标题和正文
- Do NOT commit large binary files (>50 MB) to the repo
